#!/usr/bin/env python3
"""List every mention of "Vantage" in a lender ratesheet (xlsx/xlsm/xls/pdf), with its row context.

Why this exists: whether a lender prices FICO and VantageScore in ONE column or in two columns offset by a band is only
visible in the layout, so the scan prints each hit with the other cells of its row, and groups the hits into the patterns
the decision in SKILL.md is made on. The hints are a starting point; read the grid with dump-sheet.py before deciding.

Usage:
  python3 vantage-scan.py <sheet.xlsx|.xls|.pdf> [--word Vantage] [--context 8]
"""

import argparse
import re
import subprocess
import sys
from collections import OrderedDict
from pathlib import Path

PATTERNS = OrderedDict([
    ("shared column (one band set: 'FICO/Vantage', 'FICO / VS')", re.compile(r"fico\s*/\s*(vantage|vs\b)|(vantage|vs)\s*/\s*fico", re.I)),
    ("standalone Vantage column header ('Vantage Score', 'Vantage')", re.compile(r"^\s*vantage(\s*score)?\s*$", re.I)),
    ("offset wording (+20, 'points higher', 'one band')", re.compile(r"vantage.*(\+\s*20|20\s*points?|one band|higher)|(\+\s*20|20\s*points?).*vantage", re.I)),
    ("scope / eligibility note ('not eligible', 'only', 'N/A', 'not accepted')", re.compile(r"vantage.*(not eligible|ineligible|only|n/a|not accepted|not available|not applicable)", re.I)),
])


def cell_text(value) -> str:
    return " ".join(str(value).split()) if value is not None else ""


def col_letter(idx: int) -> str:
    out = ""
    while idx:
        idx, rem = divmod(idx - 1, 26)
        out = chr(65 + rem) + out
    return out


def scan_workbook_xlsx(path: Path, word: str, context: int):
    import openpyxl
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    for ws in wb.worksheets:
        for row in ws.iter_rows():
            cells = [(c.coordinate, cell_text(c.value)) for c in row if c.value is not None and cell_text(c.value)]
            for coord, text in cells:
                if word.lower() in text.lower():
                    others = [f"{k}={t[:22]}" for k, t in cells if k != coord][:context]
                    yield ws.title, coord, text, others


def scan_workbook_xls(path: Path, word: str, context: int):
    import xlrd
    wb = xlrd.open_workbook(path)
    for ws in wb.sheets():
        for r in range(ws.nrows):
            cells = [(f"{col_letter(c + 1)}{r + 1}", cell_text(ws.cell_value(r, c))) for c in range(ws.ncols) if cell_text(ws.cell_value(r, c))]
            for coord, text in cells:
                if word.lower() in text.lower():
                    others = [f"{k}={t[:22]}" for k, t in cells if k != coord][:context]
                    yield ws.name, coord, text, others


def scan_pdf(path: Path, word: str, context: int):
    try:
        text = subprocess.run(["pdftotext", "-layout", str(path), "-"], capture_output=True, text=True, check=True).stdout
    except FileNotFoundError:
        sys.exit("pdftotext not found (brew install poppler)")
    for page_no, page in enumerate(text.split("\f"), start=1):
        for line_no, line in enumerate(page.splitlines(), start=1):
            if word.lower() in line.lower():
                yield f"page {page_no}", f"line {line_no}", " ".join(line.split()), []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--word", default="Vantage")
    ap.add_argument("--context", type=int, default=8, help="other cells of the hit's row to print")
    args = ap.parse_args()
    path = Path(args.path)
    suffix = path.suffix.lower()
    if suffix in (".xlsx", ".xlsm"):
        hits = list(scan_workbook_xlsx(path, args.word, args.context))
    elif suffix == ".xls":
        hits = list(scan_workbook_xls(path, args.word, args.context))
    elif suffix == ".pdf":
        hits = list(scan_pdf(path, args.word, args.context))
    else:
        sys.exit(f"unsupported file type {suffix}")

    print(f"# {path.name}: {len(hits)} cell(s) mention '{args.word}'")
    if not hits:
        print("\nNo mention: class C (FICO only) unless the lender says otherwise. Nothing to switch on.")
        return
    by_sheet = OrderedDict()
    for sheet, coord, text, others in hits:
        by_sheet.setdefault(sheet, []).append((coord, text, others))
    for sheet, items in by_sheet.items():
        print(f"\n[{sheet}] {len(items)} hit(s)")
        for coord, text, others in items:
            print(f"  {coord:>8}  {text[:150]}")
            if others:
                print(f"            row: {' | '.join(others)}")

    print("\n# Pattern hints (a human reads the grid before deciding)")
    for name, rx in PATTERNS.items():
        matched = [(sheet, coord) for sheet, coord, text, _ in hits if rx.search(text)]
        shown = ", ".join(f"{s}!{c}" for s, c in matched[:6]) + (" ..." if len(matched) > 6 else "")
        print(f"  {len(matched):>3}  {name}" + (f"\n         {shown}" if matched else ""))


if __name__ == "__main__":
    main()
