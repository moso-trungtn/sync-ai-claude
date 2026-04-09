---
name: Verify sent emails via prospect conversation history
description: How to verify email notifications were sent in MOSO — check prospect dashboard conversation history
type: feedback
originSessionId: b461afe5-71e7-44a6-a1e8-f47d927c0b57
---
To verify sent emails in MOSO: after triggering the action (e.g., pulling credit), go back to the Prospect Dashboard, find the prospect by ID, and check the Conversation History. If the email was sent, it will appear as an entry there.

**Why:** There is no separate email log or test inbox. The conversation history on the prospect is the source of truth for sent notifications.

**How to apply:** During UI testing (/test-task), after any action that should trigger an email notification, navigate to the prospect's dashboard and check conversation history to verify the email was sent with the correct content.
