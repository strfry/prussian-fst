#!/usr/bin/env python3
"""Leitet das Akzentmodell nach Rinkevičius (2009) aus dem Goldstandard ab.

Theorie (Rinkevičius 2009, »Das altpreußische Akzentsystem«, Diss. Vilnius):

  - Zwei nominale Akzentparadigmen: **Barytona** (Akzent fest auf dem Stamm,
    Wurzelvokal durchgehend lang) und **Mobilia** (Akzent springt auf »starke«
    Endungen; dort ist der Wurzelvokal unbetont und kurz).
  - Generative Grundregel: *Akzent = erstes starkes Morphem; fehlt eines,
    erstes Morphem überhaupt.*
  - Orthographischer Reflex in der TABVLA NOVA: Makron = langer betonter
    Vokal; Doppelkonsonant markiert Kürze des (betonten) Vorvokals.

Ableitung aus goldstandard.json (die `betont`-Flags pro Zelle sind die
phänomenologische Evidenz; sie bleiben unverändert):

  1. **Lexemklassen**: alle Zellen betont → Baryton (`bar`); gemischt →
     Mobile (`mob`); kein Archiphonem im Stamm → Akzent unbeobachtbar (`na`).
  2. **Endungsstärke**: in Mobilia ist die Endung einer Zelle mit
     `betont=false` (Stamm kurz) **stark**, sonst **schwach**. Aggregiert
     über alle Mobilia pro (Zelle, Endungsoberfläche); Konflikte werden
     gemeldet.
  3. **De-Akzentuierungspaare**: starke Endung minus Akzentorthographie
     (Makron-Tilgung + Degemination) sollte der unbetonten Variante in
     Barytona entsprechen (āi↔ai, ammans↔amans, …) — Evidenz dafür, dass
     Länge/Gemination der Endung reiner Akzentreflex ist.
  4. **Verben**: gleiche Klassifikation; gemischte Muster betreffen dort
     ausschließlich den Infinitiv → Ablaut (Stammstufe), kein Akzent.
     Sie werden als `ablaut` getrennt ausgewiesen.

Output:
  data/gold/accent_model.json       Endungstabelle + Lexemklassen + Paare
  data/gold/accent_exceptions.json  Zellen, die das Modell nicht vorhersagt
"""

import json
from collections import defaultdict
from pathlib import Path

GOLD = Path("data/gold/goldstandard.json")
VERB_GOLD = Path("data/gold/goldstandard_verben_fst.json")
MODEL_OUT = Path("data/gold/accent_model.json")
EXC_OUT = Path("data/gold/accent_exceptions.json")

LONG2SHORT = str.maketrans("āēīōū", "aeiou")

CELLS = ["Nom sg", "Gen sg", "Dat sg", "Akk sg",
         "Nom pl", "Gen pl", "Dat pl", "Akk pl"]


def has_archiphoneme(stamm: str) -> bool:
    """Großbuchstabe im Roh-Stamm = Archiphonem = alternierender Langvokal."""
    return any(c.isupper() for c in stamm)


def accent_class(entry: dict) -> str:
    """bar = Stamm immer lang, mob = alterniert, na = nicht beobachtbar."""
    if not has_archiphoneme(entry["stamm"]):
        return "na"
    vals = [v["betont"] for v in entry["suffixe"].values()]
    if all(vals):
        return "bar"
    if not any(vals):
        return "na"  # Archiphonem, das nie lang erscheint — käme einer Anomalie gleich
    return "mob"


def std_suffix(v: dict) -> str:
    """Doubletten ('a/stan') auf den Standardteil reduzieren."""
    return v["suffix"].split("/")[0]


def deaccent(suffix: str) -> str:
    """Akzentorthographie tilgen: Makron weg, Gemination reduzieren."""
    s = suffix.translate(LONG2SHORT)
    out = []
    for ch in s:
        if not (out and out[-1] == ch and ch not in "aeiou"):
            out.append(ch)
    return "".join(out)


