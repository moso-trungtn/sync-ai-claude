---
name: fix-parser
description: Automated pipeline that pulls parser-failed Jira tasks, downloads new ratesheets, fixes tests, reviews code, commits, and updates Jira status. Usage: /fix-parser [@assigneeId]
argument-hint: "[@assigneeId] (optional, defaults to Trung Thach)"
allowed-tools: Bash, Read, Write, Edit, Glob, Grep, Agent, mcp__claude_ai_Atlassian__searchJiraIssuesUsingJql, mcp__claude_ai_Atlassian__getJiraIssue, mcp__claude_ai_Atlassian__editJiraIssue, mcp__claude_ai_Atlassian__getTransitionsForJiraIssue, mcp__claude_ai_Atlassian__transitionJiraIssue
---

# Fix Parser Pipeline

You are the **orchestrator** for an automated pipeline that fixes parser-failed lenders from Jira.

Pipeline flow: **Query Jira → Download → Test → Fix → Test → Commit**

---

## Environment & Constants

```
CLOUD_ID = "5858106a-50e6-442e-a751-14c0f4243e87"
DEFAULT_ASSIGNEE = "712020:c86c8eaf-7415-4e7d-8afe-59fd529b6fac"
PROJECT_ROOT = "/Users/trungthach/IdeaProjects"
MOSO_PRICING = "/Users/trungthach/IdeaProjects/moso-pricing"
PACKS_LOAN = "/Users/trungthach/IdeaProjects/packs/loan"
MOSO_MEMORY_DIR = "/Users/trungthach/.claude/projects/-Users-trungthach-IdeaProjects/memory"
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

## STEP 0 — Environment Check & Memory Load

### 0.1 Environment Verification

```bash
echo "JIRA_EMAIL=${JIRA_EMAIL:-MISSING} | JIRA_TOKEN=${JIRA_API_TOKEN:-MISSING}"
```

**If any value is `MISSING` → stop immediately:**
```
/fix-parser: Environment not configured.
Set JIRA_EMAIL and JIRA_API_TOKEN in ~/.claude/settings.json env vars.
```

### 0.2 Parse Arguments

If `$ARGUMENTS` contains an `@`-prefixed string, extract it as the assignee ID.
Otherwise use `DEFAULT_ASSIGNEE`.

```
Examples:
  /fix-parser                          → assignee = DEFAULT_ASSIGNEE
  /fix-parser @712020:abc123           → assignee = "712020:abc123"
