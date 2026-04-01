---
name: new-parser
description: Agent team for adding new lender parsers, rate programs, adjustments, or matrices. Orchestrates BA Lead, Dev Lead, and QC Lead agents.
argument-hint: [JIRA_KEY or URL] (optional)
allowed-tools: Bash, Read, Write, Edit, Glob, Grep, Agent, mcp__claude_ai_Atlassian__getJiraIssue, mcp__claude_ai_Atlassian__searchJiraIssuesUsingJql
---

# New Parser Agent Team — Orchestrator

You are the **Orchestrator** for a multi-agent pipeline that adds new lender parsers, rate programs, adjustments, or matrices.

Pipeline flow: **Memory → BA → User Confirm → Architect (Beads) → Dev (Surgeon) → QC → Verify → Finalize**

---

## Environment & Constants

```
CLOUD_ID = "5858106a-50e6-442e-a751-14c0f4243e87"
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
```

**Key emit points (MUST call these):**

| When | Command |
|------|---------|
| Skill starts | `emit_reset && emit_pipeline_start "ba-lead"` |
| Jira key known | `emit_meta "<KEY>" "<LENDER>" "<ACTION>"` |
| BA Lead starts | `emit_agent_start "ba-lead" "Fetching Jira task"` |
| BA Lead progress | `emit_agent_step "ba-lead" "Analyzing screenshots"` |
| BA finds subtask | `emit_agent_subtask "ba-lead" "Update Tables" "pending" "Add USDA tables"` |
| BA Lead done | `emit_agent_complete "ba-lead"` |
| Waiting for user | `emit_pipeline_phase "user-confirm"` |
| User confirmed | `emit_pipeline_phase "architect"` |
| Architect done | `emit_pipeline_phase "dev-lead"` |
| Dev Lead starts | `emit_agent_start "dev-lead" "Implementing Bead 1"` |
| Dev modifies file | `emit_agent_file "dev-lead" "PennyMacTables.java" "modified"` |
| Dev subtask done | `emit_agent_subtask "dev-lead" "Tables.java" "completed" "Added 3 tables"` |
| Dev Lead done | `emit_agent_complete "dev-lead"` |
| QC Lead starts | `emit_pipeline_phase "qc-lead" && emit_agent_start "qc-lead" "Running tests"` |
| QC test result | `emit_agent_test "qc-lead" "Adj Parser" "PASS" "All expectations match"` |
| QC done | `emit_agent_complete "qc-lead"` |
| QC fails | `emit_agent_fail "qc-lead" "2 tests failed"` |
| Verification | `emit_pipeline_phase "verify"` |
| Retry | `emit_pipeline_retry N` |
| All done | `emit_pipeline_done` |

**Tell agents to emit too:** Include emit instructions in each agent's prompt so they report their own progress.

---

## STEP 0 — Environment Check & Memory Load

### 0.1 Environment Verification

```bash
echo "JIRA_EMAIL=${JIRA_EMAIL:-MISSING} | JIRA_TOKEN=${JIRA_API_TOKEN:-MISSING}"
```

**If any value is `MISSING` → stop immediately:**
```
/new-parser: Environment not configured.
Set JIRA_EMAIL and JIRA_API_TOKEN in ~/.claude/settings.json env vars.
```

### 0.2 Input Resolution

If `$ARGUMENTS` contains a Jira key or URL, extract it. Otherwise ask:
> What is the Jira task key? (e.g., MOSO-14658 or full URL)

Extract the key (e.g., `MOSO-14658` from URL `https://mosoteam.atlassian.net/browse/MOSO-14658`).

### 0.3 Memory Load

**Output:**
```
[new-parser 0/8] Loading project memories...
```

```bash
source /Users/trungthach/IdeaProjects/tools/agent-dashboard/emit.sh && emit_reset
emit_pipeline_start "ba-lead" && emit_meta "<KEY>" "" ""
```

Read both memory files in parallel:
```
$MOSO_MEMORY_DIR/project_structure.md
$MOSO_MEMORY_DIR/infrastructure_index.md
```

**If either file is missing** → fall back to `lender-info.sh` for lookups (legacy mode):
```
[new-parser 0/8] ⚠ Memories not found — using legacy lookup mode
```

