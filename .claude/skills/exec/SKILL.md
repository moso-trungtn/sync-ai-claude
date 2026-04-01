---
name: exec
description: Multi-agent GWT pipeline orchestrator. Runs BA → UX → Dev Lead (Beads) → Dev (Surgeon) → DevOps chain for a Jira ticket. Memory-first file lookup, self-correcting mvn compile, full artifact trail.
argument-hint: <JIRA_ID or URL>
allowed-tools: Bash, Read, Write, Edit, Glob, Grep, Agent
---

# /exec — Multi-Agent GWT Pipeline

Orchestrates the full development pipeline for a GWT Java Jira ticket.

---

## DASHBOARD INTEGRATION

Source the emit helper at the start and emit status events throughout:

```bash
source /Users/trungthach/IdeaProjects/tools/agent-dashboard/emit.sh
```

**Key emit points (MUST call these):**

| When | Command |
|------|---------|
| Skill starts | `emit_reset && emit_pipeline_start "exec"` |
| Jira key known | `emit_meta "<KEY>" "" "<ACTION>"` |
| Memory loading | `emit_agent_start "memory" "Loading project memories"` |
| Memory loaded | `emit_agent_complete "memory"` |
| BA starts | `emit_pipeline_phase "ba" && emit_agent_start "ba" "Fetching ticket"` |
| BA investigating | `emit_agent_step "ba" "Investigating codebase"` |
| BA done | `emit_agent_complete "ba"` |
| UX starts | `emit_pipeline_phase "ux" && emit_agent_start "ux" "Analyzing UI"` |
| UX skipped | `emit_agent_step "ux" "SKIPPED (server-only)"` |
| UX done | `emit_agent_complete "ux"` |
| Dev Lead starts | `emit_pipeline_phase "dev-lead" && emit_agent_start "dev-lead" "Decomposing beads"` |
| Dev Lead bead | `emit_agent_subtask "dev-lead" "Bead N" "pending" "<description>"` |
| Dev Lead done | `emit_agent_complete "dev-lead"` |
| Dev starts | `emit_pipeline_phase "dev" && emit_agent_start "dev" "Implementing beads"` |
| Dev bead progress | `emit_agent_step "dev" "Bead N: <description>"` |
| Dev file modified | `emit_agent_file "dev" "<filename>" "modified"` |
| Dev bead done | `emit_agent_subtask "dev" "Bead N" "completed" "<summary>"` |
| Dev compiling | `emit_agent_step "dev" "Compiling..."` |
| Dev compile pass | `emit_agent_test "dev" "Compile" "PASS" "BUILD SUCCESS"` |
| Dev compile fail | `emit_agent_test "dev" "Compile" "FAIL" "<error>"` |
| Dev retry | `emit_pipeline_retry N` |
| Dev done | `emit_agent_complete "dev"` |
| DevOps starts | `emit_pipeline_phase "devops" && emit_agent_start "devops" "Writing PR description"` |
| DevOps done | `emit_agent_complete "devops"` |
| All done | `emit_pipeline_done` |

---

## First Run Check

**Before doing anything else**, verify the environment is configured:

```bash
source /Users/trungthach/IdeaProjects/tools/agent-dashboard/emit.sh && emit_reset
echo "WS=${MOSO_WORKSPACE:-MISSING} | MVN=${MAVEN_CMD:-MISSING} | JIRA=${JIRA_EMAIL:-MISSING} | TOKEN=${JIRA_API_TOKEN:-MISSING}"
```

**If any value is `MISSING` → stop immediately and output:**

```
/exec: First-time setup needed. Run:

  bash $MOSO_WORKSPACE/.claude/helpers/setup.sh

(or if MOSO_WORKSPACE is not set yet:)

  bash <path-to-workspace>/.claude/helpers/setup.sh

The script will:
  • Auto-detect workspace and Maven paths
  • Prompt for Jira email + API token
  • Save everything to ~/.claude/settings.json
  • Build project memories automatically

Then restart Claude Code and retry.
```

**Do NOT attempt the task** until all 4 variables are set.

---

## Input Resolution

`$ARGUMENTS` may be:
1. A Jira issue key — `MOSO-15806`
2. A Jira URL — `https://mosoteam.atlassian.net/browse/MOSO-15806`
3. **Empty or a natural-language code task** — derive from conversation context

### GUARD: Reject non-code tasks FIRST

**Before doing anything else**, classify whether the input is a **code change task** or not.

