# Pricing Domain Knowledge

## Table Patterns by Loan Type

### Conventional (QM)
- **Always has**: FICO×LTV matrix (per purpose: Purchase, RateTerm, CashOut)
- **Usually has**: State adjustment, Property type adj, Subordinate financing
- **Lock periods**: typically [15, 30, 45, 60]
- **FICO ranges**: 780→620 (standard), some go to 580
- **LTV ranges**: 60→97 (Purchase), 60→90 (CashOut)
- **Modes**: PURCHASE, RATE_TERM, CASH_OUT (minimum)
- **Rate products**: fixed(15,20,25,30) + ARM variants

### NonQM
- **Always has**: FICO×LTV matrix (wider ranges 500-780)
- **Often has**: DSCR adjustment, Bank statement months adj, Prepay penalty adj
- **Lock periods**: typically [30, 45, 60]
- **FICO ranges**: 780→500 (wider than QM)
- **LTV ranges**: varies widely, often up to 80 max
- **Special**: 999.0 sentinel more common, more ValidateCalculator rules
- **Modes**: often just DEFAULT or by program name

### FHA
- **Always has**: FICO×LTV matrix with FHA_STREAMLINE column
- **Specific**: colRange includes FHA_STREAMLINE condition
- **Lock periods**: [15, 30, 45, 60]
- **Modes**: PURCHASE, RATE_TERM, FHA_STREAMLINE

### VA
- **Always has**: FICO×LTV matrix with IRRRL condition
- **Specific**: VA funding fee adjustment, IRRRL streamline
- **Modes**: PURCHASE, RATE_TERM, IRRRL, CASH_OUT

### USDA
- **Similar to**: Conventional but fewer LTV columns
- **Specific**: Rural property restrictions
- **Modes**: PURCHASE, RATE_TERM (usually no CashOut)

### High Balance / Jumbo
- **Always has**: Loan amount ranges in conditions
- **Specific**: loanAmount() ranges for tier breakpoints
- **Higher FICO requirements**: usually 700+ minimum

## Common Adjustment Table Types

### FICO x LTV Matrix
- Most common table type across all loan types
- Rows: FICO ranges (descending, sentinels: MAX_VALUE, MIN_VALUE)
- Cols: LTV ranges (ascending, sentinels: MIN_VALUE) or loan type conditions
- Use ConditionTableInfo with fico().crawlNote() rows
- NEVER use RangeTableInfo for FICO tables

### Condition List
- Single-column adjustments based on conditions
- Examples: State, Property type, Occupancy, Subordinate financing
- Use ConditionTableInfo with condition.setNote() rows

### Loan Amount Tiers
- Used in Jumbo/NonQM for amount-based adjustments
- Use loanAmount(min, max) ranges
- Often combined with FICO or LTV

## Common Mistakes (Learned from QC)

### Frequency: Very Common (>30% of first attempts)
1. **Forgetting allTables()**: Table defined but not added to allTables() -> invisible to calculator
2. **FICO rows not descending**: Copy-paste from ratesheet which is ascending -> must reverse
3. **crawlLabels count mismatch**: Must be rowRange count minus 2 (exclude MAX/MIN sentinels)
4. **field_N reuse**: Must grep existing fields before choosing next number

### Frequency: Common (10-30%)
5. **colRange count mismatch**: Must match actual value columns in ratesheet
6. **Mode not in resolver**: Adding .mode() to rate parser without updating getModeResolver()
7. **Wrong condition gate**: Using CONVENTIONAL when should be NON_JUMBO (includes HighBalance)

### Frequency: Occasional (<10%)
8. **Numeric colRange for FICO table**: Must use fico() ranges, not 0d/85d/95d
9. **Missing ValidateCalculator**: Eligibility rules from matrix not implemented
10. **Sheet name mismatch**: Must match EXACT tab name in ratesheet
