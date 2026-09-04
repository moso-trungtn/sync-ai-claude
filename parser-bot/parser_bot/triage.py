"""Read-only triage: download today's sheet, run parser-fix.sh in the bot clones, classify, predict tier."""
from __future__ import annotations

import logging
import os
import re
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .classify import LAYOUT, Classification, classify
from .config import Config
from .cookbook import parse_cookbook, predict_tier
from .lf_api import RateFailure
from .nights import ICT, PT
from .state import NightState

log = logging.getLogger("parser-bot")


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


_SUREFIRE = re.compile(r"^\[ERROR\]\s+\S+\.\w+:\d+\s+»\s+(.+)$", re.M)
_JAVA_EXC = re.compile(r"^(?:[\w.]+\.)?(\w+(?:Exception|Error)):\s*(.*)$", re.M)
_ADJ_METHOD = re.compile(r"^\s*Adj:\s+AdjustmentParsersTest#(\w+)", re.M)
_RATE_METHOD = re.compile(r"^\s*Rate:\s+RateParserTest#(\w+)", re.M)


def surefire_cause(log_text: str) -> str:
    """One line naming what broke, from a parser-fix maven log: the surefire summary (`» ...`) or the first Java exception."""
    text = log_text or ""
    summary = ""
    m = _SUREFIRE.search(text)
    if m:
        summary = m.group(1).strip()
        if not summary.endswith("..."):
            return summary
    m = _JAVA_EXC.search(text)
    if m:
        msg = m.group(2).strip()
        if not msg:
            rest = text[m.end():].splitlines()
            msg = next((ln.strip() for ln in rest if ln.strip() and not ln.strip().startswith("at ")), "")
        full = f"{m.group(1)}: {msg}".rstrip(": ")
        return full if msg else (summary or full)
    return summary


def _pick(methods: list[str], channel: str) -> str:
    """The test method matching the channel: NonQM wants a name containing 'NonQM', QM wants one without."""
    wanted = [m for m in methods if ("NonQM" in m) == (channel == "NonQM")]
    return (wanted or methods)[0]


def test_args(lender_info_output: str, channel: str) -> list[str] | None:
    """parser-fix.sh arguments for the tests lender-info.sh reports, or None when the lender has no local test.

    parser-fix.sh dies silently (set -e + pipefail on a non-matching grep) when a lender lacks one of the two
    tests, so whenever we know the method we pass --test-method explicitly, chosen by channel.
    """
    adj = _ADJ_METHOD.findall(lender_info_output or "")
    rate = _RATE_METHOD.findall(lender_info_output or "")
    if adj and rate:
        a, r = _pick(adj, channel), _pick(rate, channel)
        return ["--both", "--test-method", a] if a == r else ["--both"]
    if adj:
        return ["--adj", "--test-method", _pick(adj, channel)]
    if rate:
        return ["--rate", "--test-method", _pick(rate, channel)]
    return None


@dataclass
class TestRun:
    report: str | None
    report_path: str
    available: bool      # False when lender-info found no local test for the lender
    log_cause: str       # surefire/exception line from the maven logs, "" when none


