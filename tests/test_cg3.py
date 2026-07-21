"""Golden-Tests für den CG3-Disambiguator und die Dependenzschicht.

Primäre Verifikationslinie: Nominalgruppen aus tests/fixtures/cg3_golden.tsv
werden korrekt disambiguiert — die erwartete Lesartenmenge bleibt EXAKT übrig
(richtige Lesart überlebt, falsche werden entfernt).  Zweite Linie:
Kopf/Label-Paare aus tests/fixtures/cg3_dep_golden.tsv (SETPARENT-Baum aus
disambiguator.cg3 SECTION 8 + ADDRELATION-Labels aus dependency.cg3).
"""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]

from prussian_fst import cg3_pipeline as pipe  # noqa: E402
from prussian_fst.export_conllu import resolve_deps  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures/cg3_golden.tsv"
DEP_FIXTURES = Path(__file__).parent / "fixtures/cg3_dep_golden.tsv"
VAL_FIXTURES = Path(__file__).parent / "fixtures/cg3_validator_golden.tsv"
GRAMMAR = REPO / "cg3/disambiguator.cg3"
DEP_GRAMMAR = REPO / "cg3/dependency.cg3"
VAL_GRAMMAR = REPO / "cg3/validator.cg3"
FST = REPO / "build/base.hfstol"

pytestmark = pytest.mark.skipif(
    not (shutil.which("cg-proc") and FST.exists()),
    reason="cg-proc/base.hfstol nicht verfügbar",
)


def load_golden() -> tuple[list[str], list[tuple[str, str, set[str]]]]:
    """(Satzliste, [(Satz, Token, erwartete Lesartenmenge)])."""
    sentences: list[str] = []
    cases = []
    for line in FIXTURES.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        sent, token, expected = line.split("\t")
        if sent not in sentences:
            sentences.append(sent)
        cases.append((sent, token, set(expected.split("|"))))
    return sentences, cases


def load_dep_golden() -> tuple[list[str], list[tuple[str, str, str, str]]]:
    """(Satzliste, [(Satz, Token, Kopf-Token|'0', DEPREL)])."""
    sentences: list[str] = []
    cases = []
    for line in DEP_FIXTURES.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        sent, token, head, deprel = line.split("\t")
        if sent not in sentences:
            sentences.append(sent)
        cases.append((sent, token, head, deprel))
    return sentences, cases


def disambiguate_sentences(sentences: list[str]) -> dict[str, list[dict]]:
    """Alle Golden-Sätze in EINEM Lookup-/vislcg3-Lauf (Disambiguierung +
    Dependenz-Labels); Satz → Cohorts."""
    sent_objs = [{"text": s, "tokens": pipe.tokenize(s), "frequency": 1}
                 for s in sentences]
    types = {t for so in sent_objs for t in so["tokens"] if t[0].isalpha()}
    analyses = pipe.lookup_types(types, FST)
    cg_input = pipe.emit_cg_stream(sent_objs, analyses)
    output = pipe.run_cg_proc(cg_input, GRAMMAR)
    output = pipe.run_cg_proc(output, DEP_GRAMMAR)
    cohorts = pipe.parse_cg_stream(output)

    result: dict[str, list[dict]] = {}
    i = 0
    for so in sent_objs:
        n = len(so["tokens"])
        if so["tokens"][-1] not in pipe.SENT_PUNCT:
            n += 1  # erzwungener Satzend-Delimiter
        result[so["text"]] = cohorts[i:i + n]
        i += n
    assert i == len(cohorts)
    return result


@pytest.fixture(scope="module")
def disambiguated():
    sentences, _ = load_golden()
    dep_sentences, _ = load_dep_golden()
    all_sents = sentences + [s for s in dep_sentences if s not in sentences]
    return disambiguate_sentences(all_sents)


def _readings(cohorts: list[dict], token: str) -> set[str]:
    for c in cohorts:
        if c["form"] == token:
            return {"+".join([r["lemma"]] + r["tags"]) for r in c["readings"]}
    raise AssertionError(f"Token {token!r} nicht im Output gefunden")


_, CASES = load_golden()


@pytest.mark.parametrize("sent,token,expected", CASES,
                         ids=[f"{s[:20]}…{t}" for s, t, _ in CASES])
