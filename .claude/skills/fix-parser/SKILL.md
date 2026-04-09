---
name: fix-parser
description: Smart automated pipeline that fixes parser-failed lenders from Jira. Learns from past fixes, classifies errors into tiers (auto-fix vs agent-fix), and gets smarter over time. Usage: /fix-parser [@assigneeId]
argument-hint: "[@assigneeId] (optional, defaults to Trung Thach)"
allowed-tools: Bash, Read, Write, Edit, Glob, Grep, Agent, mcp__claude_ai_Atlassian__searchJiraIssuesUsingJql, mcp__claude_ai_Atlassian__getJiraIssue, mcp__claude_ai_Atlassian__editJiraIssue, mcp__claude_ai_Atlassian__getTransitionsForJiraIssue, mcp__claude_ai_Atlassian__transitionJiraIssue
---

# Fix Parser Pipeline — Smart Agent

You are a **smart orchestrator** that fixes parser-failed lenders. You learn from every fix, classify errors by complexity, and take the cheapest path that works.

Pipeline flow: **Memory + Cookbook → Jira → Download → Classify → (Tier 0 auto-fix | Tier 1 guided | Tier 2 full agent) → Verify → Learn**

**NO AUTO-COMMIT.** After all lenders are fixed and verified, leave changes staged but uncommitted. The user decides when and how to commit.

---

## Environment & Constants

```
CLOUD_ID = "5858106a-50e6-442e-a751-14c0f4243e87"
DEFAULT_ASSIGNEE = "712020:c86c8eaf-7415-4e7d-8afe-59fd529b6fac"
PROJECT_ROOT = "/Users/trungthach/IdeaProjects"
MOSO_PRICING = "/Users/trungthach/IdeaProjects/moso-pricing"
PACKS_LOAN = "/Users/trungthach/IdeaProjects/packs/loan"
MOSO_MEMORY_DIR = "/Users/trungthach/.claude/projects/-Users-trungthach-IdeaProjects/memory"
COOKBOOK_FILE = "/Users/trungthach/.claude/projects/-Users-trungthach-IdeaProjects/memory/parser_fix_cookbook.md"
```

---

## DASHBOARD INTEGRATION

```bash
source /Users/trungthach/IdeaProjects/tools/agent-dashboard/emit.sh
```

| When | Command |
|------|---------|
| Skill starts | `emit_reset && emit_pipeline_start "fix-parser"` |
| Memory/cookbook loaded | `emit_agent_step "fix-parser" "Memory loaded, cookbook: N lenders"` |
| Per lender start | `emit_meta "<KEY>" "<LENDER>" "fix-parser"` |
| Tier classified | `emit_agent_step "fix-parser" "<LENDER>: Tier N — <reason>"` |
| Tier 0 auto-fix | `emit_agent_step "fix-parser" "<LENDER>: auto-fix (no agent needed)"` |
| Tier 1/2 agent spawn | `emit_agent_start "parser-dev" "Fixing <LENDER>"` |
| Test result | `emit_agent_test "fix-parser" "<test>" "<PASS/FAIL>" "<details>"` |
| Verify pass | `emit_agent_test "fix-parser" "Verify <LENDER>" "PASS" "Both pass"` |
| Cookbook updated | `emit_agent_step "fix-parser" "Cookbook updated: <LENDER>"` |
| Staged | `emit_agent_step "fix-parser" "Staged <KEY>"` |
| Retry | `emit_pipeline_retry N` |
| Done | `emit_pipeline_done` |

---

## STEP 0 — Environment Check, Memory & Cookbook Load

### 0.1 Environment Verification

```bash
source /Users/trungthach/IdeaProjects/tools/agent-dashboard/emit.sh && emit_reset
emit_pipeline_start "fix-parser"
echo "JIRA_EMAIL=${JIRA_EMAIL:-MISSING} | JIRA_TOKEN=${JIRA_API_TOKEN:-MISSING}"
```

**If any value is `MISSING` → stop immediately.**

### 0.2 Parse Arguments

If `$ARGUMENTS` contains an `@`-prefixed string, extract it as the assignee ID.
Otherwise use `DEFAULT_ASSIGNEE`.

### 0.3 Memory Load

**Output:**
```
[fix-parser 0/5] Loading memories and cookbook...
```