**NOT a code task** — stop immediately and output the rejection message below:
- Data export / CSV / report generation requests ("give me a CSV", "export loans", "show loans closed between...")
- Analytics or dashboard queries ("how many loans", "who has the most", "list all users where...")
- Questions about data or system state
- Requests that contain user feedback about report accuracy ("the report shows 113 files", "the LC field is empty in the report")
- Any input that is asking FOR data rather than asking to FIX or BUILD code

**IS a code task** — continue to Input Resolution:
- References a specific Java class, file path, or GWT layer to change
- Describes a bug in application behavior (wrong logic, null pointer, missing field in an entity/op)
- Describes a feature to add/modify in the codebase
- Contains a Jira key (`MOSO-XXXXX`)
- Uses terms like "fix", "add field", "update op", "implement", "create", "modify"

**If NOT a code task, output and stop:**
```
/exec: This looks like a data/report request, not a code change task.
/exec only implements GWT Java code changes.

For data exports and reports, use the application directly or contact the relevant team.
If there is a bug in the report code itself, describe the specific Java class or behavior to fix.
```

### If $ARGUMENTS is empty or not a Jira key (and IS a code task):

**Do NOT ask the user.** Instead, derive the task automatically:

1. **Scan recent chat** — look for any of:
   - A feature/bug description the user just described in natural language
   - A file path or class name they mentioned that needs changing
   - A Jira key mentioned anywhere in the conversation (e.g., `MOSO-XXXXX`)
   - A `docs/changes/<KEY>/specs.md` or `beads_plan.md` that already exists

2. **Check existing docs** in parallel:
   ```bash
   ls $MOSO_WORKSPACE/docs/changes/ 2>/dev/null
   ```
   If a recent `<KEY>/` folder exists without a branch yet → resume that ticket.

3. **Check memory** — read:
   ```
   $MOSO_MEMORY_DIR/project_structure.md
   ```
   Look for any `in_progress` or recent ticket references.

4. **Synthesize a task description** from the conversation context. Use it as the `specs.md` content in STEP 1, skipping the Jira fetch. Set `ISSUE_KEY = CHAT-<YYYYMMDD>` as a placeholder.

5. If no context can be found at all → output:
   ```
   /exec: No Jira key and no task context found.
   Provide: /exec MOSO-XXXXX  or describe the task first.
   ```
   Then stop.

After resolving the key:
```bash
source /Users/trungthach/IdeaProjects/tools/agent-dashboard/emit.sh
emit_pipeline_start "exec" && emit_meta "<ISSUE_KEY>" "" ""
```

---

## STEP 0 — Memory Check

**Output:**
```
[exec 0/5] Checking project memories...
```

```bash
source /Users/trungthach/IdeaProjects/tools/agent-dashboard/emit.sh
emit_agent_start "memory" "Loading project memories"
```

Read both memory files in parallel:

```
$MOSO_MEMORY_DIR/project_structure.md
$MOSO_MEMORY_DIR/infrastructure_index.md
```

**If either file is missing or older than 24 hours:**

**Output:**
```
[exec 0/5] Memories missing or stale — scanning codebase (may take ~30s)...
```

Run a full project scan (excludes `target/`, `war/`, `*Test.java`):
```bash
bash $MOSO_WORKSPACE/.claude/helpers/scan-project.sh
```
Then re-read both files.

**Staleness check** (compare total live count vs cached total):
```bash
find $MOSO_WORKSPACE/packs/loan/src/main/java \
     $MOSO_WORKSPACE/moso/src/main/java \
     $MOSO_WORKSPACE/base/core/src/main/java \
     -name "*.java" -not -path "*/target/*" 2>/dev/null | wc -l
```
If total differs by more than 15 from `project_structure.md` total → rescan before continuing.

**Output after memory is ready:**
```
[exec 0/5] ✓ Memories loaded — <N> Java files indexed
```

```bash
source /Users/trungthach/IdeaProjects/tools/agent-dashboard/emit.sh
emit_agent_complete "memory"
```

Memory is now your **architectural map** for all subsequent steps.

### Memory-First Rule (ALWAYS enforced from here on)

**You MUST follow this lookup order for every class, file, or concept:**

```
1. infrastructure_index.md  ← check here first, every time
2. project_structure.md     ← module/package layout if index has no match
3. targeted find -name      ← only if NOT found in memory (single module, known path)
4. targeted grep            ← last resort, narrow scope only (one directory, one pattern)
```

