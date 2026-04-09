---
name: Take screenshots during UI testing
description: During /test-task runs, take Playwright screenshots at each test verdict step and save locally for Jira upload
type: feedback
originSessionId: 74791657-005d-4598-9351-5c535d346078
---
During `/test-task` runs, always take a screenshot before presenting each test verdict to the user.

**Why:** User needs visual evidence for test cases, especially for multi-case or corner-case scenarios that are easy to miss. Screenshots help reviewers verify results without re-running tests.

**How to apply:**
1. Before each TC verdict, call `browser_take_screenshot` with `type: png`
2. Save to `docs/changes/<ISSUE_KEY>/screenshots/tc{N}-{pass|fail}-{short-description}.png`
3. In the final Jira comment, reference each screenshot by filename so the user knows which to upload
4. Example: `tc03-pass-fha-warning-shown.png`
5. At the end of testing, remind the user to upload screenshots from the `screenshots/` folder to the Jira ticket
