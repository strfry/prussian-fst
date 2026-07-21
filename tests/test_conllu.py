"""Tests für den CoNLL-U-Export (fst/scripts/export_conllu.py).

Verifiziert das Unterspezifikations-Prinzip: exportiert werden nur Merkmale,
die alle verbleibenden Lesarten teilen; Rest-Ambiguität landet als Ambig=N
in MISC statt geraten zu werden.
"""

import shutil
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]

from prussian_fst import cg3_pipeline as pipe  # noqa: E402
from prussian_fst import export_conllu as ec  # noqa: E402

FST = REPO / "build/base.hfstol"
GRAMMAR = REPO / "cg3/disambiguator.cg3"

pytestmark = pytest.mark.skipif(
    not (shutil.which("cg-proc") and FST.exists()),
    reason="cg-proc/base.hfstol nicht verfügbar",
)

SENTENCES = [
    "Labban dēinan!",                # komplett eindeutig
    "As pūwa sen laīwan.",           # Prp mit Gov → MISC
    "Wīrai bilāi.",                  # P3, Pres|Pret bleibt → Unterspezifikation
    "Ir kad su tai kur.",            # litauisch → >50% Unk → übersprungen
]


@pytest.fixture(scope="module")
def blocks():
    sents = [{"text": s, "tokens": pipe.tokenize(s), "frequency": 1,
              "sent_id": f"test-{i}"} for i, s in enumerate(SENTENCES)]
    types = {t for s in sents for t in s["tokens"] if t[0].isalpha()}
    analyses = pipe.lookup_types(types, FST)
    cg_input = pipe.emit_cg_stream(sents, analyses)
    cohorts = pipe.parse_cg_stream(pipe.run_cg_proc(cg_input, GRAMMAR))
    result = {}
    i = 0
    for s in sents:
        n = len(s["tokens"]) + (0 if s["tokens"][-1] in pipe.SENT_PUNCT else 1)
        result[s["text"]] = ec.sentence_block(s, cohorts[i:i + n], "test")
        i += n
    return result


def token_cols(block: str, form: str) -> list[str]:
    for line in block.splitlines():
        cols = line.split("\t")
        if len(cols) == 10 and cols[1] == form:
            return cols
    raise AssertionError(f"{form!r} nicht im Block:\n{block}")


def test_unambiguous_full_row(blocks):
    cols = token_cols(blocks["Labban dēinan!"], "dēinan")
    assert cols[2:6] == ["dēinā", "NOUN", "N+Sg+Akk+Fem",
                         "Case=Acc|Gender=Fem|Number=Sing"]
    assert cols[9] == "_"  # kein Ambig-Marker


def test_gov_in_misc(blocks):
    cols = token_cols(blocks["As pūwa sen laīwan."], "sen")
    assert cols[3] == "ADP"
    assert "Gov=Acc" in cols[9]


def test_underspecified_feats(blocks):
    # bilāi: P3 gesichert (Subjekt Wīrai), Pres|Pret unentscheidbar →
    # Mood/Person/Number exportiert, Tense NICHT, Ambig=N in MISC
    cols = token_cols(blocks["Wīrai bilāi."], "bilāi")
    assert cols[3] == "VERB"
    assert cols[4] == "_"  # XPOS nur bei eindeutiger Signatur
    feats = set(cols[5].split("|"))
    assert "Mood=Ind" in feats and "Person=3" in feats
    assert not any(f.startswith("Tense=") for f in feats)
    assert "Ambig=" in cols[9]


def test_foreign_sentence_skipped(blocks):
    assert blocks["Ir kad su tai kur."] is None


def test_metadata_and_column_count(blocks):
    block = blocks["Labban dēinan!"]
    assert block.startswith("# sent_id = test-0\n# text = Labban dēinan!\n"
                            "# source = test")
    for line in block.splitlines():
        if not line.startswith("#"):
            assert len(line.split("\t")) == 10
