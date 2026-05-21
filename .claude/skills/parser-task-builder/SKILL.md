---
name: parser-task-builder
description: Build a Jira parser ticket from a ratesheet + screenshots. Auto-detects QM / Non-QM / Correspondent, asks only for the four fields the ratesheet can't tell, creates the ticket via Atlassian MCP, uploads attachments, returns the URL.
argument-hint: [ratesheet path or folder] (optional)
allowed-tools: Bash, Read, Write, Glob, Grep, AskUserQuestion, mcp__d4873f66-6c13-4695-be2b-dbd414d76d1d__createJiraIssue, mcp__d4873f66-6c13-4695-be2b-dbd414d76d1d__getJiraIssue
---

# /parser-task-builder — Ratesheet → Jira Ticket

You are a **task builder** for new lender parser work. You take a ratesheet (PDF / XLSX / XLSM / XLS) plus any portal screenshots and produce a Jira ticket in the **exact format the Moso team uses in practice** for one of three parser types: QM new parser, Non-QM new parser, or Correspondent.

You do NOT analyze the ratesheet beyond identification — that's the `/new-parser` skill's job downstream.

---

## Environment & Constants

```
CLOUD_ID    = "5858106a-50e6-442e-a751-14c0f4243e87"
PROJECT_KEY = "MOSO"
TICKET_TEMPLATES_DIR = "/Users/trungthach/IdeaProjects/tools/.claude/skills/parser-task-builder"
```

---

## Three Templates (derived from real samples)

These are the **actual patterns** the team uses, observed from MOSO-12073 (QM), MOSO-12677 (Non-QM), MOSO-14984 (Correspondent). Match them exactly — do NOT inject the more thorough BA_GUIDE_WRITE_PARSER_TASK template; current practice is leaner and BA derives matrix/eligibility from the ratesheet + portal screenshots downstream.

### Template A — QM new parser

- **Title**: `[Parse QM] <Lender Name>`
- **Issue type**: `Epic`
- **Body**:
  ```markdown
  # **Get rate sheet**

  * **Apply for lender:** <Lender Full Name>(<provider_account_id>)
  * **Rate sheet attached to email from sender:** <email_address> (**<Sender Name>**)
  * **Email subject:** <email_subject>
  ```

### Template B — Non-QM new parser

- **Title**: `[Parse Non-QM] <Lender Name>`
- **Issue type**: `Epic`
- **Body**: same shape as Template A — only the title prefix differs.

### Template C — Correspondent

- **Title**: `[QM] <Lender Name> - Parse Correspondent's rates`
- **Issue type**: `Task`
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

The Correspondent template only fits when the lender's Wholesale parser already exists and uses the same ratesheet. If it doesn't, fall back to Template A or B (this becomes effectively a new parser).

---

## Pipeline

```
0. Resolve input  →  1. Identify lender & files  →  2. Auto-detect type  →  3. Ask 4 fields  →
4. Render preview  →  5. User confirm  →  6. Create ticket (MCP)  →  7. Upload attachments (curl)  →  8. Report URL
```

### STEP 0 — Resolve input

Argument may be:
- A path to a single ratesheet file (e.g. `/Users/.../Jet_Advantage_0213.pdf`)
- A path to a folder containing the ratesheet + screenshots
- Empty → ask the user

```
What I need from you:
  • The ratesheet (PDF or XLSX) — required
  • Any portal screenshots showing the eligibility matrix — optional but helpful
Drop a path, or a folder, or paste the files.
```

Collect:
- `RATESHEET_PATH` — the main `.pdf`/`.xlsx`/`.xlsm`/`.xls` file
- `SCREENSHOT_PATHS[]` — every `.png`/`.jpg`/`.jpeg` in the same folder (or explicitly listed)

If no ratesheet found, stop with a clear error.

### STEP 1 — Identify lender & files

Extract candidate lender name from the ratesheet filename. Strip dates, common suffixes (Ratesheet, Wholesale, Correspondent, NonQM), normalize underscores/dashes to spaces, CamelCase the result.

