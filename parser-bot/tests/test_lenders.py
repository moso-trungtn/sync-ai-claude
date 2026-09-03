from pathlib import Path
from parser_bot.lenders import gen_lenders, LenderIndex

FIX = Path(__file__).parent / "fixtures" / "LenderType_sample.java"


def test_gen_lenders_parses_enum_constants():
    lenders = gen_lenders(FIX.read_text())
    assert lenders["Provident"] == {"id": 3, "name": "Provident Funding"}
    assert lenders["QuickenLoans"]["name"] == "Rocket Pro"
    assert set(lenders) == {"Provident", "QuickenLoans", "Freedom", "PennyMac", "PennyMacCorrespondent", "AAALendings"}


def test_resolve_exact_alias_and_partial():
    idx = LenderIndex(gen_lenders(FIX.read_text()), {"rocket": "QuickenLoans"})
    assert idx.resolve("provident").matches == ["Provident"]
    assert idx.resolve("Provident Funding").kind == "one"
    assert idx.resolve("rocket").matches == ["QuickenLoans"]
    assert idx.resolve("AAA").matches == ["AAALendings"]
    assert idx.resolve("PennyMac").matches == ["PennyMac"]          # exact enum wins over partial
    assert idx.resolve("Penny").kind == "many"
    assert idx.resolve("nobody").kind == "none"
    assert idx.label("AAALendings") == "AAA Lendings"
