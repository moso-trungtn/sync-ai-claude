"""Per-night persisted state (state/<night>.json). Atomic writes so a crash never leaves a half file."""
from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path

DETECTED = "DETECTED"
TRIAGED = "TRIAGED"
AWAITING_CONFIRM = "AWAITING_CONFIRM"
FIXING = "FIXING"
FIXED = "FIXED"
FIX_FAILED = "FIX_FAILED"
SKIPPED = "SKIPPED"
NOT_CODE = "NOT_CODE"


@dataclass
class LenderState:
    lender: str
    channel: str
    status: str
    detected_at: str
    reason: str = ""
    cause: str = ""
    cls: str = ""
    error_type: str = ""
    tier: str = ""
    streak: int = 0
    sheet: str = ""
    thread_name: str = ""
    branch: str = ""
    notes: str = ""


@dataclass
class NightState:
    night: str
    path: str
    seen_keys: set[str] = field(default_factory=set)
    ticket: str | None = None
    prepared: bool = False
    lenders: dict[str, LenderState] = field(default_factory=dict)

    @staticmethod
    def key(lender: str, channel: str) -> str:
        return f"{lender}|{channel}"

    @classmethod
    def load(cls, state_dir: str, night: str) -> "NightState":
        path = os.path.join(state_dir, f"{night}.json")
        st = cls(night=night, path=path)
        if os.path.exists(path):
            raw = json.loads(Path(path).read_text(encoding="utf-8"))
            st.seen_keys = set(raw.get("seen_keys", []))
            st.ticket = raw.get("ticket")
            st.prepared = bool(raw.get("prepared", False))
            st.lenders = {k: LenderState(**v) for k, v in raw.get("lenders", {}).items()}
        return st

    def mark_seen(self, key: str) -> bool:
        if key in self.seen_keys:
            return False
        self.seen_keys.add(key)
        return True

    def save(self) -> None:
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        data = {
            "night": self.night,
            "seen_keys": sorted(self.seen_keys),
            "ticket": self.ticket,
            "prepared": self.prepared,
            "lenders": {k: asdict(v) for k, v in self.lenders.items()},
        }
        fd, tmp = tempfile.mkstemp(dir=os.path.dirname(self.path), suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp, self.path)