def test_golden(disambiguated, sent, token, expected):
    got = _readings(disambiguated[sent], token)
    # Golden-Lesart(en) müssen überleben UND nichts Falsches übrig bleiben
    assert got == expected, (
        f"{sent!r} / {token}: erwartet {sorted(expected)}, erhalten {sorted(got)}")


_, DEP_CASES = load_dep_golden()


@pytest.mark.parametrize("sent,token,head,deprel", DEP_CASES,
                         ids=[f"{s[:20]}…{t}" for s, t, _, _ in DEP_CASES])
def test_dep_golden(disambiguated, sent, token, head, deprel):
    cohorts = disambiguated[sent]
    deps = resolve_deps(cohorts)
    forms = [c["form"] for c in cohorts]
    idx = forms.index(token)
    assert deps[idx] is not None, f"{sent!r} / {token}: keine Dependenz-Info"
    got_head, got_label = deps[idx]
    got_head_form = "0" if got_head == 0 else forms[got_head - 1]
    assert (got_head_form, got_label) == (head, deprel), (
        f"{sent!r} / {token}: erwartet {head}:{deprel}, "
        f"erhalten {got_head_form}:{got_label}")


@pytest.mark.parametrize("grammar", [GRAMMAR, DEP_GRAMMAR, VAL_GRAMMAR],
                         ids=["disambiguator", "dependency", "validator"])
def test_grammar_syntax(grammar):
    r = subprocess.run(["cg-comp", str(grammar), "/dev/null"],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


# ── Validator (Phase 3): &-Fehler-Tags auf korrumpierten Sätzen ──

def load_validator_golden() -> tuple[list[str], list[tuple[str, str, set[str]]]]:
    """(Satzliste, [(Satz, Token, erwartete &-Tag-Menge; leer = fehlerfrei)])."""
    sentences: list[str] = []
    cases = []
    for line in VAL_FIXTURES.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        sent, token, expected = line.split("\t")
        if sent not in sentences:
            sentences.append(sent)
        tags = set() if expected == "-" else set(expected.split("|"))
        cases.append((sent, token, tags))
    return sentences, cases


def validate_sentences(sentences: list[str]) -> dict[str, list[dict]]:
    """Alle Validator-Sätze in EINEM Lauf durch die drei Grammatik-
    Pässe (Disambiguierung + Dependenz + Validator); Satz → Cohorts."""
    sent_objs = [{"text": s, "tokens": pipe.tokenize(s), "frequency": 1}
                 for s in sentences]
    types = {t for so in sent_objs for t in so["tokens"] if t[0].isalpha()}
    analyses = pipe.lookup_types(types, FST)
    cg_input = pipe.emit_cg_stream(sent_objs, analyses)
    output = pipe.run_cg_proc(cg_input, GRAMMAR)
    output = pipe.run_cg_proc(output, DEP_GRAMMAR)
    output = pipe.run_cg_proc(output, VAL_GRAMMAR)
    cohorts = pipe.parse_cg_stream(output)

    result: dict[str, list[dict]] = {}
    i = 0
    for so in sent_objs:
        n = len(so["tokens"])
        if so["tokens"][-1] not in pipe.SENT_PUNCT:
            n += 1
        result[so["text"]] = cohorts[i:i + n]
        i += n
    assert i == len(cohorts)
    return result


@pytest.fixture(scope="module")
def validated():
    sentences, _ = load_validator_golden()
    return validate_sentences(sentences)


_, VAL_CASES = load_validator_golden()


@pytest.mark.parametrize("sent,token,expected", VAL_CASES,
                         ids=[f"{s[:20]}…{t}" for s, t, _ in VAL_CASES])
def test_validator_golden(validated, sent, token, expected):
    cohorts = validated[sent]
    got = next((set(c["errtags"]) for c in cohorts if c["form"] == token), None)
    assert got is not None, f"Token {token!r} nicht im Output gefunden"
    assert got == expected, (
        f"{sent!r} / {token}: erwartet {sorted(expected)}, "
        f"erhalten {sorted(got)}")
    if not expected:
        # Fehlalarm-Test: der GANZE Satz muss fehlerfrei sein
        flags = {c["form"]: c["errtags"] for c in cohorts if c["errtags"]}
        assert not flags, f"{sent!r}: unerwartete Fehler-Tags {flags}"