**NEVER skip to step 3 or 4 without exhausting steps 1 and 2 first.**
**NEVER run a broad `find` or `grep -r` across the whole workspace.**

If a keyword maps to a section in `infrastructure_index.md` → read those files directly, no search needed.

---

## STEP 1 — BA Agent: Fetch Ticket & Write Specs

**Output:**
```
[exec 1/5] BA — Fetching ticket <ISSUE_KEY>...
```

```bash
source /Users/trungthach/IdeaProjects/tools/agent-dashboard/emit.sh
emit_pipeline_phase "ba" && emit_agent_start "ba" "Fetching ticket <ISSUE_KEY>"
```

### 1.1 Fetch Jira Ticket (skip if chat-context mode)

**If ISSUE_KEY starts with `CHAT-`** (derived from conversation) → skip 1.1 and 1.2, go directly to 1.3 using the synthesized task description as the problem statement.

**If ISSUE_KEY is a real Jira key:**
```bash
curl -s -L -u "$JIRA_EMAIL:$JIRA_API_TOKEN" \
  "https://mosoteam.atlassian.net/rest/api/2/issue/<ISSUE_KEY>?fields=summary,description,status,assignee,priority,attachment,comment,issuetype,labels,parent"
```

Parse: summary, full description (wiki markup), all comments.

```bash
source /Users/trungthach/IdeaProjects/tools/agent-dashboard/emit.sh
emit_meta "<ISSUE_KEY>" "" "<ACTION_TYPE>"
```

### 1.2 Download Image Attachments (skip if chat-context mode)

For each attachment with `mimeType` starting with `image/`:
```bash
mkdir -p /tmp/jira-<ISSUE_KEY>
curl -s -L -u "$JIRA_EMAIL:$JIRA_API_TOKEN" \
  -o "/tmp/jira-<ISSUE_KEY>/<filename>" \
  "https://mosoteam.atlassian.net/rest/api/2/attachment/content/<id>"
```
Download all images in one chained command, then read them with the Read tool in parallel.

### 1.3 Investigate the Codebase — Memory First

**Output:**
```
[exec 1/5] BA — Investigating codebase (memory-first lookup)...
```

```bash
source /Users/trungthach/IdeaProjects/tools/agent-dashboard/emit.sh
emit_agent_step "ba" "Investigating codebase (memory-first)"
```

For each keyword matched → output one line: `  → <ClassName>: <path>`

**Step A — Check infrastructure_index.md (already loaded in STEP 0):**

Map every keyword from the ticket to an index section:

| Keyword type | Index section to check |
|---|---|
| email, template, sendEmail | Email, Template System |
| PDF, document, generate | PDF / Document Generation |
| drive, upload | Google Drive |
| AI, DTI, batch | AI Service |
| MCP, syncToMCP, ai_mcpl, mcp/api | MCP Sync |
| entity, field, typekey | Loan Domain |
| op, service, DAO, cron | Server Infrastructure |
| form, view, input, panel | Client Infrastructure |
| permission, config | Configuration / Auth |

For each match → **read the file path directly from the index**. No search needed.

**Step B — Check project_structure.md (already loaded in STEP 0):**

If the class is not in the index → look up the module and package in `project_structure.md` to identify the right directory before searching.

**Step C — Targeted `find` (only if A and B give no result):**
```bash
find $MOSO_WORKSPACE/<relevant-module>/src/main/java -name "ClassName.java" -not -path "*/target/*"
```
Scope to the single most likely module. Never search workspace root.

**Step D — Targeted `grep` (absolute last resort):**
```bash
grep -r "SpecificClassName" $MOSO_WORKSPACE/<module>/src/main/java --include="*.java" -l
```
Single module, single pattern. Never use `xargs grep` across all files.

**Determine which GWT layers are affected:**
- `shared/` — entities, typekeys, fields → `[shared]` label
- `server/` — ops, services, DAOs → `[server]` label
- `client/` — forms, views, inputs, panels → `[client]` label

### 1.4 Write specs.md

**Output:**
```
[exec 1/5] BA — Writing specs.md...
```

Create `docs/changes/<ISSUE_KEY>/specs.md`:

```markdown
# <ISSUE_KEY>: <summary>

## Problem
<from ticket + codebase investigation>

## Proposed Solution
<technical solution with GWT-specific details>

## Affected Layers
- [shared]: <entities/typekeys to add/change>
- [server]: <ops/services to add/change>
- [client]: <forms/views to add/change>

## Key Classes (from infrastructure_index.md)
<list the exact file paths from memory that are relevant>

## Compliance / Edge Cases
<mortgage domain implications if any>

## Acceptance Criteria
<from ticket>
```

```bash
source /Users/trungthach/IdeaProjects/tools/agent-dashboard/emit.sh
emit_agent_complete "ba"
```

---

## STEP 2 — UX Agent: Analyze UI & Write Design

**Only run this step if the ticket has `[client]` changes.**

```bash
source /Users/trungthach/IdeaProjects/tools/agent-dashboard/emit.sh
emit_pipeline_phase "ux"
```

If server/shared only:
```
[exec 2/5] UX — SKIPPED (server-only)
```
```bash
emit_agent_step "ux" "SKIPPED (server-only)"
```
Go to STEP 3.

**Output (if client changes):**
```
[exec 2/5] UX — Analyzing UI patterns...
```
```bash
emit_agent_start "ux" "Analyzing UI patterns"
```

### 2.1 Read Existing UI Code

From `specs.md`, identify the client files to change. Read:
1. The form/view to modify
2. Its base class
3. A similar existing form for the GWT pattern

Key GWT client locations:
- `base/core/src/main/java/com/mvu/core/client/` — core widgets
- `packs/loan/src/main/java/com/mvu/loan/client/` — loan UI
- `packs/loan/src/main/java/com/mvu/loan/client/view/` — loan views

### 2.2 Write ui_design_refine.md

Create `docs/changes/<ISSUE_KEY>/ui_design_refine.md`:

```markdown
# UI/UX Design: <ISSUE_KEY>

## Layout & Components

| Field | GWT Input Type | Section | Required | Notes |
|-------|---------------|---------|----------|-------|
| <field_name> | SelectInput<T> / SuggestInput<T> / TextInput / DateInput | <section> | Yes/No | |

## Interactions & Watchers

- When `<Field.A>` changes → filter `<Input>` options:
  ```java
  watch(new Watcher(Loan.field_a) {
    protected void run(HasValues scope) {
      input.options().filter(item -> item.get(...).equals(scope.get(Loan.field_a)));
    }
  });
  ```

## Field Dependencies
<list show/hide conditions, required/optional rules>

## GWT Pattern Reference
<existing class to copy from, with file path>

## Validation Notes
<what to validate on submit vs on change>
```

```bash
source /Users/trungthach/IdeaProjects/tools/agent-dashboard/emit.sh
emit_agent_complete "ux"
```

---

## STEP 3 — Dev Lead Agent: Beads Decomposition

**Output:**
```
[exec 3/5] Dev Lead — Decomposing into beads...
```

```bash
source /Users/trungthach/IdeaProjects/tools/agent-dashboard/emit.sh
emit_pipeline_phase "dev-lead" && emit_agent_start "dev-lead" "Decomposing into beads"
```

### 3.1 Read All Artifacts

`specs.md` is already in context from STEP 1 — do NOT re-read it.

Only read if it exists and was not already read this session:
- `docs/changes/<ISSUE_KEY>/ui_design_refine.md` (if client changes)

Read the actual key files from specs.md to verify the design is feasible (use infrastructure_index paths directly).

### 3.2 Decompose into Beads

Beads are **atomic, dependency-ordered tasks**. Always decompose in this order:

| Bead | Layer | Description |
|------|-------|-------------|
| **Bead 1** | `[shared]` | Shared DTO / Model changes — new entity fields, TypeKey constants, shared enums |
| **Bead 2** | `[server]` | RPC / Service Interface contracts — Op registration in LoanOps, service method signatures |
| **Bead 3** | `[server]` | Server ServiceImpl logic — Op implementation, DAO changes, business rules |
| **Bead 4** | `[client]` | Client UI / Presenter — forms, views, inputs, watchers, submit handlers |

**Skip beads that have no changes** (e.g., server-only ticket → skip Bead 4).

Emit each bead:
```bash
source /Users/trungthach/IdeaProjects/tools/agent-dashboard/emit.sh
emit_agent_subtask "dev-lead" "Bead 1: Shared DTO" "pending" "<description>"
emit_agent_subtask "dev-lead" "Bead 2: RPC Interface" "pending" "<description>"
emit_agent_subtask "dev-lead" "Bead 3: Server Impl" "pending" "<description>"
emit_agent_subtask "dev-lead" "Bead 4: Client UI" "pending" "<description>"
```

