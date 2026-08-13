---
name: ratesheet-change
description: Handle a detected ratesheet change report end-to-end — Jira task, parser implementation on a branch, QC test evidence. Invoked headless by ratesheet-watch pipeline.sh with a report path argument.
---

# Ratesheet Change Handler

Input: path to a change report (`reports/<date>/<key>.md`) produced by
`tools/ratesheet-watch/sweep.py`. The key is `<LenderEnum>__<variant>`.

## Steps — follow in order, stop and leave evidence on any failure

1. **Read the report.** Identify lender enum, variant, and each change
   (kind, detail). MANUAL_REVIEW/UNEXTRACTABLE-only reports: do step 2
   with a "manual review" summary, attach the report, then STOP.
2. **Create the Jira task** — use /trung-jira if available, else Atlassian
   MCP `createJiraIssue`. Project MOSO. Summary:
   `[Ratesheet change] <Lender>: <top change kind> <date>`. Description:
   the full report. Assign to the current user; leave status In Progress
   forever — NEVER transition further. Skip creation if an open task with
   the same summary prefix already exists for this lender (search JQL) —
   comment on it instead.
3. **Branch** in packs: `git -C /Users/trungthach/IdeaProjects/packs
   checkout -b MOSO-<key> origin/master` (fetch first).
4. **Baseline tests** (from `packs/loan`): run
   `./parser-fix.sh <Lender> --both` — record output as baseline.
5. **Download the new ratesheet** the standard way:
   `./download-ratesheet.sh <Lender> [--nonqm] --no-detect` (variant per
   the report key). Update inputStream refs in RateParserTest and
   AdjustmentParsersTest per packs/loan conventions.
6. **Implement** per change kind — PROMO_*: SPECIAL adjustment row in the
   lender's *Tables.java using real ConditionFactory conditions (NEVER a
   lazy ALL; PPP rows use prepaymentPenalty(...)+NOO; colName is always
   "LTV"). PROGRAM/STRUCTURE/LAYOUT: fix parser/Tables per
   moso-pricing/CLAUDE.md workflow. Rebuild moso-pricing first:
   `mvn install -DskipTests -Pjar-packaging -Dgwt.compiler.skip=true`.
7. **QC**: run BOTH RateParserTest and AdjustmentParsersTest for the
   lender. Up to 3 fix iterations. Still failing → comment failure output
   on the Jira task, add label `needs-human`, STOP (leave branch).
8. **Acknowledge**: fingerprint the JUST-COMMITTED resource file directly —
   NOT via `sweep.py --bootstrap`, which pulls from GCS and stamps a
   cache-style `source` name that never matches a committed ratesheet
   resource, leaving the packs `RatesheetFingerprintTest` guard skipped
   forever for that lender. After `download-ratesheet.sh` has placed the
   new sheet in `packs/loan/src/test/resources/ratesheets/`, run:
   ```
   /Users/trungthach/IdeaProjects/tools/ratesheet-watch/.venv/bin/python \
     /Users/trungthach/IdeaProjects/tools/ratesheet-watch/fingerprint.py \
     <that resource file> \
     -o /Users/trungthach/IdeaProjects/packs/loan/src/test/resources/fingerprints/<key>.json
   ```
   then git-add the fingerprint. This makes `source` a real resource name
   and activates the guard test for that lender.
9. **Commit** on the branch — ONE commit:
   `MOSO-<key>: <lender> ratesheet update — <short change summary>`.
   No Co-Authored-By. Do NOT push, do NOT merge.
10. **Evidence to Jira**: comment with before/after test summary, the
    diff stat, and the change report. Leave In Progress.

## Update lender docs
After any parser change, update `moso-pricing/docs/lenders/<lender>.md`
per moso-pricing/CLAUDE.md "Update Rules".
