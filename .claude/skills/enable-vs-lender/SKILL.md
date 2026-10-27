---
name: enable-vs-lender
description: Use when a lender starts accepting VantageScore 4.0 — "lender X thêm VS", "X nhận Vantage", "bật VS cho X", "X vừa approve VantageScore", "X's new ratesheet has a FICO/Vantage column" — and to re-check an already enabled lender when its sheet changes (PennyMac 10/06 added FHA Streamline and VA IRRRL). Reads the sheet, classifies it (one shared FICO/Vantage column, offset +20, or FICO only), decides which products and scope price on VantageScore, then wires it in the same change: vantageCondition(), .ficoOnly() on tables the sheet does not extend to Vantage, parser label changes, tests, lender docs and the VS report artifact. Never switches on a lender whose sheet still offsets the Vantage bands.
argument-hint: "<LenderType> [ratesheet path | latest] — what the lender said (AE answer, tracker row, sheet footnote)"
allowed-tools: Bash, Read, Edit, Write, Glob, Grep, Agent
---

# Enable VantageScore for a lender

> **House rules.** Per-task working files (specs, test cases, results, screenshots) go ONLY to `/Users/trungthach/IdeaProjects/docs/changes/<KEY>/`
> (workspace, outside every git repo). Docs stay few: the rule lives in `moso-pricing/docs/vantage-score-pricing.md`, the lender facts in
> `moso-pricing/docs/lenders/<slug>/`. **Never commit or push** unless asked, never invent a Jira key (ask; one commit per key, and the parser change and
> the VS switch are separate commits; if the user waives the key, a short descriptive subject in the repo's recent style, no `MOSO-` prefix, still never push).
> Tell the user about any data fix up front (a new or reshaped parsed table needs a re-parse right after deploy).

## What already exists (do not rebuild it)

The engine prices a lender **twice** when it is switched on, once on VantageScore and once on Classic FICO, and keeps the cheaper rate
(tie = FICO). A lender is "on" only through its own `*Tables` class. Read `moso-pricing/docs/vantage-score-pricing.md` first; in short:

| Piece | Where |
|---|---|
| Switch + scope of a lender | `HasTableInfos.vantageCondition()` in `<Lender>Tables` (default: never) |
| A table the sheet does not extend to Vantage | `.ficoOnly()` on its builder; the Vantage pass skips it |
| Which products can price on VS at all | `QuoteServer.VANTAGE_PRODUCTS`: agency conforming, FHA Streamline, VA IRRRL |
| Two passes, merge, "VS better / FICO better" | `RunPricingOp` + `VantageRateMerge` (alerts: `GetBestRate`) |
| The loan's own VS | `Loan.vantage` (3 bureaus, 4.0, every borrower), `LoanQuoteUtils.attachVantageScore` |
| Quote form with no loan | picked score = FICO = VS (`assumeVantageEqualsCreditScore`, flag `vantage_assumed`) |
| Adjustment lines of a row priced on VS | whole word `FICO` becomes `VantageScore` ("VantageScore (760 - 779)"): `AdjustmentUtils.nameTheVantageScore`, called from `RateOps.process` |

Nothing else is lender-specific. If the engine needs a new product type or a new rule, stop and ask the user: `QuoteServer` is shared by every lender.

## Step 1. Read the sheet

```bash
cd /Users/trungthach/IdeaProjects/packs/loan && ./lender-info.sh <Lender>             # Tables class, parsers, doc folder
./download-ratesheet.sh <Lender> --no-detect                                          # GCS first; prove it is the latest (see check-lender-rate)
python3 ~/.claude/skills/enable-vs-lender/scripts/vantage-scan.py <sheet>            # every "Vantage" mention + its row
python3 ~/.claude/skills/check-lender-rate/scripts/dump-sheet.py <sheet> --sheet "<name>" --rows 8-22   # read the grid by real coordinate
```

Also read the lender's `docs/lenders/<slug>/README.md` and the top of `history.md`, and the AE survey row (link in the artifact's "Nguồn").

## Step 2. Classify

