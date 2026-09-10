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
import re
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
    "ustem": (ROOT / "gen" / "ustem.lexc", {
        "42": ("P42Stems", "P42", "us"),
        "43": ("P43Stems", "P43", "us"),
        "44": ("P44Stems", "P44", "us"),
    }),
    "jostem": (ROOT / "gen" / "jostem.lexc", {
        "40": ("P40Stems", "P40", "jas"),
        "41": ("P41Stems", "P41", "jas"),
        "37": ("P37Stems", "P37", "jas"),
        "38": ("P38Stems", "P38", "jas"),
        "39": ("P39Stems", "P39", "ijjas"),
    }),
    # ā/jā/ī-Familie fem. Par.46 = konsonantischer Stamm, Themavokal-Länge in der
    # Endung (Nom.Sg./Dat.Pl. -ā, sonst -a) — keine Stammreduktion.
    "aastem": (ROOT / "gen" / "aastem.lexc", {
        "45": ("P45Stems", "P45", "s"),
        "46": ("P46Stems", "P46", "as"),
        "50": ("P50Stems", "P50", "jas"),
        "51": ("P51Stems", "P51", "jas"),
    }),
    "nstem": (ROOT / "gen" / "nstem.lexc", {
        "61": ("P61Stems", "P61", "es"),
        "63": ("P63Stems", "P63", "es"),
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


def nom_exception_lemmas() -> set[str]:
    """Lemmata mit hand-gepflegtem Nom.Sg. aus LEXICON NomSg der lexc-Datei.

    Die Ausnahmen leben im lexc selbst (LEXICON NomSg: fertige Nom.Sg.-Oberflächen);
    ihre obliquen Formen werden hier auto-inventarisiert, aber auf die -_o-Klasse
    (ohne Nom.Sg.) geleitet, damit der Nom.Sg. allein aus NomSg kommt.
    """
    text = LEXC.read_text()
    m = re.search(r"^LEXICON NomSg\b(.*?)(?=^LEXICON |\Z)", text, re.M | re.S)
    if not m:
        return set()
    return set(re.findall(r"^\s*(\S+?)\+N\+", m.group(1), re.M))


def load_targets() -> tuple[list[dict], list[dict]]:
    """Lexeme der Ziel-Paradigmen mit abgeleitetem Stamm + Referenzformen.

    Rückgabe: (targets, data_errors). data_errors sind Twanksta-Lexeme mit
    identitäts-kollabierter Deklinationstabelle (alle Zellen = Lemma) — ein
    Twanksta-Datenfehler, kein Generatorfehler; aus der Deckung ausgenommen.
    """
    entries = json.loads(TWANKSTA.read_text())
    out, seen = [], set()
    data_errors: list[dict] = []
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
        spec = TARGETS[para]
        gen_end = spec[2]
        # Optionaler 4. Eintrag: aus welchem Slot der Stamm abgeleitet wird
        # (Default Gen.Sg.; Par.46 z. B. aus dem schweren Nom.Sg.).
        source = spec[3] if len(spec) > 3 else "Sg+Gen"
        srcform = forms.get(source, "")
        # Ausschluss: Mehrwort/Slash (lexc-Symbole ohne Leerzeichen), fehlendes
        # Genus, unvollständige Formen, oder Quellform ohne erwartete Klassenendung.
        if (" " in lemma or "/" in lemma or not gender
                or len(forms) < 8 or not srcform.endswith(gen_end)):
            excluded += 1
            continue
        stem = srcform[: -len(gen_end)] if gen_end else srcform
        key = (lemma, para, stem, gender)
        if key in seen:
            continue
        seen.add(key)
        # Identitäts-Kollaps (alle Zellen gleich) = Twanksta-Datenfehler, nicht zählen.
        if len({v for v in forms.values() if v}) <= 1:
            data_errors.append({"lemma": lemma, "para": para})
            continue
        out.append({"lemma": lemma, "para": para, "stem": stem,
                    "gender": gender, "forms": forms})
    print(f"Ziel-Lexeme: {len(out)}  (ausgeschlossen: {excluded} — "
          f"Mehrwort/Slash/unvollständig; {len(data_errors)} Twanksta-Datenfehler)")
    return out, data_errors


def stems_block(targets: list[dict], nom_exc: set[str]) -> str:
    """Aus twanksta inventarisierte Stämme als LEXICON PxxStems-Block.

    Die Grammatik (Endungen, Ausnahmen) steht datenfrei in gen/<fam>.lexc; ihr
    LEXICON Root verweist auf die PxxStems, die hier aus den realen Lexemen
    erzeugt werden — so ist getrennt, was Hand (Grammatik) und was Daten (Stämme)
    ist. Lemmata mit hand-gepflegtem Nom.Sg. (nom_exc, aus LEXICON NomSg) werden
    auf die -_o-Klasse geleitet (obliquer Stamm ohne Nom.Sg.); ihr Nom.Sg. kommt
    aus NomSg.
    """
    stems = {spec[0]: [] for spec in TARGETS.values()}
    for t in targets:
        stem_lex, infl = TARGETS[t["para"]][:2]
        if t["lemma"] in nom_exc:
            infl += "_o"
        stems[stem_lex].append(
            f"  {t['lemma']}+N+{t['gender']}:{t['stem']}  {infl} ;")

    body = ["! === Aus twanksta generierte Stämme — NICHT von Hand editieren ===",
            "! (erzeugt von gen/coverage_gen.py --emit-stems; die Grammatik mit den",
            "!  Endungen/Ausnahmen steht datenfrei in gen/" + FAMILY + ".lexc)"]
    for root_lex, lines in stems.items():
        body.append(f"LEXICON {root_lex}")
        body.extend(lines)
        body.append("")
    return "\n".join(body) + "\n"


def write_combined(targets: list[dict], nom_exc: set[str]) -> Path:
    """Grammatikdatei + generierter Stamm-Block → kompilierbares build/-lexc.

    Kein Marker-Splicing mehr: die ganze (datenfreie) Grammatik wird verbatim
    übernommen und der Stamm-Block angehängt. LEXICON Root der Grammatik verweist
    auf die PxxStems, die der angehängte Block definiert (Reihenfolge egal in lexc).
    """
    combined = LEXC.read_text().rstrip() + "\n\n" + stems_block(targets, nom_exc)
    out = BUILD / f"gen-{FAMILY}-cov.lexc"
    out.write_text(combined)
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
    ap.add_argument("--emit-stems", metavar="PATH",
                    help="nur den generierten LEXICON PxxStems-Block nach PATH "
                         "schreiben (für den Build) und beenden — kein Deckungstest")
    args = ap.parse_args()

    global FAMILY, LEXC, TARGETS
    FAMILY = args.family
    LEXC, TARGETS = FAMILIES[FAMILY]

    nom_exc = nom_exception_lemmas()
    targets, data_errors = load_targets()

    if args.emit_stems:
        Path(args.emit_stems).write_text(stems_block(targets, nom_exc))
        print(f"Stämme geschrieben: {args.emit_stems} ({len(targets)} Lexeme)")
        return

    hfstol = build(write_combined(targets, nom_exc))

    queries = [f"{t['lemma']}+N+{t['gender']}+{n}+{c}"
               for t in targets for n in ("Sg", "Pl") for c in CASES]
    gen = glookup_batch(queries, str(hfstol))

    hit_exc = sum(1 for t in targets if t["lemma"] in nom_exc)
    print(f"Nom.Sg.-Ausnahmen (LEXICON NomSg): {len(nom_exc)} deklariert, "
          f"{hit_exc} unter den Ziel-Lexemen")

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

    if data_errors:
        print(f"\nTwanksta-Datenfehler (nicht Generatorfehler, {len(data_errors)} "
              f"— identitäts-kollabierte Tabelle):")
        for d in data_errors:
            print(f"  {d['lemma']}[{d['para']}]")


if __name__ == "__main__":
    main()
