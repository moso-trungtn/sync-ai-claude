---                                                                                                                                                                                                                              
  name: jira                                                                                                                                                                                                                       
  description: Fetch and display a Jira issue with all images                                                                                                                                                                      
  disable-model-invocation: true                                                                                                                                                                                                   
  argument-hint: <ISSUE_KEY or URL>                               
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
