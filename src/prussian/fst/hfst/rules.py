"""Regelschicht des HFST-Zweigs als HFST-Regex-Strings (reines Python).

Keine hfst-Importe beim Laden — die Strings werden in build.py mit
``hfst.regex`` kompiliert. Zwei Gruppen:

1. **Phonologie/Akzent** (entspricht pyfomas ``phonology.rule_chain``):
   löst Archiphoneme (Â Ê Î Ô Û) und die Marker M/S/J zur Standard-
   oberfläche auf. Markierte Unterseite → saubere Oberfläche.
   twolc-Äquivalente: docs/ORTHO_RULES.md §4.

2. **spellrelax** (nur lenient): generalisierende optionale Replace, die
   belegte Quellschreibungen auf die Standardoberfläche abbilden, ohne
   sie pro Lexem aufzuzählen. Über-Generierung ist zulässig — der
   Analysator filtert (docs/HFST_SPIKE.md §D).

Konvention: ``Â Ê Î Ô Û`` Archiphoneme (distinkte Symbole statt nackter
Großbuchstaben, damit literale Großbuchstaben/Eigennamen frei sind),
``M`` Mobile-Marker (Stammanfang),
``S`` starke Endung, ``J`` palatalisierende Endung. ``.#.`` = Wortgrenze.
"""

# ── 1. Phonologie / Akzent (markierte Unterseite → Standardoberfläche) ──
#
# Reihenfolge (komponiert in dieser Folge): SHORTEN ≺ LENGTHEN ≺ JPAL ≺ CLEANUP.

#: Akzent-Kürzung: in einem Mobile-Lexem (M) liegt vor einer starken Endung
#: (S) der Akzent auf der Endung — das Stamm-Archiphonem bleibt kurz.
#: twolc: {A}:a <=> M: ?* _ ?* S: ;   (analog E I O U)
SHORTEN = (
    "Â -> a, Ê -> e, Î -> i, Ô -> o, Û -> u "
    "|| M ?* _ ?* S ;"
)

#: Default-Längung: alle übrigen Archiphoneme stehen in akzentuierter Silbe
#: und erscheinen lang (Makron). twolc: {A}:ā ; (Default)
LENGTHEN = "Â -> ā, Ê -> ē, Î -> ī, Ô -> ō, Û -> ū ;"

#: J-Palatalisierung des Stammauslauts vor palatalisierender Endung (J).
#: twolc: g:ģ <=> _ %^JPal: ;  usw. (Mažiulis §§21–25)
JPAL = (
    "g -> ģ, k -> ķ, n -> ņ, s -> š, t -> ţ, z -> ž "
    "|| _ J ;"
)

#: Marker-Tilgung nach allen kontextsensitiven Regeln. Neben M/S/J/V wird
#: auch der (jetzt funktionslose) Grenzmarker ``·`` getilgt: er trug früher die
#: spellrelax-Grenz-j-Regeln; die orthographischen Quellvarianten liegen jetzt
#: zentral in der Faltung (prussian.fst.ortho / hfst.fold), nicht mehr hier.
#: ``·`` wird von lexd_gen noch emittiert und hier folgenlos getilgt
#: (Aufräumen: eigener Folgeschritt).
CLEANUP = "M -> 0, S -> 0, J -> 0, V -> 0, · -> 0 ;"

#: Phonologie-Kaskade in Anwendungsreihenfolge (Standard-Generator).
PHONOLOGY = [SHORTEN, LENGTHEN, JPAL, CLEANUP]

# Die frühere spellrelax-Schicht (TWANKSTA_J/HARD_J/SOFT_J/ELAKTR/AS_US_S) ist
# AUFGELÖST: orthographische Quellvarianten (Diakritika, palatales Twanksta-j,
# elaktr) faltet jetzt die zentrale Faltung (hfst.fold ∘ Analysator, s.
# lexd_build); das weichvokalische Twanksta-j (-jas~-es …) und -as/-us sind
# morphologische Varianten und kommen aus der gold-freien Morphologie (beide
# Wörterbücher), nicht aus generativen Regeln.
