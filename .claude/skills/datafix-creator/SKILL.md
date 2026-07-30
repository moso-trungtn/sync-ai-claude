---
name: datafix-creator
description: >
  Multi-agent workflow for creating production-ready datafix scripts that modify Loan or Admin entities
  using updateEntityInRange and DatafixConfigManager. Use this skill whenever the user asks to:
  create a datafix, write a data migration, fix data in bulk, update entity fields in range,
  batch update loans/admins, write an upgrade script, create a data fix operation, or mentions
  "datafix", "data fix", "data migration", "bulk update", "updateEntityInRange", "DatafixConfigManager",
  "UpgradeManOp", "BaseUpgrader". Also trigger when the user describes a scenario that requires
  modifying existing database records in bulk — even if they don't use the word "datafix".
---

# Datafix Creator — Multi-Agent Workflow

This skill orchestrates 4 specialized agents in sequence to produce a production-ready datafix script.
The flow ensures correctness through separation of concerns: architecture design, business validation,
code implementation, and quality verification each happen independently.

## When to Use This Skill

Any time you need to create a Java class that extends `UpgradeManOp` or `BaseUpgrader` to modify
existing data in the database. Common scenarios:

- Backfill a new field across all loans/admins
- Fix incorrect data (date formats, null values, wrong statuses)
- Migrate data to a new schema
- Update labels, scores, or computed fields in bulk
- Process entities within a date range using `updateEntityInRange`

## Flow Overview

```
User Request → Step 1: Architect → Step 2: BA → Step 2.5: Ask User → Step 3: Developer → Step 4: QC → Final Output
                                                                        ↑                              │
                                                                        └────── if QC fails ────────────┘
```

**Step 1 — Architect**: Analyzes requirements, finds similar samples, designs the query + config + recommends split
strategy
**Step 2 — BA**: Validates business rules, defines scope and risk
**Step 2.5 — Ask User**: Confirm execution split strategy + terminal support (BEFORE coding)
**Step 3 — Developer**: Implements the Java class following the design + user's choices
**Step 4 — QC**: Reviews code, cross-checks with BA rules, verifies patterns

**Post-Generation (Step 2.5+)**: If user asks to split an already-generated datafix, refactor directly without
re-running the full flow.

## How to Execute This Flow

You are the **orchestrator**. You do NOT write code yourself — you spawn subagents (using the Agent tool)
for each step and pass outputs between them. Each subagent runs independently with its own reference file.

**Execution pattern:**

1. Spawn Architect agent → get design document
2. Spawn BA agent (pass Architect output) → get validation report
3. YOU ask the user clarifications (Step 2.5) — do NOT spawn an agent for this
4. Spawn Developer agent (pass Architect + BA + user choices) → get Java code
5. Spawn QC agent (pass Architect + BA + Developer code) → get QC report
6. If QC fails → spawn Developer agent again with QC issues → spawn QC again

### Step 1: Architect Agent

**Spawn an Agent** with this prompt structure:

```
You are the Architect agent for a datafix workflow.

Read these files FIRST:
1. moso-docs/skills/datafix-creator/references/architect-agent.md (your instructions)
2. [entity source files — see list below based on entity type]
3. moso-docs/docs/data/DATAFIX_GUIDE.md
4. moso-docs/docs/data/DATAFIX_CONFIG_USAGE.md
5. moso/src/test/java/com/p2/lenderrate/server/op/datafix/helper/DatafixConfigManager.java

Then follow architect-agent.md instructions to produce a design document for:
[PASTE USER'S ORIGINAL REQUEST HERE]

Search moso/src/test/java/com/p2/lenderrate/server/op/ for similar datafix scripts.
Output ONLY the design document in the format specified in architect-agent.md.
```

**Source files to include in the prompt based on entity type:**

For Loan entities:

- `packs/loan/src/main/java/com/mvu/loan/shared/entity/Loan.java` — field definitions (4,044 lines)
- `packs/loan/src/main/java/com/mvu/loan/shared/LoanUtils.java` — type checking and conditions (3,642 lines)
- `moso-docs/docs/features/LOAN_ENTITY_LIFECYCLE_GUIDE.md` — entity types, status machines
- `moso-docs/docs/features/LOAN_STATUS_TRANSITIONS.md` — status transitions

