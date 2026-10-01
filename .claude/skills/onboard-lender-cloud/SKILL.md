---
name: onboard-lender-cloud
description: Cloud variant of /onboard-lender for Claude Code Projects threads and cloud sessions (no local machine, no internal network, no Jira). Takes ONE new lender from its ratesheet + guideline to a draft PR — recon → extraction report + scope gate (parser-task-builder rules, extract-only) → implement parser + tests (new-parser rules, input = extraction report instead of a Jira ticket) → CHECKPOINT → push a feature branch + open a draft PR. Stops before staging; staging deploy and /test-task stay local with the original /onboard-lender. One thread = one lender, so several lenders can run in parallel. Trigger: "onboard <lender>" inside a Claude Code Project or cloud session, "/onboard-lender-cloud <qm|nonqm|corr> <lender>".
argument-hint: [qm|nonqm|corr] [lender full name] — tab is required, e.g. "nonqm Nations Direct Mortgage"
---

# /onboard-lender-cloud — ratesheet → extraction → parser → draft PR (cloud-safe)

This is the cloud-safe sibling of `/onboard-lender`. The local pipeline is unchanged and is still
the one to use on Trung's Mac. This file exists because the local chain cannot run in a cloud thread:

| Local `/onboard-lender` chain needs | Cloud thread reality | What this skill does instead |
|---|---|---|
| Browser pane + signed-in Google Sheet (Step 0) | no browser session | lender name comes from the user's message; read the sheet only via a Google Drive connector if one is attached |
| `download-ratesheet.sh`, internal hosts | no internal network | use files the user uploaded to the project; try public GCS only as a bonus |
| Jira Epic/sub-tasks (`parser-task-builder`, `new-parser`) | Jira is gone (team uses MOSO Tasks) | extraction report + PR description are the spec; no ticket writes |
| `/Users/trungthach/...` paths, `~/.claude/projects/.../memory` | repos are cloned somewhere else | resolve paths at runtime (Step E) |
| `agent-dashboard/emit.sh` | not present | skip every `emit_*` call silently |
| staging deploy + `/test-task` on viet18 | unreachable | out of scope — listed as manual steps in the PR |

The two sibling skills are used as **reference documents**, not invoked as-is:
- `claude-sync/skills/parser-task-builder/SKILL.md` — extraction rules (Steps 1–1.9, extract-only)
- `claude-sync/skills/new-parser/SKILL.md` — build rules (BA → Architect → Dev → QC → Verify → Finalize)
Read the relevant sections of both before Step 3. Wherever they conflict with this file, **this file wins**.

---

## STEP E — Resolve the environment (once per thread)

1. Find the clones. Look for directories containing `.git` named `moso`, `moso-pricing`, `packs`,
   `moso-docs`, and this repo (`sync-ai-claude`, the one holding `claude-sync/`). Typical check:
   `ls -d */ ../*/ 2>/dev/null` from the working directory, then `git -C <dir> remote -v`.
   Export them: `MOSO_REPO_ROOT` (parent dir that holds moso/packs/moso-pricing), `MOSO_PRICING`,
   `PACKS_LOAN=$MOSO_REPO_ROOT/packs/loan`, `TOOLS=<sync-ai-claude checkout>`.
2. Every `/Users/trungthach/IdeaProjects/<x>` in the reference skills means `$MOSO_REPO_ROOT/<x>`
   (or `$TOOLS` for `tools/...`).
3. Knowledge files: the build cookbook and pricing knowledge live in `$TOOLS/.claude/knowledge/`
   (`parser_build_cookbook.md`, plus any `parser_*` / `feedback_*` files). Read them from there.
   `~/.claude/projects/.../memory` does not exist in the cloud.
4. Scratch working files (specs, plans, extraction report) go to `/tmp/onboard/<lender-slug>/`.
   Never commit them, never create `docs/changes/` inside a repo.
5. Check the toolchain once: `java -version`, `mvn -v`. If Maven or a dependency cannot be resolved
   (private artifacts, no network), say so in the thread immediately — Step 4's tests depend on it.
   Do not try to work around it with fake test results.
6. If any required repo is missing from the project, stop and tell the user which one to attach.

## STEP 0 — Resolve the target

- Tab (`qm` / `nonqm` / `corr`) and lender name come from the user's message. If the tab is missing
  or ambiguous, ask — the three tabs produce structurally different work (see `/onboard-lender` Step 0).
- If a Google Drive / Sheets connector is attached, you MAY read the tracking sheet
  ("Lender-Integration-Status-AI-Version", id `1jMxc-keU4h-itos__Vk-0o3fsHUmn6bMp_dm5BYLO1M`) to fill
  Type / Programs / Status. Otherwise skip it and use what the user gave.
- `#N` / `next` selectors are NOT supported here (they need a fresh sheet read). Ask for a name.
- Echo the resolved target before continuing.

## STEP 1 — Recon (parallel, read-only)

Run these as independent subagents in one batch where the environment supports it, else sequentially:

- **1a Verify lender** — `cd $PACKS_LOAN && ./lender-info.sh "<Lender>"` (existing parser?), and
  `grep -in "<name fragments>" $MOSO_REPO_ROOT/packs/quote/src/main/java/com/mvu/quote/shared/typekey/LenderType.java`
  (registered? exact constant). Optionally WebFetch `https://www.loanfactory.com/our-lenders`.
