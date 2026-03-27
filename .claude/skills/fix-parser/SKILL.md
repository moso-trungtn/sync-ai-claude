---
name: fix-parser
description: Automated pipeline that pulls parser-failed Jira tasks, downloads new ratesheets, fixes tests, reviews code, commits, and updates Jira status. Usage: /fix-parser [@assigneeId]
argument-hint: "[@assigneeId] (optional, defaults to Trung Thach)"
allowed-tools: Bash, Read, Write, Edit, Glob, Grep, Agent, mcp__claude_ai_Atlassian__searchJiraIssuesUsingJql, mcp__claude_ai_Atlassian__getJiraIssue, mcp__claude_ai_Atlassian__editJiraIssue, mcp__claude_ai_Atlassian__getTransitionsForJiraIssue, mcp__claude_ai_Atlassian__transitionJiraIssue
---

# Fix Parser Pipeline

You are the **orchestrator** for an automated pipeline that fixes parser-failed lenders from Jira.

## Constants

```
CLOUD_ID = "5858106a-50e6-442e-a751-14c0f4243e87"
DEFAULT_ASSIGNEE = "712020:c86c8eaf-7415-4e7d-8afe-59fd529b6fac"
PROJECT_ROOT = "/Users/trungthach/IdeaProjects"
MOSO_PRICING = "/Users/trungthach/IdeaProjects/moso-pricing"
PACKS_LOAN = "/Users/trungthach/IdeaProjects/packs/loan"
```

---

## DASHBOARD INTEGRATION

Source the emit helper at the start and emit status events throughout:

```bash
source /Users/trungthach/IdeaProjects/tools/agent-dashboard/emit.sh
emit_reset
emit_pipeline_start "fix-parser"
```

---

## PIPELINE STEPS

### Step 0: Parse Arguments

If `$ARGUMENTS` contains an `@`-prefixed string, extract it as the assignee ID.
Otherwise use `DEFAULT_ASSIGNEE`.

```
Examples:
  /fix-parser                          → assignee = DEFAULT_ASSIGNEE
  /fix-parser @712020:abc123           → assignee = "712020:abc123"
```

### Step 1: Query Jira for Parser-Failed Tasks

Use the Jira MCP tool to search:

```
JQL: project = MOSO AND assignee = "<ASSIGNEE_ID>" AND status = "Backlog" AND summary ~ "[Parser failed]" ORDER BY created DESC
Fields: summary, status, issuetype, priority, assignee
Cloud ID: CLOUD_ID
```

If no results found, also try with `status = "To Do"` as a fallback.

If still no results, tell the user:
> No parser-failed tasks found for this assignee. Nothing to fix.

### Step 2: Show Task List and Get Confirmation

Present the tasks in a table:

```
## Parser-Failed Tasks Found: N

| # | Key | Lender | Date | Priority |
|---|-----|--------|------|----------|
| 1 | MOSO-15944 | Broker First Funding NON QM | 03/24/2026 | Medium |
| 2 | MOSO-15943 | Logan Finance Non QM | 03/24/2026 | Medium |
...

Fix all tasks? Or specify which ones (e.g., "1,3,5" or "all")
```

Wait for user response. Parse their selection.

### Step 3: Build moso-pricing JAR (once)

```bash
cd /Users/trungthach/IdeaProjects/moso-pricing
mvn install -DskipTests -Pjar-packaging -Dgwt.compiler.skip=true 2>&1 | tail -20
```

Verify `BUILD SUCCESS` in output. If build fails, stop and report the error.

Emit:
```bash
source /Users/trungthach/IdeaProjects/tools/agent-dashboard/emit.sh
emit_agent_step "fix-parser" "Built moso-pricing JAR"
```

### Step 4: Process Each Task

Initialize tracking:
```
fixed_tasks = []
skipped_tasks = []
```

**FOR EACH selected task, execute steps 4a through 4k:**

#### Step 4a: Parse Lender Name from Title

Title pattern: `[Parser failed] {Lender Name} [NonQM/non-QM/NON QM]: {MM/DD/YYYY}`

Extract:
- **Raw lender name**: text between `]` and `:` (strip NonQM/non-QM/NON QM suffix)
- **Is NonQM**: true if title contains "NonQM", "non-QM", "NON QM", or "Non QM" (case-insensitive)
- **Fail date**: the date at the end

Then resolve the exact codebase lender name:
```bash
cd /Users/trungthach/IdeaProjects/packs/loan
./lender-info.sh <RawLenderName> 2>/dev/null | head -5
```

