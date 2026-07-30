---
name: email-investigate
description: Investigate an issue reported in an email thread end-to-end. Reads the email (pasted text or fetched via the Gmail MCP), scans the moso / moso-pricing / packs source code for the relevant area, then spawns two `general-purpose` subagents in parallel — one carrying a Business Analyst persona, one carrying a Mortgage Architect persona — to produce a root-cause + recommended-fix writeup. Works in both Claude Code CLI and Cowork because personas are embedded inline (not custom subagent types). Finishes by offering to create a Jira ticket (assigned to the user, in the current sprint) with a dev-friendly description. Trigger when the user says things like "investigate this email", "investigate this thread", "what's wrong here" with an email attached or pasted, "look into this customer report", "trace this issue to the code", or "open a ticket from this email".
---

# Email Thread Investigator

A guided workflow that turns an email-reported issue into a code-grounded analysis and (optionally) a well-written Jira ticket. Follow the steps in order. Do not skip the synthesis step.

---

## Step 1 — Get the email thread

There are two input modes. Detect which one applies before doing anything else.

**Mode A — User pasted the thread.** They've included subject, body, and possibly replies directly in chat. Use that text as-is.

**Mode B — User gave a search hint** (sender name, subject keywords, a date range, "the email from <person> about <topic>"). Use the connected Gmail MCP:

1. Call `mcp__32d9110a-2688-4d4b-8e69-14f0b9046c88__search_threads` with a focused query (Gmail search syntax — `from:`, `subject:`, `newer_than:7d`, etc.).
2. If multiple threads match, list the top 3 (subject, sender, date) and ask which one with `AskUserQuestion`.
3. Call `mcp__32d9110a-2688-4d4b-8e69-14f0b9046c88__get_thread` to fetch the full content of the chosen thread.

Once you have the thread, extract and note:

- **Reporter** — who raised it (name + email)
- **Date** — when the latest message was sent
- **Subject** — the email subject line
- **Problem in their words** — copy 1–3 quoted sentences verbatim
- **Hard signals** — exact error messages, stack traces, loan numbers, lender names, file paths, screenshots referenced
- **Severity hints** — "production is down", "blocking close", "one customer", "intermittent", "since the last deploy"

If the email is ambiguous or you only have a vague forwarded message, ask one clarifying question before proceeding.

**Capture an upstream ticket number, if any.** If the user mentioned a ticket number alongside the email (e.g., "the email about ticket 37106757186", or a support-system reference inside the email body), store it as `<upstream_ticket>` for use in the Source footer in Step 7e. Do not invent one if it wasn't provided.

---

## Step 2 — Quick code reconnaissance (light, not deep)

Before spawning the subagents, do a fast scan so they get focused context, not a blank page. Spend at most 2–3 tool calls here.

Heuristics for where to look:

- **Entity name in email** (Loan, Alert, Admin, Contact, Quote, Rate, etc.) → `Glob` for `**/<Entity>*.java` under `base/` and `moso/`.
- **Lender / parser mentioned** → check `moso-pricing/docs/lenders/<lender>.md` and `moso-pricing/src/main/java/.../<Lender>*.java`.
- **Feature area named** (1003, fee worksheet, credit report, pricing, AUS, rate alert, RE division) → note the corresponding `moso-docs/docs/features/<NAME>_GUIDE.md`.
- **Error / exception text quoted** → `Grep` for a distinctive string from it across the workspace.
- **HTTP endpoint or URL path** → `Grep` the path segment.

Output of this step: a short list (3–7 entries) of concrete leads — file paths with line numbers where possible, plus 1 or 2 relevant doc guides. Do **not** attempt to diagnose the problem yourself yet. The point is to give the subagents a focused starting set.

---

## Step 3 — Spawn two investigators IN PARALLEL (BA lens + Architect lens)

Send a single message containing two `Agent` tool calls. Running them in parallel matters — it cuts wall time roughly in half and keeps their analyses independent.

### Subagent type selection (IMPORTANT — read first)

This skill must work in **both** environments:

- **Claude Code CLI** — has custom subagents `ba` and `mortgage-architect` at `~/.claude/agents/`. Prefer them if available.
- **Cowork** — does NOT load custom agents. Only built-in types exist: `claude`, `claude-code-guide`, `Explore`, `general-purpose`, `Plan`, `statusline-setup`.

