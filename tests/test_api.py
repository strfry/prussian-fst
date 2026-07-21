"""Smoke-Tests für die stabile In-Process-API (prussian_fst.api).

Ergänzend zur CLI: die API muss dasselbe liefern wie
cg3_pipeline.py --text … --conllu/--validate (Extraktions-Guard)."""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
FST = REPO / "build/base.hfstol"

pytestmark = pytest.mark.skipif(
    not (shutil.which("cg-proc") and FST.exists()),
    reason="cg-proc/base.hfstol nicht verfügbar",
)

from prussian_fst import api  # noqa: E402


def test_check_artifacts_ready():
    assert api.check_artifacts() == []


def test_validate_violation():
    results = api.validate("As pūwa sen laīwu.")
    assert len(results) == 1
    r = results[0]
    assert r["status"] == "violations_found"
    v = r["violations"][0]
    assert v["rule"] == "prep-akk-dat"
    assert v["severity"] == "error"
    assert v["form"] == "laīwu"


def test_validate_clean_sentence():
    r = api.validate("As pūwa sen laīwan.")[0]
    assert r["status"] == "verified_in_coverage"
    assert r["violations"] == []
    assert set(r["coverage"]) >= {"word_tokens", "oov", "collapsed",
                                  "ambig", "checks_relevant", "reasons"}


def test_validate_oov_is_out_of_coverage():
    r = api.validate("Vakar buvau namie.")[0]
    assert r["status"] == "out_of_coverage"
    assert "oov" in r["coverage"]["reasons"]


def test_conllu_format():
    out = api.conllu("Labban dēinan!")
    assert out.startswith("# sent_id = ")
    token_lines = [l for l in out.splitlines() if l and l[0].isdigit()]
    assert token_lines and all(len(l.split("\t")) == 10 for l in token_lines)
    assert "Rule=" in out


def test_conllu_matches_cli():
    """Extraktions-Guard: API-Output == CLI-Output (byte-identisch)."""
    text = "Labban dēinan! As pūwa sen laīwu."
    cli = subprocess.run(
        [sys.executable, "-m", "prussian_fst.cg3_pipeline",
         "--text", text, "--conllu", "--trace"],
        capture_output=True, text=True, check=True, cwd=REPO)
    assert api.conllu(text) == cli.stdout


def test_empty_text_raises():
    with pytest.raises(ValueError):
        api.validate("   ")