Read in parallel:
```
$MOSO_MEMORY_DIR/project_structure.md
$MOSO_MEMORY_DIR/infrastructure_index.md
$COOKBOOK_FILE
```

**If memory files missing** → legacy mode (lender-info.sh fallback).
**If cookbook missing** → create empty cookbook (first run).

```bash
source /Users/trungthach/IdeaProjects/tools/agent-dashboard/emit.sh
emit_agent_step "fix-parser" "Memory loaded, cookbook: <N> lenders tracked"
```

### Memory-First Rule (enforced from here on)

```
1. infrastructure_index.md  ← check here first
2. project_structure.md     ← module/package layout
3. cookbook (lender section)  ← past fix history, cached paths
4. targeted find -name      ← only if NOT in memory
5. lender-info.sh           ← last resort
```

**NEVER run broad `find` or `grep -r` across the workspace.**

---

## COOKBOOK FORMAT

The cookbook is a markdown file that grows after every fix. It stores per-lender intelligence:

```markdown
# Parser Fix Cookbook

## PennyMac
- **paths**: Tables=`<path>`, Rate=`<path>`, Adj=`<path>`
- **tier_history**: [0, 0, 0, 1, 0, 0, 0, 0, 0, 0] (last 10)
- **tier_0_streak**: 6
- **last_fix**: 2026-03-31
- **last_error**: expectation mismatch
- **last_tier1_fix**: CRAWL_MISMATCH on field_8 → updated section keyword "FICO Score" → "Credit Score" (2026-03-15)
- **notes**: NonQM lender, usually just expectation updates

## LoganFinance
- **paths**: Tables=`<path>`, Rate=`<path>`, Adj=`<path>`
- **tier_history**: [0, 1, 0, 0, 0]
- **tier_0_streak**: 3
- **last_fix**: 2026-03-28
- **last_error**: expectation mismatch
- **last_tier1_fix**: VALUE_MISMATCH on FICO table → row ranges changed from 640-659 to 620-639 (2026-03-10)
- **notes**: —
```

---

## ERROR TIER CLASSIFICATION

**This is the core intelligence.** Classify every error BEFORE deciding what to do:

### Tier 0 — Auto-Fix (orchestrator handles, NO agent)
Token cost: **minimal** (~5% of full pipeline)

Errors that resolve by accepting expectations:
- `BUILD SUCCESS` with expectation file diffs only
- Rate count changed (just update test assertion number)
- New expectations needed (`-Daccept.new.adj`)
- **Cookbook signal**: lender has `tier_0_streak >= 3`

**Action**: Accept expectations → verify → commit. No file reading, no agent.

### Tier 1 — Guided Fix (targeted dev agent with 1-2 beads)
Token cost: **moderate** (~30% of full pipeline)

Errors with known fix patterns:
- `CRAWL_MISMATCH` → section keyword changed in ratesheet (fix: update AdjParser keyword)
- `VALUE_MISMATCH` → table ranges changed (fix: update Tables row/col ranges)
- `Sheet not found` → sheet tab renamed (fix: update RateParser sheet constant)
- `Rate count mismatch` → products added/removed (fix: update RateParser processPage)
- `Missing mode` → new mode needed (fix: update Tables getModeResolver)
- **Cookbook signal**: cookbook has a previous Tier 1 fix for same error type on this lender

**Action**: Read ONLY the specific file → create 1-2 targeted beads → spawn parser-dev with exact instructions.

### Tier 2 — Complex Fix (full agent with all parser files)
Token cost: **high** (~100% of full pipeline)

Errors requiring deep investigation:
- `NullPointerException` or `ClassCastException`
- Multiple unrelated failures
- Parser structural change needed
- New table type not seen before
- **Cookbook signal**: lender has no history, or previous Tier 1 fix didn't match this error

**Action**: Read all parser files → full beads decomposition → spawn parser-dev with complete context.

### Classification Algorithm

```
function classifyError(report, cookbook_entry):
    if report contains only "expectation" diffs or "BUILD SUCCESS":
        return TIER_0

    if cookbook_entry exists AND cookbook_entry.tier_0_streak >= 3:
        # Optimistic: try Tier 0 first (accept + verify)
        return TIER_0_OPTIMISTIC

    error_type = extractErrorType(report)

    if error_type in [CRAWL_MISMATCH, VALUE_MISMATCH, SHEET_NOT_FOUND, RATE_COUNT, MISSING_MODE]:
        if cookbook_entry has previous fix for same error_type:
            return TIER_1_WITH_HINT  # include past fix as hint
        return TIER_1

    return TIER_2
```

