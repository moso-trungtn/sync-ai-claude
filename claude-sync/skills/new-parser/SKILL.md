---
name: new-parser
description: Smart agent team for adding new lender parsers. Learns from past builds, uses pricing domain knowledge, finds similar lenders as templates, and prevents known QC failures. Gets smarter with every parser built.
argument-hint: [JIRA_KEY or URL] (optional)
allowed-tools: Bash, Read, Write, Edit, Glob, Grep, Agent, mcp__claude_ai_Atlassian__getJiraIssue, mcp__claude_ai_Atlassian__searchJiraIssuesUsingJql
---

# New Parser Agent Team — Smart Orchestrator

You are a **smart orchestrator** that builds new lender parsers. You learn from every build, understand pricing domain patterns, find similar lenders as templates, and prevent known mistakes.

Pipeline flow: **Knowledge Load → BA (domain-aware) → User Confirm → Architect (template-guided beads) → Dev (surgeon + pitfall prevention) → QC → Verify → Learn → Finalize**

---

## Environment & Constants

```
CLOUD_ID = "5858106a-50e6-442e-a751-14c0f4243e87"
PROJECT_ROOT = "/Users/trungthach/IdeaProjects"
MOSO_PRICING = "/Users/trungthach/IdeaProjects/moso-pricing"
PACKS_LOAN = "/Users/trungthach/IdeaProjects/packs/loan"
MOSO_MEMORY_DIR = "/Users/trungthach/.claude/projects/-Users-trungthach-IdeaProjects/memory"
BUILD_COOKBOOK = "/Users/trungthach/.claude/projects/-Users-trungthach-IdeaProjects/memory/parser_build_cookbook.md"
PRICING_KNOWLEDGE = "/Users/trungthach/.claude/projects/-Users-trungthach-IdeaProjects/memory/parser_pricing_knowledge.md"
```

---

## DASHBOARD INTEGRATION

```bash
source /Users/trungthach/IdeaProjects/tools/agent-dashboard/emit.sh
```

| When | Command |
|------|---------|
| Skill starts | `emit_reset && emit_pipeline_start "new-parser"` |
| Knowledge loaded | `emit_agent_step "new-parser" "Knowledge loaded: N lenders in cookbook"` |
| Similar lender found | `emit_agent_step "new-parser" "Similar lender: <name> (N% match)"` |
| BA starts | `emit_pipeline_phase "ba" && emit_agent_start "ba" "Analyzing task"` |
| BA done | `emit_agent_complete "ba"` |
| User confirm | `emit_pipeline_phase "user-confirm"` |
| Architect starts | `emit_pipeline_phase "architect"` |
| Architect bead | `emit_agent_subtask "architect" "Bead N" "pending" "<desc>"` |
| Dev starts | `emit_pipeline_phase "dev" && emit_agent_start "dev" "Implementing"` |
| Dev bead done | `emit_agent_subtask "dev" "Bead N" "completed" "<summary>"` |
| Dev file | `emit_agent_file "dev" "<file>" "modified"` |
| QC starts | `emit_pipeline_phase "qc" && emit_agent_start "qc" "Testing"` |
| QC test | `emit_agent_test "qc" "<test>" "<PASS/FAIL>" "<details>"` |
| QC done | `emit_agent_complete "qc"` |
| Verify | `emit_pipeline_phase "verify"` |
| Learn | `emit_agent_step "new-parser" "Cookbook updated: <lender>"` |
| Retry | `emit_pipeline_retry N` |
| Done | `emit_pipeline_done` |

---

## KNOWLEDGE SYSTEM

### Three Knowledge Files

#### 1. Build Cookbook (`parser_build_cookbook.md`)
Per-lender build history — grows after every successful build:

