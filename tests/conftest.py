"""Gemeinsame Fixtures: Golddaten."""

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session")
def gold_nominal():
    return json.loads((ROOT / "data/gold/goldstandard.json").read_text())


@pytest.fixture(scope="session")
def gold_verbal():
    return json.loads(
        (ROOT / "data/gold/goldstandard_verben_fst.json").read_text())
