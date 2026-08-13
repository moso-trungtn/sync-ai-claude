"""Ratesheet fingerprint extractor (deterministic).

A fingerprint separates NARRATIVE content (promo banners, program names —
kept verbatim, dates masked) from TABULAR content (rates/adjustments —
numbers masked so daily rate moves never diff).
"""
from __future__ import annotations
import argparse, hashlib, json, re, subprocess, zipfile
from pathlib import Path

NUM_RE = re.compile(r"^[<>=~+\-(]*\$?\d[\d,]*\.?\d*%?\)?$")
ANY_NUM_RE = re.compile(r"\$?\d[\d,]*\.?\d*%?")
DATE_RE = re.compile(
    r"\b(January|February|March|April|May|June|July|August|September|"
    r"October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|"
    r"Nov|Dec)\b\.?\s*\d{0,2}(st|nd|rd|th)?,?\s*\d{0,4}"
    r"|\b\d{1,2}/\d{1,2}(/\d{2,4})?\b", re.I)
MIN_TEXT_CHARS = 200
MIN_BANNER_LEN = 12


def _collapse(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def _is_numeric_line(line: str) -> bool:
    toks = line.split()
    if not toks:
        return False
    numeric = sum(1 for t in toks if NUM_RE.match(t))
    return numeric / len(toks) >= 0.5


def _mask(line: str) -> str:
    return _collapse(ANY_NUM_RE.sub("#", line))


def _mask_dates(line: str) -> str:
    return _collapse(DATE_RE.sub("<DATE>", line))


def _classify_lines(lines) -> tuple[list[str], list[str]]:
    banners, structure = set(), set()
    for raw in lines:
        line = _collapse(raw)
        if not line:
            continue
        if _is_numeric_line(line):
            structure.add(_mask(line))
        elif len(line) >= MIN_BANNER_LEN:
            banners.add(_mask_dates(line))
    return sorted(banners), sorted(structure)


def _extract_pdf(path: Path) -> dict:
    text = subprocess.run(
        ["pdftotext", "-layout", str(path), "-"],
        capture_output=True, text=True).stdout
    pages = max(1, text.count("\f")) if text else 0
    banners, structure = _classify_lines(text.splitlines())
    return {
        "version": 1, "format": "pdf",
        "unextractable": len(text.strip()) < MIN_TEXT_CHARS,
        "banners": banners, "structure": structure,
        "images": [], "pages": pages,
    }


def embedded_images(path: Path) -> list[tuple[str, bytes]]:
    out = []
    with zipfile.ZipFile(path) as z:
        for name in sorted(z.namelist()):
            if name.startswith("xl/media/"):
                out.append((name, z.read(name)))
    return out


def _extract_xlsx(path: Path) -> dict:
    import openpyxl
    wb = openpyxl.load_workbook(path, read_only=False, data_only=True)
    forced_banners, lines = set(), []
    for ws in wb.worksheets:
        if ws.sheet_state != "visible":
            continue
        merged_wide = set()
        for rng in ws.merged_cells.ranges:
            if rng.max_col - rng.min_col + 1 >= 4:
                # Key by anchor only; non-anchor cells have value=None in openpyxl
                merged_wide.add((rng.min_row, rng.min_col))
        for row in ws.iter_rows():
            for cell in row:
                if cell.value is None:
                    continue
                text = _collapse(str(cell.value))
                if not text:
                    continue
                tagged = f"{ws.title}: {text}"
                fill = cell.fill
                filled = (fill is not None and fill.patternType == "solid"
                          and getattr(fill.fgColor, "rgb", None)
                          not in (None, "00000000", "FFFFFFFF"))
                is_banner_cell = ((cell.row, cell.column) in merged_wide
                                  or (filled and len(text) >= MIN_BANNER_LEN))
                if is_banner_cell and not _is_numeric_line(text):
                    forced_banners.add(_mask_dates(tagged))
                else:
                    lines.append(tagged)
    banners, structure = _classify_lines(lines)
    banners = sorted(set(banners) | forced_banners)
    img_hashes = sorted(hashlib.sha1(b).hexdigest()
                        for _, b in embedded_images(path))
    return {
        "version": 1, "format": "xlsx",
        "unextractable": not banners and not structure,
        "banners": banners, "structure": structure,
        "images": img_hashes,
        "pages": sum(1 for ws in wb.worksheets if ws.sheet_state == "visible"),
    }


def extract(path: Path) -> dict:
    path = Path(path)
    if path.suffix.lower() == ".pdf":
        return _extract_pdf(path)
    elif path.suffix.lower() == ".xls":
        # Old binary .xls format cannot be read by openpyxl
        return {
            "version": 1, "format": "xls",
            "unextractable": True,
            "banners": [], "structure": [],
            "images": [], "pages": 0,
        }
    return _extract_xlsx(path)   # Task 3


def to_json(fp: dict) -> str:
    return json.dumps(fp, sort_keys=True, indent=2, ensure_ascii=False) + "\n"


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("-o", "--out")
    args = ap.parse_args()
    out = to_json(extract(Path(args.file)))
    if args.out:
        Path(args.out).write_text(out)
    else:
        print(out, end="")
