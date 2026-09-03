from pathlib import Path
from parser_bot.cookbook import CookbookEntry, parse_cookbook, predict_tier

TEXT = (Path(__file__).parent / "fixtures" / "cookbook_sample.md").read_text()


def test_parse_cookbook_keys_on_the_first_header_token_and_skips_global_lessons():
    cb = parse_cookbook(TEXT)
    assert set(cb) == {"LoanStream", "JMAC", "UnionHome", "RocketCorrespondent", "LoganFinance"}


def test_parse_cookbook_reads_the_real_field_shapes():
    cb = parse_cookbook(TEXT)
    assert cb["LoanStream"].tier_history == [0] and cb["LoanStream"].tier_0_streak == 1
    assert cb["LoanStream"].last_fix.startswith("2026-08-11") and "NOT a parser bug" in cb["LoanStream"].last_error
    assert cb["LoanStream"].last_tier1_fix == ""                       # entry has no such field
    assert cb["LoganFinance"].tier_history == [0, 0, 1] and cb["LoganFinance"].tier_0_streak == 0
    assert cb["UnionHome"].last_tier1_fix.startswith("Lender REMOVED the blank page")


def test_predict_tier_follows_fix_parser_algorithm():
    cb = parse_cookbook(TEXT)
    assert predict_tier(cb["UnionHome"], "CRAWL_MISMATCH") == ("1", 0, True)   # hint lives in last_error only
    assert "CRAWL_MISMATCH" not in cb["UnionHome"].last_tier1_fix
    assert predict_tier(cb["LoanStream"], "VALUE_MISMATCH") == ("1", 1, False)
    assert predict_tier(cb["JMAC"], "NULL_POINTER") == ("2", 1, False)
    assert predict_tier(None, "VALUE_MISMATCH") == ("1", 0, False)
    assert predict_tier(None, "NULL_POINTER") == ("2", 0, False)
    assert predict_tier(CookbookEntry("X", tier_0_streak=6), "VALUE_MISMATCH") == ("0", 6, False)  # streak >= 3


def test_hint_comes_from_any_of_the_three_narrative_fields():
    assert predict_tier(CookbookEntry("X", last_tier1_fix="CRAWL_MISMATCH on field_8"), "CRAWL_MISMATCH")[2] is True
    assert predict_tier(CookbookEntry("X", last_error="RATE_COUNT 421 != 472"), "RATE_COUNT")[2] is True
    assert predict_tier(CookbookEntry("X", last_fix="2026-08-11 KEYWORD_MISSING re-anchored"), "KEYWORD_MISSING")[2] is True
    assert predict_tier(CookbookEntry("X", last_error="none — verify only"), "CRAWL_MISMATCH")[2] is False
    assert predict_tier(CookbookEntry("X", last_error="CRAWL_MISMATCH"), "")[2] is False
