#!/usr/bin/env python3
"""List and fetch a lender's guideline documents, picking by loan type.

A lender publishes ONE GUIDELINE PER PRODUCT FAMILY, each with its own revision
date. Reading the Conventional guideline tells you nothing about FHA, VA, Jumbo or
Non-QM. This tool makes that explicit: it classifies every document in the lender's
Drive folder by the loan types its name claims, then ranks candidates for the loan
type you ask about.

Where the links come from: PROD caches them on the Lender entity in
`Lender.document_links` (see references/matrix-doc-format.md). The folder is
world-readable, so no auth is needed and the real filename arrives in the
`content-disposition` header.

Usage:
  # find a lender in the registry
  python3 lender-guidelines.py --find-lender nexbank

  # classify everything in that lender's folder
  python3 lender-guidelines.py --lender NexBank

  # which document governs this loan type?
  python3 lender-guidelines.py --lender NexBank --loan-type Conventional

  # fetch the top candidate and print its own stated date
  python3 lender-guidelines.py --lender NexBank --loan-type FHA --download out/

  # or pass Drive ids directly, no registry needed
  python3 lender-guidelines.py --ids-file nexbank_ids.txt
  python3 lender-guidelines.py --ids 1DcJrkO6NuNW... 1zcV1V6gkwK2...

The registry maps every lender to its Drive file ids. Rebuild it when a lender's
documents change:

  cd moso && mvn test -Dtest=LenderDocumentRegistryTools#dumpRegistry \\
      -q -Dgwt.compiler.skip=true

It lives outside any git repo on purpose. The ids point at confidential lender
guidelines, so the file is a cache, not a source. The ids file may hold bare ids or
full drive.google.com links, one per line.
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

DEFAULT_REGISTRY = Path.home() / ".cache" / "moso" / "lender-documents.json"

DOC_TYPES = ["Guidelines and Matrices", "Guidelines", "Matrices", "Niches"]

NAME_RE = re.compile(
    r"^(?P<scope>.+?)_(?P<doctype>" + "|".join(DOC_TYPES) + r")_(?P<date>\d{8})\.pdf$",
    re.IGNORECASE,
)

# Scope token -> LoanType names. Order matters: the first pattern that matches a
# token wins, so "Non QM" must be tried before "QM" and "FHA Streamline" before "FHA".
SCOPE_MAP = [
    (r"non[\s-]*qm",            ["Non_QM"]),
    (r"fha[\s-]*streamline",    ["FHA_Streamline"]),
    (r"fha[\s-]*203",           ["FHA_203"]),
    (r"\bfha\b",                ["FHA"]),
    (r"va[\s-]*irrrl",          ["VA_IRRRL"]),
    (r"\bva\b",                 ["VA"]),
    (r"\busda\b",               ["USDA"]),
    (r"home[\s-]*possible",     ["HomePossible"]),
    (r"home[\s-]*ready",        ["Conventional_HomeReady"]),
    (r"home[\s-]*one",          ["HomeOne"]),
    (r"\bheloc\b",              ["HELOC"]),
    (r"\bheloan\b",             ["HELOAN"]),
    (r"piggyback|2nd|second",   ["Second_Mortgage"]),
    (r"\bjumbo\b",              ["Jumbo"]),
    # Agency and category names are conventional business under another label. Kept after
    # the program entries above so "Freddie Mac Home Possible" resolves to HomePossible.
    (r"conventional|conforming", ["Conventional"]),
    (r"freddie[\s-]*mac|fannie[\s-]*mae", ["Conventional"]),
    (r"refi[\s-]*now|refi[\s-]*possible", ["Conventional"]),
    (r"\bqm\b",                 ["QM_Loan"]),
]

# Loan-size categories, not products. "FHA Streamline+High Balance" is an FHA document,
# so a modifier only contributes a loan type when nothing else in the scope resolved.
MODIFIER_MAP = [
    (r"high[\s-]*balance|super[\s-]*conf", ["Conventional"]),
]

WILDCARD = "*"


def load_registry(path: Path) -> list:
    if not path.exists():
        sys.exit(
            f"no registry at {path}\n"
            "Build it with:\n"
            "  cd moso && mvn test -Dtest=LenderDocumentRegistryTools#dumpRegistry "
            "-q -Dgwt.compiler.skip=true"
        )
    return json.loads(path.read_text())["lenders"]


def match_lender(rows: list, needle: str) -> list:
    """Exact LenderType first, then a case-insensitive substring on either field."""
    exact = [r for r in rows if (r.get("lender_type") or "").lower() == needle.lower()]
    if exact:
        return exact
    n = needle.lower()
    return [r for r in rows
            if n in (r.get("name") or "").lower() or n in (r.get("lender_type") or "").lower()]


def read_ids(args) -> list:
    raw = list(args.ids or [])
    if args.ids_file:
        raw += Path(args.ids_file).read_text().split()
    if args.lender:
        rows = match_lender(load_registry(Path(args.registry)), args.lender)
        if not rows:
            sys.exit(f"no lender matching {args.lender!r} in the registry "
                     f"(try --find-lender {args.lender})")
        if len(rows) > 1:
            print(f"{args.lender!r} matches {len(rows)} lenders:", file=sys.stderr)
            for r in rows:
                print(f"   {r['lender_type'] or '-':28} {r['name']}  "
                      f"({len(r['file_ids'])} files)", file=sys.stderr)
            sys.exit("be more specific, or use the LenderType name")
        row = rows[0]
        print(f"# {row['name']}  LenderType={row['lender_type']}  id={row['id']}")
        raw += row["file_ids"]
    out = []
    for item in raw:
        m = re.search(r"[?&/]id=([A-Za-z0-9_-]+)", item) or re.fullmatch(r"[A-Za-z0-9_-]{20,}", item)
        if m:
            out.append(m.group(1) if m.lastindex else m.group(0))
    if not out:
        sys.exit("no ids given (use --lender, --ids or --ids-file)")
    return out


def head(fid: str) -> tuple:
    """Return (filename, size) for a public Drive file, or (None, None)."""
    out = subprocess.run(
        ["curl", "-sIL", "-m", "40", f"https://drive.google.com/uc?export=download&id={fid}"],
        capture_output=True, text=True, check=False,
    ).stdout
    name = re.search(r'(?i)^content-disposition:.*filename="([^"]+)"', out, re.M)
    size = re.findall(r"(?i)^content-length:\s*(\d+)", out, re.M)
    return (name.group(1) if name else None, int(size[-1]) if size else None)


def classify(filename: str) -> dict:
    """Split a filename into scope / doc type / upload date and the loan types it claims."""
    info = {"name": filename, "scope": None, "doctype": None, "upload_date": None,
            "loan_types": [], "structured": False}
    m = NAME_RE.match(filename)
    if not m:
        return info
    info["structured"] = True
    info["scope"] = m.group("scope")
    info["doctype"] = m.group("doctype")
    d = m.group("date")
    info["upload_date"] = f"{d[0:2]}/{d[2:4]}/{d[4:8]}"
    info["_sort_date"] = d[4:8] + d[0:2] + d[2:4]

    types = []
    deferred = []       # modifier-only tokens, folded in later if nothing else resolved
    for token in re.split(r"\+", info["scope"]):
        token = token.strip()
        if re.fullmatch(r"(?i)all", token):
            types.append(WILDCARD)
            continue
        modifier = next((m for p, m in MODIFIER_MAP if re.search(p, token, re.IGNORECASE)), None)
        if modifier and not any(re.search(p, token, re.IGNORECASE) for p, _ in SCOPE_MAP):
            deferred.extend(modifier)
            continue
        matched = False
        for pattern, mapped in SCOPE_MAP:
            if re.search(pattern, token, re.IGNORECASE):
                types.extend(mapped)
                matched = True
                break
        if not matched and token:
            # "Conventional ALL" style: a trailing ALL widens a named token
            if re.search(r"(?i)\ball\b", token):
                base = re.sub(r"(?i)\ball\b", "", token).strip()
                for pattern, mapped in SCOPE_MAP:
                    if base and re.search(pattern, base, re.IGNORECASE):
                        types.extend(mapped)
                        matched = True
                        break
            if not matched:
                types.append(f"?{token}")
    if not any(t == WILDCARD or not t.startswith("?") for t in types):
        types.extend(deferred)
    # dedupe, keep order
    seen = set()
    info["loan_types"] = [t for t in types if not (t in seen or seen.add(t))]
    return info


def covers(info: dict, loan_type: str) -> bool:
    lt = loan_type.lower()
    for t in info["loan_types"]:
        if t == WILDCARD:
            return True
        if t.lower() == lt:
            return True
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lender", help="LenderType name or part of the lender's name")
    ap.add_argument("--find-lender", help="search the registry and exit")
    ap.add_argument("--registry", default=str(DEFAULT_REGISTRY), help="registry JSON path")
    ap.add_argument("--ids", nargs="*", help="Drive file ids or links")
    ap.add_argument("--ids-file", help="file with one id/link per line")
    ap.add_argument("--loan-type", help="LoanType name, e.g. Conventional, FHA, VA, Non_QM, Jumbo")
    ap.add_argument("--download", metavar="DIR", help="download the ranked candidates into DIR")
    ap.add_argument("--top", type=int, default=3, help="how many candidates to download (default 3)")
    args = ap.parse_args()

    if args.find_lender:
        rows = match_lender(load_registry(Path(args.registry)), args.find_lender)
        if not rows:
            print(f"no lender matching {args.find_lender!r}")
            return
        print(f"{len(rows)} match(es):")
        for r in sorted(rows, key=lambda x: -len(x["file_ids"])):
            rate = "prices" if r["has_rate"] else "no rates"
            print(f"  {len(r['file_ids']):4} files  {r['lender_type'] or '-':28} "
                  f"{r['name']}  ({rate})")
        return

    ids = read_ids(args)
    print(f"# {len(ids)} Drive file(s)\n")

    docs, skipped = [], []
    for fid in ids:
        name, size = head(fid)
        if not name:
            skipped.append((fid, size))
            continue
        info = classify(name)
        info.update(id=fid, size=size)
        docs.append(info)

    structured = [d for d in docs if d["structured"]]
    freeform = [d for d in docs if not d["structured"]]

    print("GUIDELINE / MATRIX DOCUMENTS")
    print("-" * 100)
    for d in sorted(structured, key=lambda x: (x["scope"].lower(), x["_sort_date"]), reverse=False):
        types = ", ".join(d["loan_types"])
        print(f"  {d['upload_date']}  {str(d['size']):>9}  {d['name']}")
        print(f"{'':14}scope={d['scope']!r}  doc={d['doctype']!r}  loan types -> {types}")

    if freeform:
        print("\nOTHER FILES (no scope/date convention: lock policies, portal guides, disclosures)")
        print("-" * 100)
        for d in sorted(freeform, key=lambda x: x["name"].lower()):
            print(f"  {'':10}  {str(d['size']):>9}  {d['name']}")

    if skipped:
        print("\nNOT FETCHABLE (Google-native file, folder, or permission change)")
        for fid, size in skipped:
            print(f"  id={fid}  size={size}")

    # duplicates by (name, size)
    seen = {}
    for d in docs:
        seen.setdefault((d["name"], d["size"]), []).append(d["id"])
    dupes = {k: v for k, v in seen.items() if len(v) > 1}
    if dupes:
        print("\nDUPLICATES (same name and size, more than one Drive id)")
        for (name, _size), fids in dupes.items():
            print(f"  {name}  x{len(fids)}")
    clashes = {}
    for d in docs:
        clashes.setdefault(d["name"], set()).add(d["size"])
    clashes = {n: s for n, s in clashes.items() if len(s) > 1}
    if clashes:
        print("\nSAME NAME, DIFFERENT CONTENT (filename is not a unique key)")
        for name, sizes in clashes.items():
            print(f"  {name}  sizes={sorted(sizes)}")

    if not args.loan_type:
        print("\nPass --loan-type to rank the documents that govern one product family.")
        return

    lt = args.loan_type
    matches = [d for d in structured if covers(d, lt)]
    if not matches:
        print(f"\nNO DOCUMENT CLAIMS LOAN TYPE {lt!r}.")
        print("  Either the lender does not offer it, or its guideline is filed under a")
        print("  lender-specific program name. Scopes this tool could not map to a LoanType:")
        unmapped = sorted({t[1:] for d in structured for t in d["loan_types"] if t.startswith("?")})
        for t in unmapped:
            print(f"    {t}")
        if not unmapped:
            print("    (none — every scope mapped, so the lender likely does not offer it)")
        print("  Lenders name Non-QM and portfolio products themselves, so those scopes are")
        print("  program names rather than loan types. Pick from the full list above by hand.")
        return

    # Newest first, because using a stale guideline is the dangerous error. An explicit
    # scope still beats a bare ALL wildcard, and within one date a narrower scope and a
    # document that includes Guidelines win.
    def rank(d):
        wildcard = WILDCARD in d["loan_types"]
        breadth = len(d["loan_types"])
        has_guidelines = "guidelines" in d["doctype"].lower()
        return (wildcard, -int(d["_sort_date"]), breadth, not has_guidelines)

    matches.sort(key=rank)
    print(f"\nDOCUMENTS GOVERNING {lt} (newest first; ALL-wildcard documents last)")
    print("-" * 100)
    for i, d in enumerate(matches, 1):
        note = "ALL wildcard" if WILDCARD in d["loan_types"] else f"{len(d['loan_types'])} loan type(s)"
        print(f"  {i}. {d['upload_date']}  {d['name']}")
        print(f"{'':6}{note}, doc={d['doctype']!r}, id={d['id']}")
    print("\n  The date above is the UPLOAD date from the filename, not the document's own")
    print("  revision date. Confirm against the PDF before recording anything.")

    if args.download:
        out = Path(args.download)
        out.mkdir(parents=True, exist_ok=True)
        for d in matches[:args.top]:
            dest = out / d["name"]
            subprocess.run(["curl", "-sL", "-m", "180", "-o", str(dest),
                            f"https://drive.google.com/uc?export=download&id={d['id']}"], check=False)
            title = subprocess.run(["pdfinfo", str(dest)], capture_output=True, text=True,
                                   check=False).stdout
            t = re.search(r"(?im)^Title:\s*(.+)$", title)
            p = re.search(r"(?im)^Pages:\s*(\d+)$", title)
            print(f"\n  saved {dest}")
            print(f"    pages={p.group(1) if p else '?'}  pdf title={t.group(1).strip() if t else '<none>'}")


if __name__ == "__main__":
    main()
