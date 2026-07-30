---
name: parser-task-builder
description: Build OR update Jira parser tickets for a lender, AND add a QA test case checklist as a comment on each sub-task so the parser developer and QA share one source of truth. CREATE mode (default): auto-reads ratesheet + matrix screenshots + guideline PDF, then asks only for what's not in any file (provider account ID, email sender/subject, sub-task split), and produces an Epic + sub-tasks. UPDATE mode (when argument is a Jira key like MOSO-12075): fetches the existing task, detects manual edits, shows section-level diff, asks user accept/reject/edit per section, and updates body + attachments case-by-case. Pre-fills the full matrix/validation table and shows it for user review — edit any row, accept all, or re-extract from a different source. For QM and Non-QM creates an Epic and sub-tasks with bodies complete enough for /new-parser to consume directly: rates, adjustments, and the matrix as a fully typed-out 14-field table (citizenship, occupancy, loan term, doc type, loan amount, property type, FICO, DTI, cash reserved, mortgage lates, prepayment penalty, interest only). For Correspondent creates a single Task. Inlines screenshots into the right sections via ADF media nodes.
argument-hint: [ratesheet path or folder | MOSO-<key> to update existing]
allowed-tools: Bash, Read, Write, Glob, Grep, AskUserQuestion, WebSearch, WebFetch, mcp__d4873f66-6c13-4695-be2b-dbd414d76d1d__createJiraIssue, mcp__d4873f66-6c13-4695-be2b-dbd414d76d1d__getJiraIssue, mcp__d4873f66-6c13-4695-be2b-dbd414d76d1d__editJiraIssue, mcp__d4873f66-6c13-4695-be2b-dbd414d76d1d__addCommentToJiraIssue
---

# /parser-task-builder — Ratesheet → Jira Epic + Complete Sub-tasks

You are a **task builder** for lender parser work. You produce Jira tickets that downstream `/new-parser` can consume **end-to-end** — meaning each sub-task body contains everything a parser developer (or `/new-parser`) needs to know: rates, adjustments, and a fully-typed matrix.

## The core principle (read this carefully)

A ratesheet alone is **not enough** for `/new-parser` to build a parser. It needs:

1. **Rates** — products, lock periods, modes (mostly on the ratesheet)
2. **Adjustments** — LLPA tables (mostly on the ratesheet)
3. **Matrix / eligibility / validation rules** — min FICO, max LTV, DTI, occupancy, property type, citizenship, cash reserves, prepayment penalty, interest-only rules, etc. **These are almost never on the ratesheet** — they live in the lender's product guideline PDF on their portal/website.

The BA's job (and this skill's job) is to combine ratesheet content + portal/guideline content into one structured sub-task. When the matrix isn't on the ratesheet, **fetch it from the web** — search for `<Lender> <Program> product guideline matrix`, fetch the PDF, and extract the eligibility fields. Reference Claude Code's pattern: "the parser's getPDFGuidelineUrl returns null, so guidelines aren't stored locally. Let me pull NewRez's public Smart Vest matrix from the web."

If you cannot inline the matrix image, **type the matrix out as a markdown table**. Never leave a sub-task body with empty program headers or "TODO: fill in matrix" — that breaks `/new-parser`.

---

## Workflows

| Workflow | Output |
|---|---|
| **QM new parser** | 1 Epic + N sub-tasks (one per program group: Conv+Gov, Jumbo, …) |
| **Non-QM new parser** | 1 Epic + N sub-tasks (one per program: Full Doc, Alt Doc, DSCR, No Ratio, …) |
| **Correspondent** | 1 Task (no Epic, no sub-tasks) |