def derive_nominal_model(entries: list[dict]):
    classes: dict[tuple[str, str], dict] = {}
    # (cell, suffix) -> {"strength": .., "evidence": [..]}
    strength: dict[str, dict[str, dict]] = defaultdict(dict)
    exceptions: list[dict] = []

    # Pass 1: Lexemklassen (pro Paradigma × Genus; Lemmata teilen das Muster)
    for e in entries:
        key = (e["paradigm"], e["gender"])
        cls = accent_class(e)
        strong_cells = sorted(
            c for c, v in e["suffixe"].items() if not v["betont"]
        ) if cls == "mob" else []
        if key in classes:
            if classes[key]["class"] != cls:
                exceptions.append({
                    "type": "klassen-konflikt", "paradigm": e["paradigm"],
                    "gender": e["gender"], "lemma": e["lemma"],
                    "expected": classes[key]["class"], "got": cls,
                })
            if e["lemma"] not in classes[key]["lemmas"]:
                classes[key]["lemmas"].append(e["lemma"])
        else:
            classes[key] = {"class": cls, "strong_cells": strong_cells,
                            "lemmas": [e["lemma"]]}

    # Pass 2: Endungsstärke aus den Mobilia
    for e in entries:
        if accent_class(e) != "mob":
            continue
        for cell, v in e["suffixe"].items():
            sfx = std_suffix(v)
            st = "stark" if not v["betont"] else "schwach"
            ev = f"P{e['paradigm']} {e['gender']} {e['lemma']}"
            rec = strength[cell].get(sfx)
            if rec is None:
                strength[cell][sfx] = {"strength": st, "evidence": [ev]}
            elif rec["strength"] != st:
                exceptions.append({
                    "type": "endungs-konflikt", "cell": cell, "suffix": sfx,
                    "expected": rec["strength"], "got": st, "evidence": ev,
                })
            elif ev not in rec["evidence"]:
                rec["evidence"].append(ev)

    # Pass 3: De-Akzentuierungspaare — starke Endung ↔ Baryton-Gegenstück
    bar_endings: dict[str, set[str]] = defaultdict(set)
    for e in entries:
        if accent_class(e) == "bar":
            for cell, v in e["suffixe"].items():
                bar_endings[cell].add(std_suffix(v))
    pairs: dict[str, list] = defaultdict(list)
    for cell, sfxs in strength.items():
        for sfx, rec in sfxs.items():
            if rec["strength"] != "stark":
                continue
            plain = deaccent(sfx)
            attested = plain in bar_endings.get(cell, set())
            pairs[cell].append({"stark": sfx, "deakzentuiert": plain,
                                "in_barytona_belegt": attested})

    # Pass 4: Vorhersage-Abdeckung — globale Tabelle + Klasse ⇒ betont-Flag
    total = correct = 0
    for e in entries:
        cls = accent_class(e)
        for cell, v in e["suffixe"].items():
            total += 1
            sfx = std_suffix(v)
            if cls in ("bar", "na"):
                pred = (cls == "bar")
            else:
                rec = strength[cell].get(sfx)
                if rec is None:
                    exceptions.append({
                        "type": "endung-unbekannt", "paradigm": e["paradigm"],
                        "gender": e["gender"], "lemma": e["lemma"],
                        "cell": cell, "suffix": sfx,
                    })
                    continue
                pred = (rec["strength"] == "schwach")
            if pred == v["betont"]:
                correct += 1
            else:
                exceptions.append({
                    "type": "fehlvorhersage", "paradigm": e["paradigm"],
                    "gender": e["gender"], "lemma": e["lemma"], "cell": cell,
                    "suffix": sfx, "class": cls,
                    "betont_gold": v["betont"], "betont_modell": pred,
                })

    return classes, strength, pairs, exceptions, (correct, total)


def derive_verb_classes(verb_entries: list[dict]):
    """bar/na wie nominal; Inf-only-Mischung = Ablaut (lexikalische Stammstufe)."""
    out = []
    for e in verb_entries:
        cls = accent_class(e)
        unstressed = sorted(c for c, v in e["suffixe"].items() if not v["betont"])
        if cls == "mob":
            cls = "ablaut" if unstressed == ["Inf"] else "mob"
        out.append({"paradigm": e["paradigm"], "tense": e["tense"],
                    "lemma": e["lemma"], "class": cls,
                    **({"unbetonte_zellen": unstressed} if cls in ("mob", "ablaut") else {})})
    return out


def main() -> None:
    entries = json.loads(GOLD.read_text(encoding="utf-8"))
    verb_entries = json.loads(VERB_GOLD.read_text(encoding="utf-8"))

    classes, strength, pairs, exceptions, (correct, total) = \
        derive_nominal_model(entries)
    verb_classes = derive_verb_classes(verb_entries)

    model = {
        "_meta": {
            "beschreibung": "Akzentmodell nach Rinkevičius 2009: Lexemklassen "
                            "(Barytona/Mobilia) + globale Endungsstärke. "
                            "Abgeleitet aus den betont-Flags des Goldstandards. "
                            "Siehe docs/AKZENT.md.",
            "generiert_von": "src/prussian/gold/accent.py",
            "quellen": [str(GOLD), str(VERB_GOLD)],
        },
        "lexeme_classes": [
            {"paradigm": par, "gender": g, **rec}
            for (par, g), rec in sorted(classes.items())
        ],
        "ending_strength": {
            cell: dict(sorted(strength[cell].items()))
            for cell in CELLS if cell in strength
        },
        "deaccent_pairs": {cell: pairs[cell] for cell in CELLS if cell in pairs},
        "verb_classes": verb_classes,
        "coverage": {"zellen": total, "korrekt": correct,
                     "quote": round(correct / total, 4) if total else None},
    }
    MODEL_OUT.write_text(json.dumps(model, ensure_ascii=False, indent=1),
                         encoding="utf-8")
    EXC_OUT.write_text(json.dumps(exceptions, ensure_ascii=False, indent=1),
                       encoding="utf-8")

    # ── Report ──
    ncls = defaultdict(int)
    for rec in classes.values():
        ncls[rec["class"]] += 1
    print(f"Nominal: {len(entries)} Einträge, {len(classes)} Paradigma×Genus")
    print(f"  Barytona: {ncls['bar']}   Mobilia: {ncls['mob']}   "
          f"unbeobachtbar: {ncls['na']}")
    n_stark = sum(1 for c in strength for s in strength[c]
                  if strength[c][s]["strength"] == "stark")
    n_schw = sum(len(strength[c]) for c in strength) - n_stark
    print(f"Endungstabelle: {n_stark} stark, {n_schw} schwach")
    npairs = sum(len(v) for v in pairs.values())
    nbelegt = sum(1 for v in pairs.values() for p in v if p["in_barytona_belegt"])
    print(f"De-Akzentuierungspaare: {nbelegt}/{npairs} in Barytona belegt")
    vcls = defaultdict(int)
    for v in verb_classes:
        vcls[v["class"]] += 1
    print(f"Verben: {dict(vcls)}")
    print(f"Abdeckung: {correct}/{total} Zellen "
          f"({100 * correct / total:.1f} %)" if total else "")
    print(f"Exceptions: {len(exceptions)}  →  {EXC_OUT}")
    if exceptions:
        for x in exceptions[:10]:
            print(f"  {x}")
    print(f"Modell → {MODEL_OUT}")


if __name__ == "__main__":
    main()
