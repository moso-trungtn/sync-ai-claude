"""Read /fix-parser's cookbook (markdown) and predict the fix tier like the skill does."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

TIER_0_ERRORS = {"VALUE_MISMATCH", "NEW_ADJ_DETECTED", "RATE_COUNT"}
TIER_1_ERRORS = {"CRAWL_MISMATCH", "VALUE_MISMATCH", "KEYWORD_MISSING", "RATE_COUNT", "NEW_ADJ_DETECTED"}

_SECTION = re.compile(r"^## (.+?)\s*$", re.M)
_FIELD = re.compile(r"^- \*\*(\w+)\*\*:\s*(.*)$", re.M)
# A lender header is one lender token, optionally + a "(channel)" qualifier and/or "/ Twin" siblings:
# "JMAC", "LoanStream (NonQM)", "RocketCorrespondent / QuickenLoans". "GLOBAL LESSONS" is not one.
_LENDER_HEADER = re.compile(r"^[A-Za-z][A-Za-z0-9]*(\s*\([^)]+\))?(\s*/\s*[A-Za-z][A-Za-z0-9]*(\s*\([^)]+\))?)*$")


@dataclass
class CookbookEntry:
    lender: str
    tier_history: list[int] = field(default_factory=list)
    tier_0_streak: int = 0
    last_tier1_fix: str = ""
    last_fix: str = ""
    last_error: str = ""


def parse_cookbook(text: str) -> dict[str, CookbookEntry]:
    out: dict[str, CookbookEntry] = {}
    heads = list(_SECTION.finditer(text))
    for i, h in enumerate(heads):
        header = h.group(1).strip()
        if not _LENDER_HEADER.match(header):
            continue                       # "## GLOBAL LESSONS" and friends are prose, not lender entries
        body = text[h.end(): heads[i + 1].start() if i + 1 < len(heads) else len(text)]
        e = CookbookEntry(lender=header.split()[0])
        for m in _FIELD.finditer(body):
            k, v = m.group(1), m.group(2).strip()
            if k == "tier_history":
                e.tier_history = [int(x) for x in re.findall(r"\d+", v.split("]")[0])]
            elif k == "tier_0_streak":
                e.tier_0_streak = int(re.search(r"\d+", v).group(0)) if re.search(r"\d+", v) else 0
            elif k == "last_tier1_fix":
                e.last_tier1_fix = v
            elif k == "last_fix":
                e.last_fix = v
            elif k == "last_error":
                e.last_error = v
        out[e.lender] = e
    return out


def predict_tier(entry: CookbookEntry | None, error_type: str) -> tuple[str, int, bool]:
    streak = entry.tier_0_streak if entry else 0
    # Most entries record the error type in last_error, not in last_tier1_fix — check all three.
    past = " ".join([entry.last_tier1_fix, entry.last_fix, entry.last_error]) if entry else ""
    hint = bool(error_type and error_type in past)
    if error_type in TIER_0_ERRORS and streak >= 3:
        return "0", streak, hint
    if error_type in TIER_1_ERRORS:
        return "1", streak, hint
    return "2", streak, hint
