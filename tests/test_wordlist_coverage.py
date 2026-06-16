"""Wortlisten-Coverage: analysiert alle wordlist.json-Einträge gegen den FST.

Für jedes Wort mit einem vom FST abgedeckten Paradigma wird geprüft, ob
der Analysator eine Analyse liefert.  Die Coverage wird pro Paradigma
ausgewiesen — das zeigt, welche Stämme der FST erkennt und welche nicht.
"""

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
ANALYSER = ROOT / "build/analyser.fst"
WORDLIST = ROOT / "data/external/wordlist.json"
GOLD_NOM = ROOT / "data/gold/goldstandard.json"
GOLD_VERB = ROOT / "data/gold/goldstandard_verben_fst.json"


def _load_fst(path: Path):
    from pyfoma import FST
    if not path.exists():
        pytest.skip(f"{path} fehlt — erst `uv run python -m prussian.fst.build`")
    return FST.load(str(path))


def _par_int(p: str) -> int:
    m = re.match(r"(\d+)", p)
    return int(m.group(1)) if m else 999


@pytest.fixture(scope="session")
def analyser():
    return _load_fst(ANALYSER)


@pytest.fixture(scope="session")
def wordlist():
    if not WORDLIST.exists():
        pytest.skip(f"{WORDLIST} fehlt — externe Daten beziehen (s. README)")
    return json.loads(WORDLIST.read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def fst_paradigms():
    gs = json.loads(GOLD_NOM.read_text(encoding="utf-8"))
    gsv = json.loads(GOLD_VERB.read_text(encoding="utf-8"))
    return set(e["paradigm"] for e in gs) | set(e["paradigm"] for e in gsv)


def test_wordlist_coverage(analyser, wordlist, fst_paradigms):
    total = 0
    recognized = 0
    lemma_matched = 0
    stats: dict[str, dict] = {}

    for e in wordlist:
        par = e.get("paradigm", "")
        if not par or par not in fst_paradigms:
            continue
        w = e["word"].lower()
        total += 1
        results = list(analyser.analyze(w))
        has_any = bool(results)
        has_lemma = any(
            r.startswith(e["word"]) or r.lower().startswith(w)
            for r in results
        ) if results else False

        if has_any:
            recognized += 1
        if has_lemma:
            lemma_matched += 1

        stats.setdefault(par, {"total": 0, "recognized": 0, "lemma_match": 0})
        stats[par]["total"] += 1
        if has_any:
            stats[par]["recognized"] += 1
        if has_lemma:
            stats[par]["lemma_match"] += 1

    # ── Report ──
    lines = [
        f"\n{'='*70}",
        f"Wortlisten-Coverage ({total} Einträge in {len(stats)} Paradigmen)",
        f"{'='*70}",
        f"  Analysiert (beliebig):    {recognized:5d}  ({100*recognized/total:5.1f}%)",
        f"  Lemma-Analyse:            {lemma_matched:5d}  ({100*lemma_matched/total:5.1f}%)",
        f"  Unerkannt:                {total-recognized:5d}  ({100*(total-recognized)/total:5.1f}%)",
        "",
        f"  {'Pragma':5s}  {'Coverage':22s} {'Ratio':14s} {'Details'}",
        f"  {'─'*5}  {'─'*22} {'─'*14} {'─'*20}",
    ]

    sorted_pars = sorted(stats, key=lambda p: (_par_int(p), p))
    for par in sorted_pars:
        s = stats[par]
        pct = 100 * s["recognized"] / s["total"]
        bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
        lines.append(
            f"  P{par:5s}  {bar} {s['recognized']:5d}/{s['total']:5d} "
            f"({pct:5.1f}%)"
        )

    lines.append("")
    coverage_nom = []
    coverage_verb = []
    for par in sorted_pars:
        s = stats[par]
        pct = 100 * s["recognized"] / s["total"]
        if _par_int(par) <= 70:
            coverage_nom.append(pct)
        else:
            coverage_verb.append(pct)

    if coverage_nom:
        avg_nom = sum(coverage_nom) / len(coverage_nom)
        lines.append(
            f"Nominalparadigmen (P9–P70): {len(coverage_nom):3d} Paradigmen, "
            f"mittlere Coverage {avg_nom:.1f}%"
        )
    if coverage_verb:
        avg_verb = sum(coverage_verb) / len(coverage_verb)
        lines.append(
            f"Verbparadigmen (P71+):       {len(coverage_verb):3d} Paradigmen, "
            f"mittlere Coverage {avg_verb:.1f}%"
        )

    report = "\n".join(lines)
    print(report)

    overall_pct = 100 * recognized / total
    assert overall_pct > 50, (
        f"Gesamt-Coverage ({overall_pct:.1f}%) liegt unter 50%"
    )

    if coverage_nom:
        avg_nom = sum(coverage_nom) / len(coverage_nom)
        assert avg_nom > 60, (
            f"Mittlere Nominal-Coverage ({avg_nom:.1f}%) liegt unter 60%"
        )
