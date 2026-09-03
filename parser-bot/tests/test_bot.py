from datetime import datetime
from parser_bot.bot import Bot
from parser_bot.classify import Classification
from parser_bot.commands import Command
from parser_bot.fixer import FixResult
from parser_bot.lenders import LenderIndex
from parser_bot.lf_api import RateFailure
from parser_bot.nights import ICT
from parser_bot.state import NightState, LenderState, TRIAGED, NOT_CODE, FIXED, FIXING, FIX_FAILED, SKIPPED
from parser_bot.triage import TriageResult
from tests.test_triage import make_cfg

NOW = datetime(2026, 9, 3, 21, 14, tzinfo=ICT)
LENDERS = LenderIndex({"AAALendings": {"id": 1, "name": "AAA Lendings"}, "Provident": {"id": 3, "name": "Provident Funding"}}, {})


class FakeLF:
    def __init__(self, failures): self.failures, self.since = failures, []
    def failures_since(self, since): self.since.append(since); return self.failures


class FakeChat:
    def __init__(self): self.posts = []
    def post(self, text, thread_key=None, thread_name=None):
        self.posts.append((text, thread_key, thread_name)); return {"thread": {"name": f"spaces/S/threads/{thread_key or 'reply'}"}}


class FakeTriager:
    def __init__(self, results): self.results, self.prepared = results, 0
    def prepare(self): self.prepared += 1
    def prepare_night(self, state): self.prepared += 1; state.prepared = True
    def triage(self, failure): return self.results[failure.lender]


class FakeJira:
    def __init__(self): self.comments = []
    def ensure_ticket(self, state, label, date_pt): state.ticket = state.ticket or "MOSO-9"; return state.ticket
    def comment(self, key, text): self.comments.append((key, text))


class FakePuller:
    """Stands in for PubSubPuller: hands back a canned event list once, then nothing."""
    def __init__(self, events): self.events, self.pulls = events, 0
    def pull(self, max_messages=10, timeout=30):
        self.pulls += 1
        return self.events if self.pulls == 1 else []


class FakeFixer:
    def __init__(self, result): self.result, self.calls = result, []
    def run(self, lender, key, plan_only=False): self.calls.append((lender, key, plan_only)); return self.result


class ConcurrentWriteFixer:
    """Simulates the poller writing new state (a fresh triage + a seen key) while a fix is running."""
    def __init__(self, cfg, result): self.cfg, self.result, self.calls = cfg, result, []
    def run(self, lender, key, plan_only=False):
        self.calls.append((lender, key, plan_only))
        st = NightState.load(self.cfg.state_dir, "2026-09-03")
        st.lenders["Provident|QM"] = LenderState("Provident", "QM", TRIAGED, "t")
        st.mark_seen("k9")
        st.save()
        return self.result


class FlakyTriager:
    """Raises on the first triage() call, then behaves — a lender site hiccup mid-poll."""
    def __init__(self, results): self.results, self.prepared, self.calls = results, 0, 0
    def prepare(self): self.prepared += 1
    def triage(self, failure):
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("triage boom")
        return self.results[failure.lender]


class FlakyPrepareTriager(FakeTriager):
    """prepare() fails the first time (bad pull / mvn), succeeds afterwards."""
    def prepare(self):
        self.prepared += 1
        if self.prepared == 1:
            raise RuntimeError("mvn boom")


class CrashingFixer:
    def run(self, lender, key, plan_only=False): raise RuntimeError("boom")


class LockCheckingTriager:
    """Fails the test if prepare() ever runs while bot.state_lock is held."""
    def __init__(self, holder, results): self.holder, self.results, self.prepared = holder, results, 0
    def prepare(self):
        assert self.holder["bot"].state_lock.locked() is False, "prepare() must not run inside the state lock"
        self.prepared += 1
    def triage(self, failure): return self.results[failure.lender]


def layout(lender):
    return TriageResult(lender, "QM", True, "/tmp/x.xlsx", Classification("LAYOUT", "CRAWL_MISMATCH", "hdr moved", "FAILED", "PASSED"), "1", 2, False, "")


def build(tmp_path, failures, results, fix=None, commands_enabled=True):
    cfg = make_cfg(tmp_path); cfg.commands_enabled = commands_enabled
    lf, chat, jira = FakeLF(failures), FakeChat(), FakeJira()
    fixer = FakeFixer(fix or FixResult("fixed", "1", "CRAWL_MISMATCH", "MOSO-9", ["c1"], ["T.java"], {"rate": "PASSED", "adj": "PASSED"}, "ok"))
    bot = Bot(cfg, lf, chat, jira, FakeTriager(results), fixer, LENDERS, now=lambda: NOW, spawn=lambda fn: fn())
    return bot, cfg, chat, jira, fixer


