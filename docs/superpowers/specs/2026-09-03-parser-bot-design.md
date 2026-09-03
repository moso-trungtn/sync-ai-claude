# Parser Bot — chat-confirmed parser triage & fix (design)

Date: 2026-09-03. Status: draft for review. Related: moso-pricing MOSO-17136 (parse-failure chat alert),
`/fix-parser` skill, `ratesheet-watch` pipeline (headless `claude -p` pattern).

## 1. Goal

When a lender ratesheet parse fails overnight (20:00–04:00 ICT), a bot in the Google Chat space
**Parser Alerts**:

1. explains *why* it failed within minutes (triage), without changing any code;
2. waits for a human to say `@Parser Bot fix <lender>`;
3. fixes the parser on a branch, runs both parser test suites, pushes the branch, records evidence in
   **one Jira ticket per night**, and reports back in the same thread.

Non-goals (v1): merging to master, fixing login/download/Selenium problems, fixing anything without a
human confirmation, acting on staging failures.

## 2. Flow

```
builder fails ──► ParseFailureNotifier (MOSO-17136) ──► webhook alert in Space   (exists)
                                    │
bot poller (2 min) ── LF API rate_update?status=false ──► new failure
        │
        ▼
triage (read-only, bot clones): download today's sheet ─► parser-fix.sh --both ─► classify
        │
        ▼
post thread "<Lender> <MM/DD>": cause, predicted tier, "@Parser Bot fix <lender>"
        │
human: @Parser Bot fix AAA  ──► Pub/Sub ──► bot listener
        │
        ▼
nightly Jira ticket (create on first confirm, else append lender)
        │
        ▼
claude -p "/fix-parser --auto --lender AAA --key MOSO-xxxxx" in bot clones
        │
        ▼
tests pass ─► commit + push branch MOSO-xxxxx ─► Jira comment (diff summary, test output)
        │
        ▼
reply in thread: fixed (branch, files, what changed) | could not fix (why) | not a code problem
```

## 3. Components (`tools/parser-bot/`, Python 3.12, runs on Trung's Mac via launchd)

| Module | Responsibility |
|---|---|
| `bot.py` | launchd daemon. Two loops: poller (active window 19:30–05:30 ICT) and Pub/Sub listener (always on). One fix at a time (asyncio lock). |
| `lf_api.py` | LF EntityAPI client. `POST /api/oauth2/v1/LOAN_FACTORY/token` (password grant, bot admin account), refresh at 25 min. `GET /api/entity/v1/rate_update?created>=<since>&l=200&o=-created`, filter `status == false` client-side (avoids a new Datastore composite index). |
| `triage.py` | For a failure: resolve LenderType → parser test names via `packs/loan/lender-info.sh`; `download-ratesheet.sh <lender> [--nonqm] --no-detect`; `parser-fix.sh <lender> --ratesheet <file> --both`; read `/tmp/parser-fix/<lender>/report.txt`; classify (see §5); read cookbook entry (`parser_fix_cookbook.md`) for tier prediction. Deterministic, no LLM. |
| `chat.py` | Chat API `spaces.messages.create` with app credentials (scope `chat.bot`), `threadKey = "<LenderType>-<MM-DD>"`, `messageReplyOption=REPLY_MESSAGE_FALLBACK_TO_NEW_THREAD`. |
| `commands.py` | Pub/Sub pull, parse `MESSAGE` events: `fix <lender>`, `fix all`, `skip <lender>`, `retry <lender>`, `status`. Lender resolution: LenderType name, display name, or alias table; ambiguous → ask. Anyone in the space may command (user decision 2026-09-03). |
| `fixer.py` | Runs `claude -p "/fix-parser --auto --lender <L> --key <KEY>" --permission-mode acceptEdits --max-turns 200` with `PARSER_BOT_ROOT` pointing at the bot clones; 60 min timeout; parses the JSON summary block the skill prints last. |
| `jira.py` | Nightly ticket: `[Parser failed] MM/DD/YYYY: L1 · L2` (US/Pacific date, middle-dot separator — lender names contain commas), Task, label `parser`, In Progress. Created on first confirm; later lenders appended to summary + a comment each. Assignee from config (default Trung). |
| `state.py` | `state/<night>.json`: per lender `DETECTED → TRIAGED → AWAITING_CONFIRM → FIXING → FIXED | FIX_FAILED | SKIPPED | NOT_CODE`, RateUpdate keys seen, ticket key, thread names. Idempotent restarts. |
| `config.yaml` | Space name, LF bot credentials path, Jira creds env names, allowlist (empty = anyone), `commands_enabled` (Phase A = false), active window, paths. |

Repos: bot clones at `worktrees/bot/moso-pricing` and `worktrees/bot/packs` made with `git clone --shared`
(git worktrees cannot build: parent pom copies `.git/HEAD`). `mvn install` of moso-pricing writes the same
`~/.m2` snapshot the human uses — acceptable at night, noted.

## 4. fix-parser changes (`tools/claude-sync/skills/fix-parser/SKILL.md`)

Add `--auto --lender <L> --key <KEY>` mode; interactive mode unchanged.

