# Recording a lender's eligibility matrix

## Where it goes

`moso-pricing/docs/lenders/` — the same files the parser knowledge already lives in:

- a lender with its own file (`pennymac.md`, `provident.md`, ...) gets the section appended
- a lender documented inside a grouped file (`medium-lenders.md`, `simple-lenders.md`) gets
  the section nested under its existing `## <Lender>` heading

Never `moso-docs` — that repo is not pushed for everyone. Do not commit guideline PDFs;
record the link and the version instead.

## Where the guideline comes from

Each lender's documents are on loanfactory.com under Admin -> the lender -> Lender
documents, backed by a Drive folder. On PROD the `Lender` entity caches the links in
`Lender.document_links` (`drive.google.com/open?id=...`) — NexBank has 17, theLender 104,
Mega Capital 51. `LenderDriveFolder` shares each folder `sharePublic(reader)`, so
`https://drive.google.com/uc?export=download&id=<id>` fetches a file with no auth and the
`content-disposition` header carries the real filename.

`scripts/lender-guidelines.py` resolves a lender to its documents, classifies them, and
ranks the ones that govern a loan type. It reads a local registry built from PROD:

```bash
cd moso && mvn test -Dtest=LenderDocumentRegistryTools#dumpRegistry -q -Dgwt.compiler.skip=true
```

That harness (`moso/src/test/java/com/ignored/lenderrate/`) is read-only and writes
`~/.cache/moso/lender-documents.json`: 454 lenders on PROD, **240 with documents, 3681
documents**, 82 of them mapped to a `LenderType`. The file sits outside any git repo on
purpose, since the ids are direct-download links to confidential guidelines.

**There is deliberately no guideline change-watcher.** The vendor team reports when a lender
revises a guideline, so the registry is rebuilt on demand at that point rather than polled.
Do not build a `ratesheet-watch` equivalent for guidelines; ratesheets change daily and
guidelines change a few times a year with a human already in the loop.

**Loan type is not always the key.** Agency and category labels resolve fine (`Freddie Mac`
and `Conforming+High Balance` are conventional; `High Balance` is a loan-size modifier, so
`FHA Streamline+High Balance` stays an FHA document). But lenders file Non-QM and portfolio
products under their own program names — HomeBridge has `Access`, `Elite Access`,
`Investor Solution` — and those map to no `LoanType`. The tool surfaces them as `?token`
instead of guessing.

**One lender has many guidelines.** Filenames follow
`<scope>_<Guidelines|Matrices|Guidelines and Matrices|Niches>_<MMDDYYYY>.pdf`, where scope
names the product family and `+` joins several (`FHA+FHA Streamline`,
`QM+Jumbo+Conventional`, `Conventional ALL`). Conventional, FHA, VA, Jumbo and Non-QM are
separate documents with separate revision dates. A finding from one document applies only
to the loan types that document names.

Four things that will bite:

1. **The filename date is the upload date, not the revision date.** NexBank's conventional
   file is named `..._04012026` and the document says 04.14.2026; the FHA file is named
   `..._12012025` and the document says 12/19/2025. Open the PDF and read its header.
2. **Stale revisions stay in the folder** next to current ones, and the same document can
   appear under two Drive ids. Rank by date, and prefer a newer broad document over an older
   narrow one.
3. **A filename is not a unique key.** HomeBridge has two files both named
   `USDA and Non Streamlined_Guidelines_11132025.pdf` at 153 KB and 618 KB.
4. **"Has a guideline" is not "has a current guideline."** Provident's are dated 03/09/2022.

The PDFs are lender-confidential. Keep them in a scratch directory, never commit them, and
never send them to an external service.

**Write findings into the lender doc as you read, not at the end.** The scratch directory is
volatile: a 122-lender / 2082-file inventory and a set of downloaded guidelines were wiped
mid-session on 09/04/2026. Re-fetching one PDF costs seconds, but a broad inventory costs
over an hour, so anything worth keeping belongs in `moso-pricing/docs/lenders/` the moment
you have it.

## The section

Fixed headings so the section can be grepped across lenders. The document inventory comes
first, because which document a rule came from is part of the rule.

```markdown
## Eligibility (guideline)

| Loan type | Guideline document (filename date) | Doc's own date | Read? |
|---|---|---|---|
| Conventional / Conforming | `Conventional ALL_Guidelines and Matrices` (04012026) | 04.14.2026 | yes, 09/04/2026, 72 pp |
| FHA + FHA Streamline | `FHA+FHA Streamline_Guidelines and Matrices` (12012025) | 12/19/2025 | no |
| VA | `VA ALL_Matrices` (12012025) | — | no |

Sheet matrix: modelled, <N> ValidateCalculators in `<Lender>Tables.validations`, parsed
from the matrix printed on the ratesheet. Verified <date> against `<RatesheetFiles const>`.

### <Program> — <Purpose> — <Occupancy>

| Units | Max LTV | Max CLTV | Min FICO | Notes |
|-------|---------|----------|----------|-------|
| 1     | 85      | 85       | 620      |       |
| 2-4   | 75      | 75       | 620      |       |

#### Rules NOT on the ratesheet — <Loan type>

From `<document>` dated <doc date>, read <date>, against a grep of the validations block.

**Real overlays moso does not enforce:**

| Guideline rule | Status |
|---|---|
| Max 10 financed properties on second home or investment | **NOT MODELLED** |

<cheapest scenario that reproduces the gap>

**Correctly absent — the guideline sets no lender overlay:**

| Guideline rule | Why not modelled |
|---|---|
| Cash reserves | Deferred to the AUS: "<quote>" (p.<n>). No fixed number to model. |

**Not checked yet:** <loan types whose guideline document has not been read>
```

## Rules for filling it in

**Only write what you verified.** A row copied from the ratesheet cites the ratesheet; a
row from the guideline cites the guideline version. If a value was not checked, leave the
cell empty rather than plausible — a wrong matrix is worse than a missing one, because the
next check trusts it.

**Split real gaps from correct absences.** These documents are laid out as
`Topic | Fannie Mae (DU) | Freddie Mac (LPA)` tables, so most credit rules defer to the AUS
and have no number to model. "Reserves not modelled" is the right behaviour when the
guideline says "as addressed on the AUS findings"; recording it as a gap manufactures
phantom backlog. A real overlay is a rule with the lender's own number in it, and it earns a
ticket plus the cheapest scenario that reproduces it. Quote `failReason()` text exactly for
rules that ARE modelled, because that is the string an eligibility loop prints and the LO
sees.

**Scope every finding to the document it came from.** A conclusion drawn from the
Conventional guideline says nothing about FHA, VA, Jumbo or Non-QM. End the section with an
explicit list of the loan types whose guideline has not been read.

**Keep the sheet matrix and the guideline matrix apart.** The sheet matrix is already
modelled in `validations()`, so it is documentation. The guideline matrix is the part moso
cannot see, so it is the new information.

**Date every claim.** Guidelines are revised a few times a year with no notice. A row
without `Effective`/`Retrieved` cannot be trusted later. When a guideline is re-read and a
value changed, replace the row and note the change with its ticket, matching how
`medium-lenders.md` already records dated changes.