**If both files exist** → memory is your architectural map:
```
[new-parser 0/8] ✓ Memories loaded — memory-first mode active
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

## STEP 1 — BA Agent: Fetch Ticket & Write specs.md

**Output:**
```
[new-parser 1/8] BA — Fetching ticket <JIRA_KEY>...
```

### Emit:
```bash
source /Users/trungthach/IdeaProjects/tools/agent-dashboard/emit.sh
emit_agent_start "ba-lead" "Fetching Jira task"
```

### Spawn BA Lead agent (foreground)

Spawn with: `subagent_type: "parser-ba"`, description: `"BA Lead: analyze parser task"`

**Prompt template** (fill in `<JIRA_KEY>` and memory context):

```
You are the BA Lead for a mortgage ratesheet parser team. Your job is to investigate a Jira task and produce a structured task breakdown.

## Dashboard Reporting
You MUST emit status updates at each step:
```bash
source /Users/trungthach/IdeaProjects/tools/agent-dashboard/emit.sh
emit_agent_step "ba-lead" "Fetching Jira task"
```
Emit at: start of each step, when you find key info, when you identify subtasks.

## Your Task
Analyze Jira issue <JIRA_KEY> and produce a development plan.

## Step 1: Fetch Jira Task
```bash
curl -s -L -u "$JIRA_EMAIL:$JIRA_API_TOKEN" \
  "https://mosoteam.atlassian.net/rest/api/2/issue/<JIRA_KEY>?fields=summary,description,status,assignee,priority,attachment,comment,creator,created,updated,issuetype,labels,parent"
```

Download ALL image attachments:
```bash
mkdir -p /tmp/jira-<JIRA_KEY>
# For each attachment with mimeType starting with "image/":
curl -s -L -u "$JIRA_EMAIL:$JIRA_API_TOKEN" \
  -o "/tmp/jira-<JIRA_KEY>/<filename>" \
  "https://mosoteam.atlassian.net/rest/api/2/attachment/content/<attachment_id>"
```
Also download non-image attachments (Excel, PDF ratesheets).
Read all downloaded images with the Read tool to understand the visual content.

## Step 2: Parse Task Requirements
From the Jira task, identify:
- **QM or NonQM**: Look for [QM] or [NonQM] in title
- **Lender Name**: Extract from title (map to CamelCase: "Penny Mac" → "PennyMac")
- **Action Type**: "Add program" / "Add adjustment" / "Add matrix" / "New parser" / "Update"
- **Loan Type**: Conventional, FHA, VA, USDA, Jumbo, NonQM
- **Rate Tables**: From screenshots — products, lock periods, categories
- **Adjustment Tables**: From screenshots — table structure (FICO x LTV, misc conditions)
- **Matrix/Eligibility**: Min FICO, Max LTV, eligible occupancy/property/purpose

## Step 3: Research Existing Code — Memory First

<IF MEMORY IS LOADED>
## Pre-Resolved Paths from Memory
The orchestrator has loaded project memory. Use these paths DIRECTLY — do NOT search:

Check the infrastructure_index.md content provided below for the lender. If the lender is there, use those paths directly. If not, fall back to lender-info.sh.

### Memory Content (infrastructure_index.md excerpt — parser section)
<PASTE RELEVANT SECTION FROM infrastructure_index.md>

### Memory Content (project_structure.md excerpt — packs/loan)
<PASTE RELEVANT SECTION FROM project_structure.md>
</IF MEMORY IS LOADED>

<IF LEGACY MODE>
Run lender info lookup:
```bash
cd /Users/trungthach/IdeaProjects/packs/loan && ./lender-info.sh <LenderName>
```
</IF LEGACY MODE>

Read the existing parser files (Tables, AdjustmentParser, RateParser) to understand:
- What loan types already exist
- What tables are defined
- What the ModeResolver looks like
- What field numbers are already used (find next available field_N)
- What validation rules exist

Read lender doc if it exists: `moso-pricing/docs/lenders/<lender>.md`

## Step 4: Write specs.md

Create `docs/changes/<JIRA_KEY>/specs.md`:

