"""Read /fix-parser's cookbook (markdown) and predict the fix tier like the skill does."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

TIER_0_ERRORS = {"VALUE_MISMATCH", "NEW_ADJ_DETECTED", "RATE_COUNT"}
TIER_1_ERRORS = {"CRAWL_MISMATCH", "VALUE_MISMATCH", "KEYWORD_MISSING", "RATE_COUNT", "NEW_ADJ_DETECTED"}

_SECTION = re.compile(r"^## (\S+)\s*$", re.M)
_FIELD = re.compile(r"^- \*\*(\w+)\*\*:\s*(.*)$", re.M)


@dataclass
class CookbookEntry:
    lender: str
    tier_history: list[int] = field(default_factory=list)
    tier_0_streak: int = 0
    last_tier1_fix: str = ""


def parse_cookbook(text: str) -> dict[str, CookbookEntry]:
    out: dict[str, CookbookEntry] = {}
    heads = list(_SECTION.finditer(text))
    for i, h in enumerate(heads):
        body = text[h.end(): heads[i + 1].start() if i + 1 < len(heads) else len(text)]
        e = CookbookEntry(lender=h.group(1))
        for m in _FIELD.finditer(body):
            k, v = m.group(1), m.group(2).strip()
            if k == "tier_history":
                e.tier_history = [int(x) for x in re.findall(r"\d+", v.split("]")[0])]
            elif k == "tier_0_streak":
                e.tier_0_streak = int(re.search(r"\d+", v).group(0)) if re.search(r"\d+", v) else 0
            elif k == "last_tier1_fix":
                e.last_tier1_fix = v
        out[e.lender] = e
    return out


def predict_tier(entry: CookbookEntry | None, error_type: str) -> tuple[str, int, bool]:
    streak = entry.tier_0_streak if entry else 0
    hint = bool(entry and error_type and error_type in entry.last_tier1_fix)
    if error_type in TIER_0_ERRORS and streak >= 3:
        return "0", streak, hint
    if error_type in TIER_1_ERRORS:
        return "1", streak, hint
    return "2", streak, hint
