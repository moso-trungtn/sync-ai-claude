---
name: test-task
description: General-purpose Playwright UI testing for MOSO. Fetches Jira ticket, generates test cases using BA/architect agents, walks through them step-by-step in the browser. Usage: /test-task [MOSO-XXXXX]
argument-hint: "[MOSO-XXXXX] (optional Jira key, will prompt if omitted)"
allowed-tools: Bash, Read, Write, Edit, Glob, Grep, Agent, mcp__claude_ai_Atlassian__getJiraIssue, mcp__plugin_playwright_playwright__browser_navigate, mcp__plugin_playwright_playwright__browser_snapshot, mcp__plugin_playwright_playwright__browser_click, mcp__plugin_playwright_playwright__browser_fill_form, mcp__plugin_playwright_playwright__browser_wait_for, mcp__plugin_playwright_playwright__browser_handle_dialog, mcp__plugin_playwright_playwright__browser_select_option, mcp__plugin_playwright_playwright__browser_type, mcp__plugin_playwright_playwright__browser_press_key, mcp__plugin_playwright_playwright__browser_tabs, mcp__plugin_playwright_playwright__browser_hover
---

# /test-task — MOSO Playwright UI Testing

You are a **QA test engineer** for the MOSO mortgage platform. You take a Jira ticket, understand what was built, generate test cases, and walk through them step-by-step using Playwright with user confirmation at each step.

**Flow:** Jira Context → Agent Analysis → Test Cases → User Login → Step-by-Step Execution → Results

---

## Constants

```
CLOUD_ID = "5858106a-50e6-442e-a751-14c0f4243e87"
PROJECT_ROOT = "/Users/trungthach/IdeaProjects"
CHANGES_DIR = "/Users/trungthach/IdeaProjects/docs/changes"
```

---

## Phase 0 — Gather Context

### Step 1: Get the Jira ticket

If the user passed a Jira key as argument, use it. Otherwise ask:
> "What's the Jira ticket? (e.g., MOSO-15545 or full URL)"

Extract the issue key (e.g., `MOSO-15545` from URL or direct input).

Fetch the ticket:
```
mcp__claude_ai_Atlassian__getJiraIssue({
  cloudId: "5858106a-50e6-442e-a751-14c0f4243e87",
  issueIdOrKey: "<ISSUE_KEY>",
  responseContentFormat: "markdown"
})
```

Save the ticket summary, description, and acceptance criteria.

### Step 2: Check for tera artifacts

Check if `docs/changes/<ISSUE_KEY>/` exists:
- `specs.md` — requirements, affected layers, acceptance criteria
- `ui_design_refine.md` — UI components, form fields, watchers
- `beads_plan.md` — what code was changed

If these exist, read them. They provide rich context about what was implemented and how.

### Step 3: Analyze with agents

**If tera artifacts exist:**
Spawn a BA agent to identify edge cases not covered by specs.md:

```
Agent({
  subagent_type: "ba",
  description: "Identify test edge cases for <ISSUE_KEY>",
  prompt: "Given this Jira ticket and specs, identify edge cases, boundary values, and error paths that should be tested in the UI. Focus on business rule validation, form behavior, and user-facing warnings/errors.\n\nJira: <ticket description>\nSpecs: <specs.md content>\n\nReturn a concise list of edge cases with expected behavior."
})
```

**If no tera artifacts:**
Spawn both agents in parallel:

```
// Agent 1: Business rules analysis
Agent({
  subagent_type: "ba",
  description: "Analyze business rules for <ISSUE_KEY>",
  prompt: "Analyze this Jira ticket for MOSO mortgage platform. Identify all business rules, validation logic, edge cases, and acceptance criteria that should be tested in the UI.\n\nJira: <ticket description>\n\nWorkspace: /Users/trungthach/IdeaProjects\n\nRead relevant source files to understand the implementation. Return: business rules list, edge cases, expected validation messages, form behavior."
})

// Agent 2: UI structure analysis
Agent({
  subagent_type: "mortgage-architect",
  description: "Identify UI components for <ISSUE_KEY>",
  prompt: "Analyze this Jira ticket for MOSO mortgage platform. Identify which UI sections are affected, the navigation path to reach them, what GWT form components are involved (inputs, tables, watchers, warnings), and what the user will see.\n\nJira: <ticket description>\n\nWorkspace: /Users/trungthach/IdeaProjects\n\nReturn: affected UI sections, navigation path (which tabs to click), form fields involved, expected warnings/errors, GWT component types."
})
```

---

## Phase 1 — Generate Test Cases

Using all gathered context (Jira + tera artifacts + agent analysis), generate test cases.

### Test case types

| Type | When to use | Playwright actions |
|------|-------------|-------------------|
| **form-validation** | Testing error/warning messages, required fields, input validation | `fill_form`, `click`, `snapshot` |
| **navigation** | Testing tabs load, sections appear, page transitions | `click`, `snapshot`, `wait_for` |
| **visual** | Testing element visibility, CSS states, banners shown/hidden | `snapshot` |
| **data-driven** | Testing multiple input combinations with different expected outcomes | Multiple `fill_form` iterations |

### Generate and save

Create `docs/changes/<ISSUE_KEY>/test_cases.md`:

```markdown
# Test Cases for <ISSUE_KEY>

## Context
- **Task:** <Jira summary>
- **Affected Section:** <from analysis>
- **Business Rules:** <key rules>

## Test Cases

### TC-01: <descriptive name>
- **Type:** form-validation
- **Precondition:** <required state>
- **Steps:**
  1. Navigate to <section/tab>
  2. <action>
  3. <action>
- **Expected:** <what should happen>
- **Verify:** <what to check in snapshot>

### TC-02: ...
```