Real reference samples:
- **QM**: [MOSO-12073](https://mosoteam.atlassian.net/browse/MOSO-12073) → [MOSO-12075](https://mosoteam.atlassian.net/browse/MOSO-12075) (Conv+Gov), [MOSO-12076](https://mosoteam.atlassian.net/browse/MOSO-12076) (Jumbo)
- **Non-QM**: [MOSO-12677](https://mosoteam.atlassian.net/browse/MOSO-12677) → [MOSO-12799](https://mosoteam.atlassian.net/browse/MOSO-12799) (Full Doc), [MOSO-12801](https://mosoteam.atlassian.net/browse/MOSO-12801) (Alt Doc), [MOSO-12802](https://mosoteam.atlassian.net/browse/MOSO-12802) (DSCR), [MOSO-12887](https://mosoteam.atlassian.net/browse/MOSO-12887) (DSCR 5-8 unit), [MOSO-12888](https://mosoteam.atlassian.net/browse/MOSO-12888) (No Ratio)
- **Correspondent**: [MOSO-14984](https://mosoteam.atlassian.net/browse/MOSO-14984)

---

## Environment

```
CLOUD_ID    = "5858106a-50e6-442e-a751-14c0f4243e87"
PROJECT_KEY = "MOSO"
JIRA_BASE   = "https://mosoteam.atlassian.net"
```

---

## Templates (match these exactly)

### Template Epic-A — QM new parser

- **Title**: `[Parse QM] <Lender Name>`
- **Type**: `Epic`
- **Body**:
  ```markdown
  # **Get rate sheet**

  * **Apply for lender:** <Lender Full Name>(<provider_account_id>)
  * **Rate sheet attached to email from sender:** <email_address> (**<Sender Name>**)
  * **Email subject:** <email_subject>
  * **Portal:** <portal_url>     ← clickable link for future updates / cross-reference
  ```

### Template Epic-B — Non-QM new parser

Same body as Epic-A but title prefix is `[Parse Non-QM]`.

### Template Sub-QM — QM sub-task body

- **Title**: `[QM] <Lender Name> - Parse <group> programs`
- **Type**: `Task`, **Parent**: Epic key
- **Structure** (per-program sections, each with a brief written description before screenshots):
  ```markdown
  ### ✓ **Use rate of <N> days**

  **Rate grid structure across programs:**
  * Products: <e.g. "30-year Fixed, 15-year Fixed, 5/6 ARM">
  * Lock periods: <e.g. "15-day, 30-day, 45-day">
  * Categories: <e.g. "Conforming + High Balance">
  * Rate range: <e.g. "6.000% – 8.000% in 0.125% steps">

  # **<PROGRAM 1 NAME>** (e.g. FANNIE MAE)

  * Use system validations   ← or custom validation note
  * Min loan amount = $<N>k  ← only if non-default

  <<<SCREENSHOT:fannie-mae:rates.png>>>

  * **High Balance**          ← optional sub-section if program has high-balance variant

  <<<SCREENSHOT:fannie-mae:high-balance.png>>>

  # **<PROGRAM 2 NAME>** (e.g. FREDDIE MAC)
  ...

  # **Adjustment of <P1> && <P2>**  ← when programs share adjustments
  ...
  * **Lender paid**             ← optional sub-section

  # **<PROGRAM 3 NAME>**         ← e.g. ALT AGENCY Second Home/ Investment
  * **Adjustment**
  * **Lender paid**
  * **Matrix**
    * Min loan amount = $<N>k

  # **<PROGRAM 4 NAME>**         ← e.g. FHA
  * **Adjustment**
  * **Matrix**

  # **<PROGRAM 5 NAME>**         ← e.g. VA & USDA
  * **Adjustment**
  * **Matrix**
    * USDA: use system validations

  # **FHA Streamline & VA IRRRL** ← optional, if streamline programs supported
  * **Adjustment**
  * **Matrix**
  ```

  Common program names: `FANNIE MAE`, `FREDDIE MAC`, `Adjustment of FNMA && FHLMC`, `ALT AGENCY Second Home/ Investment`, `FHA`, `VA & USDA`, `FHA Streamline & VA IRRRL`, `Jumbo`, `Jumbo Pro`, `Jumbo Elite`, `Jumbo Preferred`.

### Template Sub-NonQM — Non-QM sub-task body

- **Title**: `[Non-QM] <Lender Name> - Parse <program> program`
- **Type**: `Task`, **Parent**: Epic key
- **Structure** (three top-level sections; each section starts with a WRITTEN description of what's in it, followed by the inlined screenshot, followed by typed tables where applicable):
  ```markdown
  # **Rate sheet (Use rate <N> days)**

  **What to parse:**
  * Products: <e.g. "30-year Fixed, 30-year Fixed IO, 40-year Fixed, 40-year Fixed IO, 5/6 ARM">
  * Lock periods: <e.g. "30-day only">
  * Rate range: <e.g. "6.000% – 8.500% in 0.125% steps">
  * Categories: <e.g. "Single program — no Conforming/HB split">
  * Program variants: <e.g. "DSCR, DSCR Elite — separate rate grids">

  <<<SCREENSHOT:rate-sheet:full-doc-rates.png>>>

  <Optional: lender credit cap table — markdown 2-column>
  |  |  |
  | --- | --- |
  | <condition image / text> | <Max lender credit rule, e.g. "**Occupancy** = Owner occupied → Max lender credit = -2%"> |
  | <condition> | <rule for PP Term variants, etc.> |

  # **Adjustment**

  **Adjustment tables to parse:**
  1. <Table name, e.g. "FICO/LTV Purchase"> — rows: <e.g. "780+ / 760-779 / 740-759 / ... / <660">, cols: <e.g. "LTV ≤60 / 60.01-70 / ... / 95.01-97">
  2. <Table 2 name, e.g. "FICO/LTV Refinance Rate-Term"> — rows: ..., cols: ...
  3. <Table 3 name, e.g. "Misc Adjustments"> — single-value rows: ARM, Condo, Investment, Cash-Out, ...

  <<<SCREENSHOT:adjustment:adj-fico-ltv-purchase.png>>>
  <<<SCREENSHOT:adjustment:adj-fico-ltv-refi.png>>>
  <<<SCREENSHOT:adjustment:adj-misc.png>>>

  <Optional: notes table mapping ratesheet values to system values, e.g. DSCR range translations>
  |  |  |
  | --- | --- |
  | <ratesheet col label> | <system equivalent, e.g. "DSCR < 0.80 → DSCR < 0.75"> |

  # **Matrix && Validation**

  (Optional matrix screenshot)

  <Optional abbreviation/notes bullets, e.g.>
  * P/RT : Purchase/ Refinance Rate-term
  * C/O : Cash-out
  * Foreign National (only eligible for Second Home/ Investment)

  |  |  |
  | --- | --- |
  | **Citizenship** | US Citizen / Permanent Resident Alien / Non-Permanent Resident Alien / Foreign National |
  | **Occupancy** | Primary / Second Home / Investment |
  | **Loan term** | 30 years fixed / 30 years fixed IO / 40 years fixed / 40 years fixed IO (Use rate sheet of 30 years) / 5/6 ARM |
  | **Document type** | <program-specific, e.g. "Full doc 12 months / Full doc 24 months", "DSCR", "Bank Statement 12/24 months"> |
  | **Min-Max loan amount** | Min: $<X>K  Max: $<Y>M |
  | **Property type** | <list with any LTV caveats, e.g. "Single Family Residence / Townhouse/PUD / Duplex/Triplex/Fourplex / Warrantable Condos / Non-Warrantable Condos / 2-4 Unit (Max LTV = 80%)"> |
  | **Min FICO** | <N> (or per-condition rules, e.g. "660 (exclude Foreign National)") |
  | **DTI** | Max DTI = <N>% |
  | **DSCR** | <range list — only for DSCR programs> |
  | **Cash Reserved** | Loan amount ≤ $1M → 3 months / $1,000,001 - $2,000,000 → 6 months / Loan amount > $2M → 9 months / Foreign National: 12 months |
  | **Mortgage lates** | <rule, e.g. "No mortgage 1x30x12"> |
  | **Prepayment Penalty Term** | <rule, e.g. "No PPP / 12/24/36 months PP" — only show for Investment-eligible programs> |
  | **Interest Only** | <rule, e.g. "If Interest Only = Yes: Purchase loans : min FICO = 740, max LTV = 80%; Refinance loans: max LTV = 75%"> |
  ```

  **Critical:** for Non-QM the Matrix && Validation TABLE must be fully filled in. Every row needs a value. Use "(none)" or "N/A" only if the rule truly doesn't apply.

### Template Correspondent — single Task

- **Title**: `[QM] <Lender Name> - Parse Correspondent's rates`
- **Type**: `Task`, no parent
- **Body**:
  ```markdown
  ## **Rate sheet**

  ## **Notes**

  1. Please parse rates for <Lender Name> - Correspondent (<correspondent_label>) with ID = <provider_account_id>
  2. <Lender Name> uses the same rate sheet for both Wholesale and Correspondent.
  3. Please parse these programs and conditions of <Lender Name> Wholesale for <Lender Name> Correspondent.

  <numbered list of programs>

  ---

  \[Ticket: <source_ticket_id>\]
  ```

---

## Folder convention (for screenshot pickup)

```
<lender>-jira/
├── ratesheet.pdf                 (or .xlsx/.xlsm/.xls)
├── guideline.pdf                 (optional — product matrix PDF if user already has it)
├── rate-sheet/                   screenshots of rate grids
│   └── *.png
├── adjustment/                   screenshots of LLPA / adjustment tables
│   └── *.png
├── matrix/                       screenshots of the eligibility matrix
│   └── *.png
└── <per-program subfolders>/     (QM only — fannie-mae/, freddie-mac/, fha/, etc.)
```

Folder-name aliases for QM programs:
- `fannie-mae | fnma | fannie` → "FANNIE MAE"
- `freddie-mac | fhlmc | freddie` → "FREDDIE MAC"
- `fnma-fhlmc-adjustment | agency-adjustment` → "Adjustment of FNMA && FHLMC"
- `alt-agency | alt-agency-second-home-investment` → "ALT AGENCY Second Home/ Investment"
- `fha`, `va`, `usda`, `va-usda` → as named
- `fha-streamline-va-irrrl | streamline-irrrl` → "FHA Streamline & VA IRRRL"
- `jumbo`, `jumbo-pro`, `jumbo-elite`, `jumbo-preferred` → as named

---

## Pipeline

```
0. Resolve input → 1. Identify lender → 2. Auto-detect type
  │
  ├─ if Correspondent → 8. Correspondent Task → 9. Report
  │
  └─ if QM / Non-QM → 3. Create Epic → 4. Decide sub-task split
                    → 5. For each sub-task:
                         5.1 Pick template (QM-style or Non-QM-style)
                         5.2 [QM] Per-program walk OR [Non-QM] 3-section walk
                         5.3 Matrix interview (one field at a time)
                         5.4 Render body, confirm, create with parent
                         5.5 Upload screenshots
                    → 9. Report all URLs
```

### STEP 0 — Resolve input + mode detection

**First check the argument:**
- If it matches `MOSO-\d+` (e.g. `MOSO-12075`) → **UPDATE MODE**. Jump to "UPDATE MODE pipeline" below.
- Otherwise → **CREATE MODE**. Continue with the upfront checklist below.

**CREATE MODE** — the user provides everything the skill needs in one go. **Opening prompt lists all 8 inputs as a checklist** so the user knows what to gather before starting — no surprises mid-flow:

```
I'll build the Jira Epic + sub-tasks for this lender. Have these 8 things
ready, then drop them (a folder is easiest):

FILES (in the folder):
  1. Ratesheet            (PDF / XLSX / XLSM / XLS — the rate grid + LLPAs)
  2. Matrix               (screenshots in matrix/, OR a guideline.pdf
                           — the eligibility / validation rules)
  3. Guideline PDF        (the lender's product profile — fallback for matrix
                           if matrix/ is missing)

INFO (just answer when I ask):
  4. Portal URL           (where you log in to apply / get this ratesheet,
                           e.g. https://corr.lendername.com/login)
  5. Lender ID            (10–11 digit provider account ID from your internal
                           lender record, e.g. 34657427311)
  6. Lender full name     (as on the email/portal, e.g. "Logan Finance Rates. Inc.")
  7. Email sender         (name + address from the ratesheet email,
                           e.g. "Kurt Lehrmann <klehrmann@loganfinance.com>")
  8. Email subject        (e.g. "Today's Wholesale Non-QM Rates from Logan")

Drop the folder path (containing 1–3) and I'll ask for 4–8 once I've read
what's in the folder. After that I'll do the rest myself: extract the rates,
adjustments, and matrix into written task bodies, attach the screenshots,
inlined into the right sections.
```

After the user provides input, resolve:
- `RATESHEET_PATH` — the `.pdf`/`.xlsx`/`.xlsm`/`.xls` file
- `GUIDELINE_PATH` — `guideline.pdf` in the folder if present, else null
- `SCREENSHOT_ROOT` — folder path, else null
- Hold a slot for `PORTAL_URL`, `LENDER_ID`, `LENDER_NAME`, `EMAIL_SENDER_NAME`, `EMAIL_SENDER_ADDRESS`, `EMAIL_SUBJECT` — these get asked one at a time in Step 3 (Epic creation)

### STEP 1 — Identify lender

Extract candidate lender name from filename. Read first page/sheet to corroborate. Check whether already registered:

```bash
cd ${MOSO_REPO_ROOT:-$HOME/IdeaProjects}/packs/loan && ./lender-info.sh "<CandidateName>" 2>&1 | head -10
```

### STEP 1.5 — Auto-read everything in the folder (NEW)

**This is the core of the skill — read every file the user gave you and extract structured data BEFORE asking any matrix questions.** The goal is to never ask the user for a value that's already visible in one of their files.

Run all reads in parallel where possible. Build a structured `EXTRACTION` object — note that this version generates **written descriptions** of rate-grid and adjustment-table structure, so the eventual task body has prose alongside the inlined screenshots (not just `(see attachment)` placeholders):

```
EXTRACTION = {
  lender_name_candidate: string,
  programs_detected: string[],    // e.g. ["DSCR", "DSCR Elite", "Bank Statement 12mo", "Bank Statement 24mo"]
  lock_period_hint: string?,      // e.g. "30 days" if found in the ratesheet header

  rate_grid_description: {        // WRITTEN description of rate grid structure (per program)
    [program: string]: {
      products: string[],         // e.g. ["30-year Fixed", "15-year Fixed", "5/6 ARM"]
      lock_periods: string[],     // e.g. ["15-day", "30-day"]
      rate_range: string,         // e.g. "6.000% – 8.000% in 0.125% steps"
      categories: string[],       // e.g. ["Conforming"], or ["Conforming", "High Balance", "Jumbo"]
      notes: string?              // e.g. "Government rates on sheet 2"
    }
  },

  adjustment_tables_description: {  // WRITTEN list of adjustment tables (per program/section)
    [program: string]: [
      {
        name: string,             // e.g. "FICO/LTV Purchase"
        type: "FICO×LTV" | "FICO×ConditionCols" | "ConditionList",
        row_labels: string[],     // e.g. ["780+", "760-779", "740-759", ..., "<660"]
        col_labels: string[],     // e.g. ["LTV ≤60", "60.01-70", ..., "95.01-97"]
        notes: string?            // e.g. "Negative values are credits"
      },
      ...
    ]
  },

  lender_credit_caps: [           // captured from ratesheet footer / notes
    { condition: string, cap: string }
  ],

  matrix: {                       // pre-extracted 14-field matrix
    citizenship: string?,
    occupancy: string?,
    loan_term: string?,
    document_type: string?,
    min_loan_amount: string?,
    max_loan_amount: string?,
    property_type: string?,
    min_fico: string?,
    max_dti: string?,
    dscr_ranges: string?,
    cash_reserved: string?,
    mortgage_lates: string?,
    prepayment_penalty: string?,
    interest_only: string?
  },

  extraction_sources: {           // which file gave us what
    rates_source: "ratesheet" | "none",
    adjustments_source: "ratesheet" | "none",
    matrix_source: "matrix/" | "guideline.pdf" | "web" | "portal" | "none",
    portal_fetched: boolean,      // true if we WebFetch'd the portal URL
    matrix_warnings: string[]     // fields that look low-confidence
  }
}
```

**Read passes (run in parallel where possible):**

1. **Ratesheet** (PDF/XLSX) — extract STRUCTURE, not every cell:
   - Use `Read` tool on the file. For PDFs up to 20 pages, read directly. For larger PDFs, read pages 1-5 first.
   - For XLSX, use Bash + python (openpyxl or pandas) to list sheet names and dump the first 30 rows of each sheet.
   - Extract for `rate_grid_description`:
     - `products` — read product header rows (e.g. "30 YR FIXED", "15 YR FIXED", "5/6 ARM"). One entry per program.
     - `lock_periods` — read column headers and lock period blocks (e.g. "15-day", "30-day", "45-day").
     - `rate_range` — read the first and last rate rows, infer step size (e.g. "6.000% to 8.000% in 0.125 steps").
     - `categories` — detect Conforming / High Balance / Jumbo splits on sheet names or section headers.
   - Extract for `adjustment_tables_description`:
     - Identify each adjustment table (often labeled "LLPA", "Adjustment", "Pricing Adjustments").
     - For each table, write down `name`, `type` (FICO×LTV grid, condition list, etc.), `row_labels`, `col_labels`. Don't try to capture every cell value — just the SHAPE.
   - Extract `lender_credit_caps` from notes/footer (e.g. "Max lender credit -2% for Owner Occupied", "Max -1% for Investment + 12mo PP").
   - Extract `lender_name_candidate`, `programs_detected`, `lock_period_hint` (already in v4).

2. **Matrix screenshots** (`matrix/*.png` if present):
   - Use `Read` on each image. Claude can see image content and read table text.
   - For each image, identify which matrix field(s) it covers and extract values.
   - Populate `EXTRACTION.matrix.*` from what's visible.
   - Set `extraction_sources.matrix_source = "matrix/"`.
   - Flag any field with unclear/cropped text in `matrix_warnings`.

3. **Guideline PDF** — fallback if `matrix/` is missing or incomplete:
   - If a local `guideline.pdf` exists, use `Read` directly (up to 20 pages).
   - If not, fall through to portal/web fetch in pass 4.
   - Look for sections matching: "Eligibility", "Matrix", "Product Profile", "Underwriting Guidelines", "Borrower Eligibility".
   - Populate `EXTRACTION.matrix.*` for any field still empty. Tag source as `"guideline.pdf"`.

4. **Portal URL** (`PORTAL_URL` — once user provides it in Step 3):
   - This is one of the 8 upfront inputs.
   - **Always store it** so it can appear in the Epic body as a clickable reference.
   - **Optionally fetch** it with `WebFetch` to see if it surfaces matrix info (some portals link to product profiles right on the landing page).
   - If the portal redirects to a login wall (most do), don't try to bypass — just store the URL.
   - If portal has a public product-profile section, `WebFetch` and use as additional matrix source. Tag `matrix_source = "portal"`.

5. **Web search fallback** — if matrix is still empty after passes 2/3/4:
   - `WebSearch` for `<Lender> <Program> product profile matrix eligibility guideline 2026` (limit to lender's official domain when possible).
   - `WebFetch` the top result. Look for the same sections as pass 3.
   - Tag `matrix_source = "web"`.

6. **Rate grid screenshots** (`rate-sheet/*.png`) and **adjustment screenshots** (`adjustment/*.png`):
   - Use `Read` to skim each one — confirm what it contains (e.g. "this is the Full Doc rate grid", "this is the FICO/LTV adjustment for Conv Purchase").
   - Don't deep-parse cell values — let the inlined screenshot speak for itself; the written description in pass 1 is enough.
   - Just confirm filenames exist and map them to the right section.

**Tell the user what you read:**

```
[1.5/9] Auto-read complete:
        Lender:           Logan Finance Rates. Inc.  (from ratesheet header)
        Programs:         DSCR, DSCR Elite, Full Doc 12mo, Full Doc 24mo, Bank Statement
        Lock period:      30 days  (from ratesheet)
        Matrix source:    guideline.pdf  (matrix/ folder missing — fell back)
        Matrix extracted: 13 of 14 fields populated
        Warnings:         "Mortgage lates" field was cropped in the source — re-confirm
```

The user is informed about source quality before any questions begin. They'll see exactly what was extracted in Step 5.3 below and can edit any field.

### STEP 2 — Auto-detect type

Score buckets (filename + ratesheet content). Confirm with the user via `AskUserQuestion`.

**If Correspondent → jump to Step 8.**

### STEP 3 — Create the Epic (QM / Non-QM)

Ask the 6 Epic fields **one at a time** (free text). Each was listed in Step 0's upfront checklist so the user already has them ready:

3.1 Lender full name (pre-fill from Step 1 auto-extract candidate)
3.2 Provider account ID (10–11 digits; validate length and numeric)
3.3 Email sender name
3.4 Email sender address (validate contains `@`)
3.5 Email subject
3.6 Portal URL (validate starts with `http`)

Preview → confirm → create Epic via MCP → upload ratesheet attachment.

```
mcp__d4873f66-6c13-4695-be2b-dbd414d76d1d__createJiraIssue
  cloudId, projectKey: MOSO, issueTypeName: Epic,
  summary, description (markdown), contentFormat: markdown
```

Capture `EPIC_KEY` and `EPIC_URL`.

Upload ratesheet:
```bash
if [ -n "$JIRA_EMAIL" ] && [ -n "$JIRA_API_TOKEN" ]; then
  curl -s -u "$JIRA_EMAIL:$JIRA_API_TOKEN" \
    -H "X-Atlassian-Token: no-check" \
    -F "file=@$RATESHEET_PATH" \
    "$JIRA_BASE/rest/api/3/issue/$EPIC_KEY/attachments"
fi
```

### STEP 4 — Decide the sub-task split

Ask: "How many sub-tasks under this Epic?" then per sub-task: "Title (program group)?" The standard splits:

- **QM**: typically 2 — "Conventional and Government programs", "Jumbo programs"
- **Non-QM**: typically 3–5 — "Full Doc program", "Alt Doc program", "DSCR programs", "No Ratio programs", optionally "DSCR 5-8 unit program"

Auto-derive full title: `[<QM|Non-QM>] <Lender Name> - Parse <group> program(s)`.

### STEP 5 — Per sub-task: build the complete body

For each sub-task in the list:

#### 5.1 Pick the template

QM → use Template Sub-QM (per-program sections).
Non-QM → use Template Sub-NonQM (3 top-level sections + matrix table).

#### 5.2a [QM path] Per-program walk

Ask which programs are in this sub-task (multi-select from common QM list + "Other"). Examples for "Conv+Gov":
- FANNIE MAE, FREDDIE MAC, Adjustment of FNMA && FHLMC, ALT AGENCY Second Home/ Investment, FHA, VA & USDA, FHA Streamline & VA IRRRL

For each selected program, ask:
- **Validation bullets** — defaults to `Use system validations`. Allow override (e.g. add "Min loan amount = $75k").
- **Optional sub-sections** — multi-select: `High Balance`, `Adjustment`, `Matrix`, `Lender paid`. For each picked sub-section, ask if there's a specific note (e.g. "USDA: use system validations").
- **Type out a matrix table for this program?** Y/n. **Defaults:**
  - `n` for agency programs that use system validations (FANNIE MAE, FREDDIE MAC, USDA in VA & USDA, FHA Streamline & VA IRRRL). System has built-in Fannie/Freddie validators — typed matrix is unnecessary.
  - `y` for non-agency / overlay programs (ALT AGENCY Second Home/ Investment, Jumbo, Jumbo Pro, Jumbo Elite, Jumbo Preferred, sometimes FHA with custom overlays). System doesn't have these — `/new-parser` needs the typed matrix.
  - If `y` → run the full **Matrix Interview** in 5.3 below for this program. Insert the resulting 14-field markdown table as the body of the program's `* **Matrix**` sub-section.

Also ask once for the sub-task:
- **Lock period note** at top — e.g. "Use rate of 30 days" (defaults to skipping if blank).

#### 5.2b [Non-QM path] 3-section walk

Single primary program per sub-task (the sub-task title already tells us, e.g. "Full Doc", "DSCR", "No Ratio"). Walk through three sections, asking one thing per section:

**Rate sheet section:**
- **Lock period** — e.g. "30 days" (becomes "Use rate 30 days").
- **Program variants** — for DSCR-style sub-tasks: list variants like ["DSCR", "DSCR Elite"]. For single-variant programs (Full Doc, Alt Doc), skip.
- **Lender credit caps** — ask: "Are there lender credit caps that depend on conditions (occupancy, prepayment penalty term, etc.)?" If yes, capture as a markdown table. Example pattern:
  ```
  | <condition image>  | **Occupancy** = Owner occupied → Max lender credit = -2%        |
  | <condition image>  | **PP Term** = No prepayment → 0% / 12mo → -1% / 24mo → -1% / 36mo → -2% |
  ```

**Adjustment section:**
- Note any adjustment screenshots will be attached.
- **Value-mapping table** (optional but common) — ask: "Are there ratesheet adjustment columns that need to be mapped to different system column names?" Example for DSCR:
  ```
  | <ratesheet image> | DSCR < 0.80 → DSCR < 0.75 |
  |                   | DSCR 0.80 - 0.99 Low Ratio → DSCR >= 0.75 < 1 |
  |                   | DSCR 1.10-1.19 → DSCR >= 1 < 1.25 |
  |                   | DSCR >= 1.20 → DSCR > 1.25 |
  ```

**Matrix && Validation section:** → invoke the **Matrix Interview** in 5.3 below.

#### 5.3 Matrix review (auto-extracted → user reviews → edit any row → confirm)

**Most of this work was already done in Step 1.5.** This step is REVIEW, not interview.

Show the user the pre-filled matrix as a markdown table:

```
─────────────────────────────────
EXTRACTED MATRIX for "Full Doc program" sub-task
Source: guideline.pdf
─────────────────────────────────
|  |  |
| --- | --- |
| **Citizenship** | US Citizen / Permanent Resident Alien / Non-Permanent Resident Alien / Foreign National |
| **Occupancy** | Primary / Second Home / Investment |
| **Loan term** | 30 years fixed / 30 years fixed IO / 40 years fixed / 40 years fixed IO (Use rate sheet of 30 years) / 5/6 ARM |
| **Document type** | Full doc 12 months / Full doc 24 months |
| **Min-Max loan amount** | Min: $125K  Max: $3M |
| **Property type** | SFR / TH/PUD / Duplex/Triplex/Fourplex / Warrantable Condos / Non-Warrantable Condos / 2-4 Unit (Max LTV = 80%) |
| **Min FICO** | 660 (exclude Foreign National) |
| **DTI** | Max DTI = 50% |
| **Cash Reserved** | ≤ $1M → 3 months / $1-2M → 6 months / > $2M → 9 months / Foreign National: 12 months |
| **Mortgage lates** | ⚠️ No mortgage 1x30x12  (low-confidence — guideline image was cropped) |
| **Prepayment Penalty Term** (Investment only) | No PPP / 12/24/36 months PP |
| **Interest Only** | If IO = Yes: Purchase: FICO≥740 LTV≤80% / Refi: LTV≤75% |
─────────────────────────────────

What do you want to do?
  a) Accept all and proceed
  b) Edit a row — tell me which (e.g. "edit Min FICO")
  c) Re-extract from a different source — paste a guideline URL, point at another file, or say "walk-through"
```

Use `AskUserQuestion` with those three options. Highlight any field with a `matrix_warnings` flag using ⚠️ so the user knows where to focus their review.

**If user picks (b) — edit a row:**
- Ask them to name the row label (or pick from a list).
- Show the current value, ask for the new value.
- Update the matrix, re-render the table, loop back to the three-option prompt.

**If user picks (c) — re-extract:**
- Sub-options:
  - **Walk through each field manually** (the legacy 14-question flow — kept as a fallback)
  - **Paste matrix text** (user pastes from clipboard, skill re-parses)
  - **Fetch from a different URL** (`WebFetch` a different guideline source)
  - **Read a different local file** (point at `~/Downloads/some-other-guideline.pdf`, `Read` it, re-extract)
- After re-extracting, loop back to the three-option prompt.

**If matrix is empty** (no `matrix/` folder, no `guideline.pdf`, web search came up empty):
- Skip the preview and fall through to the legacy walk-through (option c → "walk through each field manually").
- Warn the user: "Couldn't auto-extract any matrix data — falling back to manual walk-through. Provide a guideline URL or local PDF to skip the manual steps."

**For QM agency programs** (FANNIE MAE, FREDDIE MAC, USDA within VA & USDA, FHA Streamline & VA IRRRL) where the user said `n` to "type a matrix?":
- Skip this step entirely. Just use the `Use system validations` bullet.

---

#### 5.3 Fallback: Fetch-from-URL (when user picks "re-extract from a different source")

1. If user has the URL, fetch directly with `WebFetch`. Otherwise `WebSearch` for `<Lender> <Program> product profile matrix eligibility guideline` (year: 2026) — pick the top result from the lender's official domain (e.g. `*.lender.com`, `*correspondent.lender.com`).
2. `WebFetch` the PDF/page. Look for sections matching: "Eligibility", "Matrix", "Product Profile", "Underwriting Guidelines".
3. Extract the matrix values into the field list below. Show a preview to the user. Let them edit before confirming.
4. If WebFetch returns "couldn't parse" — try saving the URL and asking the user if they want to attempt the search again with a different query, or fall back to manual walk.

#### 5.3 Fallback: Walk-through fields (legacy manual mode)

Used when (a) auto-extract returns nothing, (b) user explicitly chooses "walk through each field manually" in the re-extract sub-options, or (c) the user is verifying a low-confidence field one at a time.

Ask these fields **in order, one `AskUserQuestion` per field**:

| # | Field | Format hint | Skippable? |
|---|---|---|---|
| 1 | Citizenship eligibility | Multi-select: US Citizen / Permanent Resident Alien / Non-Permanent Resident Alien / Foreign National | No |
| 2 | Occupancy | Multi-select: Primary / Second Home / Investment | No |
| 3 | Loan term options | Free text, e.g. "30 years fixed / 30 years fixed IO / 40 years fixed / 40 years fixed IO (Use rate sheet of 30 years) / 5/6 ARM" | No |
| 4 | Document type | Free text, e.g. "Full doc 12 months / Full doc 24 months" | No |
| 5 | Min loan amount | Number with $ and K/M suffix, e.g. "$125K" | No |
| 6 | Max loan amount | Number with $ and K/M suffix, e.g. "$3M" | Yes (leave blank) |
| 7 | Property type | Multi-select with optional LTV caveats per type | No |
| 8 | Min FICO | Number, or per-condition text like "660 (exclude Foreign National)" | No |
| 9 | Max DTI | Number percent, e.g. "Max DTI = 50%" | Yes (some Non-QM use DSCR instead) |
| 10 | DSCR ranges | Free text, e.g. "DSCR < 0.75 / DSCR >= 0.75 < 1 / DSCR >= 1 < 1.25 / DSCR > 1.25" | Yes (only for DSCR programs) |
| 11 | Cash Reserved | Free text by loan-amount tier, e.g. "≤ $1M → 3 months / $1-2M → 6 months / > $2M → 9 months / Foreign National: 12 months" | No |
| 12 | Mortgage lates | Free text, e.g. "No mortgage 1x30x12" | No |
| 13 | Prepayment Penalty Term | Free text, e.g. "No PPP / 12/24/36 months PP" | Yes (only if Investment-eligible) |
| 14 | Interest Only | Free text conditional rule, e.g. "If Interest Only = Yes: Purchase: min FICO = 740, max LTV = 80%; Refi: max LTV = 75%" | Yes (only if IO offered) |

When asking, always include:
- A one-line example from real samples (above) so the user knows the expected format.
- An option to skip (writes blank in the table — user can fill in Jira later).
- An option to type "guideline" — re-invokes the fetch-from-URL flow for that field only.

After all 14 fields, render the matrix table preview (markdown 2-column). Let the user edit any single row before confirming.

#### 5.4 Render the sub-task body

Combine sections per the template chosen in 5.1. Show the full preview:

```
─────────────────────────────────
SUB-TASK 1 of N
TITLE:   [Non-QM] Logan Finance - Parse Full Doc program
TYPE:    Task
PARENT:  MOSO-15234 (the Epic)
─────────────────────────────────
DESCRIPTION:
# **Rate sheet (Use rate 30 days)**

(Rate grid screenshot attached)

|  |  |
| --- | --- |
| <image placeholder> | **Occupancy** = Owner occupied → Max lender credit = -2% |
| <image placeholder> | **Occupancy** = Investment && PPT = No → 0% / 12mo → -1% / 24mo → -1% / 36mo → -2% |

# **Adjustment**

(Adjustment screenshots attached)

# **Matrix && Validation**

* P/RT : Purchase/Refinance Rate-term
* C/O : Cash-out
* Foreign National (only eligible for Second Home/Investment)

|  |  |
| --- | --- |
| **Citizenship** | US Citizen / Permanent Resident Alien / Non-Permanent Resident Alien / Foreign National |
| **Occupancy** | Primary / Second Home / Investment |
| **Loan term** | 30 years fixed / 30 years fixed IO / 40 years fixed / 40 years fixed IO (Use rate sheet of 30 years) / 5/6 ARM |
| **Document type** | Full doc 12 months / Full doc 24 months |
| **Min-Max loan amount** | Min: $125K  Max: $3M |
| **Property type** | SFR / TH/PUD / Duplex/Triplex/Fourplex / Warrantable Condos / Non-Warrantable Condos / 2-4 Unit (Max LTV = 80%) |
| **Min FICO** | 660 (exclude Foreign National) |
| **DTI** | Max DTI = 50% |
| **Cash Reserved** | ≤ $1M → 3 months / $1-2M → 6 months / > $2M → 9 months / Foreign National: 12 months |
| **Mortgage lates** | No mortgage 1x30x12 |
| **Prepayment Penalty Term** (Investment only) | No PPP / 12/24/36 months PP |
| **Interest Only** | If IO = Yes: Purchase: min FICO = 740, max LTV = 80%; Refi: max LTV = 75% |
─────────────────────────────────
ATTACHMENTS (14 files):
  rate-sheet/full-doc-rates.png, adjustment/full-doc-adj1.png, ...
─────────────────────────────────

Send to Jira? [Y/edit/skip]
```

On confirm, create:

```
mcp__d4873f66-6c13-4695-be2b-dbd414d76d1d__createJiraIssue
  cloudId, projectKey: MOSO, issueTypeName: Task,
  parent: <EPIC_KEY>,
  summary, description (markdown), contentFormat: markdown
```

#### 5.5 Upload screenshots AND inline them into the right sections (2-pass)

The skill inlines screenshots programmatically using a 2-pass create-then-update flow with ADF (Atlassian Document Format), because Jira's markdown mode doesn't support attachment references reliably.

**Pass 1 — placeholder body, create, upload:**

In the body built in 5.4, mark each screenshot insertion point with a unique placeholder token: `<<<SCREENSHOT:section-name:filename.png>>>`. Examples:

```markdown
# **Rate sheet (Use rate 30 days)**

<<<SCREENSHOT:rate-sheet:full-doc-rates.png>>>

|  |  |
| --- | --- |
| <<<SCREENSHOT:rate-sheet:lender-credit-cap-conditions.png>>> | **Occupancy** = Owner occupied → Max lender credit = -2% |
| <<<SCREENSHOT:rate-sheet:lender-credit-cap-pp-conditions.png>>> | **PP Term** = No prepayment → 0% / 12mo → -1% ... |

# **Adjustment**

<<<SCREENSHOT:adjustment:full-doc-adj1.png>>>
<<<SCREENSHOT:adjustment:full-doc-adj2.png>>>
```

Create the sub-task via `createJiraIssue` with this placeholder-laden markdown body. Capture `SUB_TASK_KEY`.

Then upload each image file to the sub-task via curl. For each successful upload, capture from the response JSON:
- `id` (attachment ID — e.g. `"94627"`)
- `filename`
- `mimeType`

Build a map `placeholder_map[token] → {id, filename}` keyed by the placeholder token.

**Pass 2 — replace placeholders with ADF media nodes, edit:**

Convert the body to an ADF document. For each placeholder, replace it with an ADF `mediaSingle` node:

```json
{
  "type": "mediaSingle",
  "attrs": { "layout": "center" },
  "content": [
    {
      "type": "media",
      "attrs": {
        "type": "file",
        "id": "<attachment_id_from_upload_response>",
        "collection": ""
      }
    }
  ]
}
```

Surrounding markdown is converted into ADF paragraph / heading / table nodes (use `contentFormat: "adf"` from the start of Pass 2). Then `editJiraIssue` with the ADF body:

```
mcp__d4873f66-6c13-4695-be2b-dbd414d76d1d__editJiraIssue
  cloudId, issueIdOrKey: <SUB_TASK_KEY>
  additional_fields: {
    "description": <ADF JSON object>
  }
  contentFormat: "adf"
```

**Fallback if ADF generation fails:** if a placeholder fails to find its corresponding upload (file missing, upload rejected, etc.), replace it with a plain text marker `[Screenshot: filename.png — not inlined; see Attachments]` and proceed. Log a warning at the end of the run.

**Files that don't map to placeholders** (extra screenshots in the folder): upload them anyway as plain attachments. They'll appear at the bottom of the ticket and the user can place them manually if desired.

**For the Epic** (ratesheet only): no placeholders needed. Upload the ratesheet as a single plain attachment after Epic creation — `<<<SCREENSHOT:epic:ratesheet>>>` is not necessary since the Epic body doesn't reference the ratesheet inline anyway.

#### 5.6 Add the QA test case checklist as a comment on the sub-task

After the sub-task is created and screenshots are inlined, post a comment on the same sub-task containing a structured QA checklist. The format mirrors the Confluence checklist style observed at MOSO-12073's reference page — items in tables with a "Check" column that QA fills with ✅ or ❌ as they verify each parsed element.

The comment body is **derived from what's in the sub-task body** — every program, adjustment table, and matrix field that was put in the body becomes one row in the checklist. Same source of truth, no duplication of facts, just a different view for QA.

**For QM sub-task** (mirrors MOSO-12073 format):

```markdown
## QA Test Case Checklist

> Verify each parsed element matches the ratesheet. Replace ☐ with ✅ when verified, ❌ if mismatched.

### Fannie Mae — Loan Programs
|  Loan Program | Check |
| --- | --- |
| FANNIE MAE 30 YEAR FIXED (101) | ☐ |
| FANNIE MAE 25 YEAR FIXED (125) | ☐ |
| FANNIE MAE 20 YEAR FIXED (120) | ☐ |
| FANNIE MAE 15 YEAR FIXED (115) | ☐ |
| FANNIE MAE 10 YEAR FIXED (110) | ☐ |
| HOME READY 30 YEAR FIXED (R101) | ☐ |
| FANNIE MAE HB 30 YEAR FIXED (101HB) | ☐ |
| ... | ☐ |

### Freddie Mac — Loan Programs
| Loan Program | Check |
| --- | --- |
| FREDDIE MAC 30 YEAR FIXED (201) | ☐ |
| ... | ☐ |

### Adjustment of FNMA && FHLMC
| Adjustment | Check |
| --- | --- |
| FICO/LTV Purchase Adjustments (Loan terms > 15 years) | ☐ |
| FICO/LTV Rate & Term Adjustments (Loan terms > 15 years) | ☐ |
| FICO/LTV Cashout Adjustments | ☐ |
| Additional Agency Adjustments | ☐ |
| LOAN AMOUNT ** | ☐ |
| MISCELLANEOUS | ☐ |
| LENDER PAID MI | ☐ |
| LPMI (in addition to adjustments above) | ☐ |

### ALT AGENCY Second Home / Investment — Loan Programs
| Loan Program | Check |
| --- | --- |
| Alt Agency 30 Yr Fixed (AltA101) | ☐ |
| ... | ☐ |

### Adjustment for ALT AGENCY 2nd home / Investment
| Adjustment | Check |
| --- | --- |
| FICO/LTV Purchase Adjustments | ☐ |
| ... | ☐ |

### FHA — Base Price
| Loan Program | Check |
| --- | --- |
| FHA 30 - 25 Year Fixed (301 & 325) | ☐ |
| FHA 20 Year Fixed (320) | ☐ |
| FHA 15 Year Fixed (315) | ☐ |
| FHA 30 Year Fixed HB (301HB) | ☐ |

### FHA — Adjustment
| Adjustment | Check |
| --- | --- |
| FICO ≥700 | ☐ |
| FICO 680-699 | ☐ |
| FICO 660-679 | ☐ |
| FICO 640-659 | ☐ |
| FICO 620-639 | ☐ |
| FICO 600-619 | ☐ |
| FICO 580-599 | ☐ |
| FICO 550-579 | ☐ |
| No FICO Score | ☐ |
| Loan Amount >=$100,000 <=$249,999 | ☐ |
| Manufactured Home (Purchase/Rate-Term/Cashout) | ☐ |
| Select (FICO ≥680 & ≥$250,000 & N/A on DPAs) | ☐ |
| 3-4 Units | ☐ |

### VA & USDA — Base Price
| Loan Program | Check |
| --- | --- |
| VA 30 - 25 Year Fixed (401 & 425) | ☐ |
| ... | ☐ |

### VA & USDA — Adjustment
| Adjustment | Check |
| --- | --- |
| ... (same FICO buckets as FHA, plus VA-specific rows) | ☐ |
```

**For QM sub-task with matrix-heavy programs** (Jumbo variants, MOSO-12076 format):

```markdown
## QA Test Case Checklist

### Jumbo — Matrix
| Eligibility Matrix | Check |
| --- | --- |
| Matrix row 1 (Purchase only) | ☐ |
| Matrix row 2 (Purchase and Refinance) | ☐ |
| Matrix row 3 | ☐ |
| ... | ☐ |

### Jumbo — Base Price and Adjustment
- Base Price: ☐
- Adjustment: ☐

### Jumbo Pro — Matrix
| Eligibility Matrix | Check |
| --- | --- |
| ... | ☐ |

### Jumbo Pro — Base Price and Adjustment
- Base Price: ☐
- Adjustment: ☐

### Jumbo Elite — Matrix
### Jumbo Elite — Base Price and Adjustment
### Jumbo Preferred — Matrix
### Jumbo Preferred — Base Price and Adjustment
```

**For Non-QM sub-task** (since the body uses 3 sections + matrix table — checklist mirrors that):

```markdown
## QA Test Case Checklist

### Rate sheet
| Item | Expected | Check |
| --- | --- | --- |
| Products parsed | 30yr Fixed, 30yr IO, 40yr Fixed, 40yr IO, 5/6 ARM | ☐ |
| Lock periods | 30 days | ☐ |
| Rate range | 6.000% – 8.500% in 0.125% steps | ☐ |
| Program variants | DSCR, DSCR Elite | ☐ |
| Lender credit caps applied (Owner Occupied) | Max -2% | ☐ |
| Lender credit caps applied (Investment + PP terms) | 0% / -1% / -1% / -2% | ☐ |

### Adjustment
| Adjustment table | Check |
| --- | --- |
| FICO/LTV Purchase | ☐ |
| FICO/LTV Refinance Rate-Term | ☐ |
| Misc Adjustments | ☐ |
| Value mapping (DSCR < 0.80 → DSCR < 0.75 etc.) | ☐ |

### Matrix && Validation
| Field | Expected | Check |
| --- | --- | --- |
| Citizenship | US Citizen / PRA / NPRA / FN | ☐ |
| Occupancy | Primary / Second Home / Investment | ☐ |
| Loan term | 30 fixed / 30 IO / 40 fixed / 40 IO / 5/6 ARM | ☐ |
| Document type | Full doc 12 mo / 24 mo | ☐ |
| Min loan amount | $125K | ☐ |
| Max loan amount | $3M | ☐ |
| Property type | SFR / TH/PUD / Duplex / 2-4 Unit (≤80% LTV) / Condos | ☐ |
| Min FICO | 660 (exclude FN) | ☐ |
| Max DTI | 50% | ☐ |
| DSCR ranges | < 0.75 / 0.75-1 / 1-1.25 / >1.25 | ☐ |
| Cash Reserved | ≤$1M→3mo / $1-2M→6mo / >$2M→9mo / FN→12mo | ☐ |
| Mortgage lates | No mortgage 1x30x12 | ☐ |
| Prepayment Penalty Term | No PPP / 12/24/36 months PP | ☐ |
| Interest Only | Purchase: FICO≥740 LTV≤80% / Refi: LTV≤75% | ☐ |
```

**For Correspondent sub-task** (single Task, no Epic):

```markdown
## QA Test Case Checklist

### Programs to parse (from Wholesale → Correspondent)
| Program | Check |
| --- | --- |
| Conventional including Home Ready and Home Possible | ☐ |
| High balance and Jumbo | ☐ |
| VA including VA IRRRL | ☐ |

### Cross-reference verification
| Item | Check |
| --- | --- |
| Same rate values as Wholesale parser | ☐ |
| Same adjustment tables as Wholesale parser | ☐ |
| Correspondent provider ID matches the lender record | ☐ |
| Correspondent label appears correctly in pricing UI | ☐ |
```

**Posting the comment:**

```
mcp__d4873f66-6c13-4695-be2b-dbd414d76d1d__addCommentToJiraIssue
  cloudId, issueIdOrKey: <SUB_TASK_KEY>
  commentBody: <markdown body from above templates>
  contentFormat: "markdown"
```

**Important rules for the checklist:**

1. **Source of truth = the sub-task body.** Don't invent items — every checklist row maps to something in the body (a program, an adjustment table, a matrix field). If the body says it's parsed, the checklist tests it.
2. **Empty checkbox by default.** Use `☐` (or `- [ ]` task-list syntax). QA replaces with ✅ when verified, ❌ when mismatched.
3. **Don't post checklist for the Epic.** Epic isn't where parsing is verified — only sub-tasks (which is where the actual rates/adjustments/matrix live). Skip the comment step for the Epic.
4. **For Correspondent (single Task)**, post the checklist as a comment on the Task itself — same place as the body.

### STEP 6 / 7 — (reserved for flow clarity)

### STEP 8 — Correspondent (single Task)

Ask 6 fields one at a time:
1. Lender full name (pre-fill)
2. Provider account ID for Correspondent
3. Correspondent label (e.g. "Loan Factory Direct - Newrez - CL1")
4. Wholesale lender cross-ref (auto-suggest)
5. Programs to parse (free text comma list)
6. Source ticket ID (optional)

Preview → confirm → create one Task (no parent) → upload ratesheet → **also run Step 5.6 (test case comment) on this Task** using the Correspondent template.

### STEP 9 — Final report

```
✓ Created in Jira:

  Epic:        MOSO-15234   https://mosoteam.atlassian.net/browse/MOSO-15234
                            [Parse Non-QM] Logan Finance

  Sub-task 1:  MOSO-15235   [Non-QM] Logan Finance - Parse Full Doc program       (14 attachments, ✓ test case comment)
  Sub-task 2:  MOSO-15236   [Non-QM] Logan Finance - Parse Alt Doc program        (8 attachments, ✓ test case comment)
  Sub-task 3:  MOSO-15237   [Non-QM] Logan Finance - Parse DSCR programs          (12 attachments, ✓ test case comment)

Each sub-task has rates, adjustments, and a complete Matrix && Validation table
ready for /new-parser. Ratesheet attached to the Epic. Each sub-task also has
a QA test case checklist as a comment — QA fills ☐ with ✅ or ❌ as items are
verified.

When you're ready, run:
  /new-parser MOSO-15234            (whole lender)
  /new-parser MOSO-15235            (one sub-task at a time)
```

Do NOT auto-invoke `/new-parser`.

---

## UPDATE MODE pipeline (when argument is a Jira key)

Triggered when the skill is called with a Jira key like `/parser-task-builder MOSO-12075`. The goal: update an existing ticket's body and attachments to reflect a newer ratesheet / matrix / guideline — while preserving any manual edits the user (or BA) made directly in Jira.

```
U.0 Detect & confirm  →  U.1 Fetch existing  →  U.2 Collect new files & detect changes  →
U.3 Section diff with manual-edit detection  →  U.4 Per-section accept/reject/edit  →
U.5 Attachment management (case-by-case)  →  U.6 Build new body  →
U.7 Upload new attachments  →  U.8 Delete attachments marked for removal  →
U.9 editJiraIssue with ADF body  →  U.10 Report
```

### U.0 — Detect & confirm

```
Detected Jira key: MOSO-12075 → UPDATE MODE.

I'll fetch the existing ticket, then ask you for the new files (new ratesheet,
new matrix, or new guideline). I'll detect any sections you've manually edited
in Jira and ask before overwriting them. Attachments will be handled
case-by-case (keep / replace / delete) per file.

Proceed? [Y/cancel]
```

### U.1 — Fetch existing task

```
mcp__d4873f66-6c13-4695-be2b-dbd414d76d1d__getJiraIssue
  cloudId, issueIdOrKey: <KEY>
  fields: ["summary", "description", "issuetype", "parent", "attachment"]
  responseContentFormat: "adf"   ← so we can detect inline media nodes
```

Parse the response:
- `EXISTING.title`, `EXISTING.type` (Epic / Task), `EXISTING.parent_key` (if any)
- `EXISTING.body_adf` — the current description as ADF
- `EXISTING.body_text` — flattened markdown approximation for diffing
- `EXISTING.attachments[]` — `[{id, filename, mimeType, size, created}, ...]`

From the title, infer which template the ticket follows:
- `[Parse QM] <Lender>` or `[Parse Non-QM] <Lender>` → Epic
- `[QM] <Lender> - Parse ... programs` → QM sub-task (per-program template)
- `[Non-QM] <Lender> - Parse ... program` → Non-QM sub-task (3-section template)
- `[QM] <Lender> - Parse Correspondent's rates` → Correspondent

### U.2 — Collect new inputs

Ask the user what changed:

```
What's new for this ticket?

  a) Updated ratesheet         (new rates / new LLPAs)
  b) Updated matrix            (new eligibility rules)
  c) Updated guideline PDF     (full product profile refresh)
  d) Updated portal URL or email metadata
  e) Several of the above
  f) Just fixing a typo / specific value
```

For each chosen category, ask for the input (same upfront checklist as create mode, but only the relevant fields). Then run **the same Step 1.5 auto-extract pass** on the new files — produces a fresh `EXTRACTION` object.

### U.3 — Section diff + manual-edit detection

Compare current ticket body section-by-section against (a) what's in the new `EXTRACTION` and (b) what the create-mode template would have generated originally.

For each section (e.g. `# Rate sheet`, `# Adjustment`, `# Matrix && Validation` for Non-QM; per-program sections for QM):

1. **Extract current section content** from `EXISTING.body_adf`.
2. **Generate proposed section content** from new `EXTRACTION`.
3. **Detect manual edits**: if current section has content that doesn't match either (a) the original template skeleton or (b) old extraction, flag it as `manual_edit_suspected`. Heuristics:
   - Free-text paragraphs outside of expected template slots
   - Bulleted notes/comments not produced by template
   - Extra rows in the matrix table beyond the standard 14 fields
   - Modified field values that look like deliberate edits (e.g. annotations like "(checked with underwriting 2025-04-01)")
4. **Classify the section** as one of:
   - `unchanged` — current matches proposed
   - `changed_auto` — current matches template, proposed has new auto-extracted values → safe to update
   - `changed_manual` ⚠️ — current has manual edits, proposed would overwrite them → REQUIRES CONFIRMATION
   - `removed` — current has content, proposed has nothing → unlikely but report
   - `added` — current has nothing, proposed has content → safe to add

Show the user the classification summary:

```
─────────────────────────────────
SECTION DIFF for MOSO-12075
─────────────────────────────────
  Rate sheet         changed_auto    Lock period: 30d → 30d, 45d
                                     Rate range:  6.000-8.000 → 6.250-8.500

  Adjustment         changed_auto    Misc Adjustments: +2 new rows
                                     (Manufactured Home, Cash-Out)

  Matrix && Validation
    Citizenship      unchanged
    Occupancy        unchanged
    Min FICO         changed_auto    660 → 640
    Cash Reserved    changed_manual ⚠️  Has a manual note added by user:
                                       "Updated 2025-03-15 per Kurt's email re:
                                       FN reserve requirement"
    Mortgage lates   unchanged
    Interest Only    unchanged
    ... (10 more rows)
─────────────────────────────────

Found 2 auto changes and 1 section with suspected manual edits.
How do you want to proceed?
```

### U.4 — Per-section review

Use `AskUserQuestion` with options:

- **Accept all `changed_auto`, ask per `changed_manual`** (default — recommended)
- **Accept all changes including manual** (overwrites manual edits)
- **Per-section walk** — ask `accept / edit / reject` for every section that has any change
- **Cancel update**

For each `changed_manual` section, ALWAYS ask explicitly:

```
Section "Cash Reserved" has a manual note:
  "Updated 2025-03-15 per Kurt's email re: FN reserve requirement"

The new extraction would replace this with the auto-extracted value from the
new guideline. What do you want?

  a) Keep the manual note unchanged
  b) Replace with auto-extracted value (discard manual note)
  c) Merge — keep both (auto-extracted value + your manual note as a sub-bullet)
  d) Show me the proposed new value before deciding
```

### U.5 — Attachment management (case-by-case)

List all existing attachments with metadata:

```
Existing attachments on MOSO-12075:
  1. NON_QM_Wholesale_Rate_Sheet_2025-04-04.pdf    (392 KB, attached 2025-04-04)
  2. matrix-citizenship.png                          (45 KB, attached 2025-04-04)
  3. matrix-occupancy.png                            (38 KB, attached 2025-04-04)
  4. adj-fico-ltv-purchase.png                       (153 KB, attached 2025-04-04)

For each, what do you want?
```

Ask `AskUserQuestion` for each file:

- **Keep** (no change)
- **Replace** with new file (user provides path)
- **Delete**
- **Skip review** (treat as keep)

Also list NEW files to upload from the new folder (any file in the user-provided new folder that doesn't have a matching name in EXISTING.attachments).

### U.6 — Build new body

Construct the new body the same way as create mode:
1. Render markdown with `<<<SCREENSHOT:section:filename.png>>>` placeholders.
2. Skipped sections (rejected by user in U.4) → leave EXISTING content untouched (extract from EXISTING.body_adf and pass through).
3. Merged sections (option `c` in U.4) → combine auto value + manual note.
4. Reordering: preserve the original section order — don't shuffle.

### U.7 — Upload new attachments

For each file user marked as "replace" or "new":
- Upload via curl to `$JIRA_BASE/rest/api/3/issue/<KEY>/attachments`
- Capture new attachment ID

For attachments that are kept (no change), preserve the existing IDs for ADF media references.

### U.8 — Delete attachments marked for removal

For each file user marked `delete` (and each old file being `replace`d):
```bash
curl -s -u "$JIRA_EMAIL:$JIRA_API_TOKEN" \
  -X DELETE \
  "$JIRA_BASE/rest/api/3/attachment/<attachment_id>"
```

### U.9 — Update via editJiraIssue with ADF body

Convert the new markdown body to ADF, replacing each `<<<SCREENSHOT:...>>>` placeholder with a `mediaSingle` node pointing at the correct attachment ID (new uploads OR preserved IDs from U.7).

```
mcp__d4873f66-6c13-4695-be2b-dbd414d76d1d__editJiraIssue
  cloudId, issueIdOrKey: <KEY>
  additional_fields: { "description": <ADF JSON> }
  contentFormat: "adf"
```

**Do NOT change** title, issue type, or parent. Update mode only touches description and attachments.

### U.9.5 — Refresh test case comment (only if body changed)

If U.4 resulted in any section actually being updated (not just unchanged + rejected), post a new test case comment on the ticket using the **updated** body's contents (programs, adjustment tables, matrix fields). Do NOT delete the old test case comment — leave it for history so QA can see what changed:

```
mcp__d4873f66-6c13-4695-be2b-dbd414d76d1d__addCommentToJiraIssue
  cloudId, issueIdOrKey: <KEY>
  commentBody: |
    ## QA Test Case Checklist (refreshed <YYYY-MM-DD>)

    > This checklist was regenerated after a body update. The previous
    > checklist comment is still above for reference.

    <regenerated checklist tables, same format as STEP 5.6>
  contentFormat: "markdown"
```

If body changes were trivial (only typos, no item changes), skip this step — old checklist still applies.

### U.10 — Final report

```
✓ Updated MOSO-12075

Sections updated:
  ✓ Rate sheet         (Lock period + Rate range refreshed)
  ✓ Adjustment         (2 new Misc rows added)
  ✓ Min FICO           (660 → 640)
  ⊙ Cash Reserved      (preserved your manual note)

Attachments:
  ✓ Replaced: NON_QM_Wholesale_Rate_Sheet → 2025-05-04 version
  + Added: matrix-cash-reserved-updated.png
  - Deleted: outdated-adj-misc.png

URL: https://mosoteam.atlassian.net/browse/MOSO-12075

If this is part of a re-parse cycle, run /new-parser MOSO-12075 to rebuild
the parser code against the updated body.
```

---

## Pitfalls to Catch

0. **Don't ask what you can read.** Always run Step 1.5 (auto-extract) before asking matrix questions. If a value is visible in the ratesheet, matrix screenshot, or guideline PDF, pre-fill it and let the user review — don't make them type it.
0a. **UPDATE MODE: never silently overwrite manual edits.** Section diff must detect content that doesn't match the original template skeleton and flag it as `changed_manual` ⚠️. Always ask the user before overwriting flagged sections. Loss of manual notes is the #1 user complaint with this kind of tool.
0b. **UPDATE MODE: never change title, type, or parent.** Update mode only touches description and attachments. If user wants to change title/type/parent, they edit in Jira directly or recreate the ticket.
0c. **UPDATE MODE: confirm attachment deletion explicitly.** Deletes are irreversible. Always show the filename + size + date before each delete and require user confirmation. Default to "keep" if user is unsure.
0d. **Test case checklist must derive from body, not from the lender's portal/web.** Every row in the QA checklist must correspond to something explicitly listed in the sub-task body — a program in the Rate sheet section, an adjustment table in the Adjustment section, or a field in the Matrix table. Never add a checklist row for something not in the body. If an item is in the body but not the checklist, that's a bug — re-generate.
0e. **No test case checklist on the Epic.** The Epic doesn't hold the parsing facts — only sub-tasks do. Only Tasks (sub-tasks under an Epic AND standalone Correspondent Tasks) get the comment.
0a. **Auto-extraction is fallible.** Always show the extracted matrix as a preview before submission. Mark low-confidence fields with ⚠️. Never auto-submit without user review.
1. **Empty matrix table.** Never let a sub-task body have a Matrix section with blank rows. If auto-extract found nothing AND the user can't fill it manually, run the fetch-from-URL flow or warn loudly and ask whether to proceed anyway. Applies to both Non-QM (mandatory) and QM (when the per-program "type matrix?" gate is `y`).
2. **QM matrix gate defaults.** Agency programs (FNMA, FHLMC, USDA-within-VA&USDA, FHA Streamline & VA IRRRL) default to `Use system validations` only — skip the matrix interview. Non-agency / overlay programs (ALT AGENCY, Jumbo variants, custom FHA overlays) default to running the matrix interview. Always confirm with the user before skipping.
3. **Inline-screenshot 2-pass ordering.** Always create the ticket first, upload attachments second, edit the description third. If you try to inline before upload, the attachment IDs don't exist and ADF media nodes break.
4. **ADF media node `id` correctness.** The `id` must match the attachment response's `id` field exactly. If you upload `image.png` and the response says `"id": "94627"`, the ADF media attrs `id` must be `"94627"`. Mismatch = broken image render in Jira.
5. **Provider ID typos.** Echo digits back in the preview. Validate length and numeric.
6. **Sub-task missing `parent`.** Always pass `parent: <EPIC_KEY>` for QM/Non-QM sub-tasks.
7. **QM vs Non-QM template mismatch.** QM = per-program sections (with optional typed matrix per program). Non-QM = 3 sections + always-typed matrix table. Don't mix.
8. **Title prefix mismatch.** `[Parse QM]`/`[Parse Non-QM]` for Epic. `[QM]`/`[Non-QM]` for sub-tasks. `[QM] ... - Parse Correspondent's rates` for Correspondent. Auto-derive from type — don't ask.
9. **Issue type mismatch.** Epic for parent, Task for everything else (sub-tasks AND Correspondent).
10. **JIRA_EMAIL/API_TOKEN missing.** Tickets create via MCP (OAuth). Attachments need curl + env vars. Without env vars, the 2-pass inline flow can't complete — fall back to creating tickets with `(screenshots not attached)` placeholders and warn loudly. Don't crash.
11. **One question at a time.** Never batch. Never show a wall of fields. `AskUserQuestion` per field. Pre-fill suggestions from earlier answers.
12. **Don't auto-chain into `/new-parser`.** Print URLs and stop.

---

## Example walkthrough (Non-QM, with guideline fetch)

User: `/parser-task-builder ~/Downloads/logan-finance-jira/`

```
[Skill] I'll help you build the Jira tickets for this lender. …
        I see a folder with ratesheet + screenshots + a guideline.pdf. Looking inside.

[1/9] Ratesheet: NON_QM_Wholesale_Rate_Sheet_2025-04-04.pdf
      Candidate lender: "Logan Finance"
      lender-info.sh: not yet registered → new parser
      Guideline PDF: guideline.pdf (will use if needed for matrix)
      Screenshot folders: rate-sheet/, adjustment/, matrix/

[2/9] Type: Non-QM (high — "DSCR", "Bank Statement", "Non-QM" in ratesheet)
      Confirm? → Non-QM

[3/9] Epic fields:
      • Lender full name? → Logan Finance Rates. Inc.
      • Provider ID?      → 32280617046
      • Sender name?      → Kurt Lehrmann
      • Sender address?   → klehrmann@loganfinance.com
      • Subject?          → Today's Wholesale Non-QM Rates from Logan
      Preview Epic → confirm → MOSO-15234 created, ratesheet attached ✓

[4/9] How many sub-tasks? → 3
      Title 1? → Full Doc program
      Title 2? → Alt Doc program
      Title 3? → DSCR programs

[5/9] SUB-TASK 1: "[Non-QM] Logan Finance - Parse Full Doc program"

      Rate sheet section:
        Lock period? → 30 days
        Variants? → (single, skip)
        Lender credit caps? → Yes
          Caps:
            Owner occupied → max -2%
            Investment + PPT No → 0% / 12mo → -1% / 24mo → -1% / 36mo → -2%

      Adjustment section:
        Value mapping needed? → No

      Matrix && Validation section:
        How to fill the matrix?
          a) Walk through each field
          b) Paste full matrix text
          c) Fetch from guideline URL
        → c

        Guideline URL? → (user pastes Logan Finance guideline URL)
        Fetching… extracted matrix:
          Citizenship: US Citizen, PRA, NPRA, FN
          Occupancy:   Primary, Second Home, Investment
          Loan term:   30 fixed, 30 IO, 40 fixed, 40 IO (use 30 rate), 5/6 ARM
          Doc type:    Full doc 12 months / 24 months
          Loan amt:    $125K - $3M
          Property:    SFR, TH/PUD, 2-4 unit (LTV ≤80%), Condos, Non-Warrantable
          Min FICO:    660 (excl. FN)
          DTI:         50%
          Cash res:    ≤$1M → 3mo / $1-2M → 6mo / >$2M → 9mo / FN: 12mo
          Lates:       No mortgage 1x30x12
          PPT:         No PPP / 12/24/36 months PP (Investment only)
          IO:          Purchase: FICO≥740, LTV≤80% / Refi: LTV≤75%
        Looks right? → Y

      Render preview → confirm → MOSO-15235 created as child of MOSO-15234
      Uploaded 14 screenshots ✓

[5/9] SUB-TASK 2: "[Non-QM] Logan Finance - Parse Alt Doc program"
      ... (same flow)

[5/9] SUB-TASK 3: "[Non-QM] Logan Finance - Parse DSCR programs"
      Variants? → DSCR, DSCR Elite
      Adjustment value mapping? → Yes (DSCR < 0.80 → DSCR < 0.75, etc.)
      Matrix fill → walk-through (no DTI, has DSCR ranges)
      ... → MOSO-15237 created ✓

[9/9] ✓ Done.
      Epic: MOSO-15234
      Sub-task 1 (Full Doc):  MOSO-15235
      Sub-task 2 (Alt Doc):   MOSO-15236
      Sub-task 3 (DSCR):      MOSO-15237

      Ready: /new-parser MOSO-15234
```

---

## Rules of Operation

1. **Read first, ask second.** Step 1.5 auto-extracts from ratesheet + matrix screenshots + guideline PDF before any matrix questions. Never ask the user for a value that's in one of their files.
2. **Sub-task body must be complete.** Rates described or attached, adjustments described or attached, matrix table FULLY TYPED OUT. Empty matrix = bug.
3. **QM and Non-QM bodies are different.** QM = per-program sections (with optional typed matrix per program — gated by the agency/overlay default). Non-QM = Rate sheet / Adjustment / Matrix && Validation with always-typed 14-field matrix.
4. **Always show extraction before submission.** The auto-extracted matrix is presented as a preview with three options: accept all / edit a row / re-extract. ⚠️-flag any low-confidence fields.
5. **One question at a time for what's NOT extractable.** Use `AskUserQuestion` per field for provider ID, email metadata, sub-task split. Never batch.
6. **Pre-fill from earlier answers and extraction.** Lender name from ratesheet header, type from auto-detect, matrix from screenshots/guideline, programs from sub-task title.
7. **Always confirm before sending.** Render the Epic and each sub-task body preview. Provider IDs especially — echo digits back.
8. **Sub-task `parent` is mandatory.** Verify `EPIC_KEY` non-empty before each sub-task create.
9. **Markdown for create, ADF for edit.** Pass 1 `createJiraIssue` uses `contentFormat: "markdown"` with placeholders. Pass 2 `editJiraIssue` uses `contentFormat: "adf"` to inline media nodes.
10. **Attachments fail open.** No `JIRA_EMAIL`/`JIRA_API_TOKEN` → ticket created with `(screenshots not attached)` placeholders, warn user.
11. **Never auto-chain into `/new-parser`.** Print URLs and stop.
12. **Always post a test case checklist comment** after creating any sub-task (or Correspondent Task). Skip only for the Epic. Checklist content derives from the sub-task body.
