"""Orchestrator: baut data/derived/dashboard.json aus den report-Runnern.

Spiegelt die Eintrags-Assemblierung aus fst/build.py, damit der Report exakt
das abbildet, was im FST steckt (Gold + Wortliste + Verb-Wortliste + closed).
Aufruf:  PYTHONPATH=src pypy3 -m prussian.report.dashboard
"""

import json
import subprocess
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from prussian.fst.morphology import adverbs as adv_mod
from prussian.fst.morphology import function_words as fw_mod
from prussian.fst.morphology import nominals, verbs
from prussian.report import corpus_coverage, dict_coverage, generation
from prussian.report.cases import nominal_cases, nominal_pos, verbal_cases

ROOT = Path(__file__).resolve().parent.parent.parent.parent
BUILD = ROOT / "build"
GOLD = ROOT / "data/gold/goldstandard.json"
VERB_GOLD = ROOT / "data/gold/goldstandard_verben_fst.json"
WORDLIST = ROOT / "data/external/wordlist.json"
DICT = ROOT / "data/external/prussian_dictionary.json"
CLOSED_PRONOUNS = ROOT / "data/closed/personal_pronouns.json"
CLOSED_FW = ROOT / "data/closed/function_words.json"
OUT = ROOT / "data/derived/dashboard.json"
DATA_JS = ROOT / "dashboard/data.js"  # window.DASHBOARD_DATA — von index.html geladen
SCHEMA_VERSION = "2.0"

POS_META = {
    "+N":    ("Substantive", "wīrs"),
    "+A":    ("Adjektive", "debīks"),
    "+Pron": ("Pronomina", "as"),
    "+Num":  ("Numeralia", "aīns"),
    "+Adv":  ("Adverbien", "labbai"),
    "+V":    ("Verben", "bēi"),
}


def _pct(num: int, den: int) -> float:
    return round(100 * num / den, 1) if den else 0.0


def _git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=ROOT,
            text=True).strip()
    except Exception:
        return "unknown"


def _paradigm_pos(par: str, nominal_pos_map: dict[str, str]) -> str:
    if par in nominal_pos_map:
        return nominal_pos_map[par]
    return "+V"  # Verb-Paradigmen (P71+) tauchen nur verbal auf


def _load_entries():
    gs = json.loads(GOLD.read_text(encoding="utf-8"))
    verb_gold = json.loads(VERB_GOLD.read_text(encoding="utf-8"))
    wl_data = json.loads(WORDLIST.read_text(encoding="utf-8"))
    dict_data = json.loads(DICT.read_text(encoding="utf-8"))
    closed = json.loads(CLOSED_PRONOUNS.read_text(encoding="utf-8"))

    wl_entries = nominals.wordlist_to_entries(wl_data, gs)
    combined = nominals.combine_entries(gs, wl_entries)
    verb_wl = verbs.wordlist_to_verb_entries(dict_data, verb_gold)
    fwords = fw_mod.load(CLOSED_FW)
    adverbs = adv_mod.load(DICT)
    return {
        "gold_nom": gs, "gold_verb": verb_gold,
        "combined_nom": combined + closed, "verb_all": verb_gold + verb_wl,
        "dict": dict_data, "function_words": fwords, "adverbs": adverbs,
    }


def _paradigm_completeness(analyser, nom_entries, verb_entries) -> dict:
    """Lemma vollständig = jede seiner erwarteten Zellen generiert (≠ ∅)."""
    per_lemma_total: dict[str, int] = defaultdict(int)
    per_lemma_gen: dict[str, int] = defaultdict(int)
    cache: dict[str, bool] = {}

    def gen_ok(tag: str) -> bool:
        v = cache.get(tag)
        if v is None:
            v = bool(list(analyser.generate(tag)))
            cache[tag] = v
        return v

    for case in (*nominal_cases(nom_entries), *verbal_cases(verb_entries)):
        per_lemma_total[case.lemma] += 1
        if gen_ok(case.tag):
            per_lemma_gen[case.lemma] += 1

    complete = sum(1 for lemma, tot in per_lemma_total.items()
                   if per_lemma_gen[lemma] == tot)
    return {"num": complete, "den": len(per_lemma_total)}


def _merge_gen_paradigms(gen: dict) -> dict[str, dict]:
    merged: dict[str, dict] = {}
    for slice_ in ("nominal", "verbal"):
        for par, b in gen[slice_]["per_paradigm"].items():
            merged[par] = b
    return merged


