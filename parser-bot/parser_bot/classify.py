"""Turn (alert reason, download outcome, parser-fix report) into one of four classes. Pure, no I/O."""
from __future__ import annotations

import re
from dataclasses import dataclass

LOGIN_DOWNLOAD = "LOGIN_DOWNLOAD"
EMAIL_MISSING = "EMAIL_MISSING"
LAYOUT = "LAYOUT"
TESTS_GREEN = "TESTS_GREEN"
NO_TEST = "NO_TEST"

ERROR_PRIORITY = ["NULL_POINTER", "STRUCTURE_CHANGE", "KEYWORD_MISSING", "CRAWL_MISMATCH",
                  "RATE_COUNT", "NEW_ADJ_DETECTED", "VALUE_MISMATCH"]

_LOGIN = re.compile(r"login|rejected|imperva|403|timeout|selenium|download|captcha|credential", re.I)
_EMAIL = re.compile(r"could not handle email|no email|attachment", re.I)
_ERR_LINE = re.compile(r"^(" + "|".join(ERROR_PRIORITY) + r")\s*\|\s*(.*)$", re.M)
_ADJ = re.compile(r"^Adj:\s+(PASSED|FAILED)", re.M)
_RATE = re.compile(r"^Rate:\s+(PASSED|FAILED)", re.M)


@dataclass(frozen=True)
class Classification:
    cls: str
    error_type: str
    cause: str
    adj_status: str = ""
    rate_status: str = ""


def classify(reason: str, downloaded: bool, report: str | None, test_available: bool = True) -> Classification:
    reason = reason or ""
    if not downloaded:
        if _LOGIN.search(reason):
            return Classification(LOGIN_DOWNLOAD, "", reason.strip())
        if _EMAIL.search(reason):
            return Classification(EMAIL_MISSING, "", reason.strip())
        return Classification(EMAIL_MISSING, "", f"No ratesheet found for today; builder said: {reason.strip()}")
    if not test_available:
        return Classification(NO_TEST, "", "No local parser test for this lender (lender-info found none); check the builder log")
    text = report or ""
    adj = (_ADJ.search(text) or [None, ""])[1]
    rate = (_RATE.search(text) or [None, ""])[1]
    if adj == "PASSED" and rate == "PASSED":
        return Classification(TESTS_GREEN, "", "Local tests pass on today's sheet", adj, rate)
    found = {m.group(1): m.group(2).strip() for m in reversed(list(_ERR_LINE.finditer(text)))}
    for t in ERROR_PRIORITY:
        if t in found:
            return Classification(LAYOUT, t, found[t], adj, rate)
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    exc = next((ln for ln in lines if "Exception" in ln), "") or next((ln for ln in lines if "FAILED" in ln), "")
    return Classification(LAYOUT, "UNKNOWN", exc or "Tests failed; see report", adj, rate)
