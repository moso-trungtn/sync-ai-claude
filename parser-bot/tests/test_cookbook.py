from pathlib import Path
from parser_bot.cookbook import parse_cookbook, predict_tier

TEXT = (Path(__file__).parent / "fixtures" / "cookbook_sample.md").read_text()


def test_parse_cookbook_entries():
    cb = parse_cookbook(TEXT)
    assert set(cb) == {"PennyMac", "LoganFinance"}
    assert cb["PennyMac"].tier_0_streak == 6
    assert cb["PennyMac"].tier_history == [0, 0, 0, 1, 0, 0, 0, 0, 0, 0]
    assert cb["LoganFinance"].last_tier1_fix.startswith("VALUE_MISMATCH")


def test_predict_tier_follows_fix_parser_algorithm():
    cb = parse_cookbook(TEXT)
    assert predict_tier(cb["PennyMac"], "VALUE_MISMATCH") == ("0", 6, False)      # streak >= 3 → optimistic Tier 0
    assert predict_tier(cb["PennyMac"], "CRAWL_MISMATCH") == ("1", 6, True)        # known pattern + past fix hint
    assert predict_tier(None, "VALUE_MISMATCH") == ("1", 0, False)
    assert predict_tier(None, "NULL_POINTER") == ("2", 0, False)
    assert predict_tier(cb["LoganFinance"], "UNKNOWN") == ("2", 3, False)