- Skip STEP 1–2 (JQL + task list prompt). One lender, given key.
- Paths from `PARSER_BOT_ROOT` env when set (else current constants).
- Keep: download → update inputStream refs → first test pass → classify → tier fix → verify both tests → cookbook learn.
- New in auto mode: `git checkout -B <KEY>` in both clones, commit `KEY: fix <Lender> parser (<error type>)`
  per repo touched, `git push -u origin <KEY>` (branch only, never master). Existing rule "NO AUTO-COMMIT"
  applies to interactive mode only.
- Print a final fenced JSON block `{lender, tier, error_type, status, branch, commits[], files[], tests{rate, adj}, notes}`
  for `fixer.py`.
- Jira: no transitions (bot owns the ticket); post one comment with the JSON summary + test tail.

## 5. Classification

| Class | Signal | Bot says / does |
|---|---|---|
| `LOGIN_DOWNLOAD` | download-ratesheet.sh finds no new file **and** the alert reason matches `login|rejected|imperva|403|timeout|selenium|download|captcha|credential` | "Not a code problem — credentials/site. IT action." No fix offered. |
| `EMAIL_MISSING` | download-ratesheet.sh finds no new file and the reason does not match the login/download regex — including `Could not handle email` and any other no-sheet CRON_JOB build | "No ratesheet arrived / email unreadable." No fix offered. |
| `LAYOUT` | new sheet downloaded and `parser-fix.sh` reports VALUE_MISMATCH / CRAWL_MISMATCH / KEYWORD_MISSING / STRUCTURE_CHANGE / RATE_COUNT / NULL_POINTER / NEW_ADJ_DETECTED | Cause line from report + cookbook tier prediction (0/1/2, streak). Offers `fix`. |
| `TESTS_GREEN` | new sheet parses locally with no error | "Local tests pass on today's sheet — likely transient/builder issue. Retry the build instead." |

## 6. Messages

Triage (new thread per lender per night):

```
🔎 *AAA Lendings* (QM) failed 21:14 ICT
• Cause: CRAWL_MISMATCH — row label "Credit Score" not found (sheet now says "FICO Score")
• Prediction: Tier 1 (cookbook streak 4) · ~10 min
• Sheet: gs://lender-rate-ratesheet/history/AAALendings/2026/09/03/...
Reply `@Parser Bot fix AAA` to fix, `@Parser Bot skip AAA` to ignore.
```

Result:

```
✅ *AAA Lendings* fixed — branch MOSO-17140, 2 commits, tests: RateParserTest ✓ AdjustmentParsersTest ✓
• Changed: AAALendingsTables.java (crawlNote "Credit Score" → "FICO Score"), adj-expectations/aaa.txt
• Jira: MOSO-17140 (comment with diff + test output). Review & merge in the morning.
```

Failure: `❌ *AAA Lendings* not fixed after Tier 2 — <reason>. Left on branch MOSO-17140 for a human.`

## 7. Safety

- Never merge or push master. Push only `MOSO-xxxxx` branches.
- No fix without a command; `commands_enabled=false` in Phase A (triage only, ~1 week) to validate causes.
- One fix at a time; triage timeout 15 min, fix timeout 60 min; on timeout report and mark `FIX_FAILED`.
- Bot never edits the human's checkouts; only its own clones.
- Secrets (`sa.json`, LF bot password, Jira token) in `~/.config/parser-bot/`, mode 600, never in git.
- Staging failures are not polled (LF prod API only).

## 8. Setup (once, human)

GCP (`lenderrate-master`, after `gcloud auth login`): enable Google Chat API + Pub/Sub API; topic
`parser-bot-events`; grant `chat-api-push@system.gserviceaccount.com` Pub/Sub Publisher on it; pull
subscription `parser-bot-sub`; service account `parser-bot@lenderrate-master.iam.gserviceaccount.com`
with Pub/Sub Subscriber, key → `~/.config/parser-bot/sa.json`. Chat API configuration: name "Parser Bot",
not an add-on, connection = Cloud Pub/Sub (topic above), functionality "Join spaces and group
conversations", visibility "specific people and groups" (Trung + IT). Add the app to the Parser Alerts space.

LF: admin account `parser-bot@loanfactory.com` (owner permission for EntityAPI). Jira: existing REST token.

## 9. Testing

- Unit: `classify()`, command parsing + lender resolution, nightly-ticket naming (US/Pacific), state
  transitions, LF token refresh (mocked HTTP), Chat threadKey.
- Dry run: `bot.py --dry-run` posts to a test space and never runs `claude`.
- E2E: replay a known past failure (RateUpdate of a fixed lender) through triage; then one supervised
  `fix` on a real failure with `commands_enabled=true`.

## 10. Open items

- Chat app creation may hit a Workspace admin gate (webhooks were allowed, so likely fine). Fallback: Jira
  comment `fix <lender>` as the command channel; everything else unchanged.
- Multi-zone lenders alert per zone build; triage dedupes by LenderType per night.
- Phase B extension (not now): auto-fix Tier 0 with streak ≥ 5 without confirmation.