```markdown
# Parser Build Cookbook

## PennyMac
- **type**: Conventional, QM
- **paths**: Tables=`<path>`, Rate=`<path>`, Adj=`<path>`
- **tables**: 8 total — 3 FICO×LTV, 2 condition, 3 validate
- **table_details**:
  - purchaseFicoLtv: ConditionTableInfo, FICO rows 780→620, LTV cols 60→97, gate: PM
  - refinanceFicoLtv: ConditionTableInfo, FICO rows 780→620, LTV cols 60→97, gate: ALL_REFINANCE
  - cashOutFicoLtv: ConditionTableInfo, FICO rows 780→620, LTV cols 60→80, gate: CASH_OUT
  - stateAdj: ConditionTableInfo, state conditions
  - propertyAdj: ConditionTableInfo, property type conditions
- **rate_products**: 6 — fixed(15), fixed(20), fixed(25), fixed(30), arm(5,1), arm(7,1)
- **lock_periods**: [15, 30, 45, 60]
- **adj_sections**: split by "Pricing Adjustments", then "LTV Adjustment"
- **adj_keyword**: "Pricing Adjustments"
- **modes**: [PURCHASE, RATE_TERM, CASH_OUT]
- **field_range**: field_1 through field_8
- **qc_issues**: ["field_5 duplicate on first attempt — was already used by cashOutFicoLtv"]
- **similar_to**: ["USBank", "WellsFargo"]
- **build_date**: 2026-03-15
- **build_tiers**: [dev: 2 beads, qc: 1 retry]

## LoganFinance
- **type**: NonQM
- **tables**: 5 total — 2 FICO×LTV, 1 DSCR, 2 validate
- **rate_products**: 4 — fixed(30), arm(5,1), arm(7,1), arm(10,1)
- **adj_sections**: split by "Base Price Adjustments"
- **special**: DSCR table uses loanAmount ranges instead of LTV
- **qc_issues**: ["crawlLabels count off by 1 — forgot sentinel rows"]
- **similar_to**: ["AngelOak", "Verus"]
```

#### 2. Pricing Domain Knowledge (`parser_pricing_knowledge.md`)
Accumulated understanding of pricing patterns:

```markdown
# Pricing Domain Knowledge

## Table Patterns by Loan Type

### Conventional (QM)
- **Always has**: FICO×LTV matrix (per purpose: Purchase, RateTerm, CashOut)
- **Usually has**: State adjustment, Property type adj, Subordinate financing
- **Lock periods**: typically [15, 30, 45, 60]
- **FICO ranges**: 780→620 (standard), some go to 580
- **LTV ranges**: 60→97 (Purchase), 60→90 (CashOut)
- **Modes**: PURCHASE, RATE_TERM, CASH_OUT (minimum)
- **Rate products**: fixed(15,20,25,30) + ARM variants

### NonQM
- **Always has**: FICO×LTV matrix (wider ranges 500-780)
- **Often has**: DSCR adjustment, Bank statement months adj, Prepay penalty adj
- **Lock periods**: typically [30, 45, 60]
- **FICO ranges**: 780→500 (wider than QM)
- **LTV ranges**: varies widely, often up to 80 max
- **Special**: 999.0 sentinel more common, more ValidateCalculator rules
- **Modes**: often just DEFAULT or by program name

### FHA
- **Always has**: FICO×LTV matrix with FHA_STREAMLINE column
- **Specific**: colRange includes FHA_STREAMLINE condition
- **Lock periods**: [15, 30, 45, 60]
- **Modes**: PURCHASE, RATE_TERM, FHA_STREAMLINE

### VA
- **Always has**: FICO×LTV matrix with IRRRL condition
- **Specific**: VA funding fee adjustment, IRRRL streamline
- **Modes**: PURCHASE, RATE_TERM, IRRRL, CASH_OUT

### USDA
- **Similar to**: Conventional but fewer LTV columns
- **Specific**: Rural property restrictions
- **Modes**: PURCHASE, RATE_TERM (usually no CashOut)

### High Balance / Jumbo
- **Always has**: Loan amount ranges in conditions
- **Specific**: loanAmount() ranges for tier breakpoints
- **Higher FICO requirements**: usually 700+ minimum

## Common Adjustment Table Types

### FICO × LTV Matrix
- Most common table type across all loan types
- Rows: FICO ranges (descending, sentinels: MAX_VALUE, MIN_VALUE)
- Cols: LTV ranges (ascending, sentinels: MIN_VALUE) or loan type conditions
- Use ConditionTableInfo with fico().crawlNote() rows
- NEVER use RangeTableInfo for FICO tables

### Condition List
- Single-column adjustments based on conditions
- Examples: State, Property type, Occupancy, Subordinate financing
- Use ConditionTableInfo with condition.setNote() rows

### Loan Amount Tiers
- Used in Jumbo/NonQM for amount-based adjustments
- Use loanAmount(min, max) ranges
- Often combined with FICO or LTV

## Common Mistakes (Learned from QC)

### Frequency: Very Common (>30% of first attempts)
1. **Forgetting allTables()**: Table defined but not added to allTables() → invisible to calculator
2. **FICO rows not descending**: Copy-paste from ratesheet which is ascending → must reverse
3. **crawlLabels count mismatch**: Must be rowRange count minus 2 (exclude MAX/MIN sentinels)
4. **field_N reuse**: Must grep existing fields before choosing next number

### Frequency: Common (10-30%)
5. **colRange count mismatch**: Must match actual value columns in ratesheet
6. **Mode not in resolver**: Adding .mode() to rate parser without updating getModeResolver()
7. **Wrong condition gate**: Using CONVENTIONAL when should be NON_JUMBO (includes HighBalance)

### Frequency: Occasional (<10%)
8. **Numeric colRange for FICO table**: Must use fico() ranges, not 0d/85d/95d
9. **Missing ValidateCalculator**: Eligibility rules from matrix not implemented
10. **Sheet name mismatch**: Must match EXACT tab name in ratesheet
```

