# Parser Bot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A Google Chat bot that triages overnight lender parse failures automatically and fixes a parser only after a human says `@Parser Bot fix <lender>`, leaving evidence on a branch and one Jira ticket per night.

**Architecture:** One Python daemon (`tools/parser-bot/`) on Trung's Mac: a poller reads failures from the LF EntityAPI, runs the existing parser scripts read-only in bot-owned clones to classify the cause, and posts a thread per lender to the Chat space; a Pub/Sub listener receives `@Parser Bot` commands and, when enabled, runs `claude -p "/fix-parser --auto ..."` in the bot clones, then reports to Chat and Jira. Every external system (LF API, Chat, Jira, Pub/Sub, shell) sits behind a small client with an injectable session/runner so each module is unit-tested with fakes.

**Tech Stack:** Python 3.12, requests, PyYAML, google-auth (service account → Chat API), google-cloud-pubsub (pull), pytest. Shell tools already in `packs/loan/` (`download-ratesheet.sh`, `parser-fix.sh`, `lender-info.sh`), `claude` CLI headless, launchd.

**Spec:** `tools/docs/superpowers/specs/2026-09-03-parser-bot-design.md`

## Global Constraints

- Runs on Trung's Mac (`/Users/trungthach/IdeaProjects`), Python 3.12.8, `mvn` at `/opt/homebrew/bin/mvn`, Java 21, `claude` at `~/.local/bin/claude`.
- Bot never touches the human checkouts. It works only in `worktrees/bot/moso-pricing` and `worktrees/bot/packs`, created with `git clone --shared` (a git worktree cannot build: parent pom copies `.git/HEAD`).
- Never merge or push `master`. Only branches named `MOSO-<n>` may be pushed, and only by `/fix-parser --auto`.
- `commands_enabled: false` until Phase A (triage-only, ~1 week) is reviewed.
- Anyone in the space may command (allowlist empty). Config keeps `allowlist` for later.
- One Jira ticket per night: `[Parser failed] MM/DD/YYYY: L1, L2`, Task, label `parser`, In Progress, US/Pacific date.
- All Jira/commit/doc text in English. Tools-repo commit style: `parser-bot: <imperative subject>` (see `git log` of `tools/`).
- Secrets live in `~/.config/parser-bot/` (mode 600): `sa.json`, `lf.json`; Jira creds from env `JIRA_EMAIL` / `JIRA_API_TOKEN`. Nothing secret in git.
- Chat space: `spaces/AAQASuO_evs`. GCS bucket for sheet history: `lender-rate-ratesheet`.
- Python HTTP must go through `requests` (bundled certifi); this Mac's Python has no system CA bundle, so `urllib` fails TLS.

---

## File structure

```
tools/parser-bot/
  README.md                     setup checklist (GCP, LF account, launchd), run/dry-run commands
  requirements.txt
  config.example.yaml           committed template; real config at ~/.config/parser-bot/config.yaml
  aliases.yaml                  optional lender aliases {"rocket": "QuickenLoans"}
  run.sh                        venv bootstrap + `python -m parser_bot.bot --config ...`
  setup_clones.sh               one-time: git clone --shared of moso-pricing + packs into worktrees/bot/
  refresh_clones.sh             nightly: pull master in both clones, mvn install moso-pricing (jar) to ~/.m2
  launchd/com.loanfactory.parser-bot.plist
  parser_bot/
    __init__.py
    config.py        load_config(path) -> Config (dataclass, expanded paths, defaults)
    nights.py        night_id(), in_window(), pacific_date(), ict_clock()  (pure time helpers)
    state.py         NightState / LenderState persisted to state/<night>.json
    lenders.py       gen_lenders(java) -> dict, LenderIndex.resolve(text)
    lf_api.py        LFClient: token (password grant), failures_since(since)
    classify.py      classify(reason, downloaded, report) -> Classification
    cookbook.py      parse_cookbook(text), predict_tier(entry, error_type)
    triage.py        Triager.prepare_night(), Triager.triage(failure) -> TriageResult (shell via runner)
    messages.py      triage_text(), result_text(), failure_text(), disabled_text(), status_text()
    chat.py          ChatClient.post(text, thread_key|thread_name)
    commands.py      parse_event(event) -> Command | None
    pubsub.py        pull_events(subscription, sa_file, max_messages, timeout) -> list[dict]  (thin, integration-only)
    jira.py          JiraClient: create_night_ticket(), append_lender(), comment(), ensure_ticket()
    fixer.py         Fixer.run(lender, key, plan_only) -> FixResult; parse_summary(stdout)
    bot.py           Bot.poll_once(), Bot.handle_command(), Bot.run(); main()
  tests/
    test_config.py test_nights.py test_state.py test_lenders.py test_lf_api.py test_classify.py
    test_cookbook.py test_triage.py test_messages.py test_chat.py test_commands.py test_jira.py
    test_fixer.py test_bot.py
    fixtures/LenderType_sample.java fixtures/report_layout.txt fixtures/report_green.txt fixtures/cookbook_sample.md
  state/.gitkeep    (state/*.json ignored)
  logs/.gitkeep     (logs/* ignored)
tools/claude-sync/skills/fix-parser/SKILL.md   add AUTO MODE section (Task 15)
```

Every task: `cd /Users/trungthach/IdeaProjects/tools/parser-bot`, tests with `.venv/bin/python -m pytest tests/<file> -q`. Commit from `/Users/trungthach/IdeaProjects/tools` with `git add parser-bot/<paths>` (never `git add -A`; the tools repo has unrelated uncommitted files).

---

### Task 1: Scaffold + config loader

**Files:**
- Create: `tools/parser-bot/requirements.txt`, `tools/parser-bot/config.example.yaml`, `tools/parser-bot/parser_bot/__init__.py`, `tools/parser-bot/parser_bot/config.py`, `tools/parser-bot/.gitignore`, `tools/parser-bot/state/.gitkeep`, `tools/parser-bot/logs/.gitkeep`
- Test: `tools/parser-bot/tests/test_config.py`

**Interfaces:**
- Produces: `Config` dataclass and `load_config(path: str) -> Config` used by every later task. Field names below are the contract.

- [ ] **Step 1: Create the package skeleton and venv**

```bash
mkdir -p /Users/trungthach/IdeaProjects/tools/parser-bot/{parser_bot,tests/fixtures,state,logs,launchd}
cd /Users/trungthach/IdeaProjects/tools/parser-bot
cat > requirements.txt <<'EOF'
requests==2.32.*
PyYAML==6.*
google-auth==2.*
google-cloud-pubsub==2.*
pytest==8.*
certifi
EOF
printf '.venv/\n__pycache__/\nstate/*.json\nlogs/*\n!logs/.gitkeep\n!state/.gitkeep\n' > .gitignore
touch parser_bot/__init__.py tests/__init__.py state/.gitkeep logs/.gitkeep
python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt
```

- [ ] **Step 2: Write the example config**

`config.example.yaml`:

```yaml
space: spaces/AAQASuO_evs
lf:
  base_url: https://loanfactory.com
  ns: LOAN_FACTORY
  credentials_file: ~/.config/parser-bot/lf.json      # {"username": "parser-bot@loanfactory.com", "password": "..."}
jira:
  base_url: https://mosoteam.atlassian.net
  email_env: JIRA_EMAIL
  token_env: JIRA_API_TOKEN
  project: MOSO
  assignee_account_id: "712020:c86c8eaf-7415-4e7d-8afe-59fd529b6fac"
gcp:
  subscription: projects/lenderrate-master/subscriptions/parser-bot-sub
  service_account_file: ~/.config/parser-bot/sa.json
paths:
  bot_root: /Users/trungthach/IdeaProjects/worktrees/bot     # contains moso-pricing/ and packs/
  state_dir: /Users/trungthach/IdeaProjects/tools/parser-bot/state
  cookbook: /Users/trungthach/.claude/projects/-Users-trungthach-IdeaProjects/memory/parser_fix_cookbook.md
  report_dir: /tmp/parser-fix
  lenders_json: /Users/trungthach/IdeaProjects/tools/parser-bot/state/lenders.json
  aliases: /Users/trungthach/IdeaProjects/tools/parser-bot/aliases.yaml
  gcs_bucket: lender-rate-ratesheet
schedule:
  timezone: Asia/Ho_Chi_Minh
  poll_start: "19:30"
  poll_end: "05:30"
  poll_interval_sec: 120
  lookback_hours: 6
commands_enabled: false
allowlist: []
timeouts:
  triage_sec: 900
  fix_sec: 3600
  prepare_sec: 1500
```

- [ ] **Step 3: Write the failing test**

`tests/test_config.py`:

```python
import textwrap
from parser_bot.config import load_config


def test_load_config_expands_paths_and_applies_defaults(tmp_path):
    cfg_file = tmp_path / "c.yaml"
    cfg_file.write_text(textwrap.dedent("""
        space: spaces/X
        lf: {base_url: https://lf, ns: LOAN_FACTORY, credentials_file: ~/lf.json}
        jira: {base_url: https://j, email_env: JE, token_env: JT, project: MOSO, assignee_account_id: "1:2"}
        gcp: {subscription: projects/p/subscriptions/s, service_account_file: ~/sa.json}
        paths: {bot_root: /bot, state_dir: /st, cookbook: /cb.md, report_dir: /tmp/pf, lenders_json: /l.json, aliases: /a.yaml, gcs_bucket: b}
        schedule: {timezone: Asia/Ho_Chi_Minh, poll_start: "19:30", poll_end: "05:30", poll_interval_sec: 60, lookback_hours: 6}
        timeouts: {triage_sec: 10, fix_sec: 20, prepare_sec: 30}
    """))
    cfg = load_config(str(cfg_file))
    assert cfg.space == "spaces/X"
    assert cfg.lf_credentials_file.startswith("/") and cfg.lf_credentials_file.endswith("/lf.json")
    assert cfg.gcp_service_account_file.endswith("/sa.json") and "~" not in cfg.gcp_service_account_file
    assert cfg.commands_enabled is False          # default when missing
    assert cfg.allowlist == []                    # default when missing
    assert cfg.poll_interval_sec == 60 and cfg.fix_sec == 20 and cfg.lookback_hours == 6
    assert cfg.jira_assignee == "1:2"
```