**To be safe in both environments, always use `subagent_type: "general-purpose"`** and embed the persona + project context inline (see prompts below). This works everywhere. The custom-agent route fails silently in Cowork — don't rely on it.

Both subagents need full tool access (Read / Grep / Glob / Bash) so they can actually open files in the mounted project folders. `general-purpose` has this by default.

### Agent 1 — Business Analyst lens

- `subagent_type: "general-purpose"`
- `description: "BA investigation of reported issue"`
- Prompt — paste this entire block, then append the email + Step 2 leads at the end:

  > You are a **Senior Business Analyst** for the moso mortgage brokerage platform (US loan origination, CRM, pricing, billing). You are investigating an issue reported via email. Your job is to figure out what the user wanted, what business rule is being violated, who is affected, and what "fixed" means.
  >
  > **Project context — read these first if relevant to the issue:**
  > - `moso-docs/CLAUDE.md` — documentation hub and decision tree (which guide to read for which topic)
  > - `moso-docs/docs/AI_WORKFLOW_GUIDE.md` — which feature guide matches the keywords in the email
  > - Matching feature guide in `moso-docs/docs/features/*_GUIDE.md` (e.g. RATE_ALERT_GUIDE, PRICING_ENGINE_GUIDE, LOAN_PIPELINE_GUIDE, CLOSING_COST_GUIDE, CREDIT_REPORT_GUIDE, AUS_GUIDE, 1003_WIZARD_GUIDE, LO_RECRUITING_GUIDE, BILLING_SUBSCRIPTION_GUIDE, EMAIL_SYSTEM_GUIDE, BORROWER_PORTAL_WIZARD_GUIDE, REAL_ESTATE_DIVISION_GUIDE, etc.)
  > - `moso-docs/docs/data/LOAN_CLASSIFICATION_GUIDE.md` — loan lifecycle (Lead → Prospect → Loan → Funded)
  >
  > **How you work:**
  > - Always explore before answering — read the actual code and feature guide, don't assume.
  > - Cite specific file paths when you reference behavior.
  > - Quote the reporter's literal words when defining the problem.
  >
  > **Answer these four things:**
  > 1. What is the user actually trying to accomplish? (Their goal, in their words.)
  > 2. Which business rule, workflow, or expectation is being violated? Cite the relevant feature guide section.
  > 3. Who is impacted and how badly — single user, all brokers, blocks closing, cosmetic? Severity rating: Lowest / Low / Medium / High / Highest.
  > 4. What outcome would the user consider "fixed"? Be concrete — a sentence the reporter would agree with.
  >
  > **Output rules:**
  > - Under 400 words total.
  > - Be specific. Cite file paths and feature-guide sections.
  > - Do not restate the email.
  > - End with a 1-line "What's missing from the email" note if there are obvious clarifying questions.
  >
  > **Email and leads follow below:**
  >
  > === EMAIL THREAD ===
  > [paste full email thread]
  > === END ===
  >
  > === LEADS FROM STEP 2 ===
  > [paste the file paths and doc guides you collected]
  > === END ===

### Agent 2 — Mortgage Architect lens