```

### 0.3 Memory Load

**Output:**
```
[fix-parser 0/5] Loading project memories...
```

Read memory files in parallel:
```
$MOSO_MEMORY_DIR/project_structure.md
$MOSO_MEMORY_DIR/infrastructure_index.md
```

**If either file is missing** → fall back to `lender-info.sh` for lookups (legacy mode). Log:
```
[fix-parser 0/5] ⚠ Memories not found — using legacy lookup mode
```

**If both files exist** → memory is your architectural map. Log:
```
[fix-parser 0/5] ✓ Memories loaded — memory-first mode active
```

### Memory-First Rule (enforced from here on)

When memory is loaded, you MUST follow this lookup order for every class/file:

```
1. infrastructure_index.md  ← check here first, every time
2. project_structure.md     ← module/package layout if index has no match
3. targeted find -name      ← only if NOT found in memory (single module)
4. lender-info.sh           ← last resort fallback
```

**NEVER skip to step 3 or 4 without exhausting steps 1 and 2 first.**
**NEVER run broad `find` or `grep -r` across the whole workspace.**

---

## STEP 1 — Query Jira for Parser-Failed Tasks

**Output:**
```
[fix-parser 1/5] Querying Jira for parser-failed tasks...
```

Use the Jira MCP tool to search:

```
JQL: project = MOSO AND assignee = "<ASSIGNEE_ID>" AND status = "Backlog" AND summary ~ "[Parser failed]" ORDER BY created DESC
Fields: summary, status, issuetype, priority, assignee
Cloud ID: CLOUD_ID
```

If no results found, also try with `status = "To Do"` as a fallback.

If still no results, tell the user:
> No parser-failed tasks found for this assignee. Nothing to fix.

---

## STEP 2 — Show Task List and Get Confirmation

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

---

## STEP 3 — Build moso-pricing JAR (once)

**Output:**
```
[fix-parser 2/5] Building moso-pricing JAR...
```

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

---

## STEP 4 — Process Each Task

Initialize tracking:
```
fixed_tasks = []
skipped_tasks = []
lender_context = {}  # cache resolved paths per lender — no re-reads
```

**FOR EACH selected task, execute steps 4a through 4m:**

### Step 4a: Parse Lender Name & Resolve Paths (Memory-First)

Title pattern: `[Parser failed] {Lender Name} [NonQM/non-QM/NON QM]: {MM/DD/YYYY}`

Extract:
- **Raw lender name**: text between `]` and `:` (strip NonQM/non-QM/NON QM suffix)
- **Is NonQM**: true if title contains "NonQM", "non-QM", "NON QM", or "Non QM" (case-insensitive)
- **Fail date**: the date at the end

**Resolve parser file paths (memory-first):**

1. **Check `infrastructure_index.md`** for the lender name → get Tables, RateParser, AdjustmentParser paths directly
2. **If not in index**, check `project_structure.md` for the lender's package location
3. **If not in memory**, fall back to:
   ```bash
   cd /Users/trungthach/IdeaProjects/packs/loan
   ./lender-info.sh <RawLenderName> 2>/dev/null | head -10
   ```

**Cache the resolved paths** in `lender_context` so you never search again:
```
lender_context[<LENDER>] = {
  camelName: "PennyMac",
  tablesPath: "<path>/PennyMacTables.java",
  rateParserPath: "<path>/PennyMacRateParser.java",
  adjParserPath: "<path>/PennyMacAdjustmentParser.java",
  isNonQM: true/false
}
```

Emit:
```bash
source /Users/trungthach/IdeaProjects/tools/agent-dashboard/emit.sh
emit_meta "<JIRA_KEY>" "<LENDER_NAME>" "fix-parser"
emit_agent_step "fix-parser" "Processing <LENDER_NAME> (<JIRA_KEY>)"
```

### Step 4b: Transition Jira to "In Progress"

The Jira workflow requires TWO transitions to reach "In Progress":
1. **Backlog → New**: transition name "Select for development" (id varies)
2. **New → In Progress**: transition name "Start Progress" (id varies)

For each transition, get available transitions first, then apply:

```
# First: Backlog → New
Tool: getTransitionsForJiraIssue
  cloudId: CLOUD_ID
  issueIdOrKey: <JIRA_KEY>

Find transition with name "Select for development" or containing "development". Apply it.

Tool: transitionJiraIssue
  cloudId: CLOUD_ID
  issueIdOrKey: <JIRA_KEY>
  transition: { id: "<SELECT_FOR_DEV_ID>" }

# Second: New → In Progress
Tool: getTransitionsForJiraIssue
  cloudId: CLOUD_ID
  issueIdOrKey: <JIRA_KEY>

Find transition with name "Start Progress" or containing "Progress". Apply it.

Tool: transitionJiraIssue
  cloudId: CLOUD_ID
  issueIdOrKey: <JIRA_KEY>
  transition: { id: "<START_PROGRESS_ID>" }
```

**IMPORTANT:** After the pipeline completes, leave tasks at "In Progress" status. Do NOT transition to "Done" — the user will review and close tasks themselves.

### Step 4c: Download New Ratesheet

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

### Step 4d: Update inputStream in Test Files to New Ratesheet

**CRITICAL STEP — do NOT skip.** After downloading the new ratesheet, `download-ratesheet.sh` adds a new constant to `RatesheetFiles.java` (e.g., `DARTBANK_20260327`) but does **NOT** update the test files. The tests still reference the OLD constant.

You MUST update the `inputStream` / `mergedInputStream` reference in BOTH test files:

1. **AdjustmentParsersTest.java** — find the test method for this lender, find `RatesheetFiles.<OLD_CONSTANT>`, replace with `RatesheetFiles.<NEW_CONSTANT>`
2. **RateParserTest.java** — same: find the test method, replace the old `RatesheetFiles` constant with the new one

```bash
# Step 1: Find what constant the tests currently use
cd /Users/trungthach/IdeaProjects/packs/loan
grep -n "RatesheetFiles.*<LENDER>" src/test/java/com/mvu/loan/AdjustmentParsersTest.java
grep -n "RatesheetFiles.*<LENDER>" src/test/java/com/mvu/loan/RateParserTest.java

