"""Einträge aus der lean Twanksta-NVH (``../corpus/parsed/twanksta_dmlex.nvh``).

Geparst wird mit dem vendorten Lexical-Computing-Parser (``_vendor/nvh.py``);
hier steht nur die Feldlogik für die Konsumenten außerhalb des FST-Builds
(Linker, prussian-embeddings, prussian-mcp).  Formen (``inflectedForm``,
``stemOverrides``) werden bewusst nicht gelesen — die liefert der FST.

Ein Eintrag als flaches dict::

    {"id": "be-2", "word": "be", "homograph": 2, "pos": "cconj",
     "gender": "", "paradigm": "", "label": "",
     "desc": "[bhe 17(13)]",
     "translations": {"en": ["and"], "de": ["und"], ...}}

``desc`` ist ``legacy.desc`` als Klartext (Einzeilen-Kodierung dekodiert,
HTML-Tags entfernt, Entities aufgelöst), so wie der Linker sie parst.
"""

from __future__ import annotations

import html
import re
from pathlib import Path

from ._vendor.nvh import nvh

REPO = Path(__file__).resolve().parents[2]
# Kanonische lean NVH aus dem corpus-Repo (dieselbe wie LEAN_NVH im Makefile).
DEFAULT_LEAN_NVH = REPO.parent / "corpus" / "parsed" / "twanksta_dmlex.nvh"

LANGS = ("en", "de", "lt", "lv", "pl", "ru")

_TAG_RE = re.compile(r"<[^>]*>")


def decode_val(s: str) -> str:
    """Einzeilen-Kodierung der NVH-Werte (``\\n``, ``\\r``, ``\\\\``) auflösen.

    Gegenstück zu ``encode_val`` in ``corpus/scripts/twanksta_to_dmlex.py``.
    """
    out, i = [], 0
    while i < len(s):
        c = s[i]
        if c == "\\" and i + 1 < len(s):
            nxt = s[i + 1]
            out.append({"n": "\n", "r": "\r", "\\": "\\"}.get(nxt, nxt))
            i += 2
        else:
            out.append(c)
            i += 1
    return "".join(out)


def plain_desc(value: str) -> str:
    """``legacy.desc`` (verbatim HTML) → Klartext für den Linker."""
    text = html.unescape(_TAG_RE.sub("", decode_val(value)))
    return " ".join(text.split())


def _entry(node: nvh) -> dict:
    entry = {"id": "", "word": node.value, "homograph": 0, "pos": "",
             "gender": "", "paradigm": "", "label": "", "desc": "",
             "translations": {}}
    for child in node.children:
        name = child.name
        if name == "id":
            entry["id"] = child.value
        elif name == "homograph":
            entry["homograph"] = int(child.value)
        elif name in ("pos", "gender", "paradigm", "label"):
            entry[name] = child.value
        elif name == "sense":
            for tr in child.children:
                if tr.name in LANGS and tr.value:
                    entry["translations"].setdefault(tr.name, []).append(tr.value)
        elif name == "legacy":
            for leg in child.children:
                if leg.name == "desc":
                    entry["desc"] = plain_desc(leg.value)
    entry["id"] = entry["id"] or entry["word"]
    return entry


def read_entries(path: str | Path = DEFAULT_LEAN_NVH) -> list[dict]:
    """Alle Einträge der NVH in Dateireihenfolge."""
    with open(path, encoding="utf-8") as f:
        root = nvh.parse_file(f)
    return [_entry(node) for node in root.children if node.name == "entry"]
