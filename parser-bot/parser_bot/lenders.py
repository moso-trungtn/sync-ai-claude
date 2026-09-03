"""LenderType enum → {enum: {id, name}} and fuzzy resolution of chat text to one enum constant."""
from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml

_CONST = re.compile(r'^\s*([A-Z][A-Za-z0-9]*)\((\d+)L?,\s*"([^"]+)"', re.M)


def gen_lenders(java_text: str) -> dict[str, dict]:
    return {m.group(1): {"id": int(m.group(2)), "name": m.group(3)} for m in _CONST.finditer(java_text)}


@dataclass
class Resolution:
    kind: str            # "one" | "none" | "many"
    matches: list[str]


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


class LenderIndex:
    def __init__(self, lenders: dict[str, dict], aliases: dict[str, str] | None = None):
        self.lenders = lenders
        self.aliases = {_norm(k): v for k, v in (aliases or {}).items()}

    def label(self, enum: str) -> str:
        return self.lenders.get(enum, {}).get("name", enum)

    def resolve(self, text: str) -> Resolution:
        q = _norm(text)
        if not q:
            return Resolution("none", [])
        if q in self.aliases and self.aliases[q] in self.lenders:
            return Resolution("one", [self.aliases[q]])
        for enum, info in self.lenders.items():
            if q == _norm(enum) or q == _norm(info["name"]):
                return Resolution("one", [enum])
        words = q.split()
        partial = [e for e, i in self.lenders.items()
                   if all(w in _norm(e) or w in _norm(i["name"]) for w in words)]
        if len(partial) == 1:
            return Resolution("one", partial)
        return Resolution("many" if partial else "none", sorted(partial))


def load_index(lenders_json: str, aliases_yaml: str) -> LenderIndex:
    lenders = json.loads(Path(lenders_json).read_text(encoding="utf-8"))
    aliases = {}
    if Path(aliases_yaml).exists():
        aliases = yaml.safe_load(Path(aliases_yaml).read_text(encoding="utf-8")) or {}
    return LenderIndex(lenders, aliases)


if __name__ == "__main__":  # python -m parser_bot.lenders <LenderType.java> <out.json>
    src, out = sys.argv[1], sys.argv[2]
    data = gen_lenders(Path(src).read_text(encoding="utf-8"))
    Path(out).write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    print(f"{len(data)} lenders -> {out}")
