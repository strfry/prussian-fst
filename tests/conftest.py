"""Gemeinsame Fixtures: geladene FSTs + Golddaten.

Die Tests setzen einen vorhandenen Build voraus
(`uv run python -m prussian.fst.build`, ggf. `--gold-only`) und werden
übersprungen, wenn die Artefakte fehlen.
"""

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
ANALYSER = ROOT / "build/analyser.fst"
LENIENT = ROOT / "build/lenient.fst"


def _load_fst(path: Path):
    from pyfoma import FST
    if not path.exists():
        pytest.skip(f"{path} fehlt — erst `uv run python -m prussian.fst.build`")
    return FST.load(str(path))


@pytest.fixture(scope="session")
def analyser():
    return _load_fst(ANALYSER)


@pytest.fixture(scope="session")
def lenient():
    return _load_fst(LENIENT)


@pytest.fixture(scope="session")
def gold_nominal():
    return json.loads((ROOT / "data/gold/goldstandard.json").read_text())


@pytest.fixture(scope="session")
def gold_verbal():
    return json.loads(
        (ROOT / "data/gold/goldstandard_verben_fst.json").read_text())