def test_poll_once_triages_new_failures_once_and_posts_threads(tmp_path):
    f1 = RateFailure("k1", "c", "AAALendings", "Error while parsing rates for AAALendings")
    f2 = RateFailure("k2", "c", "Provident", "Error while parsing rates for Provident ← login rejected")
    prov = TriageResult("Provident", "QM", False, "", Classification("LOGIN_DOWNLOAD", "", "login rejected"), "", 0, False, "")
    bot, cfg, chat, *_ = build(tmp_path, [f1, f2], {"AAALendings": layout("AAALendings"), "Provident": prov})
    out = bot.poll_once()
    assert [r.lender for r in out] == ["AAALendings", "Provident"]
    assert chat.posts[0][1] == "AAALendings-09-03" and chat.posts[0][0].startswith("🔎 *AAA Lendings* (QM) failed 21:14 ICT")
    st = NightState.load(cfg.state_dir, "2026-09-03")
    assert st.lenders["AAALendings|QM"].status == TRIAGED and st.lenders["AAALendings|QM"].thread_name == "spaces/S/threads/AAALendings-09-03"
    assert st.lenders["Provident|QM"].status == NOT_CODE
    assert st.prepared is True
    assert bot.poll_once() == [] and len(chat.posts) == 2          # same keys again → nothing new
    assert bot.triager.prepared == 1


def test_fix_command_creates_ticket_runs_fixer_and_reports(tmp_path):
    f1 = RateFailure("k1", "c", "AAALendings", "Error while parsing rates for AAALendings")
    bot, cfg, chat, jira, fixer = build(tmp_path, [f1], {"AAALendings": layout("AAALendings")})
    bot.poll_once()
    reply = bot.handle_command(Command("fix", "AAA", "t@lf", "Trung", "spaces/S/threads/AAALendings-09-03", "spaces/S"))
    assert reply.startswith("⏳ Fixing *AAA Lendings* (Tier 1)")
    assert fixer.calls == [("AAALendings", "MOSO-9", False)]
    assert chat.posts[-1][0].startswith("✅ *AAA Lendings* fixed — branch MOSO-9")
    assert chat.posts[-1][2] == "spaces/S/threads/AAALendings-09-03"
    assert jira.comments and jira.comments[0][0] == "MOSO-9" and "CRAWL_MISMATCH" in jira.comments[0][1]
    st = NightState.load(cfg.state_dir, "2026-09-03")
    assert st.lenders["AAALendings|QM"].status == FIXED and st.lenders["AAALendings|QM"].branch == "MOSO-9" and st.ticket == "MOSO-9"


def test_skip_status_unknown_and_disabled(tmp_path):
    f1 = RateFailure("k1", "c", "AAALendings", "Error while parsing rates for AAALendings")
    bot, cfg, chat, jira, fixer = build(tmp_path, [f1], {"AAALendings": layout("AAALendings")})
    bot.poll_once()
    assert "SKIPPED" not in bot.handle_command(Command("status", "", "", "", "", ""))
    bot.handle_command(Command("skip", "AAA Lendings", "", "", "", ""))
    assert NightState.load(cfg.state_dir, "2026-09-03").lenders["AAALendings|QM"].status == SKIPPED
    assert "did not fail tonight" in bot.handle_command(Command("fix", "Provident", "", "", "", ""))
    assert fixer.calls == []
    bot.cfg.commands_enabled = False
    assert "Phase A" in bot.handle_command(Command("fix", "AAA", "", "", "", ""))


def test_fix_is_refused_while_another_fix_holds_the_lock(tmp_path):
    f1 = RateFailure("k1", "c", "AAALendings", "Error while parsing rates for AAALendings")
    cfg = make_cfg(tmp_path); cfg.commands_enabled = True
    lf, chat, jira = FakeLF([f1]), FakeChat(), FakeJira()
    fixer = FakeFixer(FixResult("fixed", "1", "CRAWL_MISMATCH", "MOSO-9", ["c1"], ["T.java"], {"rate": "PASSED", "adj": "PASSED"}, "ok"))
    bot = Bot(cfg, lf, chat, jira, FakeTriager({"AAALendings": layout("AAALendings")}), fixer, LENDERS,
             now=lambda: NOW, spawn=lambda fn: None)  # worker never runs
    bot.poll_once()
    first = bot.handle_command(Command("fix", "AAA", "", "", "", ""))
    assert first.startswith("⏳ Fixing *AAA Lendings* (Tier 1)")
    assert bot.fix_lock.locked() is False
    second = bot.handle_command(Command("fix", "AAA", "", "", "", ""))
    assert "already" in second
    st = NightState.load(cfg.state_dir, "2026-09-03")
    assert st.lenders["AAALendings|QM"].status == FIXING


