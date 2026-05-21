---
name: Separate LF namespace from other namespaces in migration ops
description: When writing UpgradeManOp/migration scripts that iterate namespaces, run LoanFactory (LF) namespace separately from other company namespaces instead of lumping them together via runOnActiveCompaniesNS
type: feedback
originSessionId: bb6079cb-4b9c-46da-baf0-f3df2e51b5be
---
When writing migration / UpgradeManOp scripts (e.g. `MigrateVisaTypes`-style ops) that iterate namespaces, **separate the LoanFactory (LF) namespace from other tenant namespaces**. Don't run them together in a single `NS.runOnActiveCompaniesNS(...)` block.

**Why:** LF and tenant namespaces have different data shapes, scale, and risk profiles. Mixing them in one loop makes failures harder to isolate, makes it impossible to skip/rerun just one side, and can let an LF-specific error abort the tenant migration (or vice versa).

**How to apply:**
- In migration `main()` methods, branch the run into two explicit phases: one for LF, one for active companies.
- Wrap each in its own try/catch and logging prefix so failures are attributable.
- Reference example to fix: `moso/src/test/java/com/p2/lenderrate/server/op/v3_56_0/MigrateVisaTypes.java:46-47` currently calls `runOnActiveCompaniesNS` only — it should also handle LF as a separate step (and the comment "Runs on ALL namespaces including LoanFactory" is misleading).
