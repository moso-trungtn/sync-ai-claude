---                                                                                                                                                                                                                              
  name: jira                                                                                                                                                                                                                       
  description: View a Jira issue with all images, or create a short BA-friendly MOSO task (`create <what happened>`)                                                                                                                                                                      
  disable-model-invocation: true                                                                                                                                                                                                   
  argument-hint: <ISSUE_KEY or URL> | create <what happened>                               
  allowed-tools: Bash, Read
  ---

  # Jira Task Viewer

  Read a Jira task with full content and all images.

  ## Input
  `$ARGUMENTS` — a Jira URL (e.g., `https://mosoteam.atlassian.net/browse/MOSO-15758`) or issue key (e.g., `MOSO-15758`).

  ## Instructions

  ### Step 1: Extract the issue key
  Parse the issue key from `$ARGUMENTS`. If it's a URL like `https://mosoteam.atlassian.net/browse/MOSO-15758`, extract `MOSO-15758`. If it's already a key, use it directly.

  ### Step 2: Fetch the issue via REST API
  Run this command (the user has `JIRA_EMAIL` and `JIRA_API_TOKEN` env vars configured):

  ```bash
  curl -s -L -u "$JIRA_EMAIL:$JIRA_API_TOKEN" \
    "https://mosoteam.atlassian.net/rest/api/2/issue/<ISSUE_KEY>?fields=summary,description,status,assignee,priority,attachment,comment,creator,created,updated,issuetype,labels,parent"

  Step 3: Parse and present the issue metadata

  Display a summary table with: Title, Status, Priority, Assignee, Creator, Created date, Type, Labels, Parent (if exists).

  Step 4: Download ALL image attachments

  For each attachment with mimeType starting with image/:

  mkdir -p /tmp/jira-<ISSUE_KEY>
  curl -s -L -u "$JIRA_EMAIL:$JIRA_API_TOKEN" \
    -o "/tmp/jira-<ISSUE_KEY>/<filename>" \
    "https://mosoteam.atlassian.net/rest/api/2/attachment/content/<attachment_id>"

  Download all images in a single chained command for efficiency.

  Step 5: Read all downloaded images

  Use the Read tool to view each downloaded image file. Read all images in parallel.

  Step 6: Present the description

  Parse the Jira wiki markup description and present it in readable markdown, inserting the images inline where they appear in the description (match by filename). For images referenced in the description (e.g.,
  !image-xxx.png!), show them at that position.

  Step 7: Show comments (if any)

  Display comments with author and date.

  Step 8: List non-image attachments

  If there are non-image attachments (PDFs, Excel, etc.), list them with download info:
  Attachment: <filename> (<size>) — saved to /tmp/jira-<ISSUE_KEY>/<filename>
  Download these files too so the user can access them locally.

  To share: others need to place this file at `~/.claude/skills/jira/skill.md` and set the `JIRA_EMAIL` and `JIRA_API_TOKEN` env vars. They may also need to update the Atlassian base URL (`mosoteam.atlassian.net`) if their
  instance differs.

  ---

  # Mode B — Create a task (`/trung-jira create ...`, or whenever the user says "tạo task / tạo ticket")

  The task is read by non-technical BAs. Write it so a BA can understand and re-test it without reading code.

  ## Writing rules
  - **Short.** 8–15 lines total. No class names, methods, file paths, stack traces, table ids, mode strings.
  - **Plain English**, business words only: lender, program, rate, price, borrower, quote, ratesheet.
  - **Summary** ≤ 90 chars, prefixed by area: `[Pricing engine > <Lender>] ...`, `[Parser > <Lender>] ...`, `[Loans] ...`.
  - Numbers that matter go in the text (what moso showed vs. what it should show). Attach the user's screenshots.
  - Description in **wiki markup** (API v2), exactly these 4 sections:

  ```
  h3. What was reported
  <who saw what, where (share link / screen), 1–2 sentences, with the wrong vs. expected value>

  h3. Why
  <root cause in one or two business sentences — no code>

  h3. What changed
  * <behavior change 1, as the user will see it>
  * <behavior change 2>

  h3. How to check
  # <step a BA/QA can do on staging, with the expected result>
  # <a second scenario that must NOT change / must fall back>
  ```

  ## API steps (same auth as Mode A)
  1. Active sprint: `GET /rest/agile/1.0/board/2/sprint?state=active` → take the id (match by NAME, ids ≠ sprint numbers).
  2. Create: `POST /rest/api/2/issue` with `project.key=MOSO`, `issuetype.name=Task`, `summary`, `description`,
     `assignee.accountId=712020:c86c8eaf-7415-4e7d-8afe-59fd529b6fac` (Trung).
  3. Sprint: `POST /rest/agile/1.0/sprint/<id>/issue {"issues":["MOSO-XXXXX"]}`.
  4. Status: transition `Select for development` → `Start Progress` (re-fetch `/transitions` after each step) and **stop at
     In Progress**. Never move to Ready for Review / Done — the user reviews and closes.
  5. Screenshots the user pasted: `POST /rest/api/2/issue/<KEY>/attachments` with `-H "X-Atlassian-Token: no-check" -F file=@...`.
  6. Reply with the key + URL, and use the key in the commit subject (`MOSO-XXXXX: short subject`, one commit per task per repo).

  ## Example (MOSO-17134, 2026-09-03)
  Summary: `[Pricing engine > Mega Capital] Conventional quotes miss the better-priced MegaAgencyX table`
  What was reported: at 5.875% moso showed base price 1.338, the lender's ratesheet shows 1.213 — moso 0.125 worse.
  Why: the ratesheet has two Conventional tables; moso only read the standard "DU/LP Agency" one, never the MegaAgencyX one.
  What changed: eligible borrowers now see a row labeled MegaAgencyX with the better price; others keep the Agency price.
  How to check: open the share link on staging → MegaAgencyX / 1.213; switch to self-employed or 3+ properties → Agency price.
