# Agent Workflows

This file defines the standard workflows that orchestrate multiple agents together.
When a user triggers a workflow, the orchestrating agent (or Claude itself) follows the
steps below, spawning sub-agents as needed.

Think of workflows like Spring Boot's `@TransactionalEventListener` chains —
each step publishes an event that triggers the next agent in the pipeline.

---

## Infrastructure Index Check (ALL Workflows)

Before starting ANY workflow, the first agent in the pipeline must:

1. Read `.claude/index/project_stats.md` → check if exists and staleness
2. If stale (file count drift >5) or missing → run `bash .claude/helpers/scan-project.sh`
3. Read `moso-docs/docs/core/INFRASTRUCTURE_INDEX.md` → loaded into context for entire pipeline

All file lookups in the pipeline follow the Memory-First Lookup Rule (see `.claude/skills/codebase-indexer/SKILL.md`):
Index → Stats → Feature Docs → Targeted Glob → Targeted Grep.

---

## Per-Ticket Artifacts

When working on a Jira ticket or code task, all agents output to:

```
.claude/outputs/changes/<ISSUE_KEY>/
├── specs.md              ← BA: business requirements, acceptance criteria
├── tech_analysis.md      ← Architect: technical investigation, solution design
├── beads_plan.md         ← Dev Lead: implementation plan, bead decomposition
├── pr_description.md     ← DevOps: PR-ready description with changes table
└── review_notes.md       ← Review feedback trail (architect + QA verdicts)
```

