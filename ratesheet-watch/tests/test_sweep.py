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