- `subagent_type: "general-purpose"`
- `description: "Architect investigation of reported issue"`
- Prompt — paste this entire block, then append the email + Step 2 leads at the end:

  > You are a **Senior Technical Architect** for the moso mortgage platform. You have deep expertise in: US mortgage domain (loan origination, rate sheet pricing, lock policies, TRID/RESPA/ECOA compliance, MISMO), the **moso legacy stack** (Java 17, GWT 2.11, Google App Engine, Cloud Datastore, Cloud Tasks, Pub/Sub), and the **tera target stack** (Spring Boot, PostgreSQL, Kubernetes). You participate in code audits, bug-fix impact analysis, and feature design. You always cite specific file paths and line numbers.
  >
  > **Project context — read these first (in this order):**
  > 1. `moso-docs/docs/core/INFRASTRUCTURE_INDEX.md` — keyword → exact file path lookup. **Use this BEFORE running broad Grep/Glob.** It's an O(1) hashmap, not an O(n) scan.
  > 2. `moso-docs/CLAUDE.md` — documentation hub and AI workflow guide
  > 3. `moso-docs/docs/core/ENTITY_GUIDE.md` — Bean / JSON / HasValues / Field patterns (MANDATORY before any entity code reasoning)
  > 4. `moso-docs/docs/core/ENTITY_INHERITANCE_GUIDE.md` — entity hierarchy discovery
  > 5. `moso-docs/memory/coding-patterns.md` — 15 mandatory coding rules (method chaining, hasValue, dot(), label fields, etc.)
  > 6. Relevant feature guide in `moso-docs/docs/features/*_GUIDE.md` based on what the email is about
  > 7. If the issue is about rate sheet parsing: `moso-pricing/CLAUDE.md` and `moso-pricing/docs/lenders/<lender>.md`
  > 8. If the issue is about a test/loan-pack thing: `packs/loan/CLAUDE.md`
  >
  > **How you work:**
  > - Always explore before answering — read the actual file, don't assume from the path name.
  > - Use the Infrastructure Index FIRST for file lookups. Fall back to Grep/Glob only when the index has no match, and scope to ONE module.
  > - Cite exact file paths AND line numbers, e.g. `base/loan/src/main/java/com/loan/op/LoanSaveOp.java:142`.
  > - If you have a hypothesis but can't confirm it from the code, write "Suspected:" and say how to confirm.
  >
  > **Answer these five things:**
  > 1. **Components involved.** Which entities, services, operations, and data flows are touched? List file paths.
  > 2. **Root cause.** Code defect, data bug, configuration, design gap, or upstream system? Pick one, justify with code references.
  > 3. **Recommended fix.** Specific files to change with line numbers. What to change in each. Reference applicable `coding-patterns.md` rule number.
  > 4. **Datafix assessment.** Is the code fix alone enough, or do EXISTING records also need to be repaired? Be explicit: (a) which entities (Loan / Admin / Alert / Lead / other) and roughly how many records are affected, (b) what's wrong with the historical data, (c) the **high-level backfill intent in one sentence** — the actual script will be produced separately by the `datafix-creator` skill, **do NOT design the full script here**, (d) what could go wrong if we ship code-only and skip the datafix (past loans still wrong, calculated fields stale, FK orphans, broken queries), (e) suggested split strategy if any (e.g. "active Loans first, then Prospects, then dead Loans" — `datafix-creator` will formalize). If no datafix is needed, say so explicitly. Reference `moso-docs/docs/data/DATAFIX_GUIDE.md` for context.
  > 5. **Alternatives considered.** 1–2 alternative approaches with why the recommended one wins.
  >
  > **Output rules:**
  > - Under 500 words total.
  > - File paths with line numbers everywhere.
  > - No vague verbs ("improve", "handle", "address"). Use "validate", "guard with `hasValue()`", "load via `bundle.load()`", etc.
  > - Do not restate the email.
  > - Do not write the datafix script — only the intent and scope.
  >
  > **Email and leads follow below:**
  >
  > === EMAIL THREAD ===
  > [paste full email thread]
  > === END ===
  >
  > === LEADS FROM STEP 2 ===
  > [paste the file paths and doc guides you collected]
  > === END ===

If a subagent returns "I couldn't find enough information", do one targeted follow-up pass with extra context (specific file Reads, narrower Grep results) rather than guessing.

---

## Step 4 — Synthesize and present to the user

After both subagents return, combine their reports into a single, scannable writeup. Do **not** dump the raw agent outputs. Use the same two-tier shape the ticket will use, so the user sees on screen exactly what would get filed.

```
Problem (plain language)
<2-3 short sentences. What the user tried to do, what happened, why it matters. No jargon.>

Who reported it
<Name> on <date>.

Who is affected
<Plain words. One line.>

Severity
<Lowest / Low / Medium / High / Highest> — <one-line reason>

How to test
Test 1: <scenario — exact case from email>
  1. <step>
  2. <step>
  Expected: <outcome>

Test 2: <scenario>
  ...

Done when
- <plain-language outcome>
- <plain-language outcome>

--- Technical details (for devs) ---

Root cause
<2-3 sentences. File paths with line numbers.>

Files to change
- `<path>:<line>` — <what to change>
- `<path>:<line>` — <what to change>

Tests / docs
- <what test to add or update>
- <moso-docs guide if applicable>

Datafix required?
<"No — code-only fix" OR "Yes — <one-line scope, e.g. 'backfill ~12k funded loans created before 2026-06-01'. Dev should use the `datafix-creator` skill to produce the script.'">

Alternatives considered
<Only if applicable.>

Effort estimate
<XS / S / M / L / XL>
<If datafix required, factor in datafix-creator run + dry-run + verification time, not just the code change.>
```

Keep paragraphs short. Use bullets only when listing three or more items. The user should be able to skim the top half in 20 seconds and decide whether to file a ticket.