#### 3. Infrastructure Index + Project Structure (existing memory)
Standard memory-first file resolution.

---

## STEP 0 — Knowledge Load

**Output:**
```
[new-parser 0/8] Loading knowledge base...
```

```bash
source /Users/trungthach/IdeaProjects/tools/agent-dashboard/emit.sh && emit_reset
emit_pipeline_start "new-parser"
```

Read in parallel:
```
$MOSO_MEMORY_DIR/project_structure.md
$MOSO_MEMORY_DIR/infrastructure_index.md
$BUILD_COOKBOOK
$PRICING_KNOWLEDGE
```

**If cookbook/pricing files missing** → create them with seed content (use the templates from the KNOWLEDGE SYSTEM section above as initial content). This is the first run — the agent starts learning from here.

**Output:**
```
[new-parser 0/8] ✓ Knowledge loaded — cookbook: <N> lenders, pricing: <N> loan types
```

```bash
emit_agent_step "new-parser" "Knowledge loaded: <N> lenders in cookbook"
```

### 0.2 Input Resolution

If `$ARGUMENTS` contains a Jira key or URL, extract it. Otherwise ask.

### 0.3 Environment Check

```bash
echo "JIRA_EMAIL=${JIRA_EMAIL:-MISSING} | JIRA_TOKEN=${JIRA_API_TOKEN:-MISSING}"
```

---

## STEP 1 — Smart BA Agent: Domain-Aware Analysis

**Output:**
```
[new-parser 1/8] BA — Analyzing ticket (domain-aware)...
```

```bash
source /Users/trungthach/IdeaProjects/tools/agent-dashboard/emit.sh
emit_pipeline_phase "ba" && emit_agent_start "ba" "Analyzing ticket"
```

### 1.1 Pre-Analysis: Classify Loan Type & Find Similar Lenders

**Before spawning BA agent**, the orchestrator does a quick classification from the Jira title:

```
1. Extract loan type from title: [QM], [NonQM], FHA, VA, USDA, Jumbo
2. Search cookbook for lenders with same type
3. Rank by similarity:
   - Same loan type = base match
   - Same action type (add program vs new parser) = bonus
   - Similar table count = bonus
4. Pick top 1-2 similar lenders as references
```

```bash
emit_agent_step "new-parser" "Similar lender: <name> (<type>, <N> tables)"
```

### 1.2 Spawn BA Agent with Domain Context

Spawn with: `subagent_type: "parser-ba"`, description: `"BA: domain-aware parser analysis"`

**Prompt template** — includes pricing knowledge + similar lender + cookbook hints:

