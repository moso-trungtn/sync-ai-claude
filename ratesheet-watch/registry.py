"""Lender registry: which ratesheet files exist, and their GCS URLs.

Parses LenderType.java (enum names == GCS object names) and
RatesheetFiles.java (sections named by enum; constants reveal variants
and extensions). Latest constant per (lender, variant) wins — constants
within a section are ordered oldest→newest, so last one wins.
"""
from __future__ import annotations
import re
from dataclasses import dataclass
from pathlib import Path

GCS_BASE = "https://storage.googleapis.com/lender-rate-ratesheet"

PILOT_LENDERS = [
    "HomeBridgeWholesale", "AAALendings", "ADMortgage",
    "AmWestFunding", "CommunityWholesaleLending",
]

ENUM_RE = re.compile(r"^\s{2}([A-Za-z][A-Za-z0-9]*)\(", re.M)
SECTION_RE = re.compile(r"^\s*//\s*─+\s*([A-Za-z0-9][A-Za-z0-9 ]*?)\s*─+", re.M)
CONST_RE = re.compile(
    r'public static final String\s+([A-Z0-9_]+)\s*=\s*"(/ratesheets/[^"]+)"')


def _normalize(name: str) -> str:
    return name.lower().replace(" ", "")


def _resolve_enum(section_name: str, enums_by_norm: dict[str, str]) -> str | None:
    """Match a section header (may contain spaces, e.g. "AAA Lendings") to
    its enum name (e.g. "AAALendings") by normalized (lowercase, no-space)
    comparison. Returns None if no enum matches (rename drift — drop it)."""
    return enums_by_norm.get(_normalize(section_name))


@dataclass
class Entry:
    lender: str
    variant: str          # base | nonqm | adj | zone<N>
    ext: str              # ".pdf" / ".xlsx" / ...
    latest_resource: str  # "/ratesheets/foo.pdf"

    @property
    def key(self) -> str:
        return f"{self.lender}__{self.variant}"

    def gcs_url(self, millis: int) -> str:
        if self.variant == "nonqm":
            obj = f"{self.lender}NonQM{self.ext}"
        elif self.variant == "adj":
            obj = f"{self.lender}__adjustment_{self.ext}"
        elif self.variant.startswith("zone"):
            obj = f"{self.lender}_Zone%20{self.variant[4:]}{self.ext}"
        else:
            obj = f"{self.lender}{self.ext}"
        return f"{GCS_BASE}/{obj}?v={millis}"


def _variant_of(const_name: str) -> str:
    if re.search(r"NON_?QM", const_name):
        return "nonqm"
    if "ADJUSTMENT" in const_name:
        return "adj"
    m = re.search(r"ZONE_?(\d+)", const_name)
    if m:
        return f"zone{int(m.group(1))}"
    return "base"


def load_registry(lender_type_java: str | Path, ratesheet_files_java: str | Path) -> list[Entry]:
    enums = set(ENUM_RE.findall(Path(lender_type_java).read_text()))
    enums_by_norm = {_normalize(e): e for e in enums}
    text = Path(ratesheet_files_java).read_text()

    # Split into sections; a section header names the lender enum (headers
    # may contain spaces, e.g. "AAA Lendings" for enum AAALendings).
    entries: dict[tuple[str, str], Entry] = {}
    sections = list(SECTION_RE.finditer(text))
    for i, sec in enumerate(sections):
        lender = _resolve_enum(sec.group(1), enums_by_norm)
        if lender is None:
            continue  # section name doesn't match any enum (rename drift) — skip
        end = sections[i + 1].start() if i + 1 < len(sections) else len(text)
        for const_name, resource in CONST_RE.findall(text[sec.end():end]):
            variant = _variant_of(const_name)
            ext = "." + resource.rsplit(".", 1)[1]
            # later constants overwrite earlier ones → latest wins
            entries[(lender, variant)] = Entry(lender, variant, ext, resource)
    return sorted(entries.values(), key=lambda e: e.key)
