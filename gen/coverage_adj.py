"""Nicht-zirkulärer Deckungstest für die adjektivisch deklinierten Wortarten.

Deckt die Adjektive (Positiv, a-/i-/jo-/u-Stamm) UND die Partizipien (Par.68 aktiv
-uns, Par.69 passiv -ts) UND die Komparativ-/Superlativ-Deklination ab — alle mit
DREI Genusblöcken (24 Formen). Wie beim Nomen (gen/coverage_gen.py) ist die Grammatik
hand-geschrieben und datenfrei (gen/adj.lexc: Endungslexika + Genusblöcke); hier wird
nur die STAMM-Inventarisierung skaliert: für jedes reale Lexem wird der Stamm aus dem
Masc-Block abgeleitet, an die Grammatik gehängt, kompiliert, mit gen/accent.regex
komponiert und die Formen exakt gegen Twanksta verglichen. Der Komparativ-/Superlativ-
Stamm (i-/jo-Deklination) wird aus der Komparativ-Deklination abgeleitet; der
Superlativ-Stamm = "uka" + Komparativ-Stamm (regelhaft, einmal gebaut — dieselbe
Mechanik wie beim Adverb-Superlativ in gen/coverage_adverb.py).

    uv run python gen/coverage_adj.py [--show N]
    uv run python gen/coverage_adj.py --emit-stems build/gen-adj-stems.lexc
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import json  # noqa: E402

from prussian_fst.fst_lookup import glookup_batch  # noqa: E402

TWANKSTA = ROOT.parent / "corpus" / "parsed" / "twanksta_entries.json"
LEXC = ROOT / "gen" / "adj.lexc"
ACCENT = ROOT / "build" / "gen-accent.hfst"
BUILD = ROOT / "build"
HFST = ["uv", "run", "python", str(ROOT / "src" / "prussian_fst" / "build_fst.py")]

# Paradigma → (Tag-Typ, Stamm-Lexikon, Infl-Lexikon, Masc-Quell-Slot, Klassenendung).
# Tag-Typ "Adj" → +Adj+…; "Pass"/"Past" → +Part+Pass/Past+…. Stamm = Masc-Quellform
# minus Klassenendung. Par.25 = festes a-Stamm-Adjektiv, Par.26 = mobiles a-Stamm-
# Adjektiv, Par.68/69 = Partizipien.
#
# Par.27 (i-/jo-Stamm-Adj, fest), 29 (mobiles i-Stamm-Adj), 31 (u-Stamm-Adj, w-Gleit,
# mobil) haben eigene Endungstabellen (aus den Daten die dominante Flexion gemodellt).
# Par.31 leitet den Stamm aus dem Masc.Nom.Sg. ab (der trägt den Grundakzent, der
# Gen.Sg. ist dort mobil), die übrigen aus dem Gen.Sg.
TARGETS = {
    "25": ("Adj",  "AdjFixed",  "AdjFixedInfl",  "Genitive",   "as"),
    "26": ("Adj",  "AdjMobile", "AdjMobileInfl", "Genitive",   "as"),
    "27": ("Adj",  "AdjI",      "AdjIInfl",      "Genitive",   "jas"),
    "29": ("Adj",  "AdjIMob",   "AdjIMobInfl",   "Genitive",   "is"),
    "31": ("Adj",  "AdjUMob",   "AdjUMobInfl",   "Nominative", "us"),
    "69": ("Pass", "PartPass",  "PartPassInfl",  "Genitive",   "as"),
    "68": ("Past",  "PartAct",   "PartActInfl",   "Nominative", "uns"),
}
# Alle Stamm-Lexika, auf die LEXICON Root in gen/adj.lexc verweist — der generierte
# Block muss sie (ggf. leer) definieren, damit die Referenzen auflösen.
STEM_LEXICONS = ["AdjFixed", "AdjMobile", "AdjI", "AdjIMob", "AdjUMob",
                 "PartPass", "PartAct", "AdjCmpStems", "AdjSupStems"]

# Komparativ/Superlativ: i-/jo-Deklination (fix), unabhängig vom Basis-Paradigma.
# Der Komparativ-Stamm = Komparativ Masc.Gen.Sg. minus -jas; der Superlativ-Stamm
# = "uka" + Komparativ-Stamm (100 % regelhaft). Diese Paradigmen tragen eine
# Gradtafel (forms.comparative/forms.superlative).
DEGREE_PARADIGMS = {"25", "26", "27", "30", "31"}

GEN = {"m": "Masc", "f": "Fem", "n": "Neut"}
CASES = ["Nom", "Gen", "Dat", "Acc"]
CA = {"Nominative": "Nom", "Genitive": "Gen", "Dative": "Dat", "Accusative": "Acc"}


def primary(cell: str) -> str:
    return (cell or "").split(" / ")[0].strip()


def analysis(lemma: str, typ: str, g: str, n: str, c: str) -> str:
    """Analyse-String: Adjektive tragen +Adj, Partizipien +Part+Typ."""
    if typ == "Adj":
        return f"{lemma}+Adj+{g}+{n}+{c}"
    return f"{lemma}+Part+{typ}+{g}+{n}+{c}"


def load_targets() -> list[dict]:
    entries = json.loads(TWANKSTA.read_text())
    out, seen = [], set()
    excluded = 0
    for e in entries:
        para = e.get("paradigm")
        if para not in TARGETS:
            continue
        decl = e.get("forms", {}).get("declension") or []
        blocks = {b.get("gender"): b for b in decl}
        lemma = e.get("word", "")
        _, _, _, src_case, end = TARGETS[para]
        if " " in lemma or "/" in lemma or set("mfn") - set(blocks):
            excluded += 1
            continue
        # Referenzformen je Genus/Slot
        forms = {}
        for g, b in blocks.items():
            for c in b.get("cases", []):
                ca = CA.get(c.get("case", ""))
                if not ca:
                    continue
                forms[(GEN[g], f"Sg+{ca}")] = primary(c.get("singular"))
                forms[(GEN[g], f"Pl+{ca}")] = primary(c.get("plural"))
        # Stamm aus Masc-Quellslot minus Klassenendung
        src = ""
        for c in blocks["m"].get("cases", []):
            if c.get("case") == src_case:
                src = primary(c.get("singular"))
        if not src.endswith(end) or len(forms) < 24:
            excluded += 1
            continue
        stem = src[: -len(end)]
        if (lemma, para) in seen:
            continue
        seen.add((lemma, para))
        out.append({"lemma": lemma, "para": para, "stem": stem, "forms": forms})
    print(f"Ziel-Lexeme: {len(out)}  (ausgeschlossen: {excluded})")
    return out


def load_degree_targets() -> list[dict]:
    """Komparativ-/Superlativ-Lexeme (Gradtafel) mit abgeleitetem Stamm + Referenzformen.

    Der Komparativ-Stamm = Komparativ Masc.Gen.Sg. minus -jas (i-/jo-Stamm für ALLE
    Basis-Paradigmen); der Superlativ-Stamm = "uka" + Komparativ-Stamm. Ausschluss:
    Mehrwort/Slash, fehlender Masc-Block, oder eine Komparativ-Quellform ohne -jas
    (die Suppletiva labs→walns, līkuts→mazs, debīks→māises sind a-stämmig/regellos).
    """
    entries = json.loads(TWANKSTA.read_text())
    out, seen = [], set()
    excluded = 0
    for e in entries:
        para = e.get("paradigm")
        if para not in DEGREE_PARADIGMS:
            continue
        cmp_decl = e.get("forms", {}).get("comparative")
        sup_decl = e.get("forms", {}).get("superlative")
        if not cmp_decl or not sup_decl:
            continue
        lemma = e.get("word", "")
        cmp_blocks = {b.get("gender"): b for b in cmp_decl}
        sup_blocks = {b.get("gender"): b for b in sup_decl}
        if " " in lemma or "/" in lemma or set("mfn") - set(cmp_blocks):
            excluded += 1
            continue
        csrc = ""
        for c in cmp_blocks["m"].get("cases", []):
            if c.get("case") == "Genitive":
                csrc = primary(c.get("singular"))
        if not csrc.endswith("jas"):
            excluded += 1
            continue
        cmp_stem = csrc[: -len("jas")]
        sup_stem = "uka" + cmp_stem
        cmp_forms, sup_forms = {}, {}
        for g in ("m", "f", "n"):
            for c in cmp_blocks[g].get("cases", []):
                ca = CA.get(c.get("case", ""))
                if not ca:
                    continue
                cmp_forms[(GEN[g], f"Sg+{ca}")] = primary(c.get("singular"))
                cmp_forms[(GEN[g], f"Pl+{ca}")] = primary(c.get("plural"))
            for c in sup_blocks[g].get("cases", []):
                ca = CA.get(c.get("case", ""))
                if not ca:
                    continue
                sup_forms[(GEN[g], f"Sg+{ca}")] = primary(c.get("singular"))
                sup_forms[(GEN[g], f"Pl+{ca}")] = primary(c.get("plural"))
        if len(cmp_forms) < 24 or len(sup_forms) < 24:
            excluded += 1
            continue
        if (lemma, para) in seen:
            continue
        seen.add((lemma, para))
        out.append({"lemma": lemma, "para": para, "cmp_stem": cmp_stem,
                    "sup_stem": sup_stem, "cmp_forms": cmp_forms,
                    "sup_forms": sup_forms})
    print(f"Grad-Lexeme (Komp/Sup): {len(out)}  (ausgeschlossen: {excluded})")
    return out


def stems_block(targets: list[dict], degree_targets: list[dict] | None = None) -> str:
    """Aus twanksta inventarisierte Stämme als LEXICON-Block (Lemma:Stamm  …Infl ;).

    Die Grammatik (Endungen) steht datenfrei in gen/adj.lexc; ihr LEXICON Root
    verweist auf die Stamm-Lexika, die hier erzeugt werden — Hand (Grammatik) und
    Daten (Stämme) sind getrennt. Alle STEM_LEXICONS werden (ggf. leer) definiert.
    degree_targets trägt zusätzlich Komparativ-/Superlativ-Stämme in die
    AdjCmpStems/AdjSupStems ein (die uka-Präfix-Mechanik wird einmalig angewendet:
    SupStamm = "uka" + Komparativ-Stamm).
    """
    stems: dict[str, list[str]] = {sl: [] for sl in STEM_LEXICONS}
    for t in targets:
        _, stem_lex, infl, _, _ = TARGETS[t["para"]]
        stems[stem_lex].append(f"  {t['lemma']}:{t['stem']}  {infl} ;")
    for t in degree_targets or []:
        stems["AdjCmpStems"].append(f"  {t['lemma']}:{t['cmp_stem']}  AdjCmpInfl ;")
        stems["AdjSupStems"].append(f"  {t['lemma']}:{t['sup_stem']}  AdjSupInfl ;")
    body = ["! === Aus twanksta generierte Stämme — NICHT von Hand editieren ===",
            "! (erzeugt von gen/coverage_adj.py --emit-stems; Grammatik: gen/adj.lexc)"]
    for stem_lex in STEM_LEXICONS:
        body.append(f"LEXICON {stem_lex}")
        body.extend(stems[stem_lex] or ["  0:0  # ;"])
        body.append("")
    return "\n".join(body) + "\n"


def write_combined(targets: list[dict], degree_targets: list[dict]) -> Path:
    """Datenfreie Grammatik gen/adj.lexc + generierter Stamm-Block → build/-lexc."""
    combined = LEXC.read_text().rstrip() + "\n\n" + stems_block(targets, degree_targets)
    out = BUILD / "gen-adjcov.lexc"
    out.write_text(combined)
    return out


def build(lexc: Path) -> Path:
    fst = BUILD / "gen-adjcov.fst"
    composed = BUILD / "gen-adjcov.composed.fst"
    hfstol = BUILD / "gen-adjcov.gen.hfstol"
    if not ACCENT.exists():
        subprocess.run(HFST + ["xfst", str(ROOT / "gen" / "accent.regex")], check=True)
    subprocess.run(HFST + ["lexc", str(lexc), str(fst)], check=True)
    subprocess.run(HFST + ["compose", str(composed), str(fst), str(ACCENT)], check=True)
    subprocess.run(HFST + ["hfstol-gen", str(composed), str(hfstol)], check=True)
    return hfstol


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--show", type=int, default=15)
    ap.add_argument("--emit-stems", metavar="PATH",
                    help="nur den generierten Stamm-Block nach PATH schreiben "
                         "(für den Build) und beenden — kein Deckungstest")
    args = ap.parse_args()

    targets = load_targets()
    degree_targets = load_degree_targets()

    if args.emit_stems:
        Path(args.emit_stems).write_text(stems_block(targets, degree_targets))
        print(f"Stämme geschrieben: {args.emit_stems} ({len(targets)} Positiv-, "
              f"{len(degree_targets)} Grad-Lexeme)")
        return

    hfstol = build(write_combined(targets, degree_targets))
    queries = [analysis(t["lemma"], TARGETS[t["para"]][0], g, n, c)
               for t in targets for g in ("Masc", "Fem", "Neut")
               for n in ("Sg", "Pl") for c in CASES]
    queries += [f"{t['lemma']}+Adj+{deg}+{g}+{n}+{c}"
                for t in degree_targets for deg in ("Cmp", "Sup")
                for g in ("Masc", "Fem", "Neut") for n in ("Sg", "Pl")
                for c in CASES]
    gen = glookup_batch(queries, str(hfstol))

    total = hit = 0
    per = Counter(); per_hit = Counter(); miss_slot = Counter(); misses = []
    for t in targets:
        typ = TARGETS[t["para"]][0]
        for g in ("Masc", "Fem", "Neut"):
            for n in ("Sg", "Pl"):
                for c in CASES:
                    want = t["forms"].get((g, f"{n}+{c}"))
                    if not want:
                        continue
                    total += 1; per[t["para"]] += 1
                    a = analysis(t["lemma"], typ, g, n, c)
                    ok = want in gen.get(a, [])
                    hit += ok; per_hit[t["para"]] += ok
                    if not ok:
                        miss_slot[f"{g} {n}+{c}"] += 1
                        misses.append(f"  {t['lemma']}[{t['para']}] {g} {n}+{c}: "
                                      f"{want!r} ≠ {(gen.get(a) or ['∅'])[0]!r}")
    print(f"\nDeckung Positiv gesamt: {hit}/{total} ({100*hit/total:.1f}%)")
    for para in TARGETS:
        if per[para]:
            print(f"  Par.{para}: {per_hit[para]}/{per[para]} "
                  f"({100*per_hit[para]/per[para]:.1f}%)")
    if miss_slot:
        print("\nPositiv-Abweichungen je Slot:", dict(miss_slot.most_common()))
    if misses:
        print(f"\nPositiv-Beispiele (erste {args.show}):")
        print("\n".join(misses[: args.show]))

    # Komparativ/Superlativ
    for deg, key in (("Cmp", "cmp_forms"), ("Sup", "sup_forms")):
        total = hit = 0
        per = Counter(); per_hit = Counter(); deg_misses = []
        for t in degree_targets:
            for g in ("Masc", "Fem", "Neut"):
                for n in ("Sg", "Pl"):
                    for c in CASES:
                        want = t[key].get((g, f"{n}+{c}"))
                        if not want:
                            continue
                        total += 1; per[t["para"]] += 1
                        a = f"{t['lemma']}+Adj+{deg}+{g}+{n}+{c}"
                        ok = want in gen.get(a, [])
                        hit += ok; per_hit[t["para"]] += ok
                        if not ok:
                            deg_misses.append(f"  {t['lemma']}[{t['para']}] "
                                              f"{g} {n}+{c}: {want!r} ≠ "
                                              f"{(gen.get(a) or ['∅'])[0]!r}")
        print(f"\nDeckung {deg} gesamt: {hit}/{total} ({100*hit/total:.1f}%)")
        for para in sorted(DEGREE_PARADIGMS):
            if per[para]:
                print(f"  Par.{para}: {per_hit[para]}/{per[para]} "
                      f"({100*per_hit[para]/per[para]:.1f}%)")
        if deg_misses:
            print(f"\n{deg}-Beispiele (erste {args.show}):")
            print("\n".join(deg_misses[: args.show]))


if __name__ == "__main__":
    main()
