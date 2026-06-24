"""Isolierte Tests für prussian.fst.ortho (Standard-Faltung).

Braucht nur pyfoma — keinen Morphotaktik-Build. Die Paar-Tests sind
hartkodiert; der Coverage-Test überspringt, wenn die externen Dicts fehlen.
"""

import json
from pathlib import Path

import pytest

from prussian.fst.ortho import PR_PATH, TW_PATH, fold

# (Twanksta-Schreibung, Prusaspira/Standard-Schreibung) — müssen auf dieselbe
# Skelettform falten. Deckt jede modellierte Differenzklasse ab.
VARIANT_PAIRS = [
    ("Bangladēšs", "Bangladēšas"),     # themat. Vokal -s ~ -as
    ("Autrīmps", "Autrīmpus"),         # themat. Vokal -s ~ -us
    ("mekānisks", "mekāniskas"),       # -isks ~ -iskas
    ("malnīkiskan", "malnīkisku"),     # -an ~ -u
    ("Ōkeans", "Ōceans"),              # c ~ k
    ("āldī", "aldī"),                  # Macron-Länge
    ("ankstāinan", "ankstaīnan"),      # Diphthong-Macron-Position + -an
    ("bilīsnā", "bilisnā"),            # Macron im Stamm
    ("agristi", "agrìsti"),            # Stress-Akzent
]

# Paare, die NICHT kollabieren dürfen (verschiedene Lexeme).
DISTINCT_PAIRS = [
    ("deiws", "tāns"),
    ("būtwei", "dātwei"),
]


@pytest.mark.parametrize("tw,pr", VARIANT_PAIRS)
def test_variante_faltet_auf_standard(tw, pr):
    assert fold(tw) == fold(pr), f"{tw!r}→{fold(tw)!r} ≠ {pr!r}→{fold(pr)!r}"


@pytest.mark.parametrize("a,b", DISTINCT_PAIRS)
def test_verschiedene_lexeme_kollidieren_nicht(a, b):
    assert fold(a) != fold(b)


def test_fold_deterministisch():
    assert fold("abōrts") == fold("abōrts")
    assert fold("ABŌRTS") == fold("abōrts")  # Groß/klein gefaltet


def test_dict_coverage():
    """Faltung paart >1000 der nicht-exakten Twanksta-Lemmata mit Prusaspira."""
    if not (TW_PATH.exists() and PR_PATH.exists()):
        pytest.skip("externe Dicts fehlen — s. README data/external")
    tw = {e["word"] for e in json.loads(TW_PATH.read_text(encoding="utf-8"))}
    pr = {e["word"] for e in json.loads(PR_PATH.read_text(encoding="utf-8"))}
    pr_skel = {fold(w) for w in pr}
    paired = sum(1 for w in (tw - pr) if fold(w) in pr_skel)
    assert paired > 1000, f"nur {paired} gepaart"
