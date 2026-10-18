"""Stufe prusaspira = lenient + Prusaspira-Schreibnorm (norm/palatal, norm/length).

lenient bleibt ohne die Prusaspira-Layer; prusaspira deckt lenient mit ab.
"""

from pathlib import Path

import pytest

from prussian_fst.fst_lookup import flookup_batch

REPO = Path(__file__).resolve().parents[1]
LENIENT = REPO / "build/lenient.hfstol"
PRUSASPIRA = REPO / "build/prusaspira.hfstol"

pytestmark = pytest.mark.skipif(
    not (LENIENT.exists() and PRUSASPIRA.exists()),
    reason="build/lenient.hfstol / build/prusaspira.hfstol fehlen (make)")

# Prusaspira-Form → erwartete Analyse (twanksta-Form in Klammern)
PS_ONLY = [
    ("absōrbiwušas", "absōrbitun+V+PrfPrc+Act+Fem+Sg+Gen"),   # absōrbiwusjas, Sib
    ("Angōlin", "Angōla+N+Prop+Fem+Sg+Acc"),                   # Angōlan, LAN
    ("Pilkalnes", "Pilkalnis+N+Prop+Msc+Sg+Gen"),              # Pilkalnjas, PalA
]


def _analyses(form, path):
    return {"+".join([lemma, *tags]) for lemma, tags in flookup_batch([form], path).get(form, [])}


@pytest.mark.parametrize("form,analysis", PS_ONLY)
def test_prusaspira_layers_only_in_prusaspira(form, analysis):
    assert analysis in _analyses(form, PRUSASPIRA)
    assert analysis not in _analyses(form, LENIENT)


@pytest.mark.parametrize("form", ["mitāwusjan", "labban", "pawīsts"])
def test_prusaspira_covers_lenient(form):
    assert _analyses(form, LENIENT) <= _analyses(form, PRUSASPIRA)