| The sheet shows | Class | Action |
|---|---|---|
| One band set under a header like `FICO/Vantage`, no second column | **A. shared** | switch on (steps 3 to 7) |
| A separate "Vantage Score" column beside "FICO Score", or Vantage bands one step above FICO (+20) | **B. offset** | stay FICO. JMAC (re-checked 10/13), Freedom before 10/07 and PennyMac before 10/01 are this. Record it in the lender doc, say so, stop |
| No mention of Vantage | **C. FICO only** | stay FICO; ask the AE before anything. Never switch on by assumption |
| Some grids `FICO/Vantage`, others FICO only | A, per table | `.ficoOnly()` on the FICO-only ones |

Two columns with identical band labels would be a shared column printed twice; check the labels in the grid before calling B. If the scan
finds a "Vantage" column but the lender's own words say the bands moved, B wins.

## Step 3. Decide the scope (from the sheet's footnotes, not from habit)

Build `vantageCondition()` with one clause per product, from what the sheet says:

- **Occupancy**: investment / second-home credits that say "Vantage not eligible" mean owner-occupied only (`OWNER`).
- **Minimum score**: a ladder note such as `<700 FICO (Vantage Not Eligible)` means `vantage(700, 850)`.
  An add-on printed twice one band apart (Rocket: `FICO < 620` 1.000 beside `VS < 640` 1.000) with only the FICO row
  modelled means a floor at the top of the VS row (`vantage(640, 850)`): above it neither row applies on either model.
- **LPMI**: if the LPMI grids are keyed by model or the sheet is silent, exclude it (`MI_PAID_BY_LENDER.not()`).
- **Tables headed FICO only** (PennyMac `FICO/CLTV (18)`): `.ficoOnly()`. The engine cannot tell which tables read the score, so a forgotten one
  is only caught by the quote test (step 5).
- **Government**: only FHA Streamline / VA IRRRL, and only when the grid header says `FICO/Vantage` (PennyMac: "Vantage applies to FHA Streamlines Only").
  Full Doc FHA, VA, USDA, Jumbo and Non-QM stay FICO.
- **Channel**: the AE survey covers TPO. Switch on the wholesale `*Tables`; the correspondent class stays off until the AE confirms.

Template (PennyMac):

```java
@Override
public AdjustmentCondition vantageCondition() {
  return AGENCY_CONVENTIONAL.and(OWNER).and(MI_PAID_BY_LENDER.not()).and(vantage(700, 850))
          .or(FHA_STREAMLINE_OR_VA_IRRRL);
}
// and on a FICO-only table builder:  .naValue(0d).ficoOnly().build();
```

Builders: `RangeCondition.vantage(a, b)` / `fico(a, b)`, `ConditionFactory.AGENCY_CONVENTIONAL`, `OWNER`, `MI_PAID_BY_LENDER`, `FHA_STREAMLINE_OR_VA_IRRRL` (all under
`moso-pricing/src/main/java/com/mosopricing/shared/parser/condition/`). `vantageCondition()` is declared in `HasTableInfos`, `ficoOnly()` on `TableInfo.Builder`.

## Step 4. Parser (only if the sheet's labels changed)

The scan and a parser run tell you. When a lender merges "FICO | Vantage" pairs into one column (PennyMac 10/01) or adds a Vantage column, the crawl
labels in `*Tables` change (PennyMac dropped the Vantage half of 30 paired labels). Run the usual loop and read the report, not the Maven log:

```bash
cd packs/loan && ./parser-fix.sh <Lender> --ratesheet <new sheet> --both
```

Fix labels in `*Tables`, accept expectations only with the user's go-ahead, update the lender README and history (CLAUDE.md rule). A header that only changed its text needs no parser change.
This is a parser change: its own Jira key and commit, apart from the VS switch.

## Step 5. Tests (the proof; all three)

