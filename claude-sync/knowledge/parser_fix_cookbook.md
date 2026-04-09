# Parser Fix Cookbook

<!-- Auto-maintained by fix-parser pipeline. Do not edit manually. -->

## BrokersFirstFunding
- **paths**: Tables=`moso-pricing/src/main/java/com/mosopricing/shared/parser/lender/BrokersFirstFundingTables.java`, Rate=`moso-pricing/src/main/java/com/mosopricing/server/op/parser/rate/BrokersFirstFundingPdfParser.java`, Adj=`moso-pricing/src/main/java/com/mosopricing/server/op/parser/adjustment/BrokersFirstFundingPdfAdjParser.java`
- **tier_history**: [1]
- **tier_0_streak**: 0
- **last_fix**: 2026-04-08
- **last_error**: CRAWL_MISMATCH — row label '2 - 4 units' not found in Jumbo Adjustments table
- **last_tier1_fix**: CRAWL_MISMATCH on Jumbo Adjustments → removed UNIT_2_4 row ("2 - 4 units") that lender dropped from ratesheet (2026-04-08)
- **notes**: Regular BFF parser. Ratesheet is PDF. Both QM and NonQM share same PDF file.

## WindsorMortgage
- **paths**: Tables=`moso-pricing/src/main/java/com/mosopricing/shared/parser/lender/WindsorMortgageTables.java`, Rate=`moso-pricing/src/main/java/com/mosopricing/server/op/parser/rate/WindsorMortgageExcelParser.java`, Adj=`moso-pricing/src/main/java/com/mosopricing/server/op/parser/adjustment/WindsorMortgageAdjustmentExcelParser.java`
- **tier_history**: [-1]
- **tier_0_streak**: 0
- **last_fix**: 2026-04-09
- **last_error**: FAILED: Ratesheet completely restructured — old sheets (Conv LLPA, Conventional and Government) gone, replaced by Medical Professional, NonQM Products, Expanded Prime Plus LLPA, Sharp LLPA, DSCR Plus LLPA
- **notes**: Needs /new-parser rebuild. Ratesheet format fundamentally changed 2026-04-09.

## TPOGo
- **paths**: Tables=`moso-pricing/src/main/java/com/mosopricing/shared/parser/lender/TPOGoTables.java`, Rate=`moso-pricing/src/main/java/com/mosopricing/server/op/parser/rate/TPOGoPdfParser.java`, Adj=`moso-pricing/src/main/java/com/mosopricing/server/op/parser/adjustment/TPOGoAdjustmentPdfParser.java`
- **tier_history**: [2]
- **tier_0_streak**: 0
- **last_fix**: 2026-04-09
- **last_error**: Page shift — new pages inserted (Gov Reno, Gov ARM, Conv ARM, Conv Reno). Adj pages 8→10, 12→14. Rate page 10→12.
- **last_tier1_fix**: —
- **notes**: PDF parser (27 pages). Page numbers shift when lender adds new products. Gov rates page 0 and Conv rates page 4 stable. Watch for page shifts.

## ElevenMortgage
- **paths**: Tables=`moso-pricing/src/main/java/com/mosopricing/shared/parser/lender/ElevenMortgageTables.java`, Rate=`moso-pricing/src/main/java/com/mosopricing/server/op/parser/rate/ElevenMortgageExcelParser.java`, Adj=`moso-pricing/src/main/java/com/mosopricing/server/op/parser/adjustment/ElevenMortgageAdjustmentExcelParser.java`
- **tier_history**: [0]
- **tier_0_streak**: 1
- **last_fix**: 2026-04-09
- **last_error**: expectation mismatch — TOPAZ GOV LOAN FEATURES adj values changed
- **notes**: Excel parser (.xlsm). 122 tables. Usually just expectation updates.

## LoanStore
- **paths**: Tables=`moso-pricing/src/main/java/com/mosopricing/shared/parser/lender/LoanStoreTables.java`, Rate=`moso-pricing/src/main/java/com/mosopricing/server/op/parser/rate/LoanStorePdfParser.java`, Adj=`moso-pricing/src/main/java/com/mosopricing/server/op/parser/adjustment/LoanStorePdfAdjustmentParser.java`
- **tier_history**: [0]
- **tier_0_streak**: 1
- **last_fix**: 2026-04-09
- **last_error**: expectation mismatch — Government FICO Adjustments values changed
- **notes**: PDF parser. 51 tables. Has lender doc at docs/lenders/loan-store.md.

## AmWestFundingNonQM
- **paths**: Tables=`moso-pricing/src/main/java/com/mosopricing/shared/parser/lender/AmWestFundingNonQMTables.java`, Rate=`moso-pricing/src/main/java/com/mosopricing/server/op/parser/rate/AmWestFundingNonQMPdfParser.java`, Adj=`moso-pricing/src/main/java/com/mosopricing/server/op/parser/adjustment/AmWestFundingNonQMAdjustmentPdfParser.java`
- **tier_history**: [1]
- **tier_0_streak**: 0
- **last_fix**: 2026-04-09
- **last_error**: Page shift — investorAdvantageAdditionalAdj hardcoded page 10→11
- **last_tier1_fix**: PAGE_SHIFT on investorAdvantageAdditionalAdj → PdfUtils.extractTextInRect page 10→11, new page inserted earlier in document (2026-04-09)
- **notes**: NonQM PDF parser. Has fragile hardcoded page number on line 49 for investorAdvantageAdditionalAdj. Other sections use dynamic PageMap. Watch for page shifts.