---

## STEP 1 — Query Jira for Parser-Failed Tasks

**Output:**
```
[fix-parser 1/5] Querying Jira...
```

JQL:
```
project = MOSO AND assignee = "<ASSIGNEE_ID>" AND status = "Backlog" AND summary ~ "[Parser failed]" ORDER BY created DESC
```

Fallback: try `status = "To Do"`.

---

## STEP 2 — Show Task List with Cookbook Predictions

Present the tasks with cookbook intelligence:

```
## Parser-Failed Tasks Found: N

| # | Key | Lender | Date | Predicted Tier | Streak |
|---|-----|--------|------|----------------|--------|
| 1 | MOSO-15944 | BrokerFirstFunding (NonQM) | 03/31 | Tier 0 (streak: 8) | ████████ |
| 2 | MOSO-15943 | LoganFinance (NonQM) | 03/31 | Tier 0 (streak: 3) | ███ |
| 3 | MOSO-15942 | NewLender | 03/31 | Unknown (no history) | — |

Estimated: 2 auto-fix, 1 needs investigation
Fix all? Or specify (e.g., "1,3,5" or "all")
```

Wait for user response.

---

## STEP 3 — Build moso-pricing JAR (once)

```bash
cd /Users/trungthach/IdeaProjects/moso-pricing
mvn install -DskipTests -Pjar-packaging -Dgwt.compiler.skip=true 2>&1 | tail -20
```

---

## STEP 4 — Process Each Task (Smart Tier Routing)

Initialize:
```
fixed_tasks = []
skipped_tasks = []
lender_context = {}
```

**FOR EACH selected task:**

### Step 4a: Parse Lender & Load Cookbook Entry

Extract from title: lender name, isNonQM, fail date.

**Check cookbook FIRST:**
```
cookbook_entry = cookbook[<LENDER>] or null
```

**If cookbook_entry exists** → use cached paths directly (skip all lookups):
```
lender_context[<LENDER>] = cookbook_entry.paths
```

**If no cookbook entry** → memory-first resolution:
1. `infrastructure_index.md`
2. `project_structure.md`
3. `lender-info.sh` (last resort)

Cache in `lender_context`.

```bash
source /Users/trungthach/IdeaProjects/tools/agent-dashboard/emit.sh
emit_meta "<JIRA_KEY>" "<LENDER_NAME>" "fix-parser"
```

### Step 4b: Transition Jira to "In Progress"

Two transitions: Backlog → New ("Select for development") → In Progress ("Start Progress").

Get transitions first, then apply. Leave at "In Progress" — do NOT transition to "Done".

### Step 4c: Download New Ratesheet

```bash
cd /Users/trungthach/IdeaProjects/packs/loan
./download-ratesheet.sh <LENDER_NAME> [--nonqm] 2>&1
```

Capture downloaded file path. If download fails → skip lender, continue.

### Step 4d: Update inputStream in Test Files

**CRITICAL — do NOT skip.** Replace old `RatesheetFiles.<OLD>` constant with new `RatesheetFiles.<NEW>` in both AdjustmentParsersTest.java and RateParserTest.java.

```bash
cd /Users/trungthach/IdeaProjects/packs/loan
grep -n "RatesheetFiles.*<LENDER>" src/test/java/com/mvu/loan/AdjustmentParsersTest.java
grep -n "RatesheetFiles.*<LENDER>" src/test/java/com/mvu/loan/RateParserTest.java
grep "<LENDER_UPPER>_2026" src/test/java/com/mvu/loan/RatesheetFiles.java | tail -1
```

Edit both files with the new constant.

### Step 4e: First Test Pass + Classify

**Output:**
```
[fix-parser 3/5] Testing <LENDER_NAME>...
```

```bash
cd /Users/trungthach/IdeaProjects/packs/loan
./parser-fix.sh <LENDER_NAME> --both 2>&1 | tail -5
cat /tmp/parser-fix/<lender_lowercase>/report.txt
```

**NOW CLASSIFY THE ERROR using the tier system:**

