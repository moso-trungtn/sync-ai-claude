---
name: setup-lender
description: Use when a lender has to be set up on the LOCAL dev server or on STAGING so its pricing can be tested — "setup lender X", "setup SpringEQ local", "load rate + adjustment cho X", "copy lender từ prod về local", after /new-parser built a parser and before testing it locally or on staging. Copies the Lender and its Loan Factory LenderAgreement from PROD, then loads the lender's rates and adjustments from the test ratesheet. Usage: /setup-lender <LenderType> [local|staging]
---

# /setup-lender — copy lender from PROD, load rates + adjustments

> Working files (logs, notes) go to `/Users/trungthach/IdeaProjects/docs/changes/<KEY>/` or the scratchpad, never into a repo.

Six steps, always in this order, **each in its own JVM** (one `mvn` run per step):

| # | Method (`SetupLenderTools#…`) | What it does |
|---|---|---|
| 1 | `step1DownloadLender` | read `Lender` (global NS) from PROD into the customization backups dir |
| 2 | `step2UploadLender` | upload that `Lender` to the target |
| 3 | `step3DownloadLenderAgreement` | read `LenderAgreement` (LOAN_FACTORY NS) from PROD |
| 4 | `step4UploadLenderAgreement` | upload it to the target, LOAN_FACTORY NS |
| 5 | `step5LoadRates` | `QuoteTester.loadRates(<LenderType>)` on the target (global NS) |
| 6 | `step6LoadAdjustments` | `<AdjParser>.parseInputStream(<RatesheetFiles constant>)` on the target, **global NS** (pricing reads `LenderAdjustments` there; `-Dadj.company=true` only for `LenderParserMap.CUSTOM_RATESHEET_LENDERS`) |

Why separate JVMs: a PROD `runRemoteOn` installs `CloudTasksQueue` as the static queue service; a later local save in
the same JVM (Lender's afterSave queues a task) fails with "Could not find default credential in DB". Never merge a
download and an upload into one run.

Class: `moso/src/test/java/com/ignored/lenderrate/SetupLenderTools.java` (dev-only, parameterised by `-D` properties —
never edit it per lender). Runner: `scripts/run-step.sh <step> <LenderType> <server> [-D...]`. PROD is only READ.

## 0. Resolve inputs

- `LENDER` = `LenderType` constant (e.g. `SpringEQ`), must exist in `packs/quote/.../typekey/LenderType.java`.
- `SERVER` = `""` for local (`localhost:8888`). Staging = `lenderrate-master` (used for CakeMortgage 2026-10-21; web app viet18.com).
- `ADJ_PARSER` = FQCN of the adjustment parser (`com.mosopricing.server.op.parser.adjustment.<Lender>…Parser`). QM + NonQM lender → run step 6 once per parser (and its ratesheet).
- `RATESHEET` = `RatesheetFiles` constant name the parser tests use (`grep -n <Lender> packs/loan/src/test/java/com/mvu/loan/RatesheetFiles.java`).
- Step 5 needs a branch for the lender in `packs/loan/src/test/java/com/mvu/loan/QuoteTester._loadRates`
  (`new <Lender>RateParser().parse(getRateSheetStream(RatesheetFiles.X), EMAIL)`); add it if missing
  ("Does not support parsing rate for lender").

## 1. Preflight

- Disk: `df -h /System/Volumes/Data` — need ≥ 3 GB. Under that, clean dead GWT code-server dirs
  (memory: reference_local_moso_test_recipe, "Disk is nearly full"). At 0 bytes the Bash tool itself dies: use
  `mcp__terminal__run_in_terminal`.
- Build (once per code change):
  ```bash
  cd ~/IdeaProjects/moso-pricing && mvn -o -q install -DskipTests -Pjar-packaging -Dgwt.compiler.skip=true
  cd ~/IdeaProjects/packs/loan   && mvn -o -q install -DskipTests -Dgwt.compiler.skip=true
  cd ~/IdeaProjects/moso         && mvn -o -q test-compile -Dgwt.compiler.skip=true
  ```
  `LenderType` changed → install `packs/quote` first. Never `mvn install` pylon-apis.
- Target up and on the NEW code. Local: "Moso - default" 8888 (+ "Moso - pricing" 8889 to quote), restarted AFTER the
  packs/loan install (WAR takes `loan-*.jar` from `~/.m2`); `curl -s -o /dev/null -w '%{http_code}' localhost:8888/` → 200.
  Trung starts the IDE servers. Staging: the commits must be deployed there first — ask, never deploy.

## 2. Run

```bash
R=~/.claude/skills/setup-lender/scripts/run-step.sh
$R step1DownloadLender            SpringEQ ""
$R step2UploadLender              SpringEQ ""
$R step3DownloadLenderAgreement   SpringEQ ""
$R step4UploadLenderAgreement     SpringEQ ""
$R step5LoadRates                 SpringEQ ""
$R step6LoadAdjustments           SpringEQ "" -Dadj.parser=com.mosopricing.server.op.parser.adjustment.SpringEQNonQMAdjustmentPdfParser -Dratesheet=SPRING_EQ_NON_QM_20261013
```
One at a time; stop at the first failure and report step + exception. Each run must show `Connected to: <expected server>`
(downloads: `lender-rate`; uploads/loads: `lenderrate-master on localhost` locally) and
`Tests run: 1, Failures: 0, Errors: 0, Skipped: 0`. Step 4 prints `Uploading to NS: 5716104026521600`.
Step 5 must print `Parsed <N> New <Lender> Rates` with N = rows × lock keys of the rate test; step 6
`Parsed new <Lender> Adjustments`. A 1-second "success" without those lines did nothing.

The runner adds `packs/loan/target/test-classes` to the classpath: the packs/loan pom excludes `**/ratesheets/*` from
the test jar, so without it step 5/6 fail with "Ratesheet may be excluded from test jar resource".
`java.io.FileNotFoundException: src/test/java/com/mvu/loan/server/LoanServer.java` from `DatafixLogger.initLog` is harmless.

## 3. Verify

- **Prove step 6 stored something**: a quote that hits the lender must not fail with `<Lender>: temporarily unavailable`
  (dev aborts the whole call). Root cause seen: `lenderAdj is null` in `ConditionTableInfo.calculate` = no
  `LenderAdjustments` under `<nonQMName|name>` in the global NS.
- New Non-QM lender: `/available_lenders` → lender row → **Non-QM Quotable** must be checked, else the lender is
  silently missing from results (PROD's agreement has it off until the lender is live). Say so in the report.

- Admin > Lenders: the lender record exists with the PROD has-rate toggles.
- A quote restricted to the lender (`alert_lenders: ["<Lender>"]`, Purchase locally) returns rates; its adjustments
  match the parser test expectations. Then `/test-task` (staging) or the local quote recipe.

## Pitfalls (seen)

- `LenderType.X.hasQM()` is a boolean, not the id — always `.id()` (2026-10-15).
- Download + upload in one JVM → "Could not find default credential in DB" (2026-10-15).
- Ratesheet missing from the test jar → step 5/6 fail; use the runner (2026-10-15).
- Disk full mid-build → `No space left on device` in testCompile (2026-10-15).
- Adjustment parser built OUTSIDE the remote call → its constructor-time `Bundle` commits nowhere, log still says
  "Parsed new … Adjustments" (2026-10-15). SetupLenderTools builds it inside the remote call.
- Adjustments loaded into LOAN_FACTORY NS → pricing (global NS) finds none (2026-10-15).
