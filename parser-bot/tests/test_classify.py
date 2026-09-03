from pathlib import Path
from parser_bot.classify import classify, LAYOUT, TESTS_GREEN, LOGIN_DOWNLOAD, EMAIL_MISSING

FIX = Path(__file__).parent / "fixtures"


def test_layout_picks_most_severe_error_type_and_its_detail():
    c = classify("Error while parsing rates for AAA", True, (FIX / "report_layout.txt").read_text())
    assert c.cls == LAYOUT
    assert c.error_type == "CRAWL_MISMATCH"                 # outranks VALUE_MISMATCH
    assert c.cause == 'field_3 (ficoLtv): crawlNote "Credit Score" not found on page 2'
    assert (c.adj_status, c.rate_status) == ("FAILED", "PASSED")


def test_green_report_means_transient():
    c = classify("UWMRateParser empty rate tables", True, (FIX / "report_green.txt").read_text())
    assert c.cls == TESTS_GREEN and c.error_type == "" and c.adj_status == "PASSED"


def test_login_and_email_causes_without_a_sheet():
    assert classify("ProvidentRateDownloader: login rejected", False, None).cls == LOGIN_DOWNLOAD
    assert classify("Selenium timeout waiting for loanProgramFilter", False, None).cls == LOGIN_DOWNLOAD
    assert classify("Could not handle email with subject Rates", False, None).cls == EMAIL_MISSING
    c = classify("UWMRateParser empty rate tables", False, None)
    assert c.cls == EMAIL_MISSING and "no ratesheet" in c.cause.lower()


def test_failed_report_without_typed_lines_falls_back_to_unknown():
    report = "RESULTS\n-------\nAdj:  FAILED\nRate: FAILED\n\njava.lang.IllegalStateException: boom\n"
    c = classify("x", True, report)
    assert c.cls == LAYOUT and c.error_type == "UNKNOWN" and "IllegalStateException" in c.cause