- [ ] **Step 4: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_config.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'parser_bot.config'`

- [ ] **Step 5: Implement `parser_bot/config.py`**

```python
"""Typed config loaded from YAML. All paths are expanded to absolute strings."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class Config:
    space: str
    lf_base_url: str
    lf_ns: str
    lf_credentials_file: str
    jira_base_url: str
    jira_email_env: str
    jira_token_env: str
    jira_project: str
    jira_assignee: str
    gcp_subscription: str
    gcp_service_account_file: str
    bot_root: str
    state_dir: str
    cookbook: str
    report_dir: str
    lenders_json: str
    aliases: str
    gcs_bucket: str
    timezone: str
    poll_start: str
    poll_end: str
    poll_interval_sec: int
    lookback_hours: int
    triage_sec: int
    fix_sec: int
    prepare_sec: int
    commands_enabled: bool = False
    allowlist: list[str] = field(default_factory=list)

    @property
    def moso_pricing(self) -> str:
        return os.path.join(self.bot_root, "moso-pricing")

    @property
    def packs_loan(self) -> str:
        return os.path.join(self.bot_root, "packs", "loan")


def _p(value: str) -> str:
    return str(Path(os.path.expanduser(value)))


def load_config(path: str) -> Config:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    lf, jira, gcp, paths = raw["lf"], raw["jira"], raw["gcp"], raw["paths"]
    sched, to = raw["schedule"], raw["timeouts"]
    return Config(
        space=raw["space"],
        lf_base_url=lf["base_url"].rstrip("/"),
        lf_ns=lf["ns"],
        lf_credentials_file=_p(lf["credentials_file"]),
        jira_base_url=jira["base_url"].rstrip("/"),
        jira_email_env=jira["email_env"],
        jira_token_env=jira["token_env"],
        jira_project=jira["project"],
        jira_assignee=str(jira["assignee_account_id"]),
        gcp_subscription=gcp["subscription"],
        gcp_service_account_file=_p(gcp["service_account_file"]),
        bot_root=_p(paths["bot_root"]),
        state_dir=_p(paths["state_dir"]),
        cookbook=_p(paths["cookbook"]),
        report_dir=_p(paths["report_dir"]),
        lenders_json=_p(paths["lenders_json"]),
        aliases=_p(paths["aliases"]),
        gcs_bucket=paths["gcs_bucket"],
        timezone=sched["timezone"],
        poll_start=str(sched["poll_start"]),
        poll_end=str(sched["poll_end"]),
        poll_interval_sec=int(sched["poll_interval_sec"]),
        lookback_hours=int(sched.get("lookback_hours", 6)),
        triage_sec=int(to["triage_sec"]),
        fix_sec=int(to["fix_sec"]),
        prepare_sec=int(to["prepare_sec"]),
        commands_enabled=bool(raw.get("commands_enabled", False)),
        allowlist=list(raw.get("allowlist", []) or []),
    )
```

- [ ] **Step 6: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_config.py -q`
Expected: `1 passed`

- [ ] **Step 7: Commit**

```bash
cd /Users/trungthach/IdeaProjects/tools
git add parser-bot/requirements.txt parser-bot/config.example.yaml parser-bot/.gitignore parser-bot/parser_bot/__init__.py parser-bot/parser_bot/config.py parser-bot/tests/__init__.py parser-bot/tests/test_config.py parser-bot/state/.gitkeep parser-bot/logs/.gitkeep
git commit -m "parser-bot: scaffold package and typed config loader"
```

---

### Task 2: Time helpers (`nights.py`)

**Files:**
- Create: `parser_bot/nights.py`
- Test: `tests/test_nights.py`

**Interfaces:**
- Produces: `night_id(now: datetime) -> str` ("YYYY-MM-DD", ICT date; before 12:00 belongs to the previous day), `in_window(now, start: str, end: str) -> bool` (overnight window, start inclusive, end exclusive, ICT), `pacific_date(now) -> str` ("MM/DD/YYYY"), `ict_clock(now) -> str` ("HH:MM ICT"), constants `ICT`, `PT`.

- [ ] **Step 1: Write the failing test**

```python
from datetime import datetime, timezone
from parser_bot.nights import ICT, night_id, in_window, pacific_date, ict_clock


def ict(y, mo, d, h, mi=0):
    return datetime(y, mo, d, h, mi, tzinfo=ICT)


def test_night_id_groups_evening_and_next_morning():
    assert night_id(ict(2026, 9, 3, 21)) == "2026-09-03"
    assert night_id(ict(2026, 9, 4, 3)) == "2026-09-03"
    assert night_id(ict(2026, 9, 4, 12)) == "2026-09-04"


def test_in_window_handles_overnight_range():
    assert in_window(ict(2026, 9, 3, 19, 30), "19:30", "05:30") is True
    assert in_window(ict(2026, 9, 3, 23), "19:30", "05:30") is True
    assert in_window(ict(2026, 9, 4, 3), "19:30", "05:30") is True
    assert in_window(ict(2026, 9, 4, 5, 30), "19:30", "05:30") is False
    assert in_window(ict(2026, 9, 3, 12), "19:30", "05:30") is False


def test_pacific_date_and_clock():
    # 21:00 ICT on 09/03 is 07:00 PDT on 09/03
    assert pacific_date(ict(2026, 9, 3, 21)) == "09/03/2026"
    # 03:00 ICT on 09/04 is 13:00 PDT on 09/03
    assert pacific_date(ict(2026, 9, 4, 3)) == "09/03/2026"
    assert ict_clock(datetime(2026, 9, 3, 14, 14, tzinfo=timezone.utc)) == "21:14 ICT"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_nights.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'parser_bot.nights'`

- [ ] **Step 3: Implement `parser_bot/nights.py`**

```python
"""Pure time helpers. A "night" is the ICT evening date; 00:00-11:59 ICT belongs to the previous date."""
from __future__ import annotations

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

ICT = ZoneInfo("Asia/Ho_Chi_Minh")
PT = ZoneInfo("US/Pacific")


def _hm(s: str) -> time:
    h, m = s.split(":")
    return time(int(h), int(m))


def night_id(now: datetime) -> str:
    local = now.astimezone(ICT)
    if local.hour < 12:
        local = local - timedelta(days=1)
    return local.date().isoformat()


def in_window(now: datetime, start: str, end: str) -> bool:
    t = now.astimezone(ICT).time().replace(second=0, microsecond=0)
    s, e = _hm(start), _hm(end)
    if s <= e:
        return s <= t < e
    return t >= s or t < e


def pacific_date(now: datetime) -> str:
    return now.astimezone(PT).strftime("%m/%d/%Y")


def ict_clock(now: datetime) -> str:
    return now.astimezone(ICT).strftime("%H:%M ICT")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_nights.py -q`
Expected: `3 passed`

- [ ] **Step 5: Commit**

```bash
cd /Users/trungthach/IdeaProjects/tools
git add parser-bot/parser_bot/nights.py parser-bot/tests/test_nights.py
git commit -m "parser-bot: add night id and active-window time helpers"
```

---

### Task 3: Night state (`state.py`)

**Files:**
- Create: `parser_bot/state.py`
- Test: `tests/test_state.py`

**Interfaces:**
- Produces: `LenderState` dataclass (fields: `lender, channel, status, detected_at, reason="", cause="", cls="", error_type="", tier="", streak=0, sheet="", thread_name="", branch="", notes=""`), statuses `DETECTED, TRIAGED, AWAITING_CONFIRM, FIXING, FIXED, FIX_FAILED, SKIPPED, NOT_CODE`; `NightState.load(state_dir, night) -> NightState`, `.save()`, `.mark_seen(key) -> bool`, `.lenders: dict[str, LenderState]` keyed by `"<LenderType>|<channel>"`, `.ticket: str | None`, `.prepared: bool`, `.key(lender, channel) -> str`.

- [ ] **Step 1: Write the failing test**

```python
from parser_bot.state import NightState, LenderState, TRIAGED


def test_state_roundtrip_and_seen_keys(tmp_path):
    st = NightState.load(str(tmp_path), "2026-09-03")
    assert st.lenders == {} and st.ticket is None and st.prepared is False
    assert st.mark_seen("k1") is True
    assert st.mark_seen("k1") is False
    st.lenders[st.key("AAALendings", "QM")] = LenderState(
        lender="AAALendings", channel="QM", status=TRIAGED, detected_at="2026-09-03T21:14+07:00",
        cause="CRAWL_MISMATCH", thread_name="spaces/x/threads/y")
    st.ticket = "MOSO-1"
    st.prepared = True
    st.save()

    again = NightState.load(str(tmp_path), "2026-09-03")
    assert again.mark_seen("k1") is False
    assert again.ticket == "MOSO-1" and again.prepared is True
    ls = again.lenders["AAALendings|QM"]
    assert ls.status == TRIAGED and ls.thread_name == "spaces/x/threads/y"
    assert (tmp_path / "2026-09-03.json").exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_state.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'parser_bot.state'`

- [ ] **Step 3: Implement `parser_bot/state.py`**

```python
"""Per-night persisted state (state/<night>.json). Atomic writes so a crash never leaves a half file."""
from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path

DETECTED = "DETECTED"
TRIAGED = "TRIAGED"
AWAITING_CONFIRM = "AWAITING_CONFIRM"
FIXING = "FIXING"
FIXED = "FIXED"
FIX_FAILED = "FIX_FAILED"
SKIPPED = "SKIPPED"
NOT_CODE = "NOT_CODE"


@dataclass
class LenderState:
    lender: str
    channel: str
    status: str
    detected_at: str
    reason: str = ""
    cause: str = ""
    cls: str = ""
    error_type: str = ""
    tier: str = ""
    streak: int = 0
    sheet: str = ""
    thread_name: str = ""
    branch: str = ""
    notes: str = ""


@dataclass
class NightState:
    night: str
    path: str
    seen_keys: set[str] = field(default_factory=set)
    ticket: str | None = None
    prepared: bool = False
    lenders: dict[str, LenderState] = field(default_factory=dict)

    @staticmethod
    def key(lender: str, channel: str) -> str:
        return f"{lender}|{channel}"

    @classmethod
    def load(cls, state_dir: str, night: str) -> "NightState":
        path = os.path.join(state_dir, f"{night}.json")
        st = cls(night=night, path=path)
        if os.path.exists(path):
            raw = json.loads(Path(path).read_text(encoding="utf-8"))
            st.seen_keys = set(raw.get("seen_keys", []))
            st.ticket = raw.get("ticket")
            st.prepared = bool(raw.get("prepared", False))
            st.lenders = {k: LenderState(**v) for k, v in raw.get("lenders", {}).items()}
        return st

    def mark_seen(self, key: str) -> bool:
        if key in self.seen_keys:
            return False
        self.seen_keys.add(key)
        return True

    def save(self) -> None:
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        data = {
            "night": self.night,
            "seen_keys": sorted(self.seen_keys),
            "ticket": self.ticket,
            "prepared": self.prepared,
            "lenders": {k: asdict(v) for k, v in self.lenders.items()},
        }
        fd, tmp = tempfile.mkstemp(dir=os.path.dirname(self.path), suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp, self.path)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_state.py -q`
Expected: `1 passed`

- [ ] **Step 5: Commit**

```bash
cd /Users/trungthach/IdeaProjects/tools
git add parser-bot/parser_bot/state.py parser-bot/tests/test_state.py
git commit -m "parser-bot: persist per-night lender state"
```

---

### Task 4: Lender index (`lenders.py`)

**Files:**
- Create: `parser_bot/lenders.py`, `tests/fixtures/LenderType_sample.java`, `tools/parser-bot/aliases.yaml`
- Test: `tests/test_lenders.py`

**Interfaces:**
- Produces: `gen_lenders(java_text: str) -> dict[str, dict]` (`{"Provident": {"id": 3, "name": "Provident Funding"}}`), `LenderIndex(lenders: dict, aliases: dict[str, str])`, `LenderIndex.resolve(text: str) -> Resolution` where `Resolution(kind: "one"|"none"|"many", matches: list[str])`, `LenderIndex.label(enum: str) -> str` (display name), `load_index(lenders_json: str, aliases_yaml: str) -> LenderIndex`, CLI `python -m parser_bot.lenders <LenderType.java> <out.json>`.
- Consumes: nothing.

- [ ] **Step 1: Write the fixture and aliases**

`tests/fixtures/LenderType_sample.java`:

```java
public enum LenderType {
  // comment
  Provident(3L, "Provident Funding"),
  QuickenLoans(19L, "Rocket Pro", true, true), // after
  Freedom(6567741112713216L, "Freedom Mortgage", TierType.freedomTiers), // after
  PennyMac(1L, "PennyMac"),
  PennyMacCorrespondent(2L, "PennyMac Correspondent", true),
  AAALendings(4L, "AAA Lendings");
  private final String name;
}
```

`tools/parser-bot/aliases.yaml`:

```yaml
rocket: QuickenLoans
uwm: UnitedWholesale
```

- [ ] **Step 2: Write the failing test**

```python
from pathlib import Path
from parser_bot.lenders import gen_lenders, LenderIndex

FIX = Path(__file__).parent / "fixtures" / "LenderType_sample.java"


def test_gen_lenders_parses_enum_constants():
    lenders = gen_lenders(FIX.read_text())
    assert lenders["Provident"] == {"id": 3, "name": "Provident Funding"}
    assert lenders["QuickenLoans"]["name"] == "Rocket Pro"
    assert set(lenders) == {"Provident", "QuickenLoans", "Freedom", "PennyMac", "PennyMacCorrespondent", "AAALendings"}


def test_resolve_exact_alias_and_partial():
    idx = LenderIndex(gen_lenders(FIX.read_text()), {"rocket": "QuickenLoans"})
    assert idx.resolve("provident").matches == ["Provident"]
    assert idx.resolve("Provident Funding").kind == "one"
    assert idx.resolve("rocket").matches == ["QuickenLoans"]
    assert idx.resolve("AAA").matches == ["AAALendings"]
    assert idx.resolve("PennyMac").matches == ["PennyMac"]          # exact enum wins over partial
    assert idx.resolve("Penny").kind == "many"
    assert idx.resolve("nobody").kind == "none"
    assert idx.label("AAALendings") == "AAA Lendings"
```

- [ ] **Step 3: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_lenders.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'parser_bot.lenders'`

- [ ] **Step 4: Implement `parser_bot/lenders.py`**

```python
"""LenderType enum → {enum: {id, name}} and fuzzy resolution of chat text to one enum constant."""
from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml

_CONST = re.compile(r'^\s*([A-Z][A-Za-z0-9]*)\((\d+)L?,\s*"([^"]+)"', re.M)


def gen_lenders(java_text: str) -> dict[str, dict]:
    return {m.group(1): {"id": int(m.group(2)), "name": m.group(3)} for m in _CONST.finditer(java_text)}


@dataclass
class Resolution:
    kind: str            # "one" | "none" | "many"
    matches: list[str]


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


class LenderIndex:
    def __init__(self, lenders: dict[str, dict], aliases: dict[str, str] | None = None):
        self.lenders = lenders
        self.aliases = {_norm(k): v for k, v in (aliases or {}).items()}

    def label(self, enum: str) -> str:
        return self.lenders.get(enum, {}).get("name", enum)

    def resolve(self, text: str) -> Resolution:
        q = _norm(text)
        if not q:
            return Resolution("none", [])
        if q in self.aliases and self.aliases[q] in self.lenders:
            return Resolution("one", [self.aliases[q]])
        for enum, info in self.lenders.items():
            if q == _norm(enum) or q == _norm(info["name"]):
                return Resolution("one", [enum])
        words = q.split()
        partial = [e for e, i in self.lenders.items()
                   if all(w in _norm(e) or w in _norm(i["name"]) for w in words)]
        if len(partial) == 1:
            return Resolution("one", partial)
        return Resolution("many" if partial else "none", sorted(partial))


def load_index(lenders_json: str, aliases_yaml: str) -> LenderIndex:
    lenders = json.loads(Path(lenders_json).read_text(encoding="utf-8"))
    aliases = {}
    if Path(aliases_yaml).exists():
        aliases = yaml.safe_load(Path(aliases_yaml).read_text(encoding="utf-8")) or {}
    return LenderIndex(lenders, aliases)


if __name__ == "__main__":  # python -m parser_bot.lenders <LenderType.java> <out.json>
    src, out = sys.argv[1], sys.argv[2]
    data = gen_lenders(Path(src).read_text(encoding="utf-8"))
    Path(out).write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    print(f"{len(data)} lenders -> {out}")
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_lenders.py -q`
Expected: `2 passed`

- [ ] **Step 6: Generate the real index once and check the count is plausible**

```bash
.venv/bin/python -m parser_bot.lenders /Users/trungthach/IdeaProjects/packs/quote/src/main/java/com/mvu/quote/shared/typekey/LenderType.java state/lenders.json
```
Expected: prints `N lenders -> state/lenders.json` with N > 80.

- [ ] **Step 7: Commit**

```bash
cd /Users/trungthach/IdeaProjects/tools
git add parser-bot/parser_bot/lenders.py parser-bot/tests/test_lenders.py parser-bot/tests/fixtures/LenderType_sample.java parser-bot/aliases.yaml
git commit -m "parser-bot: build lender index from LenderType and resolve chat text"
```

---

### Task 5: LF EntityAPI client (`lf_api.py`)

**Files:**
- Create: `parser_bot/lf_api.py`
- Test: `tests/test_lf_api.py`

**Interfaces:**
- Produces: `RateFailure(key: str, created: str, lender: str, description: str)`; `LFClient(base_url, ns, username, password, session=None, clock=time.time)` with `token() -> str` and `failures_since(since: datetime) -> list[RateFailure]`.
- Facts: token endpoint `POST {base}/api/oauth2/v1/{ns}/token` JSON `{"grant_type":"password","username":...,"password":...}` → `{"access_token","refresh_token","expires_in"}` (30 min). List endpoint `GET {base}/api/entity/v1/rate_update` with query `created>=YYYY-MM-DDTHH:MM`, `l=200`, `o=-created`, header `Authorization: Bearer <token>` → `{"items":[{...}], "length", "total", "cursor"}`. `status` is filtered client-side (no composite index). `session` must expose `post(url, json=..., timeout=...)` and `get(url, params=..., headers=..., timeout=...)` returning objects with `.status_code`, `.json()`, `.raise_for_status()` (a `requests.Session`).

- [ ] **Step 1: Write the failing test**

```python
from datetime import datetime, timezone
from parser_bot.lf_api import LFClient, RateFailure


class FakeResp:
    def __init__(self, payload, status=200):
        self._p, self.status_code = payload, status
    def json(self):
        return self._p
    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeSession:
    def __init__(self):
        self.calls = []
        self.token_calls = 0
    def post(self, url, json=None, timeout=None):
        self.calls.append(("POST", url, json))
        self.token_calls += 1
        return FakeResp({"access_token": f"tok{self.token_calls}", "refresh_token": "r", "expires_in": 1800})
    def get(self, url, params=None, headers=None, timeout=None):
        self.calls.append(("GET", url, params, headers))
        return FakeResp({"items": [
            {"key": "k1", "created": "2026-09-03T14:10", "lender": "AAALendings", "description": "Error while parsing rates for AAALendingsNonQM", "status": False},
            {"key": "k2", "created": "2026-09-03T14:05", "lender": "Provident", "description": "Parsed 120 New Provident Rates", "status": True},
            {"key": "k3", "created": "2026-09-03T14:00", "lender": "Rocket", "description": "Can not parseRocketAdjustmentParser"},
        ]})


def test_token_is_fetched_once_and_reused():
    s = FakeSession()
    clock = [1000.0]
    c = LFClient("https://lf", "LOAN_FACTORY", "bot@lf", "pw", session=s, clock=lambda: clock[0])
    assert c.token() == "tok1"
    assert c.token() == "tok1"
    assert s.calls[0] == ("POST", "https://lf/api/oauth2/v1/LOAN_FACTORY/token",
                          {"grant_type": "password", "username": "bot@lf", "password": "pw"})
    clock[0] += 1800 - 200          # inside the 5-minute safety margin → refresh
    assert c.token() == "tok2"


def test_failures_since_filters_status_false_only():
    s = FakeSession()
    c = LFClient("https://lf", "LOAN_FACTORY", "u", "p", session=s, clock=lambda: 0.0)
    out = c.failures_since(datetime(2026, 9, 3, 10, 0, tzinfo=timezone.utc))
    assert out == [RateFailure("k1", "2026-09-03T14:10", "AAALendings", "Error while parsing rates for AAALendingsNonQM")]
    method, url, params, headers = s.calls[-1]
    assert url == "https://lf/api/entity/v1/rate_update"
    assert params == {"created>": "2026-09-03T10:00", "l": "200", "o": "-created"}
    assert headers == {"Authorization": "Bearer tok1"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_lf_api.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'parser_bot.lf_api'`

- [ ] **Step 3: Implement `parser_bot/lf_api.py`**

```python
"""Loan Factory EntityAPI client: password-grant token + RateUpdate failures."""
from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timezone

import requests

TOKEN_MARGIN_SEC = 300


@dataclass(frozen=True)
class RateFailure:
    key: str
    created: str
    lender: str
    description: str


class LFClient:
    def __init__(self, base_url: str, ns: str, username: str, password: str, session=None, clock=time.time):
        self.base_url = base_url.rstrip("/")
        self.ns = ns
        self.username = username
        self.password = password
        self.session = session or requests.Session()
        self.clock = clock
        self._token: str | None = None
        self._expires_at = 0.0

    def token(self) -> str:
        if self._token and self.clock() < self._expires_at - TOKEN_MARGIN_SEC:
            return self._token
        r = self.session.post(f"{self.base_url}/api/oauth2/v1/{self.ns}/token",
                              json={"grant_type": "password", "username": self.username, "password": self.password},
                              timeout=30)
        r.raise_for_status()
        body = r.json()
        self._token = body["access_token"]
        self._expires_at = self.clock() + float(body.get("expires_in", 1800))
        return self._token

    def failures_since(self, since: datetime) -> list[RateFailure]:
        since_utc = since.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M")
        r = self.session.get(f"{self.base_url}/api/entity/v1/rate_update",
                             params={"created>": since_utc, "l": "200", "o": "-created"},
                             headers={"Authorization": f"Bearer {self.token()}"}, timeout=60)
        r.raise_for_status()
        out = []
        for row in r.json().get("items", []):
            if row.get("status", True) is not False:
                continue
            out.append(RateFailure(key=str(row.get("key", "")), created=str(row.get("created", "")),
                                   lender=str(row.get("lender", "")), description=str(row.get("description", ""))))
        return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_lf_api.py -q`
Expected: `2 passed`

- [ ] **Step 5: Commit**

```bash
cd /Users/trungthach/IdeaProjects/tools
git add parser-bot/parser_bot/lf_api.py parser-bot/tests/test_lf_api.py
git commit -m "parser-bot: add LF EntityAPI client for rate_update failures"
```

---

### Task 6: Failure classification (`classify.py`)

**Files:**
- Create: `parser_bot/classify.py`, `tests/fixtures/report_layout.txt`, `tests/fixtures/report_green.txt`
- Test: `tests/test_classify.py`

**Interfaces:**
- Produces: constants `LOGIN_DOWNLOAD, EMAIL_MISSING, LAYOUT, TESTS_GREEN`; `Classification(cls: str, error_type: str, cause: str, adj_status: str, rate_status: str)`; `classify(reason: str, downloaded: bool, report: str | None) -> Classification`; `ERROR_PRIORITY` list.
- Report format (from `parser-fix.sh`): a `RESULTS` section with `Adj:  PASSED|FAILED (...)` and `Rate: PASSED|FAILED`, then error lines `TYPE | detail` where TYPE ∈ VALUE_MISMATCH, STRUCTURE_CHANGE, CRAWL_MISMATCH, KEYWORD_MISSING, NULL_POINTER, RATE_COUNT, NEW_ADJ_DETECTED.

- [ ] **Step 1: Write fixtures**

`tests/fixtures/report_layout.txt`:

```
PARSER FIX REPORT
=================
Lender:    AAALendings
Ratesheet: aaa_lendings_20260903.xlsx
Date:      2026-09-03 21:20

RESULTS
-------
Adj:  FAILED
Rate: PASSED

ERRORS
------
VALUE_MISMATCH | field_7 (loanAmount): 12 cell(s)
CRAWL_MISMATCH | field_3 (ficoLtv): crawlNote "Credit Score" not found on page 2
```

`tests/fixtures/report_green.txt`:

```
PARSER FIX REPORT
=================
Lender:    Provident
Date:      2026-09-03 21:20

RESULTS
-------
Adj:  PASSED (14 tables)
Rate: PASSED
```

- [ ] **Step 2: Write the failing test**

```python
from pathlib import Path
from parser_bot.classify import classify, LAYOUT, TESTS_GREEN, LOGIN_DOWNLOAD, EMAIL_MISSING

FIX = Path(__file__).parent / "fixtures"


def test_layout_picks_most_severe_error_type_and_its_detail():
    c = classify("Error while parsing rates for AAA", True, (FIX / "report_layout.txt").read_text())
    assert c.cls == LAYOUT
    assert c.error_type == "CRAWL_MISMATCH"                 # outranks VALUE_MISMATCH
    assert c.cause == 'field_3 (ficoLtv): crawlNote "Credit Score" not found on page 2'
    assert (c.adj_status, c.rate_status) == ("FAILED", "PASSED")


def test_green_report_means_transient():
    c = classify("UWMRateParser empty rate tables", True, (FIX / "report_green.txt").read_text())
    assert c.cls == TESTS_GREEN and c.error_type == "" and c.adj_status == "PASSED"


def test_login_and_email_causes_without_a_sheet():
    assert classify("ProvidentRateDownloader: login rejected", False, None).cls == LOGIN_DOWNLOAD
    assert classify("Selenium timeout waiting for loanProgramFilter", False, None).cls == LOGIN_DOWNLOAD
    assert classify("Could not handle email with subject Rates", False, None).cls == EMAIL_MISSING
    c = classify("UWMRateParser empty rate tables", False, None)
    assert c.cls == EMAIL_MISSING and "no ratesheet" in c.cause.lower()


def test_failed_report_without_typed_lines_falls_back_to_unknown():
    report = "RESULTS\n-------\nAdj:  FAILED\nRate: FAILED\n\njava.lang.IllegalStateException: boom\n"
    c = classify("x", True, report)
    assert c.cls == LAYOUT and c.error_type == "UNKNOWN" and "IllegalStateException" in c.cause
```

- [ ] **Step 3: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_classify.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'parser_bot.classify'`

- [ ] **Step 4: Implement `parser_bot/classify.py`**

```python
"""Turn (alert reason, download outcome, parser-fix report) into one of four classes. Pure, no I/O."""
from __future__ import annotations

import re
from dataclasses import dataclass

LOGIN_DOWNLOAD = "LOGIN_DOWNLOAD"
EMAIL_MISSING = "EMAIL_MISSING"
LAYOUT = "LAYOUT"
TESTS_GREEN = "TESTS_GREEN"

ERROR_PRIORITY = ["NULL_POINTER", "STRUCTURE_CHANGE", "KEYWORD_MISSING", "CRAWL_MISMATCH",
                  "RATE_COUNT", "NEW_ADJ_DETECTED", "VALUE_MISMATCH"]

_LOGIN = re.compile(r"login|rejected|imperva|403|timeout|selenium|download|captcha|credential", re.I)
_EMAIL = re.compile(r"could not handle email|no email|attachment", re.I)
_ERR_LINE = re.compile(r"^(" + "|".join(ERROR_PRIORITY) + r")\s*\|\s*(.*)$", re.M)
_ADJ = re.compile(r"^Adj:\s+(PASSED|FAILED)", re.M)
_RATE = re.compile(r"^Rate:\s+(PASSED|FAILED)", re.M)


@dataclass(frozen=True)
class Classification:
    cls: str
    error_type: str
    cause: str
    adj_status: str = ""
    rate_status: str = ""


def classify(reason: str, downloaded: bool, report: str | None) -> Classification:
    reason = reason or ""
    if not downloaded:
        if _LOGIN.search(reason):
            return Classification(LOGIN_DOWNLOAD, "", reason.strip())
        if _EMAIL.search(reason):
            return Classification(EMAIL_MISSING, "", reason.strip())
        return Classification(EMAIL_MISSING, "", f"No ratesheet found for today; builder said: {reason.strip()}")
    text = report or ""
    adj = (_ADJ.search(text) or [None, ""])[1]
    rate = (_RATE.search(text) or [None, ""])[1]
    if adj == "PASSED" and rate == "PASSED":
        return Classification(TESTS_GREEN, "", "Local tests pass on today's sheet", adj, rate)
    found = {m.group(1): m.group(2).strip() for m in reversed(list(_ERR_LINE.finditer(text)))}
    for t in ERROR_PRIORITY:
        if t in found:
            return Classification(LAYOUT, t, found[t], adj, rate)
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    exc = next((ln for ln in lines if "Exception" in ln), "") or next((ln for ln in lines if "FAILED" in ln), "")
    return Classification(LAYOUT, "UNKNOWN", exc or "Tests failed; see report", adj, rate)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_classify.py -q`
Expected: `4 passed`

- [ ] **Step 6: Commit**

```bash
cd /Users/trungthach/IdeaProjects/tools
git add parser-bot/parser_bot/classify.py parser-bot/tests/test_classify.py parser-bot/tests/fixtures/report_layout.txt parser-bot/tests/fixtures/report_green.txt
git commit -m "parser-bot: classify failures from reason, download outcome and parser-fix report"
```

---

### Task 7: Cookbook tier prediction (`cookbook.py`)

**Files:**
- Create: `parser_bot/cookbook.py`, `tests/fixtures/cookbook_sample.md`
- Test: `tests/test_cookbook.py`

**Interfaces:**
- Produces: `CookbookEntry(lender: str, tier_history: list[int], tier_0_streak: int, last_tier1_fix: str)`; `parse_cookbook(text: str) -> dict[str, CookbookEntry]`; `predict_tier(entry: CookbookEntry | None, error_type: str) -> tuple[str, int, bool]` = (tier "0"|"1"|"2", streak, has_hint). Mirrors `/fix-parser` SKILL §"Classification Algorithm".

- [ ] **Step 1: Write the fixture**

`tests/fixtures/cookbook_sample.md`:

```
# Parser Fix Cookbook

## PennyMac
- **tier_history**: [0, 0, 0, 1, 0, 0, 0, 0, 0, 0] (last 10)
- **tier_0_streak**: 6
- **last_tier1_fix**: CRAWL_MISMATCH on field_8 → updated section keyword "FICO Score" → "Credit Score" (2026-03-15)

## LoganFinance
- **tier_history**: [0, 1, 0, 0, 0]
- **tier_0_streak**: 3
- **last_tier1_fix**: VALUE_MISMATCH on FICO table → row ranges changed (2026-03-10)
```

- [ ] **Step 2: Write the failing test**

```python
from pathlib import Path
from parser_bot.cookbook import parse_cookbook, predict_tier

TEXT = (Path(__file__).parent / "fixtures" / "cookbook_sample.md").read_text()


def test_parse_cookbook_entries():
    cb = parse_cookbook(TEXT)
    assert set(cb) == {"PennyMac", "LoganFinance"}
    assert cb["PennyMac"].tier_0_streak == 6
    assert cb["PennyMac"].tier_history == [0, 0, 0, 1, 0, 0, 0, 0, 0, 0]
    assert cb["LoganFinance"].last_tier1_fix.startswith("VALUE_MISMATCH")


def test_predict_tier_follows_fix_parser_algorithm():
    cb = parse_cookbook(TEXT)
    assert predict_tier(cb["PennyMac"], "VALUE_MISMATCH") == ("0", 6, False)      # streak >= 3 → optimistic Tier 0
    assert predict_tier(cb["PennyMac"], "CRAWL_MISMATCH") == ("1", 6, True)        # known pattern + past fix hint
    assert predict_tier(None, "VALUE_MISMATCH") == ("1", 0, False)
    assert predict_tier(None, "NULL_POINTER") == ("2", 0, False)
    assert predict_tier(cb["LoganFinance"], "UNKNOWN") == ("2", 3, False)
```

- [ ] **Step 3: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_cookbook.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'parser_bot.cookbook'`

- [ ] **Step 4: Implement `parser_bot/cookbook.py`**

```python
"""Read /fix-parser's cookbook (markdown) and predict the fix tier like the skill does."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

