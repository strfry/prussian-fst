"""Orthographische Quellvarianten (≈ GiellaLT orthography/spellrelax.regex).

Erzeugt die V-markierten Variantenzeilen, die nur der nachsichtige
Analysator (lenient.fst) akzeptiert: Twanksta-Palatalisierungs-j statt
palatalisiertem Konsonanten + weicher Endung (Mažiulis §§21–25, §122 Fn54)
sowie die Prusaspira-Schreibung elektr- ↔ elaktr- (docs/BACKLOG.md).

Hinweis: in HFST ließen sich diese als generalisierende optionale
Replace-Regeln (`(->)`) formulieren; in pyfoma scheitert das an der
Wildcard-Komposition, daher V-Zeilen in der Morphotaktik (docs/HFST_SPIKE.md).
"""

#: Vokale, die den weichen Endungsvokal-Shift auslösen (→ ja).
_SOFT_VOWELS = set("ieīē")
#: Vokale, die reinen j-Einschub bekommen (→ jV).
_HARD_VOWELS = set("aāuū")
#: Endungen ohne j-Variante (reine Vokale außer 'u', Nom-sg-Endungen).
_NO_J_VARIANT = frozenset({"is", "īs", "i", "ī", "a", "ā", "e", "ē", "ū"})


def jan_variant(suffix: str) -> str | None:
    """Standard-Endung → Twanksta-j-Variante (in→jan, es→jas, u→ju, …).

    Überspringt Endungen, die bereits j enthalten (echte j-Stämme),
    sowie reine Vokalendungen.
    """
    if not suffix or "j" in suffix or suffix in _NO_J_VARIANT:
        return None
    for i, ch in enumerate(suffix):
        if ch in _SOFT_VOWELS | _HARD_VOWELS:
            prefix, rest = suffix[:i], suffix[i:]
            if rest[0] in _SOFT_VOWELS:
                return prefix + "ja" + rest[1:]
            if rest[0] in _HARD_VOWELS:
                return prefix + "j" + rest
            return None
    return None


def sj_variant(suffix: str) -> str | None:
    """Standard-Steigerungsendung → Twanksta-sj-Schreibung (aišas→aisjas).

    Der Komparativ-/Superlativformant palatalisiert das Formant-s vor
    a-anlautender weicher Endung; der Goldstandard backt das als ``š``
    literal ein (data/spec/adj_comparison.json, Template AIS/UIS), Twanksta
    schreibt dieselbe Zelle als ``sj`` (z. B. spārtaisjas, māldaisjas). Diese
    Quellvariante akzeptiert nur der nachsichtige Analysator (lenient.fst).
    """
    if "š" not in suffix:
        return None
    return suffix.replace("š", "sj")


def elaktr_variant(stem: str) -> str | None:
    """Stammvariante elektr- → elaktr- (Prusaspira-Schreibung) oder None."""
    if "elektr" in stem:
        return stem.replace("elektr", "elaktr")
    return None
