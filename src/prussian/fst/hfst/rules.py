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
#: auch der Grenzmarker ``·`` (Stamm|Endung, s. spellrelax) getilgt — im
#: Standard-Generator bleibt er folgenlos, im lenient-Build dient er den
#: j-Einschubregeln und wird erst danach getilgt.
CLEANUP = "M -> 0, S -> 0, J -> 0, V -> 0, · -> 0 ;"

#: Phonologie-Kaskade in Anwendungsreihenfolge (Standard-Generator).
PHONOLOGY = [SHORTEN, LENGTHEN, JPAL, CLEANUP]


# ── 2. spellrelax (generalisierende Quellvarianten, nur lenient) ──
#
# Diese Regeln werden auf die fertige *Standardoberfläche* (Ausgabeseite des
# Generators) angewandt und erzeugen dort zusätzlich die Quellschreibungen;
# nach Inversion akzeptiert lenient damit die Varianten und liefert die
# Standardanalyse. Es sind echte Regeln (kein Lexem-Listing) — sie greifen
# auch auf Wortlisten-/Korpusvokabular.

# Twanksta markiert die Palatalisierung/Weichheit am Stamm-Endungs-Übergang
# durch ein explizites ``j``; der Standard löst sie je nach Zelle entweder als
# palatalisierten Konsonanten (ģ ķ ņ š ţ ž) oder als weichen Endungsvokal
# (e/i…) auf. Beide Auflösungen werden generalisierend (regelbasiert, nicht
# pro Lexem) auf das Twanksta-``j`` abgebildet:
#
#   (a) palataler Konsonant → Cj      (Oberflächenregel TWANKSTA_J)
#   (b) weicher Endungsvokal → j…     (Grenzregeln HARD_J/SOFT_J am Marker ·)

#: Konsonant(en), die am Endungsanlaut vor dem ersten Vokal stehen können
#: (Lücke zwischen Grenzmarker ``·`` und erstem Endungsvokal). ``à`` zählt zur
#: Lücke (Sonderform ``àsmu`` → ``àsmju``).
_CONS = ("[ b | c | d | f | g | h | j | k | l | m | n | p | r | s | t | v | w "
         "| z | ŗ | ņ | š | ž | ţ | ķ | ģ | ļ | à ]")

#: (b/hart) ``j``-Einschub vor dem ersten **harten** Endungsvokal (a ā u ū)
#: am Grenzmarker — ``us→jus``, ``āns→jāns``, ``wai→wjai``, ``àsmu→àsmju``.
HARD_J = f"[..] (->) j || · {_CONS}* _ [ a | ā | u | ū ] ;"

#: (b/weich) erster **weicher** Endungsvokal (e ē i ī) am Grenzmarker → ``ja``
#: (das eingeschobene ``j`` steckt im Replacement) — ``in→jan``, ``es→jas``,
#: ``ēi→jai``, ``emans→jamans``, ``īmans→jamans``. Nach HARD_J anzuwenden.
SOFT_J = (f"e (->) j a, ē (->) j a, i (->) j a, ī (->) j a "
          f"|| · {_CONS}* _ ;")

#: (a) palataler Konsonant ↔ Twanksta ``Cj`` (Dat/Gen weicher Stämme:
#: ``kūģu→kūgju``, ``dulžas→dulzjas``). Oberflächenregel (nach CLEANUP).
TWANKSTA_J = (
    "ģ (->) g j, ķ (->) k j, ņ (->) n j, "
    "š (->) s j, ţ (->) t j, ž (->) z j ;"
)

#: elektr- ↔ elaktr- (Prusaspira-Schreibung, docs/BACKLOG.md). Regelhafter
#: Replace (kein Lexem-Listing).
ELAKTR = "e l e k t r (->) e l a k t r ;"

#: Nom sg -as/-us ↔ -s (P25/P32, BACKLOG): der Standard kennt die volle
#: -as/-us-Form; die transparentere -s-Schreibung entsteht durch optionale
#: Tilgung des ``a``/``u`` vor wortfinalem ``s`` nach Konsonant.
AS_US_S = "[ a | u ] (->) 0 || [ b|d|g|k|l|m|n|p|r|t|z ] _ s .#. ;"

#: Lenient-Kaskade auf der **markierten** Unterseite (vor CLEANUP): die
#: Grenz-j-Regeln brauchen den Marker ``·``. Reihenfolge: HARD_J ≺ SOFT_J.
SPELLRELAX_MARKED = [HARD_J, SOFT_J]

#: Lenient-Kaskade auf der **Oberfläche** (nach CLEANUP): rein orthografische
#: Quellvarianten. Reihenfolge unkritisch, alle optional.
SPELLRELAX_SURFACE = [TWANKSTA_J, ELAKTR, AS_US_S]