TIER_0_ERRORS = {"VALUE_MISMATCH", "NEW_ADJ_DETECTED", "RATE_COUNT"}
TIER_1_ERRORS = {"CRAWL_MISMATCH", "VALUE_MISMATCH", "KEYWORD_MISSING", "RATE_COUNT", "NEW_ADJ_DETECTED"}

_SECTION = re.compile(r"^## (\S+)\s*$", re.M)
_FIELD = re.compile(r"^- \*\*(\w+)\*\*:\s*(.*)$", re.M)


@dataclass
class CookbookEntry:
    lender: str
    tier_history: list[int] = field(default_factory=list)
    tier_0_streak: int = 0
    last_tier1_fix: str = ""


def parse_cookbook(text: str) -> dict[str, CookbookEntry]:
    out: dict[str, CookbookEntry] = {}
    heads = list(_SECTION.finditer(text))
    for i, h in enumerate(heads):
        body = text[h.end(): heads[i + 1].start() if i + 1 < len(heads) else len(text)]
        e = CookbookEntry(lender=h.group(1))
        for m in _FIELD.finditer(body):
            k, v = m.group(1), m.group(2).strip()
            if k == "tier_history":
                e.tier_history = [int(x) for x in re.findall(r"\d+", v.split("]")[0])]
            elif k == "tier_0_streak":
                e.tier_0_streak = int(re.search(r"\d+", v).group(0)) if re.search(r"\d+", v) else 0
            elif k == "last_tier1_fix":
                e.last_tier1_fix = v
        out[e.lender] = e
    return out