This returns the CamelCase lender name used in test methods and parser classes. If lender-info.sh returns nothing, try variations (remove spaces, try partial match with `./lender-info.sh --list | grep -i <partial>`).

Emit:
```bash
source /Users/trungthach/IdeaProjects/tools/agent-dashboard/emit.sh
emit_meta "<JIRA_KEY>" "<LENDER_NAME>" "fix-parser"
emit_agent_step "fix-parser" "Processing <LENDER_NAME> (<JIRA_KEY>)"
```

#### Step 4b: Transition Jira to "In Progress"

First get available transitions:
```
Tool: getTransitionsForJiraIssue
  cloudId: CLOUD_ID
  issueIdOrKey: <JIRA_KEY>
```

Find the transition with name containing "Progress" (case-insensitive). Then transition:
```
Tool: transitionJiraIssue
  cloudId: CLOUD_ID
  issueIdOrKey: <JIRA_KEY>
  transition: { id: "<TRANSITION_ID>" }
```

#### Step 4c: Download New Ratesheet

```bash
cd /Users/trungthach/IdeaProjects/packs/loan
./download-ratesheet.sh <LENDER_NAME> 2>&1
```

If the lender is NonQM, add `--nonqm`:
```bash
./download-ratesheet.sh <LENDER_NAME> --nonqm 2>&1
```

**Capture the downloaded file path** from the output. The script prints the path of the downloaded file. Look for lines containing the ratesheet path (usually ends with `.xlsx`, `.xlsm`, `.pdf`, `.csv`).

If download fails (no file found in GCS), skip this lender:
```
skipped_tasks.append({ key: <JIRA_KEY>, lender: <LENDER>, reason: "Download failed — no ratesheet in GCS" })
```
Continue to next task.

Emit:
```bash
source /Users/trungthach/IdeaProjects/tools/agent-dashboard/emit.sh
emit_agent_step "fix-parser" "Downloaded ratesheet for <LENDER_NAME>"
```

#### Step 4d: Run Tests (First Pass)

```bash
cd /Users/trungthach/IdeaProjects/packs/loan
./parser-fix.sh <LENDER_NAME> --both --ratesheet <DOWNLOADED_PATH> 2>&1 | tail -5
cat /tmp/parser-fix/<lender_lowercase>/report.txt
```

Note the test results. This first pass will likely show expectation mismatches (`.txt` files need updating).

#### Step 4e: Accept Expectations

Accept adjustment expectations:
```bash
cd /Users/trungthach/IdeaProjects/packs/loan
mvn test -Dtest=AdjustmentParsersTest#test<LenderName> -Dratesheet.path=<DOWNLOADED_PATH> -Daccept -Daccept.new.adj 2>&1 | tail -20
```

This regenerates the `.txt` expectation files to match the new ratesheet.

#### Step 4f: Re-run Tests (Verify Pass)

```bash
cd /Users/trungthach/IdeaProjects/packs/loan
./parser-fix.sh <LENDER_NAME> --both --ratesheet <DOWNLOADED_PATH> 2>&1 | tail -5
cat /tmp/parser-fix/<lender_lowercase>/report.txt
```

Emit:
```bash
source /Users/trungthach/IdeaProjects/tools/agent-dashboard/emit.sh
emit_agent_test "fix-parser" "AdjParser <LENDER>" "<PASS|FAIL>" "<details>"
emit_agent_test "fix-parser" "RateParser <LENDER>" "<PASS|FAIL>" "<details>"
```

#### Step 4g: Handle Test Results

**If BOTH tests PASS → continue to Step 4h.**

**If tests FAIL (code error, not just expectation mismatch):**

Enter retry loop (max 3 attempts):

```
for attempt in 1..3:
    1. Read the error report:
       cat /tmp/parser-fix/<lender_lowercase>/report.txt

    2. Spawn parser-dev agent (foreground):
       Prompt: """
       Fix the parser test failure for <LENDER_NAME>.

       ## Error Report
       <PASTE REPORT CONTENTS>

       ## Ratesheet Path
       <DOWNLOADED_PATH>

       ## Instructions
       1. Read the error report and identify the root cause
       2. Fix the parser code in moso-pricing
       3. Rebuild: cd /Users/trungthach/IdeaProjects/moso-pricing && mvn install -DskipTests -Pjar-packaging -Dgwt.compiler.skip=true
       4. Do NOT run tests — just fix and rebuild
       """

    3. After Dev Agent returns, accept expectations again:
       cd /Users/trungthach/IdeaProjects/packs/loan
       mvn test -Dtest=AdjustmentParsersTest#test<LenderName> -Dratesheet.path=<DOWNLOADED_PATH> -Daccept -Daccept.new.adj 2>&1 | tail -20

    4. Re-run tests:
       ./parser-fix.sh <LENDER_NAME> --both --ratesheet <DOWNLOADED_PATH> 2>&1 | tail -5
       cat /tmp/parser-fix/<lender_lowercase>/report.txt

    5. If PASS → break loop, continue to Step 4h
       If FAIL → continue loop

    Emit per retry:
    source /Users/trungthach/IdeaProjects/tools/agent-dashboard/emit.sh
    emit_pipeline_retry <attempt>
```