# Step 2: Find what NEW constant was added by download-ratesheet.sh
grep "<LENDER_UPPER>_2026" src/test/java/com/mvu/loan/RatesheetFiles.java | tail -1
```

Use the Edit tool to replace the old constant with the new one in BOTH files. Example:
```
Old: final InputStream inputStream = RateParserTest.class.getResourceAsStream(RatesheetFiles.DARTBANK_20260312);
New: final InputStream inputStream = RateParserTest.class.getResourceAsStream(RatesheetFiles.DARTBANK_20260327);
```

**WHY:** If you skip this step, the tests will run against the OLD ratesheet and either pass incorrectly (masking real failures) or be meaningless.

### Step 4e: Run Tests — First Pass (Detect Failures)

**Output:**
```
[fix-parser 3/5] Testing <LENDER_NAME> (first pass)...
```

Now that the test files reference the new ratesheet constant, run tests WITHOUT the `--ratesheet` flag:

```bash
cd /Users/trungthach/IdeaProjects/packs/loan
./parser-fix.sh <LENDER_NAME> --both 2>&1 | tail -5
cat /tmp/parser-fix/<lender_lowercase>/report.txt
```

Note the test results. This first pass will likely show expectation mismatches (`.txt` files need updating) or parser errors if the ratesheet format changed.

### Step 4f: Accept Expectations

Accept adjustment expectations:
```bash
cd /Users/trungthach/IdeaProjects/packs/loan
mvn test -Dtest=AdjustmentParsersTest#test<LenderName> -Daccept -Daccept.new.adj 2>&1 | tail -20
```

This regenerates the `.txt` expectation files to match the new ratesheet.

### Step 4g: Re-run Tests (Verify After Accept)

```bash
cd /Users/trungthach/IdeaProjects/packs/loan
./parser-fix.sh <LENDER_NAME> --both 2>&1 | tail -5
cat /tmp/parser-fix/<lender_lowercase>/report.txt
```

Emit:
```bash
source /Users/trungthach/IdeaProjects/tools/agent-dashboard/emit.sh
emit_agent_test "fix-parser" "AdjParser <LENDER>" "<PASS|FAIL>" "<details>"
emit_agent_test "fix-parser" "RateParser <LENDER>" "<PASS|FAIL>" "<details>"
```

### Step 4h: Handle Test Results — Beads Fix Loop

**If BOTH tests PASS → skip to Step 4i (verification test).**

**If tests FAIL (code error, not just expectation mismatch):**

**Output:**
```
[fix-parser 3/5] Tests failed — analyzing root cause with beads decomposition...
```

Enter retry loop (max 3 attempts):

```
for attempt in 1..3:

    1. READ the error report:
       cat /tmp/parser-fix/<lender_lowercase>/report.txt

    2. ANALYZE root cause using memory — identify exactly which file(s) need fixing:
       - Check lender_context for cached paths (Tables, RateParser, AdjParser)
       - Map error type to the right file:
         | Error Type               | Target File              |
         |--------------------------|--------------------------|
         | CRAWL_MISMATCH           | AdjustmentParser         |
         | VALUE_MISMATCH           | Tables (wrong ranges)    |
         | field_N conflict         | Tables (duplicate field)  |
         | NullPointerException     | Read the stack trace      |
         | Missing mode             | Tables (getModeResolver)  |
         | Sheet not found          | RateParser (sheet name)   |
         | Rate count mismatch      | RateParser (products)     |

    3. DECOMPOSE into ordered beads:
       Write a quick fix plan (in context, not to file):

       ## Fix Beads for <LENDER> (attempt <N>)

       ### Bead 1: <target file> — <specific change>
       - File: <exact path from lender_context>
       - Root cause: <from error analysis>
       - Fix: <specific code change needed>

       ### Bead 2: <target file if needed> — <specific change>
       - File: <exact path>
       - Fix: <specific code change>

    4. SPAWN parser-dev agent (foreground) with beads:
       subagent_type: "parser-dev"
       Prompt: """
       Fix the parser test failure for <LENDER_NAME>.

       ## Memory-Resolved File Paths (do NOT search — use these directly)
       - Tables: <tablesPath from lender_context>
       - RateParser: <rateParserPath from lender_context>
       - AdjParser: <adjParserPath from lender_context>

       ## Error Report
       <PASTE REPORT CONTENTS>

       ## Fix Beads (implement in this order)

       ### Bead 1: <file> — <change>
       <specific fix instructions>

       ### Bead 2: <file> — <change> (if applicable)
       <specific fix instructions>

       ## Rules
       - Do NOT search for files — paths are provided above
       - Do NOT read files not listed above unless absolutely necessary
       - Implement beads in order
       - Rebuild after fixes:
         cd /Users/trungthach/IdeaProjects/moso-pricing && mvn install -DskipTests -Pjar-packaging -Dgwt.compiler.skip=true
       - Do NOT run tests — just fix and rebuild
       """

    5. After Dev Agent returns, accept expectations again:
       cd /Users/trungthach/IdeaProjects/packs/loan
       mvn test -Dtest=AdjustmentParsersTest#test<LenderName> -Daccept -Daccept.new.adj 2>&1 | tail -20

    6. Re-run tests:
       ./parser-fix.sh <LENDER_NAME> --both 2>&1 | tail -5
       cat /tmp/parser-fix/<lender_lowercase>/report.txt

    7. If PASS → break loop, continue to Step 4i
       If FAIL → continue loop (new beads analysis on next iteration)

    Emit per retry:
    source /Users/trungthach/IdeaProjects/tools/agent-dashboard/emit.sh
    emit_pipeline_retry <attempt>