| Test | Module | What to add |
|---|---|---|
| `VantagePricingByLenderTest` | moso-pricing `.../shared/parser/lender/` | the lender prices on Vantage inside its scope and stays FICO outside it (under the minimum, investment, LPMI, Jumbo, Full Doc government) |
| `VantageQuoteTest` | packs/loan `com/mvu/loan/` | parse the real sheet; price FICO against VS: `creditModel`, the `.ficoOnly()` table is skipped (adjustment note), a dearer VS keeps FICO |
| `VantageTwoPassTest` | packs/loan `com/mvu/loan/parity/` | `RunPricingOp` and the alert through the seam: cheaper VS wins and says "Vantage", a quote-form score says "FICO" where a FICO-only credit applies and nothing where both cost the same |

Engine-side tests that need no new lender code: `QuoteServerCreditModelTest`, `VantageRateMergeTest` (moso-pricing), `LoanVantageScoreTest` (packs/loan `.../shared/`).

```bash
cd packs/quote   && mvn -o install -DskipTests -Dgwt.compiler.skip=true            # only if quote changed
cd moso-pricing  && mvn -o test -Dgwt.compiler.skip=true                           # whole suite, about 600 tests
cd moso-pricing  && mvn -o install -DskipTests -Pjar-packaging -Dgwt.compiler.skip=true
cd packs/loan    && mvn -o test -Dtest=VantageQuoteTest -Dgwt.compiler.skip=true   # one class per run (surefire runs only the first)
```

If `testCompile` cannot find `Loan`, the IDE is rebuilding `target/classes`: wait until `find target/classes -name '*.class' | wc -l` is stable (about 10.7k) and rerun.
This Mac is nearly full: check `df -h /System/Volumes/Data` before building; every GWT recompile adds about 150 MB and at 0 bytes Bash itself fails (use the Terminal tool).

## Step 6. Docs, in the same change

- `docs/lenders/<slug>/README.md` (the sections that changed: scope, `.ficoOnly()` tables) and a dated entry at the top of `history.md`. Keep it short.
- `moso-pricing/docs/vantage-score-pricing.md`: the "Which lenders" line.
- The VS report artifact (Docs connector, never the Artifact tool): https://claude.ai/code/artifact/31691e71-1655-4a1f-9fb9-fac31b7e3124 . Read it, then edit the lender's row in
  "Lender nào dùng VS" (Trạng thái trong MOSO), the lead paragraph, "Còn mở" and the test counts. Plain Vietnamese, no code dumps.
- `docs/lenders/check-lender-docs.sh` must pass.

## Step 7. Give the user test cases (computed, not guessed)

Copy `references/cases-probe.java.txt` into `packs/loan/src/test/java/com/mvu/loan/parity/`, adapt the lender, the sheets (the one in the user's local datastore AND the newest) and the
scenarios, run it, read the table it writes, then delete the class and its compiled copy. Cover: the quote form at one score above and below the lender's FICO-only credit
threshold, under the minimum score, investment, LPMI, a loan with its own higher VS (expects "VS better" and "VS n"), a loan whose VS is only one band up (expects "FICO better").

## Report back

One short message: the class (A/B/C) and why (cell references), the scope you set, the tables flagged `.ficoOnly()`, tests run with counts, what is **not** verified (local UI, staging),
the AE questions, deploy notes (re-parse, restart "Moso - default" and "Moso - pricing", install order), and the files changed. Nothing committed.

## Known caveats to say out loud

- In the Vantage pass the minimum-score validations read the VantageScore, so a loan under the floor on FICO can price on VS. Ask the AE whether the floor stays on Classic FICO; if it does, add a `fico(floor, 850)` clause to the product's side of `vantageCondition()` (it is evaluated while `fico` is still the Classic FICO).
- FHA's own VS4 date in our sources is 2027-01-01. A sheet that says "Vantage applies to FHA Streamlines" still needs the AE to confirm it is live.
- At one score (the quote form) VS can only tie or lose when the only FICO-only table is a credit; "VS better" shows only for a loan whose real VS is higher.
- The relabel above looks for the word `FICO`. A lender whose adjustment lines say something else ("Credit Score", "FICO/Vantage") keeps its own wording on a VS row: open the rate popup of a VS row in step 7 and read the lines.
- On a form opened from a loan the credit score box keeps the loan's FICO band (700 - 719) while the rows are priced on its VS band (760 - 779); a second VS box is designed, not built. Say so when a tester asks why the box does not show the VS.