```
You are the BA Lead for a mortgage ratesheet parser team. You have deep pricing domain knowledge.

## Dashboard Reporting
```bash
source /Users/trungthach/IdeaProjects/tools/agent-dashboard/emit.sh
emit_agent_step "ba" "<step description>"
```

## Your Task
Analyze Jira issue <JIRA_KEY> and produce a development plan.

## Pricing Domain Knowledge
<PASTE RELEVANT SECTION from parser_pricing_knowledge.md based on loan type>

For example, if this is a Conventional QM lender:
- Always expect: FICO×LTV matrices per purpose, State adj, Property adj
- Standard FICO ranges: 780→620
- Standard lock periods: 15, 30, 45, 60
- Standard modes: PURCHASE, RATE_TERM, CASH_OUT

Use this knowledge to VALIDATE what you see in the ratesheet. If the ratesheet
is missing something that's "always has" for this loan type, flag it as a risk.

## Similar Lender Reference
<IF SIMILAR LENDER FOUND>
The most similar lender in our cookbook is **<similar_lender>** (<type>):
- Tables: <table_details from cookbook>
- Rate products: <products>
- Adj sections: <sections>
- Modes: <modes>

Use this as a TEMPLATE — expect similar structure. Note any differences.
</IF>

## Step 1: Fetch Jira Task
```bash
curl -s -L -u "$JIRA_EMAIL:$JIRA_API_TOKEN" \
  "https://mosoteam.atlassian.net/rest/api/2/issue/<JIRA_KEY>?fields=summary,description,status,assignee,priority,attachment,comment,creator,created,updated,issuetype,labels,parent"
```

Download ALL attachments (images + ratesheets). Read images with Read tool.

## Step 2: Parse Task Requirements
From the Jira task + your domain knowledge, identify:
- **QM or NonQM**
- **Lender Name** (CamelCase)
- **Action Type**: Add program / Add adjustment / Add matrix / New parser
- **Loan Type**: Use pricing knowledge to predict expected tables
- **Rate Tables**: Compare against domain expectations
- **Adjustment Tables**: Compare against domain expectations
- **Matrix/Eligibility**: Compare against domain expectations
- **Differences from similar lender**: What's unique about this one?

## Step 3: Research Existing Code — Memory First

<IF MEMORY LOADED>
### Pre-Resolved Paths from Memory
<PASTE RELEVANT infrastructure_index.md section>
<PASTE RELEVANT project_structure.md section>
Check these paths DIRECTLY — do NOT search.
</IF>

<IF LEGACY MODE>
```bash
cd /Users/trungthach/IdeaProjects/packs/loan && ./lender-info.sh <LenderName>
```
</IF>

Read the existing parser files. Compare against similar lender's structure.

## Step 4: Write specs.md

Create `docs/changes/<JIRA_KEY>/specs.md` with:
- Problem statement
- Lender info
- **Domain expectations**: what tables/products are expected for this loan type
- **Ratesheet vs expectations**: what matches and what's different
- **Similar lender comparison**: differences from template
- Existing code status
- Screenshots analysis
- Key file paths
- Risk assessment (including domain expectation mismatches)
- Missing information

Return the full analysis to the orchestrator.
```

### After BA returns:

```bash
source /Users/trungthach/IdeaProjects/tools/agent-dashboard/emit.sh
emit_agent_complete "ba"
```

Cache lender_context with resolved paths.

---

## STEP 2 — User Confirmation

```bash
source /Users/trungthach/IdeaProjects/tools/agent-dashboard/emit.sh
emit_pipeline_phase "user-confirm"
```

Show specs.md summary + domain analysis:

> **BA Analysis:**
> [summary]
>
> **Domain Expectations** (for <loan_type>):
> - Expected tables: <list from pricing knowledge>
> - Found in ratesheet: <list from BA>
> - Missing: <any gaps>
>
> **Similar Lender**: <name> — <differences>
>
> Before Dev starts:
> 1. **Ratesheet file path**?
> 2. **Corrections** to analysis?
> 3. **Concerns**?

---

## STEP 3 — Architect: Template-Guided Beads

