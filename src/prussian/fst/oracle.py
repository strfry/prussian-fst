"""Akzent-/Palatalisierungs-Orakel + orthographische Normalisierung.

`resolve_stem` ist die frühere Bake-Logik — im laufenden FST löst die
Regelschicht (phonology.py) Akzent und Palatalisierung über Marker auf;
hier dient sie nur noch als **Orakel** für Validierung (gen_check, Tests)
und für die Doubletten-Prüfung bei der lexd-Emission. Dazu die
Makron-/Diakritika-Normalisierung (strip_macron, fold, case_normalize).
"""

import unicodedata

# Archiphoneme: abgeleitete alternierende Vokale (Akzenttyp aus der
# Deklinationstabelle). Distinkte Symbole (Zirkumflex) statt nackter
# Großbuchstaben A/E/I/O/U, damit literale Großbuchstaben (Eigennamen wie
# Afrika) nicht mehr als Archiphonem missverstanden werden.
ARCHI = "ÂÊÎÔÛ"
ARCHI_SET = set(ARCHI)
#: Makron-Langvokal → Archiphonem (für detect_archiphoneme).
MACRON_TO_ARCHI = {"ā": "Â", "ē": "Ê", "ī": "Î", "ō": "Ô", "ū": "Û"}
#: alte Konvention (Großbuchstabe) → Archiphonem (Gold-Migration).
UPPER_TO_ARCHI = str.maketrans("AEIOU", ARCHI)

# Vokal-Auflösung (Archiphonem → lang/kurz)
LONG = {"Â": "ā", "Ê": "ē", "Î": "ī", "Ô": "ō", "Û": "ū"}
SHORT = {"Â": "a", "Ê": "e", "Î": "i", "Ô": "o", "Û": "u"}

# Palatalisierung (Mažiulis §§21–25)
PALATAL = {"g": "ģ", "k": "ķ", "n": "ņ", "s": "š", "t": "ţ", "z": "ž"}

VOWELS = set("aeiouāēīōūAEIOU") | ARCHI_SET
LONG_VOWELS = set("āēīōū")


def _last_consonant_idx(s: str) -> int | None:
    for i in range(len(s) - 1, -1, -1):
        if s[i] not in VOWELS:
            return i
    return None


def resolve_stem(stamm: str, betont: bool, palatize: bool) -> str:
    """ORAKEL (frühere Bake-Logik): Archiphonem + Palatalisierung auflösen.

    Nur Archiphoneme (``ÂÊÎÔÛ``) werden zu lang/kurz aufgelöst; literale Zeichen
    werden casegefaltet (Großschreibung ist hier keine eigene Eigenschaft —
    s. docs/BACKLOG.md »Großschreibung«; eigener Folgeschritt).
    """
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
