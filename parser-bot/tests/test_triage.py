import logging, os, subprocess, time
from datetime import datetime
from pathlib import Path
from parser_bot.config import Config
from parser_bot.lf_api import RateFailure
from parser_bot.nights import ICT
from parser_bot.state import NightState
from parser_bot.triage import Triager

LAYOUT_REPORT = (Path(__file__).parent / "fixtures" / "report_layout.txt").read_text()
COOKBOOK = (Path(__file__).parent / "fixtures" / "cookbook_sample.md").read_text()


def make_cfg(tmp_path):
    bot = tmp_path / "bot"
    (bot / "packs" / "loan" / "src" / "test" / "resources" / "ratesheets").mkdir(parents=True)
    (bot / "moso-pricing").mkdir()
    cb = tmp_path / "cookbook.md"; cb.write_text(COOKBOOK)
    return Config(space="s", lf_base_url="", lf_ns="", lf_credentials_file="", jira_base_url="", jira_email_env="",
                  jira_token_env="", jira_project="MOSO", jira_assignee="", gcp_subscription="",
                  gcp_service_account_file="", bot_root=str(bot), state_dir=str(tmp_path / "state"),
                  cookbook=str(cb), report_dir=str(tmp_path / "pf"), lenders_json="", aliases="", gcs_bucket="bkt",
                  timezone="Asia/Ho_Chi_Minh", poll_start="19:30", poll_end="05:30", poll_interval_sec=1,
                  lookback_hours=6, triage_sec=5, fix_sec=5, prepare_sec=5)


class Runner:
    """Fake shell: records commands, simulates download-ratesheet.sh and parser-fix.sh side effects."""
    def __init__(self, cfg, download_ok=True, report=LAYOUT_REPORT, gsutil_listing=""):
        self.cfg, self.download_ok, self.report, self.gsutil_listing = cfg, download_ok, report, gsutil_listing
        self.calls = []
    def __call__(self, cmd, cwd=None, timeout=None, **kw):
        self.calls.append((cmd, cwd, timeout))
        out = ""
        if cmd[0] == "./download-ratesheet.sh" and self.download_ok:
            time.sleep(0.01)
            f = Path(cwd) / "src/test/resources/ratesheets" / f"{cmd[1].lower()}_20260903.xlsx"
            f.write_text("x"); out = "  → Downloading... OK (10 bytes)"
        if cmd[0] == "gsutil" and cmd[1] == "ls":
            out = self.gsutil_listing
        if cmd[0] == "./parser-fix.sh":
            d = Path(self.cfg.report_dir) / cmd[1].lower(); d.mkdir(parents=True, exist_ok=True)
            (d / "report.txt").write_text(self.report)
        return subprocess.CompletedProcess(cmd, 0, stdout=out, stderr="")


NOW = datetime(2026, 9, 3, 21, 14, tzinfo=ICT)


def test_triage_layout_failure_runs_download_then_tests_and_predicts_tier(tmp_path):
    cfg = make_cfg(tmp_path); runner = Runner(cfg)
    t = Triager(cfg, runner=runner, now=lambda: NOW)
    res = t.triage(RateFailure("k", "2026-09-03T14:10", "PennyMac", "Error while parsing rates for PennyMac from Cron Job"))
    assert res.channel == "QM" and res.downloaded is True and res.sheet.endswith("pennymac_20260903.xlsx")
    assert res.classification.cls == "LAYOUT" and res.classification.error_type == "CRAWL_MISMATCH"
    assert (res.tier, res.streak, res.hint) == ("1", 6, True)
    assert runner.calls[0][0] == ["./download-ratesheet.sh", "PennyMac", "--no-detect", "--no-git", "--no-java"]
    assert runner.calls[0][1] == cfg.packs_loan
    assert runner.calls[0][2] == cfg.triage_sec
    assert runner.calls[1][0][:2] == ["./parser-fix.sh", "PennyMac"] and "--both" in runner.calls[1][0]
    assert runner.calls[1][2] == cfg.triage_sec


def test_nonqm_channel_adds_flag_and_no_sheet_becomes_not_code(tmp_path):
    cfg = make_cfg(tmp_path); runner = Runner(cfg, download_ok=False)
    t = Triager(cfg, runner=runner, now=lambda: NOW)
    res = t.triage(RateFailure("k", "c", "Provident", "Error while parsing rates for ProvidentNonQM ← login rejected"))
    assert res.channel == "NonQM"
    assert runner.calls[0][0] == ["./download-ratesheet.sh", "Provident", "--nonqm", "--no-detect", "--no-git", "--no-java"]
    assert any(c[0][:2] == ["gsutil", "ls"] for c in runner.calls)      # GCS fallback attempted
    assert res.downloaded is False and res.classification.cls == "LOGIN_DOWNLOAD"
    assert not any(c[0][0] == "./parser-fix.sh" for c in runner.calls)


