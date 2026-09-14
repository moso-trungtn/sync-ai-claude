# Project Memory Index

## Architecture & Documentation
- **UNDERSTAND_MOSO.md** (in repo root) ⭐ **START HERE** - Complete consolidated codebase reference with all architecture, code locations, patterns, and workflows
- [Project Architecture - Service Modules](project_architecture.md) - 5 service modules with their roles and technologies
- **PROJECT_ARCHITECTURE.md** (in repo root) - Complete technical guide with code locations, patterns, and integration points
- **QUICK_REFERENCE.md** (in repo root) - Quick lookup card for common tasks and code locations
- **MODULE_INTERACTIONS.md** (in repo root) - Data flows, module communication patterns, and operational boundaries

## Build Architecture
- [b2 build pulls base from nexus](project_b2_build_nexus_deps.md) ⚠️ — moso-pricing builds from git source on b2 but resolves base/quote/appengine from nexus snapshots
- ["Rate keys changed" with only `-` lines](build_rate_key_diff_unpushed_pricing.md) ⚠️ — packs expectations pushed while the moso-pricing parser commit is still local; push pricing, do not re-accept

## Parser Automation & Testing
- [Parser docs: one folder per lender + workspace-only task files](project_parser_docs_layout.md) ⚠️ — `docs/lenders/<slug>/{README,history,nonqm}.md`, contract in `docs/lenders/README.md`; specs/plans/test results only in `/Users/trungthach/IdeaProjects/docs/changes/<KEY>/`, never in a repo (2026-09-14)
- [AI Parser Workflow](ai_parser_workflow.md) — say "ai-parser" to enter parser-fix mode; 5 tools (lender-info / parser-fix / download-ratesheet / ratesheet-update / cl

## New Parser Skill & Guides (Agent Team)
- **Skill**: `/new-parser` — BA Lead → Dev Lead → QC Lead team; max 3 QC retry loops then escalate. Live dashboard: `python3 tools/agent-dashboard/server.py` → localhost:3847, events in `/tmp/parser-team/events.jsonl`
- **Skill**: `/parser-task-builder` — the ONE pre-implementation pipeline (extract + file/update Jira); `--extract-only <path>` for just the report
- [parser-task-builder merge 2026-09-11](project_parser_task_builder_merge.md) ⚠️ — two disagreeing skill versions + extract-ratesheet merged into one; old BA/AI guide memory links were dead, now removed
- [NonQM lender sheet tracking](project_nonqm_lender_sheet_tracking.md) — 35 un-integrated Non-QM lenders, tiers, 3 with Backlog Epics ready to run, "lender #3" = Nations Direct Mortgage

## Feedback & Preferences
- [Ratesheet refresh: GCS first](feedback_ratesheet_refresh_gcs_first.md) — try download-ratesheet.sh before asking user to manually save; manual only if GCS genuinely has nothing (mail-trigger code unpushed)
- [Agents must load moso-docs first](feedback_agents_load_moso_docs_first.md) — ba/mortgage-architect (and any project agent) must read moso-docs before work
- [Never auto-Done Jira tasks](feedback_jira_no_auto_done.md) — Leave at "In Progress" after fixing; user reviews and closes
- [Update test inputStream refs](feedback_update_test_inputstream.md) — After downloading new ratesheet, must update AdjustmentParsersTest + RateParserTest references
- [Email templates are file-based](feedback_email_templates.md) — Templates are .json + .content.htm in moso-configuration, not admin panel
- [Commit style for parser fixes](feedback_commit_style.md) — One commit per Jira task, short messages, no Co-Authored-By
- [check-rate commit style](feedback_check_rate_commit_style.md) — `[type] subject` bracketed prefix, imperative mood, no AI-branding trailers
- [Never push without asking](feedback_never_push_without_asking.md) — "commit đi" = commit only; push needs its own explicit ask
- [Run both tests for parser fixes](feedback_run_both_tests.md) — Always run RateParserTest AND AdjustmentParsersTest before and after fixing
- [Take screenshots during UI testing](feedback_test_screenshots.md) — During /test-task, screenshot each verdict step, save to screenshots/ folder, reference in Jira comment
- [Test reports: scenario + numbers + embedded screenshot](feedback_test_report_scenario_with_screenshot.md) — every S<n> block in Jira/test_results carries its lines AND its own `!S<n>_x.png|thumbnail!`
- [Verify emails via prospect conversation](feedback_verify_emails.md) — After triggering email, check Prospect Dashboard → Conversation History for the sent email
- [Separate LF namespace in migration ops](feedback_separate_lf_namespace.md) — In UpgradeManOp scripts, run LoanFactory NS separately from active companies, not together
- [Never guess ALL for adjustment conditions](feedback_no_lazy_all_condition.md) — Identify the real ConditionFactory/RangeCondition/StateCondition/etc. class first
- [Parser rewrites must carry over revertSignal](feedback_parser_rewrite_check_revertsignal.md) — -Daccept blesses sign-flipped tables silently; whole-table sign flip in a diff = check revertSignal (BFF MOSO-17010)
- [colName must match the sheet — never rename CLTV to LTV](feedback_lt_colname_not_cltv.md) ⚠️ SUPERSEDED — old advice was backwards and caused MOSO-16737; real fix is computing `cltv` (see [[pricing_nonqm_cltv_never_computed]])
- [Check lender rate from a /l/ share link](feedback_check_lender_rate_link_workflow.md) — resolve link via curl 302, download TODAY's sheet (verify SHA/last-modified), reconcile rate + full LLPA stack
- [Rate check ≠ eligibility check](feedback_rate_check_vs_eligibility_check.md) — link+sheet proves PRICE math + sheet-matrix validations only; guideline (reserves, #properties
- [Eligibility check runs locally off validations()](pricing_eligibility_check_local_validations.md) — QuoteServer + *Tables.validations(); isApplicable()=TRUE means BLOCK; always add a control case

- [Crawling the second number on a line](pricing_second_column_crawl.md) — Max+Min price pairs: embed the first value in crawlPattern, never narrow the region
- [asSection() latches until the next section](pricing_assection_latches_until_next_section.md) ⚠️ — rows declared after the last asSection() inherit its gate and silently stop applying
- [reverseDirection() rows anchor on the FOLLOWING label](pricing_reversedirection_terminator_label.md) ⚠️ — an inserted block between the values and the terminator kills the crawl (PennyMac loan_amount_adj2 vs the 08/28 buydown
- [Specials row collapse: re-check the gate, not just the crawlNote](pricing_special_row_collapse_recheck_gate.md) ⚠️ — Giant/JetAdvantage 09/04 merged gov+conventional specials into one row
- [Staging pricing UI test recipe](project_staging_pricing_ui_test_recipe.md) — viet18.com = LF staging (logged-in Playwright profile); lender pool gated by company LenderAgreement.qm_active → check /

## Qualification Matrix Updates
- **[SKILL_UPDATE_QUALIFICATION_MATRICES.md](../docs/SKILL_UPDATE_QUALIFICATION_MATRICES.md)** — update/create program eligibility + pricing matrices in `*Tables.java` (moso-pricing): ValidateCalculator rules + ConditionTableInfo adjustment tables; workflow, condition builders, checklist
| [project_structure.md](project_structure.md) | GWT Java project file index — file counts and package structure for fast file lookup |
| [infrastructure_index.md](infrastructure_index.md) | Known infrastructure class paths by concern — use before grepping |

- [com.ignored tests naming](project_ignored_tests_naming.md) ⚠️ — dev-only harnesses in moso-pricing `com.ignored` must be named `*Tools`, never `*Test`

## Ratesheet Sweep
- [Last routed lender email = public GCS object](ratesheet_email_gcs_object_last_routed.md) — `curl -I lender-rate-email/<LenderType>` shows when mail last passed routing, no gcloud needed
- [Downloader "all constants already exist" is a false-skip](ratesheet_sweep_emet_probe_flag.md) — fires on 404s AND when the day's constant is pre-registered (hit EMET/PennyMac/Rocket-Corr/LoanStream-NonQM 08/20)
- [GCS history recovery for clobbered ratesheets](ratesheet_gcs_history_recovery.md) — history/<Lender>/<y>/<m>/<d>/ holds every upload; this Mac's gsutil is read-only (needs gcloud auth login for writes)
- [moso-pricing "cannot find symbol PylonInputs" = stale M2](project_moso_pricing_pylon_apis_m2.md) — install packs/pylon-apis to M2 first, then rebuild moso-pricing
- [Sweep Slack DM must be split at 5000 chars](ratesheet_sweep_slack_dm_split.md) — buckets in the main DM, Jira block as a thread reply; never drop a flagged lender to fit
- [QM/Non-QM share one GCS file](ratesheet_sweep_qm_nonqm_shared_gcs.md) — group by post-download SHA (not a fixed lender list); also Jet Advantage/Giant Lending are dupe slugs for one lender
- [download-ratesheet.sh date detector is flaky](ratesheet_sweep_mvn_date_detector_flaky.md) — mvn-based detector hangs/fails silently; always pass --no-detect and extract date yourself in Python
- [Housing history vs event vs seasoning mapping](pricing_housing_history_event_seasoning.md) — 1x30x12=mortgageLates, BK|FC|SS=creditEvent, >=36MO/24~35MO=bankruptcyPeriodType buckets
- [No essay comments in parser code](feedback_no_essay_comments_parser_code.md) — bare row definitions only; narrative/fix-history goes to docs/lenders/<slug>/history.md, class javadoc = 2-3 lines
- [ratesheet-watch daily change detection](project_ratesheet_watch.md) — tool layout, cron, gotchas, Phase-2 gate
- [SyncGmailLastLoginCronOp reverts LF Admin datafixes](project_gmail_cron_wipes_admin_datafix.md) — daily 16:00 ICT cron re-saves active LF admins with stale data; write after 17:00 + re-verify next day
- [parser-fix.sh shows PASSED for @Disabled tests](project_disabled_tests_false_pass.md) — check for Skipped:1 / @Disabled when b2 fails but local passes
- [Downloader guesses one extension](ratesheet_downloader_wrong_extension.md) ⚠️ — a 404 on the guessed ext reports as "all constants already exist"; probe all 5 exts but try the BASELINE ext first
- [Big PDF size jump can be a render artifact](ratesheet_pdf_size_jump_render_artifact.md) — identical page count + same text length + one extra embedded image = print-to-PDF blowup, not new content
- [Verify sweep snapshots actually persisted](ratesheet_sweep_verify_snapshot_persist.md) — 08/25 rendered but never wrote snapshots; next run's deltas silently span 2 days
- [Parallel downloader collision in sweeps](ratesheet_sweep_parallel_downloader_collision.md) — take the exact `File:` path, never sweep the resources dir; Giant Lending + Jet Advantage share one filename (5 lenders
- [Verify downloaded ratesheet content](ratesheet_download_verify_content.md) — download-ratesheet.sh can save a stale sheet; check Effective date + SHA vs direct curl of GCS
- [expected-new-adj deletions = clobbered baseline](ratesheet_expected_new_adj_baseline.md) — a line removed from expected-new-adj/*.txt with no RatesheetFiles change means a stray accept, not a parser bug
- [BFF QM sheet redesigned 07/29, parser expects dead Jumbo page](project_bff_qm_sheet_redesign.md) — snapshot baseline contaminated by PennyMac XLSX clobber 05/22; QM tests band-aided to NonQM sheet (MOSO-16983)
- [Provident: 3 stacked problems](project_provident_imperva_block.md) ⚠️ — 09/03 commit 33c46f7d (local, unpushed) fixes Blazor stale login + password-expiry interstitial + Credit Fee Cap table r
- [Cap values are COST, not the sheet price](pricing_premium_caps_sum_not_min.md) ⚠️⚠️ — a raw 99.000 Max Price clamps net cost to 99 points; ≥100 is silently discarded. Use PREMIUM_CAP_VALUE_HANDLER. Also: premiumCaps() sums, never MINs — multiple cap tables under one gate blend into a single added cap; use ONE table + HitHighest + PREMIUM_CAP_VALUE_HANDLER for MIN semantics
- [Literal shadows function field in quote payloads](pricing_literal_shadows_function_field.md) ⚠️ — saved/linked/loan quotes carry derived fields as literals that bypass Field functions
- [VA funding fee: PQ (Pre-qualification) falls to IRRRL row](pricing_va_purchase_refi_toggle_stale_rows.md) ⚠️ — Quote.va_funding_fees checks only PM/PA, not PQ, so VA Leads in Pre-qualification get 0.5% IRRRL instead of purchase-by-LTV (escalation 37537847200); also documents a separate real bug: Purchase↔Refinance toggle doesn't refresh the rate list
- [Jira test comment = per-scenario matrix](feedback_jira_test_comment_scenario_matrix.md) — S1/S2 blocks in {noformat}: inputs, eligible/ineligible + reason, each adj line + band, TOTAL
- [Verify staging via the pricer op, not the GWT form](feedback_staging_verify_via_op_call.md) — browser_evaluate fetch `/exec/GetNonQMRatesOp` with the UI's headers + enum ordinals (PM=2, CashOut=1!
- [Staging = viet18 / lenderrate-master + test login](reference_staging_viet18_login.md) — www.viet18.com, account chauchau.inc@gmail.com / Phuong123456 (Trung 09/08); log in yourself for /test-task
- [Jira REST create/transition workflow](reference_jira_rest_workflow.md) — trung-jira = local `jira` viewer skill; create via curl, board 2, transition chain 841→4→851 to Ready for Review
- [NewRez moved wholesale to Polly](project_newrez_polly_migration.md) ⚠️ — public no-auth URL, but 27-sheet layout matches 0/26 parser sheet names and Polly prices != ND3 (comp plan P6-A-A
- [NewRez H2O ND2 -> ND3 rename](project_newrez_h2o_nd2_to_nd3.md) — unmatched dropdown search keeps the DEFAULT sheet and exports it silently
- [Pylon restructured-principal fix is uncommitted WIP](project_pylon_restructured_principal_wip.md) ⚠️ — escalation 37521807093 fix exists only in the moso-pricing working tree, unverified, no Jira
- [Mega Capital MegaAgencyX block was unparsed](project_shared_conv_homeready_rate_rows_tera.md) ⚠️ — "shows the Home Ready rate" = DU/LP AGENCY block used instead of the MAX* block
- [moso-pricing cannot build inside a git worktree](project_moso_pricing_worktree_build_fails.md) — parent pom copies .git/HEAD as a resource; `.git` is a file in worktrees → maven-resources fails
- [Jira task writing style](feedback_jira_task_writing_style.md) — "tạo task" ⇒ trung-jira skill Mode B: short, non-tech, 4 sections (What was reported / Why / What changed / How to check
- [Jira tickets in English](feedback_jira_english.md) — summary + description always English, short; Vietnamese only in chat with Trung
- [Parser-failed Jira convention](project_parser_failed_jira_convention.md) — `[Parser failed] <Lender>: MM/DD/YYYY` + label parser (Yên creates them)
- [Vendor AE survey is the authority for conventional FICO floors](project_conventional_fico_ae_survey.md) ⚠️ — "Min Fico Conventional" sheet (31 Aug 2026) outranks matrix readings
- [Grid is not a floor on any axis: FICO/DSCR/LTV outside the bands quotes at base price](pricing_fico_grid_below_bottom_band_quotes.md) ⚠️ — N/A cell (999) only blocks its own band; min DSCR / units / citizenship gates must be explicit ValidateCalculators (Home
- [NA cells in an incentive grid = 0, not deny](pricing_na_cells_incentive_grid_navalue.md) ⚠️ — default NA→999 silently drops the whole lender; PennyMac FICO/CLTV (18) hid every >400k LTV>90 / FICO<700 loan 07/29→09/
- [Parser Bot (tools/parser-bot)](project_parser_bot.md) — Chat triage/fix bot merged to tools main locally 2026-09-04; Phase A pending Trung: push moso-pricing + SystemProp
- [LoanUnited VA HB 640+ moved tabs, was not retired](project_loanunited_va_hb_640_moved_not_retired.md) ⚠️ — 06/09 called it retired but it moved Tango → Government Standard and still prices daily
- [Label-only ratesheet diff hides value changes](ratesheet_label_diff_misses_value_changes.md) — "0 changed labels" ≠ nothing changed; diff labels and numbers separately
- [Sweep buckets come from masked-text diff, not byte size](ratesheet_sweep_masked_text_diff.md) ⚠️ — mask digits AND parens/`%`, filter AM/PM+commentary noise, compare Excel sheet-name sets
- [Ext-probe fallback can hit a dead GCS object](ratesheet_ext_probe_stale_object_trap.md) ⚠️ — Provident.html was last modified 2017; reject fallback hits older than the baseline. Also: Florida.xls is OOXML behind an .xls name — read via BytesIO
- [Side-by-side Excel blocks: column-slice when labels repeat](pricing_side_by_side_blocks_column_slice.md) — getSheet joins a row into ONE line; same-label ladders need `getSheet(sheet, fromCol, toCol, fromRow, toRow)` (0-based
- [NonQM Correspondent channel initiative](project_nonqm_correspondent_channel.md) — MOSO-17158 implemented 2026-09-07, unpushed; all 3 repos fast-forwarded into local master (branches deleted)
- [lender_paid silently drops every correspondent lender](pricing_lender_paid_drops_correspondent_lenders.md) ⚠️ — `RateOps.isCorrespondent()` returns false on compensation_type=lender_paid before reading channel
- [NonQM pricer: stale channel=Correspondent hides ALL lenders silently](pricing_nonqm_correspondent_channel_hides_all_lenders.md) ⚠️ — rows=0 + empty ineligible_products + generic note; check `channel`/`alert_lender` on the loan before validations (esc 37
- [NonQMQuoteServer never computed CLTV](pricing_nonqm_cltv_never_computed.md) ⚠️⚠️ — fixed MOSO-17186 (engine) + MOSO-17188 (AAA colName); CES itself then REMOVED entirely from AAA+EMET (home-equity/HELOAN-family, no dedicated engine yet) — don't confuse with the has_equity_loan UI fix, which stays (needed by AmWest/LoanStream/JetAdvantage's unrelated Subordinate Financing rows)
- [Rocket Pro DSCR: "$500k max cash-out" rule is the Super Jumbo footnote, sheet says LTV<65% unlimited; DSCR 30-Day column unparsed](project_rocket_dscr_cashout_rule_wrong.md) ⚠️ — blocks eligible cash-out DSCR loans; lock 30 → "Only 45-day lock is supported"
- [Read a prod Loan read-only via moso *Tools](project_read_prod_loan_readonly_tools.md) — runRemoteOn(PROD)+NS.set(LOAN_FACTORY)+Bundle().readOnly() (Bucket<Bean>)
- [rate() tables go in rateAdjustmentCalculators(), never calculators()](pricing_rate_keyed_tables_go_in_rate_adjustment_calculators.md) ⚠️ — parse + lender tests stay green, only b2/b4 ConvertTableInfoToJsTest fails; reference AnnieMacTables.rateAdjCalculators
- [LF approved lenders are public at /our-lenders](reference_lf_our_lenders_public_approved_list.md) — 237 cards, slug id = LenderType id, badges = loan types; fresh lender-rate-email object ⇒ has_rate=true
- [Per-lender LO-license carve-out is data, not code](project_nonlicense_setting_lo_carveout.md) — NonLicenseSetting.states_lo + lender/product/occupancy items via LoanUtils.checkLicenseForAgent; AmWest wholesale rule 35263227012 already exists, AmWest Corr blocked by non_qm_active=false