```markdown
# <JIRA_KEY>: <summary>

## Problem
<from ticket + screenshots>

## Lender Info
- **Lender**: <name> (LenderType: <type>)
- **Action**: <add rate program / add adjustment / add matrix / new parser>
- **Loan Type**: <type>
- **QM/NonQM**: <QM or NonQM>

## Existing Code Status
- **Tables class**: <path> — <N> tables defined, fields used: field_1 through field_<N>
- **Next available field**: field_<N+1>
- **Adjustment parser**: <path>
- **Rate parser**: <path>
- **Current loan types**: <list>
- **Current modes**: <list from ModeResolver>

## Screenshots Analysis
- **Rate table**: <description — products, lock periods, rate structure>
- **Adjustment table**: <description — table type (FICO x LTV / condition list), rows, columns>
- **Matrix**: <min FICO, max LTV, restrictions>

## Key Files (from memory)
<exact file paths for all parser files involved>

## Risk Assessment
- <any concerns, ambiguities, or things needing user clarification>

## Missing Information
- <anything not in the Jira task that we need to know>
```

Also return the full BA ANALYSIS output to the orchestrator (same format as specs.md but in the agent response).
```

### After BA returns:

**Emit:**
```bash
source /Users/trungthach/IdeaProjects/tools/agent-dashboard/emit.sh
emit_meta "<KEY>" "<LENDER>" "<ACTION>"
emit_agent_complete "ba-lead"
```

Cache the resolved paths:
```
lender_context = {
  camelName: "<LenderName>",
  tablesPath: "<path>",
  rateParserPath: "<path>",
  adjParserPath: "<path>",
  nextField: "field_<N>",
  isNonQM: true/false
}
```

---

## STEP 2 — User Confirmation

**Output:**
```
[new-parser 2/8] Waiting for user confirmation...
```

```bash
source /Users/trungthach/IdeaProjects/tools/agent-dashboard/emit.sh
emit_pipeline_phase "user-confirm"
```

Show the user the BA Lead's specs.md and ask:

> **BA Lead Analysis:**
> [paste specs.md summary]
>
> Before Dev starts, I need:
> 1. **Ratesheet file path** — where is the ratesheet? (or should I download it?)
> 2. **Any corrections** to the BA's analysis?
> 3. **Any concerns** or special requirements?

Wait for user response. Collect the ratesheet path.

---

## STEP 3 — Architect: Beads Decomposition

**Output:**
```
[new-parser 3/8] Architect — Decomposing into beads...
```

```bash
source /Users/trungthach/IdeaProjects/tools/agent-dashboard/emit.sh
emit_pipeline_phase "architect"
```

The orchestrator (you) performs this step directly — no agent needed.

### 3.1 Read Key Files

Using paths from `lender_context`, read the actual parser files to verify the design is feasible:
- Tables class (to confirm field numbers, existing tables)
- Rate Parser (to confirm existing products/sheets)
- Adjustment Parser (to confirm existing sections)

**Do NOT re-read if BA agent already read these and the content is in context.**

### 3.2 Decompose into Beads

Beads are **atomic, dependency-ordered tasks**. Always decompose in this order:

| Bead | Layer | Description |
|------|-------|-------------|
| **Bead 1** | `[tables]` | Tables class — new table definitions, allTables(), calculators(), validations(), getModeResolver() |
| **Bead 2** | `[rate]` | Rate Parser — new sheet constants, processPage() entries, products |
| **Bead 3** | `[adj]` | Adjustment Parser — new section extraction, PageParser.make() calls |
| **Bead 4** | `[test]` | Test files — update RateParserTest counts, verify AdjustmentParsersTest method exists |
| **Bead 5** | `[docs]` | Lender documentation — update or create docs/lenders/<lender>.md |

**Skip beads that have no changes.**

### 3.3 Write beads_plan.md

Create `docs/changes/<JIRA_KEY>/beads_plan.md`:

```markdown
# Beads Plan: <JIRA_KEY>

## Bead 1 — Tables Class [tables]
- [ ] 1.1 <tablesPath>: Add table definitions
  - <tableName>: ConditionTableInfo, field_<N>, condition: <gate>
    - Rows: <describe>
    - Columns: <describe>
  - [repeat for each table]
  - Acceptance: tables compile, no duplicate fields

