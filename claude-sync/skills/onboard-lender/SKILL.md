---
name: onboard-lender
description: End-to-end orchestrator for taking ONE brand-new lender from "pick it off the tracking sheet" to "verified on staging" — recon (3 parallel read-only agents: registration/parser check, ratesheet fetch, matrix+guideline fetch) → /parser-task-builder (extract, scope-gate, file Jira Epic+sub-tasks) → /new-parser (implement, local commit) → CHECKPOINT (user reviews before push) → push → CHECKPOINT (user deploys staging) → /test-task (verify the deployed build). This is a thin sequencer — every real step is delegated to an existing skill; this file owns the parallel recon fan-out and the two human checkpoints none of those skills stop for on their own. The tracking sheet has THREE separate "not integrated" tabs (QM, Non-QM, Non-QM Correspondent) — the tab is part of the argument, not inferred. Trigger: "làm lender số N", "onboard <lender>", "next lender from the sheet", "/onboard-lender <tab> <name|#N|next>".
argument-hint: [qm|nonqm|corr] [lender full name | "#N" (row N in that tab) | "next" (first untouched team's-list row in that tab)] — tab is required, e.g. "nonqm #3", "nonqm next", "corr AmWest Funding"
allowed-tools: Bash, Read, Write, Glob, Grep, AskUserQuestion, Agent, Skill, WebSearch, WebFetch
---

# /onboard-lender — Recon → ticket → implement → 2 checkpoints → staging verify

> **House rule — docs and working files.** Per-task working files (specs, plans, test cases/results, screenshots, review notes) go ONLY to `/Users/trungthach/IdeaProjects/docs/changes/<KEY>/` (workspace, outside git) — never inside moso, moso-pricing, packs, base or moso-configuration, and never as `docs/changes/`, `docs/superpowers/` or `MOSO-xxxxx/` folders in a repo. Lender parser knowledge lives in `moso-pricing/docs/lenders/<slug>/` (`README.md` reference, `history.md` dated changes, `nonqm.md` Non-QM); after any parser change update that folder in the same commit. Contract: `moso-pricing/docs/lenders/README.md`.

You are a **thin sequencer**, not a reimplementation. Every real unit of work below already
has its own skill (`/parser-task-builder`, `/new-parser`, `/test-task`) — invoke them with the
`Skill` tool exactly as the user would type the slash command. This file's only original
content is: (a) the 3-way parallel recon fan-out before any of those run, and (b) the two
places this pipeline stops and waits for the user, because none of the skills it calls stop
there on their own.

**Read [[project_parser_task_builder_merge]] and [[project_nonqm_lender_sheet_tracking]] memory
before your first run if you haven't already — they explain why this skill exists and what the
sheet's columns mean.**

---

## Pipeline

```
0. Resolve target lender (name arg, "#N", or "next" → read the tracking sheet — MAIN LOOP,
   needs the Browser pane, not delegable to a subagent)
  │
  ▼
1. RECON — 3 parallel agents, read-only, no writes, single Agent-tool batch:
     1a. Verify lender    — lender-info.sh (existing parser?) + grep LenderType.java
                             (registered?) + loanfactory.com/our-lenders (approved?)
     1b. Fetch ratesheet   — download-ratesheet.sh --no-detect / GCS ratesheet-watch bucket /
                             lender-rate-email GCS object / else: flag "need email or
                             request-upload"
     1c. Fetch matrix+guideline — WebSearch/WebFetch the lender's own product guideline PDF /
                             else: flag "need matrix screenshots from the user"
  │
  ▼
2. Synthesize recon (MAIN LOOP) — report findings; if anything's blocked or missing, ask
   before continuing rather than guessing
  │
  ▼
3. Skill("parser-task-builder", <resolved ratesheet/matrix/guideline paths>)
   → extraction report, scope gate, Epic + sub-tasks filed
  │
  ▼
4. Skill("new-parser", <EPIC_KEY, or loop one sub-task key at a time>)
   → BA → Dev → QC, ends at local commit
  │
  ▼
5. ⏸ CHECKPOINT 1 — show `git diff --stat` + test results, AskUserQuestion: "Review this —
   push?" Only proceed to 6 on an explicit yes.
  │
  ▼
6. git push (only after 5's yes — never push without this specific ask, even if a broader
   "go ahead with everything" was given earlier in the conversation)
  │
  ▼
7. ⏸ CHECKPOINT 2 — tell the user it's pushed, ask them to deploy staging themselves (this
   skill has no deploy tool and doesn't try to find one), wait for their "it's live" before 8
  │
  ▼
8. Skill("test-task", <EPIC_KEY or sub-task keys>) → verify against the DEPLOYED build,
   screenshots, Jira comment, ticket left "In Progress" (never auto-Done)
```

---

## STEP 0 — Resolve the tab, then the target lender

The tracking sheet (`https://docs.google.com/spreadsheets/d/1BJ3MniiE9sBbQ6L-lZpE-WR2NVqvCGA5`) has **three separate "not integrated" tabs** — they are NOT the same list and don't share row numbers:

| Tab (exact name in the sheet) | Selector word | Feeds which `/parser-task-builder` workflow |
|---|---|---|
| `QM not integrated` | `qm` | QM new parser (Epic + per-program-group sub-tasks) |
| `Non-QM not integrated` | `nonqm` | Non-QM new parser (Epic + per-program sub-tasks) |
| `Non-QM Corress Not Integrated` | `corr` | Correspondent (single Task, no Epic — usually piggybacks on an existing Wholesale parser, see recon 1a) |

**Always resolve the tab first, never guess it from the lender name** — the same lender can legitimately appear on more than one tab (e.g. a Wholesale QM row and a separate Correspondent row).

**If the argument's first word matches `qm`/`nonqm`/`corr`** (or an unambiguous variant like "non-qm", "correspondent"), use that tab. **If it's missing or ambiguous**, ask via `AskUserQuestion` before opening the sheet — don't default silently, the three tabs produce structurally different tickets.

Once the tab is known, open the sheet in the Browser pane and click the tab by its exact name (tab gids aren't hardcoded here — click by label, the way you'd click any other tab; only the Non-QM tab's gid happens to be known from earlier use: `#gid=291558153`). This needs a logged-in session — if the sign-in wall shows up, ask the user to log in in that tab themselves (never enter credentials).

**Argument's remainder is a lender name** — use it directly on the resolved tab, skip to Step 1 (recon still matters even when you already know the name — it's what finds the actual files).

**Argument's remainder is `#N`** — row `N` = the `N`-th data row of the resolved tab (row 2 = #1). Read the Lender / Team's list? / Type / Programs / Status columns for that row (Correspondent tab's columns may differ slightly — read whatever header row it actually has, don't assume the Non-QM layout).

**Argument's remainder is `next` or missing** — same sheet read, but walk the resolved tab top to bottom and pick the first row where `Team's list? = YES` and `Status` is not `Ticket created (Backlog)` and not `Integrated`. If a row already has a Backlog Epic (Status = `Ticket created (Backlog)`), that lender skips Steps 1–3 entirely — jump straight to Step 4 with the existing Epic key instead of re-extracting.

**Don't trust a stale read.** The sheet changes; if this conversation already has a cached row list from earlier, re-open the sheet rather than reusing it — Status especially moves as tickets get filed.

Echo what was resolved before continuing, tab included:
```
Target: Nations Direct Mortgage  (tab: Non-QM not integrated, row 4, "#3" in team's-list order)
  Team's list?  YES
  Type          Non-QM
  Programs      DSCR, Bank Statement, 1099, Full Doc, Asset Qual/Depletion
  Status        No ticket
```

---

## STEP 1 — Recon (3 parallel agents)

Send all three in **one message, one batch** of Agent tool calls (they're independent and read-only — no reason to serialize them). Each returns a short structured finding, not a wall of text.

**1a — Verify lender** (prompt sketch):
> Check whether "<Lender>" is ready to build a parser for. Run `cd $MOSO_REPO_ROOT/packs/loan && ./lender-info.sh "<Lender>"` — report whether a parser already exists. Separately `grep -in "<Lender fragments>" $MOSO_REPO_ROOT/packs/quote/src/main/java/com/mvu/quote/shared/typekey/LenderType.java` — report whether it's a registered LenderType constant, and if so the exact constant name. Also try fetching `https://www.loanfactory.com/our-lenders` and check whether "<Lender>" appears in the card list (that page lists Loan Factory's approved lenders — see [[reference_lf_our_lenders_public_approved_list]]). Report all three findings plainly, don't guess if a check is inconclusive — say so.

**1b — Fetch ratesheet** (prompt sketch):
> Get today's ratesheet for "<Lender>" if one exists. Try `cd $MOSO_REPO_ROOT/packs/loan && ./download-ratesheet.sh "<Lender>" --no-detect` first. If that fails, check `curl -I https://storage.googleapis.com/lender-rate-email/<LenderType>` (see [[ratesheet_email_gcs_object_last_routed]]) for whether mail has ever routed for this lender at all. Report the resolved local file path if you got one, or exactly what's missing (no account/credential yet vs. a download error vs. never been routed).

**1c — Fetch matrix + guideline** (prompt sketch):
> Find "<Lender>"'s Non-QM product guideline / eligibility matrix. WebSearch `<Lender> Non-QM product guideline matrix eligibility 2026`, prefer the lender's own domain, WebFetch the top hit. Report the URL and a one-line summary of what it contains (full guideline vs. matrix-only vs. nothing found), or say plainly if nothing turned up.

## STEP 2 — Synthesize + gate

Render one summary combining all three, e.g.:

```
RECON — Nations Direct Mortgage
  Registration:  NOT in LenderType.java yet — needs a developer (see new-parser's Scope note)
  Existing parser: none
  Approved list: found on loanfactory.com/our-lenders

  Ratesheet:     downloaded ✓  src/test/resources/ratesheets/NationsDirectMortgage_2026-09-11.xlsx
  Guideline:     found — https://www.nationsdirectmortgage.com/wholesale/nonqm-guidelines.pdf
```

If ratesheet or guideline is missing, stop and run the same "no ratesheet yet" branch `/parser-task-builder` Step 0 defines (ask email/download/request-upload) — don't proceed to Step 3 with a gap silently unfilled. If the lender isn't registered, surface it (as above) but this alone doesn't block Steps 3; it WILL block Step 4 later, say so now so it isn't a surprise mid-pipeline.

## STEP 3 — Extract + file the ticket

```
Skill("parser-task-builder", "<ratesheet path> <guideline path/url>")
```
Let it run its normal interactive flow (scope gate, matrix review, sub-task split, previews) — don't skip its confirmations just because this is an orchestrator. Capture `EPIC_KEY` and each `SUB_TASK_KEY` from its final report.

**If Step 0 found an existing Backlog Epic** (the `next`/`#N` fast-path), skip Step 3 entirely and use that Epic's existing sub-task keys.

## STEP 4 — Implement

For each in-scope sub-task (or the whole Epic if `/new-parser` accepts it directly):
```
Skill("new-parser", "<SUB_TASK_KEY>")
```
This ends at a local commit per lender's own Scope note — don't expect it to push or touch staging.

## STEP 5 — CHECKPOINT 1 (review before push)

```bash
git -C "$MOSO_REPO_ROOT/moso-pricing" diff --stat HEAD~<N>   # N = number of new-parser commits this run made
```
Show the diff stat and the final test results from Step 4. `AskUserQuestion`:
> "Implementation done for <Lender> — <N> sub-tasks, tests passing. Review the diff above. Push?"
> - "Yes — push now"
> - "Let me look first — show me the full diff"
> - "Hold — I'll push manually later"

Only Step 6 runs on the first option. This is a real gate, not a formality — per [[feedback_never_push_without_asking]], a broader "go ahead" earlier in the conversation does not cover this specific push.

## STEP 6 — Push

```bash
git -C "$MOSO_REPO_ROOT/moso-pricing" push
```
(and `packs`/`moso` if `/new-parser` touched them — check what actually changed, don't blind-push every repo).

## STEP 7 — CHECKPOINT 2 (staging deploy)

This skill has no deploy mechanism and doesn't go looking for one. Tell the user plainly and wait:
> "Pushed. Deploy staging whenever's convenient — let me know once it's live and I'll run test-task against it."

Do not proceed to Step 8 on a guess that enough time has passed. Wait for the user's explicit confirmation.

## STEP 8 — Verify on staging

```
Skill("test-task", "<EPIC_KEY or each SUB_TASK_KEY>")
```
Runs scenario-by-scenario against the now-deployed build, screenshots each, comments on Jira per [[feedback_test_report_scenario_with_screenshot]]. Leaves the ticket "In Progress" — never auto-Done, per [[feedback_jira_no_auto_done]].

---

## Final report

```
✓ Onboarded: Nations Direct Mortgage
  Epic:         MOSO-xxxxx  https://mosoteam.atlassian.net/browse/MOSO-xxxxx
  Sub-tasks:    5 filed, 5 implemented, 5 pushed
  Staging:      verified — screenshots attached, Jira commented, tickets left In Progress
  Still open:   LenderType.java registration (flag to a developer if not already in flight)

Next: /onboard-lender next   (picks up the next team's-list row with no ticket)
```

---

## Pitfalls to catch

1. **Don't delegate the sheet read to a subagent.** The Browser pane tools are only reliably available in the main loop — Step 0 happens here, not inside an Agent call.
2. **Don't skip a skill's own confirmations because this is "automated."** `/parser-task-builder`'s previews, `/new-parser`'s user-confirm step, `AskUserQuestion` prompts inside either — all still fire. This orchestrator adds two MORE checkpoints, it doesn't remove the ones already there.
3. **Never push on an earlier, broader approval.** Checkpoint 1 is its own ask every single run.
4. **Never invent a staging-deploy step.** If you don't know how this user deploys staging, don't guess a command — ask them to do it and wait.
5. **A `? new` vocabulary program (surfaced by `/parser-task-builder`'s scope gate) doesn't get silently dropped from the final report** — list it as blocked/excluded, same as any other open item.
6. **Recon findings are advisory, not a hard stop**, except missing ratesheet/guideline — an unregistered LenderType is worth flagging loudly (Step 2) but the ticket is still real groundwork, so don't refuse to continue over it; that mirrors `/parser-task-builder`'s own Step 1 behavior.