Then read the first page of the PDF or the first sheet of the Excel and look for a lender name near the top to corroborate. Pick the best candidate and confirm with the user later.

Pre-check whether this lender already has a parser:

```bash
cd /Users/trungthach/IdeaProjects/packs/loan && ./lender-info.sh "<CandidateName>" 2>&1 | head -10
```

If the script returns a hit, this is likely a Correspondent (or update-existing) case, not a new parser.

### STEP 2 — Auto-detect type

Score against three buckets using the ratesheet + filename:

| Bucket | Strong signals | Weak signals |
|---|---|---|
| **Non-QM** | filename contains `nonqm` / `non-qm`; ratesheet contains "DSCR", "Bank Statement", "1099", "ITIN", "Asset Depletion", "Non-QM" | "Non-Agency", "Investor Cash Flow" |
| **Correspondent** | filename contains `correspondent`; description says "uses same ratesheet"; existing Wholesale parser found in Step 1 | tab named "Correspondent" |
| **QM** (default) | "Conventional", "Conforming", "FHA", "VA", "USDA"; no Non-QM signals | — |

Show the user the detection result and ask to confirm:

```
Detected type: <BUCKET> (confidence: <high/medium/low>)
Reason: <one-sentence reason>

Is that right? [Y/n/other]
```

Use the `AskUserQuestion` tool with the three options if the user picks "other" or confidence is low.

### STEP 3 — Ask the 4 (or 5) fields the ratesheet can't tell

Use `AskUserQuestion` per field for clean rendering. Match the questions to the type:

For **QM** and **Non-QM**:
1. **Provider account ID** — 10–11 digit number from the lender's record. Copy-paste, never re-type. Sample: `34657427311`.
2. **Email sender name** — e.g. `Todd Halbreich`.
3. **Email sender address** — e.g. `THalbreich@jetadvantagemtg.com`.
4. **Email subject** — e.g. `FW: Jet Advantage Ratesheet`.

For **Correspondent**:
1. **Provider account ID for the Correspondent record** (different from Wholesale).
2. **Correspondent label** as it appears in the system — e.g. `Loan Factory Direct - Newrez - CL1`.
3. **Wholesale lender name** to cross-reference (auto-suggest the candidate from Step 1).
4. **Programs to parse** — multi-select or free text. Examples: `Conventional including Home Ready and Home Possible`, `High balance and Jumbo`, `VA including VA IRRRL`.
5. **Source ticket ID** — optional. The internal request ticket if there is one (sample: `36507707157`).

### STEP 4 — Render the preview

Build the title and description from the chosen template. Show the user the full preview before sending:

```
─────────────────────────────────
TITLE:  [Parse QM] Jet Advantage Mortgage
TYPE:   Epic
─────────────────────────────────
DESCRIPTION:
# **Get rate sheet**

* **Apply for lender:** Jet Advantage Mortgage Rates. Inc.(34657427311)
* **Rate sheet attached to email from sender:** THalbreich@jetadvantagemtg.com (**Todd Halbreich**)
* **Email subject:** FW: Jet Advantage Ratesheet
─────────────────────────────────
ATTACHMENTS:
  • Jet_Advantage_Ratesheet_0213.pdf
  • portal_eligibility_matrix.png
─────────────────────────────────

Send to Jira? [Y/edit/cancel]
```

If the user picks "edit", let them adjust any one field and re-render. If "cancel", abort cleanly.

### STEP 5 — Create the ticket via Atlassian MCP

```
mcp__d4873f66-6c13-4695-be2b-dbd414d76d1d__createJiraIssue
  cloudId:       "5858106a-50e6-442e-a751-14c0f4243e87"
  projectKey:    "MOSO"
  issueTypeName: "Epic"  (or "Task" for Correspondent)
  summary:       "<title>"
  description:   "<rendered markdown body>"
  contentFormat: "markdown"
```

Capture the returned issue `key` (e.g. `MOSO-15234`) and `webUrl`.

### STEP 6 — Upload attachments

