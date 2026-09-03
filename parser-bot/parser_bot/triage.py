"""Read-only triage: download today's sheet, run parser-fix.sh in the bot clones, classify, predict tier."""
from __future__ import annotations

import os
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .classify import Classification, classify
from .config import Config
from .cookbook import parse_cookbook, predict_tier
from .lf_api import RateFailure
from .nights import ICT, PT
from .state import NightState


@dataclass
class TriageResult:
    lender: str
    channel: str
    downloaded: bool
    sheet: str
    classification: Classification
    tier: str
    streak: int
    hint: bool
    report_path: str


def channel_of(failure: RateFailure) -> str:
    """QM unless the builder named the NonQM parser (description carries lender.nonQMName())."""
    return "NonQM" if "NonQM" in failure.description else "QM"


class Triager:
    def __init__(self, cfg: Config, runner=subprocess.run, now=None):
        self.cfg = cfg
        self.runner = runner
        self.now = now or (lambda: datetime.now(tz=ICT))

    channel_of = staticmethod(channel_of)

    # ---- helpers -------------------------------------------------------------------------------
    def _run(self, cmd: list[str], cwd: str, timeout: int) -> subprocess.CompletedProcess:
        return self.runner(cmd, cwd=cwd, timeout=timeout, capture_output=True, text=True)

    @staticmethod
    def _new_files(root: str, since: float) -> list[str]:
        out = []
        for p in Path(root).rglob("*"):
            if p.is_file() and p.stat().st_mtime >= since:
                out.append(str(p))
        return sorted(out, key=lambda s: os.path.getmtime(s), reverse=True)

    # ---- nightly preparation -------------------------------------------------------------------
    def prepare_night(self, state: NightState) -> None:
        if state.prepared:
            return
        self._run(["git", "-C", self.cfg.moso_pricing, "pull", "--ff-only"], cwd=self.cfg.bot_root, timeout=self.cfg.prepare_sec)
        self._run(["git", "-C", os.path.join(self.cfg.bot_root, "packs"), "pull", "--ff-only"], cwd=self.cfg.bot_root, timeout=self.cfg.prepare_sec)
        self._run(["mvn", "-q", "install", "-DskipTests", "-Pjar-packaging", "-Dgwt.compiler.skip=true"],
                  cwd=self.cfg.moso_pricing, timeout=self.cfg.prepare_sec)
        state.prepared = True
        state.save()

    # ---- sheet acquisition ---------------------------------------------------------------------
    def _download(self, lender: str, channel: str) -> str:
        resources = os.path.join(self.cfg.packs_loan, "src", "test", "resources")
        t0 = time.time()
        cmd = ["./download-ratesheet.sh", lender] + (["--nonqm"] if channel == "NonQM" else []) + \
              ["--no-detect", "--no-git", "--no-java"]
        try:
            self._run(cmd, cwd=self.cfg.packs_loan, timeout=self.cfg.triage_sec)
        except subprocess.TimeoutExpired:
            return ""
        files = self._new_files(resources, t0)
        if files:
            return files[0]
        try:
            return self._gcs_fallback(lender, channel)
        except subprocess.TimeoutExpired:
            return ""

    def _gcs_fallback(self, lender: str, channel: str) -> str:
        name = lender + ("NonQM" if channel == "NonQM" else "")
        now = self.now()
        for day in {now.astimezone(ICT).date(), now.astimezone(PT).date()}:
            prefix = f"gs://{self.cfg.gcs_bucket}/history/{name}/{day:%Y}/{day:%m}/{day:%d}/"
            try:
                ls = self._run(["gsutil", "ls", prefix], cwd=self.cfg.bot_root, timeout=self.cfg.triage_sec)
            except subprocess.TimeoutExpired:
                return ""
            objects = [ln.strip() for ln in (ls.stdout or "").splitlines() if ln.strip().startswith("gs://")]
            if objects:
                dest = os.path.join("/tmp/parser-bot", lender.lower())
                os.makedirs(dest, exist_ok=True)
                try:
                    self._run(["gsutil", "cp", objects[-1], dest + "/"], cwd=self.cfg.bot_root, timeout=self.cfg.triage_sec)
                except subprocess.TimeoutExpired:
                    return ""
                local = os.path.join(dest, objects[-1].rsplit("/", 1)[-1])
                return local if os.path.exists(local) else ""
        return ""

    # ---- tests + report ------------------------------------------------------------------------
    def _run_tests(self, lender: str, sheet: str) -> tuple[str | None, str]:
        t0 = time.time()
        try:
            self._run(["./parser-fix.sh", lender, "--ratesheet", sheet, "--both"], cwd=self.cfg.packs_loan,
                      timeout=self.cfg.triage_sec)
        except subprocess.TimeoutExpired:
            return None, ""
        expected = os.path.join(self.cfg.report_dir, lender.lower(), "report.txt")
        candidates = [expected] if os.path.exists(expected) else \
            [p for p in self._new_files(self.cfg.report_dir, t0) if p.endswith("report.txt")] if os.path.isdir(self.cfg.report_dir) else []
        if not candidates:
            return None, ""
        return Path(candidates[0]).read_text(encoding="utf-8", errors="replace"), candidates[0]

    # ---- entry point ---------------------------------------------------------------------------
    def triage(self, failure: RateFailure) -> TriageResult:
        channel = self.channel_of(failure)
        sheet = self._download(failure.lender, channel)
        report, report_path = (None, "")
        if sheet:
            report, report_path = self._run_tests(failure.lender, sheet)
        c = classify(failure.description, bool(sheet), report)
        entry = None
        if os.path.exists(self.cfg.cookbook):
            entry = parse_cookbook(Path(self.cfg.cookbook).read_text(encoding="utf-8")).get(failure.lender)
        tier, streak, hint = predict_tier(entry, c.error_type) if c.cls == "LAYOUT" else ("", entry.tier_0_streak if entry else 0, False)
        return TriageResult(failure.lender, channel, bool(sheet), sheet, c, tier, streak, hint, report_path)
