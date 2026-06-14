#!/usr/bin/env python3
"""Synthetische Komparativ-/Superlativ-Deklination der Adjektive erzeugen.

Modell (docs/HANDOFF_allomorphie_steigerung.md, Lehrer-Antwort 2026-06-14):
Komparativstamm = Positivstamm + Formant (`-ais-`/`-uis-`, binär nach Stammklasse);
danach die weiche `-s`-Stamm-Deklination (Endungssatz unten, P28 māldaisis-Typ).
Superlativ = `uka-` + identische Deklination. Die Palatalisierung an der
Stamm+Formant-Grenze (palatale i-/jo-/weiche Stämme: `-ais-`→`-eis-`/`-jais-`,
gerendert als ģ/š …) übernimmt die vorhandene Jotierung (J-Marker `palatize`).

Pilot: u-Stämme P30/P31 (attestiert ānguisis/līguisis/ukalīguisis) + palataler
Stamm P27 (weselīngis → Grenzpalatalisierung). Rollout der übrigen Paradigmen +
Adverb + Suppletive (deklinieren wie P26) folgt; siehe Handoff.

Liest data/gold/goldstandard.json (Positiv-Stämme), hängt comp-/sup-Einträge an
und schreibt es zurück. Idempotent (Dedup über (lemma, paradigm, gender)).
"""
import json
from collections import OrderedDict
from pathlib import Path

GS = Path("data/gold/goldstandard.json")

CELLS = ["Nom sg", "Nom pl", "Gen sg", "Gen pl",
         "Dat sg", "Dat pl", "Akk sg", "Akk pl"]

# Weiche -s-Stamm-Deklination, -ais--Formant (Lehrer-Tabelle P28). š = Formant-s
# palatalisiert vor a-anlautender Endung — hier literal eingebacken.
TEMPLATE_AIS = {
    "m": {"Nom sg": "aisis", "Nom pl": "aišai", "Gen sg": "aišas", "Gen pl": "aisin",
          "Dat sg": "aišasmu", "Dat pl": "aisimans", "Akk sg": "aisin", "Akk pl": "aisins"},
    "f": {"Nom sg": "aisi", "Nom pl": "aisis", "Gen sg": "aišas", "Gen pl": "aisin",
          "Dat sg": "aišai", "Dat pl": "aisimans", "Akk sg": "aisin", "Akk pl": "aisins"},
    "n": {"Nom sg": "aisi", "Nom pl": "aišai", "Gen sg": "aišas", "Gen pl": "aisin",
          "Dat sg": "aišasmu", "Dat pl": "aisimans", "Akk sg": "aisi", "Akk pl": "aisins"},
}


def _uis(tpl):
    """-uis--Variante (u-Stämme): nur der FÜHRENDE Formant ai→ui (die Endung
    -ai z. B. im Nom pl bleibt erhalten)."""
    return {g: {c: ("ui" + s[2:] if s.startswith("ai") else s)
                for c, s in cells.items()}
            for g, cells in tpl.items()}


TEMPLATE_UIS = _uis(TEMPLATE_AIS)

# Paradigma → (Formant-Template, palatal-Stamm?). palatal=True setzt den J-Marker
# (Stammauslaut palatalisiert vor dem Formant). Pilot-Auswahl, s. Modul-Docstring.
SPEC = {
    "30":  (TEMPLATE_UIS, False),   # āngus  → ānguisis
    "31":  (TEMPLATE_UIS, False),   # līgus  → līguisis
    "27":  (TEMPLATE_AIS, True),    # weselīngis → Grenzpalatalisierung
}


def _positive_stems(entries):
    """(paradigm, gender) → Positiv-Stamm (archiphonemisch markiert)."""
    out = {}
    for e in entries:
        out.setdefault((e["paradigm"], e["gender"]), e["stamm"])
    return out


def build_comparison_entries(entries):
    stems = _positive_stems(entries)
    new = []
    for par, (tpl, palatal) in SPEC.items():
        for g in ("m", "f", "n"):
            stamm = stems.get((par, g)) or stems.get((par, "m"))
            if not stamm:
                continue
            lemma = next((e["lemma"] for e in entries
                          if e["paradigm"] == par and e["gender"] == g), None) \
                or next((e["lemma"] for e in entries if e["paradigm"] == par), par)
            for kind, stem in (("comp", stamm), ("sup", "uka" + stamm)):
                suffixe = OrderedDict()
                for cell in CELLS:
                    suffixe[cell] = {"suffix": tpl[g][cell], "betont": True,
                                     "palatize": palatal}
                new.append(OrderedDict([
                    ("paradigm", f"{par}{kind}"), ("lemma", lemma),
                    ("gender", g), ("stamm", stem), ("suffixe", suffixe),
                    ("provisional", True),
                ]))
    return new


def main():
    entries = json.loads(GS.read_text(encoding="utf-8"))
    base = [e for e in entries if e["paradigm"] not in
            {f"{p}{k}" for p in SPEC for k in ("comp", "sup")}]
    new = build_comparison_entries(base)
    GS.write_text(json.dumps(base + new, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"goldstandard.json: {len(base)} + {len(new)} comp/sup = {len(base) + len(new)}")


if __name__ == "__main__":
    main()
