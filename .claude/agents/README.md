# Custom Agents & Skills for Moso

## Architecture: Agent + Skills (Hybrid)

We use **focused agents** with **multiple skills** that load on demand.
Think of it like Spring Boot: each agent is a `@Configuration` class (scoped context),
and skills are `@Lazy @Bean` (loaded only when triggered by context).

```
.claude/
├── agents/
│   ├── README.md                    ← This file
│   ├── mortgage-architect.md        ← Technical architect agent
│   ├── business-analyst.md          ← Business analyst agent
│   ├── qa-tester.md                 ← QA engineer agent
│   └── tech-lead.md                 ← Tech lead agent (code + review)
├── helpers/
│   └── scan-project.sh             ← Codebase scan script (builds index)
├── index/                           ← Per-machine index data (gitignored)
└── skills/
    ├── codebase-indexer/            ← Infrastructure index lifecycle management
    ├── brainstorm/                  ← Architecture brainstorming & trade-offs
    ├── migration-planner/           ← moso → tera migration planning
    ├── codebase-explorer/           ← Deep system exploration & diagrams
    ├── impact-analyzer/             ← Change impact / blast radius analysis
    ├── compliance-checker/          ← Mortgage regulatory compliance (TRID/RESPA/ECOA)
    ├── onboarding-guide/            ← Developer onboarding documentation
    ├── business-code-analyzer/      ← Extract business logic from source code
    └── business-doc-verifier/       ← Verify docs against code truth
```

## Available Agents

### `mortgage-architect`
Senior technical architect agent with full code modification capabilities. Use for:
- Exploring and understanding the moso codebase
- Planning migration from moso → tera
- Designing and implementing new features with optimal performance
- Writing, editing, and refactoring code following project patterns
- Reviewing architectural decisions
- Identifying and fixing technical debt
- Implementing data migrations and fixes

### `business-analyst`
Senior business analyst agent for requirements and process analysis. Use for:
- Analyzing and documenting business processes and workflows
- Writing user stories with detailed acceptance criteria
- Extracting business rules from moso source code into human-readable format
- Gap analysis between moso features and tera implementation
- Compliance analysis (TRID, RESPA, ECOA, HMDA)
- Preparing stakeholder-facing documentation (non-technical)
- Mapping loan origination lifecycle, pricing logic, and pipeline flows
- Defining KPIs and reporting requirements
- **HTML reports** — auto-generates polished, browser-viewable reports with Mermaid diagrams
- **Jira integration** — creates Stories/Bugs/Tasks from analysis (gap → stories, compliance → bugs)
- **Confluence publishing** — pushes reports to Confluence for team-wide visibility

### `qa-tester`
Senior QA engineer for testing and validation. Use for:
- Writing test cases (unit, integration, E2E) with realistic mortgage data
- Validating acceptance criteria from business-analyst output
- Migration validation — comparing moso vs tera behavior for same inputs
- Compliance testing (TRID timing, fee tolerances, RESPA, ECOA)
- Test coverage analysis and gap identification
- Bug report generation with severity classification
- **HTML test reports** — test matrix with pass/fail badges and coverage summary

### `tech-lead`
Tech lead who can both **write code** and **review code**. Use for:
- Writing production-quality Java/Spring Boot code
- Code review with structured checklist (correctness, performance, security, style)
- PR review (full diff analysis, commit message validation)
- Code audits (anti-pattern detection, technical debt scoring)
- Review verdicts: ✅ APPROVED / 🔄 REQUEST CHANGES / ❌ REJECTED
- Mentoring with before/after examples and complexity analysis
- Orchestrating other agents and reviewing their outputs

## Workflows

Full workflow definitions with diagrams are in `.claude/agents/workflows.md`.

### Workflow 1: Jira Task → Analysis → Implement → Review → QA

**Trigger:** "analyze MOSO-1234", "work on this Jira task"

