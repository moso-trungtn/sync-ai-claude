---
name: check-lender-rate
description: Use when a loan officer reports moso's quoted price or LLPA/SRP adjustments don't match a lender's own rate/portal quote, or when asked to verify moso-pricing's parsed adjustments against a lender screenshot for a given loan scenario. Covers running MosoPricingTools#testDebug on staging, resolving lender/program ordinals, and root-causing mismatches (parser bug vs. stale ratesheet vs. bad loan data).
argument-hint: "[LenderName] — you'll also need to paste the loan Quote JSON and the lender's portal screenshot"
allowed-tools: Bash, Read, Edit, Write, Glob, Grep, Agent
---

# Check Lender Rate

## Overview
Reconciles moso-pricing's computed adjustment breakdown for one loan scenario against that lender's own rate/portal quote, then root-causes any gap: parser bug, stale local ratesheet, or bad loan input (e.g. wrong escrow flag) — never assume "parser bug" first.

## Steps

1. **Set up `testDebug()`** in `moso-pricing/src/test/java/com/ignored/mosopricing/MosoPricingTools.java`. Paste the given Quote JSON in as-is. Pick the Op:
   - No `non_qm_*` fields present → `new RunPricingOp().execute(parse)`
   - Has `non_qm_document_type` / `non_qm_dscr` / `prepayment_penalty` → `new RunNonQMPricingOp().execute(parse)`
   Add `System.out.println("RESULT=" + execute2);` if not already there.

2. **Decode ordinal-typed fields before trusting them.** `quote_lender`, `alert_lenders`, and `loan_program_group` are `EnumType` fields — a bare JSON number is the enum's **ordinal position** (`EnumType._fromJson`, `base/core/.../EnumType.java`), NOT the `id()` constant in the enum declaration. Count entries in `LenderType.java` / `ProgramFilterGroup.java` to resolve the real name (e.g. ordinal 106 = `NewRezCorrespondent`, a different lender than `NewRez` id=114). Never insert into these enums mid-list — ordinals are persisted everywhere.

3. **Run it**: `cd moso-pricing && mvn test -Dtest=MosoPricingTools#testDebug -q`. Keep whatever `NS.set(...)` is already in the file unless told otherwise — it's a tenant namespace, unrelated to the quote's lender/branch. Pull the `adjustment_detail` rows from `RESULT=`.

4. **Read the lender's screenshot/text** and line up each item against `adjustment_detail`. Before flagging a mismatch, check whether the lender splits ONE of moso's combined table values into two display lines (e.g. an "LLMA"/"WHL" line + an "SRP"/"MSR" line) — **sum them and compare to moso's single line**. This reconciled every category except one in past runs; only a real sum-level gap is a real issue.

5. **For any real gap, verify against today's ratesheet before touching code:**
   ```bash
   cd packs/loan
   ./download-ratesheet.sh <Lender> --no-detect        # pulls today's file from GCS, git-adds it
   mvn test -Dtest=RatesheetDumpTest#dumpFile -Ddump.file=src/test/resources/ratesheets/<new file> \
     -Ddump.out=/tmp/<lender>_dump -Djunit.jupiter.conditions.deactivate='*'
   grep -rn "<row/column keyword>" /tmp/<lender>_dump/**/*.csv
   ```
   Compare the raw cell to moso's `Tables.java` field for that row/column bucket.

6. **Classify the gap:**
   - Raw ratesheet cell ≠ moso's value → real parser bug. Draft the `Tables.java`/parser fix, **show it and wait for confirmation before editing** — never auto-edit pricing code.
   - Raw ratesheet cell = moso's value, but doesn't match the lender's screenshot → not a code bug. Check the loan's actual field values (escrow/impounds, FICO, LTV, occupancy) against what was really used for the quote — one flag being wrong (e.g. `impounds`) commonly explains the whole delta.
   - The lender's line item has no matching keyword anywhere in the dumped ratesheet (grep the whole workbook, all sheets) → the data isn't in what moso ingests at all (e.g. a separate SRP schedule). Report as a known gap, not a fixable bug.

## Common mistakes
- Treating `quote_lender:106` as `LenderType.id()==106` — it's ordinal, not id.
- Calling `RunNonQMPricingOp` on a QM quote — it force-sets `loan_type=Non_QM` and throws on missing `NON_QM_REQUIRED_FIELDS`.
- Concluding "parser bug" from a local test fixture without re-downloading today's ratesheet — fixtures can be a week+ stale.
- Missing the LLMA+SRP sum trick and flagging a false mismatch that's actually just a portal display split.