```

**If still failing after 3 attempts:**
```
skipped_tasks.append({ key: <JIRA_KEY>, lender: <LENDER>, reason: "Code fix failed after 3 attempts. Error: <summary>" })
```

Write failure report:
```bash
mkdir -p /tmp/fix-parser/<lender_lowercase>
cat > /tmp/fix-parser/<lender_lowercase>/fix_report.md << 'REPORT'
# Fix Report: <LENDER> (<JIRA_KEY>) — FAILED

## Error Summary
<root cause analysis from last attempt>

## Beads Attempted
<list of beads tried across all attempts>

## Files Modified
<list of files changed>

## Remaining Issue
<what still fails and why>
REPORT
```

Transition Jira back to "Backlog" (find the Backlog transition ID and apply it).
Continue to next task.

### Step 4i: Verification Test (MUST PASS before commit)

**Output:**
```
[fix-parser 4/5] Verification test for <LENDER_NAME>...
```

Run BOTH tests together to confirm no interference:
```bash
cd /Users/trungthach/IdeaProjects/packs/loan
mvn test -Dtest="AdjustmentParsersTest#test<LenderName>+RateParserTest#test<LenderName>" 2>&1 | tail -20
```

**If verification FAILS:**
- Do NOT commit
- Go back to Step 4h retry loop (counts as a new attempt)

**If verification PASSES:**
- Continue to Step 4j

Emit:
```bash
source /Users/trungthach/IdeaProjects/tools/agent-dashboard/emit.sh
emit_agent_test "fix-parser" "Verification <LENDER>" "PASS" "Both tests pass together"
```

### Step 4j: Code Review

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

### Step 4k: Copy Ratesheet and Update Resources

The `download-ratesheet.sh` script already handles copying to test resources and updating `RatesheetFiles.java`. Verify the ratesheet file exists in resources:

```bash
ls /Users/trungthach/IdeaProjects/packs/loan/src/test/resources/ratesheets/ | grep -i <lender> | tail -3
```

If the ratesheet wasn't auto-copied by the download script, copy manually:
```bash
cp <DOWNLOADED_PATH> /Users/trungthach/IdeaProjects/packs/loan/src/test/resources/ratesheets/
```

### Step 4l: Git Commit

**Output:**
```
[fix-parser 5/5] Committing <LENDER_NAME>...
```

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

Write success report:
```bash
mkdir -p /tmp/fix-parser/<lender_lowercase>
cat > /tmp/fix-parser/<lender_lowercase>/fix_report.md << 'REPORT'
# Fix Report: <LENDER> (<JIRA_KEY>) — SUCCESS

