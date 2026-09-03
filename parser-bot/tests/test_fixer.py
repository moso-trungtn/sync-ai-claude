import subprocess
from parser_bot.fixer import Fixer, FixResult, build_command, parse_summary
from tests.test_triage import make_cfg

STDOUT = """lots of agent chatter
```json
{"lender": "AAALendings", "tier": "1", "error_type": "CRAWL_MISMATCH", "status": "fixed",
 "branch": "MOSO-9", "commits": ["a1b2"], "files": ["AAALendingsTables.java"],
 "tests": {"rate": "PASSED", "adj": "PASSED"}, "notes": "crawlNote updated"}
```
"""


def test_build_command_and_plan_only_flag():
    assert build_command("AAALendings", "MOSO-9") == [
        "claude", "-p", "/fix-parser --auto --lender AAALendings --key MOSO-9",
        "--permission-mode", "acceptEdits", "--max-turns", "200"]
    assert build_command("AAALendings", "MOSO-9", plan_only=True)[2].endswith(" --plan-only")


def test_parse_summary_reads_last_json_block():
    s = parse_summary("```json\n{\"status\": \"old\"}\n```\n" + STDOUT)
    assert s["status"] == "fixed" and s["branch"] == "MOSO-9"
    assert parse_summary("no block here") is None


def test_run_maps_summary_timeout_and_error(tmp_path):
    cfg = make_cfg(tmp_path)
    calls = []
    def ok_runner(cmd, cwd=None, timeout=None, env=None, **kw):
        calls.append((cmd, cwd, timeout, env.get("PARSER_BOT_ROOT")))
        return subprocess.CompletedProcess(cmd, 0, stdout=STDOUT, stderr="")
    res = Fixer(cfg, runner=ok_runner).run("AAALendings", "MOSO-9")
    assert res == FixResult("fixed", "1", "CRAWL_MISMATCH", "MOSO-9", ["a1b2"], ["AAALendingsTables.java"],
                            {"rate": "PASSED", "adj": "PASSED"}, "crawlNote updated", res.raw_tail)
    assert calls[0][1] == cfg.bot_root and calls[0][2] == cfg.fix_sec and calls[0][3] == cfg.bot_root

    def slow(cmd, **kw): raise subprocess.TimeoutExpired(cmd, 1)
    assert Fixer(cfg, runner=slow).run("A", "K").status == "timeout"

    def noblock(cmd, **kw): return subprocess.CompletedProcess(cmd, 1, stdout="boom", stderr="err")
    r = Fixer(cfg, runner=noblock).run("A", "K")
    assert r.status == "error" and "boom" in r.raw_tail