For Admin entities:

- `packs/loan/src/main/java/com/mvu/loan/shared/entity/Admin.java` — field definitions (4,491 lines)
- `base/core/src/main/java/com/mvu/core/shared/entity/Admin.java` — base Admin interface

### Step 2: BA Agent

**Spawn an Agent** with this prompt structure:

```
You are the BA (Business Analyst) agent for a datafix workflow.

Read these files FIRST:
1. moso-docs/skills/datafix-creator/references/ba-agent.md (your instructions)
2. [relevant feature guides — see ba-agent.md for the list]

Then validate the Architect's design below:

=== ARCHITECT'S DESIGN ===
[PASTE ARCHITECT AGENT'S FULL OUTPUT HERE]
=== END ===

Original user request: [PASTE USER'S ORIGINAL REQUEST HERE]

Output ONLY the BA validation report in the format specified in ba-agent.md.
```

The BA validates that the datafix won't break business flows. For Loan entities, this means checking
against loan lifecycle rules (status transitions, type detection, ownership). For Admin entities,
checking role constraints and active/suspended status.

### Step 2.5: Ask User — Clarifications Before Development

Before proceeding to the Developer, ask the user these questions:

#### A. Execution Split Strategy

Splitting the datafix into smaller, focused runs is a best practice because it:

- **Reduces run time** per execution (smaller dataset = faster)
- **Prioritizes high-value data** (active loans before dead loans)
- **Gives fine-grained control** (can stop after one split, adjust config, continue)
- **Easier to debug** if something goes wrong (smaller blast radius)

Ask the user: "Do you want to split execution by priority? Here are the common splits:"

**For Loan entity:**

| Split Dimension | High Priority (run first)                     | Low Priority (run after)                                        |
|-----------------|-----------------------------------------------|-----------------------------------------------------------------|
| Type            | Loan (`transaction_type = Loan`)              | Prospect (`transaction_type = null AND has_application = true`) |
| Status          | Active loans (`dead = false, funded = false`) | Inactive/Dead loans (`dead = true` or `funded = true`)          |
| Dead flag       | Not dead (`dead = false`)                     | Dead (`dead = true`)                                            |

**For Alert entity:**

| Split Dimension | High Priority                                     | Low Priority                              |
|-----------------|---------------------------------------------------|-------------------------------------------|
| Link type       | Linked to Loan/Prospect (`original_loan != null`) | Standalone alert (`original_loan = null`) |
| Status          | Active alerts (`alert_status = Active`)           | Other statuses (Disabled, Expired, etc.)  |

**For Lead entity:**

| Split Dimension | High Priority           | Low Priority                     |
|-----------------|-------------------------|----------------------------------|
| Type            | Lead (`is_lead = true`) | Loan/Prospect (separate datafix) |

**For Admin entity:**

| Split Dimension | High Priority                                   | Low Priority                                         | Config Method                    |
|-----------------|-------------------------------------------------|------------------------------------------------------|----------------------------------|
| Status          | Active (`available = true`)                     | Inactive (`available = false` or `suspended = true`) | `config.isActiveAdmin()`         |
| Branch          | Specific branch (`setBranchId(id)`)             | All branches (default)                               | `config.getBranchIds()`          |
| Admin Key       | Specific admins (`setAdminFolderIdFiles(keys)`) | All admins (default)                                 | `config.getAdminFolderIdFiles()` |

The user can combine splits. For example: "Run for active Loans first, then active Prospects,
then dead Loans." Each split becomes a separate `updateEntityInRange` call with its own query,
controlled by `DatafixConfigManager` flags (e.g., `config.isProspect()`, `config.isActiveAdmin()`).

The Developer implements the split as an if/else chain (see `CorrectLastTransactionDate.java`
pattern), and the operator runs the datafix multiple times with different config values.

