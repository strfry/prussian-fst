"""Erweiterter, nicht-zirkulärer Deckungstest für den handgeschriebenen i-Stamm-FST.

Im Unterschied zu gen/paradigm_survey.py (das Endungen aus den Daten LERNT und
gegen dieselben Daten prüft) sind hier Endungen und Akzentregel von Hand
formuliert (gen/istem.lexc + gen/accent.regex). Der Test skaliert nur die
STAMM-Inventarisierung: für jedes reale Twanksta-Lexem der Ziel-Paradigmen wird
der Stamm mechanisch abgeleitet (Gen.Sg. minus Klassenendung) und in die
HANDGESCHRIEBENEN Endungslexika eingespeist. Gemessen wird dann, welcher Anteil
der 8 Formen je Lexem exakt reproduziert wird — echte Deckung, nicht
Selbstkonsistenz.

    uv run python gen/coverage_gen.py            # Gesamtdeckung + Abweichungen
    uv run python gen/coverage_gen.py --show 40  # bis zu 40 Abweichungen zeigen
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
ACCENT = ROOT / "build" / "gen-accent.hfst"
BUILD = ROOT / "build"
HFST = ["uv", "run", "python", str(ROOT / "src" / "prussian_fst" / "build_fst.py")]
STEMS_MARKER = "! >>> STÄMME"
ENDINGS_MARKER = "! >>> ENDUNGEN"

# Stammfamilien → lexc-Datei + Ziel-Paradigmen. Je Paradigma:
# (Stamm-Lexikon, Endungslexikon, Klassenendung im Gen.Sg. zum Abtrennen).
# Der Stamm = Gen.Sg. minus dieser Endung (Gen.Sg. trägt den Grundakzent).
# Ein Endungslexikon pro Twanksta-Paradigmennummer.
FAMILIES = {
    "istem": (ROOT / "gen" / "istem.lexc", {
        "52": ("P52Stems", "P52", "is"),
        "53": ("P53Stems", "P53", "is"),
        "54": ("P54Stems", "P54", "is"),
        "56": ("P56Stems", "P56", "is"),
        "57": ("P57Stems", "P57", "is"),
        "58": ("P58Stems", "P58", "is"),
        "60": ("P60Stems", "P60", "is"),
    }),
    "astem": (ROOT / "gen" / "astem.lexc", {
        "32": ("P32Stems", "P32", "as"),
        "35": ("P35Stems", "P35", "as"),
        "36": ("P36Stems", "P36", "as"),
    }),
}

# Werden in main() aus --family gesetzt.
FAMILY = "istem"
LEXC = FAMILIES["istem"][0]
TARGETS = FAMILIES["istem"][1]
GENDER = {"masc": "Masc", "fem": "Fem", "neut": "Neut"}
CASES = ["Nom", "Gen", "Dat", "Akk"]
CA = {"Nominative": "Nom", "Genitive": "Gen", "Dative": "Dat", "Accusative": "Akk"}


def primary(cell: str) -> str:
    return (cell or "").split(" / ")[0].strip()


def load_targets() -> list[dict]:
    """Lexeme der Ziel-Paradigmen mit abgeleitetem Stamm + Referenzformen."""
    entries = json.loads(TWANKSTA.read_text())
    out, seen = [], set()
    excluded = 0
    for e in entries:
        para = e.get("paradigm")
        if para not in TARGETS:
            continue
        decl = e.get("forms", {}).get("declension")
        if not decl:
            continue
        block = decl[0]
        gender = GENDER.get(e.get("gender") or block.get("gender") or "")
        lemma = e.get("word", "")
        forms = {}
        for c in block.get("cases", []):
            case = CA.get(c.get("case", ""))
            if not case:
                continue
            forms[f"Sg+{case}"] = primary(c.get("singular"))
            forms[f"Pl+{case}"] = primary(c.get("plural"))
        gensg = forms.get("Sg+Gen", "")
        _, _, gen_end = TARGETS[para]
        # Ausschluss: Mehrwort/Slash (lexc-Symbole ohne Leerzeichen), fehlendes
        # Genus, unvollständige Formen, oder Gen.Sg. ohne erwartete Klassenendung.
        if (" " in lemma or "/" in lemma or not gender
                or len(forms) < 8 or not gensg.endswith(gen_end)):
            excluded += 1
            continue
        stem = gensg[: -len(gen_end)]
        key = (lemma, para, stem, gender)
        if key in seen:
            continue
        seen.add(key)
        out.append({"lemma": lemma, "para": para, "stem": stem,
                    "gender": gender, "forms": forms})
    print(f"Ziel-Lexeme: {len(out)}  (ausgeschlossen: {excluded} — "
          f"Mehrwort/Slash/unvollständig)")
    return out


def write_lexc(targets: list[dict]) -> Path:
    """Handgeschriebene Endungen + auto-inventarisierte Stämme → build/-lexc."""
    text = LEXC.read_text()
    preamble = text[: text.index(STEMS_MARKER)]
    endings = text[text.index(ENDINGS_MARKER):]

    stems = {name: [] for name, _, _ in TARGETS.values()}
    for t in targets:
        stem_lex, infl, _ = TARGETS[t["para"]]
        stems[stem_lex].append(
            f"  {t['lemma']}+N+{t['gender']}:{t['stem']}  {infl} ;")

    body = []
    for root_lex, lines in stems.items():
        body.append(f"LEXICON {root_lex}")
        body.extend(lines)
        body.append("")

    out = BUILD / f"gen-{FAMILY}-cov.lexc"
    out.write_text(preamble + "\n".join(body) + "\n" + endings)
    return out


def build(lexc: Path) -> Path:
    fst = BUILD / f"gen-{FAMILY}-cov.fst"
    composed = BUILD / f"gen-{FAMILY}-cov.composed.fst"
    hfstol = BUILD / f"gen-{FAMILY}-cov.gen.hfstol"
    if not ACCENT.exists():
        subprocess.run(HFST + ["xfst", str(ROOT / "gen" / "accent.regex")], check=True)
    subprocess.run(HFST + ["lexc", str(lexc), str(fst)], check=True)
    subprocess.run(HFST + ["compose", str(composed), str(fst), str(ACCENT)], check=True)
    subprocess.run(HFST + ["hfstol-gen", str(composed), str(hfstol)], check=True)
    return hfstol


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--family", choices=sorted(FAMILIES), default="istem",
                    help="Stammfamilie (istem, astem, …)")
    ap.add_argument("--show", type=int, default=15, help="max. Abweichungen zeigen")
    args = ap.parse_args()

    global FAMILY, LEXC, TARGETS
    FAMILY = args.family
    LEXC, TARGETS = FAMILIES[FAMILY]

    targets = load_targets()
    hfstol = build(write_lexc(targets))

    queries = [f"{t['lemma']}+N+{t['gender']}+{n}+{c}"
               for t in targets for n in ("Sg", "Pl") for c in CASES]
    gen = glookup_batch(queries, str(hfstol))

    total = hit = 0
    per_para = Counter()
    per_para_hit = Counter()
    miss_slot = Counter()
    misses = []
    for t in targets:
        for n in ("Sg", "Pl"):
            for c in CASES:
                a = f"{t['lemma']}+N+{t['gender']}+{n}+{c}"
                want = t["forms"].get(f"{n}+{c}")
                if not want:
                    continue
                total += 1
                per_para[t["para"]] += 1
                ok = want in gen.get(a, [])
                hit += ok
                per_para_hit[t["para"]] += ok
                if not ok:
                    miss_slot[f"{n}+{c}"] += 1
                    misses.append(f"  {t['lemma']}[{t['para']}] {n}+{c}: "
                                  f"erwartet {want!r}, generiert {gen.get(a) or '∅'}")

    print(f"\nDeckung gesamt: {hit}/{total} ({100*hit/total:.1f}%)")
    for para in TARGETS:
        n = per_para[para]
        if n:
            print(f"  Par.{para}: {per_para_hit[para]}/{n} "
                  f"({100*per_para_hit[para]/n:.1f}%)")
    if miss_slot:
        print("\nAbweichungen je Slot:", dict(miss_slot.most_common()))
    if misses:
        print(f"\nBeispiel-Abweichungen (erste {args.show}):")
        print("\n".join(misses[: args.show]))


if __name__ == "__main__":
    main()
