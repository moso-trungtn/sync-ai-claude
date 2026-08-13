"""Ratesheet fingerprint extractor (deterministic).

A fingerprint separates NARRATIVE content (promo banners, program names —
kept verbatim, dates masked) from TABULAR content (rates/adjustments —
numbers masked so daily rate moves never diff).
"""
from __future__ import annotations
import argparse, json, re, subprocess
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


def _extract_xlsx(path: Path) -> dict:
    raise NotImplementedError


def extract(path: Path) -> dict:
    path = Path(path)
    if path.suffix.lower() == ".pdf":
        return _extract_pdf(path)
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