```
 Jira Task
    │
    ├──────────────────────┐
    ▼                      ▼
 mortgage-architect    business-analyst     ← Step 1: Parallel Analysis
 (tech challenges)     (business rules)
    │                      │
    └──────────┬───────────┘
               ▼
         USER CHECKPOINT                    ← "Proceed with implementation?"
               │
               ▼
          tech-lead                         ← Step 2: Implement
          (code + tests)
          │  ◄──► architect / BA if blocked
          │
          ▼
     Self-Review                            ← tech-lead reviews own code
          │
          ▼
     mortgage-architect                     ← Step 3: Architecture Review
     ✅ → QA  │  🔄 → back to tech-lead  │  ❌ → back to Step 1
              │
              ▼
         qa-tester                          ← Step 4: Test & Validate
         ✅ → Finalize  │  ❌ → back to tech-lead
              │
              ▼
         Finalize                           ← Step 5: Update Jira + Confluence
```

### Workflow 2: Add Feature → BA → Architect → Implement → Review → QA

**Trigger:** "add feature X", "new feature", "I want to build..."

```
 Feature Request
    │
    ▼
 business-analyst                           ← Step 1: Requirements
 (user stories, acceptance criteria)
    │
    ▼
 USER CHECKPOINT                            ← "Requirements OK?"
    │
    ▼
 mortgage-architect                         ← Step 2: Solution Design
 (brainstorm solutions, pick best)
 │  ◄──► BA if needs business clarification
    │
    ▼
 USER CHECKPOINT                            ← "Approve this design?"
    │
    ▼
 Same as Workflow 1 Steps 2-5               ← Implement → Review → QA → Finalize
```

### Workflow 3: Bug Fix / Hotfix

**Trigger:** "fix this bug", "hotfix", "production issue", Jira bug ticket

```
 Bug Report
    │
    ▼
 tech-lead (diagnose root cause)            ← Step 1: No BA needed
    │
    ▼
 mortgage-architect (impact analysis)       ← Step 2: Is the fix safe?
 ✅ SAFE → continue  │  ❌ DANGEROUS → rethink
    │
    ▼
 tech-lead (implement fix + regression test) ← Step 3
    │
    ▼
 qa-tester (regression testing)             ← Step 4
    │
    ▼
 Finalize (update Jira bug ticket)          ← Step 5
```

### Workflow 4: Code Audit / Tech Debt

**Trigger:** "audit module X", "tech debt review", "code quality check"

```
 mortgage-architect (explore & inventory)    ← Step 1
    │
    ▼
 tech-lead (code audit: anti-patterns,      ← Step 2
            performance, security)
    │
    ▼
 business-analyst (business impact +        ← Step 3
                   effort estimation)
    │
    ▼
 Combined HTML audit report                  ← Step 4
 + Jira tasks + Confluence page
```

### Workflow 5: Parser Fix (moso-pricing)

**Trigger:** "parser issue", "rate sheet error", "fix parser for [lender]"

```
 Parser Issue
    │
    ▼
 mortgage-architect (diagnose parser logic)  ← Step 1
    │
    ▼
 tech-lead (implement parser fix)            ← Step 2
    │
    ▼
 qa-tester (test with sample rate sheets)    ← Step 3
    │
    ▼
 Finalize (update lender docs)               ← Step 4
```

### Workflow Summary

| # | Workflow | Trigger | Lead Agent |
|---|---------|---------|------------|
| 1 | Jira Task | Jira ticket | BA + architect (parallel) |
| 2 | Add Feature | "add feature X" | BA first |
| 3 | Bug Fix | bug report | tech-lead first |
| 4 | Code Audit | "audit", "tech debt" | architect first |
| 5 | Parser Fix | parser/ratesheet issue | architect first |

### How to Trigger

**In Cowork (Desktop)** — just describe what you need:
- "Analyze MOSO-1234" → Workflow 1
- "Add feature for automatic rate alerts" → Workflow 2
- "Fix this bug: loan calculator returns wrong APR" → Workflow 3
- "Audit the follow-up tracking module" → Workflow 4
- "Parser broken for AmeriHome rate sheet" → Workflow 5

**In Claude Code CLI:**
```bash
claude --agent business-analyst    # Workflow 1 & 2
claude --agent mortgage-architect  # Workflow 4 & 5
claude --agent tech-lead           # Workflow 3, implementation, review
claude --agent qa-tester           # Testing in any workflow
```

## Custom Skills

### `codebase-indexer`
Build and maintain the infrastructure index for fast O(1) class/file lookup. Eliminates 60-80% of Grep/Glob calls by providing keyword → file path mapping. Outputs:
- `moso-docs/docs/core/INFRASTRUCTURE_INDEX.md` — Class paths by concern (git-tracked, relative paths)
- `.claude/index/project_stats.md` — File counts per module (gitignored, per-machine)

