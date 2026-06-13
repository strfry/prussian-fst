"""Generierungs-Integrität: jede Gold-Zelle generieren und gegen das
``resolve_stem``-Orakel prüfen (nominal + verbal).

Klassifikation je Zelle:
  exact          erwartete Form ist unter den generierten
  case_only      nur Groß/Klein-Differenz (case_normalize)
  no_gen         FST generiert gar nichts für den Tag
  true_mismatch  generiert, aber falsche Oberfläche

Doubletten-Vollformen werden separat gezählt (variants_matched/total).
"""

from collections import defaultdict

from prussian.fst.oracle import case_normalize
from prussian.report.cases import nominal_cases, verbal_cases


def _empty_bucket() -> dict:
    return {
        "cells": 0, "matched": 0, "exact": 0, "case_only": 0,
        "no_gen": 0, "true_mismatch": 0,
        "variants_total": 0, "variants_matched": 0,
    }


def _check_cases(analyser, cases) -> dict:
    """Eine Zell-Klassifikation + Aggregation nach POS und Paradigma."""
    agg = _empty_bucket()
    per_pos: dict[str, dict] = defaultdict(_empty_bucket)
    per_paradigm: dict[str, dict] = defaultdict(_empty_bucket)
    no_gen_samples: list[dict] = []
    mismatch_samples: list[dict] = []

    for c in cases:
        results = list(analyser.generate(c.tag))
        for bucket in (agg, per_pos[c.pos], per_paradigm[c.paradigm]):
            bucket["cells"] += 1

        if not results:
            for bucket in (agg, per_pos[c.pos], per_paradigm[c.paradigm]):
                bucket["no_gen"] += 1
            if len(no_gen_samples) < 30:
                no_gen_samples.append(
                    {"paradigm": c.paradigm, "lemma": c.lemma,
                     "tag": c.tag, "expected": c.expected})
        elif c.expected in results:
            for bucket in (agg, per_pos[c.pos], per_paradigm[c.paradigm]):
                bucket["matched"] += 1
                bucket["exact"] += 1
        elif any(case_normalize(r) == case_normalize(c.expected) for r in results):
            for bucket in (agg, per_pos[c.pos], per_paradigm[c.paradigm]):
                bucket["matched"] += 1
                bucket["case_only"] += 1
        else:
            for bucket in (agg, per_pos[c.pos], per_paradigm[c.paradigm]):
                bucket["true_mismatch"] += 1
            if len(mismatch_samples) < 30:
                mismatch_samples.append(
                    {"paradigm": c.paradigm, "lemma": c.lemma,
                     "tag": c.tag, "expected": c.expected, "got": results})

        if c.variant is not None:
            for bucket in (agg, per_pos[c.pos], per_paradigm[c.paradigm]):
                bucket["variants_total"] += 1
            if results and c.variant in results:
                for bucket in (agg, per_pos[c.pos], per_paradigm[c.paradigm]):
                    bucket["variants_matched"] += 1

    return {
        **agg,
        "per_pos": {k: dict(v) for k, v in per_pos.items()},
        "per_paradigm": {k: dict(v) for k, v in per_paradigm.items()},
        "no_gen_samples": no_gen_samples,
        "mismatch_samples": mismatch_samples,
    }


def run(analyser, gold_nom: list[dict], gold_verb: list[dict]) -> dict:
    """Generierungs-Integrität für nominales + verbales Gold."""
    return {
        "nominal": _check_cases(analyser, nominal_cases(gold_nom)),
        "verbal": _check_cases(analyser, verbal_cases(gold_verb)),
    }