---

## Step 5 — Clarification gate (MANDATORY — do not skip)

Before offering to create a ticket, you must verify that the analysis is solid enough to act on. A bad ticket wastes a dev's day. **Pause here** and run through the checklist below. If any item is unresolved, surface it to the user and resolve it first.

### Concerns checklist

For each item, check the email + the subagent reports + your code recon:

1. **Code-vs-email mismatch.** Does the code in the cited file paths actually match what the email describes? If the architect cited `LoanSaveOp.java:142` but the line looks unrelated, flag it.
2. **"Suspected" without proof.** Did the architect use words like "suspected", "likely", "probably", "might be"? If the root cause isn't confirmed, flag it.
3. **Missing critical info from the email.** Is there a loan number / customer ID / lender name / exact error / screenshot / repro steps that the reporter mentioned but didn't actually include? If so, flag it.
4. **Two reasonable interpretations.** Could the reported behavior be read two different ways (e.g. "the rate is wrong" — is it the displayed rate, the saved rate, or the calculated rate)? If yes, flag the ambiguity.
5. **Out-of-scope fix.** Does the recommended fix touch areas the agents flagged as risky, deprecated, or owned by another team? If yes, flag it.
6. **Conflicts with project rules or recent changes.** Does the fix conflict with `moso-docs/memory/coding-patterns.md`, with a recent commit in the area, or with an in-flight ticket? `Grep` recent changes if you suspect overlap. If yes, flag it.
7. **Cannot apply in this codebase.** Is the email describing something the project doesn't support, or talking about a system that lives elsewhere (a different repo, a third-party tool, a configuration in the lender's portal, etc.)? If yes, flag it — the fix may not belong here at all.
8. **Reporter's expected behavior not documented.** Did the reporter say "it should do X" but X is not documented in any `moso-docs/docs/features/*_GUIDE.md` and not in the BA's writeup? If yes, flag it — we may be guessing the requirement.
9. **Data impact unclear or risky.** Did the architect identify a datafix need that is vague ("might affect some loans"), unbounded ("recompute all rates"), or destructive (deletes, overwrites without backup)? Did the architect skip the datafix question entirely? Is there a real risk that **shipping the code fix alone leaves historical data broken** (e.g. past loans still calculated with the old buggy logic, FK orphans, mismatched enum values)? If any of these — flag it. Data corruption is the most expensive class of bug; the gate must catch it.

If **all nine items pass cleanly**, skip ahead to Step 6 (Ask about Jira).

If **any item is flagged**, do not proceed to Step 6. Instead, run the next subsection.

### Surface the concerns and resolve them

Present the user with a short, scannable list — one line per concern — using this format:

```
Before I recommend creating a ticket, a few things need to be cleared up:

1. <concern> — <what's unclear, in one line>
2. <concern> — <what's unclear, in one line>
3. <concern> — <what's unclear, in one line>

How should we handle these?
```

Then offer the user a choice via `AskUserQuestion`:

> Question: "How do you want to clear up these concerns?"
> Header: "Clarify"
> Options:
> - "I'll answer here" — User answers your concerns in chat; you re-synthesize with the new info before going to Step 6
> - "Draft a reply email to the sender" — You draft a clarification email (see template below) for the user to send; once the user gets a response and pastes it back, you re-synthesize
> - "Proceed anyway" — User accepts the risk; you proceed to Step 6 but the ticket description must include a "## Open questions" section listing the unresolved items

If the user picks "I'll answer here", ask the concerns **one at a time** (use `AskUserQuestion` per concern, or a single multi-question call if all are short yes/no). Do not bulk-ask 8 questions in a wall of text.

If the user picks "Draft a reply email to the sender", produce a draft using the template below, then stop and wait for the user's reply email (or a "they responded with X" message). Do not file a ticket in the meantime.

### Reply-email template (use when drafting a clarification email)

Keep the email short, friendly, and specific. Anchor each question to what they wrote.

```
Subject: Re: <original subject>

Hi <reporter first name>,

Thanks for flagging this. Before we dig in, a couple of quick clarifications so we fix the right thing:

1. <Question 1 — be specific. Quote their words where helpful.>
2. <Question 2>
3. <Question 3>

<If asking for a loan number / screenshot / steps:>
If possible, could you also share:
- <Specific artifact, e.g. "the loan number where this happened">
- <Specific artifact, e.g. "a screenshot of the screen when the error appeared">
- <Specific artifact, e.g. "what you clicked just before it failed">

Once we have these, we'll open a ticket and loop you in.

Thanks,
Trung
```