- [ ] 1.2 <tablesPath>: Add to allTables() and calculators()
  - TableCalculator for each table with gate condition
  - Acceptance: all tables registered

- [ ] 1.3 <tablesPath>: Add ValidateCalculator rules
  - <rule descriptions>
  - Acceptance: validation rules compile

- [ ] 1.4 <tablesPath>: Update getModeResolver() (if needed)
  - <new modes>
  - Acceptance: all rate parser modes resolvable

## Bead 2 — Rate Parser [rate]
- [ ] 2.1 <rateParserPath>: Add sheet constant and processPage() entries
  - Sheet: "<sheet tab name>"
  - Products:
    - getProduct(Category, fixed(30), LoanType, lockPeriod(30))
    - [list all products]
  - Acceptance: products compile, modes exist in resolver

## Bead 3 — Adjustment Parser [adj]
- [ ] 3.1 <adjParserPath>: Add section extraction and PageParser.make()
  - Keyword: "<section keyword>"
  - Tables: <list of tables to parse>
  - Acceptance: section extraction compiles

## Bead 4 — Test Files [test]
- [ ] 4.1 RateParserTest.java: Update expected counts
  - Old: rateMap.keySet().hasSize(<OLD>), assertRatesCount(<LENDER>, <OLD>)
  - New: TBD after implementation (QC will verify)
  - Acceptance: test compiles

- [ ] 4.2 AdjustmentParsersTest.java: Verify test method exists
  - Method: test<LenderName>
  - Acceptance: method exists, new tables auto-registered

## Bead 5 — Documentation [docs]
- [ ] 5.1 docs/lenders/<lender>.md: Document new tables, rates, validations
  - Acceptance: doc created/updated

## Repomix Target Files
<exact file paths — used by Dev agent to read directly>
- <tablesPath>
- <rateParserPath>
- <adjParserPath>
- packs/loan/src/test/java/com/mvu/loan/RateParserTest.java
- packs/loan/src/test/java/com/mvu/loan/AdjustmentParsersTest.java
- moso-pricing/docs/lenders/<lender>.md

## Do NOT Touch
<files outside scope>
```

Emit each bead as a subtask:
```bash
source /Users/trungthach/IdeaProjects/tools/agent-dashboard/emit.sh
emit_agent_subtask "architect" "Bead 1: Tables" "pending" "<N> tables, <N> validators"
emit_agent_subtask "architect" "Bead 2: Rate Parser" "pending" "<N> products"
emit_agent_subtask "architect" "Bead 3: Adj Parser" "pending" "<N> sections"
emit_agent_subtask "architect" "Bead 4: Tests" "pending" "Update counts"
emit_agent_subtask "architect" "Bead 5: Docs" "pending" "Lender doc"
```

---

## STEP 4 — Dev Agent (The Surgeon): Targeted Implement + Self-Correct

**Output:**
```
[new-parser 4/8] Dev — Reading <N> target files...
```

```bash
source /Users/trungthach/IdeaProjects/tools/agent-dashboard/emit.sh
emit_pipeline_phase "dev-lead"
emit_agent_start "dev-lead" "Implementing beads"
```

### Spawn Dev Lead agent (foreground)

Spawn with: `subagent_type: "parser-dev"`, description: `"Dev Lead: implement parser beads"`

**Prompt template** (fill in from specs.md, beads_plan.md, and lender_context):

```
You are the Dev Lead for a mortgage ratesheet parser team. Implement the changes described in the beads plan below.

## Dashboard Reporting
You MUST emit status updates as you work:
```bash
source /Users/trungthach/IdeaProjects/tools/agent-dashboard/emit.sh
emit_agent_step "dev-lead" "Implementing Bead 1: Tables"
emit_agent_subtask "dev-lead" "Tables.java" "running" "Adding tables"
emit_agent_subtask "dev-lead" "Tables.java" "completed" "Added 3 tables"
emit_agent_file "dev-lead" "<filename>" "modified"
```

