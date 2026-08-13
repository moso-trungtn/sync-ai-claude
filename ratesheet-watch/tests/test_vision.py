import json
from pathlib import Path
import vision

def test_render_xlsx_extracts_embedded_images(tmp_path):
    import openpyxl, zipfile
    src = tmp_path / "s.xlsx"
    openpyxl.Workbook().save(src)
    with zipfile.ZipFile(src, "a") as z:
        z.writestr("xl/media/image1.png", b"\x89PNGx")
    out = vision.render(src, tmp_path / "imgs")
    assert len(out) == 1 and out[0].read_bytes() == b"\x89PNGx"

def test_analyze_parses_and_guards_quotes(tmp_path):
    calls = []
    def fake_runner(prompt, images):
        calls.append(prompt)
        if prompt.startswith("Is the exact text"):
            return "NO" if "HALLUCINATED" in prompt else "YES"
        return json.dumps([
            {"kind": "PROMO_NEW", "summary": "new 350K promo",
             "quote": ".375 Price Improvement", "materiality": "high"},
            {"kind": "PROMO_NEW", "summary": "fake",
             "quote": "HALLUCINATED TEXT", "materiality": "high"},
        ])
    new = tmp_path / "n.pdf"; new.write_bytes(b"%PDF-1.4")
    # monkeypatch render to avoid real pdftoppm on a fake pdf
    vision_render, vision.render = vision.render, lambda f, o: [tmp_path / "n.pdf"]
    try:
        out = vision.analyze(None, new, tmp_path, runner=fake_runner)
    finally:
        vision.render = vision_render
    kinds = [c["kind"] for c in out]
    assert kinds == ["PROMO_NEW", "MANUAL_REVIEW"]

def test_analyze_no_images_returns_manual_review(tmp_path):
    new = tmp_path / "n.xls"; new.write_bytes(b"\xd0\xcf\x11\xe0")
    out = vision.analyze(None, new, tmp_path, runner=lambda p, i: "[]")
    assert out == [{"kind": "MANUAL_REVIEW",
                    "summary": "file could not be rendered for vision",
                    "quote": "", "materiality": "high"}]
