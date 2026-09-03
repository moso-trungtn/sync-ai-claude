"""All Chat text lives here so wording can change without touching logic. Google Chat: *bold*, plain newlines."""
from __future__ import annotations

from .classify import LAYOUT, LOGIN_DOWNLOAD, EMAIL_MISSING, TESTS_GREEN
from .state import NightState
from .triage import TriageResult

_MINUTES = {"0": "~3 min", "1": "~10 min", "2": "~30 min"}


def triage_text(res: TriageResult, label: str, when: str, sheet_uri: str) -> str:
    lines = [f"🔎 *{label}* ({res.channel}) failed {when}"]
    c = res.classification
    if c.cls == LAYOUT:
        lines.append(f"• Cause: {c.error_type} — {c.cause}")
        hint = ", past fix hint" if res.hint else ""
        lines.append(f"• Prediction: Tier {res.tier} (cookbook streak {res.streak}{hint}) · {_MINUTES.get(res.tier, '')}".rstrip(" ·"))
        if sheet_uri:
            lines.append(f"• Sheet: {sheet_uri}")
        lines.append(f"Reply `@Parser Bot fix {res.lender}` to fix, `@Parser Bot skip {res.lender}` to ignore.")
    elif c.cls == LOGIN_DOWNLOAD:
        lines.append(f"• Cause: {c.cause}")
        lines.append("• Not a code problem — credentials/site. IT action (turn off lender or fix login).")
    elif c.cls == EMAIL_MISSING:
        lines.append(f"• Cause: {c.cause}")
        lines.append("• No ratesheet arrived / email unreadable. Nothing to fix in the parser.")
    elif c.cls == TESTS_GREEN:
        lines.append("• Local tests pass on today's sheet — likely a transient/builder issue. Retry the build instead.")
    return "\n".join(lines)


def _tests_line(tests: dict) -> str:
    mark = lambda k: "✓" if str(tests.get(k, "")).upper() == "PASSED" else "✗"
    return f"RateParserTest {mark('rate')} AdjustmentParsersTest {mark('adj')}"


def result_text(label: str, fix, key: str) -> str:
    n = len(fix.commits or [])
    head = f"✅ *{label}* fixed — branch {fix.branch}, {n} commit{'s' if n != 1 else ''}, tests: {_tests_line(fix.tests or {})}"
    lines = [head]
    if fix.files:
        lines.append("• Changed: " + ", ".join(fix.files))
    if fix.notes:
        lines.append(f"• What: {fix.notes}")
    lines.append(f"• Jira: {key} (comment with diff + test output). Review & merge in the morning.")
    return "\n".join(lines)


def failure_text(label: str, fix, key: str) -> str:
    tier = f" after Tier {fix.tier}" if getattr(fix, "tier", "") else ""
    where = f" Left on branch {fix.branch} for a human." if getattr(fix, "branch", "") else ""
    return f"❌ *{label}* not fixed{tier} — {fix.notes or fix.status}.{where}"


def disabled_text() -> str:
    return "Commands are disabled during Phase A (triage only). Fix it manually with /fix-parser for now."


def unknown_lender_text(text: str, matches: list[str]) -> str:
    if matches:
        return f"'{text}' matches several lenders: {', '.join(matches)}. Say the full name."
    return f"'{text}' did not fail tonight (or I can't match it to a lender). Try `@Parser Bot status`."


def status_text(state: NightState, labels: dict[str, str]) -> str:
    if not state.lenders:
        return f"Night {state.night}: no failures so far."
    lines = [f"Night {state.night}" + (f" · ticket {state.ticket}" if state.ticket else "")]
    for ls in state.lenders.values():
        extra = f" (Tier {ls.tier})" if ls.tier else (f" ({ls.cls})" if ls.cls else "")
        lines.append(f"• {labels.get(ls.lender, ls.lender)} ({ls.channel}): {ls.status}{extra}")
    return "\n".join(lines)