**Output:**
```
[new-parser 3/8] Architect — Building beads from template...
```

```bash
source /Users/trungthach/IdeaProjects/tools/agent-dashboard/emit.sh
emit_pipeline_phase "architect"
```

### 3.1 Load Reference Implementation

**If similar lender found in cookbook:**
- Read the similar lender's Tables class (from cookbook.paths)
- Use it as a TEMPLATE for bead structure
- Note: "Copy structure from <similar>, adjust ranges from new ratesheet"

**If no similar lender:**
- Use pricing domain knowledge for the loan type as guide
- Build beads from scratch based on BA analysis

### 3.2 Decompose into Beads (template-guided)

| Bead | Layer | Description |
|------|-------|-------------|
| **Bead 1** | `[tables]` | Tables class — guided by similar lender template |
| **Bead 2** | `[rate]` | Rate Parser — products from BA analysis |
| **Bead 3** | `[adj]` | Adjustment Parser — section keywords from ratesheet |
| **Bead 4** | `[test]` | Test files — expected counts |
| **Bead 5** | `[docs]` | Documentation |

### 3.3 Write beads_plan.md

Create `docs/changes/<JIRA_KEY>/beads_plan.md`:

Include for each bead:
- Exact file path (from lender_context)
- Specific changes
- **Template reference**: "Based on <similar_lender>'s <table>, adjust: <differences>"
- **Pitfall warnings**: from pricing knowledge common mistakes section
- Acceptance criteria

```markdown
# Beads Plan: <JIRA_KEY>

## Reference Lender: <similar_lender> (from cookbook)

## Pitfall Prevention (from pricing knowledge)
- [ ] Verify field_N uniqueness before assigning
- [ ] FICO rows descending (MAX_VALUE first)
- [ ] crawlLabels count = rowRange count - 2
- [ ] Every table in allTables() AND calculators()
- [ ] Every .mode() in getModeResolver()
- [ ] colRange count matches ratesheet columns

## Bead 1 — Tables [tables]
- [ ] 1.1 <tablesPath>: Add table definitions
  - Template: copy structure from <similar_lender>'s Tables
  - Adjust: FICO ranges from <ratesheet>, LTV ranges from <ratesheet>
  - New field_N: start from field_<next_available>
  ...

## Bead 2 — Rate Parser [rate]
...

## Bead 3 — Adj Parser [adj]
- Template: <similar_lender> splits by "<keyword>"
- This lender: check ratesheet for actual section headers
...

## Repomix Target Files
<paths>
+ <similar_lender Tables path> (for reference only — DO NOT modify)
```

Emit beads:
```bash
source /Users/trungthach/IdeaProjects/tools/agent-dashboard/emit.sh
emit_agent_subtask "architect" "Bead 1" "pending" "<desc>"
```

---

## STEP 4 — Dev Agent (Surgeon): Template-Guided + Pitfall Prevention

**Output:**
```
[new-parser 4/8] Dev — Implementing with template guidance...
```

```bash
source /Users/trungthach/IdeaProjects/tools/agent-dashboard/emit.sh
emit_pipeline_phase "dev" && emit_agent_start "dev" "Implementing beads"
```

### Spawn Dev Agent

Spawn with: `subagent_type: "parser-dev"`, description: `"Dev: template-guided implementation"`

**Prompt includes these extra sections vs basic implementation:**

```
## Reference Implementation (READ FIRST, DO NOT MODIFY)
<similar_lender>'s Tables class is at: <path>
Read this file FIRST to understand the pattern. Then implement the new lender
following the same structure, with adjustments from the beads plan.

## Pitfall Prevention Checklist
Before completing EACH bead, verify:
□ field_N is unique (grep existing fields: grep -o "field_[0-9]*" <tablesPath> | sort -u)
□ FICO rows start with Double.MAX_VALUE (descending)
□ LTV cols start with Double.MIN_VALUE (ascending)
□ crawlLabels count = rowRange entries - 2
□ Every table added to allTables()
□ Every table has TableCalculator in calculators()
□ Every .mode() exists in getModeResolver()
□ colRange count matches ratesheet value columns

## Known Issues from Similar Lenders
<IF cookbook has qc_issues for similar lender>
When building <similar_lender>, these QC issues occurred:
<list qc_issues>
Avoid making the same mistakes.
</IF>

## Memory-Resolved File Paths (do NOT search)
- New lender Tables: <tablesPath>
- New lender RateParser: <rateParserPath>
- New lender AdjParser: <adjParserPath>
- Reference Tables (read-only): <similar_lender_tablesPath>
- Tests: RateParserTest.java, AdjustmentParsersTest.java

## Beads Plan
<PASTE beads_plan.md>

## Implementation Rules
<standard critical rules + code patterns + conditions reference>
```