def build(analyser, lenient) -> dict:
    e = _load_entries()

    gen = generation.run(analyser, e["gold_nom"], e["gold_verb"])
    dc_nom = dict_coverage.run_nominal(analyser, lenient, e["dict"])
    dc_verb = dict_coverage.run_verbal(analyser, lenient, e["dict"])
    dc_closed = dict_coverage.run_closed(analyser, e["function_words"])
    dc_adv = dict_coverage.run_closed(analyser, e["adverbs"])
    corpus = corpus_coverage.run(analyser, lenient, e["dict"])
    completeness = _paradigm_completeness(
        analyser, e["combined_nom"], e["verb_all"])

    # POS-Routing der nominalen Paradigmen
    nominal_pos_map = {x["paradigm"]: nominal_pos(x["paradigm"])
                       for x in e["combined_nom"]}

    # ── Paradigmen-Detailliste ──
    gen_par = _merge_gen_paradigms(gen)
    dict_par: dict[str, dict] = {}
    for par, st in {**dc_nom["par_stats"], **dc_verb["par_stats"]}.items():
        dict_par[par] = {"total": st["total"],
                         "matched": st["direct"] + st["ortho"]}
    genders_of: dict[str, set] = defaultdict(set)
    for x in e["combined_nom"]:
        if x["gender"]:
            genders_of[x["paradigm"]].add(x["gender"])

    paradigms = []
    for par in sorted(set(gen_par) | set(dict_par),
                      key=lambda p: (dict_coverage._par_int(p), p)):
        g = gen_par.get(par, {})
        d = dict_par.get(par, {})
        gold_cells = g.get("cells", 0)
        gold_matched = g.get("matched", 0)
        if gold_cells and gold_matched == gold_cells:
            status = "done"
        elif gold_cells == 0:
            status = "open"
        else:
            status = "in_progress"
        paradigms.append({
            "id": par, "pos": _paradigm_pos(par, nominal_pos_map),
            "label": f"P{par}", "genders": sorted(genders_of.get(par, [])),
            "gold_cells": gold_cells, "gold_matched": gold_matched,
            "dict_total": d.get("total", 0), "dict_matched": d.get("matched", 0),
            "status": status,
        })

    # ── POS-Tabelle ──
    lemmata_per_pos: dict[str, set] = defaultdict(set)
    for x in e["combined_nom"]:
        lemmata_per_pos[nominal_pos(x["paradigm"])].add(x["lemma"])
    for x in e["verb_all"]:
        lemmata_per_pos["+V"].add(x["lemma"])

    pos_rows = []
    for tag, (name, example) in POS_META.items():
        if tag == "+Adv":
            continue  # geschlossene Klasse, eigene Zeile unten (nicht paradigmenbasiert)
        gen_pos = (gen["nominal"]["per_pos"].get(tag)
                   or gen["verbal"]["per_pos"].get(tag) or {})
        # Form-Coverage je POS aus den Paradigmen dieser POS aggregieren
        f_tot = sum(p["dict_total"] for p in paradigms if p["pos"] == tag)
        f_mat = sum(p["dict_matched"] for p in paradigms if p["pos"] == tag)
        pars = [p for p in paradigms if p["pos"] == tag]
        done = sum(1 for p in pars if p["status"] == "done")
        gold_cells = gen_pos.get("cells", 0)
        pos_rows.append({
            "tag": tag, "name": name, "example": example,
            "lemmata": len(lemmata_per_pos.get(tag, [])),
            "paradigms_done": done, "paradigms_total": len(pars),
            "gen_integrity_pct": (_pct(gen_pos.get("matched", 0), gold_cells)
                                  if gold_cells else None),
            "form_coverage_pct": _pct(f_mat, f_tot),
            "status": "done" if gold_cells and gen_pos.get("matched") == gold_cells
                      else ("in_progress" if len(pars) else "planned"),
        })

    # Adverbien als geschlossene Klasse (av-Lemmata, invariante +Adv-Lexeme)
    adv_name, adv_example = POS_META["+Adv"]
    pos_rows.append({
        "tag": "+Adv", "name": adv_name, "example": adv_example,
        "lemmata": dc_adv["total"],
        "paradigms_done": 0, "paradigms_total": 0,
        "gen_integrity_pct": None,
        "form_coverage_pct": _pct(dc_adv["recognized"], dc_adv["total"]),
        "status": "done" if dc_adv["recognized"] == dc_adv["total"]
                  else "in_progress",
    })

    # Funktionswörter als eigene POS-Zeile (real, nicht planned)
    pos_rows.append({
        "tag": "+Func", "name": "Funktionswörter", "example": "ni",
        "lemmata": dc_closed["total"],
        "paradigms_done": 0, "paradigms_total": 0,
        "gen_integrity_pct": None,
        "form_coverage_pct": _pct(dc_closed["recognized"], dc_closed["total"]),
        "status": "done" if dc_closed["recognized"] == dc_closed["total"]
                  else "in_progress",
    })

    # ── KPIs ──
    form_num = dc_nom["direct"] + dc_nom["ortho"]
    form_den = dc_nom["total"]
    ct = corpus["totals"]
    corpus_num = ct["analyzed"] + ct["ortho"]

    # ── Korpus-Block ──
    corpus_sources = [{
        "id": s["id"], "name": s["name"], "tokens": s["tokens"],
        "coverage_pct": _pct(s["analyzed"] + s["ortho"], s["tokens"]),
        "dropped_docs": s["dropped_docs"], "dropped_words": s["dropped_words"],
    } for s in corpus["per_source"]]
    unrec = ct["variant"] + ct["propn"] + ct["oov"]
    unanalyzable = [
        {"reason": "oov", "label": "Unbekannte Lemmata", "pct": _pct(ct["oov"], unrec)},
        {"reason": "propn", "label": "Eigennamen", "pct": _pct(ct["propn"], unrec)},
        {"reason": "variant", "label": "Form-/Flexionslücke", "pct": _pct(ct["variant"], unrec)},
    ]

    def _gen_health(slice_: str) -> dict:
        b = gen[slice_]
        out = {"cells": b["cells"], "matched": b["matched"],
               "no_gen": b["no_gen"], "mismatch": b["true_mismatch"],
               "case_only": b["case_only"]}
        if slice_ == "nominal":
            out["variants_matched"] = b["variants_matched"]
            out["variants_total"] = b["variants_total"]
        return out

    return {
        "meta": {
            "schema_version": SCHEMA_VERSION,
            "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "fst": {
                "engine": "pyfoma", "build_commit": _git_commit(),
                "analyser_states": len(analyser.states),
                "lenient_states": len(lenient.states),
                "tagset": "giella-flat-plus",
            },
        },
        "kpis": {
            "paradigm_completeness": {
                "label": "Lemmata mit vollständigem Paradigma",
                "pct": _pct(completeness["num"], completeness["den"]),
                "num": completeness["num"], "den": completeness["den"],
            },
            "form_coverage": {
                "label": "Formen generierbar vs. Wörterbuch",
                "pct": _pct(form_num, form_den), "num": form_num, "den": form_den,
                "ortho_pct": _pct(dc_nom["ortho"], form_den),
            },
            "corpus_coverage": {
                "label": "Korpus-Token analysierbar",
                "pct": _pct(corpus_num, ct["tokens"]),
                "num": corpus_num, "den": ct["tokens"],
            },
        },
        "health": {
            "generation": {"nominal": _gen_health("nominal"),
                           "verbal": _gen_health("verbal")},
        },
        "pos": pos_rows,
        "paradigms": paradigms,
        "corpus": {
            "total_tokens": ct["tokens"],
            "coverage_pct": _pct(corpus_num, ct["tokens"]),
            "sources": corpus_sources,
            "unanalyzable": unanalyzable,
            "top_oov": corpus.get("top_oov", [])[:100],
            "top_variant": corpus.get("top_variant", [])[:100],
        },
        "closed_class": {
            "total": dc_closed["total"], "recognized": dc_closed["recognized"],
            "per_pos": [{"tag": k, **v} for k, v in
                        sorted(dc_closed["per_pos"].items())],
        },
        "adverbs": {
            "total": dc_adv["total"], "recognized": dc_adv["recognized"],
        },
        "verbs_dict": {
            "total": dc_verb["total"],
            "matched": dc_verb["direct"] + dc_verb["ortho"],
            "ortho": dc_verb["ortho"], "no_match": dc_verb["no"],
        },
    }


