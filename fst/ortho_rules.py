"""Orthographische Variationsregeln fuer den Normalisierungs-FST.

Mažiulis §§21-25 (Palatalisierung), §122 Fn54 (weiche Endung).

Der Normalisierungs-FST mappt Twanksta-Orthographievarianten (explizites
Palatalisierungs-j) auf die Goldstandard-Formen zurueck.

Abbildung ist standard:variant (obere:untere Seite des FST):
  .analyze(variant) → standard
  .generate(standard) → variant
"""

# Vokale die den weichen Endungsvokal-Shift ausloesen (→ ja).
_SOFT_VOWELS = set("ieīē")
# Vokale die reine j-Einschub bekommen (→ jV).
_HARD_VOWELS = set("aāuū")


# Suffixe, die KEINE -j- Variante bekommen.
# Reine Vokale (ausser 'u' = Dat.Sg) und Nom.Sg-Endungen.
_NO_J_VARIANT = frozenset({"is", "īs", "i", "ī", "a", "ā", "e", "ē", "ū"})


def jan_variant(suffix: str) -> str | None:
    """Goldstandard-Suffix → Twanksta -j- Variante.

    Sucht den ersten Vokal im Suffix (kann nach fuehrenden Konsonanten
    kommen, z.B. nin → njan). Wendet dann die passende Regel an:

      - i/e/ī/ē-Anlaut → ja + Rest   (weiche Endung: in→jan, es→jas, ei→jai)
      - a/ā/u/ū-Anlaut → j + ganzes Suffix  (harte Endung: as→jas, u→ju)

    Ueberspringt Suffixe die bereits -j- enthalten (echte j-Staemme)
    sowie reine Vokalsuffixe (Nom.Sg u.ae.).
    """
    if not suffix or "j" in suffix or suffix in _NO_J_VARIANT:
        return None
    for i, ch in enumerate(suffix):
        if ch in _SOFT_VOWELS | _HARD_VOWELS:
            prefix = suffix[:i]
            rest = suffix[i:]
            if rest[0] in _SOFT_VOWELS:
                return prefix + "ja" + rest[1:]
            if rest[0] in _HARD_VOWELS:
                return prefix + "j" + rest
            return None
    return None


def variant_suffix(suffix: str) -> str | None:
    """Haupt-Einstieg: generiere Twanksta-Variante fuer ein Suffix."""
    return jan_variant(suffix)
