"""Vision fallback: render changed files and ask Claude for a change list."""
from __future__ import annotations
import json, re, subprocess
from pathlib import Path

import fingerprint

PROMPT = """You compare mortgage lender ratesheet images to find MATERIAL changes.
Old version images (may be absent): {old}
New version images: {new}
Report ONLY: new/changed/expired promotions or specials, added/removed
programs, structural changes to adjustment tables. IGNORE ordinary daily
rate/price number movements.
Reply with ONLY a JSON array (no prose): [{{"kind":
"PROMO_NEW|PROMO_CHANGED|PROMO_EXPIRED|PROGRAM|STRUCTURE|LAYOUT",
"summary": "...", "quote": "exact text visible in the image",
"materiality": "high|medium|low"}}]. Empty array if nothing material."""

VERIFY_PROMPT = 'Is the exact text "{quote}" visible in these images? Answer only YES or NO.'


def _claude_runner(prompt: str, image_paths: list[Path]) -> str:
    files = "\n".join(str(p) for p in image_paths)
    full = f"{prompt}\n\nImage files to read:\n{files}"
    r = subprocess.run(["claude", "-p", full, "--max-turns", "8"],
                       capture_output=True, text=True, timeout=600)
    return r.stdout


def render(file: Path, outdir: Path) -> list[Path]:
    outdir.mkdir(parents=True, exist_ok=True)
    suffix = file.suffix.lower()
    if suffix == ".pdf":
        subprocess.run(["pdftoppm", "-png", "-r", "100", str(file),
                        str(outdir / file.stem)], capture_output=True)
        return sorted(outdir.glob(f"{file.stem}*.png"))
    if suffix in (".xlsx", ".xlsm"):
        out = []
        for name, data in fingerprint.embedded_images(file):
            p = outdir / Path(name).name
            p.write_bytes(data)
            out.append(p)
        return out
    return []


def _parse_json_array(text: str) -> list[dict]:
    m = re.search(r"\[.*\]", text, re.S)
    return json.loads(m.group(0)) if m else []


def analyze(old_file, new_file: Path, workdir: Path, runner=None) -> list[dict]:
    runner = runner or _claude_runner
    new_imgs = render(Path(new_file), Path(workdir) / "new")
    if not new_imgs:
        return [{"kind": "MANUAL_REVIEW",
                 "summary": "file could not be rendered for vision",
                 "quote": "", "materiality": "high"}]
    old_imgs = render(Path(old_file), Path(workdir) / "old") if old_file else []
    prompt = PROMPT.format(
        old=", ".join(str(p) for p in old_imgs) or "(none)",
        new=", ".join(str(p) for p in new_imgs))
    changes = _parse_json_array(runner(prompt, old_imgs + new_imgs))

    out = []
    for c in changes:
        c = {"kind": c.get("kind", "MANUAL_REVIEW"),
             "summary": c.get("summary", ""), "quote": c.get("quote", ""),
             "materiality": c.get("materiality", "medium")}
        if c["kind"].startswith("PROMO"):
            # An expired promo's quote is only visible in the OLD images —
            # verifying it against new_imgs always fails and downgrades a
            # correct finding to MANUAL_REVIEW. Verify against whichever
            # image set the quote should actually appear in.
            verify_imgs = old_imgs if c["kind"] == "PROMO_EXPIRED" and old_imgs else new_imgs
            verdict = "" if not c["quote"] else runner(
                VERIFY_PROMPT.format(quote=c["quote"]), verify_imgs)
            if "YES" not in verdict.upper():
                c["kind"] = "MANUAL_REVIEW"
        out.append(c)
    return out