def main() -> None:
    from pyfoma import FST
    analyser = FST.load(str(BUILD / "analyser.fst"))
    lenient = FST.load(str(BUILD / "lenient.fst"))
    report = build(analyser, lenient)
    payload = json.dumps(report, ensure_ascii=False, indent=2)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(payload, encoding="utf-8")
    # Standalone-Dashboard: data.js wird per <script src> geladen (auch file://)
    DATA_JS.parent.mkdir(parents=True, exist_ok=True)
    DATA_JS.write_text(f"window.DASHBOARD_DATA = {payload};\n", encoding="utf-8")
    k = report["kpis"]
    print(f"Paradigmen-Vollständigkeit: {k['paradigm_completeness']['pct']}% "
          f"({k['paradigm_completeness']['num']}/{k['paradigm_completeness']['den']})")
    print(f"Formen-Coverage (Dict):     {k['form_coverage']['pct']}% "
          f"({k['form_coverage']['num']}/{k['form_coverage']['den']})")
    print(f"Korpus-Coverage:            {k['corpus_coverage']['pct']}% "
          f"({k['corpus_coverage']['num']}/{k['corpus_coverage']['den']})")
    g = report["health"]["generation"]
    print(f"Gen-Integrität nominal: {g['nominal']['matched']}/{g['nominal']['cells']}"
          f"  verbal: {g['verbal']['matched']}/{g['verbal']['cells']}")
    print(f"Funktionswörter: {report['closed_class']['recognized']}/"
          f"{report['closed_class']['total']}")
    print(f"Adverbien: {report['adverbs']['recognized']}/"
          f"{report['adverbs']['total']}")
    print(f"→ {OUT}")


if __name__ == "__main__":
    main()