#### B. Processing Strategy (for non-Loan/non-Admin entities)

If the target entity is NOT Loan or Admin (e.g., Branch, LoanProgram, DriveFile, etc.),
ask the user:

> "This entity type doesn't have a standard date range pattern. How do you want to process?"
>
> **Option A — Date range (updateEntityInRange):** Process in chunks by date field.
> Safer for large datasets — processes in circles, auto-commits per chunk.
> Requires a date field on the entity (e.g., `created`, `updated`).
>
> **Option B — Full query (find + loop):** Query all matching entities at once, loop and update.
> Simpler code, good for small datasets (< 10,000 records).
> Risk: large result sets can cause memory issues or long transactions.

If the user picks Option B, the Developer uses the "Full Query Template" (no updateEntityInRange).
If the user picks Option A, the Developer uses the standard template with the entity's date field.

**Note:** Loan and Admin entities should ALWAYS use `updateEntityInRange` (Option A) because
the datasets are typically large (100K+ records). Only offer Option B for other entity types.

#### C. Terminal Support

> "Do you want terminal support (ability to kill the datafix thread while running)?
> This adds a threadName + terminal() check pattern from TransferDrivesOp."

If yes → Developer uses the "With Terminal Support" template.
If no → Developer uses the standard template.

### Step 2.5+ (Post-Generation): Split an Existing Datafix