Rules for the draft email:

- **No more than 3 questions.** If you have more, prioritize the three that block the diagnosis. Pile-on questions don't get answered.
- **Quote their words** when asking about something ambiguous: *"You wrote 'the rate is wrong' — do you mean the rate displayed in the quote, the rate saved on the loan, or the rate sent to the lender?"*
- **Ask for artifacts, not opinions.** Loan numbers, screenshots, exact error text, time of day, and reproduction steps are useful. "What do you think went wrong" is not.
- **Set the expectation.** End with what happens next ("we'll open a ticket and loop you in") so the reporter knows their reply unblocks action.
- **Don't promise a fix date.** The diagnosis isn't done yet.

### After the user responds

Once the user has either answered in chat or pasted the sender's reply, **re-synthesize**: update the affected sections of your Step 4 writeup (don't dump a new full writeup unless something fundamental changed), then re-run this checklist. Only when all items pass cleanly do you move to Step 6.

If the new info reveals the issue doesn't belong as a Jira ticket at all (e.g. it's a user-training issue, a config the user can change themselves, or a problem in a different system), say so directly — don't file a ticket for completeness.

---

## Step 6 — Ask about Jira

After presenting the synthesis, ask via `AskUserQuestion`:

> Question: "Do you want me to create a Jira ticket for this?"
> Header: "Create ticket"
> Options:
> - "Yes, create and assign to me" — File the ticket now in the current sprint
> - "No, just the analysis" — Stop here, no ticket created

If the user picks "No", end the workflow with a single sentence ("Got it — no ticket created. Let me know if you change your mind."). Do **not** create the ticket.

---

## Step 7 — Create the Jira ticket (only if the user said yes)

### 7a. Gather the routing details

Ask via `AskUserQuestion` for the **Jira project key** (the user said this is per-run). Show the question even if you think you know it:

> Question: "Which Jira project should this go into?"
> Header: "Project"
> Provide 2–3 likely options based on the issue (e.g., MOSO, LF, OPS) plus the "Other" fallback for a free-text project key.

Also ask for **issue type** if it isn't obvious:

> Question: "Issue type?"
> Header: "Type"
> Options: "Bug — broken behavior", "Task — change or improvement", "Story — user-facing feature"

Default to **Bug** if the email describes broken behavior, **Task** otherwise.

### 7b. Resolve the cloudId and the assignee

First, get the Atlassian cloudId — every Jira call needs it. Cache it for the rest of the workflow:

- Call `mcp__d4873f66-6c13-4695-be2b-dbd414d76d1d__getAccessibleAtlassianResources` (no args).
- If multiple sites are returned, pick the one matching the user's workspace, or ask via `AskUserQuestion`.

Then resolve the user's Jira account ID:

- Call `mcp__d4873f66-6c13-4695-be2b-dbd414d76d1d__lookupJiraAccountId` with `cloudId` from above and `searchString: "trung.thach@loanfactory.com"`.
- Store the returned `accountId` for the create call.

If the lookup fails or returns multiple matches, ask the user to paste their Jira account ID once.

### 7c. Find the current (active) sprint

Use JQL via `mcp__d4873f66-6c13-4695-be2b-dbd414d76d1d__searchJiraIssuesUsingJql`:

- `cloudId`: the one from Step 7b
- `jql`: `project = <PROJECT_KEY> AND sprint in openSprints()`
- `fields`: `["sprint", "customfield_10020"]`
- `maxResults`: 5

From the response, find the sprint object with `state: "active"` and capture two things:

1. The sprint's `id` (numeric).
2. The Jira **custom field key** the sprint was returned under — usually `customfield_10020`, but it varies per instance. Use whatever key actually appears in the response payload.

You'll need both when building `additional_fields` in Step 7g.

If `openSprints()` returns nothing (the project may not use sprints, or no sprint is active), ask the user:

> Question: "No active sprint found in <PROJECT>. What now?"
> Options: "Create without sprint", "I'll provide a sprint ID"

### 7d. Set priority

Infer from severity hints in the email and the architect's report:

- **Highest** — production down, blocks closing, data loss
- **High** — affects many users or a critical workflow
- **Medium** — affects some users, has a workaround (default)
- **Low** — cosmetic, edge case, internal only

### 7e. Build the description (Markdown)

