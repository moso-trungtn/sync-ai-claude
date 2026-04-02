# Project Memory Index

## Architecture & Documentation
- **UNDERSTAND_MOSO.md** (in repo root) ⭐ **START HERE** - Complete consolidated codebase reference with all architecture, code locations, patterns, and workflows
- [Project Architecture - Service Modules](project_architecture.md) - 5 service modules with their roles and technologies
- **PROJECT_ARCHITECTURE.md** (in repo root) - Complete technical guide with code locations, patterns, and integration points
- **QUICK_REFERENCE.md** (in repo root) - Quick lookup card for common tasks and code locations
- **MODULE_INTERACTIONS.md** (in repo root) - Data flows, module communication patterns, and operational boundaries

## Parser Automation & Testing
- [AI Parser Workflow](ai_parser_workflow.md) - Complete ratesheet parser testing workflow, tool registry, and testing architecture
  - **Activation**: Say "ai-parser" to enter parser-fix mode
  - **5 Main Tools**: lender-info.sh, parser-fix.sh, download-ratesheet.sh, ratesheet-update.sh, cleanup-ratesheets.sh
  - **Unified CLI**: ratesheet.sh (build, status, check, diff, land)
  - **Key Rules**: Always download first, always rebuild moso-pricing, always git-add ratesheets
  - **Test Architecture**: File-based snapshot expectations with auto-registration
  - **Build Dependency**: Must run `mvn install -DskipTests -Pjar-packaging -Dgwt.compiler.skip=true` in moso-pricing before packs/loan tests

## New Parser Skill & Guides (Agent Team)
- **Skill**: `/new-parser` — 3-agent team (BA Lead → Dev Lead → QC Lead) for parser work
  - Orchestrator coordinates: Jira fetch → BA analysis → user confirms → Dev implements → QC tests → retry if needed
  - BA Lead: fetches Jira, analyzes screenshots, produces structured subtask breakdown
  - Dev Lead: implements code changes, spawns parallel Dev Agents for independent files
  - QC Lead: runs tests, validates code contracts, reports pass/fail with fix suggestions
  - Max 3 retry loops on QC failure before escalating to user
  - **Live Dashboard**: `tools/agent-dashboard/` — web UI showing real-time agent status
    - Start: `python3 tools/agent-dashboard/server.py` → `http://localhost:3847`
    - Agents emit events via `source tools/agent-dashboard/emit.sh`
    - Events stored in `/tmp/parser-team/events.jsonl`
    - Demo: `bash tools/agent-dashboard/demo.sh`
- **BA Guide**: `moso-pricing/docs/BA_GUIDE_WRITE_PARSER_TASK.md` — How BAs should write Jira tasks for AI
- **AI Guide**: `moso-pricing/docs/AI_GUIDE_PARSER_WORK.md` — Complete AI reference for parser implementation

## Feedback & Preferences
- [Never auto-Done Jira tasks](feedback_jira_no_auto_done.md) — Leave at "In Progress" after fixing; user reviews and closes
- [Update test inputStream refs](feedback_update_test_inputstream.md) — After downloading new ratesheet, must update AdjustmentParsersTest + RateParserTest references
- [Email templates are file-based](feedback_email_templates.md) — Templates are .json + .content.htm in moso-configuration, not admin panel
- [Commit style for parser fixes](feedback_commit_style.md) — One commit per Jira task, short messages, no Co-Authored-By

## Qualification Matrix Updates
- **[SKILL_UPDATE_QUALIFICATION_MATRICES.md](../docs/SKILL_UPDATE_QUALIFICATION_MATRICES.md)** - Complete skill documentation for updating/creating qualification matrices
  - Use case: Update program eligibility and pricing matrices (e.g., MOSO-15755)
  - Location: `*Tables.java` files in moso-pricing
  - Pattern: ValidateCalculator rules + ConditionTableInfo adjustment tables
  - Includes: Step-by-step workflow, condition builders, examples, checklist