def test_worker_does_not_clobber_state_written_during_fix(tmp_path):
    f1 = RateFailure("k1", "c", "AAALendings", "Error while parsing rates for AAALendings")
    cfg = make_cfg(tmp_path); cfg.commands_enabled = True
    lf, chat, jira = FakeLF([f1]), FakeChat(), FakeJira()
    fixer = ConcurrentWriteFixer(cfg, FixResult("fixed", "1", "CRAWL_MISMATCH", "MOSO-9", ["c1"], ["T.java"],
                                                {"rate": "PASSED", "adj": "PASSED"}, "ok"))
    bot = Bot(cfg, lf, chat, jira, FakeTriager({"AAALendings": layout("AAALendings")}), fixer, LENDERS,
             now=lambda: NOW, spawn=lambda fn: fn())
    bot.poll_once()
    bot.handle_command(Command("fix", "AAA", "", "", "", ""))
    st = NightState.load(cfg.state_dir, "2026-09-03")
    assert st.lenders["AAALendings|QM"].status == FIXED
    assert "Provident|QM" in st.lenders
    assert "k9" in st.seen_keys


def test_fix_all_posts_each_result_into_the_lender_thread(tmp_path):
    f1 = RateFailure("k1", "c", "AAALendings", "Error while parsing rates for AAALendings")
    f2 = RateFailure("k2", "c", "Provident", "Error while parsing rates for Provident")
    bot, cfg, chat, jira, fixer = build(tmp_path, [f1, f2],
                                        {"AAALendings": layout("AAALendings"), "Provident": layout("Provident")})
    bot.poll_once()
    reply = bot.handle_command(Command("fix_all", "", "", "", "", ""))
    assert "AAA Lendings" in reply and "Provident Funding" in reply
    posts_by_thread = {p[2]: p[0] for p in chat.posts if p[0].startswith("✅")}
    assert posts_by_thread.get("spaces/S/threads/AAALendings-09-03", "").startswith("✅ *AAA Lendings*")
    assert posts_by_thread.get("spaces/S/threads/Provident-09-03", "").startswith("✅ *Provident Funding*")


def test_worker_crash_marks_fix_failed_and_posts(tmp_path):
    f1 = RateFailure("k1", "c", "AAALendings", "Error while parsing rates for AAALendings")
    bot, cfg, chat, jira, fixer = build(tmp_path, [f1], {"AAALendings": layout("AAALendings")})
    bot.fixer = CrashingFixer()
    bot.poll_once()
    bot.handle_command(Command("fix", "AAA", "", "", "", ""))
    st = NightState.load(cfg.state_dir, "2026-09-03")
    assert st.lenders["AAALendings|QM"].status == FIX_FAILED
    assert "boom" in st.lenders["AAALendings|QM"].notes
    assert "fix crashed" in chat.posts[-1][0]
    # the fix_all path passes no thread — the crash must still land in the lender's triage thread
    bot._run_fix("AAALendings|QM", None)
    assert "fix crashed" in chat.posts[-1][0]
    assert chat.posts[-1][2] == "spaces/S/threads/AAALendings-09-03"
    # an explicit thread_name still wins over the lender's triage thread
    bot._run_fix("AAALendings|QM", "spaces/S/threads/x")
    assert "fix crashed" in chat.posts[-1][0]
    assert chat.posts[-1][2] == "spaces/S/threads/x"


def test_prepare_runs_outside_state_lock(tmp_path):
    f1 = RateFailure("k1", "c", "AAALendings", "Error while parsing rates for AAALendings")
    cfg = make_cfg(tmp_path)
    lf, chat, jira = FakeLF([f1]), FakeChat(), FakeJira()
    fixer = FakeFixer(FixResult("fixed", "1", "CRAWL_MISMATCH", "MOSO-9", ["c1"], ["T.java"], {"rate": "PASSED", "adj": "PASSED"}, "ok"))
    holder = {}
    triager = LockCheckingTriager(holder, {"AAALendings": layout("AAALendings")})
    bot = Bot(cfg, lf, chat, jira, triager, fixer, LENDERS, now=lambda: NOW, spawn=lambda fn: fn())
    holder["bot"] = bot
    bot.poll_once()
    assert triager.prepared == 1
    assert NightState.load(cfg.state_dir, "2026-09-03").prepared is True