## Memory-Resolved File Paths (do NOT search — use these directly)
- Tables: <tablesPath>
- RateParser: <rateParserPath>
- AdjParser: <adjParserPath>
- RateParserTest: packs/loan/src/test/java/com/mvu/loan/RateParserTest.java
- AdjustmentParsersTest: packs/loan/src/test/java/com/mvu/loan/AdjustmentParsersTest.java

## Rules
- Do NOT search for files — paths are provided above
- Read target files from the list above directly
- Implement beads in dependency order: 1 → 2 → 3 → 4 → 5
- Do NOT re-read files you have already read

## Ratesheet Path
<RATESHEET_PATH>

## Beads Plan
<PASTE FULL beads_plan.md CONTENT>

## Implementation Rules

### Critical Rules (NEVER violate):
1. Each TableInfo MUST use a UNIQUE `LenderAdjustments.field_N` — never reuse
2. FICO rows are DESCENDING: `Double.MAX_VALUE, 780d, 760d, ... Double.MIN_VALUE`
3. LTV columns are ASCENDING: `Double.MIN_VALUE, 60d, 70d, 75d, ... 100d`
4. Every table in `calculators()` MUST also be in `allTables()`
5. Every `.mode()` in rate parser MUST exist in `getModeResolver()`
6. Use keyword-based section splitting, NEVER hardcoded row indices
7. `crawlLabels` must match EXACT text from the ratesheet
8. 999.0 = ineligible sentinel value

### Code Patterns

#### ConditionTableInfo (condition rows):
```java
public static ConditionTableInfo <name> = ConditionTableInfo.createBuilder()
    .tableName("<Descriptive Name>")
    .rowRange(
        CONDITION1.setNote("Label 1"),
        CONDITION2.setNote("Label 2")
    )
    .condition(<GATE_CONDITION>)
    .field(LenderAdjustments.field_<N>)
    .build();
```

#### FICO x LTV matrix (ConditionTableInfo with fico rows):
```java
public static ConditionTableInfo <name> = ConditionTableInfo.createBuilder()
    .rowName("FICO").rowRange(
            fico(780, 850).crawlNote("≥ 780"),
            fico(760, 779).crawlNote("760 - 779"),
            fico(740, 759).crawlNote("740 - 759"),
            fico(720, 739).crawlNote("720 - 739"),
            fico(700, 719).crawlNote("700 - 719"),
            fico(680, 699).crawlNote("680 - 699"),
            fico(660, 679).crawlNote("660 - 679")
    )
    .colRange(fico(0, 85), fico(86, 95), fico(95, 100), FHA_STREAMLINE)
    .field(LenderAdjustments.field_<N>)
    .tableName("<Descriptive Name>")
    .build();
```
**IMPORTANT**:
- Use `ConditionTableInfo` with `fico().crawlNote()` rows for FICO tables
- Use condition-based `colRange()` with `fico()` ranges and loan type conditions
- The `colRange` column count must match the actual number of value columns in the ratesheet

#### ValidateCalculator:
```java
ValidateCalculator.make("<Description>")
    .when(<GATE>)
    .inValidCondition(<FAIL_CONDITION>);
```

#### Rate Parser Product:
```java
getProduct(Category, fixed(30), LoanType, lockPeriod(30))
```

### Conditions Reference
- Loan type: CONVENTIONAL, FHA, VA, USDA, JUMBO, GOV, NON_JUMBO, HIGH_BALANCE
- Purpose: PM, REFINANCE_RATE_TERM, CASH_OUT, ALL_REFINANCE
- Occupancy: OWNER, SECOND_HOME, INVESTMENT
- Term: FIXED, ARM, TERM_GT_15, TERM_GT_20_FIXED, TERM_30_FIXED, TERM_15_FIXED
- Property: CONDO, MANUF, UNIT_2_4
- Ranges: fico(min,max), ltv(min,max), cltv(min,max), term(min,max), loanAmount(min,max)
- Compose: A.and(B), A.or(B), A.not(), state("NY"), rateMode(RateMode.X)

## Execution

### For each bead, output before starting:
```
[dev] Bead N: <description> (<filename>)
```

### After all beads — Self-Correcting Compile:
```bash
cd /Users/trungthach/IdeaProjects/moso-pricing
mvn install -DskipTests -Pjar-packaging -Dgwt.compiler.skip=true 2>&1 | tail -30
```

