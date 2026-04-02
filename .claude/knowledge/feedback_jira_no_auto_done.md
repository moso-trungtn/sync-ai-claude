---
name: Never auto-transition Jira tasks to Done
description: Leave Jira tasks at "In Progress" after fixing — user reviews and closes them manually
type: feedback
---

Never auto-transition Jira tasks to "Done" status. After fixing a task, leave it at "In Progress" so the user can review the work and close it themselves.

**Why:** The user wants to review completed work before marking it as Done. Auto-closing tasks removes the review step and makes it look like the work was already verified.

**How to apply:** In any pipeline or skill that interacts with Jira (e.g., `/fix-parser`, `/new-parser`), after committing code, leave the task at "In Progress". Only transition to "Done" if the user explicitly asks to close/complete the task.
