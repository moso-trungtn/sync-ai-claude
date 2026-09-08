# Eligibility checking

## What this answers, and what it does not

`*Tables.validations()` holds the eligibility matrix **printed on the ratesheet**
("Conventional Fixed Rate Mortgages: not subject to ... restrictions"). Running a
scenario through it answers *"does moso block this loan, and on which rule"*.

It does **not** answer *"would the lender approve this loan"*. Reserves, tradelines,
financed-property counts, self-employed doc requirements, lender-specific DTI caps and
state restrictions live in the guideline PDF, which moso does not model. Say which of
the two you checked — see `matrix-doc-format.md` for how a lender's guideline rules and
their modelled/not-modelled status get recorded.

Agency-wide rules (conforming limits, high balance, FHA/VA floors) are lender-independent
and live outside the per-lender Tables.

## The mechanism

`ValidateCalculator.isApplicable(quote)` returns **true when the rule BLOCKS** the loan,
and `failReason()` is the message the LO sees. So the complete set of blocking rules for a
scenario is one loop:

```java
List<String> blocked = new ArrayList<>();
for (ValidateCalculator v : new NexBankTables().validations()) {
  if (v.isApplicable(q)) {
    blocked.add(v.failReason());
  }
}
```

Internally `isApplicable` walks the `when -> validCondition.not()` map in declaration
order and **stops at the first `when` that matches** (`ValidateCalculator.java`). A rule
whose `when` never matches simply does not apply — it is not a pass.

## Running it

Pure local, no prod, no remote call. `DartbankHighBalanceEligibilityTest` is the reference
implementation: 17 cases in 0.075 s.

```bash
cd moso-pricing
mvn test -Dtest=<Lender>EligibilityTools -q
```

Name a throwaway harness `*Tools`, never `*Test`, or CI surefire picks it up. A test you
intend to keep goes in `src/test/java/com/mosopricing/shared/parser/lender/` next to the
Dartbank one, named `<Lender><Topic>EligibilityTest`.

Build the `QuoteServer` with `scripts/resolve-link.py` (section 2 of its output), then
print every blocking rule rather than asserting, so the first run tells you what moso
currently enforces:

```java
QuoteServer q = new QuoteServer();
// ... paste from resolve-link.py ...
for (ValidateCalculator v : new NexBankTables().validations()) {
  System.out.println((v.isApplicable(q) ? "BLOCK  " : "ok     ") + v.failReason());
}
```

## Field mapping

`QuoteServer extends QuoteImpl`; the fields conditions read are plain public fields on
`packs/quote/.../typekey/QuoteImpl.java`.

| Share-link param | QuoteServer field | Notes |
|---|---|---|
| `loan_amount` | `loanAmount` | |
| `loan_amount / property_value` | `ltv`, `cltv` | **FRACTION** (0.523), not 52.3. `RangeCondition.ltv` scales by 100 |
| `credit_score` | `fico` | |
| `category` | `category` | `LoanCategory.SuperConf` prints as "High Balance" |
| `loan_type` | `loanType` | |
| `purpose` | `purpose` | `PurposeType.PM` / `Refinance` |
| `occupancy` | `occupancy` | `Owner` / `Second` / `Investment` |
| `property_type` | `propertyType` | |
| `attachment_type` | `attachmentType` | `Attached` / `Detached` |
| `actual_number_of_units` | `unit` | see the units trap below |
| `debt_to_income` | `debtToIncome` | |
| `number_of_borrowers` | `numberOfBorrowers` | |
| `state` | `state` | |
| `impounds` | `impound` | `NO_ESCROW` fires when false |
| `use_lp` | `isDU` | **inverted**: `isDU = !use_lp` |
| `loan_program_group` | `term`, `fixedTerm`, `arm` | `FIXED_30` -> 30/30. `ARM_7` -> term 30, `fixedTerm` 7, `arm=true` |
| `financed_properties` | `financedProperties` | |
| `total_number_properties` | `totalNumberProperties` | |
| `has_self_employed` | `hasSelfEmployment` | gates Flash Pass style programs |
| `first_time_home_buyer` | `firstTimeHomeBuyer` | |
| `income_to_ami` | `incomeToAMI` | |
| `low_income` | `lowIncome` | |
| `lock_period` | `lockPeriod` | |
| `prepayment_penalty` | `prepaymentPenaltyType` | Non-QM |
| `non_qm_document_type` | `nonQMDocumentType` | Non-QM |
| `non_qm_dscr` | `nonQMDSCR` | Non-QM |
| `non_qm_cash_reserved` | `nonQMCashReserved` | Non-QM |

**The units trap.** For property types that hide the units input, `propertyType` wins over
`actual_number_of_units` (MOSO-17025). A `Duplex` with `actual_number_of_units=1` must
still score as 2 units, or every `UNIT_2_4` rule and LLPA silently drops. When the link
carries a multi-unit `property_type`, set `unit` from the property type.

## Cross-check against live pricing

The Tables loop tells you what the *code* enforces. To confirm the same verdict end to end,
run `RunPricingOp` restricted to that lender (`"alert_lenders":["<LenderType>"]`) and read
the response:

- rows returned -> nothing blocked it
- `"_rows":[]` plus a `note` -> the note is the joined deny reasons
- `ineligible_reason` on a row -> that product was rejected

`RunPricingOp` builds the deny message at `RunPricingOp.java:473-485`. Restricting to one
lender is what makes the reason visible; with many lenders the row is just absent.