### Present to user

Show the test cases and ask:
> "Here are the test cases I've generated. Want to add, remove, or modify any before we start?"

Wait for approval before proceeding.

---

## Phase 2 — Browser Setup

### Step 1: User login

Ask the user:
> "Please login to MOSO in the browser, then tell me when ready."

Wait for confirmation.

### Step 2: Get URL

Ask:
> "What's the app URL? (e.g., https://staging.moso.com or http://localhost:8888)"

### Step 3: Get test target

Ask:
> "What loan/page should I test against? Paste the URL or describe what to navigate to."

### Step 4: Navigate and verify

```
browser_navigate({ url: "<provided URL>" })
browser_snapshot({})
```

Check the snapshot:
- If it shows a login page → tell user: "Looks like you're not logged in. Please login and tell me when ready."
- If it shows the app → confirm: "I can see the application. Ready to start testing."
- If unclear → ask user to verify

---

## Phase 3 — Step-by-Step Execution

For each test case, follow this exact loop:

### 1. ANNOUNCE

Tell the user:
> **Running TC-XX: <name>**
> - Type: <type>
> - Steps: <list steps>
> - Expected: <expected result>

### 2. NAVIGATE

```
browser_snapshot({})
```

Read the snapshot to understand current page state. If we need to navigate to a different tab/section:
- Find the tab/link ref in the snapshot
- `browser_click({ ref: "<ref>", element: "<tab name>" })`
- `browser_wait_for({ ... })` if needed for GWT async loading
- `browser_snapshot({})` to confirm navigation

### 3. EXECUTE STEPS

For each step in the test case:

**a. Snapshot to find elements:**
```
browser_snapshot({})
```

**b. Perform the action:**
- **Click:** `browser_click({ ref: "<ref>", element: "<description>" })`
- **Fill form:** `browser_fill_form({ fields: [{ name: "<field>", type: "<type>", ref: "<ref>", value: "<value>" }] })`
- **Select dropdown:** `browser_select_option({ ref: "<ref>", element: "<description>", values: ["<value>"] })`
- **Type text:** `browser_type({ ref: "<ref>", element: "<description>", text: "<text>" })`

**c. Snapshot after action:**
```
browser_snapshot({})
```
Verify the action took effect (field populated, section loaded, etc.)

**d. If element NOT found:**
Tell the user:
> "I can't find '<element>' on the page. The current page shows: <summary of snapshot>. Can you help me locate it?"

Wait for guidance. User might:
- Tell you what to look for
- Navigate manually and tell you to re-snapshot
- Skip this step

### 4. VERIFY

After all steps are done:
```
browser_snapshot({})
```

Compare actual state vs expected:
- Check for expected text/messages in snapshot
- Check element visibility (present/absent in snapshot)
- Report what you found vs what was expected

### 5. VERDICT

Ask:
> "**Expected:** <expected>
> **Actual:** <what snapshot shows>
>
> Verdict? (Pass / Fail / Skip)"

If **Fail**: ask "Any notes on what went wrong?"

Record the result.

### 6. CONTINUE

Move to the next test case. If there are remaining tests:
> "Moving to TC-XX: <name>..."

---

## Phase 4 — Results

After all test cases are done, save `docs/changes/<ISSUE_KEY>/test_results.md`:

```markdown
# Test Results for <ISSUE_KEY>

- **Date:** <YYYY-MM-DD>
- **URL:** <tested URL>
- **Loan:** <loan key/URL>

## Summary
- **Total:** N tests
- **Passed:** X
- **Failed:** Y
- **Skipped:** Z

## Results

| TC | Name | Type | Verdict |
|----|------|------|---------|
| TC-01 | <name> | form-validation | PASS |
| TC-02 | <name> | visual | FAIL |

## Failures

### TC-02 — <name>
- **Expected:** <expected>
- **Actual:** <actual>
- **Notes:** <user's notes>
```

Show summary to user:
> "Testing complete. **X passed, Y failed, Z skipped.** Results saved to `docs/changes/<ISSUE_KEY>/test_results.md`."

---

## Error Recovery

| Situation | What to do |
|-----------|------------|
| Element not found | Snapshot, describe page state, ask user to help locate |
| Wrong page | Ask user to navigate manually, re-snapshot |
| GWT still loading | `browser_wait_for` with timeout, snapshot again |
| Unexpected dialog | `browser_handle_dialog`, retry step |
| Action fails | Show error, ask user to perform step manually, continue |
| Browser disconnected | Ask user to re-open browser and login again |

---

## GWT-Specific Rules

1. **Never hardcode selectors** — GWT generates dynamic IDs. Always snapshot first, use refs from snapshot.
2. **Wait after navigation** — GWT loads sections async. After clicking a tab, wait briefly then snapshot.
3. **Tab structure** — MOSO uses wizard tabs. Look for tab text in snapshot to find refs.
4. **Borrower sub-tabs** — Multiple borrowers shown as tabs within a section. Snapshot to identify active tab.
5. **Validation messages** — Appear as `alert` divs or inline error text. Check snapshot text content after form actions.
6. **Tables** — Employment, income tables use GWT widgets. Look for "Add" buttons and row content in snapshots.

---

## Key Principles

- **Always snapshot before acting** — Never guess element refs
- **One action at a time** — Don't chain multiple actions without verifying each
- **User is in control** — Always ask for verdict, never auto-pass
- **Fail gracefully** — If something doesn't work, ask user, don't crash
- **Stay focused** — Only test what the Jira ticket describes