**If still failing after 3 attempts:**
```
skipped_tasks.append({ key: <JIRA_KEY>, lender: <LENDER>, reason: "Code fix failed after 3 attempts. Error: <summary>" })
```

Transition Jira back to "Backlog" (find the Backlog transition ID and apply it).
Continue to next task.

#### Step 4h: Code Review

Spawn the `code-reviewer` agent (foreground):

```
subagent_type: "code-reviewer"
Prompt: "Review the current git diff in /Users/trungthach/IdeaProjects for the <LENDER_NAME> parser fix. Focus on moso-pricing and packs/loan changes."
```

Emit:
```bash
source /Users/trungthach/IdeaProjects/tools/agent-dashboard/emit.sh
emit_agent_step "fix-parser" "Code review for <LENDER_NAME>"
```

**If review verdict is NEEDS FIXES:**
- Log the warnings in the summary (don't block — parser-failed fixes are routine)
- Show the review report to the user as an info message

**If review verdict is PASS:**
- Continue silently

#### Step 4i: Copy Ratesheet and Update Resources

The `download-ratesheet.sh` script already handles copying to test resources and updating `RatesheetFiles.java`. Verify the ratesheet file exists in resources:

```bash
ls /Users/trungthach/IdeaProjects/packs/loan/src/test/resources/ratesheets/ | grep -i <lender> | tail -3
```

If the ratesheet wasn't auto-copied by the download script, copy manually:
```bash
cp <DOWNLOADED_PATH> /Users/trungthach/IdeaProjects/packs/loan/src/test/resources/ratesheets/
```

#### Step 4j: Git Commit

```bash
cd /Users/trungthach/IdeaProjects

# Stage all changes for this lender
git add packs/loan/src/test/resources/adj-expectations/
git add packs/loan/src/test/resources/ratesheets/
git add packs/loan/src/test/resources/expected-new-adj/
git add packs/loan/src/test/java/
git add moso-pricing/

# Check if there's anything to commit
git diff --cached --stat
```

Only commit if there are staged changes:

```bash
git commit -m "$(cat <<'EOF'
MOSO-<XXXX>: fix <LenderName> parser

Updated expectations for new ratesheet dated <DATE>.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

Emit:
```bash
source /Users/trungthach/IdeaProjects/tools/agent-dashboard/emit.sh
emit_agent_step "fix-parser" "Committed <JIRA_KEY>"
```

#### Step 4k: Transition Jira to "Done"

Get available transitions:
```
Tool: getTransitionsForJiraIssue
  cloudId: CLOUD_ID
  issueIdOrKey: <JIRA_KEY>
```

Find the transition with name containing "Done" (case-insensitive). Then transition:
```
Tool: transitionJiraIssue
  cloudId: CLOUD_ID
  issueIdOrKey: <JIRA_KEY>
  transition: { id: "<TRANSITION_ID>" }
```

Add to fixed list:
```
fixed_tasks.append({ key: <JIRA_KEY>, lender: <LENDER> })
```

Emit:
```bash
source /Users/trungthach/IdeaProjects/tools/agent-dashboard/emit.sh
emit_agent_step "fix-parser" "Completed <JIRA_KEY>"
```

**→ Continue to next task**

### Step 5: Summary Report

After all tasks are processed, emit pipeline done and present the summary:

```bash
source /Users/trungthach/IdeaProjects/tools/agent-dashboard/emit.sh
emit_pipeline_done
```

```
## Fix Parser Pipeline — Complete

### Fixed (N tasks)
| Key | Lender | Commit |
|-----|--------|--------|
| MOSO-15944 | BrokerFirstFunding (NonQM) | abc1234 |
| MOSO-15943 | LoganFinance (NonQM) | def5678 |
...

### Skipped (M tasks)
| Key | Lender | Reason |
|-----|--------|--------|
| MOSO-15941 | ADMortgage | Code fix failed after 3 attempts |
...

### Review Warnings (if any)
<Any code review warnings logged during the pipeline>

Total: N fixed, M skipped
```
