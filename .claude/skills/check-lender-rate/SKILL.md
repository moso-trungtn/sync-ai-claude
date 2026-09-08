---
name: check-lender-rate
description: Use when checking a lender's rate/price or loan eligibility for one scenario — an LO says moso's price or LLPA/SRP doesn't match the lender's portal, someone sends a moso quote share link ("please help check <Lender> rate https://www.loanfactory.com/l/<key>") or a portal screenshot, or asks whether moso would reject a loan and on which rule. Covers resolving a share link into a scenario, downloading today's ratesheet, reconciling the full adjustment stack, running a scenario through a lender's ValidateCalculators, and auditing modelled rules against the lender's guideline matrix.
argument-hint: "[LenderName] [share link or Quote JSON] — a portal screenshot helps but is optional"
allowed-tools: Bash, Read, Edit, Write, Glob, Grep, Agent
---

# Check Lender Rate

Two different questions get asked with the same words. Decide which one is being asked
before doing anything, because they have different answers and different evidence:

| Mode | Question | Evidence |
|---|---|---|
| **price** | Does moso price this scenario the way the ratesheet says? | today's ratesheet + `RunPricingOp` |
| **eligibility** | Does moso block this loan, and on which rule? | `*Tables.validations()`, local |
| **gap** | Does moso enforce what the lender's guideline requires? | guideline matrix vs `validations()` |

"Rate is wrong" -> price. "Portal says ineligible but moso quotes it" -> eligibility, then
gap. When unsure, run price and eligibility; they are cheap and together they cover the
question.

**Never report "matches" without saying which mode you ran.** A price reconciliation says
nothing about whether the lender would approve the loan — reserves, tradelines, financed
properties and doc requirements are not modelled at all. Silence on that reads as an
all-clear.

## Start here, in every mode

```bash
python3 ~/.claude/skills/check-lender-rate/scripts/resolve-link.py --lender <LenderType> <url>
```

Accepts a `/l/<key>` link, a `quote_result` URL, or a bare query string; needs no login.
It prints the scenario, a Quote JSON literal for `RunPricingOp`, and a `QuoteServer`
builder for the eligibility loop. The `inviter` param is the LO to impersonate.

Share links carry enum **names** (`purpose=PM`, `income_to_ami=INCOME_120_TO_140_AMI`) and
`Yes`/`No` booleans. `EnumType._fromJson` accepts names, so no ordinal counting is needed.
If instead you are handed a raw payload with bare numbers, those are enum **ordinals**, not
`id()` constants — see Common mistakes.

## Mode: price

1. **Get today's ratesheet and prove it is today's.**
   ```bash
   cd packs/loan && ./download-ratesheet.sh <Lender> --no-detect
   ```
   Then verify all three, because the downloader can silently save a stale file:
   the saved file's SHA equals a direct `curl` of the GCS object, the GCS
   `last-modified` is today, and the sheet's own effective date agrees.
   ```bash
   shasum -a 256 src/test/resources/ratesheets/<new file>
   curl -sI https://storage.googleapis.com/lender-rate-ratesheet/<Lender>.xlsx | grep -i last-modified
   python3 ~/.claude/skills/check-lender-rate/scripts/dump-sheet.py <file> --rows 1-10
   ```

2. **Price the scenario as the LO.** Add a method to
   `moso-pricing/src/test/java/com/ignored/mosopricing/MosoPricingTools.java`, paste the
   Quote JSON from step 0, restrict to the lender with `"alert_lenders":["<LenderType>"]`,
   and impersonate the LO — without a user, `RunPricingOp` collapses to one row per lender
   per rate and can hide the mode you care about:
   ```java
   Bean lo = new Bundle().readOnly().find(Admin.TYPE)
           .whereEquals(Admin.email, "<inviter>").first();
   ThreadContext.setRequestUser(new AppServer().createSessionUser(lo));
   ```
   Use `RunNonQMPricingOp` only when the scenario really has `non_qm_*` fields.
   ```bash
   cd moso-pricing && mvn test -Dtest=MosoPricingTools#<method> -q
   ```

3. **Read the sheet by coordinate, never from a squashed dump.**
   ```bash
   python3 .../dump-sheet.py <file> --find "Escrow Waiver"
   python3 .../dump-sheet.py <file> --grid 615-633 --cols B-P   # header row + data aligned
   python3 .../dump-sheet.py <file> --cell C577
   ```
   Rate grids often start in column A while adjustment tables start in column B. `--grid`
   makes "which column is `<= $350,000`" unambiguous.

4. **Reconcile every line, not just the base rate.** Build the expected price by hand from
   the sheet — base price for the lock period, plus each adjustment that should fire
   (incentives, state SRP, escrow waiver, FICO×LTV, occupancy, units, DTI, loan-balance,
   premium cap) — and compare against `adjustment_detail` line by line. Note that parsed
   values carry the **cost** sign, so a sheet value of −1.125 appears as +1.125 when the
   parser uses `revertSignal(true)`.

5. **Before calling anything a mismatch**, check whether the lender's portal splits ONE of
   moso's combined values across two display lines (an LLPA/WHL line plus an SRP/MSR line).
   Sum them and compare against moso's single line.

6. **Classify a real gap.**
   - Sheet cell differs from moso's value -> parser bug. Draft the `Tables.java` fix,
     **show it and wait for confirmation** — never auto-edit pricing code.
   - Sheet cell equals moso's value but not the portal -> not a code bug. Check the loan's
     own fields (impounds, FICO, LTV, occupancy, lock period, comp, admin fee); one wrong
     flag usually explains the whole delta. Intraday repricing does too — the GCS sheet is
     the emailed one, timestamped on the sheet itself.
   - The portal's line item appears nowhere in the workbook (grep every sheet) -> the data
     is not in what moso ingests, e.g. a separate SRP schedule. Report as a known gap.

