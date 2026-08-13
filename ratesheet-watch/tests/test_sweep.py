import json
from pathlib import Path
import registry, sweep, fingerprint

def make_entry(lender="TestLender", variant="base", ext=".pdf"):
    return registry.Entry(lender, variant, ext, f"/ratesheets/{lender.lower()}.pdf")

PDF_V1 = b"%PDF-1.4 fake-v1"
PDF_V2 = b"%PDF-1.4 fake-v2"

def fake_fp(banners):
    return {"version": 1, "format": "pdf", "unextractable": False,
            "banners": sorted(banners), "structure": ["# # #"],
            "images": [], "pages": 1}

def test_sweep_lifecycle(tmp_path, monkeypatch):
    root = tmp_path / "run"; fps = tmp_path / "fps"; fps.mkdir()
    entry = make_entry()
    fetch_result = {"bytes": PDF_V1}
    fetcher = lambda url: fetch_result["bytes"]

    # extraction is faked: content bytes decide the fingerprint
    def fake_extract(path):
        data = Path(path).read_bytes()
        return fake_fp(["OLD BANNER"] if data == PDF_V1 else
                       ["OLD BANNER", "NEW .375 PROMO >$350K"])
    monkeypatch.setattr(sweep.fingerprint, "extract", fake_extract)

    # Run 1: no committed fingerprint → bootstrap, no report
    digest = sweep.run_sweep([entry], fetcher, root, fps, today="20260813")
    assert digest["bootstrapped"] == ["TestLender__base"]
    assert (fps / "TestLender__base.json").exists()
    assert not list((root / "reports" / "20260813").glob("TestLender*"))

    # Run 2: same bytes → unchanged
    digest = sweep.run_sweep([entry], fetcher, root, fps, today="20260814")
    assert digest["unchanged"] == ["TestLender__base"]

    # Run 3: new bytes with a new banner → report written
    fetch_result["bytes"] = PDF_V2
    digest = sweep.run_sweep([entry], fetcher, root, fps, today="20260815")
    assert digest["changed"] == ["TestLender__base"]
    report = (root / "reports" / "20260815" / "TestLender__base.md").read_text()
    assert "PROMO_NEW" in report and ".375 PROMO" in report

    # Run 4: same new bytes again, not yet handled → pending, no duplicate report
    digest = sweep.run_sweep([entry], fetcher, root, fps, today="20260816")
    assert digest["pending"] == ["TestLender__base"]
    assert not (root / "reports" / "20260816" / "TestLender__base.md").exists()

def test_shared_sha_dedupe(tmp_path):
    e1, e2 = make_entry("LenderA"), make_entry("LenderB")
    fps = tmp_path / "fps"; fps.mkdir()
    digest = sweep.run_sweep([e1, e2], lambda url: PDF_V1,
                             tmp_path / "run", fps, today="20260813")
    assert digest["bootstrapped"] == ["LenderA__base"]
    assert digest["duplicates"] == ["LenderB__base"]