- **1b Ratesheet** — first look in the project's uploaded files / library for this lender's ratesheet.
  Then, as a bonus only, `curl -sI https://storage.googleapis.com/lender-rate-email/<LenderType>`.
  Do NOT run `download-ratesheet.sh` (needs internal access / credentials).
- **1c Matrix + guideline** — uploaded files first; else WebSearch/WebFetch the lender's own
  product guideline / matrix (prefer the lender's domain).

## STEP 2 — Synthesize + gate

Render the same RECON block as `/onboard-lender` Step 2. Then:
- Ratesheet or guideline missing → STOP and ask the user to upload it to the project. Never guess.
- Not registered in `LenderType.java` → flag loudly. Extraction (Step 3) may continue; Step 4 may
  NOT add an enum constant on its own — ask first. If approved, append the new constant at the
  **bottom** of the enum only (ordinals are persisted; MOSO-16335).

## STEP 3 — Extract + scope gate

Follow `parser-task-builder` **EXTRACT-ONLY** mode (Steps 1–1.9) with these overrides:
- No Jira, no MOSO Tasks writes, no ADF. The output is a markdown extraction report at
  `/tmp/onboard/<slug>/extraction.md` and a summary posted in the thread.
- Scope gate is mandatory: one question per detected program (in v1 / out / `? new` program type).
  Wait for the answers. `? new` programs are listed as blocked, never silently dropped.
- Write the reviewed eligibility matrix into `moso-pricing/docs/lenders/<slug>/README.md` under
  `## Eligibility (guideline)` (copy `docs/lenders/_template/` for a new lender), with source link,
  page, effective date and unresolved conflicts — per the house rule in the reference skills.
- Correspondent (`corr`): usually piggybacks on an existing Wholesale parser — confirm with recon 1a.

## STEP 4 — Implement

Follow `new-parser` Steps 1–8 with these overrides:
- Input is `/tmp/onboard/<slug>/extraction.md` + the uploaded files, NOT a Jira key. Skip 0.2/0.3
  (Jira input / env check) and every `curl ... atlassian` call.
- Skip every `source .../emit.sh` and `emit_*` line.
- Subagents: use `parser-ba` / `parser-dev` / `parser-qc` if they are available; otherwise use a
  general-purpose subagent and paste the matching `$TOOLS/.claude/agents/parser-*.md` as its brief.
- Keep ALL pitfall rules (reuse the base API, anchor on landmark text via `section(...)`, no private
  `slice()`/`crawlX()`, field_N uniqueness, descending FICO, allTables()/calculators(), mode resolver).
- Tests: run `AdjustmentParsersTest#test<Lender>` and `RateParserTest#test<Lender>` together (both,
  always), accept expectations, copy the ratesheet into test resources + `RatesheetFiles.java` per
  new-parser 8.2–8.5. Report real output only.
- Learn step (8.1): do NOT edit the cookbook in this repo from the cloud. Put the finished cookbook
  entry in the PR description under "Cookbook entry" so Trung can paste it locally.
- Work on a feature branch per repo: `onboard/<lender-slug>`. Never commit to `master`/`main`.
- Commit messages: follow `$TOOLS/.claude/knowledge/feedback_commit_style.md`.

## STEP 5 — ⏸ CHECKPOINT (before any push)

Show `git diff --stat` per touched repo + the final test output. Ask in the thread:
"Implementation done for <Lender> — <N> programs, tests passing. Push branch and open draft PR?"
Only an explicit yes for THIS lender counts. A broader "go ahead" earlier, or approval given for a
different lender's thread, does not (`feedback_never_push_without_asking`).

## STEP 6 — Push + draft PR

Push `onboard/<lender-slug>` only for repos that actually changed, and open a **draft** PR per repo.
PR description must contain:
- Scope: programs in v1, programs excluded / blocked (`? new`) and why
- Rate tables parsed; adjustment tables parsed; tables deliberately skipped and why
- Test results (real output summary)
- `LenderType.java` status
- Cookbook entry (from Step 4)
- **Manual steps left for Trung (local):** review + merge order across repos; deploy staging;
  run `/test-task` (full five-axis sweep: adj, rate, cap, matrix, guideline) signed in on staging;
  update the tracking sheet / MOSO Tasks.

## STEP 7 — Report

```
✓ <Lender> (<tab>) — draft PR(s): <links>
  Programs:   <in v1> | excluded: <list> | blocked: <list>
  Tests:      AdjustmentParsersTest + RateParserTest PASS
  Open:       LenderType registration? / missing files? / anything unverified
  Next:       local — merge, deploy staging, /test-task
```

---

## Running several lenders at once (Projects)

- One thread = one lender = one branch name `onboard/<lender-slug>`. Never mix lenders.
- Shared files touched by every lender (`LenderType.java`, `RatesheetFiles.java`, test registries,
  lender lists) WILL conflict between parallel PRs. That's expected: keep each change minimal, rebase
  on the latest default branch right before Step 6, and mention the shared files in the PR so Trung
  can merge in order.
- A thread blocked on a question waits; it never borrows answers from another lender's thread.

## Never

- Never put credentials (staging, lender portals, Jira tokens) in files, commits, PRs or messages.
  Signing in anywhere is the user's step.
- Never invent ratesheet numbers, test results, or a staging/deploy step.
- Never push without the Step 5 yes. Never push to master/main.
- Never write to Jira.
