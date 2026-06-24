"""HFST-native Orthographie-Faltung (Spiegel von prussian.fst.ortho).

prussian.fst.ortho ist die kanonische, pyfoma-basierte Faltung (Twanksta↔
Prusaspira). Für die HFST-native Komposition mit dem Analysator (lenient =
Faltung ∘ Analysator) werden dieselben Regeln hier als HFST-Regex gespiegelt.

WICHTIG — zwei Geltungsbereiche:

* **Ortho-sicher** (``FOLD_SURFACE``): rein orthographische Normalisierungen,
  die KEINE Flexionszelle vermischen — Diakritika (Makron/Caron/Akzent/
  Rhotik), Lehnwort-c→k, palataler Konsonant ↔ Twanksta-``j`` (gj/sj…→g/s…,
  Mažiulis §§21–25) und elektr~elaktr. Diese gelten auf beliebigen flektierten
  Oberflächen und tragen den nachsichtigen Analysator.

* **Nur Lemma-Ebene** (in ortho.py: themat. ``-as/-us~-s`` und ``-an~-u``):
  verlustbehaftet — sie vermischen Kasus (Gen ``-as`` mit Nom ``-s``, Akk
  ``-an`` mit Dat ``-u``), wenn man sie auf flektierte Formen anwendet. Daher
  NICHT im Analysator, nur fürs Wörterbuch-Matching (ortho.fold).

Das weichvokalische Twanksta-``j`` (``-jas~-es``, ``-jan~-in``) ist eine
**morphologische** Alternation (ja↔e/i), keine Faltung — es kommt aus der
gold-freien Morphologie (Endungen direkt aus beiden Wörterbüchern), nicht
hierher.
"""

#: Längenerhaltende Einzelzeichen-Faltung (Diakritika, Palatale, c→k).
_CHAR = (
    "ā -> a, ē -> e, ī -> i, ō -> o, ū -> u, "
    "š -> s, ž -> z, ź -> z, č -> c, "
    "à -> a, è -> e, ì -> i, ò -> o, ù -> u, "
    "á -> a, é -> e, í -> i, ó -> o, ú -> u, ǹ -> n, "
    "ŕ -> r, ĺ -> l, ľ -> l, "
    "ģ -> g, ķ -> k, ņ -> n, ţ -> t, ļ -> l, ŗ -> r, "
    "c -> k ;"
)

#: Twanksta-Palatalisierungs-j nach Stammkonsonant tilgen (gj/kj/nj/sj/tj/zj).
_PALATAL_J = "j -> 0 || [ g | k | n | s | t | z ] _ ;"

#: Lehnwort-Stammvokal elaktr → elektr.
_ELAKTR = "a -> e || e l _ k t r ;"

#: Ortho-sichere Faltungskaskade für den Analysator (keine Kasus-Vermischung).
FOLD_SURFACE = [_CHAR, _PALATAL_J, _ELAKTR]
