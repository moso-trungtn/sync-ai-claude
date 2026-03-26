# Custom Agents & Skills for Moso

## Architecture: Agent + Skills (Hybrid)

We use a **single agent** (`mortgage-architect`) with **multiple skills** that load on demand.
Think of it like Spring Boot: the agent is the `ApplicationContext` (always loaded, lean),
and skills are `@Lazy @Bean` (loaded only when triggered by context).

```
.claude/
├── agents/
│   ├── README.md                    ← This file
│   └── mortgage-architect.md        ← The single architect agent
└── skills/
    ├── brainstorm/                  ← Architecture brainstorming & trade-offs
    ├── migration-planner/           ← moso → tera migration planning
    ├── codebase-explorer/           ← Deep system exploration & diagrams
    ├── impact-analyzer/             ← Change impact / blast radius analysis
    ├── compliance-checker/          ← Mortgage regulatory compliance (TRID/RESPA/ECOA)
    ├── onboarding-guide/            ← Developer onboarding documentation
    ├── business-code-analyzer/      ← Extract business logic from source code
    └── business-doc-verifier/       ← Verify docs against code truth
```

## Available Agent

### `mortgage-architect`
Senior technical architect agent with full code modification capabilities. Use for:
- Exploring and understanding the moso codebase
- Planning migration from moso → tera
- Designing and implementing new features with optimal performance
- Writing, editing, and refactoring code following project patterns
- Reviewing architectural decisions
- Identifying and fixing technical debt
- Implementing data migrations and fixes

## Custom Skills

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

## How to Use

### In Claude Code CLI

```bash
# Run as the architect
claude --agent mortgage-architect

# Or let Claude auto-delegate
claude
> "Brainstorm approaches for migrating the loan pipeline"
# Claude loads mortgage-architect, which triggers the brainstorm skill

# Explicitly invoke
claude
> @"mortgage-architect (agent)" analyze impact of changing Loan.status field
```

### In Cowork (Desktop)
The agent and skills are available when Claude Code tools are used within Cowork sessions.

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

## Creating More Skills

To add a new skill, create a directory in `.claude/skills/` with a `SKILL.md` file:

```yaml
---
name: your-skill-name
description: >
  When to trigger this skill. Be descriptive and include trigger phrases.
---

Your skill instructions go here...
```
