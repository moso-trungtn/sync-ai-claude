from pathlib import Path
import registry

LENDER_TYPE_JAVA = """\
public enum LenderType {
  HomeBridgeWholesale(77L, "HomeBridge Wholesale"), //after
  ADMortgage(12L, "AD Mortgage"),
  Freedom(5L, "Freedom"),
}
"""

RATESHEET_FILES_JAVA = """\
public class RatesheetFiles {
  // ── HomeBridgeWholesale ─────────────────────────────
  public static final String HOMEBRIDGE_0402 = "/ratesheets/homebridge0402.pdf";

  // ── ADMortgage ──────────────────────────────────────
  public static final String AD_MORTGAGE_20260721 = "/ratesheets/ad_mortgage_20260721.pdf";
  public static final String AD_MORTGAGE_NON_QM_20260803 = "/ratesheets/ad_mortgage_nonqm_20260803.pdf";
  public static final String AD_MORTGAGE_20260803 = "/ratesheets/ad_mortgage_20260803.pdf";

  // ── Freedom ─────────────────────────────────────────
  public static final String FREEDOM_ZONE1_0304 = "/ratesheets/freedom_zone1_20260304.xlsx";
  public static final String FREEDOM_ADJUSTMENT_0304 = "/ratesheets/freedom_adjustment_20260304.xlsx";
}
"""

def write(tmp_path, name, content):
    p = tmp_path / name
    p.write_text(content)
    return p

def test_registry_entries(tmp_path):
    lt = write(tmp_path, "LenderType.java", LENDER_TYPE_JAVA)
    rf = write(tmp_path, "RatesheetFiles.java", RATESHEET_FILES_JAVA)
    entries = registry.load_registry(lt, rf)
    keys = {e.key: e for e in entries}

    hb = keys["HomeBridgeWholesale__base"]
    assert hb.ext == ".pdf"
    assert hb.latest_resource == "/ratesheets/homebridge0402.pdf"
    assert hb.gcs_url(123000) == (
        "https://storage.googleapis.com/lender-rate-ratesheet/HomeBridgeWholesale.pdf?v=123000")

    # ADMortgage has base + nonqm variants; latest constant per variant wins
    assert keys["ADMortgage__base"].latest_resource == "/ratesheets/ad_mortgage_20260803.pdf"
    nq = keys["ADMortgage__nonqm"]
    assert nq.latest_resource == "/ratesheets/ad_mortgage_nonqm_20260803.pdf"
    assert nq.gcs_url(123000).endswith("/ADMortgageNonQM.pdf?v=123000")

    # zone variant
    z = keys["Freedom__zone1"]
    assert z.gcs_url(123000).endswith("/Freedom_Zone%201.xlsx?v=123000")

    # adj variant
    adj = keys["Freedom__adj"]
    assert adj.gcs_url(123000).endswith("/Freedom__adjustment_.xlsx?v=123000")

def test_registry_against_real_repo_files():
    lt = Path("/Users/trungthach/IdeaProjects/packs/quote/src/main/java/com/mvu/quote/shared/typekey/LenderType.java")
    rf = Path("/Users/trungthach/IdeaProjects/packs/loan/src/test/java/com/mvu/loan/RatesheetFiles.java")
    entries = registry.load_registry(lt, rf)
    assert len(entries) > 80  # ~178 constants collapse to latest-per-variant
    assert any(e.lender == "HomeBridgeWholesale" for e in entries)
    # section headers with spaces ("AAA Lendings") must still resolve to
    # their no-space enum name (AAALendings) — regression for the silent
    # coverage gap where these lenders produced zero registry entries.
    assert any(e.lender == "AAALendings" for e in entries)


SPACED_SECTION_RATESHEET_FILES_JAVA = """\
public class RatesheetFiles {
  // ── AAA Lendings ────────────────────────────────────
  public static final String AAA_LENDINGS_20260812 = "/ratesheets/aaa_lendings_20260812.pdf";
}
"""

SPACED_SECTION_LENDER_TYPE_JAVA = """\
public enum LenderType {
  AAALendings(99L, "AAA Lendings"),
}
"""

def test_registry_resolves_spaced_section_header_to_enum(tmp_path):
    lt = write(tmp_path, "LenderType.java", SPACED_SECTION_LENDER_TYPE_JAVA)
    rf = write(tmp_path, "RatesheetFiles.java", SPACED_SECTION_RATESHEET_FILES_JAVA)
    entries = registry.load_registry(lt, rf)
    keys = {e.key: e for e in entries}
    assert "AAALendings__base" in keys
    assert keys["AAALendings__base"].latest_resource == "/ratesheets/aaa_lendings_20260812.pdf"


def test_email_only_lenders_declared():
    assert "HomeBridgeWholesale" in registry.EMAIL_ONLY_LENDERS
    assert registry.EMAIL_ONLY_LENDERS <= set(registry.PILOT_LENDERS) | {
        e.lender for e in registry.load_registry(
            Path("/Users/trungthach/IdeaProjects/packs/quote/src/main/java/com/mvu/quote/shared/typekey/LenderType.java"),
            Path("/Users/trungthach/IdeaProjects/packs/loan/src/test/java/com/mvu/loan/RatesheetFiles.java"))}