### 3.3 Write beads_plan.md

Create `docs/changes/<ISSUE_KEY>/beads_plan.md`:

```markdown
# Beads Plan: <ISSUE_KEY>

## Bead 1 — Shared DTO / Model [shared]
- [ ] 1.1 [shared] <full_file_path>: <what to add/modify>
  - Pattern: `public static final Field<T> field_name = new Field<>("field_name", Type.instance());`
  - Acceptance: <criteria>
- [ ] 1.2 [shared] <typekey_file_path>: <new constant>
  - Pattern: follow existing constants in same file
  - Acceptance: <criteria>

## Bead 2 — RPC / Service Interface [server]
- [ ] 2.1 [server] <LoanOps or OpRegistry path>: register new op name constant
  - Pattern: `public static final String MY_OP = "MyOp";`
  - Acceptance: op name available to client RemoteCall

## Bead 3 — Server ServiceImpl [server]
- [ ] 3.1 [server] <full_file_path>: <implement op logic>
  - Extends: AppEngineOp / AbstractAIServiceOp / BaseCronOp
  - Annotation: @RequiresPermissions(Permission.XXX)
  - Email guard: check Strings.isEmpty(options.body) before send
  - Acceptance: <criteria>

## Bead 4 — Client UI / Presenter [client]
- [ ] 4.1 [client] <full_file_path>: <add/modify form or view>
  - GWT pattern: <reference from ui_design_refine.md>
  - Input type: SelectInput / SuggestInput / TextInput / DateInput
  - Watcher: <field dependency>
  - Acceptance: <criteria>

## Repomix Target Files
<exact file paths — max 30, used in Step 4>

## Do NOT Touch
<files outside scope>
```

```bash
source /Users/trungthach/IdeaProjects/tools/agent-dashboard/emit.sh
emit_agent_complete "dev-lead"
```

---

## STEP 4 — Dev Agent (The Surgeon): Targeted Implement + Self-Correct

**Output:**
```
[exec 4/5] Dev — Reading <N> target files...
```

```bash
source /Users/trungthach/IdeaProjects/tools/agent-dashboard/emit.sh
emit_pipeline_phase "dev" && emit_agent_start "dev" "Reading target files"
```

### 4.1 Read Target Files Directly

Using the `## Repomix Target Files` list from `beads_plan.md`, **read each file with the Read tool** — do NOT run repomix.

```
For each file in Repomix Target Files:
  → Read tool (already know the path from beads_plan.md)
  → No XML overhead, no shell command needed
```

**Why**: Read tool is ~10–20% cheaper in tokens than repomix XML wrapping. Infrastructure index already gave you the paths — no discovery needed.

### 4.2 Branch

Do NOT create a new branch. The user manages branches and commits manually.

### 4.3 Implement Bead by Bead

Work through `beads_plan.md` in dependency order: Bead 1 → 2 → 3 → 4.

**For each bead, output and emit before starting:**
```
[exec 4/5] Dev — Bead N: <description> (<filename>)
```
```bash
source /Users/trungthach/IdeaProjects/tools/agent-dashboard/emit.sh
emit_agent_step "dev" "Bead N: <description>"
```

**For each bead task:**
1. Read the file to modify (already read in 4.1 — use that, do NOT re-read unless file was not in target list)
2. Implement the change following the referenced pattern
3. Mark the task as `[x]` in beads_plan.md

**After completing each bead:**
```bash
source /Users/trungthach/IdeaProjects/tools/agent-dashboard/emit.sh
emit_agent_subtask "dev" "Bead N" "completed" "<summary of changes>"
emit_agent_file "dev" "<filename>" "modified"
```

**Key implementation rules:**
- New entity field: `public static final Field<T> field_name = new Field<>("field_name", Type.instance());`
- New typekey constant: follow existing constants in the same file
- New Op: extend `AppEngineOp`, override `execute(JSON input)`, annotate `@RequiresPermissions`
- Email send guard: always check `Strings.isNotEmpty(options.body)` before `emailService().send(...)`
- Template content guard: only `data.set(Template.content, ...)` if `Strings.isNotEmpty(input.get(Template.content))`
- GWT Shared DTOs: if a shared entity changes, update both server ops AND client forms that reference it

### 4.4 Compile Verify — Self-Correction Loop

