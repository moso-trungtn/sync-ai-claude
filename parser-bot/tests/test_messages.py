from types import SimpleNamespace as NS
from parser_bot.classify import Classification
from parser_bot.messages import triage_text, result_text, failure_text, disabled_text, status_text, unknown_lender_text
from parser_bot.state import NightState, LenderState, TRIAGED, NOT_CODE
from parser_bot.triage import TriageResult


def layout_res():
    return TriageResult("AAALendings", "QM", True, "/tmp/aaa.xlsx",
                        Classification("LAYOUT", "CRAWL_MISMATCH", 'row label "Credit Score" not found', "FAILED", "PASSED"),
                        "1", 4, True, "/tmp/pf/aaalendings/report.txt")


def test_triage_text_for_layout_offers_fix():
    t = triage_text(layout_res(), "AAA Lendings", "21:14 ICT", "gs://b/history/AAALendings/2026/09/03/x.xlsx")
    assert t.splitlines()[0] == "🔎 *AAA Lendings* (QM) failed 21:14 ICT"
    assert '• Cause: CRAWL_MISMATCH — row label "Credit Score" not found' in t
    assert "• Prediction: Tier 1 (cookbook streak 4, past fix hint) · ~10 min" in t
    assert "• Sheet: gs://b/history/AAALendings/2026/09/03/x.xlsx" in t
    assert t.rstrip().endswith("Reply `@Parser Bot fix AAALendings` to fix, `@Parser Bot skip AAALendings` to ignore.")


def test_triage_text_for_not_code_does_not_offer_fix():
    res = TriageResult("Provident", "QM", False, "", Classification("LOGIN_DOWNLOAD", "", "login rejected"), "", 0, False, "")
    t = triage_text(res, "Provident Funding", "21:14 ICT", "")
    assert "Not a code problem" in t and "fix Provident" not in t


def test_result_failure_and_disabled_texts():
    fix = NS(status="fixed", tier="1", error_type="CRAWL_MISMATCH", branch="MOSO-17140",
             commits=["a1", "b2"], files=["AAALendingsTables.java", "adj-expectations/aaa.txt"],
             tests={"rate": "PASSED", "adj": "PASSED"}, notes='crawlNote "Credit Score" → "FICO Score"')
    r = result_text("AAA Lendings", fix, "MOSO-17140")
    assert r.startswith("✅ *AAA Lendings* fixed — branch MOSO-17140, 2 commits, tests: RateParserTest ✓ AdjustmentParsersTest ✓")
    assert "• Changed: AAALendingsTables.java, adj-expectations/aaa.txt" in r and "• Jira: MOSO-17140" in r
    f = failure_text("AAA Lendings", NS(status="failed", tier="2", notes="NPE in page 3", branch="MOSO-17140"), "MOSO-17140")
    assert f == "❌ *AAA Lendings* not fixed after Tier 2 — NPE in page 3. Left on branch MOSO-17140 for a human."
    assert "Phase A" in disabled_text()
    assert "did not fail tonight" in unknown_lender_text("Foo", [])
    assert "PennyMac, PennyMacCorrespondent" in unknown_lender_text("Penny", ["PennyMac", "PennyMacCorrespondent"])


def test_status_text_lists_lenders(tmp_path):
    st = NightState.load(str(tmp_path), "2026-09-03")
    st.lenders["AAALendings|QM"] = LenderState("AAALendings", "QM", TRIAGED, "t", tier="1")
    st.lenders["Provident|QM"] = LenderState("Provident", "QM", NOT_CODE, "t", cls="LOGIN_DOWNLOAD")
    s = status_text(st, {"AAALendings": "AAA Lendings", "Provident": "Provident Funding"})
    assert "AAA Lendings (QM): TRIAGED" in s and "Provident Funding (QM): NOT_CODE" in s
