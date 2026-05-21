# Parser Fix Cookbook

<!-- Auto-updated by fix-parser pipeline. Do not edit manually. -->

## LoganFinance
- **paths**: Tables=`moso-pricing/.../LoganFinanceNonQMTables.java`, Rate=`moso-pricing/.../LoganFinanceNonQMPdfParser.java`, Adj=`moso-pricing/.../LoganFinanceNonQMAdjPdfParser.java`
- **tier_history**: [0, 0]
- **tier_0_streak**: 2
- **last_fix**: 2026-04-02
- **last_error**: expectation mismatch (values changed)
- **notes**: NonQM lender, rate test is @Disabled/skipped

## ChampionsFunding
- **paths**: Tables=`moso-pricing/.../ChampionsNonQMTables.java`, Rate=`moso-pricing/.../ChampionsNonQMPdfParser.java`, Adj=`moso-pricing/.../ChampionsNonQMAdjustmentPdfParser.java`
- **tier_history**: [2, 0]
- **tier_0_streak**: 1
- **last_fix**: 2026-04-02
- **last_error**: verified pass (same ratesheet as yesterday)
- **last_tier2_fix**: New page inserted (Activator Prime Bank Statement) at page 2 shifted all Accelerator/Ambassador pages +1. Dropped 85% LTV column from DSCR 1-4 Units table. Multiple row labels changed (FICO 680→660, BK/FC/SS row renames) and new rows added (lower FICO ranges, Short Term Rental, Asset Depletion, mortgage lates) (2026-04-01)
- **notes**: NonQM lender, uses PDF parser with page-based content extraction. LenderType enum name is "Champions" (not ChampionsFunding). Download with `--nonqm`. Rate test works.

## ADMortgage
- **paths**: Tables=`moso-pricing/.../ADMortgageTables.java`, Rate=`moso-pricing/.../ADMortgagePdfParser.java`, Adj=`moso-pricing/.../ADMortgageAdjustmentPdfParser.java`
- **tier_history**: [0]
- **tier_0_streak**: 1
- **last_fix**: 2026-04-01
- **last_error**: both tests passed with new ratesheet (expectations only)
- **notes**: Has both regular and NonQM variants. Rate test is @Disabled/skipped. Jira title may not say NonQM but regular parser is the one that fails.

## JetAdvantage
- **paths**: Tables=`moso-pricing/.../JetAdvantageTables.java`, Rate=`moso-pricing/.../JetAdvantagePdfParser.java`, Adj=`moso-pricing/.../JetAdvantageAdjustmentPdfParser.java`
- **tier_history**: [1]
- **tier_0_streak**: 0
- **last_fix**: 2026-04-02
- **last_error**: CRAWL_MISMATCH on "December Pricing Special Adjustment" table
- **last_tier1_fix**: CRAWL_MISMATCH on specialAdj → renamed "December Pricing Special Adjustment" to "Pricing Specials Adjustment", broadened condition FHA/VA→GOV, updated crawlNote to "Non-Select FHA, VA, USDA & DPA (STD Bal & High Bal)" (2026-04-02)
- **notes**: Has both regular (PDF) and NonQM (XLSM) variants. The specialAdj table is seasonal/monthly — crawlNote changes every month (Dec→Mar→Apr). Expect Tier 1 CRAWL_MISMATCH each month for this table.

## SunWest
- **paths**: Tables=`moso-pricing/.../SunWestTables.java`, Rate=`moso-pricing/.../SunWestExcelParser.java`, Adj=`moso-pricing/.../SunWestAdjustmentExcelParser.java`
- **tier_history**: [1]
- **tier_0_streak**: 0
- **last_fix**: 2026-04-02
- **last_error**: CRAWL_MISMATCH on "Government Apply All Loan Purpose adjustments"
- **last_tier1_fix**: CRAWL_MISMATCH on govAllLoanFicoAdj → extraction column shifted N→M, added colRange for FHA/USDA vs VA split columns (2026-04-02)
- **notes**: Uses Excel parser (.xlsx). Shares ratesheet with SunWestCorrespondent (same file, different parser). Download as "SunWest" (no suffix).

## SunWestCorrespondent
- **paths**: Tables=`moso-pricing/.../SunWestCorrespondentTables.java`, Rate=`moso-pricing/.../SunWestCorrespondentExcelParser.java`, Adj=`moso-pricing/.../SunWestCorrespondentAdjExcelParser.java`
- **tier_history**: [1]
- **tier_0_streak**: 0
- **last_fix**: 2026-04-02
- **last_error**: CRAWL_MISMATCH on "Government Apply All Loan Purpose adjustments" (same as SunWest)
- **last_tier1_fix**: Same fix as SunWest — extraction column N→M, added colRange for FHA/USDA vs VA split (2026-04-02)
- **notes**: Shares ratesheet file with SunWest. Always fix both together.

## Emporium
- **paths**: Tables=`moso-pricing/.../EmporiumTPONonQMTables.java`, Rate=`moso-pricing/.../EmporiumTPONonQMPdfParser.java`, Adj=`moso-pricing/.../EmporiumTPONonQMAdjustmnentPdfParser.java`
- **tier_history**: [0]
- **tier_0_streak**: 1
- **last_fix**: 2026-04-02
- **last_error**: expectation mismatch (4 values in Alt Doc table)
- **notes**: NonQM lender (EmporiumTPO). Download with `--nonqm`. LenderType resolves to "EmporiumTPO". Test methods: testEmporiumNonQM (adj), testEmporiumTPONonQM (rate).