def predict_tier(entry: CookbookEntry | None, error_type: str) -> tuple[str, int, bool]:
    streak = entry.tier_0_streak if entry else 0
    hint = bool(entry and error_type and error_type in entry.last_tier1_fix)
    if error_type in TIER_0_ERRORS and streak >= 3:
        return "0", streak, hint
    if error_type in TIER_1_ERRORS:
        return "1", streak, hint
    return "2", streak, hint
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_cookbook.py -q`
Expected: `2 passed`

- [ ] **Step 6: Commit**

```bash
cd /Users/trungthach/IdeaProjects/tools
git add parser-bot/parser_bot/cookbook.py parser-bot/tests/test_cookbook.py parser-bot/tests/fixtures/cookbook_sample.md
git commit -m "parser-bot: predict fix tier from the fix-parser cookbook"
```

---

### Task 8: Triage orchestration (`triage.py`)

**Files:**
- Create: `parser_bot/triage.py`
- Test: `tests/test_triage.py`

**Interfaces:**
- Consumes: `Config` (Task 1), `RateFailure` (Task 5), `classify` (Task 6), `parse_cookbook/predict_tier` (Task 7), `NightState` (Task 3).
- Produces: `TriageResult(lender, channel, downloaded: bool, sheet: str, classification: Classification, tier: str, streak: int, hint: bool, report_path: str)`; `Triager(cfg, runner=subprocess.run, now=datetime.now)` with `channel_of(failure) -> "QM"|"NonQM"`, `prepare_night(state) -> None` (pull clones + `mvn install` moso-pricing once per night), `triage(failure) -> TriageResult`.
- `runner(cmd: list[str], cwd: str, timeout: int) -> CompletedProcess` (stdout/stderr text). Shell commands, exactly:
  - prepare: `git -C <bot_root>/moso-pricing pull --ff-only`, `git -C <bot_root>/packs pull --ff-only`, `mvn -q install -DskipTests -Pjar-packaging -Dgwt.compiler.skip=true` in `<bot_root>/moso-pricing`.
  - download: `./download-ratesheet.sh <Lender> [--nonqm] --no-detect --no-git --no-java` in `<bot_root>/packs/loan`; the new file is whatever appeared under `<packs/loan>/src/test/resources` after the call started.
  - fallback: `gsutil ls gs://<bucket>/history/<LenderName>/<YYYY>/<MM>/<DD>/` (ICT date, then PT date), `gsutil cp <newest> /tmp/parser-bot/<lender>/`.
  - tests: `./parser-fix.sh <Lender> --ratesheet <file> --both` in `<packs/loan>`; report at `<report_dir>/<lender-lowercase>/report.txt` (fallback: any `report.txt` under `<report_dir>` modified after the call started).

- [ ] **Step 1: Write the failing test**

```python
import os, subprocess, time
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
        self.calls.append((cmd, cwd))
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
    assert runner.calls[1][0][:2] == ["./parser-fix.sh", "PennyMac"] and "--both" in runner.calls[1][0]


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
    assert cmds == [["git", "-C", cfg.moso_pricing, "pull", "--ff-only"],
                    ["git", "-C", os.path.join(cfg.bot_root, "packs"), "pull", "--ff-only"],
                    ["mvn", "-q", "install", "-DskipTests", "-Pjar-packaging", "-Dgwt.compiler.skip=true"]]
    assert st.prepared is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_triage.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'parser_bot.triage'`

- [ ] **Step 3: Implement `parser_bot/triage.py`**

```python
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
        self._run(["git", "-C", self.cfg.moso_pricing, "pull", "--ff-only"], cwd=self.cfg.bot_root, timeout=300)
        self._run(["git", "-C", os.path.join(self.cfg.bot_root, "packs"), "pull", "--ff-only"], cwd=self.cfg.bot_root, timeout=300)
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
            self._run(cmd, cwd=self.cfg.packs_loan, timeout=300)
        except subprocess.TimeoutExpired:
            return ""
        files = self._new_files(resources, t0)
        return files[0] if files else self._gcs_fallback(lender, channel)

    def _gcs_fallback(self, lender: str, channel: str) -> str:
        name = lender + ("NonQM" if channel == "NonQM" else "")
        now = self.now()
        for day in {now.astimezone(ICT).date(), now.astimezone(PT).date()}:
            prefix = f"gs://{self.cfg.gcs_bucket}/history/{name}/{day:%Y}/{day:%m}/{day:%d}/"
            ls = self._run(["gsutil", "ls", prefix], cwd=self.cfg.bot_root, timeout=120)
            objects = [ln.strip() for ln in (ls.stdout or "").splitlines() if ln.strip().startswith("gs://")]
            if objects:
                dest = os.path.join("/tmp/parser-bot", lender.lower())
                os.makedirs(dest, exist_ok=True)
                self._run(["gsutil", "cp", objects[-1], dest + "/"], cwd=self.cfg.bot_root, timeout=300)
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_triage.py -q`
Expected: `3 passed`

- [ ] **Step 5: Commit**

```bash
cd /Users/trungthach/IdeaProjects/tools
git add parser-bot/parser_bot/triage.py parser-bot/tests/test_triage.py
git commit -m "parser-bot: triage failures with download-ratesheet and parser-fix in bot clones"
```

---

### Task 9: Chat message rendering (`messages.py`)

**Files:**
- Create: `parser_bot/messages.py`
- Test: `tests/test_messages.py`

**Interfaces:**
- Consumes: `TriageResult` (Task 8), `Classification` (Task 6), `FixResult` (Task 13 — fields `status, tier, error_type, branch, commits, files, tests, notes`; define the dataclass in Task 13, this task imports only names in tests via a simple stub).
- Produces: `triage_text(res: TriageResult, label: str, when: str, sheet_uri: str) -> str`, `result_text(label, fix, key) -> str`, `failure_text(label, fix, key) -> str`, `disabled_text() -> str`, `status_text(state: NightState, labels: dict[str, str]) -> str`, `unknown_lender_text(text, matches) -> str`.

- [ ] **Step 1: Write the failing test**

```python
from types import SimpleNamespace as NS
from parser_bot.classify import Classification
from parser_bot.messages import triage_text, result_text, failure_text, disabled_text, status_text, unknown_lender_text
from parser_bot.state import NightState, LenderState, TRIAGED, NOT_CODE
from parser_bot.triage import TriageResult


def layout_res():
    return TriageResult("AAALendings", "QM", True, "/tmp/aaa.xlsx",
                        Classification("LAYOUT", "CRAWL_MISMATCH", 'row label "Credit Score" not found', "FAILED", "PASSED"),
                        "1", 4, True, "/tmp/pf/aaalendings/report.txt")


def test_triage_text_for_layout_offers_fix():
    t = triage_text(layout_res(), "AAA Lendings", "21:14 ICT", "gs://b/history/AAALendings/2026/09/03/x.xlsx")
    assert t.splitlines()[0] == "🔎 *AAA Lendings* (QM) failed 21:14 ICT"
    assert '• Cause: CRAWL_MISMATCH — row label "Credit Score" not found' in t
    assert "• Prediction: Tier 1 (cookbook streak 4, past fix hint) · ~10 min" in t
    assert "• Sheet: gs://b/history/AAALendings/2026/09/03/x.xlsx" in t
    assert t.rstrip().endswith("Reply `@Parser Bot fix AAALendings` to fix, `@Parser Bot skip AAALendings` to ignore.")


def test_triage_text_for_not_code_does_not_offer_fix():
    res = TriageResult("Provident", "QM", False, "", Classification("LOGIN_DOWNLOAD", "", "login rejected"), "", 0, False, "")
    t = triage_text(res, "Provident Funding", "21:14 ICT", "")
    assert "Not a code problem" in t and "fix Provident" not in t


def test_result_failure_and_disabled_texts():
    fix = NS(status="fixed", tier="1", error_type="CRAWL_MISMATCH", branch="MOSO-17140",
             commits=["a1", "b2"], files=["AAALendingsTables.java", "adj-expectations/aaa.txt"],
             tests={"rate": "PASSED", "adj": "PASSED"}, notes='crawlNote "Credit Score" → "FICO Score"')
    r = result_text("AAA Lendings", fix, "MOSO-17140")
    assert r.startswith("✅ *AAA Lendings* fixed — branch MOSO-17140, 2 commits, tests: RateParserTest ✓ AdjustmentParsersTest ✓")
    assert "• Changed: AAALendingsTables.java, adj-expectations/aaa.txt" in r and "• Jira: MOSO-17140" in r
    f = failure_text("AAA Lendings", NS(status="failed", tier="2", notes="NPE in page 3", branch="MOSO-17140"), "MOSO-17140")
    assert f == "❌ *AAA Lendings* not fixed after Tier 2 — NPE in page 3. Left on branch MOSO-17140 for a human."
    assert "Phase A" in disabled_text()
    assert "did not fail tonight" in unknown_lender_text("Foo", [])
    assert "PennyMac, PennyMacCorrespondent" in unknown_lender_text("Penny", ["PennyMac", "PennyMacCorrespondent"])


def test_status_text_lists_lenders(tmp_path):
    st = NightState.load(str(tmp_path), "2026-09-03")
    st.lenders["AAALendings|QM"] = LenderState("AAALendings", "QM", TRIAGED, "t", tier="1")
    st.lenders["Provident|QM"] = LenderState("Provident", "QM", NOT_CODE, "t", cls="LOGIN_DOWNLOAD")
    s = status_text(st, {"AAALendings": "AAA Lendings", "Provident": "Provident Funding"})
    assert "AAA Lendings (QM): TRIAGED" in s and "Provident Funding (QM): NOT_CODE" in s
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_messages.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'parser_bot.messages'`

