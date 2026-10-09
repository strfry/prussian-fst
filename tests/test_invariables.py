"""WS3: Invariable aus der lean NVH (LEXICON Invariables) statt gen_lexc-lexc.

Die Wortart steht in der NVH (K3-Automat + ``corpus/ids/invariable_pos.tsv``);
``function_words.lexc`` hält nur noch, was die NVH nicht als Invariable führt.
Die Tests brauchen den Build (``make``) und die lean NVH und überspringen sonst.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "gen"))

import build_analyzer as ba  # noqa: E402
import compress_forms as cf  # noqa: E402

ANALYZER_LEXC = ROOT / "build" / "analyzer.lexc"
FUNCTION_WORDS = ROOT / "lexc" / "function_words.lexc"


def _analyses(path: Path) -> set[str]:
    out: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        m = re.match(r"\s+([^!\s].*?)\s+# ;", line)
        if m:
            out.add(m.group(1).replace("% ", " "))
    return out


@pytest.fixture(scope="module")
def baked() -> set[str]:
    if not ANALYZER_LEXC.exists():
        pytest.skip("build/analyzer.lexc fehlt — erst `make`")
    return _analyses(ANALYZER_LEXC)


@pytest.fixture(scope="module")
def invariables() -> list[cf.Entry]:
    if not ba.LEAN_NVH.exists():
        pytest.skip("lean NVH fehlt")
    return [e for e in cf.read_nvh(ba.LEAN_NVH) if ba.classify_entry(e) == "invar"]


def _lemma(entry: cf.Entry) -> str:
    lemma = entry.lemma.rstrip("!") if entry.pos == "intj" else entry.lemma
    return ba.lexc_esc(lemma).replace("% ", " ")


def test_every_single_word_invariable_is_baked_with_its_tag(baked, invariables):
    missing = [f"{_lemma(e)}{ba.invariable_tags(e)}:{_lemma(e)}" for e in invariables
               if " " not in e.lemma and not ba.form_of(e)]
    missing = [a for a in missing if a not in baked]
    assert not missing, missing[:5]


def test_function_words_do_not_duplicate_nvh_invariables(invariables):
    nvh = {_lemma(e) for e in invariables}
    doubled = sorted({a.split("+", 1)[0] for a in _analyses(FUNCTION_WORDS)} & nvh)
    assert not doubled, doubled


@pytest.mark.parametrize("analysis", [
    "as+Pron+P1+Encl+Sg+Dat:mi", "tū+Pron+P2+Encl+Sg+Acc:ti",   # K5
    "beggi+CS:beggi", "paggan+Po:paggan", "stu+CC:stu",         # Hand-Tabelle
    "Mālis+N+Prop:Mālis", "ērdiw+Interj:ērdiw",
])
def test_invariable_analyses(baked, analysis):
    assert analysis in baked


def test_adverb_with_own_entry_is_its_own_lemma(baked):
    """prūsiskai hat einen eigenen Eintrag (eigene Senses) → eigenes Lemma; die
    Positiv-Form der Adjektivtabelle wird nicht doppelt gebacken, die Grade schon."""
    assert "prūsiskai+Adv:prūsiskai" in baked
    assert "prūsisks+Adv:prūsiskai" not in baked
    assert "prūsisks+Adv+Comp:prūsiskais" in baked


def test_adverb_without_own_entry_stays_with_the_adjective(baked):
    assert "amērikanisks+Adv:amērikaniskai" in baked


def test_form_reference_yields_to_its_target(baked):
    """labban-4 „↑ Labs n (av)“ ist eine Form von labs: keine eigene +Adv-Lesart,
    sonst verdeckt sie die Kongruenzprüfung (Labban wīrs). stu ← stas bleibt, weil
    das Ziel (Hand-lexc) die Oberfläche nicht erzeugt."""
    assert "labban+Adv:labban" not in baked
    assert "labs+A+Neu+Sg+Nom:labban" in baked
    assert "stu+CC:stu" in baked
