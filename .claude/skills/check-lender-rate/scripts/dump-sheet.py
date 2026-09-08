#!/usr/bin/env python3
"""Dump a lender ratesheet by real cell coordinate.

Why this exists: collapsing a sheet to CSV shifts columns silently. Rate grids
often start in column A while adjustment tables start in column B, so a
"row 577, 3rd value" read off a squashed dump lands on the wrong column and
produces a fake mismatch. Everything here prints the true coordinate.

Usage:
  # where is a label?
  python3 dump-sheet.py sheet.xlsx --find "Escrow Waiver"
  python3 dump-sheet.py sheet.xlsx --find "WA" --exact

  # what is around it? (row range, real coordinates, blank cells kept)
  python3 dump-sheet.py sheet.xlsx --rows 529-545
  python3 dump-sheet.py sheet.xlsx --rows 154-173 --cols A-E

  # one cell / one row, unambiguous
  python3 dump-sheet.py sheet.xlsx --cell C577
  python3 dump-sheet.py sheet.xlsx --row 577

  # a labelled grid: header row + data rows, aligned
  python3 dump-sheet.py sheet.xlsx --grid 615-633 --cols B-P

  # PDF ratesheets
  python3 dump-sheet.py sheet.pdf --find "Escrow" --page 3
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path


def col_letter(idx: int) -> str:
    """1 -> A, 27 -> AA."""
    out = ""
    while idx:
        idx, rem = divmod(idx - 1, 26)
        out = chr(65 + rem) + out
    return out


def col_index(letter: str) -> int:
    idx = 0
    for ch in letter.upper():
        idx = idx * 26 + (ord(ch) - 64)
    return idx


def fmt(value) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        # ratesheets carry float noise: -0.06600000000000006 is -0.066
        rounded = round(value, 6)
        return str(int(rounded)) if rounded == int(rounded) else str(rounded)
    return str(value)


def parse_span(span: str, default_hi: int):
    if span is None:
        return 1, default_hi
    m = re.fullmatch(r"([A-Za-z]+|\d+)\s*[-:]\s*([A-Za-z]+|\d+)", span.strip())
    if not m:
        sys.exit(f"bad range: {span!r} (use 10-20 or B-P)")
    lo, hi = m.group(1), m.group(2)
    if lo.isdigit():
        return int(lo), int(hi)
    return col_index(lo), col_index(hi)


def load(path: Path, sheet_name: str | None):
    try:
        import openpyxl
    except ImportError:
        sys.exit("pip install openpyxl")
    wb = openpyxl.load_workbook(path, data_only=True)
    if sheet_name:
        if sheet_name not in wb.sheetnames:
            sys.exit(f"no sheet {sheet_name!r}; have {wb.sheetnames}")
        return wb, wb[sheet_name]
    return wb, wb.worksheets[0]


def do_find(ws, needle: str, exact: bool, cols_hi: int):
    hits = 0
    low = needle.lower()
    for row in ws.iter_rows(min_row=1, max_row=ws.max_row, max_col=cols_hi):
        for cell in row:
            if cell.value is None:
                continue
            text = str(cell.value).strip()
            match = text.lower() == low if exact else low in text.lower()
            if match:
                print(f"  {cell.coordinate:>8}  (row {cell.row}, col {col_letter(cell.column)})  {text[:90]!r}")
                hits += 1
    print(f"\n  {hits} hit(s) for {needle!r}{' (exact)' if exact else ''}")


def do_rows(ws, lo: int, hi: int, clo: int, chi: int):
    for r in range(lo, min(hi, ws.max_row) + 1):
        cells = []
        for c in range(clo, min(chi, ws.max_column) + 1):
            val = fmt(ws.cell(r, c).value)
            if val:
                cells.append(f"{col_letter(c)}={val}")
        if cells:
            print(f"  r{r:<5} " + "  ".join(cells))


def do_grid(ws, lo: int, hi: int, clo: int, chi: int):
    """First row of the span is treated as the header; the rest align under it."""
    chi = min(chi, ws.max_column)
    header = [fmt(ws.cell(lo, c).value) for c in range(clo, chi + 1)]
    widths = [max(len(h), 9) for h in header]
    coords = [col_letter(c) for c in range(clo, chi + 1)]

    print("  " + " ".join(f"{c:>{w}}" for c, w in zip(coords, widths)))
    print(f"  r{lo:<4} " + " ".join(f"{h[:w]:>{w}}" for h, w in zip(header, widths)))
    print("  " + "-" * (sum(widths) + len(widths)))
    for r in range(lo + 1, min(hi, ws.max_row) + 1):
        vals = [fmt(ws.cell(r, c).value) for c in range(clo, chi + 1)]
        if any(vals):
            print(f"  r{r:<4} " + " ".join(f"{v[:w]:>{w}}" for v, w in zip(vals, widths)))


def do_pdf(path: Path, needle: str | None, page: int | None):
    cmd = ["pdftotext", "-layout"]
    if page:
        cmd += ["-f", str(page), "-l", str(page)]
    cmd += [str(path), "-"]
    try:
        text = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout
    except FileNotFoundError:
        sys.exit("pdftotext not found (brew install poppler)")
    if not needle:
        print(text)
        return
    low = needle.lower()
    for num, line in enumerate(text.splitlines(), 1):
        if low in line.lower():
            print(f"  L{num:<5} {line.rstrip()}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--sheet", help="worksheet name (default: first)")
    ap.add_argument("--find", help="locate cells containing this text")
    ap.add_argument("--exact", action="store_true", help="--find matches the whole cell")
    ap.add_argument("--rows", help="row span, e.g. 529-545")
    ap.add_argument("--row", type=int, help="a single row")
    ap.add_argument("--cell", help="a single cell, e.g. C577")
    ap.add_argument("--cols", help="column span, e.g. B-P")
    ap.add_argument("--grid", help="row span whose first row is the header")
    ap.add_argument("--page", type=int, help="PDF page (1-based)")
    ap.add_argument("--sheets", action="store_true", help="list worksheets and exit")
    args = ap.parse_args()

    path = Path(args.path)
    if not path.exists():
        sys.exit(f"no such file: {path}")

    if path.suffix.lower() == ".pdf":
        do_pdf(path, args.find, args.page)
        return

    wb, ws = load(path, args.sheet)

    if args.sheets:
        for name in wb.sheetnames:
            sheet = wb[name]
            print(f"  {name!r}  dims={sheet.dimensions} rows={sheet.max_row} cols={sheet.max_column}")
        return

    print(f"# {path.name}  sheet={ws.title!r}  rows={ws.max_row}  cols={ws.max_column}")

    clo, chi = parse_span(args.cols, ws.max_column)

    if args.cell:
        m = re.fullmatch(r"([A-Za-z]+)(\d+)", args.cell.strip())
        if not m:
            sys.exit(f"bad cell: {args.cell!r}")
        cell = ws.cell(int(m.group(2)), col_index(m.group(1)))
        print(f"  {args.cell.upper()} = {fmt(cell.value)!r}")
    elif args.find:
        do_find(ws, args.find, args.exact, chi)
    elif args.grid:
        lo, hi = parse_span(args.grid, ws.max_row)
        do_grid(ws, lo, hi, clo, chi)
    elif args.row:
        do_rows(ws, args.row, args.row, clo, chi)
    elif args.rows:
        lo, hi = parse_span(args.rows, ws.max_row)
        do_rows(ws, lo, hi, clo, chi)
    else:
        ap.error("pick one of --find / --rows / --row / --cell / --grid / --sheets")


if __name__ == "__main__":
    main()