**Output:**
```
[exec 4/5] Dev — Compiling...
```

```bash
source /Users/trungthach/IdeaProjects/tools/agent-dashboard/emit.sh
emit_agent_step "dev" "Compiling..."
```

```bash
cd $MOSO_WORKSPACE/moso
$MAVEN_CMD compile -q 2>&1 | tail -30
```

**If compile FAILS:**
```
[exec 4/5] Dev — Compile FAILED (attempt N/3) — fixing...
```
```bash
source /Users/trungthach/IdeaProjects/tools/agent-dashboard/emit.sh
emit_agent_test "dev" "Compile" "FAIL" "<error summary>"
emit_pipeline_retry N
```
1. Read the full error output — identify the exact file, line, and error type
2. Fix the specific error (wrong import? missing method? type mismatch?)
3. Re-run compile
4. Repeat up to **3 times** — if still failing after 3 attempts, stop and report the blocker

**If compile PASSES:**
```
[exec 4/5] Dev — ✓ Compile PASS
```
```bash
source /Users/trungthach/IdeaProjects/tools/agent-dashboard/emit.sh
emit_agent_test "dev" "Compile" "PASS" "BUILD SUCCESS"
emit_agent_complete "dev"
```

---

## STEP 5 — DevOps Agent: Diff, Summarize & PR Description

**Output:**
```
[exec 5/5] DevOps — Writing PR description...
```

```bash
source /Users/trungthach/IdeaProjects/tools/agent-dashboard/emit.sh
emit_pipeline_phase "devops" && emit_agent_start "devops" "Writing PR description"
```

### 5.1 Review What Was Built

`specs.md` and `beads_plan.md` are already in context — do NOT re-read them.

**Only run git diff if there are 3+ files changed** (single-file changes are self-evident from STEP 4):
```bash
cd $MOSO_WORKSPACE
git diff HEAD --stat
```

### 5.2 Write PR Description

Create `docs/changes/<ISSUE_KEY>/pr_description.md`:

```markdown
# [<ISSUE_KEY>] <ticket summary>

## Summary

<2-3 sentences describing what was implemented>

## Changes

| Layer | File | Change |
|-------|------|--------|
| [shared] | <path> | <what changed> |
| [server] | <path> | <what changed> |
| [client] | <path> | <what changed> |

## How to Test
<steps to verify the fix/feature>

## Jira
<https://mosoteam.atlassian.net/browse/<ISSUE_KEY>>
```

### 5.3 Final Report

```bash
source /Users/trungthach/IdeaProjects/tools/agent-dashboard/emit.sh
emit_agent_complete "devops"
emit_pipeline_done
```

Output to user:

```
## /exec Complete: <ISSUE_KEY>

### Pipeline Summary
✓ Memory:    Loaded — <N> Java files indexed
✓ BA:        specs.md created
✓ UX:        ui_design_refine.md created / SKIPPED (server-only)
✓ Dev Lead:  beads_plan.md created (Beads 1-4)
✓ Dev:       <N> files changed, compile PASS
✓ DevOps:    pr_description.md created

### Files Changed
<list from git diff --stat>

### Artifacts
docs/changes/<ISSUE_KEY>/
  - specs.md
  - ui_design_refine.md (if applicable)
  - beads_plan.md
  - pr_description.md

Ready for manual review and merge.
```

---

## Optimization Rules (Always Enforced)

1. **No Repomix**: Use Read tool directly on files from `infrastructure_index.md`. Never run repomix — XML overhead wastes 10–20% tokens with no benefit when file paths are already known.

2. **No Re-reads**: `specs.md` and `beads_plan.md` written earlier in the same session stay in context — never re-read them in later steps.

3. **GWT Integrity**: If a shared entity/typekey changes, **always** check both server ops AND client forms that use it and update both.

4. **Self-Correction**: If `mvn compile` fails, read the full error, identify root cause, fix, retry — up to 3 times before reporting blocker.

5. **No Broad Grep**: Never run `grep -r "keyword" ...` across the whole workspace when `infrastructure_index.md` already has the answer.

6. **No Branch**: Do NOT create a new branch. The user manages branches and commits manually.

7. **Index Update**: After creating a new Java class/Op → append it to the correct section in `infrastructure_index.md` before finishing STEP 4.

8. **Dashboard Emit**: Always emit status events at phase transitions, agent start/complete, test results, and retries. This keeps the live dashboard in sync.