def test_prepare_night_runs_once(tmp_path):
    cfg = make_cfg(tmp_path); runner = Runner(cfg)
    st = NightState.load(cfg.state_dir, "2026-09-03")
    t = Triager(cfg, runner=runner, now=lambda: NOW)
    t.prepare_night(st); t.prepare_night(st)
    cmds = [c[0] for c in runner.calls]
    packs = os.path.join(cfg.bot_root, "packs")
    assert cmds == [["git", "-C", cfg.moso_pricing, "checkout", "master"],
                    ["git", "-C", cfg.moso_pricing, "pull", "--ff-only"],
                    ["git", "-C", packs, "checkout", "master"],
                    ["git", "-C", packs, "pull", "--ff-only"],
                    ["mvn", "-q", "install", "-DskipTests", "-Pjar-packaging", "-Dgwt.compiler.skip=true"]]
    assert {c[2] for c in runner.calls} == {cfg.prepare_sec}
    assert st.prepared is True


class TimeoutRunner(Runner):
    """Fake shell that raises TimeoutExpired on gsutil ls."""
    def __call__(self, cmd, cwd=None, timeout=None, **kw):
        if cmd[:2] == ["gsutil", "ls"]:
            raise subprocess.TimeoutExpired(cmd, timeout)
        return super().__call__(cmd, cwd=cwd, timeout=timeout, **kw)


def test_gsutil_timeout_does_not_escape_triage(tmp_path):
    cfg = make_cfg(tmp_path); runner = TimeoutRunner(cfg, download_ok=False)
    t = Triager(cfg, runner=runner, now=lambda: NOW)
    res = t.triage(RateFailure("k", "c", "Provident", "Error while parsing rates for Provident ← login rejected"))
    assert res.downloaded is False
    assert res.classification.cls == "LOGIN_DOWNLOAD"


class NoReportRunner(Runner):
    """Downloads a sheet, but parser-fix.sh dies before writing a report."""
    def __call__(self, cmd, cwd=None, timeout=None, **kw):
        if cmd[0] == "./parser-fix.sh":
            self.calls.append((cmd, cwd, timeout))
            return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="parser-fix.sh: mvn blew up")
        return super().__call__(cmd, cwd=cwd, timeout=timeout, **kw)


def test_stale_report_from_an_earlier_run_is_not_reused(tmp_path):
    cfg = make_cfg(tmp_path); runner = NoReportRunner(cfg)
    stale = Path(cfg.report_dir) / "unionhome" / "report.txt"
    stale.parent.mkdir(parents=True)
    stale.write_text(LAYOUT_REPORT)
    old = time.time() - 100
    os.utime(stale, (old, old))
    t = Triager(cfg, runner=runner, now=lambda: NOW)
    res = t.triage(RateFailure("k", "c", "UnionHome", "Error while parsing rates for UnionHome"))
    assert res.downloaded is True and res.report_path == ""
    assert res.classification.cls == "LAYOUT" and res.classification.error_type == "UNKNOWN"
    assert res.classification.cause == "Tests failed; see report"


class FailingDownloadRunner(Runner):
    """download-ratesheet.sh exits non-zero and says why only on stderr."""
    def __call__(self, cmd, cwd=None, timeout=None, **kw):
        p = super().__call__(cmd, cwd=cwd, timeout=timeout, **kw)
        if cmd[0] == "./download-ratesheet.sh":
            return subprocess.CompletedProcess(cmd, 1, stdout=p.stdout, stderr="portal login failed")
        return p


def test_non_zero_shell_exit_is_logged(tmp_path, caplog):
    cfg = make_cfg(tmp_path); runner = FailingDownloadRunner(cfg, download_ok=False)
    t = Triager(cfg, runner=runner, now=lambda: NOW)
    with caplog.at_level(logging.WARNING, logger="parser-bot"):
        t.triage(RateFailure("k", "c", "Provident", "Error while parsing rates for Provident ← login rejected"))
    msgs = [r.getMessage() for r in caplog.records if r.levelname == "WARNING"]
    assert any("download-ratesheet.sh" in m and "exited 1" in m and "portal login failed" in m for m in msgs)