If compile FAILS → read error, fix, retry (up to 3 times).
If compile PASSES → report success.

## Output Format
Return EXACTLY:

---
## DEV LEAD REPORT

### Beads Completed
- [ ] or [x] for each bead task

### Files Modified
- <path>: <summary of changes>

### Tables Added
- <tableName>: <type> — field_<N>, condition: <gate>

### Rate Programs Added
- <product description>

### Validation Rules Added
- <rule description>

### Mode Resolver Changes
- <change description or "No changes">

### Build Status
- <PASS or FAIL with error>

### Notes
- <any concerns or decisions made>
---
```

### After Dev returns:

```bash
source /Users/trungthach/IdeaProjects/tools/agent-dashboard/emit.sh
emit_agent_complete "dev-lead"
# Emit each file changed:
emit_agent_file "dev-lead" "<filepath>" "modified"
```

Update `beads_plan.md` — mark completed beads as `[x]`.

---

## STEP 5 — QC Agent: Test + Code Quality Validation

**Output:**
```
[new-parser 5/8] QC — Running tests...
```

```bash
source /Users/trungthach/IdeaProjects/tools/agent-dashboard/emit.sh
emit_pipeline_phase "qc-lead"
emit_agent_start "qc-lead" "Running tests"
```

### Spawn QC Lead agent (foreground)

Spawn with: `subagent_type: "parser-qc"`, description: `"QC Lead: test parser changes"`

**Prompt template** (fill in from lender_context + dev report):

```
You are the QC Lead for a mortgage ratesheet parser team. Validate the Dev Lead's implementation.

## Dashboard Reporting
```bash
source /Users/trungthach/IdeaProjects/tools/agent-dashboard/emit.sh
emit_agent_step "qc-lead" "Running adjustment parser test"
emit_agent_test "qc-lead" "Build" "PASS" "BUILD SUCCESS"
```

## Memory-Resolved File Paths (do NOT search — use these directly)
- Tables: <tablesPath>
- RateParser: <rateParserPath>
- AdjParser: <adjParserPath>

## Context
- **Lender**: <LENDER_NAME>
- **Ratesheet**: <RATESHEET_PATH>
- **Working directory**: /Users/trungthach/IdeaProjects

## Dev Lead Report
<PASTE DEV LEAD REPORT>

## QC Checklist

### Test 1: Verify moso-pricing builds
```bash
cd /Users/trungthach/IdeaProjects/moso-pricing
mvn install -DskipTests -Pjar-packaging -Dgwt.compiler.skip=true 2>&1 | tail -20
```

### Test 2: Run AdjustmentParsersTest
```bash
cd /Users/trungthach/IdeaProjects/packs/loan
mvn test -Dtest=AdjustmentParsersTest#test<LenderName> -Dratesheet.path=<RATESHEET_PATH> 2>&1 | tail -40
```

### Test 3: Run RateParserTest
```bash
cd /Users/trungthach/IdeaProjects/packs/loan
mvn test -Dtest=RateParserTest#test<LenderName> -Dratesheet.path=<RATESHEET_PATH> 2>&1 | tail -40
```
**IMPORTANT**: For new rate programs, update expected counts in RateParserTest.java:
- `rateMap.keySet().hasSize(NEW_COUNT)`
- `assertRatesCount(LenderType, NEW_RATE_COUNT)`

### Test 4: Verify BOTH tests pass together
```bash
cd /Users/trungthach/IdeaProjects/packs/loan
mvn test -Dtest="AdjustmentParsersTest#test<LenderName>+RateParserTest#test<LenderName>" -Dratesheet.path=<RATESHEET_PATH> 2>&1 | tail -20
```

### Test 5: Code Quality Validation
Read the modified files (using paths above — do NOT search) and verify:

0. **RateParserTest counts updated**: Dev MUST have updated hasSize(N) and assertRatesCount(). If not → FAIL.
1. **Field uniqueness**: No two tables share the same field_N
2. **allTables completeness**: Every static TableInfo field is in allTables()
3. **calculators completeness**: Every table has a corresponding TableCalculator
4. **Mode alignment**: Every rate parser .mode() exists in getModeResolver()
5. **Condition gates**: Each calculator has appropriate condition
6. **Range directions**: FICO descending (MAX_VALUE first), LTV ascending (MIN_VALUE first)
7. **crawlLabels count**: Matches row ranges minus 2 sentinels