The Atlassian MCP has no attachment tool. Use Jira's REST attachment endpoint via curl. Requires `JIRA_EMAIL` and `JIRA_API_TOKEN` env vars (already used by `/new-parser`).

```bash
# Verify auth available
if [ -z "$JIRA_EMAIL" ] || [ -z "$JIRA_API_TOKEN" ]; then
  echo "WARN: JIRA_EMAIL/JIRA_API_TOKEN not set — skipping attachment upload"
  echo "      You can attach manually at: https://mosoteam.atlassian.net/browse/<ISSUE_KEY>"
  exit 0
fi

# Upload each file
for FILE in "${ATTACHMENT_PATHS[@]}"; do
  curl -s -u "$JIRA_EMAIL:$JIRA_API_TOKEN" \
    -H "X-Atlassian-Token: no-check" \
    -F "file=@$FILE" \
    "https://mosoteam.atlassian.net/rest/api/3/issue/<ISSUE_KEY>/attachments" \
    -o /tmp/jira-attach-resp.json
  if grep -q '"id"' /tmp/jira-attach-resp.json; then
    echo "✓ uploaded: $(basename "$FILE")"
  else
    echo "✗ failed: $(basename "$FILE")"
    cat /tmp/jira-attach-resp.json | head -5
  fi
done
```

Order: ratesheet first (most important), then screenshots in alphabetical order.

### STEP 7 — Verify and report

Re-fetch the ticket to confirm attachments landed:

```
mcp__d4873f66-6c13-4695-be2b-dbd414d76d1d__getJiraIssue
  cloudId:    "5858106a-50e6-442e-a751-14c0f4243e87"
  issueIdOrKey: "<ISSUE_KEY>"
  fields:     ["summary", "issuetype", "attachment"]
```

Print the summary to the user:

```
✓ Ticket created: MOSO-15234
  Title:       [Parse QM] Jet Advantage Mortgage
  Type:        Epic
  URL:         https://mosoteam.atlassian.net/browse/MOSO-15234
  Attachments: 2 files uploaded (Jet_Advantage_Ratesheet_0213.pdf, portal_eligibility_matrix.png)

Ready to parse. When you want to start, run:
  /new-parser MOSO-15234
```

Stop here. **Do not auto-invoke `/new-parser`** — the user wants to control that step.

---

## Field Mapping Reference

Built from MOSO-12073 / MOSO-12677 / MOSO-14984:

| Sample field | Where it comes from | Example |
|---|---|---|
| Lender full name | Ratesheet header + email | `Jet Advantage Mortgage Rates. Inc.` |
| Provider account ID | Internal lender record (user input) | `34657427311` |
| Email sender name | Email "From:" header (user input) | `Todd Halbreich` |
| Email sender address | Email "From:" header (user input) | `THalbreich@jetadvantagemtg.com` |
| Email subject | Email subject line (user input) | `FW: Jet Advantage Ratesheet` |
| Correspondent label | Lender record (user input) | `Loan Factory Direct - Newrez - CL1` |
| Wholesale cross-ref | `lender-info.sh` lookup | `NewRez` |
| Source ticket ID | Optional, user input | `36507707157` |

---

## Pitfalls to Catch

1. **Provider account ID typos**: Always copy-paste. Echo back the digits to the user before submission so they spot a wrong character. Format hint: it's a 10–11 digit number — flag if user types less than 10.
2. **Title prefix mismatch**: `[Parse QM]` for new parser, `[QM]` for Correspondent. Easy to confuse. Auto-derive from the chosen type, don't let the user type the prefix.
3. **Wrong issue type**: Correspondent is `Task`, new QM/Non-QM is `Epic`. The skill picks this from the type detection — don't override.
4. **Lender name spelling**: Should match (or become) the `LenderType.<Name>` enum. CamelCase the name in the title (e.g. `Jet Advantage Mortgage`, not `jet advantage mortgage`).
5. **Correspondent without Wholesale**: If `lender-info.sh` doesn't find the Wholesale lender, warn the user — the "uses same ratesheet" shortcut won't work and this should probably be a new parser instead.
6. **Missing portal screenshots for new parsers**: For Template A and B, eligibility info often isn't on the ratesheet. Gently nudge: "No screenshots provided — did you want to add eligibility/matrix screenshots from the lender portal? They help BA later. [skip/add]"
7. **JIRA_EMAIL / JIRA_API_TOKEN missing**: Ticket creates via MCP regardless (MCP uses OAuth), but attachments will silently skip. Surface a clear warning at the end of Step 6 if upload skipped.