- [ ] **Step 3: Implement `parser_bot/messages.py`**

```python
"""All Chat text lives here so wording can change without touching logic. Google Chat: *bold*, plain newlines."""
from __future__ import annotations

from .classify import LAYOUT, LOGIN_DOWNLOAD, EMAIL_MISSING, TESTS_GREEN
from .state import NightState
from .triage import TriageResult

_MINUTES = {"0": "~3 min", "1": "~10 min", "2": "~30 min"}


def triage_text(res: TriageResult, label: str, when: str, sheet_uri: str) -> str:
    lines = [f"🔎 *{label}* ({res.channel}) failed {when}"]
    c = res.classification
    if c.cls == LAYOUT:
        lines.append(f"• Cause: {c.error_type} — {c.cause}")
        hint = ", past fix hint" if res.hint else ""
        lines.append(f"• Prediction: Tier {res.tier} (cookbook streak {res.streak}{hint}) · {_MINUTES.get(res.tier, '')}".rstrip(" ·"))
        if sheet_uri:
            lines.append(f"• Sheet: {sheet_uri}")
        lines.append(f"Reply `@Parser Bot fix {res.lender}` to fix, `@Parser Bot skip {res.lender}` to ignore.")
    elif c.cls == LOGIN_DOWNLOAD:
        lines.append(f"• Cause: {c.cause}")
        lines.append("• Not a code problem — credentials/site. IT action (turn off lender or fix login).")
    elif c.cls == EMAIL_MISSING:
        lines.append(f"• Cause: {c.cause}")
        lines.append("• No ratesheet arrived / email unreadable. Nothing to fix in the parser.")
    elif c.cls == TESTS_GREEN:
        lines.append("• Local tests pass on today's sheet — likely a transient/builder issue. Retry the build instead.")
    return "\n".join(lines)


def _tests_line(tests: dict) -> str:
    mark = lambda k: "✓" if str(tests.get(k, "")).upper() == "PASSED" else "✗"
    return f"RateParserTest {mark('rate')} AdjustmentParsersTest {mark('adj')}"


def result_text(label: str, fix, key: str) -> str:
    n = len(fix.commits or [])
    head = f"✅ *{label}* fixed — branch {fix.branch}, {n} commit{'s' if n != 1 else ''}, tests: {_tests_line(fix.tests or {})}"
    lines = [head]
    if fix.files:
        lines.append("• Changed: " + ", ".join(fix.files))
    if fix.notes:
        lines.append(f"• What: {fix.notes}")
    lines.append(f"• Jira: {key} (comment with diff + test output). Review & merge in the morning.")
    return "\n".join(lines)


def failure_text(label: str, fix, key: str) -> str:
    tier = f" after Tier {fix.tier}" if getattr(fix, "tier", "") else ""
    where = f" Left on branch {fix.branch} for a human." if getattr(fix, "branch", "") else ""
    return f"❌ *{label}* not fixed{tier} — {fix.notes or fix.status}.{where}"


def disabled_text() -> str:
    return "Commands are disabled during Phase A (triage only). Fix it manually with /fix-parser for now."


def unknown_lender_text(text: str, matches: list[str]) -> str:
    if matches:
        return f"'{text}' matches several lenders: {', '.join(matches)}. Say the full name."
    return f"'{text}' did not fail tonight (or I can't match it to a lender). Try `@Parser Bot status`."


def status_text(state: NightState, labels: dict[str, str]) -> str:
    if not state.lenders:
        return f"Night {state.night}: no failures so far."
    lines = [f"Night {state.night}" + (f" · ticket {state.ticket}" if state.ticket else "")]
    for ls in state.lenders.values():
        extra = f" (Tier {ls.tier})" if ls.tier else (f" ({ls.cls})" if ls.cls else "")
        lines.append(f"• {labels.get(ls.lender, ls.lender)} ({ls.channel}): {ls.status}{extra}")
    return "\n".join(lines)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_messages.py -q`
Expected: `4 passed`

- [ ] **Step 5: Commit**

```bash
cd /Users/trungthach/IdeaProjects/tools
git add parser-bot/parser_bot/messages.py parser-bot/tests/test_messages.py
git commit -m "parser-bot: render triage, result and status chat messages"
```

---

### Task 10: Chat API client (`chat.py`)

**Files:**
- Create: `parser_bot/chat.py`
- Test: `tests/test_chat.py`

**Interfaces:**
- Produces: `ChatClient(sa_file: str, space: str, session=None)` with `post(text: str, thread_key: str | None = None, thread_name: str | None = None) -> dict` (returns the API response JSON; `["thread"]["name"]` is the thread to reply into later). Endpoint `POST https://chat.googleapis.com/v1/{space}/messages?messageReplyOption=REPLY_MESSAGE_FALLBACK_TO_NEW_THREAD`, body `{"text": ..., "thread": {"threadKey": ...}}` or `{"thread": {"name": ...}}`. Session built lazily from the service account with scope `https://www.googleapis.com/auth/chat.bot`.

- [ ] **Step 1: Write the failing test**

```python
from parser_bot.chat import ChatClient, CHAT_SCOPE


class FakeResp:
    status_code = 200
    def __init__(self, payload): self._p = payload
    def json(self): return self._p
    def raise_for_status(self): pass


class FakeSession:
    def __init__(self): self.calls = []
    def post(self, url, params=None, json=None, timeout=None):
        self.calls.append((url, params, json))
        return FakeResp({"name": "spaces/S/messages/M", "thread": {"name": "spaces/S/threads/T"}})


def test_post_with_thread_key_starts_or_joins_keyed_thread():
    s = FakeSession()
    c = ChatClient("/nonexistent/sa.json", "spaces/S", session=s)
    out = c.post("hello", thread_key="AAALendings-09-03")
    assert out["thread"]["name"] == "spaces/S/threads/T"
    url, params, body = s.calls[0]
    assert url == "https://chat.googleapis.com/v1/spaces/S/messages"
    assert params == {"messageReplyOption": "REPLY_MESSAGE_FALLBACK_TO_NEW_THREAD"}
    assert body == {"text": "hello", "thread": {"threadKey": "AAALendings-09-03"}}


def test_post_with_thread_name_replies_in_existing_thread():
    s = FakeSession()
    ChatClient("/nonexistent/sa.json", "spaces/S", session=s).post("hi", thread_name="spaces/S/threads/T")
    assert s.calls[0][2] == {"text": "hi", "thread": {"name": "spaces/S/threads/T"}}
    assert CHAT_SCOPE == "https://www.googleapis.com/auth/chat.bot"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_chat.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'parser_bot.chat'`

- [ ] **Step 3: Implement `parser_bot/chat.py`**

```python
"""Post messages into the Chat space as the app (service account, chat.bot scope)."""
from __future__ import annotations

CHAT_SCOPE = "https://www.googleapis.com/auth/chat.bot"
API = "https://chat.googleapis.com/v1"


class ChatClient:
    def __init__(self, sa_file: str, space: str, session=None):
        self.sa_file = sa_file
        self.space = space
        self._session = session

    @property
    def session(self):
        if self._session is None:
            from google.oauth2 import service_account
            from google.auth.transport.requests import AuthorizedSession
            creds = service_account.Credentials.from_service_account_file(self.sa_file, scopes=[CHAT_SCOPE])
            self._session = AuthorizedSession(creds)
        return self._session

    def post(self, text: str, thread_key: str | None = None, thread_name: str | None = None) -> dict:
        body: dict = {"text": text}
        if thread_name:
            body["thread"] = {"name": thread_name}
        elif thread_key:
            body["thread"] = {"threadKey": thread_key}
        r = self.session.post(f"{API}/{self.space}/messages",
                              params={"messageReplyOption": "REPLY_MESSAGE_FALLBACK_TO_NEW_THREAD"},
                              json=body, timeout=30)
        r.raise_for_status()
        return r.json()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_chat.py -q`
Expected: `2 passed`

- [ ] **Step 5: Commit**

```bash
cd /Users/trungthach/IdeaProjects/tools
git add parser-bot/parser_bot/chat.py parser-bot/tests/test_chat.py
git commit -m "parser-bot: post threaded messages through the Chat API"
```

---

### Task 11: Command parsing (`commands.py`) + Pub/Sub pull (`pubsub.py`)

**Files:**
- Create: `parser_bot/commands.py`, `parser_bot/pubsub.py`
- Test: `tests/test_commands.py`

**Interfaces:**
- Produces: `Command(kind: str, lender_text: str, sender_email: str, sender_name: str, thread_name: str, space: str)` with kinds `fix, fix_all, skip, retry, status`; `parse_event(event: dict) -> Command | None` (handles the classic `{"type":"MESSAGE","message":{...},"space":{...}}` shape and the newer `{"chat":{"messagePayload":{"message":{...},"space":{...}}}}` shape; uses `message.argumentText` when present, else strips a leading `@Parser Bot`); `pull_events(subscription: str, sa_file: str, max_messages: int = 10, timeout: float = 30) -> list[dict]` (acks after decode; integration-only, not unit tested).

- [ ] **Step 1: Write the failing test**

```python
import json
from parser_bot.commands import parse_event, Command


def classic(text, argument=None, etype="MESSAGE"):
    msg = {"text": text, "sender": {"name": "users/1", "displayName": "Trung", "email": "t@lf.com", "type": "HUMAN"},
           "thread": {"name": "spaces/S/threads/T"}}
    if argument is not None:
        msg["argumentText"] = argument
    return {"type": etype, "eventTime": "2026-09-03T14:20:00Z", "space": {"name": "spaces/S"}, "message": msg}


def test_fix_command_from_classic_event_uses_argument_text():
    cmd = parse_event(classic("@Parser Bot fix AAA", argument=" fix AAA"))
    assert cmd == Command("fix", "AAA", "t@lf.com", "Trung", "spaces/S/threads/T", "spaces/S")


def test_variants_and_non_commands():
    assert parse_event(classic("@Parser Bot fix all")).kind == "fix_all"
    assert parse_event(classic("@Parser Bot  SKIP Provident")).lender_text == "Provident"
    assert parse_event(classic("@Parser Bot retry rocket")).kind == "retry"
    assert parse_event(classic("@Parser Bot status")).kind == "status"
    assert parse_event(classic("@Parser Bot hello there")) is None
    assert parse_event(classic("fix AAA", etype="ADDED_TO_SPACE")) is None
    assert parse_event({"type": "MESSAGE", "space": {"name": "spaces/S"},
                        "message": {"text": "fix AAA", "sender": {"type": "BOT", "email": "", "displayName": "b"}, "thread": {"name": "x"}}}) is None


def test_new_payload_shape_is_supported():
    ev = {"chat": {"messagePayload": {"space": {"name": "spaces/S"},
                                      "message": {"text": "@Parser Bot fix AAA Lendings", "argumentText": " fix AAA Lendings",
                                                  "sender": {"email": "a@lf.com", "displayName": "A", "type": "HUMAN"},
                                                  "thread": {"name": "spaces/S/threads/Z"}}}}}
    cmd = parse_event(ev)
    assert cmd.kind == "fix" and cmd.lender_text == "AAA Lendings" and cmd.thread_name == "spaces/S/threads/Z"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_commands.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'parser_bot.commands'`

- [ ] **Step 3: Implement `parser_bot/commands.py`**

