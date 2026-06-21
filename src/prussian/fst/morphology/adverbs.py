"""Adverbien als geschlossene Lexemklasse.

Altpreußische Adverbien sind überwiegend eigenständig/lexikalisiert: nur ~25–30 %
sind regelmäßig aus einem Adjektiv ableitbar (`-ai`/`-i`/`-u`), die Mehrheit sind
Primäradverbien ohne zugehöriges Adjektiv (Untersuchung 2026-06-14). Wir führen
daher ALLE Adverb-Lemmata aus dem Wörterbuch (POS `av`) als invariante +Adv-Lexeme
— die produktive Ableitung aus dem Adjektivsystem wird bewusst NICHT modelliert.

Quelle: data/external/twanksta_entries.json, Einträge mit führendem `av`/`AV`
im `desc`-Feld. Gefiltert auf standardorthografische Einwort-Lemmata; verworfen
werden Mehrwort-Adverbien (Leerzeichen), Rausch (»!«) und nicht-standardkonforme
Schreibvarianten (Gravis ì, ń).
"""

import json
import re
from pathlib import Path

from prussian.fst.tags import ADV_POS_TAG

_POS = re.compile(r"^([A-Za-z]+)")
# Standardorthografie: Kleinbuchstaben + Makronvokale + š/ž (s. Gold-Templates
# wie `aišas`) + Apostroph. Mehrwort- und Sonderzeichen-Lemmata fallen raus.
_STD = re.compile(r"^[a-zāēīōūšž']+$")


def _is_adverb(entry: dict) -> bool:
    m = _POS.match(entry.get("desc", ""))
    return bool(m) and m.group(1).lower() == "av"


def load(dict_path: Path) -> list[tuple[str, str]]:
    """(Wort, +Adv)-Paare aus den `av`-Lemmata des Wörterbuchs (dedupliziert)."""
    raw = json.loads(dict_path.read_text(encoding="utf-8"))
    words = sorted({
        e["word"] for e in raw
        if _is_adverb(e) and _STD.fullmatch(e["word"])
    })
    return [(w, ADV_POS_TAG) for w in words]
