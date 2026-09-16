---
name: parser-task-builder
description: One skill covering the full pre-implementation pipeline for a lender parser — classify + extract a ratesheet/matrix/guideline (the old extract-ratesheet job, now built in and callable standalone), cross-check detected programs against what Moso already models, surface conflicts and "new program type" blockers, then build OR update the Jira Epic + sub-tasks. CREATE mode (default): auto-reads ratesheet + matrix screenshots + guideline PDF, renders a scannable extraction report, gates each program in/out of v1 scope, then asks only for what's not in any file (provider account ID, email sender/subject, sub-task split) before filing native-ADF tickets (/trung-jira Mode 1 style — panel breadcrumb, Specification tables, full typed 14-field matrix, Acceptance Criteria, auto-assigned to Trung) with a QA test-case checklist comment on every sub-task. EXTRACT-ONLY mode: run just the read/classify/extract/report step and stop — no Jira writes — for when you only need the report. UPDATE mode (argument is an existing MOSO-<key>): re-extracts from new files, diffs section-by-section against the live ticket, detects and protects manual edits, updates body + attachments case-by-case. For Correspondent creates a single Task. Inlines screenshots as real embedded images via a 2-pass ADF create-then-edit flow.
argument-hint: [ratesheet path or folder | --extract-only <path> | MOSO-<key> to update existing]
allowed-tools: Bash, Read, Write, Glob, Grep, AskUserQuestion, WebSearch, WebFetch, mcp__d4873f66-6c13-4695-be2b-dbd414d76d1d__createJiraIssue, mcp__d4873f66-6c13-4695-be2b-dbd414d76d1d__getJiraIssue, mcp__d4873f66-6c13-4695-be2b-dbd414d76d1d__editJiraIssue, mcp__d4873f66-6c13-4695-be2b-dbd414d76d1d__addCommentToJiraIssue
---

# /parser-task-builder — Ratesheet/Guideline → Extraction Report → Jira Epic + Complete Sub-tasks

> **House rule — docs and working files.** Per-task working files (specs, plans, test cases/results, screenshots, review notes) go ONLY to `/Users/trungthach/IdeaProjects/docs/changes/<KEY>/` (workspace, outside git) — never inside moso, moso-pricing, packs, base or moso-configuration, and never as `docs/changes/`, `docs/superpowers/` or `MOSO-xxxxx/` folders in a repo. Lender parser knowledge lives in `moso-pricing/docs/lenders/<slug>/` (`README.md` reference, `history.md` dated changes, `nonqm.md` Non-QM); after any parser change update that folder in the same commit. Contract: `moso-pricing/docs/lenders/README.md`.

You are the **one skill** that takes a lender's raw files (ratesheet, matrix screenshots, guideline PDF) all the way to a Jira Epic + sub-tasks that `/new-parser` can consume end-to-end. There is no separate "extract-ratesheet" skill anymore — reading and extracting is Step 1.5 of this pipeline, and you can stop right after that step (`--extract-only`) when the user just wants the report.

> **History note:** this file used to exist as two different, disagreeing skills — a self-contained markdown-body version and a "consumes another skill's payload" ADF-body version — plus a separately-invoked `extract-ratesheet` skill that one of them depended on and the other didn't. They produced tickets in two different Jira title/body conventions (compare `MOSO-16495` "[Parse Non-QM] Community Wholesale Lending" vs `MOSO-17041` "[Parser > theLender] Set up parser & get rate sheet" — both real production tickets, from two different skill versions). This file merges them into one pipeline: extraction is now always the same code path whether you stop after it (`--extract-only`) or continue straight into ticket filing.

## The core principle (read this carefully)

A ratesheet alone is **not enough** for `/new-parser` to build a parser. It needs two stacked layers:

1. **Rates + Adjustments** — products, lock periods, modes, LLPA tables. Mostly on the ratesheet.
2. **Eligibility matrix + Validations** — min FICO, max LTV, DTI, occupancy, property type, citizenship, cash reserves, prepayment penalty, interest-only rules, etc. **These are almost never on the ratesheet** — they live in the lender's product guideline PDF, a matrix screenshot, or the lender's portal. Two flavors, and the ticket must say which one applies to every field:
   - **System validations** = Moso's shipped defaults across the 14 fields below. Jira shorthand: the literal bullet `Use system validations`.
   - **Program validations** = an override for this specific program (e.g. "Primary residence only", "Min loan $125k", "Max LTV 80% / Min FICO 680 Purchase").

Your job is to combine ratesheet content + matrix/guideline content into one structured sub-task, typing out anything you can't inline as a screenshot. **Never leave a sub-task body with empty program headers, an empty matrix row, or "TODO: fill in matrix"** — that breaks `/new-parser`.

---

## Hard rules

1. **ADF as a native JSON object, never stringified.** Pass `description: { "version": 1, "type": "doc", "content": [...] }` to `createJiraIssue` — not a JSON string. Stringified ADF renders as raw JSON text in Jira.
2. **English in Jira, bilingual in chat.** Translate any Vietnamese inputs to natural English before building the payload.
3. **Auto-assign Trung** on every `createJiraIssue` call: `assignee_account_id: "712020:c86c8eaf-7415-4e7d-8afe-59fd529b6fac"`.
4. **User/QA perspective in the body.** A QA engineer who has never seen the source code should understand the task. No `<Lender>Tables.java`, no `RangeTableInfo`, no `ValidateCalculator`. Use plain English: "FANNIE MAE eligibility matrix", "LLPA adjustment", "system validations".
5. **`panel[info]` is breadcrumb-only.** One short line, e.g. `"Parser > AmWest Funding > Conventional and Government"`. Never put Background, Environment, or notes inside it.
6. **Read first, ask second.** Step 1.5 auto-extracts from every file before any matrix question is asked. Never ask the user for a value that's already visible in one of their files.
7. **Classify before extracting.** A guideline PDF and a ratesheet need different read strategies — see Step 1.5.
8. **Cross-check vocabulary, don't invent program names.** `moso-docs/PARSER_PRIMER.md` is canonical. A program Moso doesn't model yet is a blocker, not a typo to paper over — see Step 1.7.
9. **Surface conflicts and low-confidence fields. Never silently resolve or silently drop them.**
10. **Sub-task body must be complete.** Rates described or attached, adjustments described or attached, the full 14-field matrix TYPED OUT (not just a one-line summary — a QA engineer and `/new-parser` both need the complete table). Empty matrix = bug.
11. **One question at a time.** Never batch. Never show a wall of fields. `AskUserQuestion` per field, pre-filled from extraction where possible.
12. **Never auto-chain into `/new-parser`.** Print URLs and stop — the user controls that step.
13. **Existing-parser AND lender-registration checks are mandatory** (Step 1) — run every time, before anything else.

---

## Workflows

| Workflow | Output |
|---|---|
| **Extract-only** | A scannable extraction report — no Jira writes |
| **QM new parser** | 1 Epic + N sub-tasks (one per program group: Conv+Gov, Jumbo, …) |
| **Non-QM new parser** | 1 Epic + N sub-tasks (one per program: Full Doc, Alt Doc, DSCR, No Ratio, …) |
| **Correspondent** | 1 Task (no Epic, no sub-tasks) |
| **Update** (arg = `MOSO-<key>`) | Same ticket, refreshed body/attachments, manual edits protected |