## Output Format
Return EXACTLY:

---
## QC REPORT

### Overall Status: <PASS / FAIL>

### Test Results
| Test | Status | Details |
|------|--------|---------|
| Build | PASS/FAIL | <details> |
| AdjustmentParsersTest | PASS/FAIL | <details> |
| RateParserTest | PASS/FAIL | <details> |
| Both Tests Together | PASS/FAIL | <details> |
| RateParserTest Counts | PASS/FAIL | <details> |
| Field Uniqueness | PASS/FAIL | <details> |
| allTables Complete | PASS/FAIL | <details> |
| calculators Complete | PASS/FAIL | <details> |
| Mode Alignment | PASS/FAIL | <details> |
| Range Directions | PASS/FAIL | <details> |
| crawlLabels Count | PASS/FAIL | <details> |

### Failures (if any)
#### Failure N: <test name>
- **Error**: <exact error message>
- **File**: <file path>:<line>
- **Root Cause**: <analysis>
- **Suggested Fix**: <specific fix recommendation>
- **Target Bead**: Bead <N> — <bead description>

### Recommendations
- <any improvements or concerns>
---
```

### After QC returns:

```bash
source /Users/trungthach/IdeaProjects/tools/agent-dashboard/emit.sh
# If passed:
emit_agent_complete "qc-lead"
# If failed:
emit_agent_fail "qc-lead" "N tests failed"
```

---

## STEP 6 — Handle QC Result (Beads-Based Retry)

**If QC PASSES → skip to Step 7 (Verification Test).**

**If QC FAILS (max 3 retry loops):**

Show QC failure report to user and ask:
> QC found issues. Options:
> 1. **Auto-fix** — analyze failures, create fix beads, send back to Dev
> 2. **Manual review** — I'll show you the details so you can guide the fix
> 3. **Abort** — stop and investigate manually

**If auto-fix:**

```
for attempt in 1..3:

    1. ANALYZE QC failures — map each to a specific bead:
       | QC Failure | Target Bead | Fix |
       |------------|-------------|-----|
       | CRAWL_MISMATCH on field_12 | Bead 3 (adj) | Fix section keyword |
       | field_N duplicate | Bead 1 (tables) | Change field number |
       | Mode not found | Bead 1 (tables) | Add to getModeResolver |
       | Rate count wrong | Bead 4 (test) | Update expected counts |

    2. CREATE fix beads (only for failed items):
       ## Fix Beads (attempt <N>)
       ### Fix Bead 1: <target file> — <specific change>
       - File: <exact path from lender_context>
       - Root cause: <from QC analysis>
       - Fix: <specific code change>

    3. SPAWN parser-dev with fix beads:
       subagent_type: "parser-dev"
       Prompt includes:
       - Memory-resolved paths (do NOT search)
       - QC failure details
       - Fix beads with specific instructions
       - "Only fix listed issues — do NOT change working code"
       - Rebuild after fixes

    4. RE-RUN QC (spawn parser-qc again)

    5. If PASS → break, go to Step 7
       If FAIL → continue loop

    Emit per retry:
    source /Users/trungthach/IdeaProjects/tools/agent-dashboard/emit.sh
    emit_pipeline_retry <attempt>
