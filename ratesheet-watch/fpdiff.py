"""Fingerprint diff → classified change list."""
from __future__ import annotations
import difflib, re
from dataclasses import dataclass

PROGRAM_KEYWORDS = re.compile(
    r"FHA|VA\b|USDA|Conventional|Jumbo|DSCR|Bank Statement|HELOC|ITIN|"
    r"Foreign National|Non-QM|High Balance|HomeReady|HomePossible", re.I)
SIMILARITY = 0.7
LAYOUT_CHURN = 0.30


@dataclass
class Change:
    kind: str
    detail: str
    materiality: str


def _promo_kind(line: str, base: str) -> str:
    return "PROGRAM" if PROGRAM_KEYWORDS.search(line) else base


def diff(old: dict, new: dict) -> list[Change]:
    changes: list[Change] = []

    if new.get("unextractable") and not old.get("unextractable"):
        changes.append(Change("UNEXTRACTABLE",
                              "new file has no extractable text", "high"))
        return changes

    added = [b for b in new["banners"] if b not in set(old["banners"])]
    removed = [b for b in old["banners"] if b not in set(new["banners"])]

    # pair similar added/removed into PROMO_CHANGED
    for a in list(added):
        best = max(removed, default=None,
                   key=lambda r: difflib.SequenceMatcher(None, a, r).ratio())
        if best and difflib.SequenceMatcher(None, a, best).ratio() > SIMILARITY:
            changes.append(Change(_promo_kind(a, "PROMO_CHANGED"),
                                  f"was: {best}\nnow: {a}", "high"))
            added.remove(a); removed.remove(best)
    changes += [Change(_promo_kind(a, "PROMO_NEW"), a, "high") for a in added]
    changes += [Change(_promo_kind(r, "PROMO_EXPIRED"), r, "high") for r in removed]

    s_old, s_new = set(old["structure"]), set(new["structure"])
    s_added, s_removed = sorted(s_new - s_old), sorted(s_old - s_new)

    if new.get("pages") != old.get("pages"):
        churn = ((len(s_added) + len(s_removed)) / max(1, len(s_old))) if (s_added or s_removed) else 0
        changes.append(Change(
            "LAYOUT",
            f"pages {old.get('pages')}→{new.get('pages')}, "
            f"structure churn {churn:.0%}", "medium"))
    else:
        # Pages are the same, report individual STRUCTURE changes
        for s in s_added:
            changes.append(Change(_promo_kind(s, "STRUCTURE"), f"+ {s}", "medium"))
        for s in s_removed:
            changes.append(Change(_promo_kind(s, "STRUCTURE"), f"- {s}", "medium"))

    if sorted(old.get("images", [])) != sorted(new.get("images", [])):
        changes.append(Change("IMAGE_CHANGED",
                              "embedded image set changed", "medium"))
    return changes


def needs_vision(old: dict, new: dict, changes: list[Change]) -> bool:
    if new.get("unextractable"):
        return True
    if any(c.kind == "IMAGE_CHANGED" for c in changes):
        return True
    text_diff = [c for c in changes if c.kind not in ("IMAGE_CHANGED",)]
    return not text_diff   # file changed but text fingerprint silent
