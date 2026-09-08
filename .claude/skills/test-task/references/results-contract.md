# Results contract — what every /test-task run ships (UI mode and pricing mode)

Runs after the last scenario, in both modes. Three artifacts share one scenario order, one numbering (S1..Sn) and one
set of screenshot filenames:

1. `docs/changes/<KEY>/screenshots/S<n>_<slug>.png` — one per scenario.
2. `docs/changes/<KEY>/test_results.md` — header + the per-scenario blocks below + notes.
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

`browser_take_screenshot({ filename: "docs/changes/<KEY>/screenshots/S<n>_<slug>.png", scale: "css" })` —
a relative filename lands under `PROJECT_ROOT`. Read the PNG back once (Read tool): the heading and the total must be
inside the frame; retake if cut off.

**Pricing mode:** the numbers come from the op response, the screenshot from the UI for the same scenario. Load
`/pricing/qm` or `/pricing/non_qm` with the scenario's fields as URL params — enum **names** here
(`purpose=PM&occupancy=Owner&loan_type=FHA&loan_program_group=FIXED_30&…&alert_lenders=<LenderType>`), ordinals
only in the op payload. The page auto-quotes (20–30 s; the first snapshots are stale) and `alert_lenders` limits the
list to that lender. When the expected outcome has no UI surface (lender or program filtered out with no visible
reason), the screenshot is the results list proving the absence and the Evidence line names what is absent.

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

## Jira comment

```
h3. Staging test - <YYYY-MM-DD> (<passed>/<N> PASS)
Environment: staging www.viet18.com, <build: commit or deploy note>, <Lender> ratesheet <MM/DD/YYYY> (<re-parsed hh:mm | same file as prod>). Base scenario: <fields shared by every S<n>>. Setup: <anything toggled on staging and restored | none>.

<S1 block>

<S2 block>
…
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

## Scenarios
<S1 block> … <Sn block>      (screenshot line = `screenshots/S<n>_<slug>.png`)

## Notes
<same Note as the comment, plus anything that only matters to the next tester: toggles, stale data, UI quirks>
```
