import json, subprocess
from pathlib import Path
import fingerprint

FIXTURE = Path("/Users/trungthach/IdeaProjects/packs/loan/src/test/resources/ratesheets/homebridge0402.pdf")
GOLDEN = Path(__file__).parent / "golden" / "homebridge0402.json"

def test_pdf_extract_shape():
    fp = fingerprint.extract(FIXTURE)
    assert fp["format"] == "pdf"
    assert fp["unextractable"] is False
    assert fp["pages"] >= 1
    assert len(fp["banners"]) > 5          # narrative lines exist
    assert fp["banners"] == sorted(fp["banners"])
    # numbers in structure are masked, none survive
    assert not any(ch.isdigit() for line in fp["structure"] for ch in line)

def test_pdf_extract_deterministic_golden():
    fp = fingerprint.extract(FIXTURE)
    if not GOLDEN.exists():                 # first run records the golden
        GOLDEN.parent.mkdir(exist_ok=True)
        GOLDEN.write_text(fingerprint.to_json(fp))
    assert fingerprint.to_json(fp) == GOLDEN.read_text()

def test_masking_rules():
    assert fingerprint._is_numeric_line("6.125  100.250  99.875  1.500")
    assert not fingerprint._is_numeric_line(".375 Price Improvement for loan amounts >$350K")
    assert fingerprint._mask("6.125 100.250") == "# #"
    masked = fingerprint._mask_dates("Loan submissions dated November 17th and after 8/12/2026")
    assert "November" not in masked and "8/12/2026" not in masked and "<DATE>" in masked

def test_mask_dates_timestamps_and_clock_times():
    iso = fingerprint._mask_dates("RS: 2026-08-12 07:52:58.790000")
    assert not any(ch.isdigit() for ch in iso) and "<DATE>" in iso

    clock = fingerprint._mask_dates("Effective Date: <DATE> 09:03:40 AM PDT")
    assert not any(ch.isdigit() for ch in clock)

    clock2 = fingerprint._mask_dates("Rate lock expires 6:00 PM PDT today")
    assert not any(ch.isdigit() for ch in clock2)

    # promo numbers must survive date/time masking untouched
    promo = fingerprint._mask_dates(".375 Price Improvement for loans >$350K")
    assert ".375" in promo and "$350K" in promo

def test_unextractable_flag(tmp_path):
    blank = tmp_path / "blank.pdf"
    blank.write_bytes(b"%PDF-1.4\n%%EOF\n")   # no text layer
    fp = fingerprint.extract(blank)
    assert fp["unextractable"] is True