## Changes
- Ratesheet updated to <DATE>
- Expectations regenerated
- <code fixes if any>

## Files Modified
<list from git diff --cached --stat>

## Test Results
- AdjustmentParsersTest: PASS
- RateParserTest: PASS
- Verification (both): PASS
REPORT
```

Emit:
```bash
source /Users/trungthach/IdeaProjects/tools/agent-dashboard/emit.sh
emit_agent_step "fix-parser" "Committed <JIRA_KEY>"
```

### Step 4m: Mark Task as Fixed (leave at "In Progress")

**Do NOT transition to "Done".** Leave the task at "In Progress" so the user can review and close it themselves.

Add to fixed list:
```
fixed_tasks.append({ key: <JIRA_KEY>, lender: <LENDER> })
```

Emit:
```bash
source /Users/trungthach/IdeaProjects/tools/agent-dashboard/emit.sh
emit_agent_step "fix-parser" "Fixed <JIRA_KEY> — left at In Progress for review"
```

**→ Continue to next task**

---

## STEP 5 — Summary Report

After all tasks are processed, emit pipeline done and present the summary:

```bash
source /Users/trungthach/IdeaProjects/tools/agent-dashboard/emit.sh
emit_pipeline_done
```

```
## Fix Parser Pipeline — Complete

### Fixed (N tasks)
| Key | Lender | Commit | Fix Type |
|-----|--------|--------|----------|
| MOSO-15944 | BrokerFirstFunding (NonQM) | abc1234 | expectations only |
| MOSO-15943 | LoganFinance (NonQM) | def5678 | code fix (2 beads) |
...

### Skipped (M tasks)
| Key | Lender | Reason |
|-----|--------|--------|
| MOSO-15941 | ADMortgage | Code fix failed after 3 attempts |
...

### Review Warnings (if any)
<Any code review warnings logged during the pipeline>

### Fix Reports
Reports saved at: /tmp/fix-parser/<lender>/fix_report.md

Total: N fixed, M skipped
```

---

## Optimization Rules (Always Enforced)

1. **Memory-First**: Always check `infrastructure_index.md` before searching. Never run broad `find` or `grep -r` across the workspace when memory has the answer.

2. **No Re-reads**: Once a lender's Tables/RateParser/AdjParser paths are resolved and cached in `lender_context`, never search for them again. Files read in Step 4a stay in context — do not re-read in Step 4h.

3. **Beads over Blob**: When spawning parser-dev for fixes, decompose the error into ordered beads with exact file paths. Never send a vague "fix this error" prompt.

4. **Verify Before Commit**: Always run the verification test (Step 4i) after fixes pass. The flow is: Test → Fix → Test → Commit. Never commit without the second test pass.

5. **Targeted Dev Agent**: Always pass memory-resolved file paths to the parser-dev agent with "do NOT search" instruction. This saves 30-50% of agent tokens.

6. **Error-to-File Mapping**: Use the error type table in Step 4h to map errors directly to the right parser file. Don't let the dev agent guess which file to fix.

7. **Cache Everything**: Lender paths, ratesheet constants, test method names — cache on first lookup, reuse for all subsequent steps.
