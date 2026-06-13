"""Morphophonologische Regelschicht (pyfoma-Rewrite-Regeln) [≈ phonology.twolc].

Ersetzt die frühere (nie kompilierte) phonology.twolc. Die Morphotaktik
(morphology/lexd.py) emittiert auf der Unterseite markierte Formen:

    Marker  Position           Bedeutung
    ------  -----------------  -------------------------------------------
    M       vor dem Stamm      Lexem ist Mobile (Akzentklasse, AKZENT.md)
    S       vor der Endung     Endung ist stark (zieht den Akzent)
    J       vor der Endung     Endung palatalisiert den Stammauslaut

    A E I O U  im Stamm        Archiphonem: Vokal alterniert lang/kurz

Beispiel P35 mīstan (Mobile):
    MmIstan   → mīstan   (schwache Endung: Akzent auf Stamm, I→ī)
    MmIstSāi  → mistāi   (starke Endung: Akzent auf Endung, I→i)
Beispiel P40 kūgis, Gen sg (Palatalisierung):
    kūgJas    → kūģas

Regelreihenfolge: SHORTEN ≺ LENGTHEN ≺ JPAL ≺ CLEANUP.
Die twolc-Äquivalente sind in docs/ORTHO_RULES.md §4 dokumentiert.
"""

from pyfoma import FST

#: Akzentauflösung, Kürzung (Rinkevičius 2009: »Akzent = erstes starkes
#: Morphem«). In einem Mobile-Lexem (M) vor starker Endung (S) liegt der
#: Akzent auf der Endung — das Stamm-Archiphonem bleibt kurz.
#: twolc: {A}:a <=> M: ?* _ ?* S: ;   (analog E I O U)
R_SHORTEN = FST.re(
    "$^rewrite((A:a|E:e|I:i|O:o|U:u) / 'M' .* _ .* 'S')"
)

#: Akzentauflösung, Default-Längung. Alle übrigen Archiphoneme stehen in
#: akzentuierter Silbe (Baryton-Stamm oder Mobile vor schwacher Endung)
#: und erscheinen lang (Makron = langer betonter Vokal, TABVLA-Norm).
#: twolc: {A}:ā ;  (Default)
R_LENGTHEN = FST.re(
    "$^rewrite(A:'ā'|E:'ē'|I:'ī'|O:'ō'|U:'ū')"
)

#: J-Palatalisierung des Stammauslauts vor palatalisierender Endung
#: (Mažiulis §§21–25: Gen/Dat weicher Stämme, -un-Infinitiv).
#: twolc: g:ģ <=> _ %^JPal: ;  usw.
R_JPAL = FST.re(
    "$^rewrite((g:'ģ'|k:'ķ'|n:'ņ'|s:'š'|t:'ţ'|z:'ž') / _ 'J')"
)

#: Marker-Tilgung (nach allen kontextsensitiven Regeln). V markiert
#: orthographische Quellvarianten (spellrelax.py: Twanksta-j-Endungen,
#: elaktr-Stämme) und kommt nur im nachsichtigen Analysator vor — der
#: Standard-Build streicht die V-Zeilen bereits im lexd-Quelltext.
#: Weitere Variantenphänomene gehören ebenfalls als V-Zeilen in die
#: Morphotaktik, nicht als nachkomponierte Kleinst-Regeln (pyfomas
#: Wildcard-Arcs verhalten sich in verschachtelter Komposition nicht
#: verlässlich, wenn die Alphabete stark differieren; vgl. docs/HFST_SPIKE.md).
R_CLEANUP = FST.re("$^rewrite(('M'|'S'|'J'|'V'):'')")


def rule_chain() -> FST:
    """Alle Regeln zu einem Transducer komponiert (markiert → Oberfläche)."""
    return R_SHORTEN.compose(R_LENGTHEN).compose(R_JPAL).compose(R_CLEANUP)
