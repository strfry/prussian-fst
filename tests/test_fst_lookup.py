"""fst_lookup: pyhfst darf bei unbekannten Zeichen nicht das Präfix analysieren."""

from pathlib import Path

import pytest

from prussian_fst.fst_lookup import flookup_batch

REPO = Path(__file__).resolve().parents[1]
BASE = REPO / "build/base.hfstol"

pytestmark = pytest.mark.skipif(not BASE.exists(), reason="build/base.hfstol fehlt (make)")


def test_known_form_is_analysed():
    assert flookup_batch(["labban"], BASE)["labban"]


@pytest.mark.parametrize("form", ["labbanx", "labbanß", "labbanț", "texts"])
def test_unknown_char_gives_no_analysis(form):
    # pyhfst 1.4.0 hielte das Zeichen für das Eingabeende → Analysen von „labban“
    assert form not in flookup_batch([form], BASE)
