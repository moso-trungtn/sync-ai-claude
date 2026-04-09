---
name: Commit style for parser fixes
description: Commit per-task (not batched), short messages, no Co-Authored-By trailer
type: feedback
---

1. **Commit per Jira task, not batched.** Each MOSO-XXXXX gets its own commit in both moso-pricing and packs. Never combine multiple tasks into one commit like "MOSO-16038,16037,16036,16035,16034,15943: update ratesheets".

2. **No Co-Authored-By trailer.** Do not add `Co-Authored-By: Claude Opus ...` to commit messages.

3. **Keep commit messages short.** One line is fine, e.g. `MOSO-16038: fix JetAdvantage parser`.

**Why:** User saw batched commits in the IDE git panel and they were messy — hard to review, hard to revert per-task. Each task should be independently trackable.

**How to apply:** In the fix-parser pipeline Step 4j, commit after EACH task completes (not at the end). Commit only the files related to that specific lender. For moso-pricing changes, commit the parser/tables file right after fixing. For packs changes, commit the ratesheet + test refs + expectations right after verifying. Message format: `MOSO-XXXXX: fix <LenderName> parser` (short).