---

## Examples

### Example 1: QM new parser

User: `/parser-task-builder ~/Downloads/Jet_Advantage_Ratesheet_0213.pdf`

```
[1/8] Reading ratesheet... candidate lender: "Jet Advantage Mortgage"
[1/8] lender-info.sh shows: not yet registered. → new parser.
[2/8] Type detection: QM (high confidence — "Conventional", "FHA", "VA" in ratesheet, no Non-QM signals)
       Confirm? [Y/n] → Y
[3/8] Need 4 fields:
       • Provider account ID? → 34657427311
       • Email sender name?    → Todd Halbreich
       • Email sender address? → THalbreich@jetadvantagemtg.com
       • Email subject?        → FW: Jet Advantage Ratesheet
[4/8] Preview ready (shown above). Send? [Y/edit/cancel] → Y
[5/8] Creating Epic in MOSO... created MOSO-15234
[6/8] Uploading 1 attachment... ✓ Jet_Advantage_Ratesheet_0213.pdf
[7/8] Verifying... 1 attachment confirmed
[8/8] ✓ Done. https://mosoteam.atlassian.net/browse/MOSO-15234
       Run /new-parser MOSO-15234 when you're ready to start.
```

### Example 2: Correspondent

User: `/parser-task-builder ~/Downloads/NewRez_2025-12-08_08_50_30.xlsx`

```
[1/8] Reading ratesheet... candidate lender: "NewRez"
[1/8] lender-info.sh shows: NewRez Wholesale parser EXISTS. → likely Correspondent.
[2/8] Type detection: Correspondent (medium — Wholesale exists, ratesheet is shared format)
       Confirm? [Y/n/other] → Y
[3/8] Need 5 fields:
       • Provider account ID (Correspondent)? → 36509177491
       • Correspondent label?                  → Loan Factory Direct - Newrez - CL1
       • Wholesale cross-ref [NewRez]?         → NewRez
       • Programs to parse?                    → Conventional including Home Ready and Home Possible, High balance and Jumbo, VA including VA IRRRL
       • Source ticket ID (optional)?          → 36507707157
[4/8] Preview ready. Send? [Y/edit/cancel] → Y
[5/8] Creating Task in MOSO... created MOSO-15235
[6/8] Uploading 1 attachment... ✓ NewRez_2025-12-08_08_50_30.xlsx
[7/8] Verifying... 1 attachment confirmed
[8/8] ✓ Done. https://mosoteam.atlassian.net/browse/MOSO-15235
       Run /new-parser MOSO-15235 when you're ready to start.
```

---

## Rules of Operation

1. **Lean over thorough.** Match the actual three sample tickets, not BA_GUIDE_WRITE_PARSER_TASK.md. BA's job is to derive matrix/eligibility from ratesheet + portal screenshots later — don't pre-fill it.
2. **Auto-detect, confirm, never assume.** Always show the detected type and the rendered preview before sending. One wrong title prefix is worth catching.
3. **Don't auto-chain into `/new-parser`.** Stop at ticket creation. Print the URL and stand down.
4. **Never invent the provider account ID.** Always ask the user.
5. **Echo back what you typed.** Numbers in particular (provider IDs) — show them in the preview so typos are caught before submission.
6. **Markdown body, not ADF.** Pass `contentFormat: "markdown"` to `createJiraIssue` — matches how the existing tickets render.
7. **Attachments fail open.** If JIRA_EMAIL/API_TOKEN are missing, create the ticket anyway, warn loudly, and tell the user how to attach manually.