```python
"""Parse a Chat app event into a bot command. Only human MESSAGE events with a known verb count."""
from __future__ import annotations

import re
from dataclasses import dataclass

_VERB = re.compile(r"^\s*(fix|skip|retry|status)\b\s*(.*)$", re.I)
_MENTION = re.compile(r"^\s*@parser\s*bot\b", re.I)


@dataclass(frozen=True)
class Command:
    kind: str
    lender_text: str
    sender_email: str
    sender_name: str
    thread_name: str
    space: str


def _payload(event: dict) -> tuple[dict | None, dict]:
    if "chat" in event:  # newer Workspace event shape
        mp = event.get("chat", {}).get("messagePayload", {})
        return mp.get("message"), mp.get("space", {})
    if event.get("type") == "MESSAGE":
        return event.get("message"), event.get("space", {})
    return None, {}


def parse_event(event: dict) -> Command | None:
    message, space = _payload(event)
    if not message:
        return None
    sender = message.get("sender", {}) or {}
    if sender.get("type") == "BOT":
        return None
    text = message.get("argumentText")
    if text is None:
        text = _MENTION.sub("", message.get("text", "") or "")
    m = _VERB.match(text or "")
    if not m:
        return None
    verb, rest = m.group(1).lower(), m.group(2).strip()
    kind = "fix_all" if verb == "fix" and rest.lower() == "all" else verb
    if verb in ("fix", "skip", "retry") and kind != "fix_all" and not rest:
        return None
    return Command(kind=kind, lender_text="" if kind in ("fix_all", "status") else rest,
                   sender_email=sender.get("email", "") or "", sender_name=sender.get("displayName", "") or "",
                   thread_name=(message.get("thread") or {}).get("name", "") or "",
                   space=space.get("name", "") or "")
```

- [ ] **Step 4: Implement `parser_bot/pubsub.py` (thin, integration-only)**

```python
"""Synchronous Pub/Sub pull for the Chat app subscription. Decodes JSON and acks what it returns."""
from __future__ import annotations

import json


def pull_events(subscription: str, sa_file: str, max_messages: int = 10, timeout: float = 30) -> list[dict]:
    from google.cloud import pubsub_v1
    from google.oauth2 import service_account
    creds = service_account.Credentials.from_service_account_file(sa_file)
    client = pubsub_v1.SubscriberClient(credentials=creds)
    resp = client.pull(request={"subscription": subscription, "max_messages": max_messages}, timeout=timeout)
    events, ack_ids = [], []
    for rm in resp.received_messages:
        ack_ids.append(rm.ack_id)
        try:
            events.append(json.loads(rm.message.data.decode("utf-8")))
        except (ValueError, UnicodeDecodeError):
            continue
    if ack_ids:
        client.acknowledge(request={"subscription": subscription, "ack_ids": ack_ids})
    return events
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_commands.py -q`
Expected: `3 passed`

- [ ] **Step 6: Commit**

```bash
cd /Users/trungthach/IdeaProjects/tools
git add parser-bot/parser_bot/commands.py parser-bot/parser_bot/pubsub.py parser-bot/tests/test_commands.py
git commit -m "parser-bot: parse chat commands and pull Chat events from Pub/Sub"
```

---

### Task 12: Jira nightly ticket (`jira.py`)

**Files:**
- Create: `parser_bot/jira.py`
- Test: `tests/test_jira.py`

**Interfaces:**
- Consumes: `NightState` (Task 3).
- Produces: `JiraClient(base_url, email, token, project, assignee, session=None)` with `create_night_ticket(date_pt: str, labels: list[str]) -> str`, `append_lender(key: str, label: str) -> None`, `comment(key: str, text: str) -> None`, `ensure_ticket(state: NightState, label: str, date_pt: str) -> str`. REST v2, Basic auth via `session.auth = (email, token)`. Summary format `[Parser failed] MM/DD/YYYY: L1, L2`; new tickets get label `parser`, issuetype Task, assignee accountId, then transitions "Select for development" → "Start Progress" by name.

- [ ] **Step 1: Write the failing test**

```python
from parser_bot.jira import JiraClient
from parser_bot.state import NightState


class FakeResp:
    def __init__(self, payload, status=200): self._p, self.status_code = payload, status
    def json(self): return self._p
    def raise_for_status(self): pass


class FakeJira:
    def __init__(self):
        self.calls = []; self.auth = None; self.summary = "[Parser failed] 09/03/2026: AAA Lendings"
        self.transitions = [{"id": "841", "name": "Select for development"}]
    def post(self, url, json=None, timeout=None):
        self.calls.append(("POST", url, json))
        if url.endswith("/rest/api/2/issue"):
            return FakeResp({"key": "MOSO-9"})
        if url.endswith("/transitions"):
            self.transitions = [{"id": "4", "name": "Start Progress"}] if json["transition"]["id"] == "841" else []
            return FakeResp({})
        return FakeResp({})
    def get(self, url, params=None, timeout=None):
        self.calls.append(("GET", url, params))
        if url.endswith("/transitions"):
            return FakeResp({"transitions": self.transitions})
        return FakeResp({"fields": {"summary": self.summary}})
    def put(self, url, json=None, timeout=None):
        self.calls.append(("PUT", url, json)); self.summary = json["fields"]["summary"]; return FakeResp({}, 204)


def test_create_night_ticket_sets_fields_and_moves_to_in_progress():
    s = FakeJira()
    j = JiraClient("https://j", "me@x", "tok", "MOSO", "1:2", session=s)
    assert j.create_night_ticket("09/03/2026", ["AAA Lendings"]) == "MOSO-9"
    assert s.auth == ("me@x", "tok")
    create = s.calls[0][2]["fields"]
    assert create["summary"] == "[Parser failed] 09/03/2026: AAA Lendings"
    assert create["project"] == {"key": "MOSO"} and create["issuetype"] == {"name": "Task"}
    assert create["labels"] == ["parser"] and create["assignee"] == {"accountId": "1:2"}
    posted = [c for c in s.calls if c[0] == "POST" and c[1].endswith("/transitions")]
    assert [c[2]["transition"]["id"] for c in posted] == ["841", "4"]


def test_append_lender_and_ensure_ticket(tmp_path):
    s = FakeJira()
    j = JiraClient("https://j", "me@x", "tok", "MOSO", "1:2", session=s)
    j.append_lender("MOSO-9", "Rocket Pro")
    assert s.summary == "[Parser failed] 09/03/2026: AAA Lendings, Rocket Pro"
    j.append_lender("MOSO-9", "Rocket Pro")                       # idempotent
    assert s.summary.count("Rocket Pro") == 1
    st = NightState.load(str(tmp_path), "2026-09-03")
    assert j.ensure_ticket(st, "AAA Lendings", "09/03/2026") == "MOSO-9" and st.ticket == "MOSO-9"
    j.comment("MOSO-9", "hello")
    assert s.calls[-1] == ("POST", "https://j/rest/api/2/issue/MOSO-9/comment", {"body": "hello"})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_jira.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'parser_bot.jira'`

- [ ] **Step 3: Implement `parser_bot/jira.py`**

```python
"""One Jira ticket per night. REST v2 with Basic auth; description in wiki markup, English only."""
from __future__ import annotations

import requests

from .state import NightState

PREFIX = "[Parser failed] "


class JiraClient:
    def __init__(self, base_url: str, email: str, token: str, project: str, assignee: str, session=None):
        self.base = base_url.rstrip("/")
        self.project = project
        self.assignee = assignee
        self.session = session or requests.Session()
        self.session.auth = (email, token)

    def _transition(self, key: str, name: str) -> None:
        r = self.session.get(f"{self.base}/rest/api/2/issue/{key}/transitions", timeout=30)
        r.raise_for_status()
        for t in r.json().get("transitions", []):
            if t["name"] == name:
                self.session.post(f"{self.base}/rest/api/2/issue/{key}/transitions",
                                  json={"transition": {"id": t["id"]}}, timeout=30).raise_for_status()
                return

    def create_night_ticket(self, date_pt: str, labels: list[str]) -> str:
        fields = {
            "project": {"key": self.project},
            "issuetype": {"name": "Task"},
            "summary": f"{PREFIX}{date_pt}: {', '.join(labels)}",
            "labels": ["parser"],
            "assignee": {"accountId": self.assignee},
            "description": ("h3. Overnight parser failures\n"
                            "Created by Parser Bot. One comment per lender below: cause, tier, branch, test output.\n"
                            "Fixes live on branch(es) named after this key; review and merge to master manually."),
        }
        r = self.session.post(f"{self.base}/rest/api/2/issue", json={"fields": fields}, timeout=30)
        r.raise_for_status()
        key = r.json()["key"]
        self._transition(key, "Select for development")
        self._transition(key, "Start Progress")
        return key

    def append_lender(self, key: str, label: str) -> None:
        r = self.session.get(f"{self.base}/rest/api/2/issue/{key}", params={"fields": "summary"}, timeout=30)
        r.raise_for_status()
        summary = r.json()["fields"]["summary"]
        head, _, tail = summary.partition(": ")
        names = [n.strip() for n in tail.split(",") if n.strip()] if tail else []
        if label in names:
            return
        names.append(label)
        self.session.put(f"{self.base}/rest/api/2/issue/{key}",
                         json={"fields": {"summary": f"{head}: {', '.join(names)}"}}, timeout=30).raise_for_status()

    def comment(self, key: str, text: str) -> None:
        self.session.post(f"{self.base}/rest/api/2/issue/{key}/comment", json={"body": text}, timeout=30).raise_for_status()

    def ensure_ticket(self, state: NightState, label: str, date_pt: str) -> str:
        if state.ticket:
            self.append_lender(state.ticket, label)
        else:
            state.ticket = self.create_night_ticket(date_pt, [label])
            state.save()
        return state.ticket
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_jira.py -q`
Expected: `2 passed`

- [ ] **Step 5: Commit**

```bash
cd /Users/trungthach/IdeaProjects/tools
git add parser-bot/parser_bot/jira.py parser-bot/tests/test_jira.py
git commit -m "parser-bot: manage the nightly Jira ticket"
```

---

### Task 13: Headless fixer (`fixer.py`)

**Files:**
- Create: `parser_bot/fixer.py`
- Test: `tests/test_fixer.py`

