"""Run /fix-parser headless in the bot clones and read its JSON summary."""
from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass, field

from .config import Config

_JSON_BLOCK = re.compile(r"```json\s*(\{.*?\})\s*```", re.S)


@dataclass
class FixResult:
    status: str
    tier: str = ""
    error_type: str = ""
    branch: str = ""
    commits: list[str] = field(default_factory=list)
    files: list[str] = field(default_factory=list)
    tests: dict = field(default_factory=dict)
    notes: str = ""
    raw_tail: str = ""


def build_command(lender: str, key: str, plan_only: bool = False) -> list[str]:
    prompt = f"/fix-parser --auto --lender {lender} --key {key}" + (" --plan-only" if plan_only else "")
    return ["claude", "-p", prompt, "--permission-mode", "acceptEdits", "--max-turns", "200"]


def parse_summary(stdout: str) -> dict | None:
    import json
    blocks = _JSON_BLOCK.findall(stdout or "")
    for raw in reversed(blocks):
        try:
            return json.loads(raw)
        except ValueError:
            continue
    return None


class Fixer:
    def __init__(self, cfg: Config, runner=subprocess.run):
        self.cfg = cfg
        self.runner = runner

    def run(self, lender: str, key: str, plan_only: bool = False) -> FixResult:
        env = dict(os.environ, PARSER_BOT_ROOT=self.cfg.bot_root)
        try:
            proc = self.runner(build_command(lender, key, plan_only), cwd=self.cfg.bot_root, timeout=self.cfg.fix_sec,
                               env=env, capture_output=True, text=True)
        except subprocess.TimeoutExpired:
            return FixResult("timeout", notes=f"claude did not finish within {self.cfg.fix_sec}s")
        tail = ((proc.stdout or "") + "\n" + (proc.stderr or ""))[-4000:]
        summary = parse_summary(proc.stdout or "")
        if not summary:
            return FixResult("error", notes=f"no JSON summary (exit {proc.returncode})", raw_tail=tail)
        return FixResult(status=str(summary.get("status", "error")), tier=str(summary.get("tier", "")),
                         error_type=str(summary.get("error_type", "")), branch=str(summary.get("branch", "")),
                         commits=list(summary.get("commits", []) or []), files=list(summary.get("files", []) or []),
                         tests=dict(summary.get("tests", {}) or {}), notes=str(summary.get("notes", "")), raw_tail=tail)
