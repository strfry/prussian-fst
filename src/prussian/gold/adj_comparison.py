#!/usr/bin/env python3
"""Synthetische Komparativ-/Superlativ-Deklination der Adjektive erzeugen.

Modell (docs/HANDOFF_allomorphie_steigerung.md, Lehrer-Antworten 2026-06-14):
Komparativstamm = Positivstamm + Formant (`-ais-`/`-uis-`, binär nach Stammklasse);
danach die weiche `-s`-Stamm-Deklination (Endungssatz unten, P28 māldaisis-Typ).
Superlativ = `uka-` + identische Deklination. Die Grenz-Palatalisierung
(`-ais-`→`-eis-`/`-jais-`) feuert nur bei lexikalisch palatalen Stämmen (nur P27)
über die vorhandene Jotierung (J-Marker `palatize`); das `š` in `aišas` etc. ist
die Formant-s→š-Regel vor a-Endung und steckt literal im Template.

Formant je Paradigma (aus dem Positiv-Paradigma vorhersagbar):
  P25/P26/P29/P30a o-Stamm → `-ais-`      P27 i-Stamm → `-ais-` + palatal
  P30/P31 u-Stamm  → `-uis-`              P28 ist bereits Komparativ → nur Superlativ

Suppletive (labs→waln-, debīks→māises-, līkuts→maz-) deklinieren wie P26-Positiv
(kein Formant) und werden lemma-spezifisch über die `*_suppl`-Paradigmen
(nominals._SUPPL_PARADIGMS) eingetragen — NICHT als `25comp`/`26comp`, weil das die
Paradigma-suffixe_map kapern und alle regulären P25/P26-Komparative zerstören würde.
(„viel/sehr"→tūls/mūises- ist datenseitig unklar — zurückgestellt.)

Liest data/gold/goldstandard.json (Positiv-Stämme), hängt comp-/sup-Einträge an
und schreibt es zurück. Idempotent (Dedup über Paradigma-Mengen in main()).
"""
import json
from collections import OrderedDict
from pathlib import Path

GS = Path("data/gold/goldstandard.json")

CELLS = ["Nom sg", "Nom pl", "Gen sg", "Gen pl",
         "Dat sg", "Dat pl", "Akk sg", "Akk pl"]

# Weiche -s-Stamm-Deklination, -ais--Formant (Lehrer-Tabelle P28, HANDOFF §b).
# š = Formant-s palatalisiert vor a-anlautender Endung — hier literal eingebacken.
TEMPLATE_AIS = {
    "m": {"Nom sg": "aisis", "Nom pl": "aišai", "Gen sg": "aišas", "Gen pl": "aisin",
          "Dat sg": "aišasmu", "Dat pl": "aisimans", "Akk sg": "aisin", "Akk pl": "aisins"},
    "f": {"Nom sg": "aisi", "Nom pl": "aisis", "Gen sg": "aišas", "Gen pl": "aisin",
          "Dat sg": "aišai", "Dat pl": "aisimans", "Akk sg": "aisin", "Akk pl": "aisins"},
    "n": {"Nom sg": "aisi", "Nom pl": "aišai", "Gen sg": "aišas", "Gen pl": "aisin",
          "Dat sg": "aišasmu", "Dat pl": "aisimans", "Akk sg": "aisi", "Akk pl": "aisins"},
}


def _uis(tpl):
    """-uis--Variante (u-Stämme): nur der FÜHRENDE Formant ai→ui (Endungsreste
    wie -ai im Nom pl bleiben erhalten)."""
    return {g: {c: ("ui" + s[2:] if s.startswith("ai") else s)
                for c, s in cells.items()}
            for g, cells in tpl.items()}


TEMPLATE_UIS = _uis(TEMPLATE_AIS)

# P26-Positiv-Endungen (o-Stamm, hart) für die Suppletiva (Handoff: „deklinieren
# wie P26"). Aus dem labs-Positiv-Eintrag.
TEMPLATE_P26 = {
    "m": {"Nom sg": "s", "Nom pl": "ai", "Gen sg": "as", "Gen pl": "un",
          "Dat sg": "u",  "Dat pl": "umans", "Akk sg": "an", "Akk pl": "uns"},
    "f": {"Nom sg": "a", "Nom pl": "as", "Gen sg": "as", "Gen pl": "un",
          "Dat sg": "ai", "Dat pl": "umans", "Akk sg": "an", "Akk pl": "uns"},
    "n": {"Nom sg": "an", "Nom pl": "ai", "Gen sg": "as", "Gen pl": "un",
          "Dat sg": "u",  "Dat pl": "umans", "Akk sg": "an", "Akk pl": "uns"},
}

# Paradigma → (Formant-Template, palatal-Stamm?). palatal=True setzt den J-Marker.
SPEC = {
    "25":  (TEMPLATE_AIS, False),   # o-Stamm regulär (debīks selbst ist suppletiv)
    "26":  (TEMPLATE_AIS, False),   # o-Stamm regulär (labs selbst ist suppletiv)
    "27":  (TEMPLATE_AIS, True),    # i-Stamm palatal (weselīngis → weselīnģaisis)
    "29":  (TEMPLATE_AIS, False),   # o-Stamm hart (sēnts → swintaisis)
    "30":  (TEMPLATE_UIS, False),   # u-Stamm (āngus → ānguisis)
    "30a": (TEMPLATE_AIS, False),   # o-Stamm w-Ausl. (stāws → stāwaisis)
    "31":  (TEMPLATE_UIS, False),   # u-Stamm (līgus → līguisis)
}

# Paradigmen, deren einziges Positiv-Gold-Lemma suppletiv ist → Repräsentant aus
# einem nicht-suppletiven Wortlisten-Lemma (Lemma, archiphonem-markierter Stamm),
# damit suffixe_map[("25comp",g)]/("26comp",g) das reguläre -ais--Template trägt
# und die emittierte Repräsentantenform korrekt ist.
REPRESENTATIVES = {
    "25": ("tūlins", "tUlin"),
    "26": ("mālds", "mAld"),
}

# Suppletiva (lemma, basis-paradigm, _SUPPL-Suffix) → (komp-stamm, sup-stamm).
# Paradigma-Keys matchen nominals._SUPPL_PARADIGMS (25comp_suppl, …), damit sie
# die reguläre 25comp/26comp-suffixe_map NICHT kapern.
SUPPLE = {
    ("debīks", "25", "suppl"):  ("māises", "ukamāises"),
    ("līkuts", "25", "suppl2"): ("maz", "ukamaz"),
    ("labs", "26", "suppl"):    ("waln", "ukawaln"),
}


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