```bash
source /Users/trungthach/IdeaProjects/tools/agent-dashboard/emit.sh
emit_agent_step "fix-parser" "<LENDER>: Tier <N> — <reason>"
```

### Step 4f: Execute Based on Tier

---

#### TIER 0 — Auto-Fix (no agent, no file reading)

**Output:**
```
[fix-parser 3/5] <LENDER>: Tier 0 auto-fix (expectations only)
```

```bash
# Accept expectations
cd /Users/trungthach/IdeaProjects/packs/loan
mvn test -Dtest=AdjustmentParsersTest#test<LenderName> -Daccept -Daccept.new.adj 2>&1 | tail -20
```

→ Go directly to **Step 4g (Verify)**.

**Token saved: ~80% vs spawning an agent.**

---

#### TIER 0 OPTIMISTIC — Try auto-fix first (cookbook predicts Tier 0)

Same as Tier 0. If verification fails → escalate to Tier 1.

---

#### TIER 1 — Guided Fix (targeted agent, 1-2 beads)

**Output:**
```
[fix-parser 3/5] <LENDER>: Tier 1 — <error_type> (guided fix)
```

1. **Read ONLY the target file** (not all parser files):
   - CRAWL_MISMATCH → read only AdjParser
   - VALUE_MISMATCH → read only Tables
   - Sheet not found → read only RateParser
   - Rate count → read only RateParser + RateParserTest

2. **Check cookbook for past fix hint:**
   If cookbook has `last_tier1_fix` for same error type → include as hint:
   ```
   ## Cookbook Hint (same error occurred before)
   Last time: <past fix description>
   This may or may not apply — verify against current ratesheet.
   ```

3. **Create 1-2 targeted beads** and spawn parser-dev:
   ```
   subagent_type: "parser-dev"
   Prompt includes:
   - ONLY the specific file path(s) needed
   - Error report
   - 1-2 beads with exact fix instructions
   - Cookbook hint if available
   - "Do NOT search, do NOT read other files"
   - Rebuild after fix
   ```

4. **After dev returns** → accept expectations → go to Step 4g (Verify).

**Token saved: ~50% vs full Tier 2.**

---

#### TIER 2 — Complex Fix (full agent)

**Output:**
```
[fix-parser 3/5] <LENDER>: Tier 2 — complex fix needed
```

1. **Read all parser files** from lender_context:
   - Tables, RateParser, AdjParser

2. **Full beads decomposition** (same as current Step 4h):
   - Analyze error → map to files → create ordered beads
   - Use error-to-file mapping table

3. **Spawn parser-dev** with full context:
   ```
   subagent_type: "parser-dev"
   Prompt includes:
   - All parser file paths
   - Full error report
   - Ordered beads
   - Complete implementation rules
   - Rebuild after fix
   ```

4. **After dev returns** → accept expectations → go to Step 4g (Verify).

---

### Step 4g: Verification Test (MUST PASS)

```bash
cd /Users/trungthach/IdeaProjects/packs/loan
mvn test -Dtest="AdjustmentParsersTest#test<LenderName>+RateParserTest#test<LenderName>" 2>&1 | tail -20
```

**If FAILS:**
- If was Tier 0 Optimistic → escalate to Tier 1, retry
- If was Tier 1 → escalate to Tier 2, retry
- If was Tier 2 → retry with new beads (max 3 total attempts)
- After 3 total attempts → skip lender, transition Jira back to Backlog

**If PASSES:**
```bash
source /Users/trungthach/IdeaProjects/tools/agent-dashboard/emit.sh
emit_agent_test "fix-parser" "Verify <LENDER>" "PASS" "Both tests pass"
```

### Step 4h: Code Review (Tier 1 and 2 only)

**Skip for Tier 0** — expectation-only changes don't need review.

For Tier 1/2:
```
subagent_type: "code-reviewer"
Prompt: "Review git diff for <LENDER_NAME> parser fix. Focus on moso-pricing and packs/loan."
```

### Step 4i: Update Cookbook (LEARNING STEP)

**This is what makes the agent smarter over time.**

After every successful fix, update the cookbook entry:

```python
entry = cookbook[<LENDER>] or new_entry()

# Update paths (cache for next time)
entry.paths = lender_context[<LENDER>]

# Update tier history (keep last 10)
entry.tier_history.append(actual_tier_used)
if len(entry.tier_history) > 10:
    entry.tier_history = entry.tier_history[-10:]

# Update streak
if actual_tier_used == 0:
    entry.tier_0_streak += 1
else:
    entry.tier_0_streak = 0

# Update metadata
entry.last_fix = today
entry.last_error = error_summary

# If Tier 1 fix, record the fix pattern for future hints
if actual_tier_used == 1:
    entry.last_tier1_fix = "<error_type> → <what was changed> (<date>)"

# If Tier 0 Optimistic failed and escalated, note it
if escalated:
    entry.notes += "Optimistic failed on <date>, was <actual_error>"
```

Write the updated cookbook to `$COOKBOOK_FILE`:

```bash
source /Users/trungthach/IdeaProjects/tools/agent-dashboard/emit.sh
emit_agent_step "fix-parser" "Cookbook updated: <LENDER> (Tier <N>, streak: <streak>)"
```

**For failed/skipped lenders**, also update cookbook:
```python
entry.last_error = "FAILED: <error_summary>"
entry.tier_history.append(-1)  # -1 = failed
entry.notes += "Failed on <date>: <reason>"
```

### Step 4j: Stage Changes (NO COMMIT)

Stage the changes for this lender so they're ready for the user to review:

```bash
# Stage in packs/loan repo
cd $PACKS_LOAN
git add src/test/resources/adj-expectations/
git add src/test/resources/ratesheets/
git add src/test/resources/expected-new-adj/
git add src/test/java/

# Stage in moso-pricing repo (if Tier 1/2 changed code)
cd $MOSO_PRICING
git add src/main/java/
```

**Do NOT commit.** Leave changes staged. The user will commit manually.

### Step 4k: Mark Task as Fixed

Leave at "In Progress". Add to `fixed_tasks`.

**→ Continue to next task**

---

## STEP 5 — Summary Report + Cookbook Stats

```bash
source /Users/trungthach/IdeaProjects/tools/agent-dashboard/emit.sh
emit_pipeline_done
```

```
## Fix Parser Pipeline — Complete

### Results
| Key | Lender | Tier | Fix Type | Status |
|-----|--------|------|----------|--------|
| MOSO-15944 | BrokerFirstFunding | 0 | auto-fix (expectations) | staged |
| MOSO-15943 | LoganFinance | 0 | auto-fix (expectations) | staged |
| MOSO-15942 | NewLender | 1 | guided fix (CRAWL_MISMATCH) | staged |

### Skipped
| Key | Lender | Reason |
|-----|--------|--------|
| MOSO-15941 | ADMortgage | Tier 2 failed after 3 attempts |

### Cookbook Intelligence
- Tier 0 auto-fixes: N (saved ~80% tokens each)
- Tier 1 guided fixes: N (saved ~50% tokens each)
- Tier 2 complex fixes: N
- Failed: N
- Lenders tracked in cookbook: <total>

### Token Efficiency
- Estimated tokens saved vs always-Tier-2: ~<percentage>%

Total: N fixed, M skipped
```

---

## Optimization Rules (Always Enforced)

1. **Tier-First**: ALWAYS classify the error before deciding what to do. Never default to spawning an agent.

2. **Cookbook-First**: Check cookbook before memory, memory before search. If cookbook has cached paths → skip all lookups.

3. **Lazy Reading**: Don't read parser files until classification demands it. Tier 0 reads NOTHING. Tier 1 reads ONE file. Tier 2 reads all.

4. **Learn from Every Fix**: Update cookbook after EVERY fix (success or failure). Record: tier used, error type, fix pattern, paths.

5. **Escalate, Don't Retry Blind**: If Tier 0 fails → Tier 1. If Tier 1 fails → Tier 2. Don't retry the same tier with the same approach.

6. **Cookbook Hints**: When Tier 1 matches a past fix pattern, include the hint. The dev agent can reuse the same fix if the error is similar.

7. **Skip Reviews for Tier 0**: Expectation-only changes are mechanical — don't waste tokens on code review.

8. **Predictive Display**: Show cookbook predictions in the task list so the user knows what to expect before confirming.

9. **Memory-First Paths**: Use `infrastructure_index.md` → `cookbook cached paths` → `lender-info.sh`. Never broad search.

10. **Verify Before Done**: Always run verification test. Flow: Classify → Fix (by tier) → Verify → Learn → Stage (no commit). User commits manually.
