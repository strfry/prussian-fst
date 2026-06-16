#!/usr/bin/env python3
"""Synthetische Komparativ-/Superlativ-Deklination der Adjektive erzeugen.

Linguistische SPEC (Templates, Formant-Routing, Repräsentanten, Suppletiva) liegt
ausgelagert in data/spec/adj_comparison.json — inklusive Modell-Begründung, Quelle
und Status (_meta). Hier nur die Mechanik: SPEC laden und die comp-/sup-Einträge
erzeugen.

Liest data/gold/goldstandard.json (Positiv-Stämme), hängt comp-/sup-Einträge an
und schreibt es zurück. Idempotent (Dedup über Paradigma-Mengen in main()).
"""
import json
from collections import OrderedDict
from pathlib import Path

GS = Path("data/gold/goldstandard.json")
SPEC_FILE = Path("data/spec/adj_comparison.json")

_SPEC_DATA = json.loads(SPEC_FILE.read_text(encoding="utf-8"))

CELLS = _SPEC_DATA["cells"]


def _uis(tpl):
    """-uis--Variante (u-Stämme): nur der FÜHRENDE Formant ai→ui (Endungsreste
    wie -ai im Nom pl bleiben erhalten)."""
    return {g: {c: ("ui" + s[2:] if s.startswith("ai") else s)
                for c, s in cells.items()}
            for g, cells in tpl.items()}


def _template(name):
    """Genus→Zelle→Suffix-Template aus der SPEC (UIS wird aus AIS abgeleitet)."""
    if name == "UIS":
        return _uis(_template("AIS"))
    raw = _SPEC_DATA["templates"][name]
    return {g: cells for g, cells in raw.items() if g in ("m", "f", "n")}


TEMPLATE_AIS = _template("AIS")
TEMPLATE_UIS = _template("UIS")
TEMPLATE_P26 = _template("P26")

# Paradigma → (Formant-Template, palatal-Stamm?). palatal=True setzt den J-Marker.
SPEC = {par: (_template(s["template"]), s["palatal"])
        for par, s in _SPEC_DATA["spec"].items()}

# Paradigmen mit suppletivem Positiv-Gold-Lemma → Repräsentant (lemma, stamm).
REPRESENTATIVES = {par: tuple(v)
                   for par, v in _SPEC_DATA["representatives"].items()
                   if par != "_note"}

# Suppletiva (lemma, basis-paradigm, _SUPPL-Suffix) → (komp-stamm, sup-stamm).
SUPPLE = {(e["lemma"], e["base"], e["suffix"]): (e["comp"], e["sup"])
          for e in _SPEC_DATA["suppletives"]["entries"]}


def _positive(entries):
    """(paradigm, gender) → (lemma, stamm) des Positivs."""
    out = {}
    for e in entries:
        out.setdefault((e["paradigm"], e["gender"]), (e["lemma"], e["stamm"]))
    return out


def _entry(paradigm, lemma, gender, stamm, suffixe, provisional):
    e = OrderedDict([("paradigm", paradigm), ("lemma", lemma),
                     ("gender", gender), ("stamm", stamm), ("suffixe", suffixe)])
    if provisional:
        e["provisional"] = True
    return e


def _suffixe(template_g, betont, palatize):
    out = OrderedDict()
    for cell in CELLS:
        d = {"suffix": template_g[cell], "betont": betont}
        if palatize:
            d["palatize"] = True
        out[cell] = d
    return out


def build_comparison_entries(entries):
    pos = _positive(entries)
    new = []

    # --- Suppletive: lemma-spezifische *_suppl-Paradigmen (P26-Deklination) ---
    for (lemma, par, sfx), (comp_stem, sup_stem) in SUPPLE.items():
        for g in ("m", "f", "n"):
            for kind, stem in (("comp", comp_stem), ("sup", sup_stem)):
                new.append(_entry(f"{par}{kind}_{sfx}", lemma, g, stem,
                                  _suffixe(TEMPLATE_P26[g], betont=False, palatize=False),
                                  provisional=False))

    # --- Reguläre comp/sup aus SPEC ---
    for par, (tpl, palatal) in SPEC.items():
        for g in ("m", "f", "n"):
            if par in REPRESENTATIVES:
                lemma, stamm = REPRESENTATIVES[par]
            else:
                lp = pos.get((par, g)) or pos.get((par, "m"))
                if not lp:
                    continue
                lemma, stamm = lp
            for kind, stem in (("comp", stamm), ("sup", "uka" + stamm)):
                new.append(_entry(f"{par}{kind}", lemma, g, stem,
                                  _suffixe(tpl[g], betont=True, palatize=palatal),
                                  provisional=True))

    # --- P28: bereits Komparativ → nur Superlativ, mit P28-Positiv-Endungen
    #     auf uka+Stamm (NICHT TEMPLATE_AIS — sonst doppelter Formant) ---
    for g in ("m", "f", "n"):
        p28 = next((e for e in entries if e["paradigm"] == "28" and e["gender"] == g), None)
        if not p28:
            continue
        suffixe = OrderedDict()
        for cell, v in p28["suffixe"].items():
            suffixe[cell] = dict(v)
        new.append(_entry("28sup", p28["lemma"], g, "uka" + p28["stamm"],
                          suffixe, provisional=True))

    return new


def main():
    entries = json.loads(GS.read_text(encoding="utf-8"))
    drop = set()
    for par in list(SPEC) + ["28", "25", "26"]:
        drop |= {f"{par}comp", f"{par}sup"}
    for (lemma, par, sfx) in SUPPLE:
        drop |= {f"{par}comp_{sfx}", f"{par}sup_{sfx}"}
    base = [e for e in entries if e["paradigm"] not in drop]
    new = build_comparison_entries(base)
    GS.write_text(json.dumps(base + new, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"goldstandard.json: {len(base)} + {len(new)} comp/sup = {len(base) + len(new)}")


if __name__ == "__main__":
    main()