The description must follow the template below **exactly** — devs read these in a hurry and rely on the structure. Write it in Markdown and pass it directly to `createJiraIssue` as the `description` string, with `contentFormat: "markdown"`. The Jira MCP renders Markdown to ADF for you, so don't hand-build ADF JSON.

The template has two halves on purpose. The **top half is for everyone** — you, QC, the BA, the reporter, support. The **bottom half is for devs** and can be skipped by non-tech readers. Keep the top half short and plain-language; keep the bottom half precise.

```
## Problem (plain language)
<2-3 short sentences. No jargon. What the user tried to do, what happened instead, why it matters. Write so a non-tech reader understands in 20 seconds.>

## Who reported it
<Name> on <YYYY-MM-DD>.

## Who is affected
<Plain words: "All brokers", "One loan officer in CA", "Customers using Freedom rates", "Internal only". One line.>

## How to test (for QC)
Test 1: <One-line scenario>
  Steps:
    1. <action>
    2. <action>
  Expected: <what should happen>

Test 2: <One-line scenario>
  Steps:
    1. <action>
    2. <action>
  Expected: <what should happen>

(Include 2-4 test scenarios. Each one must be runnable without reading anything else in this ticket. Always include the exact scenario from the email as Test 1.)

## Done when
- [ ] All test scenarios above pass
- [ ] <Any specific user-visible outcome, plain language>
- [ ] <Any specific user-visible outcome, plain language>

---

## Technical details (for devs)

**Root cause**
<2-3 sentences. Cite file paths with line numbers, e.g. `base/loan/src/main/java/com/loan/op/LoanSaveOp.java:142`. If uncertain, write "Suspected:" and explain how to confirm.>

**Files to change**
- `<path>:<line>` — <what to change and why>
- `<path>:<line>` — <what to change and why>

**Tests to add or update**
- <unit/integration test file and what it should cover>

**Docs to update**
- <moso-docs path, per CLAUDE.md update rules — only if applicable>

**Datafix required?**
<Pick ONE: "No — code change only, no existing records affected." | "Yes — see below.">

<If Yes, include all of the following. If No, omit the rest of this section.>

- **Why a datafix is needed:** <1–2 sentences. What's wrong with historical records if we skip it.>
- **Scope:** <Which entity (Loan / Admin / Alert / Lead / other), which filter. E.g. "All `Loan` records where `funded = true` AND `created < 2026-06-01`. Estimated count: ~12,000.">
- **Backfill intent:** <One paragraph in plain words — what each affected record should look like after the fix. Do NOT design the script here.>
- **Suggested split (if any):** <e.g. "Active Loans first, then Prospects, then dead Loans" — the `datafix-creator` skill formalizes this.>

**How to produce the datafix script**

Use the **`datafix-creator`** skill in Claude Code (`/datafix-creator` or "create a datafix for ..."). It runs a 4-agent workflow — Architect → BA → Developer → QC — that produces a production-ready Java class extending `UpgradeManOp` or `BaseUpgrader`, with the right template (`updateEntityInRange` + `DatafixConfigManager`), split strategy, terminal support, and scenario system. **Do not hand-write the script.** Doing so loses the QC step.

When you run `datafix-creator`, paste the "Scope" and "Backfill intent" above as the request.

**Acceptance checklist for the produced script (QC will verify, but the reviewer should also confirm):**

- [ ] Script extends `UpgradeManOp` or `BaseUpgrader` (per `datafix-creator` templates)
- [ ] `bundle.disableEvents(true)` and `bundle.disableSideEffect(true)` are set
- [ ] Processes in date-range circles via `DatafixConfigManager.setLoanProcessingCircle(-N)` (resumable)
- [ ] Terminal condition honored per `moso-docs/docs/data/THREAD_TERMINATION_GUIDE.md` (killable without corrupting partial batches)
- [ ] Idempotent: re-running on already-fixed records is a no-op (uses `setIfDifferent` or pre-check)
- [ ] Dry-run mode: prints count + sample of 10 affected records before any write
- [ ] Verifiable rollback plan documented in the script header comment
- [ ] Verification query (post-run) that proves the fix worked across the full population, not just one record

**Verification after run:** <SQL/JQL/query that proves the fix worked across the full population.>

**Alternatives considered**
<Only include if there are real alternatives. Otherwise omit this line.>

**Reproduction details**
- Frequency: <always | intermittent | one-off>
- First seen: <date or "unknown">
- Environment: <prod | staging | both | unknown>

---
<!-- Source footer — MANDATORY. See "Source footer" rule below. -->
email: [<email subject line, no quotes, no brackets in the value>]
ticket: <ticket number if the user provided one>
```

