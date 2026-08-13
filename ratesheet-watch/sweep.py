"""Daily ratesheet sweep: SHA gate → fingerprint diff → reports + digest."""
from __future__ import annotations
import argparse, hashlib, json, time, urllib.request
from datetime import date
from pathlib import Path

import fingerprint, fpdiff, registry

TOOL_ROOT = Path(__file__).resolve().parent


def http_fetcher(url: str) -> bytes | None:
    for _ in range(2):
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                return r.read()
        except Exception:
            time.sleep(2)
    return None


def _load_json(p: Path, default):
    return json.loads(p.read_text()) if p.exists() else default


def _prev_cached(root: Path, key: str, ext: str, today: str) -> Path | None:
    days = sorted(d.name for d in (root / "cache").glob("*") if d.name < today)
    for day in reversed(days):
        p = root / "cache" / day / f"{key}{ext}"
        if p.exists():
            return p
    return None


def _vision_section(e, local: Path, root: Path, today: str,
                    reports_dir: Path) -> str:
    try:
        import vision
        findings = vision.analyze(_prev_cached(root, e.key, e.ext, today),
                                  local, reports_dir / f"{e.key}-vision")
        lines = ["", "## Vision findings", ""]
        for f in findings:
            lines.append(f"- **{f['kind']}** ({f['materiality']}): "
                         f"{f['summary']} — quote: `{f['quote']}`")
        return "\n".join(lines) + "\n"
    except Exception as ex:                       # vision must never kill sweep
        return f"\n## Vision failed\n\n{ex}\n"


def _report_md(key: str, changes, needs_vision: bool) -> str:
    lines = [f"# Change report — {key}", ""]
    for c in changes:
        lines += [f"## {c.kind} ({c.materiality})", "", c.detail, ""]
    if needs_vision:
        lines += ["## VISION_NEEDED", "",
                  "Text fingerprint silent or images changed — run vision pass.", ""]
    return "\n".join(lines)


def run_sweep(entries, fetcher, root: Path, fingerprints_dir: Path,
              today: str, bootstrap: bool = False) -> dict:
    root = Path(root)
    state_file = root / "state" / "state.json"
    reports_dir = root / "reports" / today
    cache_dir = root / "cache" / today
    for d in (state_file.parent, reports_dir, cache_dir):
        d.mkdir(parents=True, exist_ok=True)
    state = _load_json(state_file, {})
    digest = {"date": today, "bootstrapped": [], "unchanged": [], "changed": [],
              "pending": [], "duplicates": [], "errors": [], "warn": []}
    seen_shas: dict[str, str] = {}
    millis = int(time.time() * 1000)

    for e in entries:
        st = state.setdefault(e.key, {"sha": "", "date": "", "error_count": 0,
                                      "reported_sha": ""})
        data = fetcher(e.gcs_url(millis))
        if data is None:
            st["error_count"] += 1
            digest["errors"].append(e.key)
            if st["error_count"] >= 3:
                digest["warn"].append(
                    f"{e.key}: 3 consecutive failures")
            continue
        st["error_count"] = 0
        sha = hashlib.sha256(data).hexdigest()

        if sha in seen_shas:
            digest["duplicates"].append(e.key)
            continue
        seen_shas[sha] = e.key
        if sha == st["sha"] and not bootstrap:
            if st.get("reported_sha") == sha:
                digest["pending"].append(e.key)
            else:
                digest["unchanged"].append(e.key)
            continue

        local = cache_dir / f"{e.key}{e.ext}"
        local.write_bytes(data)
        fp_new = fingerprint.extract(local)
        fp_file = fingerprints_dir / f"{e.key}.json"

        if bootstrap or not fp_file.exists():
            fp_file.write_text(fingerprint.to_json(fp_new))
            digest["bootstrapped"].append(e.key)
        else:
            fp_old = json.loads(fp_file.read_text())
            changes = fpdiff.diff(fp_old, fp_new)
            vision = fpdiff.needs_vision(fp_old, fp_new, changes)
            if changes or vision:
                if st.get("reported_sha") == sha:
                    digest["pending"].append(e.key)
                else:
                    report = _report_md(e.key, changes, vision)
                    if vision:
                        report += _vision_section(e, local, root, today,
                                                  reports_dir)
                    (reports_dir / f"{e.key}.md").write_text(report)
                    st["reported_sha"] = sha
                    digest["changed"].append(e.key)
            else:
                digest["unchanged"].append(e.key)

        st["sha"], st["date"] = sha, today

    state_file.write_text(json.dumps(state, sort_keys=True, indent=2))
    md = [f"# Sweep digest {today}", ""]
    for bucket in ("changed", "pending", "bootstrapped", "duplicates",
                   "unchanged", "errors"):
        md.append(f"- **{bucket}** ({len(digest[bucket])}): "
                  + (", ".join(digest[bucket]) or "—"))
    for w in digest["warn"]:
        md.append(f"- ⚠️ {w}")
    (reports_dir / "digest.md").write_text("\n".join(md) + "\n")
    return digest


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--lenders", help="comma-separated enum names")
    ap.add_argument("--pilot", action="store_true")
    ap.add_argument("--bootstrap", action="store_true")
    ap.add_argument("--root", default=str(TOOL_ROOT))
    ap.add_argument("--fingerprints", default=
        "/Users/trungthach/IdeaProjects/packs/loan/src/test/resources/fingerprints")
    args = ap.parse_args()

    entries = registry.load_registry(
        "/Users/trungthach/IdeaProjects/packs/quote/src/main/java/com/mvu/quote/shared/typekey/LenderType.java",
        "/Users/trungthach/IdeaProjects/packs/loan/src/test/java/com/mvu/loan/RatesheetFiles.java")
    if args.pilot:
        entries = [e for e in entries if e.lender in registry.PILOT_LENDERS]
    if args.lenders:
        wanted = set(args.lenders.split(","))
        entries = [e for e in entries if e.lender in wanted]

    Path(args.fingerprints).mkdir(parents=True, exist_ok=True)
    digest = run_sweep(entries, http_fetcher, Path(args.root),
                       Path(args.fingerprints), date.today().strftime("%Y%m%d"),
                       bootstrap=args.bootstrap)
    print(json.dumps(digest, indent=2))
