"""Parse a Chat app event into a bot command. Only human MESSAGE events with a known verb count."""
from __future__ import annotations

import re
from dataclasses import dataclass

_VERB = re.compile(r"^\s*(fix|skip|retry|status)\b\s*(.*)$", re.I)
_MENTION = re.compile(r"^\s*@parser\s*bot\b", re.I)


@dataclass(frozen=True)
class Command:
    kind: str
    lender_text: str
    sender_email: str
    sender_name: str
    thread_name: str
    space: str


def _payload(event: dict) -> tuple[dict | None, dict]:
    if "chat" in event:  # newer Workspace event shape
        mp = event.get("chat", {}).get("messagePayload", {})
        return mp.get("message"), mp.get("space", {})
    if event.get("type") == "MESSAGE":
        return event.get("message"), event.get("space", {})
    return None, {}


def parse_event(event: dict) -> Command | None:
    message, space = _payload(event)
    if not message:
        return None
    sender = message.get("sender", {}) or {}
    if sender.get("type") == "BOT":
        return None
    text = message.get("argumentText")
    if text is None:
        text = _MENTION.sub("", message.get("text", "") or "")
    m = _VERB.match(text or "")
    if not m:
        return None
    verb, rest = m.group(1).lower(), m.group(2).strip()
    kind = "fix_all" if verb == "fix" and rest.lower() == "all" else verb
    if verb in ("fix", "skip", "retry") and kind != "fix_all" and not rest:
        return None
    return Command(kind=kind, lender_text="" if kind in ("fix_all", "status") else rest,
                   sender_email=sender.get("email", "") or "", sender_name=sender.get("displayName", "") or "",
                   thread_name=(message.get("thread") or {}).get("name", "") or "",
                   space=space.get("name", "") or "")
