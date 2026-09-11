"""Nicht-zirkulärer Deckungstest für die adjektivisch deklinierten Wortarten.

Deckt die a-stämmigen Adjektive (Par.25 fest, Par.26 mobil) UND die Partizipien
(Par.68 aktiv -uns, Par.69 passiv -ts) ab — alle mit DREI Genusblöcken (24 Formen).
Par.27/29/31 (i-/jo-/u-Stamm-Adjektive) haben eigene Deklinationen und noch kein
Endungslexikon (siehe TARGETS-Kommentar) — bewusst ausgelassen, nicht falsch generiert. Wie
beim Nomen (gen/coverage_gen.py) ist die Grammatik hand-geschrieben und datenfrei
(gen/adj.lexc: Endungslexika + Genusblöcke); hier wird nur die STAMM-Inventari-
sierung skaliert: für jedes reale Lexem wird der Stamm aus dem Masc-Block abge-
leitet, an die Grammatik gehängt, kompiliert, mit gen/accent.regex komponiert und
die 24 Formen exakt gegen Twanksta verglichen.

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
# Tag-Typ "Adj" → +Adj+…; "Pass"/"Act" → +Part+Pass/Act+…. Stamm = Masc-Quellform
# minus Klassenendung. Par.25 = festes a-Stamm-Adjektiv, Par.26 = mobiles a-Stamm-
# Adjektiv, Par.68/69 = Partizipien.
#
# NOCH NICHT modelliert (eigene Deklination, kein passendes Endungslexikon in
# gen/adj.lexc — würden falsch generiert, daher hier ausgelassen):
#   Par.27  i-/jo-Stamm-Adjektiv  (Fem -i/-is/-ei/-in; z. T. mit jo-Endungen)
#   Par.29  mobiles i-Stamm-Adjektiv (Gen.Sg -is, Dat.Sg -ismu, ā/mm-mobil)
#   Par.31  u-Stamm-Adjektiv     (Nom -us, w-Gleitlaut, mobil)
TARGETS = {
    "25": ("Adj",  "AdjFixed",  "AdjFixedInfl",  "Genitive",   "as"),
    "26": ("Adj",  "AdjMobile", "AdjMobileInfl", "Genitive",   "as"),
    "69": ("Pass", "PartPass",  "PartPassInfl",  "Genitive",   "as"),
    "68": ("Act",  "PartAct",   "PartActInfl",   "Nominative", "uns"),
}
# Alle Stamm-Lexika, auf die LEXICON Root in gen/adj.lexc verweist — der generierte
# Block muss sie (ggf. leer) definieren, damit die Referenzen auflösen.
STEM_LEXICONS = ["AdjFixed", "AdjMobile", "PartPass", "PartAct"]
GEN = {"m": "Masc", "f": "Fem", "n": "Neut"}
CASES = ["Nom", "Gen", "Dat", "Akk"]
CA = {"Nominative": "Nom", "Genitive": "Gen", "Dative": "Dat", "Accusative": "Akk"}


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


def stems_block(targets: list[dict]) -> str:
    """Aus twanksta inventarisierte Stämme als LEXICON-Block (Lemma:Stamm  …Infl ;).

    Die Grammatik (Endungen) steht datenfrei in gen/adj.lexc; ihr LEXICON Root
    verweist auf die Stamm-Lexika, die hier erzeugt werden — Hand (Grammatik) und
    Daten (Stämme) sind getrennt. Alle STEM_LEXICONS werden (ggf. leer) definiert.
    """
    stems: dict[str, list[str]] = {sl: [] for sl in STEM_LEXICONS}
    for t in targets:
        _, stem_lex, infl, _, _ = TARGETS[t["para"]]
        stems[stem_lex].append(f"  {t['lemma']}:{t['stem']}  {infl} ;")
    body = ["! === Aus twanksta generierte Stämme — NICHT von Hand editieren ===",
            "! (erzeugt von gen/coverage_adj.py --emit-stems; Grammatik: gen/adj.lexc)"]
    for stem_lex in STEM_LEXICONS:
        body.append(f"LEXICON {stem_lex}")
        body.extend(stems[stem_lex])
        body.append("")
    return "\n".join(body) + "\n"


def write_combined(targets: list[dict]) -> Path:
    """Datenfreie Grammatik gen/adj.lexc + generierter Stamm-Block → build/-lexc."""
    combined = LEXC.read_text().rstrip() + "\n\n" + stems_block(targets)
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

    if args.emit_stems:
        Path(args.emit_stems).write_text(stems_block(targets))
        print(f"Stämme geschrieben: {args.emit_stems} ({len(targets)} Lexeme)")
        return

    hfstol = build(write_combined(targets))
    queries = [analysis(t["lemma"], TARGETS[t["para"]][0], g, n, c)
               for t in targets for g in ("Masc", "Fem", "Neut")
               for n in ("Sg", "Pl") for c in CASES]
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
    print(f"\nDeckung gesamt: {hit}/{total} ({100*hit/total:.1f}%)")
    for para in TARGETS:
        if per[para]:
            print(f"  Par.{para}: {per_hit[para]}/{per[para]} "
                  f"({100*per_hit[para]/per[para]:.1f}%)")
    if miss_slot:
        print("\nAbweichungen je Slot:", dict(miss_slot.most_common()))
    if misses:
        print(f"\nBeispiele (erste {args.show}):")
        print("\n".join(misses[: args.show]))


if __name__ == "__main__":
    main()