After Dev returns:
```bash
source /Users/trungthach/IdeaProjects/tools/agent-dashboard/emit.sh
emit_agent_complete "dev"
```

---

## STEP 5 — QC Agent: Test + Learn Failures

**Output:**
```
[new-parser 5/8] QC — Testing...
```

```bash
source /Users/trungthach/IdeaProjects/tools/agent-dashboard/emit.sh
emit_pipeline_phase "qc" && emit_agent_start "qc" "Testing"
```

Spawn with: `subagent_type: "parser-qc"`, description: `"QC: test + report failures"`

QC prompt includes memory-resolved paths + dev report + standard checklist.

**NEW: QC agent must categorize any failure:**
```
For each failure, report:
- Error type: CRAWL_MISMATCH / VALUE_MISMATCH / field_N / NullPointer / etc.
- Root cause category: [pitfall_known | new_pattern | template_mismatch | bug]
- Whether pitfall checklist would have prevented it: yes/no
```

After QC returns:
```bash
source /Users/trungthach/IdeaProjects/tools/agent-dashboard/emit.sh
emit_agent_complete "qc"  # or emit_agent_fail
```

---

## STEP 6 — Handle QC Result (Smart Retry)

**If QC PASSES → Step 7 (Verify).**

**If QC FAILS (max 3 retries):**

1. **Check if failure was a known pitfall:**
   - If yes → the Dev agent ignored the prevention checklist. Re-spawn with stronger emphasis.
   - If no → new pattern. Record it for future pricing knowledge updates.

2. **Check cookbook for same error on similar lender:**
   - If cookbook has a fix for this error type → include as hint

3. **Create targeted fix beads** (same escalation as /fix-parser):
   - Map error to specific file
   - Include past fix hint if available
   - Spawn parser-dev with fix beads

4. **After fix → re-run QC**

---

## STEP 7 — Verification Test

```bash
source /Users/trungthach/IdeaProjects/tools/agent-dashboard/emit.sh
emit_pipeline_phase "verify"
```

```bash
cd /Users/trungthach/IdeaProjects/packs/loan
mvn test -Dtest="AdjustmentParsersTest#test<LenderName>+RateParserTest#test<LenderName>" -Dratesheet.path=<PATH> 2>&1 | tail -20
```

If FAILS → back to Step 6 retry.
If PASSES → continue.

---

## STEP 8 — Learn + Finalize

### 8.1 LEARN — Update Knowledge Base

**This is what makes the agent smarter. ALWAYS execute this step.**

#### Update Build Cookbook

Add/update the lender entry in `$BUILD_COOKBOOK`:

```markdown
## <LenderName>
- **type**: <Conventional/NonQM/FHA/VA/USDA>, <QM/NonQM>
- **paths**: Tables=`<path>`, Rate=`<path>`, Adj=`<path>`
- **tables**: <N> total — <breakdown by type>
- **table_details**:
  <for each table: name, type, row structure, col structure, gate condition, field_N>
- **rate_products**: <N> — <list: fixed(30), arm(5,1), etc.>
- **lock_periods**: [<list>]
- **adj_sections**: split by "<keyword>"
- **adj_keyword**: "<exact keyword used>"
- **modes**: [<list>]
- **field_range**: field_<first> through field_<last>
- **qc_issues**: [<list of issues encountered during build>]
- **similar_to**: [<lenders with similar structure>]
- **build_date**: <today>
- **build_stats**: dev: <N> beads, qc: <N> retries
```