**Interfaces:**
- Consumes: `Config` (Task 1).
- Produces: `FixResult(status: str, tier: str = "", error_type: str = "", branch: str = "", commits: list[str] = [], files: list[str] = [], tests: dict = {}, notes: str = "", raw_tail: str = "")` where `status ∈ fixed | failed | planned | timeout | error`; `build_command(lender, key, plan_only=False) -> list[str]`; `parse_summary(stdout: str) -> dict | None` (last fenced ```json block); `Fixer(cfg, runner=subprocess.run).run(lender, key, plan_only=False) -> FixResult`. Runs `claude -p "/fix-parser --auto --lender <L> --key <KEY> [--plan-only]" --permission-mode acceptEdits --max-turns 200` with `cwd=cfg.bot_root`, env `PARSER_BOT_ROOT=cfg.bot_root`, timeout `cfg.fix_sec`. The skill's JSON contract (Task 15): `{"lender","tier","error_type","status","branch","commits":[],"files":[],"tests":{"rate":"PASSED|FAILED","adj":"PASSED|FAILED"},"notes"}`.

- [ ] **Step 1: Write the failing test**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_fixer.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'parser_bot.fixer'`

- [ ] **Step 3: Implement `parser_bot/fixer.py`**

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_fixer.py -q`
Expected: `3 passed`

- [ ] **Step 5: Commit**

```bash
cd /Users/trungthach/IdeaProjects/tools
git add parser-bot/parser_bot/fixer.py parser-bot/tests/test_fixer.py
git commit -m "parser-bot: run fix-parser headless and parse its summary"
```

---

### Task 14: Bot wiring (`bot.py`)

**Files:**
- Create: `parser_bot/bot.py`
- Test: `tests/test_bot.py`

**Interfaces:**
- Consumes: everything above. Constructor takes already-built collaborators so tests inject fakes: `Bot(cfg, lf, chat, jira, triager, fixer, lenders: LenderIndex, now=None, dry_run=False, log=print)`.
- Produces: `poll_once() -> list[TriageResult]` (fetch failures since `now - lookback_hours`, dedupe by RateUpdate key and by `lender|channel` per night, run `triager.prepare_night` then `triage`, post to Chat with `thread_key=f"{lender}-{MM-DD}"`, persist state with `TRIAGED`/`NOT_CODE`); `handle_command(cmd: Command) -> str` (reply text; also performs fix/skip); `run(once: bool, listener: bool)`; `main(argv)` with `--config`, `--once`, `--dry-run`, `--no-listener`. In `dry_run` nothing is posted, no Jira, no claude — replies/messages are logged instead.

- [ ] **Step 1: Write the failing test**

```python
from datetime import datetime
from types import SimpleNamespace as NS
from parser_bot.bot import Bot
from parser_bot.classify import Classification
from parser_bot.commands import Command
from parser_bot.fixer import FixResult
from parser_bot.lenders import LenderIndex
from parser_bot.lf_api import RateFailure
from parser_bot.nights import ICT
from parser_bot.state import NightState, TRIAGED, NOT_CODE, FIXED, SKIPPED
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
    def prepare_night(self, state): self.prepared += 1; state.prepared = True
    def triage(self, failure): return self.results[failure.lender]


class FakeJira:
    def __init__(self): self.comments = []
    def ensure_ticket(self, state, label, date_pt): state.ticket = state.ticket or "MOSO-9"; return state.ticket
    def comment(self, key, text): self.comments.append((key, text))


class FakeFixer:
    def __init__(self, result): self.result, self.calls = result, []
    def run(self, lender, key, plan_only=False): self.calls.append((lender, key, plan_only)); return self.result


def layout(lender):
    return TriageResult(lender, "QM", True, "/tmp/x.xlsx", Classification("LAYOUT", "CRAWL_MISMATCH", "hdr moved", "FAILED", "PASSED"), "1", 2, False, "")


def build(tmp_path, failures, results, fix=None, commands_enabled=True):
    cfg = make_cfg(tmp_path); cfg.commands_enabled = commands_enabled
    lf, chat, jira = FakeLF(failures), FakeChat(), FakeJira()
    fixer = FakeFixer(fix or FixResult("fixed", "1", "CRAWL_MISMATCH", "MOSO-9", ["c1"], ["T.java"], {"rate": "PASSED", "adj": "PASSED"}, "ok"))
    bot = Bot(cfg, lf, chat, jira, FakeTriager(results), fixer, LENDERS, now=lambda: NOW)
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
    assert bot.poll_once() == [] and len(chat.posts) == 2          # same keys again → nothing new
    assert bot.triager.prepared == 1


def test_fix_command_creates_ticket_runs_fixer_and_reports(tmp_path):
    f1 = RateFailure("k1", "c", "AAALendings", "Error while parsing rates for AAALendings")
    bot, cfg, chat, jira, fixer = build(tmp_path, [f1], {"AAALendings": layout("AAALendings")})
    bot.poll_once()
    reply = bot.handle_command(Command("fix", "AAA", "t@lf", "Trung", "spaces/S/threads/AAALendings-09-03", "spaces/S"))
    assert fixer.calls == [("AAALendings", "MOSO-9", False)]
    assert reply.startswith("✅ *AAA Lendings* fixed — branch MOSO-9")
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_bot.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'parser_bot.bot'`

- [ ] **Step 3: Implement `parser_bot/bot.py`**

```python
"""Wiring: poll LF for failures → triage → Chat; Pub/Sub commands → fix → Chat + Jira."""
from __future__ import annotations

import argparse
import json
import logging
import os
import threading
import time
from datetime import datetime, timedelta

from . import messages
from .chat import ChatClient
from .commands import Command, parse_event
from .config import Config, load_config
from .fixer import Fixer, FixResult
from .jira import JiraClient
from .lenders import LenderIndex, load_index
from .lf_api import LFClient
from .nights import ICT, ict_clock, in_window, night_id, pacific_date
from .state import (AWAITING_CONFIRM, FIX_FAILED, FIXED, FIXING, NOT_CODE, SKIPPED, TRIAGED, LenderState, NightState)
from .triage import Triager, TriageResult, channel_of

log = logging.getLogger("parser-bot")


class Bot:
    def __init__(self, cfg: Config, lf, chat, jira, triager, fixer, lenders: LenderIndex, now=None, dry_run: bool = False):
        self.cfg, self.lf, self.chat, self.jira, self.triager, self.fixer, self.lenders = cfg, lf, chat, jira, triager, fixer, lenders
        self.now = now or (lambda: datetime.now(tz=ICT))
        self.dry_run = dry_run
        self.fix_lock = threading.Lock()

    # ---- helpers -------------------------------------------------------------------------------
    def state(self) -> NightState:
        return NightState.load(self.cfg.state_dir, night_id(self.now()))

    def _post(self, text: str, thread_key: str | None = None, thread_name: str | None = None) -> str:
        if self.dry_run:
            log.info("[dry-run] would post (%s): %s", thread_key or thread_name, text)
            return ""
        return (self.chat.post(text, thread_key=thread_key, thread_name=thread_name).get("thread") or {}).get("name", "")

    def _sheet_uri(self, res: TriageResult) -> str:
        if not res.sheet:
            return ""
        d = self.now().astimezone(ICT).date()
        name = res.lender + ("NonQM" if res.channel == "NonQM" else "")
        return f"gs://{self.cfg.gcs_bucket}/history/{name}/{d:%Y}/{d:%m}/{d:%d}/ ({os.path.basename(res.sheet)})"

    # ---- poller --------------------------------------------------------------------------------
    def poll_once(self) -> list[TriageResult]:
        now = self.now()
        st = self.state()
        failures = self.lf.failures_since(now - timedelta(hours=self.cfg.lookback_hours))
        fresh = [f for f in failures if st.mark_seen(f.key)]
        st.save()
        results: list[TriageResult] = []
        if fresh and not st.prepared:
            self.triager.prepare_night(st)   # pull clones + mvn install moso-pricing, once per night
        for f in fresh:
            channel = channel_of(f)
            k = st.key(f.lender, channel)
            if k in st.lenders:
                continue  # one thread per lender+channel per night; later zone builds are noise
            res = self.triager.triage(f)
            label = self.lenders.label(f.lender)
            text = messages.triage_text(res, label, ict_clock(now), self._sheet_uri(res))
            thread = self._post(text, thread_key=f"{f.lender}-{now.astimezone(ICT):%m-%d}")
            status = TRIAGED if res.classification.cls == "LAYOUT" else NOT_CODE
            st.lenders[k] = LenderState(lender=f.lender, channel=channel, status=status, detected_at=now.isoformat(),
                                        reason=f.description, cause=res.classification.cause, cls=res.classification.cls,
                                        error_type=res.classification.error_type, tier=res.tier, streak=res.streak,
                                        sheet=res.sheet, thread_name=thread)
            st.save()
            results.append(res)
        return results

    # ---- commands ------------------------------------------------------------------------------
    def _find(self, st: NightState, text: str) -> tuple[LenderState | None, str]:
        r = self.lenders.resolve(text)
        if r.kind != "one":
            return None, messages.unknown_lender_text(text, r.matches)
        hits = [ls for ls in st.lenders.values() if ls.lender == r.matches[0]]
        if not hits:
            return None, messages.unknown_lender_text(text, [])
        return hits[0], ""

    def handle_command(self, cmd: Command) -> str:
        st = self.state()
        if cmd.kind == "status":
            return messages.status_text(st, {e: self.lenders.label(e) for e in {ls.lender for ls in st.lenders.values()}})
        if cmd.kind == "fix_all":
            targets = [ls for ls in st.lenders.values() if ls.status in (TRIAGED, AWAITING_CONFIRM, FIX_FAILED)]
            if not targets:
                return "Nothing to fix tonight."
            return "\n".join(self._fix(st, ls) for ls in targets)
        ls, err = self._find(st, cmd.lender_text)
        if not ls:
            return err
        if cmd.kind == "skip":
            ls.status = SKIPPED
            st.save()
            return f"Skipped {self.lenders.label(ls.lender)} for tonight."
        return self._fix(st, ls)  # fix | retry

    def _fix(self, st: NightState, ls: LenderState) -> str:
        label = self.lenders.label(ls.lender)
        if not self.cfg.commands_enabled:
            return messages.disabled_text()
        if ls.status == NOT_CODE:
            return f"{label}: {ls.cause}. Not a parser problem, nothing to fix."
        if ls.status in (FIXING, FIXED):
            return f"{label} is already {ls.status.lower()}" + (f" on branch {ls.branch}." if ls.branch else ".")
        if self.dry_run:
            return f"[dry-run] would fix {label}"
        with self.fix_lock:
            key = self.jira.ensure_ticket(st, label, pacific_date(self.now()))
            ls.status = FIXING
            st.save()
            fix: FixResult = self.fixer.run(ls.lender, key)
            ls.branch = fix.branch or key
            if fix.status == "fixed":
                ls.status, text = FIXED, messages.result_text(label, fix, key)
            else:
                ls.status, text = FIX_FAILED, messages.failure_text(label, fix, key)
            ls.notes = fix.notes
            st.save()
            self.jira.comment(key, self._jira_comment(label, ls, fix))
            return text

    @staticmethod
    def _jira_comment(label: str, ls: LenderState, fix: FixResult) -> str:
        body = [f"h3. {label} ({ls.channel})", f"* Cause: {ls.error_type} — {ls.cause}", f"* Tier: {fix.tier or ls.tier}",
                f"* Status: {fix.status}", f"* Branch: {fix.branch}", f"* Files: {', '.join(fix.files) or '-'}",
                f"* Tests: {json.dumps(fix.tests)}", f"* Notes: {fix.notes or '-'}"]
        if fix.raw_tail:
            body += ["{code}", fix.raw_tail[-1500:], "{code}"]
        return "\n".join(body)

    # ---- loops ---------------------------------------------------------------------------------
    def listen_once(self) -> None:
        from .pubsub import pull_events
        for ev in pull_events(self.cfg.gcp_subscription, self.cfg.gcp_service_account_file):
            cmd = parse_event(ev)
            if not cmd:
                continue
            if self.cfg.allowlist and cmd.sender_email not in self.cfg.allowlist:
                self._post(f"Sorry {cmd.sender_name}, you are not on the allowlist.", thread_name=cmd.thread_name)
                continue
            log.info("command %s from %s", cmd, cmd.sender_email)
            try:
                reply = self.handle_command(cmd)
            except Exception as e:  # never let one command kill the loop
                log.exception("command failed")
                reply = f"Command failed: {e}"
            self._post(reply, thread_name=cmd.thread_name or None)

    def run(self, once: bool = False, listener: bool = True) -> None:
        last_poll = 0.0
        while True:
            now = self.now()
            if in_window(now, self.cfg.poll_start, self.cfg.poll_end) and time.time() - last_poll >= self.cfg.poll_interval_sec:
                try:
                    self.poll_once()
                except Exception:
                    log.exception("poll failed")
                last_poll = time.time()
            if listener:
                try:
                    self.listen_once()
                except Exception:
                    log.exception("listener failed")
                    time.sleep(10)
            if once:
                return
            if not listener:
                time.sleep(min(30, self.cfg.poll_interval_sec))


def build_bot(cfg: Config, dry_run: bool) -> Bot:
    creds = json.loads(open(cfg.lf_credentials_file, encoding="utf-8").read())
    lf = LFClient(cfg.lf_base_url, cfg.lf_ns, creds["username"], creds["password"])
    chat = ChatClient(cfg.gcp_service_account_file, cfg.space)
    jira = JiraClient(cfg.jira_base_url, os.environ[cfg.jira_email_env], os.environ[cfg.jira_token_env],
                      cfg.jira_project, cfg.jira_assignee)
    return Bot(cfg, lf, chat, jira, Triager(cfg), Fixer(cfg), load_index(cfg.lenders_json, cfg.aliases), dry_run=dry_run)


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(prog="parser-bot")
    ap.add_argument("--config", default=os.path.expanduser("~/.config/parser-bot/config.yaml"))
    ap.add_argument("--once", action="store_true", help="one poll + one pull, then exit")
    ap.add_argument("--dry-run", action="store_true", help="never post, never create Jira, never run claude")
    ap.add_argument("--no-listener", action="store_true")
    ap.add_argument("--force-window", action="store_true", help="poll even outside the active window")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    cfg = load_config(args.config)
    if args.force_window:
        cfg.poll_start, cfg.poll_end = "00:00", "23:59"
    build_bot(cfg, args.dry_run).run(once=args.once, listener=not args.no_listener)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run the whole suite**

Run: `.venv/bin/python -m pytest -q`
Expected: all tests pass (`test_bot.py` 3 passed, total ≥ 25), no warnings about unclosed files.

- [ ] **Step 5: Commit**

```bash
cd /Users/trungthach/IdeaProjects/tools
git add parser-bot/parser_bot/bot.py parser-bot/tests/test_bot.py
git commit -m "parser-bot: wire poller, command handling and main loop"
```

---

### Task 15: `/fix-parser` AUTO MODE (skill contract)

**Files:**
- Modify: `tools/claude-sync/skills/fix-parser/SKILL.md` (insert a new section right after `## Environment & Constants`, before `## DASHBOARD INTEGRATION`; also change the `Usage:` line in the front-matter description to `Usage: /fix-parser [@assigneeId] | /fix-parser --auto --lender <LenderType> --key <MOSO-n> [--plan-only]`).
- The skill is prose executed by Claude; there is no unit test. Verification is a controlled headless run (Step 3).

**Interfaces:**
- Consumes: `PARSER_BOT_ROOT` env (Task 13 sets it), `--lender <LenderType enum>`, `--key <MOSO-n>`, `--plan-only`.
- Produces: the fenced JSON summary `fixer.parse_summary` expects: `{"lender","tier","error_type","status","branch","commits":[],"files":[],"tests":{"rate","adj"},"notes"}` with `status ∈ fixed | failed | planned`.

- [ ] **Step 1: Insert the AUTO MODE section**

Add this text to `SKILL.md` after the `## Environment & Constants` block:

````markdown
## AUTO MODE (`--auto`) — used by Parser Bot, no human at the keyboard

Arguments: `--auto --lender <LenderType enum name> --key <MOSO-n> [--plan-only]`.

Rules that differ from interactive mode:

1. **Paths.** If env `PARSER_BOT_ROOT` is set, use `$PARSER_BOT_ROOT/moso-pricing` and `$PARSER_BOT_ROOT/packs/loan`
   instead of `MOSO_PRICING` / `PACKS_LOAN`. Never touch `/Users/trungthach/IdeaProjects/moso-pricing` or `.../packs`.
2. **No prompts.** Skip STEP 1 (JQL) and STEP 2 (task list). The single lender is `--lender`; the Jira key is `--key`.
   Never call AskUserQuestion. If something is ambiguous, choose the safest option and record it in `notes`.
3. **No Jira transitions.** The bot owns the ticket. Do not change status; you may add a comment.
4. **Branch.** Before editing, in BOTH clones: `git fetch origin && git checkout -B <KEY> origin/master`.
5. **Work exactly as STEP 3–4** (build moso-pricing jar → download → update inputStream refs → first test pass →
   classify → tier fix → verify BOTH `RateParserTest` and `AdjustmentParsersTest` → update cookbook).
6. **`--plan-only`.** Stop after classification. Print the summary with `"status": "planned"`, revert any file changes
   (`git checkout -- .` in both clones, keep downloaded sheets), do not commit.
7. **Commit + push (auto mode only; interactive mode still never commits).** One commit per repo touched:
   `git add <files you changed>` (never `-A`), message `KEY: fix <LenderType> parser (<error_type>)`, no body,
   no trailers. Then `git push -u origin <KEY>`. Never push master. If tests fail after 3 escalations, still commit
   the attempt on the branch with message `KEY: WIP <LenderType> parser fix (tests failing)` and report `"status": "failed"`.
8. **Final output.** The LAST thing printed must be exactly one fenced block:

```json
{"lender": "<LenderType>", "tier": "0|1|2", "error_type": "<CRAWL_MISMATCH|...>", "status": "fixed|failed|planned",
 "branch": "<KEY>", "commits": ["<sha7>", "..."], "files": ["<relative paths>"],
 "tests": {"rate": "PASSED|FAILED", "adj": "PASSED|FAILED"}, "notes": "<one sentence: what changed or why it failed>"}
```
   Nothing after this block. `commits` are short SHAs from `git log origin/master..<KEY> --format=%h` in each repo.
````

- [ ] **Step 2: Update the front-matter usage line**

Change `Usage: /fix-parser [@assigneeId]` to `Usage: /fix-parser [@assigneeId] | /fix-parser --auto --lender <LenderType> --key <MOSO-n> [--plan-only]`.

- [ ] **Step 3: Verify with a plan-only headless run (after Task 16 has created the bot clones)**

```bash
cd /Users/trungthach/IdeaProjects/worktrees/bot
PARSER_BOT_ROOT=$PWD claude -p "/fix-parser --auto --lender Provident --key MOSO-0 --plan-only" --permission-mode acceptEdits --max-turns 200 | tee /tmp/parser-bot-planonly.log | tail -20
cd /Users/trungthach/IdeaProjects/tools/parser-bot && .venv/bin/python -c "from parser_bot.fixer import parse_summary; import json; print(json.dumps(parse_summary(open('/tmp/parser-bot-planonly.log').read()), indent=1))"
git -C /Users/trungthach/IdeaProjects/worktrees/bot/moso-pricing status --short; git -C /Users/trungthach/IdeaProjects/worktrees/bot/packs status --short
```
Expected: `parse_summary` prints a dict with `"status": "planned"`; both `git status` outputs show no modified tracked files (downloaded sheets may appear as untracked). If the summary is missing, fix the SKILL wording (usually: an extra sentence printed after the block) and rerun.

- [ ] **Step 4: Commit**

```bash
cd /Users/trungthach/IdeaProjects/tools
git add claude-sync/skills/fix-parser/SKILL.md
git commit -m "fix-parser: add --auto mode contract for parser-bot"
```

---

### Task 16: Operations — clones, refresh, launchd, README, Phase A

**Files:**
- Create: `tools/parser-bot/setup_clones.sh`, `tools/parser-bot/refresh_clones.sh`, `tools/parser-bot/run.sh`, `tools/parser-bot/launchd/com.loanfactory.parser-bot.plist`, `tools/parser-bot/README.md`

- [ ] **Step 1: Clone scripts**

`setup_clones.sh`:

```bash
#!/usr/bin/env bash
# One-time: bot-owned shared clones (git worktrees cannot build: parent pom copies .git/HEAD as a resource).
set -euo pipefail
ROOT=/Users/trungthach/IdeaProjects
BOT=$ROOT/worktrees/bot
mkdir -p "$BOT"
[ -d "$BOT/moso-pricing" ] || git clone --shared -b master "$ROOT/moso-pricing" "$BOT/moso-pricing"
[ -d "$BOT/packs" ]        || git clone --shared -b master "$ROOT/packs" "$BOT/packs"
for r in moso-pricing packs; do
  git -C "$BOT/$r" remote set-url origin "$(git -C "$ROOT/$r" remote get-url origin)"
  git -C "$BOT/$r" fetch -q origin && git -C "$BOT/$r" checkout -q master && git -C "$BOT/$r" reset -q --hard origin/master
done
echo "bot clones ready under $BOT"
```

`refresh_clones.sh` (what `Triager.prepare_night` does, runnable by hand):

```bash
#!/usr/bin/env bash
set -euo pipefail
BOT=/Users/trungthach/IdeaProjects/worktrees/bot
for r in moso-pricing packs; do git -C "$BOT/$r" checkout -q master && git -C "$BOT/$r" pull -q --ff-only; done
(cd "$BOT/moso-pricing" && mvn -q install -DskipTests -Pjar-packaging -Dgwt.compiler.skip=true)
echo "clones on master, moso-pricing installed to ~/.m2"
```

`run.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
[ -x .venv/bin/python ] || { python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt; }
export PATH="/opt/homebrew/bin:/opt/homebrew/opt/openjdk@21/bin:/Users/trungthach/.local/bin:/Users/trungthach/google-cloud-sdk/bin:/usr/bin:/bin"
[ -f ~/.config/parser-bot/env ] && set -a && . ~/.config/parser-bot/env && set +a   # JIRA_EMAIL, JIRA_API_TOKEN
exec .venv/bin/python -m parser_bot.bot "$@"
```

`chmod +x setup_clones.sh refresh_clones.sh run.sh`

- [ ] **Step 2: launchd plist**

`launchd/com.loanfactory.parser-bot.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.loanfactory.parser-bot</string>
  <key>ProgramArguments</key><array>
    <string>/Users/trungthach/IdeaProjects/tools/parser-bot/run.sh</string>
    <string>--config</string><string>/Users/trungthach/.config/parser-bot/config.yaml</string>
  </array>
  <key>WorkingDirectory</key><string>/Users/trungthach/IdeaProjects/tools/parser-bot</string>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>/Users/trungthach/IdeaProjects/tools/parser-bot/logs/bot.log</string>
  <key>StandardErrorPath</key><string>/Users/trungthach/IdeaProjects/tools/parser-bot/logs/bot.err</string>
</dict></plist>
```

- [ ] **Step 3: README with the human setup checklist**

`README.md` must contain, verbatim, these sections:

````markdown
# Parser Bot

Triage overnight lender parse failures in Google Chat; fix only on `@Parser Bot fix <lender>`.
Spec: `docs/superpowers/specs/2026-09-03-parser-bot-design.md`. Plan: `docs/superpowers/plans/2026-09-03-parser-bot.md`.

## One-time setup (human)

1. LF bot account: create admin `parser-bot@loanfactory.com` with owner permission; save
   `~/.config/parser-bot/lf.json` = `{"username": "parser-bot@loanfactory.com", "password": "..."}`; `chmod 600`.
2. Jira: `~/.config/parser-bot/env` with `JIRA_EMAIL=...` and `JIRA_API_TOKEN=...`; `chmod 600`.
3. GCP (needs `gcloud auth login` first):
   ```bash
   gcloud config set project lenderrate-master
   gcloud services enable chat.googleapis.com pubsub.googleapis.com
   gcloud pubsub topics create parser-bot-events
   gcloud pubsub topics add-iam-policy-binding parser-bot-events \
     --member=serviceAccount:chat-api-push@system.gserviceaccount.com --role=roles/pubsub.publisher
   gcloud pubsub subscriptions create parser-bot-sub --topic=parser-bot-events --ack-deadline=60
   gcloud iam service-accounts create parser-bot --display-name="Parser Bot"
   gcloud pubsub subscriptions add-iam-policy-binding parser-bot-sub \
     --member=serviceAccount:parser-bot@lenderrate-master.iam.gserviceaccount.com --role=roles/pubsub.subscriber
   mkdir -p ~/.config/parser-bot && gcloud iam service-accounts keys create ~/.config/parser-bot/sa.json \
     --iam-account=parser-bot@lenderrate-master.iam.gserviceaccount.com && chmod 600 ~/.config/parser-bot/sa.json
   ```
4. Chat app (console → APIs & Services → Google Chat API → Configuration): name `Parser Bot`, description
   `Triage and fix ratesheet parser failures`, avatar any HTTPS PNG, **uncheck** "Build this Chat app as a Google
   Workspace add-on", Functionality: "Join spaces and group conversations", Connection settings: Cloud Pub/Sub,
   topic `projects/lenderrate-master/topics/parser-bot-events`, Visibility: specific people/groups (Trung + IT),
   Log errors to Logging. Save. Then in the Parser Alerts space: Apps & integrations → Add apps → Parser Bot.
5. Config: `cp config.example.yaml ~/.config/parser-bot/config.yaml` and edit if paths differ.
6. Clones + index: `./setup_clones.sh && ./refresh_clones.sh` and
   `.venv/bin/python -m parser_bot.lenders /Users/trungthach/IdeaProjects/packs/quote/src/main/java/com/mvu/quote/shared/typekey/LenderType.java state/lenders.json`.

## Run

- Smoke test (no posting, no Jira, no claude): `./run.sh --once --dry-run --force-window`
- One real poll + pull: `./run.sh --once --force-window`
- Daemon: `cp launchd/com.loanfactory.parser-bot.plist ~/Library/LaunchAgents/ && launchctl load ~/Library/LaunchAgents/com.loanfactory.parser-bot.plist`
- Logs: `logs/bot.log`, `logs/bot.err`. State: `state/<night>.json`.
- Stop: `launchctl unload ~/Library/LaunchAgents/com.loanfactory.parser-bot.plist`

## Phase A → B

Phase A: `commands_enabled: false`; the bot only triages. After ~1 week of correct causes, set
`commands_enabled: true` and `launchctl unload && launchctl load`. Commands: `@Parser Bot fix <lender>`,
`fix all`, `skip <lender>`, `retry <lender>`, `status`.
````

- [ ] **Step 4: Manual verification (record output in the commit message body is NOT needed; paste into the Jira comment later)**

```bash
cd /Users/trungthach/IdeaProjects/tools/parser-bot
./setup_clones.sh && ./refresh_clones.sh
.venv/bin/python -m parser_bot.lenders /Users/trungthach/IdeaProjects/packs/quote/src/main/java/com/mvu/quote/shared/typekey/LenderType.java state/lenders.json
./run.sh --once --dry-run --force-window --no-listener        # needs lf.json; prints "[dry-run] would post" lines or "no failures"
```
Expected: exits 0; `state/<night>.json` written; no Chat message appeared. Then, when GCP setup is done:
`./run.sh --once --force-window` → triage threads appear in the space for any failure in the last 6 hours; `@Parser Bot status` in the space gets a reply within one loop.

- [ ] **Step 5: Commit**

```bash
cd /Users/trungthach/IdeaProjects/tools
git add parser-bot/setup_clones.sh parser-bot/refresh_clones.sh parser-bot/run.sh parser-bot/launchd/com.loanfactory.parser-bot.plist parser-bot/README.md
git commit -m "parser-bot: add clone scripts, launchd unit and setup README"
```

---

## Self-review

- **Spec coverage.** §2 flow → Tasks 5, 8, 9, 10, 11, 12, 13, 14. §3 modules → one task each (`pubsub.py` folded into Task 11). §4 fix-parser changes → Task 15. §5 classification → Task 6 (+ tier prediction Task 7). §6 messages → Task 9. §7 safety: no master push (Task 15 rule 7), commands gate (Task 14 `_fix`), one fix at a time (`fix_lock`), timeouts (Tasks 8, 13), bot clones (Task 16), secrets outside git (Task 16 README). §8 setup → Task 16 README. §9 testing → unit tests in every task, dry-run in Task 14/16, plan-only E2E in Task 15. §10 open items: allowlist kept in config; multi-zone dedupe via `lender|channel` key (Task 14).
- **Placeholders.** None; every code step is complete. Illustrative keys (`MOSO-9`, `MOSO-17140`) appear only in tests/messages.
- **Type consistency.** `TriageResult` fields (Task 8) match `messages.triage_text` and `bot.poll_once`; `FixResult` (Task 13) matches `messages.result_text/failure_text` and `bot._fix`; `Command` (Task 11) matches `bot.handle_command`; `NightState.key()`/`LenderState` (Task 3) used identically in Tasks 8, 9, 12, 14; `Config` property names (Task 1) used verbatim in Tasks 8, 13, 14, 16.