### Source footer (MANDATORY)

The very last lines of the description must be a source footer. This is how the dev (and future search) connects the ticket back to where it came from.

- **If the source is an email** — always include `email: [<subject>]` on its own line. The subject goes inside the square brackets exactly as it appears in the email header, no surrounding quotes.
- **If the user provided an upstream ticket number** (e.g., a support/helpdesk ticket, a partner system ID, a previous Jira issue, an external bug tracker) — include `ticket: <number>` on its own line. Use the number exactly as the user gave it; no prefix, no URL, just the bare value.
- Both lines may appear together when both apply. Order: `email:` first, then `ticket:`.
- These lines come **after** the `## Related` section, separated from it by a `---` horizontal rule.
- Do not omit either line when its source applies. Do not fabricate a ticket number — if none was provided, omit the `ticket:` line entirely.

Example footer when both apply:

```
---
email: [Loan #123456 cannot save after credit pull]
ticket: 37106757186
```

Example footer for an email-only source:

```
---
email: [Freedom ratesheet Zone 1 missing rows]
```

### 7f. Build the summary

The **summary** (Jira's title) is the single most important field — non-tech and tech readers both see it in the backlog.

- Start with a verb in imperative form: "Fix", "Add", "Prevent", "Show", "Save", "Block".
- Name the affected thing in **plain language** (no class names, no acronyms).
- Name what the user sees go wrong — that's what makes it scannable.
- Maximum ~100 characters. Aim for 60–80.
- No trailing period.

Examples of summaries that work:

- "Fix loan save crash when agent is missing"
- "Fee worksheet shows blank section C when title fee lookup fails"
- "Freedom ratesheet skips Zone 1 rows on the latest layout"
- "Pricing page does not show LTV adjustments for Non-QM loans"

Examples of summaries that do **not** work (do not write these):

- "Loan bug" — too vague
- "Fix issue reported by Tom" — uninformative
- "Fix NPE in LoanSaveOp.java:142" — jargon in the title; save that for the description
- "Improve loan save" — no verb of action, no symptom

### 7g. Create the issue

Call `mcp__d4873f66-6c13-4695-be2b-dbd414d76d1d__createJiraIssue` with:

- `cloudId` — from Step 7b
- `projectKey` — from Step 7a
- `issueTypeName` — from Step 7a (e.g. "Bug", "Task", "Story")
- `summary` — from Step 7f
- `description` — Markdown string from Step 7e
- `contentFormat: "markdown"`
- `assignee_account_id` — from Step 7b
- `additional_fields` — JSON object with everything that isn't a top-level parameter:
  ```json
  {
    "priority": { "name": "<priority from Step 7d>" },
    "<sprint custom field key from Step 7c>": <active sprint id>,
    "labels": ["from-email", "<optional area tag e.g. parser, 1003, pricing>"]
  }
  ```
  Note: sprint values on most Jira instances are a single number (the sprint id), not an array. If the create call fails with a sprint field error, try wrapping the id in an array: `[<sprintId>]`.

### 7h. Report back to the user

After the ticket is created, post a short confirmation:

```
Created <ISSUE-KEY>: <summary>
Assigned to you, in <sprint name>.
<issue URL>
```

Then stop. Do not start working on the fix unless the user asks.

---

## Writing rules for the ticket (read every time)

The ticket has two audiences — the top half is for non-tech readers (you, QC, BA, the reporter) and the bottom half is for devs. Follow the rules for the half you're writing.

**Top-half rules (Problem / Who reported / Who affected / How to test / Done when)**

- **Plain language.** No file paths, no class names, no acronyms, no Jira-isms. If a 12-year-old wouldn't understand the sentence, rewrite it.
- **Short.** Each sentence under ~20 words. Each test scenario fits on the screen without scrolling.
- **QC must be able to run the tests with no other context.** Every "How to test" entry has numbered steps and an Expected line. No "see root cause" or "ask the dev" — those make tests untestable.
- **The first test scenario is always the exact case from the email.** That's the one the reporter cares about.
- **"Done when" boxes are user-visible outcomes**, not implementation steps. Good: "Loan #123456 saves without error." Bad: "NPE guarded in LoanSaveOp."

**Bottom-half rules (Technical details)**

- **Be specific.** "Fix bug in loan save" is useless. "LoanSaveOp throws NPE at line 142 when `agent` FK is unset on lead conversion" is useful.
- **No vague verbs.** Prefer "validate", "guard with `hasValue()`", "load via `bundle.load()`", "add Boolean shortcut" over "improve", "handle", "address", "look into".
- **Cite line numbers.** Devs jump straight to the editor from the path-and-line. Without it, they re-investigate from scratch.
- **Follow CLAUDE.md patterns.** When the fix involves entity code, reference the relevant `moso-docs/docs/core/ENTITY_GUIDE.md` section and the matching `memory/coding-patterns.md` rule number.
- **Honor i18n rules.** If the fix involves UI text, add a docs item: "Add the new message to `.properties`, `_zh.properties`, and `_vi.properties`, then run `mvn test -Dtest=StringsTest#testStaticConfiguration`."
- **Honor parser rules.** If the fix involves a ratesheet parser, add a docs item: "Update `moso-pricing/docs/lenders/<lender>.md` per the project's parser-fix workflow."
- **Data safety is non-optional.** Every ticket must answer "Datafix required?" with a clear Yes or No — never leave it blank, never write "maybe", never say "the dev will figure it out". When Yes, the ticket must include Scope + Backfill intent + Suggested split, AND must direct the dev to use the **`datafix-creator`** skill to produce the actual script (do not hand-write datafix scripts — they bypass the QC step). The reviewer-facing acceptance checklist in the template must remain so the PR review can verify the produced script honors all guards. A code fix that leaves historical records in a corrupt state is a regression, not a fix.

**Universal rules**

- **One issue per ticket.** If the email reports two unrelated problems, ask the user whether to split before filing.
- **Summary stays plain too.** The Jira title is read by non-tech and tech alike — start with a verb, name the affected thing in plain words. "Fix loan save crash when agent is missing" beats "Fix NPE in LoanSaveOp.java:142".
- **Always close with the Source footer.** The description's final lines must be the footer described in Step 7e: `email: [<subject>]` whenever the source was an email, and `ticket: <number>` whenever the user provided an upstream ticket number. Never omit the email line for an email-sourced ticket. Never fabricate a ticket number.

---

## Failure modes to avoid

- **Don't write the ticket before showing the synthesis.** The user must confirm direction first.
- **Don't guess sprint IDs.** If `openSprints()` returns nothing, ask.
- **Don't assign to anyone other than the user** unless the user explicitly names someone else.
- **Don't create a ticket if the user said no.** "Just the analysis" means stop.
- **Don't dump raw subagent output.** Synthesize. Cite. Trim.
- **Don't invent file paths or line numbers.** If you're uncertain, say "Suspected:" and explain how to confirm.
- **Don't auto-commit any code changes.** This skill produces tickets, not commits.
- **Don't skip the clarification gate.** Even if the analysis looks complete, run the eight-item checklist in Step 5. A bad ticket built on a "suspected" root cause wastes a dev's day.
- **Don't file a ticket for something that isn't actionable in this codebase.** If the email turns out to be a user-training issue, a config the reporter can change themselves, a problem in a different repo, or a third-party system issue, say so and stop. Don't file the ticket "just to have one".
- **Don't pile up clarification questions.** When drafting a reply email to the sender, keep it to three questions max. More questions get fewer answers.
- **Don't ship a code-only fix when historical data is broken.** If the bug means past records hold the wrong value (wrong rate, wrong status, wrong calculated field, dangling FK), the ticket MUST include a Datafix section. A "Phase 2 cleanup someday" note is not acceptable — file it in the same ticket or as a hard-linked follow-up ticket created in the same sprint.
- **Don't propose destructive datafixes without a rollback plan.** Any datafix that deletes records, overwrites fields without an audit log, or runs unbounded queries must have an explicit rollback strategy in the ticket. If you can't articulate one, flag it in the clarification gate instead of filing.
- **Don't design the datafix script inside this skill.** The mortgage-architect should identify the *need* and the *scope*, but the actual Java class (extending `UpgradeManOp` / `BaseUpgrader`, with `updateEntityInRange`, `DatafixConfigManager`, split strategy, terminal support, scenarios) is the job of the **`datafix-creator`** skill. Writing the script inline here bypasses datafix-creator's QC step and produces unreviewed code. The ticket must direct the dev to run `/datafix-creator` when they're ready to implement.
