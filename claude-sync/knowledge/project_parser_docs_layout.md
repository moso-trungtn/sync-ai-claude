---
name: project_parser_docs_layout
description: moso-pricing docs are one folder per lender (docs/lenders/<slug>/README+history+nonqm) since 2026-09-14; per-task specs/plans/test results live only in the workspace docs/changes, never in a repo
metadata:
  type: project
---

Reorganised 2026-09-14 (moso-pricing commits `ec077e32` + `3025e95e`, packs `b2a39711668`, moso-docs `3080c11`, tools `968a1b0`), on Trung's ask:
"no MOSO-xxx task folders in the repo, docs lender by lender, one rule every agent knows".

**Layout (moso-pricing)**
- `docs/README.md` = knowledge-base index (was `docs/MEMORY.md`).
- `docs/lenders/README.md` = the contract: LenderType → folder table, file roles, rules, fix checklists.
- `docs/lenders/<slug>/README.md` (reference) + `history.md` (dated, newest first) + optional `nonqm.md`; extra files keep their own names (`new-rez/polly-format.md`, `legacy-pre-polly.md`, `the-lender/spec.yaml`).
- slug = LenderType key in kebab-case, acronyms together (`penny-mac`, `emet-mortgage`, `nmsi`); Correspondent shares the wholesale folder; aliases RocketCorrespondent→`quicken-loans`, PlanetCorrespondent→`planet-home-lending`. `packs/loan/lender-info.sh <Key>` prints the folder; `docs/lenders/check-lender-docs.sh` (also `--slug <Key>`) verifies every registered key has README+history and that no `docs/changes`/`MOSO-*` exists.
- `_shared/bpmi.md` (MI tables, not a lender), `_template/` (new-lender skeleton). 87 folders for 90 keys; folders moved from the old grouped files are marked *summary* in the index.
- `docs/pricing-rewrite/` holds the Go-service design set (the old `docs/superpowers/` files folded in as `design.md`, `phase0-condition-ast-plan.md`, `phase1-skeleton-data-plane-plan.md`).

**Working files rule** (workspace `CLAUDE.md`, moso-pricing `CLAUDE.md`, agents + skills in tools): specs.md, beads_plan.md, test_cases/results, screenshots go to `/Users/trungthach/IdeaProjects/docs/changes/<KEY>/` only. `.gitignore` in moso-pricing blocks `docs/changes/`, `docs/superpowers/`, `docs/**/screenshots/`.

**Why:** `/tera`, `/new-parser` wrote `docs/changes/<KEY>` relative to the repo cwd and `/test-task` told agents to commit test results into moso-pricing; 22 task files reached origin (incl. the BluePoint MOSO-17200..17206 specs, pushed 09/12 before the cleanup). Lender knowledge was split across 20 deep files + 3 grouped files (medium/simple/nonqm), with fix history interleaved.

**How to apply:** resolve a lender's folder before reading anything; after a parser change update `<slug>/README.md` + add a `history.md` entry in the same commit; never create task folders inside a repo; run `check-lender-docs.sh` in QC. Known gap: `lender-info.sh PennyMacCorrespondent` exits 1 before the doc section (pre-existing, constants grep), `lender-info.sh PennyMac` works. Related: [[feedback_no_essay_comments_parser_code]], [[ai_parser_workflow]].
