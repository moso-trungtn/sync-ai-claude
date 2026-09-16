# Results contract — what every /test-task run ships (UI mode and pricing mode)

Runs after the last scenario, in both modes. Three artifacts share one scenario order, one numbering (S1..Sn) and one
set of screenshot filenames:

1. `$CHANGES_DIR/<KEY>/screenshots/S<n>_<slug>.png` — one per scenario.
2. `$CHANGES_DIR/<KEY>/test_results.md` — header + the per-scenario blocks below + notes.
3. One Jira comment on `<KEY>` built from the same blocks; every block ends with its screenshot embedded.
   Status stays In Progress.

## Screenshot per scenario

The screenshot shows the surface that carries the verdict, with the numbers legible:

- **Pricing tickets:** the lender row's *Pricing adjustment* popup — Base Price / Total Adj / Adjusted Price and the
  adjustment table. Open it by clicking the lender name in the rate row (the `N` button next to it expands the DU /
  LP / other program rows; click the program's own row). Scroll the table into view first
  (`browser_evaluate` → `scrollIntoView` on the target cell), then `browser_take_screenshot`. "View fees" is the
  closing-cost popup and the Payment cell opens the payment page — neither shows adjustments.
- **Eligibility tickets:** the results list showing the program present / absent, or the ineligible reason the UI
  shows.
- **Form / workflow tickets:** the message, banner, field state or table row the scenario asserts.

`browser_take_screenshot({ filename: "$CHANGES_DIR/<KEY>/screenshots/S<n>_<slug>.png", scale: "css" })` —
a relative filename lands under `PROJECT_ROOT`. Read the PNG back once (Read tool): the heading and the total must be
inside the frame; retake if cut off.

**Pricing mode:** the numbers come from the op response, the screenshot from the UI for the same scenario. Load
`/pricing/qm` or `/pricing/non_qm` with the scenario's fields as URL params — enum **names** here
(`purpose=PM&occupancy=Owner&loan_type=FHA&loan_program_group=FIXED_30&…&alert_lenders=<LenderType>`), ordinals
only in the op payload. The page auto-quotes (20–30 s; the first snapshots are stale) and `alert_lenders` limits the
list to that lender. When the expected outcome has no UI surface (lender or program filtered out with no visible
reason), the screenshot is the results list proving the absence and the Evidence line names what is absent.

## Verdict table — FIRST thing in both the file and the comment

Before any adjustment lines, one row per scenario. A reader must be able to answer "did it pass?" without
reading a single number. This table is not optional and never collapsed into prose.

Jira (wiki markup — `(/)` renders a green check, `(x)` a red cross):

```
|| # || What it proves || Expected || Actual || Verdict ||
| S1 | DTI 49% + Full Doc releases the >45% exception | Select + Core eligible | both eligible, price 2.362 / 2.862 | (/) PASS |
| S2 | Bank Stmt does NOT satisfy the exception | 0 eligible, DTI message | 0 eligible, DTI message on both Alt Doc | (/) PASS |
| S3 | tier floors 1.25 / 1.20 / 1.00 all clear at 1.25 | 4 products eligible | 4 eligible | (/) PASS |
| S4 | at 0.70 every floor >= 0.75 blocks, each naming its own | Fusion + No Ratio only | Fusion + No Ratio only | (/) PASS |
```

`test_results.md` (markdown, same columns, ✅ / ❌ instead of `(/)` / `(x)`).

Rules:
- **Verdict is PASS or FAIL. Never blank, never "see below", never a number on its own.** SKIP needs a
  reason in the Actual column.
- **What it proves** is the rule under test in the user's words — not the product name, not the ticket
  title. "DTI 49% + Full Doc releases the >45% exception", not "Full Doc scenario".
- **Expected** and **Actual** each fit on one line. If Actual equals Expected, say so concretely
  ("both eligible, price 2.362 / 2.862") rather than writing "as expected" — the concrete value is what
  makes the row checkable.
- A FAIL row states the gap in Actual ("Core priced 2.987, lender says 2.862 — 0.125 high"), and the
  scenario block below carries the detail.
- The matrix check gets its own row: `| Matrix | grid vs FL-NQM-Matrix.pdf 08.05.26 | all cells match | match | (/) PASS |`.

## Coverage table — second, right under the verdict table (pricing mode)

The verdict table says whether what was tested passed. This one says whether enough was tested. Both ship,
always, in the file and in the Jira comment. Counts come from the step 2b inventory.

```
|| Axis || Total || Covered || Not reachable || Not tested ||
| Adjustment tables | 29 | 29 | 0 | 0 |
| Price caps | 3 | 3 | 0 | 0 |
| Validation groups | 9 | 8 | 1 (Professional overlay - no quote field) | 0 |
| Rate ladder | - | base_price checked at 5.99% and 6.75% vs the 09/15 sheet | - | - |
| Matrix | - | FL-NQM + FL-DSCR + FL-5-8-Unit, all cells | - | - |
| Guideline | - | validations() vs docs/lenders/forward-lending/nonqm.md "## Eligibility (guideline)" | - | - |
```

Then, whenever *Not tested* is anything but 0, list those rows by name immediately under the table. A
non-zero *Not tested* that is not itemised is the same failure as not reporting it at all.

Rules:
- **Never report only the covered count.** "16 tables fired" without "of 29" reads as complete and is the
  exact shape of the 2026-09-15 Forward Lending miss.
- **Not reachable needs the missing field named**, not just the label — "Professional overlay: no quote
  attribute for borrower profession", not "not supported".
- Caps count as covered only when the cap actually **bound** in some scenario (`sum(lines) != adjusted_price`).
  A cap scenario that ran without binding is *Not tested*, not *Covered*.

## Per-scenario block

Same lines in `test_results.md` and in the Jira comment (Jira: wiki markup, `*bold*`; .md: `**bold**`):

```
*S<n> - <the scenario, or "S1 with <the one input changed>"> - PASS*
Expected: <what the ticket / lender says, with the number>
{noformat}<Program> @ <rate>   base <±x.xxx>
  <adjustment table>        ±x.xxx   <row note / band, verbatim>
  …
TOTAL ADJ ±x.xxx   (<final price, or what moved vs S1>; lender: <x.xxx when known>)
eligible   : <programs>                       ← only when eligibility is part of the ticket
ineligible : <program> -> <exact reason>{noformat}
!S<n>_<slug>.png|thumbnail!
```

A form / workflow scenario puts the observed text (message, field values, row) inside the `{noformat}` block instead
of pricing lines. A FAIL block keeps the shape: `- FAIL` in the title and `Expected: … / Actual: …` lines.

## Matrix check block

Pricing mode always carries one, right after the last scenario (see `pricing-mode.md` step 7). It is a
verdict on the transcription, not on the deploy, so it stays even when every scenario passed:

```
*Matrix check - <matrix file(s) and their dates> - MATCHES | <n> MISMATCH(ES)*
{noformat}<grid>                       <rows x bands x purposes>   match | <the differing cell, matrix vs code>
overlays: <each footnote rule checked>  match | <what differs>
not enforced (no field to carry it): <rule> ; <rule>{noformat}
```

A mismatch here is a finding in its own right - the prices can be perfect while the grid denies the
wrong loans. Say which source was used: the lender doc's `## Eligibility (guideline)` section, or the
matrix PDF when that section did not exist yet.

## Jira comment

```
h3. Staging test - <YYYY-MM-DD> (<passed>/<N> PASS)
Environment: staging www.viet18.com (signed in), <build: commit or deploy note>, <Lender> ratesheet <MM/DD/YYYY> (<re-parsed hh:mm | same file as prod>). Base scenario: <fields shared by every S<n>>. Setup: <anything toggled on staging and restored | none>.

<the verdict table>

<the coverage table>

<S1 block>

<S2 block>
…

<matrix check block>

Note: <defaults assumed; one-reason-per-program caveat; what staging cannot show and the unit test that pins it>.
```

Order of operations:

1. **Attach first.** Every screenshot:
   `curl -u "$JIRA_EMAIL:$JIRA_API_TOKEN" -H "X-Atlassian-Token: no-check" -F "file=@<png>" https://mosoteam.atlassian.net/rest/api/2/issue/<KEY>/attachments`.
   An `!file|thumbnail!` whose file is not attached renders as plain text.
2. **Post.** `POST /rest/api/2/issue/<KEY>/comment` with `{"body": "<wiki markup>"}`. If this run already has a
   results comment, `PUT /rest/api/2/issue/<KEY>/comment/<id>` replaces it — one results comment per run.
3. **Verify the render.** `GET /rest/api/2/issue/<KEY>/comment/<id>?expand=renderedBody`: the `<img` count equals
   the number of scenarios and no `!…|thumbnail!` text is left. Fix and PUT again before reporting to the user.

Do not transition the issue.

## test_results.md

```
# Test Results for <KEY>
- Date / Environment / Build / Ratesheet / Base scenario / Setup   (same header as the comment)

## Summary
<passed>/<N> PASS, <failed> FAIL, <skipped> SKIP

<the verdict table — one row per scenario plus the matrix row>

## Coverage
<the coverage table; itemise every Not tested row>

## Scenarios
<S1 block> … <Sn block>      (screenshot line = `screenshots/S<n>_<slug>.png`)

## Matrix check
<the same block; pricing mode only>

## Notes
<same Note as the comment, plus anything that only matters to the next tester: toggles, stale data, UI quirks>
```