class Triager:
    def __init__(self, cfg: Config, runner=subprocess.run, now=None):
        self.cfg = cfg
        self.runner = runner
        self.now = now or (lambda: datetime.now(tz=ICT))

    channel_of = staticmethod(channel_of)

    # ---- helpers -------------------------------------------------------------------------------
    def _run(self, cmd: list[str], cwd: str, timeout: int) -> subprocess.CompletedProcess:
        p = self.runner(cmd, cwd=cwd, timeout=timeout, capture_output=True, text=True)
        if getattr(p, "returncode", 0):
            detail = (p.stderr or "").strip() or (p.stdout or "").strip()
            log.warning("%s exited %s: %s", cmd[0], p.returncode, detail[-200:])
        return p

    @staticmethod
    def _new_files(root: str, since: float) -> list[str]:
        out = []
        for p in Path(root).rglob("*"):
            if p.is_file() and p.stat().st_mtime >= since:
                out.append(str(p))
        return sorted(out, key=lambda s: os.path.getmtime(s), reverse=True)

    # ---- nightly preparation -------------------------------------------------------------------
    def prepare(self) -> None:
        """Return both bot clones to master, pull, install moso-pricing to ~/.m2. Shell only; touches no state.

        The checkout matters: a fix left the clone on a MOSO-<n> branch, and `pull --ff-only` there
        would refresh that branch instead of master, so triage would test against yesterday's fix.
        """
        for repo in (self.cfg.moso_pricing, os.path.join(self.cfg.bot_root, "packs")):
            self._run(["git", "-C", repo, "checkout", "master"], cwd=self.cfg.bot_root, timeout=self.cfg.prepare_sec)
            self._run(["git", "-C", repo, "pull", "--ff-only"], cwd=self.cfg.bot_root, timeout=self.cfg.prepare_sec)
        self._run(["mvn", "-q", "install", "-DskipTests", "-Pjar-packaging", "-Dgwt.compiler.skip=true"],
                  cwd=self.cfg.moso_pricing, timeout=self.cfg.prepare_sec)

    def prepare_night(self, state: NightState) -> None:
        if state.prepared:
            return
        self.prepare()
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
    def _run_tests(self, lender: str, channel: str, sheet: str) -> TestRun:
        t0 = time.time()
        try:
            info = self._run(["./lender-info.sh", lender], cwd=self.cfg.packs_loan, timeout=self.cfg.triage_sec)
        except subprocess.TimeoutExpired:
            return TestRun(None, "", True, "")
        args = test_args(getattr(info, "stdout", "") or "", channel)
        if args is None:
            return TestRun(None, "", False, "")
        try:
            self._run(["./parser-fix.sh", lender, "--ratesheet", sheet, *args], cwd=self.cfg.packs_loan,
                      timeout=self.cfg.triage_sec)
        except subprocess.TimeoutExpired:
            return TestRun(None, "", True, "")
        expected = os.path.join(self.cfg.report_dir, lender.lower(), "report.txt")
        if os.path.exists(expected) and os.path.getmtime(expected) >= t0:
            candidates = [expected]     # a report older than this run is a leftover, never today's answer
        elif os.path.isdir(self.cfg.report_dir):
            candidates = [p for p in self._new_files(self.cfg.report_dir, t0) if p.endswith("report.txt")]
        else:
            candidates = []
        report = Path(candidates[0]).read_text(encoding="utf-8", errors="replace") if candidates else None
        return TestRun(report, candidates[0] if candidates else "", True, self._log_cause(lender, t0))

    def _log_cause(self, lender: str, t0: float) -> str:
        for name in ("adj-test.log", "rate-test.log"):
            path = os.path.join(self.cfg.report_dir, lender.lower(), name)
            if os.path.exists(path) and os.path.getmtime(path) >= t0:
                cause = surefire_cause(Path(path).read_text(encoding="utf-8", errors="replace"))
                if cause:
                    return cause
        return ""


    # ---- entry point ---------------------------------------------------------------------------
    def triage(self, failure: RateFailure) -> TriageResult:
        channel = self.channel_of(failure)
        sheet = self._download(failure.lender, channel)
        run = TestRun(None, "", True, "")
        if sheet:
            run = self._run_tests(failure.lender, channel, sheet)
        report, report_path = run.report, run.report_path
        c = classify(failure.description, bool(sheet), report, test_available=run.available)
        if c.cls == LAYOUT and c.error_type == "UNKNOWN" and run.log_cause:
            c = Classification(c.cls, c.error_type, run.log_cause, c.adj_status, c.rate_status)
        entry = None
        if os.path.exists(self.cfg.cookbook):
            entry = parse_cookbook(Path(self.cfg.cookbook).read_text(encoding="utf-8")).get(failure.lender)
        tier, streak, hint = predict_tier(entry, c.error_type) if c.cls == "LAYOUT" else ("", entry.tier_0_streak if entry else 0, False)
        return TriageResult(failure.lender, channel, bool(sheet), sheet, c, tier, streak, hint, report_path)