**Rules:**
- Each agent writes to its corresponding file in the `<ISSUE_KEY>/` folder
- Create the folder when the first agent runs (if it doesn't exist)
- Subsequent agents READ outputs of previous agents from this folder
- This folder is NOT committed to git — ephemeral working artifacts
- If task has no ISSUE_KEY (chat-context) → use `TASK-<YYYYMMDD>` placeholder

---

## Workflow 1: Jira Task Analysis → Implementation → Review

**Trigger:** User provides a Jira task/ticket (e.g., "analyze MOSO-1234", "work on this Jira task")

```
┌─────────────────────────────────────────────────────────────────────┐
│  STEP 1: PARALLEL ANALYSIS                                         │
│                                                                     │
│  ┌──────────────────┐    ┌──────────────────┐                      │
│  │ mortgage-architect│    │ business-analyst  │                      │
│  │                  │    │                   │                      │
│  │ • Read Jira task │    │ • Read Jira task  │                      │
│  │ • Trace code in  │    │ • Extract business│                      │
│  │   moso codebase  │    │   requirements    │                      │
│  │ • Identify tech  │    │ • Map business    │                      │
│  │   challenges     │    │   rules & flows   │                      │
│  │ • Assess impact  │    │ • Check compliance│                      │
│  │ • Propose tech   │    │ • Write acceptance│                      │
│  │   solutions      │    │   criteria        │                      │
│  └────────┬─────────┘    └────────┬──────────┘                      │
│           │                       │                                  │
│           └───────────┬───────────┘                                  │
│                       ▼                                              │
│  ┌─────────────────────────────────┐                                │
│  │ COMBINED ANALYSIS REPORT (HTML) │                                │
│  │ • Technical challenges          │                                │
│  │ • Business requirements         │                                │
│  │ • Recommended solution          │                                │
│  │ • Acceptance criteria           │                                │
│  │ • Risk assessment               │                                │
│  └────────────────┬────────────────┘                                │
│                   ▼                                                  │
│  ┌─────────────────────────────────┐                                │
│  │ USER CHECKPOINT                 │                                │
│  │ "Here's the analysis. Proceed  │                                │
│  │  with implementation?"          │                                │
│  └────────────────┬────────────────┘                                │
└───────────────────┼─────────────────────────────────────────────────┘
                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│  STEP 2: IMPLEMENTATION                                             │
│                                                                     │
│  ┌──────────────────┐                                              │
│  │ tech-lead        │                                              │
│  │                  │                                              │
│  │ • Receives the   │                                              │
│  │   combined       │                                              │
│  │   analysis       │                                              │
│  │ • Implements     │     ┌──────────────────┐                     │
│  │   the solution   │     │ mortgage-architect│                     │
│  │ • Writes tests   │◄───►│ or               │ Consult if blocked  │
│  │ • Compile verify │     │ business-analyst  │ on tech/business    │
│  │                  │     └──────────────────┘ questions            │
│  │ • If blocked:    │                                              │
│  │   asks architect │                                              │
│  │   or BA          │                                              │
│  └────────┬─────────┘                                              │
│           ▼                                                         │
│  ┌─────────────────────────────────┐                                │
│  │ SELF-REVIEW                     │                                │
│  │ tech-lead reviews own code      │                                │
│  │ using review checklist          │                                │
│  │ (correctness, performance,      │                                │
│  │  security, style)               │                                │
│  │ Fixes any issues found          │                                │
│  └────────────────┬────────────────┘                                │
└───────────────────┼─────────────────────────────────────────────────┘
                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│  STEP 3: ARCHITECTURE REVIEW                                        │
│                                                                     │
│  ┌──────────────────┐                                              │
│  │ mortgage-architect│                                              │
│  │                  │                                              │
│  │ • Reviews code   │                                              │
│  │   from tech-lead │                                              │
│  │ • Checks:        │                                              │
│  │   - Architecture │                                              │
│  │     patterns     │                                              │
│  │   - Performance  │                                              │
│  │   - Migration    │                                              │
│  │     correctness  │                                              │
│  │   - Data model   │                                              │
│  │     integrity    │                                              │
│  │                  │                                              │
│  │ • Verdict:       │                                              │
│  │   ✅ APPROVED    │──→ Continue to Step 4                        │
│  │   🔄 CHANGES    │──→ Back to tech-lead (Step 2)                 │
│  │   ❌ REJECTED   │──→ Back to Step 1 (rethink)                   │
│  └────────┬─────────┘                                              │
└───────────┼─────────────────────────────────────────────────────────┘
            ▼
┌─────────────────────────────────────────────────────────────────────┐
│  STEP 4: QA VALIDATION                                              │
│                                                                     │
│  ┌──────────────────┐                                              │
│  │ qa-tester        │                                              │
│  │                  │                                              │
│  │ • Writes test    │                                              │
│  │   cases from     │                                              │
│  │   acceptance     │                                              │
│  │   criteria       │                                              │
│  │ • Edge case      │                                              │
│  │   testing        │                                              │
│  │ • Migration      │                                              │
│  │   parity check   │                                              │
│  │   (moso vs tera) │                                              │
│  │ • Compliance     │                                              │
│  │   validation     │                                              │
│  │                  │                                              │
│  │ • Result:        │                                              │
│  │   ✅ ALL PASS    │──→ Continue to Step 5                        │
│  │   ❌ FAILURES   │──→ Back to tech-lead (Step 2)                 │
│  └────────┬─────────┘                                              │
└───────────┼─────────────────────────────────────────────────────────┘
            ▼
┌─────────────────────────────────────────────────────────────────────┐
│  STEP 5: FINALIZE                                                   │
│                                                                     │
│  • Update Jira task status                                          │
│  • Publish final report to Confluence                               │
│  • Generate HTML summary with all review/test results               │
│  • Link everything: Jira ↔ Confluence ↔ Code                       │
└─────────────────────────────────────────────────────────────────────┘
```

### Step-by-step instructions for the orchestrator:

**Step 1: Parallel Analysis**
1. Read the Jira task using `getJiraIssue` to get full context
2. Spawn `mortgage-architect` agent: "Analyze this Jira task from a technical perspective. Trace the relevant code in the moso codebase, identify technical challenges, assess impact, and propose solutions."
3. Spawn `business-analyst` agent (in parallel): "Analyze this Jira task from a business perspective. Extract business requirements, map business rules and workflows, check compliance implications, and write acceptance criteria."
4. Combine both outputs into a single analysis report (HTML)
5. Present to user for approval before proceeding

**Step 2: Implementation**
1. Spawn `tech-lead` agent with the combined analysis: "Implement the solution based on this analysis. Follow the recommended approach. Write production-quality code with tests."
2. If the tech-lead encounters a technical question → spawn `mortgage-architect` as sub-agent to consult
3. If the tech-lead encounters a business question → spawn `business-analyst` as sub-agent to consult
4. After implementation, tech-lead runs compile verification (mvn compile + self-correct loop, max 3 attempts)
5. After verification passes, tech-lead performs self-review using its review checklist
6. Tech-lead fixes any issues found during self-review

**Step 3: Architecture Review**
1. Spawn `mortgage-architect` agent: "Review this code implementation. Check architecture patterns, performance, migration correctness, and data model integrity. Issue a verdict."
2. If 🔄 REQUEST CHANGES → send feedback to tech-lead, go back to Step 2
3. If ❌ REJECTED → go back to Step 1 with architect's concerns
4. If ✅ APPROVED → proceed to Step 4

**Step 4: QA Validation**
1. Spawn `qa-tester` agent: "Write and run test cases based on the acceptance criteria. Test edge cases. Validate migration parity between moso and tera behavior."
2. If tests fail → send failure details to tech-lead, go back to Step 2
3. If all pass → proceed to Step 5

**Step 5: Finalize**
1. Update Jira task with results (transition status, add comment with summary)
2. Publish report to Confluence
3. Generate final HTML summary linking all artifacts

---

## Workflow 2: Add Feature → Analysis → Design → Implementation

**Trigger:** User says "add feature X", "new feature", "I want to build...", or provides a requirement

```
┌─────────────────────────────────────────────────────────────────────┐
│  STEP 1: BUSINESS ANALYSIS                                          │
│                                                                     │
│  ┌──────────────────┐                                              │
│  │ business-analyst  │                                              │
│  │                  │                                              │
│  │ • Understand the │                                              │
│  │   feature request│                                              │
│  │ • Check if moso  │                                              │
│  │   has similar    │                                              │
│  │   logic already  │                                              │
│  │ • Define scope   │                                              │
│  │ • Write user     │                                              │
│  │   stories        │                                              │
│  │ • Acceptance     │                                              │
│  │   criteria       │                                              │
│  │ • Compliance     │                                              │
│  │   implications   │                                              │
│  │ • Generate HTML  │                                              │
│  │   requirements   │                                              │
│  │   report         │                                              │
│  └────────┬─────────┘                                              │
│           ▼                                                         │
│  ┌─────────────────────────────────┐                                │
│  │ USER CHECKPOINT                 │                                │
│  │ "Here are the requirements.     │                                │
│  │  Anything to add/change?"       │                                │
│  └────────────────┬────────────────┘                                │
└───────────────────┼─────────────────────────────────────────────────┘
                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│  STEP 2: SOLUTION DESIGN                                            │
│                                                                     │
│  ┌──────────────────┐                                              │
│  │ mortgage-architect│                                              │
│  │                  │                                              │
│  │ • Receives BA's  │                                              │
│  │   requirements   │                                              │
│  │ • Brainstorms    │     ┌──────────────────┐                     │
│  │   multiple       │     │ business-analyst  │                     │
│  │   solutions      │◄───►│                   │ Validate business   │
│  │ • Evaluates      │     │                   │ feasibility of      │
│  │   trade-offs     │     └──────────────────┘ each approach        │
│  │ • Picks best     │                                              │
│  │   approach       │                                              │
│  │ • Designs:       │                                              │
│  │   - API contract │                                              │
│  │   - Data model   │                                              │
│  │   - Service      │                                              │
│  │     architecture │                                              │
│  │ • Generates      │                                              │
│  │   design doc     │                                              │
│  └────────┬─────────┘                                              │
│           ▼                                                         │
│  ┌─────────────────────────────────┐                                │
│  │ USER CHECKPOINT                 │                                │
│  │ "Here's the proposed design.    │                                │
│  │  Approve this approach?"        │                                │
│  └────────────────┬────────────────┘                                │
└───────────────────┼─────────────────────────────────────────────────┘
                    ▼
            ┌───────────────┐
            │ Same as        │
            │ Workflow 1     │
            │ Steps 2-5      │
            │ (Implement →   │
            │  Self-review → │
            │  Arch review → │
            │  QA → Finalize)│
            └───────────────┘
```

### Step-by-step instructions for the orchestrator:

**Step 1: Business Analysis**
1. Spawn `business-analyst` agent: "Analyze this feature request. Check if moso has similar logic. Define scope, write user stories with acceptance criteria, check compliance implications. Generate an HTML requirements report."
2. Present the requirements report to user for feedback
3. If user has changes → update and re-present
4. If user approves → proceed to Step 2

**Step 2: Solution Design**
1. Spawn `mortgage-architect` agent with BA's requirements: "Design the technical solution for this feature. Brainstorm multiple approaches, evaluate trade-offs, and recommend the best one. Include API contracts, data model, and service architecture."
2. If architect needs business clarification → spawn `business-analyst` as sub-agent
3. Present the design to user for approval
4. If user has concerns → architect revises
5. If user approves → proceed to implementation

**Steps 3-6: Same as Workflow 1, Steps 2-5**
Follow the implementation → self-review → architecture review → QA → finalize pipeline.

---

## Workflow Rules

### User Checkpoints
Every workflow has **user checkpoints** between major phases. Never auto-proceed from analysis to implementation without user confirmation. This prevents wasted effort if requirements are misunderstood.

### Feedback Loops
When a reviewer (architect or tech-lead) requests changes:
- The feedback goes back to the **implementing agent** (not to the user)
- The implementing agent fixes and resubmits
- The reviewer only re-reviews the **changed parts**
- Maximum 3 feedback loops before escalating to the user

### Escalation
If any step loops more than 3 times without resolution:
1. Generate an HTML report of all attempts and feedback
2. Present to the user with the unresolved issues
3. Ask the user to make a decision

### Agent Communication
Agents pass context to each other via:
1. **Structured summaries** — The orchestrator extracts key points from one agent's output and passes them to the next
2. **File references** — Agents reference specific files and line numbers so the next agent can read them directly
3. **HTML reports** — Shared artifact that all agents can reference

### Parallel Execution
Where agents don't depend on each other's output, run them in parallel:
- Workflow 1, Step 1: architect + BA analyze simultaneously
- Workflow 1, Step 4: QA can start writing test cases while architect reviews (QA runs tests after approval)

---

## Workflow 3: Bug Fix / Hotfix

**Trigger:** User reports a bug, provides a bug ticket, says "fix this bug", "hotfix", "production issue", or describes unexpected behavior.

Key difference from Workflow 1: No BA analysis needed — this is a fix, not a feature. Tech-lead goes first to diagnose, architect validates the fix won't cause side effects.

```
┌─────────────────────────────────────────────────────────────────────┐
│  STEP 1: DIAGNOSE                                                   │
│                                                                     │
│  ┌──────────────────┐                                              │
│  │ tech-lead        │                                              │
│  │                  │                                              │
│  │ • Read bug report│                                              │
│  │   (Jira or user  │                                              │
│  │   description)   │                                              │
│  │ • Reproduce the  │                                              │
│  │   issue (trace   │                                              │
│  │   code path)     │                                              │
│  │ • Identify root  │                                              │
│  │   cause          │                                              │
│  │ • Propose fix    │                                              │
│  │   approach       │                                              │
│  └────────┬─────────┘                                              │
│           ▼                                                         │
│  ┌─────────────────────────────────┐                                │
│  │ ROOT CAUSE REPORT               │                                │
│  │ • What: the bug behavior        │                                │
│  │ • Where: exact file:line        │                                │
│  │ • Why: root cause explanation   │                                │
│  │ • Fix: proposed approach        │                                │
│  │ • Risk: what else could break   │                                │
│  └────────────────┬────────────────┘                                │
└───────────────────┼─────────────────────────────────────────────────┘
                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│  STEP 2: IMPACT VALIDATION                                          │
│                                                                     │
│  ┌──────────────────┐                                              │
│  │ mortgage-architect│                                              │
│  │                  │                                              │
│  │ • Review the     │                                              │
│  │   proposed fix   │                                              │
│  │ • Run impact     │                                              │
│  │   analysis       │                                              │
│  │   (blast radius) │                                              │
│  │ • Check for side │                                              │
│  │   effects        │                                              │
│  │   (save cascade, │                                              │
│  │   entity deps,   │                                              │
│  │   index impact)  │                                              │
│  │ • Validate fix   │                                              │
│  │   won't break    │                                              │
│  │   migration      │                                              │
│  │                  │                                              │
│  │ • Verdict:       │                                              │
│  │   ✅ SAFE        │──→ Proceed to Step 3                         │
│  │   ⚠️ RISKY      │──→ Suggest safer alternative                 │
│  │   ❌ DANGEROUS   │──→ Back to tech-lead with concerns           │
│  └────────┬─────────┘                                              │
└───────────┼─────────────────────────────────────────────────────────┘
            ▼
┌─────────────────────────────────────────────────────────────────────┐
│  STEP 3: IMPLEMENT FIX                                              │
│                                                                     │
│  ┌──────────────────┐                                              │
│  │ tech-lead        │                                              │
│  │                  │                                              │
│  │ • Implement the  │                                              │
│  │   approved fix   │                                              │
│  │ • Write          │                                              │
│  │   regression     │                                              │
│  │   test that      │                                              │
│  │   catches the    │                                              │
│  │   original bug   │                                              │
│  │ • Compile verify │                                              │
│  │ • Self-review    │                                              │
│  └────────┬─────────┘                                              │
└───────────┼─────────────────────────────────────────────────────────┘
            ▼
┌─────────────────────────────────────────────────────────────────────┐
│  STEP 4: QA REGRESSION                                              │
│                                                                     │
│  ┌──────────────────┐                                              │
│  │ qa-tester        │                                              │
│  │                  │                                              │
│  │ • Verify the bug │                                              │
│  │   is fixed       │                                              │
│  │ • Run regression │                                              │
│  │   tests on       │                                              │
│  │   affected area  │                                              │
│  │ • Test edge      │                                              │
│  │   cases around   │                                              │
│  │   the fix        │                                              │
│  │ • Check that     │                                              │
│  │   nothing else   │                                              │
│  │   broke          │                                              │
│  │                  │                                              │
│  │ • Result:        │                                              │
│  │   ✅ ALL PASS    │──→ Finalize                                  │
│  │   ❌ REGRESSION  │──→ Back to tech-lead (Step 3)                │
│  └────────┬─────────┘                                              │
└───────────┼─────────────────────────────────────────────────────────┘
            ▼
┌─────────────────────────────────────────────────────────────────────┐
│  STEP 5: FINALIZE                                                   │
│                                                                     │
│  • Update Jira bug ticket (status, fix description, root cause)     │
│  • Add regression test reference to ticket                          │
│  • Link to related issues if the bug was caused by another change   │
└─────────────────────────────────────────────────────────────────────┘
```

### Step-by-step instructions for the orchestrator:

**Step 1: Diagnose**
1. If a Jira ticket is provided, read it using `getJiraIssue`
2. Spawn `tech-lead` agent: "Diagnose this bug. Trace the code path, identify the root cause, and propose a fix approach. Report: What, Where (file:line), Why (root cause), Fix (approach), Risk (side effects)."
3. Present root cause report to user

**Step 2: Impact Validation**
1. Spawn `mortgage-architect` agent: "Review this proposed bug fix. Run impact analysis — check blast radius, save cascading effects, entity dependencies, index impact. Is the fix safe?"
2. If ⚠️ RISKY → architect proposes safer alternative, tech-lead adjusts
3. If ❌ DANGEROUS → go back to Step 1 with architect's concerns
4. If ✅ SAFE → proceed

**Step 3: Implement Fix**
1. Spawn `tech-lead` agent: "Implement the approved fix. Write a regression test that reproduces the original bug and verifies the fix. Self-review before submitting."
2. Tech-lead self-reviews

**Step 4: QA Regression**
1. Spawn `qa-tester` agent: "Verify the bug is fixed. Run regression tests on the affected area. Test edge cases around the fix. Confirm nothing else broke."
2. If ❌ REGRESSION → back to tech-lead
3. If ✅ ALL PASS → proceed

**Step 5: Finalize**
1. Update Jira bug ticket with fix details and root cause
2. Link regression test to the ticket

---

## Workflow 4: Code Audit / Tech Debt Review

**Trigger:** "audit module X", "tech debt review", "code quality check", "review the health of...", or periodic scheduled review.

This workflow is for proactive code quality assessment — no specific bug or feature, just improving the codebase.

```
┌─────────────────────────────────────────────────────────────────────┐
│  STEP 1: EXPLORE & INVENTORY                                        │
│                                                                     │
│  ┌──────────────────┐                                              │
│  │ mortgage-architect│                                              │
│  │                  │                                              │
│  │ • Explore the    │                                              │
│  │   target module  │                                              │
│  │ • Map all classes│                                              │
│  │   operations,    │                                              │
│  │   entities       │                                              │
│  │ • Identify       │                                              │
│  │   dependencies   │                                              │
│  │ • Flag potential │                                              │
│  │   problem areas  │                                              │
│  │ • Check migration│                                              │
│  │   readiness      │                                              │
│  └────────┬─────────┘                                              │
└───────────┼─────────────────────────────────────────────────────────┘
            ▼
┌─────────────────────────────────────────────────────────────────────┐
│  STEP 2: CODE AUDIT                                                 │
│                                                                     │
│  ┌──────────────────┐                                              │
│  │ tech-lead        │                                              │
│  │                  │                                              │
│  │ • Scan for anti- │                                              │
│  │   patterns       │                                              │
│  │   (CLAUDE.md     │                                              │
│  │   checklist)     │                                              │
│  │ • Measure method │                                              │
│  │   sizes          │                                              │
│  │ • Check test     │                                              │
│  │   coverage gaps  │                                              │
│  │ • Security scan  │                                              │
│  │   (PII handling, │                                              │
│  │   input          │                                              │
│  │   validation)    │                                              │
│  │ • Performance    │                                              │
│  │   hotspots       │                                              │
│  │   (N+1, O(n²),   │                                              │
│  │   blocking I/O)  │                                              │
│  │ • Score each     │                                              │
│  │   finding by     │                                              │
│  │   severity       │                                              │
│  └────────┬─────────┘                                              │
└───────────┼─────────────────────────────────────────────────────────┘
            ▼
┌─────────────────────────────────────────────────────────────────────┐
│  STEP 3: BUSINESS IMPACT ASSESSMENT                                  │
│                                                                     │
│  ┌──────────────────┐                                              │
│  │ business-analyst  │                                              │
│  │                  │                                              │
│  │ • Map tech debt  │                                              │
│  │   to business    │                                              │
│  │   impact         │                                              │
│  │ • Prioritize:    │                                              │
│  │   which debt     │                                              │
│  │   costs the most │                                              │
│  │   (user impact,  │                                              │
│  │   compliance     │                                              │
│  │   risk, dev      │                                              │
│  │   velocity)      │                                              │
│  │ • Estimate       │                                              │
│  │   effort to fix  │                                              │
│  │   (sprints)      │                                              │
│  └────────┬─────────┘                                              │
└───────────┼─────────────────────────────────────────────────────────┘
            ▼
┌─────────────────────────────────────────────────────────────────────┐
│  STEP 4: REPORT & ACTION                                            │
│                                                                     │
│  • Generate combined HTML audit report:                             │
│    - Executive summary (module health score: A/B/C/D/F)             │
│    - Findings table (severity, category, file:line, fix effort)     │
│    - Severity distribution chart                                     │
│    - Top 5 priority fixes with ROI justification                    │
│    - Migration readiness score                                       │
│  • Create Jira tasks for each finding (prioritized)                 │
│  • Publish to Confluence under "Tech Debt / [Module Name]"          │
└─────────────────────────────────────────────────────────────────────┘
```

### Step-by-step instructions for the orchestrator:

**Step 1: Explore & Inventory**
1. Spawn `mortgage-architect` agent with `codebase-explorer` skill: "Explore [module]. Map all classes, operations, entities, and dependencies. Flag potential problem areas. Assess migration readiness."

**Step 2: Code Audit**
1. Spawn `tech-lead` agent with architect's inventory: "Audit this module. Scan for all anti-patterns in CLAUDE.md. Measure method sizes. Check test coverage gaps. Security scan. Performance hotspots. Score each finding by severity."

**Step 3: Business Impact Assessment**
1. Spawn `business-analyst` agent with tech-lead's findings: "Map these technical debt findings to business impact. Prioritize by cost (user impact, compliance risk, dev velocity). Estimate fix effort in sprints."

**Step 4: Report & Action**
1. Combine all outputs into a single HTML audit report with health scoring
2. Create Jira tasks for each prioritized finding
3. Publish to Confluence

---

## Workflow 5: Parser Fix (moso-pricing)

**Trigger:** "parser issue", "rate sheet parsing error", "fix parser for [lender]", "ratesheet update", or any issue in `moso-pricing/`.

This workflow follows the specialized parser fix process documented in `moso-pricing/CLAUDE.md` and `packs/loan/CLAUDE.md`, but orchestrated through agents.

```
┌─────────────────────────────────────────────────────────────────────┐
│  STEP 1: DIAGNOSE PARSER ISSUE                                      │
│                                                                     │
│  ┌──────────────────┐                                              │
│  │ mortgage-architect│                                              │
│  │                  │                                              │
│  │ • Read moso-     │                                              │
│  │   pricing/       │                                              │
│  │   CLAUDE.md      │                                              │
│  │ • Read lender    │                                              │
│  │   docs in moso-  │                                              │
│  │   pricing/docs/  │                                              │
│  │   lenders/       │                                              │
│  │ • Trace parser   │                                              │
│  │   logic for the  │                                              │
│  │   affected       │                                              │
│  │   lender         │                                              │
│  │ • Identify what  │                                              │
│  │   changed in the │                                              │
│  │   rate sheet     │                                              │
│  │   format         │                                              │
│  │ • Propose fix    │                                              │
│  │   approach       │                                              │
│  └────────┬─────────┘                                              │
└───────────┼─────────────────────────────────────────────────────────┘
            ▼
┌─────────────────────────────────────────────────────────────────────┐
│  STEP 2: IMPLEMENT PARSER FIX                                       │
│                                                                     │
│  ┌──────────────────┐                                              │
│  │ tech-lead        │                                              │
│  │                  │                                              │
│  │ • Implement the  │     ┌──────────────────┐                     │
│  │   parser fix     │     │ mortgage-architect│                     │
│  │ • Follow parser  │◄───►│                   │ Consult on parser   │
│  │   patterns from  │     │                   │ architecture and    │
│  │   moso-pricing/  │     └──────────────────┘ lender-specific     │
│  │   docs/parser-   │                          quirks              │
│  │   patterns.md    │                                              │
│  │ • Self-review    │                                              │
│  └────────┬─────────┘                                              │
└───────────┼─────────────────────────────────────────────────────────┘
            ▼
┌─────────────────────────────────────────────────────────────────────┐
│  STEP 3: PARSER TESTING                                             │
│                                                                     │
│  ┌──────────────────┐                                              │
│  │ qa-tester        │                                              │
│  │                  │                                              │
│  │ • Run parser     │                                              │
│  │   tests with     │                                              │
│  │   sample rate    │                                              │
│  │   sheets         │                                              │
│  │ • Use ai-parser  │                                              │
│  │   mode (see      │                                              │
│  │   packs/loan/    │                                              │
│  │   CLAUDE.md)     │                                              │
│  │ • Compare parsed │                                              │
│  │   output vs      │                                              │
│  │   expected       │                                              │
│  │   values         │                                              │
│  │ • Test with      │                                              │
│  │   multiple rate  │                                              │
│  │   sheet versions │                                              │
│  │   (old + new     │                                              │
│  │   format)        │                                              │
│  │                  │                                              │
│  │ • Result:        │                                              │
│  │   ✅ ALL PASS    │──→ Finalize                                  │
│  │   ❌ MISMATCH   │──→ Back to tech-lead (Step 2)                 │
│  └────────┬─────────┘                                              │
└───────────┼─────────────────────────────────────────────────────────┘
            ▼
┌─────────────────────────────────────────────────────────────────────┐
│  STEP 4: FINALIZE                                                   │
│                                                                     │
│  • Update lender documentation in moso-pricing/docs/lenders/        │
│  • Update Jira ticket with fix details                              │
│  • If parser pattern changed: update parser-patterns.md             │
└─────────────────────────────────────────────────────────────────────┘
```

### Step-by-step instructions for the orchestrator:

**Step 1: Diagnose**
1. Spawn `mortgage-architect` agent: "Read `moso-pricing/CLAUDE.md` and the lender-specific docs. Trace the parser logic for [lender]. Identify what changed in the rate sheet format. Propose a fix approach."

**Step 2: Implement**
1. Spawn `tech-lead` agent: "Implement the parser fix following patterns in `moso-pricing/docs/parser-patterns.md`. Consult architect if you encounter lender-specific quirks."

**Step 3: Test**
1. Spawn `qa-tester` agent: "Run parser tests using the ai-parser mode (see `packs/loan/CLAUDE.md`). Test with sample rate sheets. Compare parsed output vs expected values. Test both old and new format rate sheets."
2. If ❌ MISMATCH → back to tech-lead
3. If ✅ ALL PASS → proceed

**Step 4: Finalize**
1. Update lender documentation
2. Update Jira ticket
3. Update parser-patterns.md if a new pattern was introduced

---

## Workflow Summary

| # | Workflow | Trigger | Lead Agent | Agents Involved |
|---|---------|---------|------------|-----------------|
| 1 | Jira Task Analysis | Jira ticket | orchestrator | BA + architect → tech-lead → architect (review) → QA |
| 2 | Add Feature | "add feature", requirement | BA | BA → architect → tech-lead → architect (review) → QA |
| 3 | Bug Fix / Hotfix | bug report, "fix this" | tech-lead | tech-lead → architect (impact) → tech-lead (fix) → QA |
| 4 | Code Audit | "audit", "tech debt" | architect | architect → tech-lead → BA → combined report |
| 5 | Parser Fix | parser/ratesheet issue | architect | architect → tech-lead → QA |