#### Update Pricing Knowledge

If this build revealed NEW patterns not in pricing knowledge:
- New table type not documented → add to "Table Patterns by Loan Type"
- New common mistake discovered → add to "Common Mistakes"
- New loan type variation → add section

If QC found a pitfall that the checklist should have prevented but didn't:
- Add it to the checklist with more specific wording

#### Update Similarity Index

If this lender is structurally similar to an existing lender:
- Add `similar_to` cross-references in both cookbook entries

```bash
source /Users/trungthach/IdeaProjects/tools/agent-dashboard/emit.sh
emit_agent_step "new-parser" "Cookbook updated: <lender> (<type>, <N> tables)"
```

### 8.2 Accept Expectations

```bash
cd /Users/trungthach/IdeaProjects/packs/loan
mvn test -Dtest=AdjustmentParsersTest#test<LenderName> -Dratesheet.path=<PATH> -Daccept -Daccept.new.adj 2>&1 | tail -10
```

### 8.3 Update RateParserTest Counts

```bash
mvn test -Dtest=RateParserTest#test<LenderName> -Dratesheet.path=<PATH> 2>&1 | grep -E "hasSize|assertRatesCount|Expected|Actual"
```
Update counts, re-run to confirm.

### 8.4 Copy Ratesheet + Update RatesheetFiles.java

### 8.5 Final Verification (without --ratesheet)

```bash
cd /Users/trungthach/IdeaProjects/packs/loan
mvn test -Dtest="AdjustmentParsersTest#test<LenderName>+RateParserTest#test<LenderName>" 2>&1 | tail -20
```

### 8.6 Summary Report

```bash
source /Users/trungthach/IdeaProjects/tools/agent-dashboard/emit.sh
emit_pipeline_done
```

```
## /new-parser Complete: <JIRA_KEY>

### Pipeline Summary
✓ Knowledge:  Loaded — cookbook: <N> lenders, pricing: <N> patterns
✓ Similar:    <similar_lender> used as template
✓ BA:         specs.md (domain-aware analysis)
✓ Architect:  beads_plan.md (template-guided, <N> beads)
✓ Dev:        <N> files changed, compile PASS
✓ QC:         All tests passed [after <M> retries]
✓ Verify:     Both tests pass together
✓ Learn:      Cookbook updated (+1 lender)
✓ Finalize:   Expectations accepted, ratesheet copied

### Intelligence Used
- Domain knowledge: <loan_type> patterns applied
- Template lender: <similar_lender> (saved ~<N>% analysis time)
- Pitfalls prevented: <N> (from checklist)
- New patterns learned: <N> (added to knowledge base)

### Files Changed
<list>

### Artifacts
docs/changes/<JIRA_KEY>/
  - specs.md
  - beads_plan.md

### Ready for commit
All tests passing. Run `/commit` when ready.
```

---

## Optimization Rules (Always Enforced)

1. **Knowledge-First**: Load cookbook + pricing knowledge before any analysis. Never build from scratch when a template exists.

2. **Similar Lender as Template**: Always search cookbook for structurally similar lenders. Use their Tables class as a reference implementation.

3. **Domain-Aware BA**: BA agent gets pricing knowledge injected. It validates ratesheet against domain expectations, not just describes what it sees.

4. **Pitfall Prevention**: Dev agent gets the prevention checklist BEFORE implementing. Cheaper to prevent than to fix after QC catches it.

5. **Learn from Every Build**: ALWAYS update cookbook, pricing knowledge, and similarity index after completion. This is non-negotiable.

6. **Learn from Failures Too**: QC failures get categorized and added to pricing knowledge's "Common Mistakes" section.

7. **Memory-First Paths**: cookbook paths → infrastructure_index → project_structure → lender-info.sh. Never broad search.

8. **No Re-reads**: specs.md and beads_plan.md stay in context. Reference lender read once by Dev.

9. **Targeted Agents**: Use parser-ba, parser-dev, parser-qc. Pass pre-resolved paths with "do NOT search".

10. **Verify Before Finalize**: Dev → QC → Verify → Learn → Finalize. Never skip verify or learn.
