# Pricing mode — prove a pricing / lender fix on the deployed staging build

Applies when the ticket is about what the pricing engine returns: rate, price, LLPA / SRP / cap not matching the
lender, a program shown that the lender rejects (or hidden that it accepts), a parser change. The numbers come from
the pricer's own op; each scenario is then rendered once in the pricing UI for its screenshot. The deliverable is the
results contract (`references/results-contract.md`): per-scenario blocks with the lines and the screenshot. There is
no form click-through and nobody is asked to log in.

**What this proves:** the build running on staging prices the reported scenario the way the lender's engine does,
and every rule that was added or changed releases on its own control. The local harness (check-lender-rate,
`RunPricingOp`, `*EligibilityTest`) runs local code and cannot prove a deploy.

## Steps

0. **Deploy check.** `git -C moso-pricing branch -r --contains <fix commit>` must list `origin/master`. Staging
   engine = `moso-pricing-dot-lenderrate-master`. The sheet staging prices from is
   `https://storage.googleapis.com/lenderrate-master-ratesheet/<LenderType>.<ext>`: record `last-modified` and
   the sheet's own date, `shasum` it against the prod object `lender-rate-ratesheet/<LenderType>.<ext>`, and put
   the date in the comment header. Staging does not parse daily: Moso Lenders → lender row → *Rate* → "Current
   rates" shows the Created time of the rates; → *Adjustments* shows the parsed tables (the heading carries the
   gate note, e.g. "(Conforming/HB NOT Jumbo)").
1. **Session.** `browser_navigate https://www.viet18.com/login`, log in with the staging test account
   (memory `reference_staging_viet18_login`), open `/pricing/non_qm` (or `/pricing/qm`), click *Get Quote* once.
   If the lender is missing from the result list, check `/available_lenders` → lender row → "QM Quotable" /
   "Non-QM Quotable" for the company (`RunPricingOp` filters on `LenderAgreement.qm_active`); toggle on for the
   test, back off afterwards, and record it under Setup.
2. **Capture the real call.** `browser_network_requests` filtered on `exec/`: Non-QM fires
   `POST /exec/GetNonQMRatesOp`; QM fires its own `exec/Get*RatesOp` — take the name from the capture. With
   `browser_network_request` copy the request headers `x-property` (carries `X-Use-Enum-Ordinal=1`), `xsrf`,
   `user`, `x-sdk-namespace`, and the request body as the payload template. The body is in enum **ordinals**.
3. **Scenarios.** S1 = the reported scenario, every field as the ticket states it; the numbers to hit are the
   lender engine / portal numbers quoted in the ticket. Then one control per rule that changed: flip exactly one
   input so the rule releases (blocked -> eligible) or the adjustment line changes, everything else identical.
   Fetch `POST /exec/GetCountyLimits {"id":"<zip>"}` and pass it as `countyLimit`, with
   `super_conf_limit = countyLimit.Limit1` and `ami = countyLimit.ami`.
4. **Run.** One `browser_evaluate` async function: `fetch('/exec/<Op>', {method:'POST', credentials:'include',
   headers, body: JSON.stringify(payload)})` per scenario, responses stashed on `window`, and return a summary:
   `_rows` filtered on the lender ordinal (`quote_lender`), grouped by `non_qm_product` / `program` with count and
   rate range; the row at the ticket's rate with `base_price`, `adjustment` (total points), `adjusted_price`;
   `ineligible_products[].ineligible_products[]` as `product -> reason` (skip `out_of_scope`); the row's
   `adjustment_detail` (JSON string, `_rows[].adjustment_name / adjustment_value / is_group`).
5. **Check every line.** The band in the note contains the scenario's own FICO / LTV; the lines sum to
   `adjustment`; the eligible / ineligible split matches the lender; each control flips exactly the expected line
   or program and nothing else.
6. **Screenshot each scenario in the UI.** Load `/pricing/qm` or `/pricing/non_qm` with the scenario's fields as
   URL params in enum **names** plus `alert_lenders=<LenderType>` (the page auto-quotes; wait 20–30 s), click the
   lender name in the row at the ticket's rate (the `N` button expands DU / LP / other programs), scroll the
   *Pricing adjustment* table into view and save `docs/changes/<KEY>/screenshots/S<n>_<slug>.png`. For an
   ineligible-program scenario the screenshot is the results list proving the program is absent. Details in
   `references/results-contract.md`.
7. **Record.** `docs/changes/<KEY>/test_cases.md` and `test_results.md` (per-scenario blocks per the results
   contract), copied into `moso-pricing/docs/changes/<KEY>/` and committed as
   `MOSO-XXXXX: staging test cases and results for <topic>` (one commit, no push).
8. **Jira.** Attach the screenshots, post the results-contract comment (or `PUT` over this run's earlier results
   comment), verify the render shows one image per scenario. Status stays In Progress.

## The scenario block in this mode

The `{noformat}` part of each block is the matrix line-set — every slot filled, nothing else added:

```
*S1 - <purpose, occupancy, doc type, loan / PV (LTV %), FICO, property, citizenship, state zip, DSCR, PPP, reserves, lock> - PASS*
Expected: <lender engine / portal number quoted in the ticket>
{noformat}<Program> @ <rate>   base <±x.xxx>
  <table>                   ±x.xxx   <row note and band, verbatim from adjustment_detail>
TOTAL ADJ ±x.xxx -> final price x.xxx   (lender engine: x.xxx / x.xxx)
eligible   : <programs>
ineligible : <program>  -> <exact reason text>{noformat}
!S1_<slug>.png|thumbnail!

*S2 - S1 with <the one input changed> - PASS*
Expected: <program released | line moves to …>
{noformat}<Program> @ <rate>   base <±x.xxx>
  <lines>
TOTAL ADJ ±x.xxx   (<what moved vs S1>)
eligible   : + <program released>
ineligible : <still blocked, same reasons>{noformat}
!S2_<slug>.png|thumbnail!
```

A FAIL block keeps the shape with `- FAIL` in the title and `Expected: … / Actual: …`; the header count says N-1/N.

## Enum ordinals for the payload

| Field | Ordinals (from `packs/quote/.../typekey`) |
|---|---|
| `purpose` PurposeType | Refinance 0, **CashOut 1, PM 2**, PA 3, PQ 4 |
| `occupancy` | Owner 0, Second 1, Investment 2 |
| `non_qm_document_type` | full_doc_1_year 0, full_doc_2_years 1, bank_statements_12 2, bank_statements_24 3, cpa_p_l_12 4, cpa_p_l_24 5, **property_cash_flow_or_dscr 6**, asset_utilization 7, 1099_12 8, 1099_24 9, voe_12 10, voe_24 11 |
| `prepayment_penalty` | no_prepayment 0, 12 mo 1, 24 mo 2, 36 mo 3, 48 mo 4, 60 mo 5 |
| `citizenship` | us_citizen 0, Permanent_Resident_Alien 1, Nonresident_Alien 2, Foreign_National 3 |
| `property_type` | Single 0, Condo 1, Townhouse 2, CoOps 3, Duplex 4, Manufactured 5, Triplex 6, Fourplex 7, Multifamily 8, Commercial 9, MixedUse 10, Farm 11, HomeAndBusiness 12, Land 13, Non_Warrantable_Condo 14, Greater_Than_5_Units 15, Condotel 16 |
| `loan_program_group` | FEATURE 0, FIXED_40 1, **FIXED_30 2**, FIXED_25 3, FIXED_20 4, FIXED_15 5, FIXED_10 6, ARM_10 7, ARM_7 8, ARM_5 9 |
| `mortgage_lates` | No_mortgage_late 0, 1x30x12 1, 0x60x12 2, 1x60x12 3 |
| `credit_event` | None 0, Settled 1 |
| `loan_to_close_name` | Individual 0, LLC 1, Corporation 2 |
| `employment_history` (int) | 0 no employment history, 1 self-employed |
| `credit_score` | top of the dropdown band (760-779 -> 779) |
| `non_qm_dscr` | 0.74 for "< 0.75", then 0.75 / 1.0 / 1.25 |

Plain (non-enum) fields, names as the UI sends them: `loan_amount`, `property_value`, `zip`, `state`,
`credit_score`, `lock_period` (30), `impounds` (bool), `interest_only`, `first_time_investor`, `non_qm_cash_reserved`
(months), `non_qm_dscr`, `actual_number_of_units`, `total_number_properties`, `financed_properties`,
`has_self_employed`, `compensation_type` 1 + `borrower_paid_compensation` 1 (borrower paid), `get_all_rates` true,
`is_new` true, `kind` "Rate", `alert_lenders` null. LTV is derived server-side from `loan_amount / property_value`.

The URL query for the screenshot step uses the same field names with enum **names** and Yes/No booleans
(`purpose=PM&occupancy=Investment&loan_type=Conventional&impounds=Yes&loan_program_group=FIXED_30&
income_to_ami=INCOME_GT_140_AMI&alert_lenders=JetAdvantage`), as the pricer writes them into the address bar after
*Get Quote*.

Inputs the ticket does not state take the pricer's own defaults as seen in the captured payload (FIXED_30, 30-day
lock, impounds on, 1 unit, US citizen, no PPP change) and are listed in the comment's Note as assumptions.

Lender ordinal: `quote_lender` printed next to `quote_lender_name` in `ineligible_products`, or the position in
`LenderType`. When an ordinal is not in this table, read it from the enum source — never guess. The first EMET
run used `purpose: 1` and priced a cash-out (a phantom "Cash Out 0.5" line) until it was re-derived.

## Reading the response

- `adjusted_cost` / `total_cost` are dollars; `adjustment` is total points; `adjusted_price = base_price + adjustment`.
- The ineligible list carries **one reason per program** — the first validator whose `when` matches. Stacked rules
  are proven by the eligibility unit test; say so in the Note instead of calling them missing.
- `alert_lenders` is null in the UI payload; filter rows by lender ordinal instead of trusting it to restrict.
- Staging does not always carry today's sheet. If its date lags prod, say which values could differ.
- The response lines are the numeric evidence; the UI screenshot of the same scenario (step 6) is the visual one.
  Both go into the scenario block — never one without the other.
