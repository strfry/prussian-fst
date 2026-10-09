"""WS2b: Numeralia aus Atomen + lean NVH statt der früheren ``lexc/numerals.lexc``.

Gold ist die eingefrorene Kopie ``tests/gold/numerals_analyses.txt`` (61 Lemmata,
``lemma+Tags:surface``). Jede Gold-Analyse muss in der gebackenen
``build/analyzer.lexc`` stehen — nach einer **expliziten** Tabelle der bewussten
Abweichungen (Wortart jetzt aus der NVH ``pos``/``numtype``):

* ``eraīns``/``niaīns`` „jeder“/„kein“: ``pos: pron`` (Hand-Tabelle) → ``+Pron``
* ``dwāi``/``trīs``: ``numtype: card`` in der NVH → ``+Num+Card`` (Gold ohne ``+Card``)
* invariable Numeralia: ``+Num+Card`` ohne das Gold-Artefakt ``+Sg+Nom``
* Verweis-Einträge (``tūsimtans``) tragen die Lesart ihres Ziel-Lexems

Die Tests brauchen den Build (``make``) und überspringen sonst.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
GOLD = ROOT / "tests" / "gold" / "numerals_analyses.txt"
ANALYZER_LEXC = ROOT / "build" / "analyzer.lexc"

# Lemma → (alt, neu): Ersetzung im Tag-Teil der Gold-Analyse.
DEVIATIONS = {
    "eraīns": ("+Num+", "+Pron+"),
    "niaīns": ("+Num+", "+Pron+"),
    "dwāi": ("+Num+", "+Num+Card+"),
    "trīs": ("+Num+", "+Num+Card+"),
}
INVARIABLE_GOLD_TAGS = "+Num+Card+Sg+Nom"
# Verweis-Einträge, deren Form das Ziel-Lexem schon erzeugt, tragen dessen Lesart
# (WS3): tūsimtans „↑ Tūsimts crd acc“ = Akkusativ Plural von tūsimts.
FORM_OF = {"tūsimtans+Num+Card+Sg+Nom:tūsimtans": "tūsimts+Num+Card+Msc+Pl+Acc:tūsimtans"}


def _gold() -> list[str]:
    return [line.strip() for line in GOLD.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.startswith("#")]


def _expected(analysis: str) -> str:
    """Gold-Analyse → erwartete Analyse nach den bewussten Abweichungen."""
    if analysis in FORM_OF:
        return FORM_OF[analysis]
    lemma_tags, surface = analysis.rsplit(":", 1)
    lemma, tags = lemma_tags.split("+", 1)
    tags = "+" + tags
    if lemma in DEVIATIONS:
        old, new = DEVIATIONS[lemma]
        tags = tags.replace(old, new, 1)
    if tags == INVARIABLE_GOLD_TAGS and surface == lemma:
        tags = "+Num+Card"
    return f"{lemma}{tags}:{surface}"


@pytest.fixture(scope="module")
def baked() -> set[str]:
    if not ANALYZER_LEXC.exists():
        pytest.skip("build/analyzer.lexc fehlt — erst `make`")
    out: set[str] = set()
    for line in ANALYZER_LEXC.read_text(encoding="utf-8").splitlines():
        m = re.match(r"\s+(\S.*?)\s+# ;", line)
        if m:
            out.add(m.group(1).replace("% ", " "))
    return out


def test_gold_lists_61_numeral_lemmas():
    assert len({a.split("+", 1)[0] for a in _gold()}) == 61


def test_every_gold_analysis_is_baked(baked):
    missing = [a for a in _gold() if _expected(a) not in baked]
    assert not missing, f"{len(missing)} Gold-Analysen fehlen, z. B. {missing[:5]}"


# Eigenständige Homographen, keine Doppellesart desselben Lexems: astōndesimts
# ist in der NVH auch Nomen P58 „achtzig“ (ohne numtype — Twanksta-Datenlücke).
HOMOGRAPHS = {"astōndesimts"}


def test_numerals_have_no_adjective_or_noun_reading(baked):
    """Keine Doppellesart mehr (+A/+N aus dem Backen neben +Num aus numerals.lexc)."""
    lemmas = {a.split("+", 1)[0] for a in _gold()} - HOMOGRAPHS
    double = sorted(b for b in baked
                    if b.split("+", 1)[0] in lemmas
                    and b.split("+", 2)[1] in ("A", "N"))
    assert not double, double[:5]


def test_ordinals_have_no_degree_forms(baked):
    """Ordinalia (P26 über AdjMobile) backen nur den Positiv — kein comp/superl/Adv."""
    assert not [b for b in baked if b.startswith("pirms+")
                and ("+Comp" in b or "+Superl" in b or "+Adv" in b)]