**Triggers:** "/index", "rebuild index", "refresh index", "scan project"

### `brainstorm`
Architecture brainstorming and trade-off analysis. Generates:
- Multiple distinct approaches with Java analogies
- Decision matrix with weighted scoring
- Stress-testing of the winning option
- Mermaid diagrams for visual comparison

**Triggers:** "brainstorm", "pros and cons", "should we use X or Y", "what are our options"

### `migration-planner`
Detailed planning for moso → tera migration. Generates:
- Module inventory with business logic extraction
- Entity/operation/event listener mapping (moso pattern → tera pattern)
- Data migration strategy (including dual-write approach)
- Phased migration plan with effort estimates
- Dependency graph and risk register

**Triggers:** "plan migration", "migrate module X", "moso to tera", "convert to Spring Boot"

### `codebase-explorer`
Deep system exploration at multiple zoom levels:
- **Satellite View:** Full system module map and dependencies
- **City View:** Single module deep dive (entities, operations, flows)
- **Street View:** Single entity tracing (inheritance, fields, lifecycle)
- **Follow That Car:** End-to-end flow tracing ("what happens when X")
- **Traffic Map:** Dependency graphing and hotspot detection

**Triggers:** "explore codebase", "map architecture", "how does X connect to Y", "show me the big picture"

### `impact-analyzer`
Change impact assessment before making modifications:
- Direct impact (first-order references)
- Indirect impact (event cascades, query dependencies, UI bindings)
- Risk scoring per component (LOW → CRITICAL)
- Pre-change checklist

**Triggers:** "impact analysis", "blast radius", "what depends on X", "is it safe to change Y"

### `compliance-checker`
Mortgage regulatory compliance verification:
- TRID (fee tolerance, disclosure timing)
- RESPA (settlement procedures)
- ECOA (fair lending, adverse action)
- HMDA (data reporting)

**Triggers:** "compliance check", "TRID", "RESPA", "is this compliant", "fee tolerance"

### `onboarding-guide`
Progressive developer onboarding documentation:
- Level 1: Big picture (Day 1)
- Level 2: Core concepts with Spring Boot comparisons (Day 1-2)
- Level 3: First task walkthrough (Day 2-3)
- Level 4: Common patterns (Week 1)
- Level 5: Module-specific deep dive (Week 2+)

**Triggers:** "onboard new developer", "getting started guide", "explain to someone new"

### `business-code-analyzer`
Extract business logic directly from source code:
- Entity hierarchy discovery
- Operation and event listener inventory
- Business rule extraction with conditions and actions
- Data flow mapping

**Triggers:** "analyze business logic", "what does this module do", "extract business rules"

### `business-doc-verifier`
Verify documentation against actual code:
- Extract verifiable claims from docs
- Cross-check against code (CONFIRMED / CONFLICT / GAP / STALE)
- Per-document health score
- Priority fix recommendations

**Triggers:** "verify docs", "audit documentation", "are docs up to date"

## Also Available: Engineering Plugin Skills

These generic engineering skills complement the custom mortgage-specific skills:

| Skill | Use Case |
|---|---|
| `engineering:architecture` | Architecture Decision Records (ADR) |
| `engineering:system-design` | System design from requirements |
| `engineering:tech-debt` | Tech debt identification & prioritization |
| `engineering:code-review` | Security, performance, correctness review |
| `engineering:debug` | Structured debugging sessions |
| `engineering:testing-strategy` | Test strategy design |
| `engineering:deploy-checklist` | Pre-deployment verification |
| `engineering:documentation` | Technical writing |

## Creating More Agents or Skills

**New agent** — create a `.md` file in `.claude/agents/`:
```yaml
---
name: your-agent-name
description: >
  When to use this agent. Be descriptive.
tools:
  - Read
  - Grep
  - Glob
  - Bash
  - Agent
  - Edit
  - Write
model: sonnet
memory: project
---

Your agent instructions go here...
```

**New skill** — create a directory in `.claude/skills/` with a `SKILL.md` file:
```yaml
---
name: your-skill-name
description: >
  When to trigger this skill. Be descriptive and include trigger phrases.
---

Your skill instructions go here...
```
