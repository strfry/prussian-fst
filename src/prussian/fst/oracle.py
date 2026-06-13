"""Akzent-/Palatalisierungs-Orakel + orthographische Normalisierung.

`resolve_stem` ist die frühere Bake-Logik — im laufenden FST löst die
Regelschicht (phonology.py) Akzent und Palatalisierung über Marker auf;
hier dient sie nur noch als **Orakel** für Validierung (gen_check, Tests)
und für die Doubletten-Prüfung bei der lexd-Emission. Dazu die
Makron-/Diakritika-Normalisierung (strip_macron, fold, case_normalize).
"""

import unicodedata

# Vokal-Auflösung (Archiphonem → lang/kurz)
LONG = {"A": "ā", "E": "ē", "I": "ī", "O": "ō", "U": "ū"}
SHORT = {"A": "a", "E": "e", "I": "i", "O": "o", "U": "u"}

# Palatalisierung (Mažiulis §§21–25)
PALATAL = {"g": "ģ", "k": "ķ", "n": "ņ", "s": "š", "t": "ţ", "z": "ž"}

VOWELS = set("aeiouāēīōūAEIOU")
LONG_VOWELS = set("āēīōū")


def _last_consonant_idx(s: str) -> int | None:
    for i in range(len(s) - 1, -1, -1):
        if s[i] not in VOWELS:
            return i
    return None


def resolve_stem(stamm: str, betont: bool, palatize: bool) -> str:
    """ORAKEL (frühere Bake-Logik): Archiphonem + Palatalisierung auflösen."""
    vmap = LONG if betont else SHORT
    stem = "".join(vmap.get(c, c.lower()) for c in stamm)
    if palatize and stem:
        idx = _last_consonant_idx(stem)
        if idx is not None and stem[idx] in PALATAL:
            stem = stem[:idx] + PALATAL[stem[idx]] + stem[idx + 1:]
    return stem


def strip_macron(s: str) -> str:
    return s.translate(str.maketrans("āēīōūĀĒĪŌŪ", "aeiouAEIOU"))


def fold(s: str) -> str:
    s = strip_macron(s)
    s = unicodedata.normalize("NFD", s)
    return "".join(c for c in s if not unicodedata.combining(c)).lower()


def case_normalize(s: str) -> str:
    return strip_macron(s).lower()