## Mode: eligibility

Local, no prod, seconds. Read `references/eligibility.md` for the mechanism, the full
share-link-to-`QuoteServer` field mapping, and the traps (`ltv` is a fraction; `isDU` is
the inverse of `use_lp`; `propertyType` beats `actual_number_of_units` on multi-unit
types).

The short version: `ValidateCalculator.isApplicable(quote)` is **true when the rule
blocks**, and `failReason()` is the message the LO sees. Loop a lender's `validations()`
over the scenario and print every rule with its verdict. Cross-check end to end by running
`RunPricingOp` restricted to that lender and reading the `note` — with one lender the deny
reason is visible, with many the row is just absent.

## Mode: gap

`validations()` covers the matrix **printed on the ratesheet**. The guideline holds the
rest, and moso does not model it. To answer "does moso enforce this rule":

1. Read the lender's `## Eligibility (guideline)` section in `moso-pricing/docs/lenders/`.
   If it already covers the loan type in question, stop here; the section is the answer.
2. Otherwise fetch the guideline. Every lender's documents sit in a world-readable Drive
   folder, indexed by a local registry built from PROD's `Lender.document_links`:
   ```bash
   G=~/.claude/skills/check-lender-rate/scripts/lender-guidelines.py
   python3 $G --find-lender nexbank                                   # locate the lender
   python3 $G --lender NexBank                                        # classify the folder
   python3 $G --lender NexBank --loan-type Conventional --download out/
   ```
   Build or refresh the registry (240 lenders, 3681 documents as of 09/07/2026):
   ```bash
   cd moso && mvn test -Dtest=LenderDocumentRegistryTools#dumpRegistry \
       -q -Dgwt.compiler.skip=true
   ```
   It writes `~/.cache/moso/lender-documents.json`, deliberately outside any git repo
   because the ids link to confidential guidelines. Rebuild it when a lender's documents
   change; nothing else depends on its freshness.

   **A lender publishes one guideline per product family.** Conventional, FHA, VA, Jumbo and
   Non-QM are separate documents on separate revision dates, so reading one says nothing
   about the others. Scope the finding to the loan type you actually read.

   **Loan type is not always enough to find the document.** Lenders file Non-QM and
   portfolio products under their own program names (HomeBridge has `Access`,
   `Elite Access`, `Investor Solution`), which map to no `LoanType`. The tool prints those
   scopes as `?token` and says so when a loan type matches nothing; pick by hand from the
   full listing rather than concluding the lender does not offer the product.
3. Read the PDF's own header date, not the date in its filename; the filename carries the
   upload date and the two differ by days or weeks.
4. Compare the guideline's rules against `validations()` and sort each one into:
   - **a real overlay moso does not enforce** -> a ticket, with the cheapest reproducing scenario
   - **correctly absent** -> the guideline defers to DU/LPA, so there is no number to model.
     These documents are laid out as `Topic | Fannie Mae (DU) | Freddie Mac (LPA)` tables, and
     most credit rules land here. Record it as resolved, not as a gap.

`references/matrix-doc-format.md` has the section format and the rules for filling it in.
Keep the PDFs in a scratch directory. They are lender-confidential, so never commit them and
never send them anywhere external.

## Common mistakes

- Reporting "khớp" after a price check only, leaving the LO to read it as "the loan is fine".
- Trusting a local ratesheet fixture; they go stale in days.
- `quote_lender` / singular `alert_lender` to restrict a run — only `alert_lenders` (a list) filters.
- Running `RunPricingOp` with no user, then concluding a mode is missing when `filterLenders()` merely hid it.
- `new SessionUser(bean)` — NPEs on `kind()`; use `new AppServer().createSessionUser(bean)`.
- Reconciling base prices from `find(Rate.TYPE)` — legacy entities, returns stale rows. Live pricing reads `RateTable` (`LenderRateLoader`); take `base_price` from the `RunPricingOp` rows.
- Treating a bare `quote_lender:106` as `LenderType.id()==106`; it is the ordinal (106 = `NewRezCorrespondent`, not `NewRez` id=114). Never insert into these enums mid-list.
- `RunNonQMPricingOp` on a QM quote — it forces `loan_type=Non_QM` and throws on missing `NON_QM_REQUIRED_FIELDS`.
- Naming a throwaway harness `*Test` in `com.ignored` — CI surefire runs it. Use `*Tools`.
- Reading `ltv` as a percent in a `QuoteServer`; it is a fraction, and 52.3 means 5230% LTV.

## Worked example

NexBank, 2026-09-03, `/l/RsJfe5f981579d5` — WA investment purchase, $340k/$650k (LTV
52.3%), FICO 800, no escrow, DU, 30-day lock. Expected price was built from
`nex_bank_20260903.xlsx` as base 30-day price plus incentive +0.125, WA SRP −0.066, WA
escrow waiver −0.158, FICO≥780/LTV30-60 0.000, Investment/LTV30-60 −1.125, and the
loan-balance adjuster from the `<= $350,000` column, capped at 106. Matched
`RunPricingOp` to three decimals at every rate from 5.5 to 7.625.

Two real gaps surfaced that the scenario itself did not hit: the sheet's
"30/25yr Conv Fx (Non-HB) Investment >=$400k +0.25" incentive row is absent from
`currentIncentivesAdj`, and Mortgage Connect has no premium cap despite the sheet's
"lesser of 102.75 or $20,000" note.
