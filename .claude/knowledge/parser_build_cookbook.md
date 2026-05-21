# Parser Build Cookbook

<!-- Per-lender build history — grows after every successful build -->

## PlazaHome (QM)
- **type**: QM — Conventional, FHA, VA, USDA, Jumbo
- **paths**: Tables=`moso-pricing/.../lender/PlazaHomeTables.java`, Rate=`moso-pricing/.../rate/PlazaHomeExcelRateParser.java`, Adj=`moso-pricing/.../adjustment/PlazaHomeAdjustmentExcelParser.java`
- **rate_products**: FHA(30,25,20,15), FHA_Streamline(30,25,20), VA(30,25,20,15), VA_IRRRL(30,25,20,15), USDA(30), CF(30,20,15,10), CF_HB(30), CF_HR(30), CF_HP(30), ARM(7/6), Jumbo variants
- **lock_periods**: [15, 30, 45, 60]
- **adj_sections**: split by "GOVERNMENT ADJUSTMENTS", "Conventional Adjustments", "Jumbo AUS 1", "Solutions Adjustments", etc.
- **modes**: FHA, FHA_STREAMLINE, VA, VA_JUMBO, VA_IRRRL, VA_IRRRL_JUMBO, HOME_READY, HOME_POSSIBLE, USDA, LP, JUMBO (AUS1/AUS2/AUS3/ELITE)
- **qc_issues**: ["Agency Express (CF AX) removed in April 2026 ratesheet update"]
- **build_date**: 2026-04-10
- **build_stats**: update — 3 beads, 0 retries

## PlazaHomeNonQM
- **type**: NonQM — DSCR Investor Solutions 1 & 2, Solutions, Solutions 3
- **paths**: Tables=`moso-pricing/.../lender/PlazaHomeNonQMTables.java`, Rate=`moso-pricing/.../rate/PlazaHomeNonQMPdfParser.java`, Adj=`moso-pricing/.../adjustment/PlazaHomeNonQMAdjustmentPdfParser.java`
- **rate_products**: DSCRInvestorSolutions1(30, 40IO), DSCRInvestorSolutions2(30, 40IO), Solutions3(30, 40IO), Solutions(15, 30, 5/6ARM, 7/6ARM, 40IO, 5/6ARM_IO, 7/6ARM_IO)
- **adj_sections**: "DSCR Investor Solutions", "DSCR Investor Solutions 2", "Solutions Adjustments", "Solutions 3"
- **special**: Spotlight Special +0.50 via ConstantCalculator(ALL, 0.50) added April 2026
- **modes**: INTEREST_ONLY_MODE (for 40yr/ARM IO products), default
- **qc_issues**: ["Solutions field_189 changed 999.0→2.0 in April 2026 update"]
- **build_date**: 2026-04-10
- **build_stats**: update — 1 bead, 0 retries