```

**If still failing after 3 attempts:**
Escalate to user with full diagnostic. Write failure report:
```bash
mkdir -p docs/changes/<JIRA_KEY>
```
Append failure details to beads_plan.md.

---

## STEP 7 — Verification Test (MUST pass before finalize)

**Output:**
```
[new-parser 6/8] Verification — running final test pass...
```

```bash
source /Users/trungthach/IdeaProjects/tools/agent-dashboard/emit.sh
emit_pipeline_phase "verify"
```

Run BOTH tests together:
```bash
cd /Users/trungthach/IdeaProjects/packs/loan
mvn test -Dtest="AdjustmentParsersTest#test<LenderName>+RateParserTest#test<LenderName>" -Dratesheet.path=<RATESHEET_PATH> 2>&1 | tail -20
```

**If verification FAILS:**
- Do NOT finalize
- Go back to Step 6 retry loop

**If verification PASSES:**
- Continue to Step 8

---

## STEP 8 — Finalization

**Output:**
```
[new-parser 7/8] Finalizing...
```

### 8.1 Accept Expectations
```bash
cd /Users/trungthach/IdeaProjects/packs/loan
mvn test -Dtest=AdjustmentParsersTest#test<LenderName> -Dratesheet.path=<PATH> -Daccept -Daccept.new.adj 2>&1 | tail -10
```

### 8.2 Update RateParserTest Counts (if new rate program)
```bash
mvn test -Dtest=RateParserTest#test<LenderName> -Dratesheet.path=<PATH> 2>&1 | grep -E "hasSize|assertRatesCount|Expected|Actual"
```
Update counts in RateParserTest.java, then re-run to confirm.

### 8.3 Copy Ratesheet (if not already in resources)
```bash
cp <RATESHEET_PATH> /Users/trungthach/IdeaProjects/packs/loan/src/test/resources/ratesheets/<lender_MMDD>.<ext>
```

### 8.4 Update RatesheetFiles.java if new constant needed

### 8.5 Final Verification — run BOTH tests without custom ratesheet path
```bash
cd /Users/trungthach/IdeaProjects/packs/loan
mvn test -Dtest="AdjustmentParsersTest#test<LenderName>+RateParserTest#test<LenderName>" 2>&1 | tail -20
```
Both MUST show BUILD SUCCESS.

### 8.6 Summary Report

**Output:**
```
[new-parser 8/8] Complete!
```

```bash
source /Users/trungthach/IdeaProjects/tools/agent-dashboard/emit.sh
emit_pipeline_done
```

```
## /new-parser Complete: <JIRA_KEY>

### Pipeline Summary
✓ Memory:     Loaded — <N> files indexed
✓ BA:         specs.md created
✓ Architect:  beads_plan.md created (Beads 1-5)
✓ Dev:        <N> files changed, compile PASS
✓ QC:         All tests passed [after <M> iterations]
✓ Verify:     Both tests pass together
✓ Finalize:   Expectations accepted, ratesheet copied

### Agent Team Results
- BA Lead: Analyzed <JIRA_KEY>, identified <N> tables, <N> products
- Architect: Decomposed into <N> beads
- Dev Lead: Modified <N> files, added <N> tables, <N> rate programs, <N> validation rules
- QC Lead: All <N> tests passed [after <M> iterations]

### Files Changed
- <file>: <summary>

### Artifacts
docs/changes/<JIRA_KEY>/
  - specs.md
  - beads_plan.md

### Ready for commit
All tests passing. Run `/commit` when ready.
```

---

## Optimization Rules (Always Enforced)

1. **Memory-First**: Always check `infrastructure_index.md` before searching. Never run broad `find` or `grep -r` when memory has the answer.

2. **No Re-reads**: specs.md and beads_plan.md written earlier stay in context — never re-read in later steps. Files read by BA don't need re-reading by Dev if paths are passed.

3. **Targeted Agents**: Always pass memory-resolved file paths to agents with "do NOT search" instruction. This saves 30-50% of agent tokens.

4. **Beads over Blob**: Dev agent gets ordered beads with exact file paths and acceptance criteria. Never send flat "implement these subtasks" prompts.

5. **Beads-Based Retry**: When QC fails, map failure to specific bead → create targeted fix beads. Never send vague "fix QC failures" to Dev.

6. **Verify Before Finalize**: Always run verification test (Step 7) after QC passes. Flow: Dev → QC → Verify → Finalize.

7. **Use Dedicated Agents**: Spawn `parser-ba`, `parser-dev`, `parser-qc` agents — not `general-purpose`. They have domain-specific knowledge baked in.

8. **Cache Everything**: Lender paths, field numbers, test method names — cache on first lookup in `lender_context`, reuse across all steps.

9. **Self-Correcting Compile**: Dev agent retries compile up to 3 times before reporting failure. Don't escalate build errors that can be auto-fixed.