If the user has already generated a datafix and then asks to split it (e.g., "chia ra chạy
Loan trước, Prospect sau" or "tách active và inactive"), the Developer should:

1. Take the existing Java class
2. Refactor the single query into multiple query methods (e.g., `findActiveLoans`, `findDeadLoans`)
3. Add the split control using `DatafixConfigManager` flags
4. Update the commented config block to show each split option
5. Keep everything else unchanged (Bundle, update function, logging, error handling)

This is a common operation — the user generates a datafix, reviews it, then decides to split for
production safety. Spawn a Developer agent directly (skip Architect/BA) with the existing code +
split instructions. Then spawn QC to verify.

### Step 3: Developer Agent

**Spawn an Agent** with this prompt structure:

```
You are the Developer agent for a datafix workflow.

Read this file FIRST:
1. moso-docs/skills/datafix-creator/references/developer-agent.md (your instructions)

Then implement the datafix based on:

=== ARCHITECT'S DESIGN ===
[PASTE ARCHITECT AGENT'S FULL OUTPUT HERE]
=== END ===

=== BA VALIDATION REPORT ===
[PASTE BA AGENT'S FULL OUTPUT HERE]
=== END ===

=== USER'S CHOICES (from Step 2.5) ===
- Execution split: [user's choice — e.g., "Loan first, then Prospect"]
- Processing strategy: [Option A (updateEntityInRange) or Option B (full query)]
- Terminal support: [Yes / No]
=== END ===

Follow developer-agent.md instructions exactly. Pay special attention to:
- Code Style Rules (config.getX() directly, commented config inline, no intermediate variables)
- Template choice based on terminal support decision
- Split pattern based on user's execution split choice

Output ONLY the complete Java class file, ready to compile.
```

### Step 4: QC Agent

**Spawn an Agent** with this prompt structure:

```
You are the QC agent for a datafix workflow.

Read this file FIRST:
1. moso-docs/skills/datafix-creator/references/qc-agent.md (your instructions)

Then review the Developer's code against the Architect's design and BA's report:

=== ARCHITECT'S DESIGN ===
[PASTE ARCHITECT AGENT'S FULL OUTPUT HERE]
=== END ===

=== BA VALIDATION REPORT ===
[PASTE BA AGENT'S FULL OUTPUT HERE]
=== END ===

=== DEVELOPER'S CODE ===
[PASTE DEVELOPER AGENT'S FULL JAVA CODE HERE]
=== END ===

Run the COMPLETE QC checklist from qc-agent.md. Output the QC report in the specified format.
If any BLOCKER or CRITICAL issues found, set overall result to FAIL.
```

**If QC result is FAIL:**

Spawn a new Developer agent with the QC issues added:

```
You are the Developer agent. Fix the QC issues below in the existing code.

Read: moso-docs/skills/datafix-creator/references/developer-agent.md

=== CURRENT CODE ===
[PASTE THE FAILED CODE]
=== END ===

=== QC ISSUES TO FIX ===
[PASTE QC REPORT'S FINDINGS — only BLOCKER and CRITICAL items]
=== END ===

Fix ALL issues. Output the corrected Java class file.
```

Then spawn QC again to verify. Repeat until QC passes (max 2 retries, then ask user for help).

## Key Technical Context

### updateEntityInRange — 4 Variants

```java
// 1. Default (7-day circle, created field)
updateEntityInRange(startDate, endDate, bundle, querySupplier, updateFunction)

// 2. Custom circle
updateEntityInRange(startDate, endDate, circle, bundle, querySupplier, updateFunction)

// 3. Custom date field
updateEntityInRange(startDate, endDate, dateField, circle, bundle, querySupplier, updateFunction)

// 4. With date adjustment control
updateEntityInRange(startDate, endDate, field, circle, adjustDate, bundle, querySupplier, updateFunction)
```

### DatafixConfigManager — Key Methods

```java
DatafixConfigManager config = new DatafixConfigManager();

// === Common params (all datafixes) ===
config.setStartDate(year, month, day)       // or setStartDate(Date)
      .setEndDate(year, month, day)         // or setEndDate(Date)
      .setLoanProcessingCircle(-7)          // negative = backwards

// === Loan entity params ===
      .setIsProspect(true/false)            // filter: Loan vs Prospect
      .setAlertStatus(AlertStatus.X)        // filter: alert status

// === Admin entity params ===
      .setActiveAdmin(true/false)           // filter: active vs inactive admin
      .setBranchIds(List<Long>)             // filter: specific branch IDs
      .setBranchId(Long)                    // filter: single branch ID
      .setAdminFolderIdFiles(List<String>)  // filter: specific admin keys (HasId.key)

// === Terminal support ===
      .addTerminate("threadName")           // kill a running thread
      .terminateThread("name", params...)   // kill with generated key
      .terminateAllThreads()                // kill ALL running threads

      .save();                              // single DB write
```

### Scenario System — Multiple Configs per Datafix

The scenario system allows a single datafix class to have **multiple configuration sets**, each stored
as a separate `TemporaryConfiguration` entity keyed by `(class_name, scenario_index)`. This is useful
when you need to run the same datafix with different date ranges or parameters (e.g., split by quarter).

**All scenario operations are namespace-scoped.** Caller MUST be inside the target namespace via `runInNS(NS_ID, ...)`.

```java
// === Scenario CRUD (static methods) ===
DatafixConfigManager.loadScenario("com.example.MyDatafix", 1)   // load or create scenario 1
DatafixConfigManager.listScenarios("com.example.MyDatafix")     // list all scenarios (sorted by index)
DatafixConfigManager.clearScenario("com.example.MyDatafix", 2)  // delete one scenario
DatafixConfigManager.clearScenarios("com.example.MyDatafix")    // delete ALL scenarios for a class

// === Scenario constructors ===
new DatafixConfigManager("com.example.MyDatafix", 2)            // load/create scenario 2
new DatafixConfigManager(bundle, "com.example.MyDatafix", 2)    // with custom bundle

// === Scenario identity (instance methods) ===
config.getClassName()       // fully qualified class name (null for legacy id=1L)
config.getScenarioIndex()   // 1-based index (null for legacy id=1L)
config.delete()             // delete entity from DB entirely (vs clear() which resets values)
```

**Backward compatibility:** `new DatafixConfigManager()` still loads legacy `id=1L`. Existing datafixes are unaffected.

### ScenarioArgs — Parse Scenario Index from Maven Args

```java
// In main(): -Dexec.args="run 2" → parses scenario_index=2
ScenarioArgs scenario = ScenarioArgs.parse(args, MyDatafix.class);
DatafixConfigManager config = scenario.loadConfig();

scenario.getIndex()      // 2
scenario.getClassName()  // "com.p2.lenderrate.server.op.v3_55_0.MyDatafix"
scenario.isDefault()     // false (true when no index provided, defaults to 1)
```

Import: `com.p2.lenderrate.server.op.datafix.helper.ScenarioArgs`

**Admin filtering methods explained:**

- `getBranchIds()` — returns configured branch IDs, or ALL branch IDs if none configured
- `setBranchId(Long)` — shortcut to set a single branch
- `getAdminFolderIdFiles()` / `setAdminFolderIdFiles(List<String>)` — filter by admin key (uses `HasId.key`), useful for
  targeting specific admins by their unique key
- `isActiveAdmin()` / `setActiveAdmin(boolean)` — filter active vs inactive admins

### Standard Datafix Structure

Code style: keep main method compact — pass `config.getX()` directly as function args, no
intermediate variables. Commented config setup sits right above the runtime read.

```java
public class MyDataFix extends UpgradeManOp {
    public static void main(String[] args) {
        new AppServer().runRemoteOn(PROD, () -> {
            NS.runOnActiveCompaniesNS(() -> {
                // new DatafixConfigManager()
                //        .setStartDate(2026, 0, 1)
                //        .setEndDate(2025, 0, 1)
                //        .setLoanProcessingCircle(-7)
                //        .save();

                try {
                    DatafixConfigManager config = new DatafixConfigManager();
                    run(config.getStartDate(), config.getEndDate(), config.getLoanProcessingCircle());
                } catch (Exception e) {
                    e.printStackTrace();
                }
                return null;
            });
            return "succeeded";
        });
    }

    private static void run(Date startDate, Date endDate, int circle) {
        Bundle bundle = new Bundle();
        bundle.disableEvents(true);
        bundle.disableSideEffect(true);

        updateEntityInRange(startDate, endDate, Loan.created, circle, bundle,
            () -> bundle.find(Loan.TYPE)
                .whereEquals(Loan.transaction_type, TransactionType.Loan),
            entity -> {
                // Update logic here
                return entity.isChanged();
            }
        );
    }
}
```

### With Terminal Support (from TransferDrivesOp pattern)

Adds threadName + `terminal()` check so the datafix can be killed remotely while running.

```java
public class MyDataFix extends UpgradeManOp {
    private String threadName = "";

    public static void main(String[] args) {
        new AppServer().runRemoteOn(PROD, () -> {
            NS.runOnActiveCompaniesNS(() -> {
                // new DatafixConfigManager()
                //        .setStartDate(2026, 0, 1)
                //        .setEndDate(2025, 0, 1)
                //        .setLoanProcessingCircle(-7)
                //        .save();

                try { new MyDataFix().execute(); }
                catch (Exception e) { e.printStackTrace(); }
                return null;
            });
            return "succeeded";
        });
    }

    private void execute() {
        DatafixConfigManager config = new DatafixConfigManager();

        // Generate unique thread name for this run
        threadName = config.generateThreadKey("myDataFix",
                config.getLoanProcessingCircle(), config.getStartDate(), config.getEndDate());
        out.println("Thread: " + threadName);

        run(config.getStartDate(), config.getEndDate(), config.getLoanProcessingCircle());
    }

    private boolean terminal() {
        return new DatafixConfigManager().isTerminal(this.threadName);
    }

    // To kill: new DatafixConfigManager().addTerminate("myDataFix_-7_...").save();
}
```

### Full Query Template (No updateEntityInRange)

For small entity types where the user chose Option B (query all at once):

```java
public class MyDataFix extends UpgradeManOp {
    public static void main(String[] args) {
        new AppServer().runRemoteOn(PROD, () -> {
            NS.runOnActiveCompaniesNS(() -> {
                try {
                    run();
                } catch (Exception e) {
                    e.printStackTrace();
                }
                return null;
            });
            return "succeeded";
        });
    }

    private static void run() {
        Bundle bundle = new Bundle();
        bundle.disableEvents(true);
        bundle.disableSideEffect(true);

        List<Bean> entities = bundle.find(EntityType.TYPE)
                // Add filter conditions
                .list();

        out.println("Found " + entities.size() + " entities to process");
        int updated = 0;
        int skipped = 0;

        for (Bean entity : entities) {
            try {
                if (processEntity(entity)) {
                    updated++;
                } else {
                    skipped++;
                }
            } catch (Exception e) {
                out.println("ERROR processing " + entity.id() + ": " + e.getMessage());
                skipped++;
            }
        }

        bundle.commit();
        out.println("Done | updated: " + updated + " | skipped: " + skipped);
    }

    private static boolean processEntity(Bean entity) {
        // Update logic here
        return entity.isChanged();
    }
}
```

**Important:** This template uses `bundle.commit()` at the end — all changes are saved in one batch.
For large datasets (> 5,000 records), recommend using `updateEntityInRange` instead.

### With Scenario System (Multiple Configs per Datafix)

Use this when the same datafix needs to run with different configuration sets (e.g., split by quarter,
by branch, or by date range). Extends `BaseUpgrader` and uses `runInNS()` for namespace scoping.

```java
public class MyDataFix extends BaseUpgrader implements MosoServers {
    public static void main(String[] args) {
        new AppServer().runRemoteOn(PROD, () -> {
            runInNS(LOAN_FACTORY, () -> {
                String command = args.length > 0 ? args[0] : "run";

                switch (command) {
                    case "setup":
                        // Seed scenarios (run once before executing)
                        String cls = MyDataFix.class.getName();
                        DatafixConfigManager.clearScenarios(cls);
                        DatafixConfigManager.loadScenario(cls, 1)
                            .setStartDate(2025, 0, 1).setEndDate(2025, 3, 1)
                            .setLoanProcessingCircle(-5).save();
                        DatafixConfigManager.loadScenario(cls, 2)
                            .setStartDate(2025, 3, 1).setEndDate(2025, 6, 1)
                            .setLoanProcessingCircle(-5).save();
                        out.println("Scenarios seeded.");
                        break;

                    case "run":
                        // Parse scenario index: -Dexec.args="run 2"
                        ScenarioArgs scenario = ScenarioArgs.parse(args, MyDataFix.class);
                        DatafixConfigManager config = scenario.loadConfig();
                        out.println("Running scenario " + scenario.getIndex());
                        config.printConfiguration();
                        run(config.getStartDate(), config.getEndDate(),
                            config.getLoanProcessingCircle());
                        break;

                    case "list":
                        List<DatafixConfigManager> scenarios =
                            DatafixConfigManager.listScenarios(MyDataFix.class.getName());
                        scenarios.forEach(s -> s.printConfiguration());
                        break;

                    case "clear":
                        DatafixConfigManager.clearScenarios(MyDataFix.class.getName());
                        out.println("All scenarios cleared.");
                        break;
                }
                return null;
            });
            return "done";
        });
    }

    private static void run(Date startDate, Date endDate, int circle) {
        Bundle bundle = new Bundle();
        bundle.disableEvents(true);
        bundle.disableSideEffect(true);

        updateEntityInRange(startDate, endDate, Loan.created, circle, bundle,
            () -> bundle.find(Loan.TYPE)
                .whereEquals(Loan.transaction_type, TransactionType.Loan),
            entity -> {
                // Update logic here
                return entity.isChanged();
            }
        );
    }
}
```

**Usage:** Run `setup` once to seed configs, then `run 1`, `run 2`, etc. for each scenario.
Use `list` to inspect, `clear` to clean up.

## Real Examples for Reference

Three proven patterns exist in the codebase:

1. **CorrectLastTransactionDate** (`op/v3_54_0/`) — Loan field format fix with Prospect/Loan split
2. **SetCreditScoreToAlertLF** (`op/v3_53_0/`) — Alert processing with LoanUtils, labels query
3. **SyncAdminToAIMCPByCloud** (`op/v3_45_0/`) — Admin entity processing with updateLargeEntity

The Architect agent should find the most similar sample to the user's request and use it as a template.