def test_worker_crash_with_missing_state_key_still_posts(tmp_path):
    bot, cfg, chat, jira, fixer = build(tmp_path, [], {})
    bot._run_fix("Ghost|QM", "spaces/S/threads/x")   # no such lender in state — must not raise
    assert "fix crashed" in chat.posts[-1][0]
    assert chat.posts[-1][2] == "spaces/S/threads/x"


def status_event(text, thread):
    return {"type": "MESSAGE", "space": {"name": "spaces/S"},
            "message": {"text": text, "sender": {"type": "HUMAN", "email": "t@lf", "displayName": "Trung"},
                        "thread": {"name": thread}}}


def test_listen_once_uses_the_injected_puller_and_reuses_it(tmp_path):
    f1 = RateFailure("k1", "c", "AAALendings", "Error while parsing rates for AAALendings")
    cfg = make_cfg(tmp_path); cfg.commands_enabled = True
    lf, chat, jira = FakeLF([f1]), FakeChat(), FakeJira()
    fixer = FakeFixer(FixResult("fixed", "1", "CRAWL_MISMATCH", "MOSO-9", ["c1"], ["T.java"], {"rate": "PASSED", "adj": "PASSED"}, "ok"))
    puller = FakePuller([status_event("@Parser Bot status", "spaces/S/threads/t7")])
    bot = Bot(cfg, lf, chat, jira, FakeTriager({"AAALendings": layout("AAALendings")}), fixer, LENDERS,
              now=lambda: NOW, spawn=lambda fn: fn(), puller=puller)
    bot.poll_once()
    bot.listen_once()
    assert chat.posts[-1][0].startswith("Night 2026-09-03")
    assert "AAA Lendings (QM): TRIAGED" in chat.posts[-1][0]
    assert chat.posts[-1][2] == "spaces/S/threads/t7"
    bot.listen_once()
    assert bot.puller is puller and puller.pulls == 2


def poller(tmp_path, failures, triager):
    cfg = make_cfg(tmp_path)
    lf, chat, jira = FakeLF(failures), FakeChat(), FakeJira()
    fixer = FakeFixer(FixResult("fixed", "1", "CRAWL_MISMATCH", "MOSO-9", ["c1"], ["T.java"], {"rate": "PASSED", "adj": "PASSED"}, "ok"))
    return Bot(cfg, lf, chat, jira, triager, fixer, LENDERS, now=lambda: NOW, spawn=lambda fn: fn()), cfg, chat


def test_triage_crash_releases_the_seen_key_so_the_next_poll_retries(tmp_path):
    f1 = RateFailure("k1", "c", "AAALendings", "Error while parsing rates for AAALendings")
    triager = FlakyTriager({"AAALendings": layout("AAALendings")})
    bot, cfg, chat = poller(tmp_path, [f1], triager)
    assert bot.poll_once() == []
    st = NightState.load(cfg.state_dir, "2026-09-03")
    assert "k1" not in st.seen_keys and st.lenders == {} and chat.posts == []
    assert [r.lender for r in bot.poll_once()] == ["AAALendings"]
    st = NightState.load(cfg.state_dir, "2026-09-03")
    assert st.lenders["AAALendings|QM"].status == TRIAGED and "k1" in st.seen_keys
    assert len(chat.posts) == 1


def test_prepare_crash_releases_every_fresh_key_and_retries_next_poll(tmp_path):
    f1 = RateFailure("k1", "c", "AAALendings", "Error while parsing rates for AAALendings")
    f2 = RateFailure("k2", "c", "Provident", "Error while parsing rates for Provident")
    triager = FlakyPrepareTriager({"AAALendings": layout("AAALendings"), "Provident": layout("Provident")})
    bot, cfg, chat = poller(tmp_path, [f1, f2], triager)
    assert bot.poll_once() == []
    st = NightState.load(cfg.state_dir, "2026-09-03")
    assert st.seen_keys == set() and st.prepared is False and chat.posts == []
    assert [r.lender for r in bot.poll_once()] == ["AAALendings", "Provident"]
    assert NightState.load(cfg.state_dir, "2026-09-03").prepared is True
    assert triager.prepared == 2


def test_triage_message_uses_the_failure_time_not_the_poll_time(tmp_path):
    f1 = RateFailure("k1", "2026-09-03T14:10", "AAALendings", "Error while parsing rates for AAALendings")
    bot, cfg, chat, *_ = build(tmp_path, [f1], {"AAALendings": layout("AAALendings")})
    bot.poll_once()
    assert chat.posts[0][0].startswith("🔎 *AAA Lendings* (QM) failed 21:10 ICT")