def test_vision_failure_does_not_kill_sweep(tmp_path, monkeypatch):
    # identical fingerprints on changed bytes → needs_vision → vision raises
    entry = make_entry()
    fps = tmp_path / "fps"; fps.mkdir()
    monkeypatch.setattr(sweep.fingerprint, "extract",
                        lambda p: fake_fp(["SAME"]))
    sweep.run_sweep([entry], lambda u: PDF_V1, tmp_path / "r", fps, "20260813")
    import vision
    monkeypatch.setattr(vision, "analyze",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    digest = sweep.run_sweep([entry], lambda u: PDF_V2, tmp_path / "r", fps, "20260814")
    assert digest["changed"] == ["TestLender__base"]
    report = (tmp_path / "r" / "reports" / "20260814" / "TestLender__base.md").read_text()
    assert "Vision failed" in report

def test_looks_like_error_page():
    assert sweep._looks_like_error_page(b"") is True
    assert sweep._looks_like_error_page(b"<html><body>Redirect Error</body></html>") is True
    assert sweep._looks_like_error_page(b"  \n<?xml version=\"1.0\"?><Error/>") is True
    assert sweep._looks_like_error_page(b"%PDF-1.7\r\n6 0 obj") is False
    assert sweep._looks_like_error_page(b"PK\x03\x04 fake-xlsx-bytes") is False

def test_bad_entry_does_not_kill_sweep(tmp_path, monkeypatch):
    # Two entries with distinct bytes so they aren't deduped by sha.
    good, bad = make_entry("GoodLender"), make_entry("BadLender")
    fps = tmp_path / "fps"; fps.mkdir()
    data = {"GoodLender": b"%PDF-1.4 good", "BadLender": b"%PDF-1.4 bad"}

    def fetcher(url):
        return data["GoodLender"] if "GoodLender" in url else data["BadLender"]

    def fake_extract(path):
        if "BadLender" in str(path):
            raise RuntimeError("BadZipFile: truncated xlsx")
        return fake_fp(["GOOD BANNER"])
    monkeypatch.setattr(sweep.fingerprint, "extract", fake_extract)

    digest = sweep.run_sweep([good, bad], fetcher, tmp_path / "run", fps,
                             today="20260813")

    assert digest["bootstrapped"] == ["GoodLender__base"]
    assert digest["errors"] == ["BadLender__base"]
    assert any("BadLender__base: processing failed" in w for w in digest["warn"])
    assert (fps / "GoodLender__base.json").exists()
    assert not (fps / "BadLender__base.json").exists()
    # state.json and digest.md must still be written despite the failure
    assert (tmp_path / "run" / "state" / "state.json").exists()
    assert (tmp_path / "run" / "reports" / "20260813" / "digest.md").exists()

def test_vision_quiet_writes_no_report(tmp_path, monkeypatch):
    # identical fingerprints on changed bytes → needs_vision → vision finds nothing
    entry = make_entry()
    fps = tmp_path / "fps"; fps.mkdir()
    monkeypatch.setattr(sweep.fingerprint, "extract",
                        lambda p: fake_fp(["SAME"]))
    sweep.run_sweep([entry], lambda u: PDF_V1, tmp_path / "r", fps, "20260813")
    import vision
    monkeypatch.setattr(vision, "analyze", lambda *a, **k: [])
    digest = sweep.run_sweep([entry], lambda u: PDF_V2, tmp_path / "r", fps, "20260814")
    assert digest["unchanged"] == ["TestLender__base"]
    assert not (tmp_path / "r" / "reports" / "20260814" / "TestLender__base.md").exists()
    state = json.loads((tmp_path / "r" / "state" / "state.json").read_text())
    assert state["TestLender__base"]["reported_sha"] == ""

def test_vision_low_materiality_only_writes_no_report(tmp_path, monkeypatch):
    entry = make_entry()
    fps = tmp_path / "fps"; fps.mkdir()
    monkeypatch.setattr(sweep.fingerprint, "extract",
                        lambda p: fake_fp(["SAME"]))
    sweep.run_sweep([entry], lambda u: PDF_V1, tmp_path / "r", fps, "20260813")
    import vision
    monkeypatch.setattr(vision, "analyze", lambda *a, **k: [
        {"kind": "LAYOUT", "summary": "minor spacing tweak",
         "quote": "", "materiality": "low"}])
    digest = sweep.run_sweep([entry], lambda u: PDF_V2, tmp_path / "r", fps, "20260814")
    assert digest["unchanged"] == ["TestLender__base"]
    assert not (tmp_path / "r" / "reports" / "20260814" / "TestLender__base.md").exists()

def test_adhoc_digest_name_does_not_clobber(tmp_path):
    entry = make_entry()
    fps = tmp_path / "fps"; fps.mkdir()
    sweep.run_sweep([entry], lambda u: PDF_V1, tmp_path / "r", fps, "20260813")
    sweep.run_sweep([entry], lambda u: PDF_V1, tmp_path / "r", fps, "20260813",
                    digest_name="digest-adhoc.md")
    reports_dir = tmp_path / "r" / "reports" / "20260813"
    assert (reports_dir / "digest.md").exists()
    assert (reports_dir / "digest-adhoc.md").exists()

def test_fetch_failure_counts(tmp_path):
    fps = tmp_path / "fps"; fps.mkdir()
    entry = make_entry()
    for day in ("20260813", "20260814", "20260815"):
        digest = sweep.run_sweep([entry], lambda url: None,
                                 tmp_path / "run", fps, today=day)
    assert digest["errors"] == ["TestLender__base"]
    state = json.loads((tmp_path / "run" / "state" / "state.json").read_text())
    assert state["TestLender__base"]["error_count"] == 3
    digest_md = (tmp_path / "run" / "reports" / "20260815" / "digest.md").read_text()
    assert "3 consecutive failures" in digest_md