Real reference tickets (mixed conventions from before this merge — new tickets should all look like the QM/Non-QM row above, not the `[Parser > ...]` variant):
- **QM**: [MOSO-12073](https://mosoteam.atlassian.net/browse/MOSO-12073) → [MOSO-12075](https://mosoteam.atlassian.net/browse/MOSO-12075) (Conv+Gov), [MOSO-12076](https://mosoteam.atlassian.net/browse/MOSO-12076) (Jumbo)
- **Non-QM**: [MOSO-16495](https://mosoteam.atlassian.net/browse/MOSO-16495) (Community Wholesale Lending Epic) → [MOSO-16496](https://mosoteam.atlassian.net/browse/MOSO-16496)/[16497](https://mosoteam.atlassian.net/browse/MOSO-16497)/[16498](https://mosoteam.atlassian.net/browse/MOSO-16498)
- **Correspondent**: [MOSO-14984](https://mosoteam.atlassian.net/browse/MOSO-14984)

---

## Environment & Constants

```
CLOUD_ID          = "mosoteam.atlassian.net"
PROJECT_KEY       = "MOSO"
JIRA_BASE         = "https://mosoteam.atlassian.net"
TRUNG_ACCOUNT_ID  = "712020:c86c8eaf-7415-4e7d-8afe-59fd529b6fac"

MOSO_REPO_ROOT    = "${MOSO_REPO_ROOT:-$HOME/IdeaProjects}"
PACKS_LOAN_DIR    = "$MOSO_REPO_ROOT/packs/loan"
DOCS_DIR          = "$MOSO_REPO_ROOT/moso-docs"
PARSER_PRIMER     = "$DOCS_DIR/PARSER_PRIMER.md"
LENDER_TYPE_JAVA  = "$MOSO_REPO_ROOT/packs/quote/src/main/java/com/mvu/quote/shared/typekey/LenderType.java"
LENDERS_DOCS      = "$MOSO_REPO_ROOT/moso-pricing/docs/lenders"
# one folder per lender: $LENDERS_DOCS/<slug>/README.md (+ history.md, nonqm.md); index: $LENDERS_DOCS/README.md
```

---

## Mode detection (STEP 0)

Check the argument first:

- Starts with `--extract-only` → **EXTRACT-ONLY MODE**. Run Steps 1–1.9 only, then stop. No Jira writes ever happen in this mode.
- Matches `MOSO-\d+` (e.g. `MOSO-12075`) → **UPDATE MODE**. Jump to "UPDATE MODE pipeline" near the bottom.
- Otherwise (a path, a folder, or empty) → **CREATE MODE** (default). Runs the full pipeline through ticket creation, with an offer to stop after the report if the user prefers (Step 1.9).

**If the user just wants a quick read** ("just extract this", "what's in this ratesheet", "đọc ratesheet này thôi") without typing a flag, treat it the same as `--extract-only` — don't force them to know the flag exists.

### Resolving input files

The user can hand you files in any of these ways, checked in this order:

1. **Attached to the current chat (drag-and-drop / file upload).** Cowork lands uploads at `$HOME/Library/Application Support/Claude/local-agent-mode-sessions/<session-id>/<thread-id>/local_*/uploads/<filename>`. Collect **every** recent `*.pdf|*.xlsx|*.xlsm|*.xls` from that directory (mtime within the last ~30 min), not just the newest.
2. **A single file path argument** — single-input mode.
3. **A folder argument** — walk `*.pdf|*.xlsx|*.xlsm|*.xls` at the top level; subfolders are per-program screenshot folders (see Folder aliases at the bottom), don't treat them as more ratesheet/guideline inputs.
4. **A comma-separated path list** — split, validate each file exists.
5. **Nothing found** — this is the **no-ratesheet-yet** case, not an error. Ask which of these applies:

   ```
   I don't see a ratesheet/guideline yet. Which is it?

     a) It's in an email — paste the email text or forward it, and I'll pull
        the attachment path once you save it locally
     b) It should be downloadable — tell me the lender name and I'll check
        packs/loan/download-ratesheet.sh and the ratesheet-watch GCS bucket
     c) Neither — request it: I'll draft a short ask (to the lender AE, or
        via the "Upload Ratesheet" button on their Loan Factory Lender
        Management record if they're already a registered lender) for you
        to send, then come back here once you have the file
     d) I have it, wrong path — let me re-point you
   ```

   For (b), try `cd "$PACKS_LOAN_DIR" && ./download-ratesheet.sh "<Lender>" --no-detect` (pass `--no-detect`; the built-in date detector is flaky — confirm the effective date yourself from the sheet). For (c), this skill does not send the request itself (no email-send tool in its allowed-tools) — hand the user a short draft message and stop; re-invoke once the file exists locally. **Do not silently proceed as if a file exists — this is a hard stop, not a soft warning.**

Build `INPUTS[]`, each entry shaped `{path, filename, size_bytes, ext, kind: null, meta: {}, programs_in_file: [], tables_classified: [], product_codes: []}`. `SCREENSHOT_ROOT` = the parent folder if a folder was given, else `null`.

**Echo what you resolved** before doing any work:
```
✓ Reading 3 files:
    1. amwest_ratesheet_0521.xlsx          (1.2 MB, modified 5 min ago)
    2. amwest_conforming_guideline.pdf     (945 KB, modified 5 min ago)
    3. amwest_jumbo_guideline.pdf          (612 KB, modified 5 min ago)
  Source: drag-and-drop upload
```

**CREATE MODE opening checklist** (only shown once files are resolved or in the same breath as asking for them) — the 3 file inputs above plus 5 info fields you'll ask for one at a time once extraction is done:

```
Have these ready (files now, info as I ask for it):

FILES:
  1. Ratesheet         (PDF / XLSX / XLSM / XLS — rate grid + LLPAs)
  2. Matrix             (screenshots in matrix/, OR a guideline.pdf)
  3. Guideline PDF       (fallback for matrix if matrix/ is missing)

INFO (I'll ask once I've read what's in the files):
  4. Portal URL          e.g. https://corr.lendername.com/login
  5. Lender ID            10-11 digit provider account ID
  6. Lender full name     as on the email/portal
  7. Email sender         name + address from the ratesheet email
  8. Email subject
```

---

## STEP 1 — Identify lender + registration check

Extract a candidate lender name from filenames (strip dates and common suffixes: `Ratesheet`, `Wholesale`, `Correspondent`, `NonQM`, `Guideline`, `Matrix`, `Conforming`, `Conventional`, `FHA`, `VA`, `Jumbo`), corroborate against the first ~500 chars of each file's text. Vote across files if there are several.

**Two separate checks — both required, they answer different questions:**

```bash
cd "$PACKS_LOAN_DIR" && ./lender-info.sh "<CandidateName>" 2>&1 | head -20
```
Tells you whether a **parser already exists** (test methods, parser class, Tables class). `true` → likely a refresh or Correspondent variant, not a brand-new build; surface loudly and suggest `/fix-parser` or `check-lender-rate` mode `gap` instead. `false`/empty → no parser yet, continue. `ambiguous` → print candidates, ask.

```bash
grep -n "<CandidateName pattern>" "$LENDER_TYPE_JAVA" | head -5
```
Tells you whether the lender is **registered as a `LenderType` enum constant** — a completely different, earlier gate than "has a parser". If it's not found:

```
"<Lender>" isn't in LenderType.java yet. Two things need to happen before a
parser can go live for a brand-new lender, and only the first is something
I (or a BA) can do without a developer:

  1. Basic lender record — the "Lenders" admin screen (LendersView, needs
     EDIT_LENDER permission) — name, portal login, AE contact, etc. No code
     change. If this doesn't exist yet, create it there first.

  2. LenderType.java registration — a developer must append a new enum
     constant to the BOTTOM of LenderType.java (packs/quote/.../typekey/
     LenderType.java). Never insert mid-list — ordinals are persisted in
     the DB, and inserting out of order previously misrouted a live lender
     in production (MOSO-16335: NewRez resolved as AmWest). Until this
     lands and packs/quote + packs/loan are rebuilt/deployed, the
     Adjustments/Rate buttons and has-rate toggles on the Lenders record
     stay disabled — /new-parser cannot finish even with a perfect ticket.

I'll keep building the ticket either way (extraction and filing don't need
the enum entry), but flag this to a developer now if it isn't already
in flight. Continue?
```

This is a warning + confirm, not a hard block — the ticket is still useful groundwork — but never skip surfacing it.

---

## STEP 1.5 — Auto-read + classify + extract (the old `/extract-ratesheet` pipeline, now built in)

**This is the core of the skill.** Read every file BEFORE asking any matrix question — the goal is to never ask the user for a value that's already visible in one of their files. Run reads in parallel where possible.

### 1.5.a — Per-file inspection

For each `INPUTS[i]`:

**PDF:**
```bash
python3 - <<'PY'
import pdfplumber, os, json
p = os.environ["FILE_PATH"]
out = {"pages": 0, "tables_per_page": [], "total_tables": 0, "text_sample": "", "image_only": False}
with pdfplumber.open(p) as pdf:
    out["pages"] = len(pdf.pages)
    pages_text = []
    for i, page in enumerate(pdf.pages):
        tbls = page.find_tables()
        out["tables_per_page"].append({"page": i+1, "tables": len(tbls)})
        out["total_tables"] += len(tbls)
        if i < 6:
            pages_text.append(page.extract_text() or "")
    out["text_sample"] = "\n\n--- PAGE BREAK ---\n\n".join(pages_text)[:16000]
    if not out["text_sample"].strip():
        out["image_only"] = True
print(json.dumps(out))
PY
```
**⚠ Sampling limit — say this out loud in the report, don't bury it:** `text_sample` only covers the **first 6 pages, capped at 16,000 characters**. A longer guideline can have programs or validation rows past that window that this pass will never see. If `pages > 6` or a program you expected doesn't show up, re-read pages beyond 6 explicitly with the `Read` tool before concluding it's absent. If `image_only`, stop using this file for extraction and tell the user to run `ocrmypdf` first — don't pretend to extract from a scanned image.

**Excel:**
```bash
python3 - <<'PY'
import os, json
from openpyxl import load_workbook
p = os.environ["FILE_PATH"]
wb = load_workbook(p, data_only=True, read_only=True)
out = {"sheets": [], "text_sample": ""}
chunks = []
for name in wb.sheetnames:
    ws = wb[name]
    out["sheets"].append({"name": name, "rows": ws.max_row, "cols": ws.max_column})
    for row in ws.iter_rows(min_row=1, max_row=min(40, ws.max_row), values_only=True):
        chunks.append(" | ".join(str(c) for c in row if c is not None))
out["text_sample"] = "\n".join(chunks)[:16000]
print(json.dumps(out))
PY
```
Same caveat: **first 40 rows per sheet, capped at 16,000 characters.** For a longer sheet, re-read specific row ranges past row 40 before assuming a program is absent. Legacy `.xls` → `pandas.read_excel(..., sheet_name=None)` with `xlrd`.

### 1.5.b — Classify each file (`kind`)

Score against four kinds using filename + text-keyword + structural signals:

| Kind | Filename hints | Text hints | Structural |
|---|---|---|---|
| `ratesheet` | ratesheet, rate_sheet, wholesale, correspondent, pricing | Note Rate, 15/30/45/60-day, Lock Period, Base Price, Discount, Premium | many tables, short prose |
| `guideline` | guideline, matrix, overlays, program, underwriting, uw | Eligible Properties, Loan Terms, Reserves, Maximum LTV, Min FICO, Owner Occupied | lots of prose, few tables, ≥1 eligibility-shaped table |
| `matrix_only` | — | — | ≥80% page area is tables, almost no prose, ≥1 FICO×LTV grid |
| `mixed` | — | both rate-grid AND prose-guideline signals in one file | — |

No signal scores >1 → `kind = unknown`, warn. **The same lender often sends `ratesheet.xlsx` + `<program>_guideline.pdf` separately — don't assume one file covers everything.**

### 1.5.c — Scan for program names

Regex bank (case-insensitive, 40-char negation window checked — drop a hit if the preceding text matches `\bnot\b|\bexcept\b|\bexclud`):

```
FANNIE MAE, FREDDIE MAC, "Adjustment of FNMA && FHLMC", "ALT AGENCY (Second Home/Investment)",
HomeReady, HomePossible, "High Balance", FHA, VA, USDA, "FHA Streamline", "VA IRRRL",
Jumbo, "Jumbo Pro", "Jumbo Elite", "Jumbo Preferred",
DSCR, "Bank Statement", 1099, ITIN, "Asset Depletion", "Non-Agency Jumbo",
"Investor Cash Flow", "Foreign National", "P&L"
```

Dedupe across files into `PROGRAMS_DETECTED[]`, each with `sources[]` and hit locations.

### 1.5.d — Per-table classifier + eligibility-matrix extraction

For each detected table, tag: `eligibility` (row labels mention Purchase/R&T/Cash-Out/occupancy/property; cells have LTV% + FICO together), `rate-grid` (15/30/45-day columns, many numeric rows), `llpa` (header says LLPA/Adjustment/Overlays; signed-number cells), `product-codes` (rows like `FCF30`/`CA5/6`), `max-loan-amount` (unit counts + dollar amounts), or `other`.

For each `eligibility` table, extract into the **14-field schema** (this is the schema the sub-task body's matrix table uses verbatim — don't let it drift):

```
citizenship, occupancy, loan_term, document_type, min_loan_amount, max_loan_amount,
property_type, min_fico, max_dti, dscr_ranges, cash_reserved, mortgage_lates,
prepayment_penalty, interest_only
```

Leave a field `null` when not present in the table — 1.5.e tries prose next, then the user finishes it in Step 5.3's review.

### 1.5.e — Program-validation extraction (system vs override) + conflict detection

Scan guideline prose for validation phrases scoped to the active program heading: min/max loan amount, eligible/ineligible property, max LTV/CLTV, max DTI, reserves months, lock period, citizenship, Foreign National eligibility, manufactured-housing eligibility, etc. Each match → `{field, note, source_page}`. Fields with no override found render in the ticket as the literal bullet `Use system validations`.

**Conflict detection — never silently pick one.** If the same field has different values in two source files (ratesheet says Min FICO 680, guideline says 660), record BOTH and carry them into `conflicts[]` for the Epic/sub-task body's "Conflicts to resolve before lock" section.

### 1.5.f — Sub-product / product-code mapping

Parse any `product-codes` table into a best-guess Moso `getProduct(...)` tuple (e.g. `FCF30 → getProduct(Conforming, fixed(30), Conventional, lockPeriod(30))`). Flag unmappable/lender-specific codes as `? new product code` and Fast-Track/Buydown/Lender-Paid-style codes as needing an explicit mode.

### 1.5.g — Matrix screenshots, portal, web fallback (fills remaining `null` fields)

Run in this order, stopping as soon as a field is filled:

1. **`matrix/*.png` screenshots** — `Read` each image, extract visible values, tag `matrix_source = "matrix/"`, flag cropped/unclear text in `matrix_warnings`.
2. **`guideline.pdf`** (if `matrix/` missing/incomplete) — same 14-field extraction as 1.5.d, tag `"guideline.pdf"`.
3. **Portal URL** (once the user gives it in Step 3) — always store it for the Epic body regardless; `WebFetch` it only if it isn't behind a login wall, tag `"portal"` if it surfaces matrix info.
4. **Web search** — `WebSearch` for `<Lender> <Program> product guideline matrix eligibility 2026` (prefer the lender's own domain), `WebFetch` the top hit, tag `"web"`.

If still empty after all four passes: **eligibility table not found anywhere.** Say so plainly — `"No structured eligibility table found; matrix extraction skipped for <program> — attach matrix screenshots or provide a guideline URL before this program can be filed."` Don't fabricate values.

### 1.5.h — Rate grid + adjustment screenshots (structure, not every cell)

For `rate-sheet/*.png` and `adjustment/*.png`, skim each to confirm what it contains and map filename → section — don't deep-parse cell values, the inlined screenshot speaks for itself once attached. Separately, write a **short prose description** of rate-grid structure (products, lock periods, rate range, Conforming/High-Balance/Jumbo splits) and adjustment-table shape (name, type, row/col labels) per program — this becomes the Background paragraph and Rate-sheet section text, not just "(see attachment)".

### 1.5.i — Cross-check against Moso's vocabulary

```bash
grep -A 5 "Loan program:" "$PARSER_PRIMER" | head -20
```
For each detected program AND sub-product, classify:

| Status | Meaning |
|---|---|
| `✓ supported` | In Moso's vocabulary and at least one existing parser handles it (check `$LENDERS_DOCS/*/README.md`) |
| `~ partial` | In vocabulary but rarely parsed, no clear precedent |
| `? new` | Not in vocabulary — needs a code change (new program type / mode) before it can be modeled |

**This is the check that would have caught Community Wholesale Lending's `MOSO-16499` (2nd-lien, blocked on a missing `SECOND_LIEN` program type) before a sub-task was ever filed for it.** `? new` programs get a note: `"v1 recommendation: file a separate code-task to add the program type/mode before this can be a parser sub-task."`

### Report what you read

```
[1.5/9] Auto-read complete:
        Lender:           Logan Finance Rates. Inc.  (from ratesheet header)
        Programs:         DSCR, DSCR Elite, Full Doc 12mo, Full Doc 24mo, Bank Statement
        Lock period:      30 days  (from ratesheet)
        Matrix source:    guideline.pdf  (matrix/ folder missing — fell back)
        Matrix extracted: 13 of 14 fields populated
        Warnings:         "Mortgage lates" field was cropped in the source — re-confirm
        Vocabulary check: 4 ✓ supported, 1 ~ partial, 0 ? new
```

---

## STEP 1.6 — Render the extraction REPORT

One scannable block, same shape every time — this is the deliverable of extract-only mode:

```
─────────────────────────────────────────────────────────────
📄 RATESHEET / GUIDELINE REPORT — <Lender Candidate>
─────────────────────────────────────────────────────────────
  Inputs (3 files):
    1. amwest_ratesheet_0521.xlsx          → ratesheet   (4 sheets, 1.2 MB)
    2. amwest_conforming_guideline.pdf     → guideline   (9 pages, 945 KB — sampled first 6)
    3. amwest_jumbo_guideline.pdf          → guideline   (6 pages, 612 KB)

  Lender (detected):   AmWest Funding
  Registered?          LenderType.java: NO — needs a developer (see Step 1)
  Existing parser?     No — looks like a new lender
  Detected type:       QM (confidence: high)

🏛 PROGRAMS DETECTED (deduped across inputs)
  ✓ FANNIE MAE      supported   sources: amwest_conforming_guideline.pdf, amwest_ratesheet.xlsx
  ✓ FHA             supported   sources: amwest_ratesheet.xlsx
  ~ Jumbo Pro       partial     sources: amwest_jumbo_guideline.pdf
  ? Jumbo Elite     NEW — not in Moso vocabulary; needs a code change first

📋 ELIGIBILITY MATRIX (extracted — review before handoff, 13/14 fields for FANNIE MAE)
  ... (full 14-field table, same shape as Step 5.3's preview)

📜 VALIDATIONS (system vs override)
  FANNIE MAE: Min loan amount = $50,000 (override, p.2); Use system validations for the rest.
  ⚠ Conflict — FANNIE MAE min FICO: 620 in ratesheet vs 640 in guideline. Unresolved.

📐 ADJUSTMENTS / LLPA
  12 LLPA tables detected across ratesheet pp.4-7 and conforming guideline pp.5-7.
─────────────────────────────────────────────────────────────
```

---

## STEP 1.7 — Scope gate (in v1?)

For each program in `PROGRAMS_DETECTED[]`, one `AskUserQuestion`:

```
question: "Parse <PROGRAM> in v1?"
options:
  - "Yes — include in this parser ticket"
  - "Skip — not in v1, no ticket"
  - "Block on code-task — file a MOSO code-task to add the program type first"
```

Default the suggested answer from the vocabulary check: `✓ supported` → Yes; `~ partial` → ask without a strong default; `? new` → Block on code-task. Store `SCOPE_DECISION[program]`. Only `"in"` programs feed Step 1.8's split and Step 3–5's ticket filing. If everything ends up skip/block, stop — there's nothing to file for v1, say so.

## STEP 1.8 — Recommend a sub-task split (in-scope programs only)

| Split | Programs |
|---|---|
| "Conv + Gov" | FANNIE MAE, FREDDIE MAC, FHA, VA, USDA, FHA Streamline, VA IRRRL |
| "Jumbo" | Jumbo, Jumbo Pro, Jumbo Elite, Jumbo Preferred, Non-Agency Jumbo |
| Non-QM (by income proof) | DSCR / Bank Statement / 1099 / ITIN / Asset Depletion — usually one sub-task each |

Render the recommendation (including anything excluded for being blocked) and note it's editable in Step 4.

## STEP 1.9 — EXTRACT-ONLY exit / handoff decision

Always ask this, even in CREATE mode — it's the standalone-extraction path the user may want:

```
question: "What next?"
options:
  - "File Jira tickets now with this extraction"        (→ continue to Step 2)
  - "Let me edit the sub-task split first, then file"    (→ Step 4 first, then continue)
  - "Just save the report — I'll file later"             (→ save to
     ~/IdeaProjects/skills-updates/extract-ratesheet-runs/<lender-slug>-<YYYYMMDD>.md, print path, stop)
  - "This lender already exists — I picked the wrong flow" (→ point at check-lender-rate or /fix-parser, stop)
```

If invoked with `--extract-only`, skip this question — always behave as "just save the report" and stop. Never write to Jira from extract-only mode under any circumstance.

---

## STEP 2 — Confirm type (QM / Non-QM / Correspondent)

Already scored during 1.5.b/1.5.c from filename + content signals. Confirm with the user via `AskUserQuestion`, all three options shown. **If Correspondent → jump to Step 7.**

## STEP 3 — Create the Epic (ADF)

### 3.1 — Gather Epic-level fields, one at a time

Pre-filled from Step 1.5 where possible:
- Lender full name (pre-fill from candidate)
- Provider account ID (10–11 digits; validate length and numeric; if the lender isn't registered yet per Step 1, allow `TBD` here — don't block ticket creation on an ID that lender management hasn't assigned)
- Email sender name
- Email sender address (must contain `@`)
- Email subject
- Portal URL (validate starts with `http`; allow `TBD` if none exists yet)

### 3.2 — Title

```
[Parse QM] <Lender Name>          (or [Parse Non-QM] <Lender Name>)
```

### 3.3 — Body (ADF)

```
doc
  panel[info]     "Parser > <Lender Full Name>"
  paragraph       "Background: New <QM|Non-QM> parser kick-off for <Lender>. Rate sheet
                   attached. This Epic is the umbrella; per-program parser work happens
                   in the child sub-tasks."
  heading[3]      "Specification — Lender identification"
  table (5 cols)  # | Field name | Format | Value | Description
                  1 | Lender name | Text | <Lender Full Name> | Full legal name from email
                  2 | Provider account ID | Number | <id or TBD> | From the provider system
                  3 | Email sender | Email | <addr> (<name>) | Where the ratesheet came from
                  4 | Email subject | Text | <subject> | For traceability
                  5 | Rate sheet | Attachment | <filename> | Attached to this Epic
  heading[3]      "Acceptance Criteria"
  bulletList      - Lender is registered in LenderType.java and the Lenders admin screen.
                  - All sub-tasks (one per program group) are filed under this Epic.
                  - Rate sheet attachment is preserved on the Epic for audit.
```

Use the ADF node helpers at the bottom. Preview (rendered as readable pseudo-markdown) → confirm `[Y/edit/cancel]` → create:

```
tool: createJiraIssue
cloudId: mosoteam.atlassian.net, projectKey: MOSO, issueTypeName: "Epic"
summary: "<title>", description: <ADF doc object>, assignee_account_id: TRUNG_ACCOUNT_ID
```

Capture `EPIC_KEY`/`EPIC_URL`. Upload the ratesheet:
```bash
if [ -n "$JIRA_EMAIL" ] && [ -n "$JIRA_API_TOKEN" ]; then
  curl -s -u "$JIRA_EMAIL:$JIRA_API_TOKEN" -H "X-Atlassian-Token: no-check" \
    -F "file=@$RATESHEET_PATH" "$JIRA_BASE/rest/api/3/issue/$EPIC_KEY/attachments"
else
  echo "WARN: JIRA_EMAIL/JIRA_API_TOKEN not set — attach manually at $EPIC_URL"
fi
```

## STEP 4 — Confirm the sub-task split

Show Step 1.8's recommendation for confirmation (`[Y / edit count / edit titles]`), or ask fresh if extract-only was skipped. Auto-derive titles: `[<QM|Non-QM>] <Lender Name> - Parse <group> program(s)`.

## STEP 5 — Per sub-task: build the complete body

For each sub-task:

### 5.1 — Pick the template
QM → per-program sections. Non-QM → 3 sections (Rate sheet / Adjustment / Matrix && Validation) + always-typed matrix.

### 5.2a — [QM] Per-program walk
For each selected program (multi-select from the common list: FANNIE MAE, FREDDIE MAC, "Adjustment of FNMA and FHLMC", ALT AGENCY Second Home/Investment, FHA, VA & USDA, FHA Streamline & VA IRRRL — note: write "and" not a literal `&&` in anything user-facing, that's a formatting leftover from an earlier version, not a real ampersand-ampersand):
- **Validation bullets** — default `Use system validations`; allow override, pre-filled from Step 1.5.e.
- **Optional sub-sections** (multi-select): High Balance, Adjustment, Matrix, Lender paid.
- **Type a matrix table for this program? Y/n** — default `n` for agency programs (FANNIE MAE, FREDDIE MAC, USDA-within-VA&USDA, FHA Streamline & VA IRRRL: *"Fannie Mae/Freddie Mac already have built-in eligibility checks in our system, so a typed matrix usually isn't needed here — type one anyway?"* — say this rationale in the prompt itself, not just in this skill's internal notes), default `y` for non-agency/overlay programs (ALT AGENCY, Jumbo variants, custom FHA overlays). If `y`, run the Matrix review (5.3) for this program.
- Once for the sub-task: lock-period note at top (e.g. "Use rate of 30 days").

### 5.2b — [Non-QM] 3-section walk
Single primary program per sub-task. **Rate sheet section**: lock period, program variants (e.g. DSCR/DSCR Elite), lender credit caps (as a 2-col table if conditional). **Adjustment section**: note screenshots will attach; optional value-mapping table (e.g. ratesheet DSCR bands → system DSCR bands). **Matrix && Validation section**: → Step 5.3.

### 5.3 — Matrix review (pre-filled from Step 1.5 → user reviews → confirm)

This is REVIEW, not interview — most of the work already happened in Step 1.5. Show the full 14-field markdown table with low-confidence fields flagged `⚠️`:

```
| **Citizenship** | US Citizen / Permanent Resident Alien / Non-Permanent Resident Alien / Foreign National |
| **Occupancy** | Primary / Second Home / Investment |
| **Loan term** | 30yr fixed / 30yr fixed IO / 40yr fixed / 40yr fixed IO (use 30yr rate sheet) / 5/6 ARM |
| **Document type** | Full doc 12 months / Full doc 24 months |
| **Min-Max loan amount** | Min: $125K  Max: $3M |
| **Property type** | SFR / TH/PUD / Duplex/Triplex/Fourplex / Warrantable Condos / Non-Warrantable Condos / 2-4 Unit (Max LTV = 80%) |
| **Min FICO** | 660 (exclude Foreign National) |
| **DTI** | Max DTI = 50% |
| **DSCR** | (only for DSCR programs) |
| **Cash Reserved** | ≤$1M → 3mo / $1-2M → 6mo / >$2M → 9mo / FN: 12mo |
| **Mortgage lates** | ⚠️ No mortgage 1x30x12 (low-confidence — guideline image was cropped) |
| **Prepayment Penalty Term** | No PPP / 12/24/36 months PP (Investment only) |
| **Interest Only** | If IO = Yes: Purchase FICO≥740 LTV≤80% / Refi LTV≤75% |

a) Accept all and proceed
b) Edit a row — tell me which
c) Re-extract from a different source — paste a URL, point at another file, or say "walk-through"
```

(b) → ask row label, show current, ask new value, re-render, loop. (c) → sub-options: walk through each field manually (legacy 14-question fallback below), paste matrix text, fetch a different URL (`WebFetch`), read a different local file. If matrix is completely empty after Step 1.5, skip straight to (c)'s manual walk-through and say so loudly. **For QM agency programs where the user said `n` to "type a matrix?", skip this step entirely** — just the `Use system validations` bullet.

**Legacy fallback — walk-through fields one at a time** (only when auto-extract found nothing, or the user explicitly chooses it): ask each of the 14 fields via one `AskUserQuestion` each, with a real-sample format hint and a skip option, same field list/order as the 14-field schema in Step 1.5.d. This is the mode of last resort — it existed as the *only* mode before Step 1.5 existed; keep it working, but it should rarely trigger now.

### 5.4 — Render the sub-task body (ADF) and confirm

Build the ADF doc:

```
doc
  panel[info]     "Parser > <Lender> > <split-title>"
  paragraph       "Background: <1-2 sentences, English, naming in-scope programs and any
                   global lock-period note — derived from Step 1.5.h's structure description>"
  (only if conflicts[] non-empty for this sub-task's programs:)
  heading[3]      "Conflicts to resolve before lock"
  bulletList      - "<program> <field> is <value A> in the rate sheet but <value B> in the
                      guideline. Confirm the correct value before locking the parser."
  heading[3]      "Specification — Programs in scope"      (QM: one row per program in this
  table (5 cols)   # | Program | Sub-products | Eligibility summary | Validations           sub-task; Non-QM: usually one row, the sub-task's single program)
  heading[3]      "Specification — Adjustments / LLPA"     (if this sub-task owns adjustments)
  table (3 cols)   # | Adjustment matrix | Source
  heading[3]      "Matrix && Validation — <program>"        (repeat per program that has one —
  table (2 cols)   <full 14-field table from 5.3, typed out in full, not summarized>          THIS is what makes the body complete enough for /new-parser; the 5-col
                                                                                                Specification table above is the scannable summary, this is the source of truth)
  panel[note]      "<<<SCREENSHOT:section:filename.png>>>"   (one per screenshot — see 5.5 for
                                                                real inlining, not a permanent text placeholder)
  heading[3]      "Acceptance Criteria"
  bulletList      - All listed rate products quote correctly on viet18 staging.
                  - Every LLPA adjustment row triggers when its scenario is quoted.
                  - Quoting outside any eligibility matrix (e.g. LTV above the max) blocks
                    with the correct error.
                  - Per-program validations enforce as listed in the Specification.
                  - All conflicts above (if any) are resolved with a documented decision.
```

Render as readable pseudo-markdown, show attachment file list, `Send to Jira? [Y/edit/skip]`. On confirm:

```
tool: createJiraIssue
cloudId: mosoteam.atlassian.net, projectKey: MOSO, issueTypeName: "Task"
parent: <EPIC_KEY>, summary: "<sub-task title>", description: <ADF doc object with
<<<SCREENSHOT:...>>> tokens still as plain text — Pass 1 only>, assignee_account_id: TRUNG_ACCOUNT_ID
```

Capture `SUB_TASK_KEY`.

### 5.5 — Upload screenshots AND inline them as real images (2-pass)

Jira's create call doesn't have attachment IDs yet, so screenshots become real embedded images in two passes — this applies whether the placeholder sits inside a `panel[note]` or a table cell:

**Pass 1** (done above): body created with `<<<SCREENSHOT:section:filename.png>>>` tokens as plain text inside the ADF paragraph/panel content.

**Pass 2**: upload each file via curl to `$JIRA_BASE/rest/api/3/issue/$SUB_TASK_KEY/attachments`, capture `{id, filename, mimeType}` per upload, build `placeholder_map[token] → {id, filename}`. Walk the ADF doc and replace each placeholder text node with an ADF `mediaSingle`:

```json
{"type": "mediaSingle", "attrs": {"layout": "center"},
 "content": [{"type": "media", "attrs": {"type": "file", "id": "<attachment_id>", "collection": ""}}]}
```

Then:
```
tool: editJiraIssue
cloudId, issueIdOrKey: <SUB_TASK_KEY>
additional_fields: { "description": <ADF JSON with media nodes> }
contentFormat: "adf"
```

**Never leave `[INSERT IMAGE: ...]` as permanent literal text in a finished ticket** — that's a placeholder for Pass 1 only. If an upload fails for a specific file, replace that one token with `[Screenshot: filename.png — not inlined; see Attachments]` and log a warning; don't fail the whole ticket over one bad image. Files that don't map to any placeholder still get uploaded as plain attachments. The Epic's ratesheet attachment needs no placeholder — it's a plain attachment, not inlined.

### 5.6 — Add the QA test-case checklist as a comment

After the body is created and images inlined, post a comment with a checklist derived **only from what's actually in the sub-task body** — every program, adjustment table, and matrix field that appears becomes one checklist row. Same source of truth, different view for QA. Empty `☐` boxes; QA replaces with ✅/❌ as they verify.

**QM sub-task** (mirrors MOSO-12073):
```markdown
## QA Test Case Checklist
> Verify each parsed element matches the ratesheet. Replace ☐ with ✅ when verified, ❌ if mismatched.

### Fannie Mae — Loan Programs
| Loan Program | Check |
| --- | --- |
| FANNIE MAE 30 YEAR FIXED (101) | ☐ |
...

### Adjustment of FNMA and FHLMC
| Adjustment | Check |
| --- | --- |
| FICO/LTV Purchase Adjustments | ☐ |
...
```

**Non-QM sub-task**:
```markdown
## QA Test Case Checklist

### Rate sheet
| Item | Expected | Check |
| --- | --- | --- |
| Products parsed | 30yr Fixed, 30yr IO, ... | ☐ |
| Lock periods | 30 days | ☐ |

### Adjustment
| Adjustment table | Check |
| --- | --- |
| FICO/LTV Purchase | ☐ |

### Matrix && Validation
| Field | Expected | Check |
| --- | --- | --- |
| Citizenship | US Citizen / PRA / NPRA / FN | ☐ |
... (one row per 14-field matrix entry)
```

Post via:
```
tool: addCommentToJiraIssue
cloudId, issueIdOrKey: <SUB_TASK_KEY>, commentBody: <markdown>, contentFormat: "markdown"
```

**Rules**: never invent a checklist row not in the body (re-generate if the body changes). Skip this step for the Epic — only sub-tasks (and standalone Correspondent Tasks) get it.

## STEP 6 — reserved for flow clarity

## STEP 7 — Correspondent (single Task, ADF)

Ask 6 fields one at a time (pre-fill from extraction where possible): lender full name, Correspondent provider account ID, Correspondent label (e.g. "Loan Factory Direct - Newrez - CL1"), Wholesale parser cross-ref (auto-suggest from `lender-info.sh`), programs to parse (comma list), source ticket ID (optional).

Title: `[QM] <Lender Name> - Parse Correspondent's rates`. Body (ADF): breadcrumb, Background ("<Lender> uses the same rate sheet for Wholesale and Correspondent..."), 5-col Specification table, Acceptance Criteria. Preview → confirm → create (no `parent`) → attach ratesheet → run Step 5.6's QA checklist (Correspondent template: programs-to-parse table + cross-reference-verification table) on this Task.

## STEP 9 — Final report

```
✓ Created in Jira (auto-assigned to Trung):

  Epic:        MOSO-15234   https://mosoteam.atlassian.net/browse/MOSO-15234
                            [Parse Non-QM] Logan Finance

  Sub-task 1:  MOSO-15235   [Non-QM] Logan Finance - Parse Full Doc program   (14 attachments, ✓ QA checklist)
  Sub-task 2:  MOSO-15236   [Non-QM] Logan Finance - Parse Alt Doc program    (8 attachments, ✓ QA checklist)
  Sub-task 3:  MOSO-15237   [Non-QM] Logan Finance - Parse DSCR programs      (12 attachments, ✓ QA checklist)

Each sub-task has rates, adjustments, and a complete Matrix && Validation table ready
for /new-parser. If any conflicts were surfaced, they're listed in the body — resolve
before locking. If any program was Blocked-on-code-task, it has no sub-task — file that
separately first.

When ready:
  /new-parser MOSO-15234            (whole lender)
  /new-parser MOSO-15235            (one sub-task at a time)
```

Do NOT auto-invoke `/new-parser`.

---

## UPDATE MODE pipeline (argument is a Jira key)

```
U.0 Detect & confirm → U.1 Fetch existing → U.2 Collect new files & run Step 1.5 on them →
U.3 Section diff with manual-edit detection → U.4 Per-section accept/reject/edit →
U.5 Attachment management (case-by-case) → U.6 Build new ADF body → U.7 Upload new attachments →
U.8 Delete attachments marked for removal → U.9 editJiraIssue with ADF body → U.9.5 Refresh QA comment → U.10 Report
```

### U.0 — Detect & confirm
```
Detected Jira key: MOSO-12075 → UPDATE MODE.
I'll fetch the existing ticket, ask for the new files, detect any sections you've
manually edited in Jira and ask before overwriting them, and handle attachments
case-by-case (keep/replace/delete). Proceed? [Y/cancel]
```

### U.1 — Fetch existing task
```
tool: getJiraIssue
cloudId, issueIdOrKey: <KEY>, fields: ["summary","description","issuetype","parent","attachment"]
responseContentFormat: "adf"
```
Parse `title`, `type`, `parent_key`, `body_adf`, a flattened `body_text` for diffing, `attachments[]`. Infer the template from the title (`[Parse QM/Non-QM] <Lender>` → Epic; `[QM/Non-QM] <Lender> - Parse ... program(s)` → sub-task; `[QM] <Lender> - Parse Correspondent's rates` → Correspondent).

### U.2 — Collect new inputs
Ask what changed: updated ratesheet / updated matrix / updated guideline PDF / updated portal-or-email metadata / several / just a typo. For each category, ask the same upfront-checklist fields as Create mode, then run **the full Step 1.5 pipeline** on the new files to get a fresh extraction.

### U.3 — Section diff + manual-edit detection
Compare current body section-by-section against the new extraction. Classify each section `unchanged` / `changed_auto` (safe to update) / `changed_manual` ⚠️ (current has content that doesn't match the original template skeleton or old extraction — likely a hand-added note; NEVER silently overwrite) / `removed` / `added`. Show the classification summary before touching anything.

### U.4 — Per-section review
`AskUserQuestion`: accept all `changed_auto` + ask per `changed_manual` (default) / accept all including manual / per-section walk / cancel. For each `changed_manual` section, always ask explicitly with options keep / replace / merge / show-me-first.

### U.5 — Attachment management (case-by-case)
List existing attachments with metadata; for each, ask keep / replace / delete / skip-review-treat-as-keep. List new unmatched files to upload.

### U.6 — Build the new body
Same ADF structure as Create mode. Skipped/rejected sections pass through from `EXISTING.body_adf` untouched. Merged sections combine auto value + manual note. Preserve original section order.

### U.7/U.8 — Upload new attachments, delete removed ones
Same curl patterns as Create mode Step 5.5, plus:
```bash
curl -s -u "$JIRA_EMAIL:$JIRA_API_TOKEN" -X DELETE "$JIRA_BASE/rest/api/3/attachment/<attachment_id>"
```

### U.9 — Update via editJiraIssue
Convert the new body to ADF (real media nodes, not text placeholders — same 2-pass rule as Create mode), `editJiraIssue` with `contentFormat: "adf"`. **Never change title, issue type, or parent** — update mode only touches description and attachments.

### U.9.5 — Refresh the QA checklist comment (only if the body actually changed)
Post a new comment regenerated from the updated body; don't delete the old one — leave it for history. Skip if changes were typo-only.

### U.10 — Final report
```
✓ Updated MOSO-12075
Sections updated: ✓ Rate sheet (Lock period + Rate range refreshed) ⊙ Cash Reserved (preserved your manual note)
Attachments: ✓ Replaced ratesheet → 2025-05-04 version; + Added matrix-cash-reserved-updated.png
If this is part of a re-parse cycle, run /new-parser MOSO-12075 to rebuild against the updated body.
```

---

## Pitfalls to Catch

0. **Don't ask what you can read.** Always run Step 1.5 before matrix questions.
0a. **Auto-extraction is fallible AND sample-capped.** Always show the extracted matrix as a preview. ⚠️-flag low-confidence fields, and separately flag anything past the 6-page/40-row sampling window as unverified, not just "not found".
0b. **UPDATE MODE never silently overwrites manual edits.** Flag `changed_manual`, always ask.
0c. **UPDATE MODE never changes title/type/parent.**
0d. **UPDATE MODE confirms attachment deletion explicitly** — irreversible.
0e. **QA checklist derives from the body, never invented.** No row without a matching body item.
0f. **No QA checklist on the Epic.**
1. **Empty matrix table.** Never ship a Matrix section with blank rows — run the fetch-from-URL flow or warn loudly and get explicit confirmation to proceed anyway.
2. **QM matrix gate defaults + say why in the prompt itself**, not buried in this doc — see 5.2a.
3. **Screenshot 2-pass ordering.** Create → upload → edit-with-real-media-nodes, in that order. `[INSERT IMAGE: ...]` must never be the final state of a shipped ticket.
4. **ADF media node `id` must match the upload response's `id` exactly.**
5. **Provider ID typos** — echo digits in preview; `TBD` is fine, a wrong number isn't.
6. **Sub-task missing `parent`.**
7. **QM vs Non-QM template mismatch** — don't mix.
8. **Title prefix.** `[Parse QM]`/`[Parse Non-QM]` for Epic; `[QM]`/`[Non-QM]` for sub-tasks; `[QM] ... - Parse Correspondent's rates` for Correspondent. Auto-derive, never ask.
9. **Issue type** — Epic for parent, Task for everything else.
10. **JIRA_EMAIL/JIRA_API_TOKEN missing** → tickets still create via MCP OAuth; attachments/inlining skip with a loud warning, don't crash.
11. **One question at a time.**
12. **Never auto-chain into `/new-parser`.**
13. **Registration gap (Step 1) must be surfaced, not silently passed through** — a ticket for an unregistered `LenderType` is real groundwork but `/new-parser` will stall on it later if nobody flags it now.
14. **`? new` program types (Step 1.7) never get a normal sub-task** — either "Block on code-task" (no sub-task, a separate code-task recommendation instead) or explicitly "Skip". Filing a sub-task for a program the engine structurally can't model yet just recreates the `MOSO-16499` situation.
15. **No ratesheet in hand is a real branch, not a stall** — Step 0's request-upload/download flow, don't just wait silently.
16. **Literal `&&` and stray spaces in program names are typos, not house style** — write "and", and don't leave a trailing space before a word (e.g. "ALT AGENCY Second Home/Investment", not "...Second Home/ Investment").

---

## Rules of Operation

1. Read first, ask second — Step 1.5 before any matrix question.
2. Sub-task body must be complete: rates, adjustments, and the FULL typed matrix.
3. QM and Non-QM bodies differ — per-program (gated) vs 3-section-always-typed.
4. Always show the extraction before submission — accept all / edit a row / re-extract.
5. One question at a time for what's not extractable.
6. Pre-fill from earlier answers and extraction.
7. Always confirm before sending — full preview, provider IDs echoed.
8. Sub-task `parent` mandatory — verify `EPIC_KEY` non-empty first.
9. Markdown/plain-text placeholders for Pass 1, ADF media nodes for Pass 2.
10. Attachments fail open — never crash on missing credentials.
11. Never auto-chain into `/new-parser`.
12. Always post the QA checklist after any sub-task/Correspondent Task — never on the Epic.
13. Both registration checks (lender-info.sh AND LenderType.java) run every time, in Step 1, before anything else.
14. `? new` vocabulary items never silently become a sub-task.
15. English in Jira, bilingual in chat. No codebase jargon in any body a QA engineer reads.
16. ADF as a native JSON object, never stringified.
17. Auto-assign Trung's accountId on every create.

---

## Folder aliases (screenshot pickup)

```
<lender>-jira/
├── ratesheet.pdf / .xlsx / .xlsm / .xls
├── guideline.pdf                 (optional — fallback matrix source)
├── rate-sheet/  adjustment/  matrix/     screenshots
└── <per-program subfolders>/     (QM: fannie-mae/, freddie-mac/, fha/, va/, usda/,
                                    fha-streamline-va-irrrl/, alt-agency/, jumbo*/ ;
                                    Non-QM: dscr/, bank-statement/, 1099/, itin/,
                                    asset-depletion/, non-agency-jumbo/, investor-cash-flow/)
```

Alias map: `fannie-mae|fnma|fannie`→FANNIE MAE; `freddie-mac|fhlmc|freddie`→FREDDIE MAC; `fnma-fhlmc-adjustment|agency-adjustment`→"Adjustment of FNMA and FHLMC"; `alt-agency*`→ALT AGENCY Second Home/Investment; `fha`,`va`,`usda`,`va-usda`→as named; `fha-streamline|va-irrrl|streamline-irrrl|fha-streamline-va-irrrl`→FHA Streamline & VA IRRRL; `jumbo*`→Jumbo family; `dscr`→DSCR; `bank-statement|bankstatement|bank-stmt`→Bank Statement; `1099|ten99`→1099; `itin`→ITIN; `asset-depletion|asset-dep`→Asset Depletion; `non-agency-jumbo|nonagency-jumbo|non-agency`→Non-Agency Jumbo; `investor-cash-flow|icf|investor-cf`→Investor Cash Flow.

Unknown folder → ask the user to point at the right one. Missing folder for a selected program → ask: skip / point elsewhere / continue with no attachments.

---

## Quick reference — ADF node helpers

**Paragraph:** `{"type":"paragraph","content":[{"type":"text","text":"Hello"}]}`
**Bold text:** `{"type":"text","text":"Bold part","marks":[{"type":"strong"}]}`
**Heading 3:** `{"type":"heading","attrs":{"level":3},"content":[{"type":"text","text":"Specification"}]}`
**Info panel (breadcrumb only):** `{"type":"panel","attrs":{"panelType":"info"},"content":[{"type":"paragraph","content":[{"type":"text","text":"Parser > AmWest Funding"}]}]}`
**Note panel (image placeholder, Pass 1 only — becomes a mediaSingle in Pass 2):** `{"type":"panel","attrs":{"panelType":"note"},"content":[{"type":"paragraph","content":[{"type":"text","text":"<<<SCREENSHOT:matrix:fannie-mae-eligibility.png>>>"}]}]}`
**Bullet list:** `{"type":"bulletList","content":[{"type":"listItem","content":[{"type":"paragraph","content":[{"type":"text","text":"..."}]}]}]}`
**Media (post-upload, Pass 2):** `{"type":"mediaSingle","attrs":{"layout":"center"},"content":[{"type":"media","attrs":{"type":"file","id":"<attachment_id>","collection":""}}]}`
**5-col spec table row:** `{"type":"tableRow","content":[{"type":"tableCell","attrs":{},"content":[{"type":"paragraph","content":[{"type":"text","text":"1"}]}]}, ...]}` (header row uses `tableHeader` instead of `tableCell`)
**Full table skeleton:** `{"type":"table","attrs":{"isNumberColumnEnabled":false,"layout":"default"},"content":[{"type":"tableRow","content":[<tableHeader cells>]},{"type":"tableRow","content":[<tableCell cells>]}]}`


## Shared document reuse (onboarding and later investigations)

Use the existing shared utility at
`/Users/trungthach/IdeaProjects/tools/.claude/skills/check-lender-rate/scripts/lender-guidelines.py`.
Do not create a lender-specific downloader. Start with the lender's Loan Factory
**LenderDocument** links/registry. Download matrices and guidelines once; the utility
reuses checksum-verified PDFs in `~/.cache/moso/lender-document-files/` on subsequent runs.
Original PDFs and manifests stay outside git.

```bash
python3 /Users/trungthach/IdeaProjects/tools/.claude/skills/check-lender-rate/scripts/lender-guidelines.py --lender STG --loan-type Jumbo --download /private/tmp/stg-docs
# For explicitly selected document IDs/Drive file links, including unclassified names:
python3 /Users/trungthach/IdeaProjects/tools/.claude/skills/check-lender-rate/scripts/lender-guidelines.py --ids-file /private/tmp/selected-document-ids.txt --all --download /private/tmp/lender-docs
```

The default downloads every matching matrix/guideline, not only the top three.
Use `--top N` only for an explicitly partial investigation. Filename classification
is a discovery aid: inspect the PDF title and product scope, especially lender-specific
Jumbo series. `--all` operates on selected IDs; it does not crawl a Drive folder.

Extract each product into `moso-pricing/docs/lenders/<slug>/README.md` under
`## Eligibility (guideline)`, or a linked product Markdown file. Include source ID/link,
SHA-256, PDF page, printed effective date, product coverage, exclusions and unresolved
conflicts. Raw text extraction is not a reviewed eligibility matrix. The generated
source manifest intentionally leaves `effective_date` unknown until the PDF is read.

For `/check-lender-rate`, read this product Markdown first, compare the actual parser
rules and scenario, and reopen the cached PDF only for missing/ambiguous evidence.
Cached documentation is not proof that the lender's current policy is unchanged:
check source freshness when a reported mismatch suggests a policy revision, when
requested, or when source coverage is missing. Use `--refresh` to retrieve a current
copy; prior PDF revisions remain available. Re-extract affected products and record
changes if the SHA changes. A cache hit does not make an old extraction current.

Ratesheets are separate: use the effective ratesheet for the reported scenario (or
verify today's sheet for a current-price investigation). Do not reuse an onboarding
ratesheet just because the guidelines are cached. This utility handles PDF matrices
and guidelines; it does not replace the existing ratesheet feed or authenticate to
private lender portals.
