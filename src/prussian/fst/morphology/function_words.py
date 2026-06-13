"""Geschlossene Wortklassen (Präpositionen, Konjunktionen, Partikeln).

Adverbien werden produktiv aus Adjektiven abgeleitet (s. nominals.py
wordlist_to_entries → adv-Varianten) und daher nicht hier aufgelistet.
"""

import json
from pathlib import Path

POS_TAG = {
    "prepositions": "+Pr",
    "conjunctions": "+Cjn",
    "particles": "+Pcl",
    "interrogatives": "+Pron",
}


def load(data_path: Path) -> list[tuple[str, str]]:
    """(word, pos_tag)-Paare aus function_words.json laden."""
    raw = json.loads(data_path.read_text(encoding="utf-8"))
    result: list[tuple[str, str]] = []
    for category, words in raw.items():
        tag = POS_TAG[category]
        for w in words:
            if "..." in w:
                continue
            result.append((w, tag))
    return result
