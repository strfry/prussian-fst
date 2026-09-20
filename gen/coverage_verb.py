"""Nicht-zirkulärer Deckungstest für die finiten Verben (synthetische Formen).

Wie bei den Nomen/Adjektiven ist die Grammatik (Endungstabellen) datenfrei in
gen/verb.lexc formuliert; hier wird nur die STAMM-Inventarisierung skaliert. Verben
haben — anders als Nomen — ZWEI Stämme je Lexem (Präsens- vs. Nicht-Präsens-Stamm),
weil die Stamm-Allomorphie (Geminations-Blockierung, -īn-Kürzung, -au-/-ā-/-ī-
Suffix, Ablaut) nicht allein über die Akzentregel erfasst werden kann. Beide Stämme
werden mechanisch aus je einer Twanksta-Oberfläche abgeleitet (Present-P3 bzw.
Subjunktiv-P3 minus Klassenendung) und an die handgeschriebenen Endungslexika
gehängt; gemessen wird die exakte Reproduktion aller synthetischen Formen.

Erzeugte Formen (kanonische Reihenfolge Mood/Tense/Person/Number, P3 ohne Numerus):
  +V+Ind+Pres+{Pers}[+{Num}], +V+Ind+Pret+{Pers}[+{Num}],
  +V+Subj+{Pers}[+{Num}], +V+Opt+P3, +V+Imp+P2+{Num}.
Perfect/Future sind periphrastisch und werden NICHT generiert.

    uv run python gen/coverage_verb.py [--show N]
    uv run python gen/coverage_verb.py --emit-stems build/gen-verb-stems.lexc
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
LEXC = ROOT / "gen" / "verb.lexc"
ACCENT = ROOT / "build" / "gen-accent.hfst"
BUILD = ROOT / "build"
HFST = ["uv", "run", "python", str(ROOT / "src" / "prussian_fst" / "build_fst.py")]

# Paradigma → Stamm-Spezifikation. Jeder Eintrag ist ein Paar
# (Stamm-Lexikon, Endungs-Lexikon, Quellform, abzutrennende Klassenendung).
# Quellform: "pres" = Present-P3, "subj" = Subjunktiv-P3. Der fin-Stamm trägt
# die Präsens-Allomorphie schon vorgefertigt (z. B. Par.85 -inn-), der nonfin-
# Stamm die Optativ-/Subjunktiv-Stammform (z. B. Par.85 -in-, Par.143 -au).
PARADIGMS = {
    "85":  [("P85FinStems",  "P85Fin",  "pres", "a"),
            ("P85SubjStems", "P85Subj", "subj", "lai")],
    "132": [("P132FinStems",  "P132Fin",  "pres", "i"),
            ("P132SubjStems", "P132Subj", "subj", "lai")],
    "138": [("P138FinStems",  "P138Fin",  "pres", "i"),
            ("P138SubjStems", "P138Subj", "subj", "lai")],
    "134": [("P134FinStems",  "P134Fin",  "pres", "i"),
            ("P134SubjStems", "P134Subj", "subj", "lai")],
    "139": [("P139FinStems",  "P139Fin",  "pres", "a"),
            ("P139SubjStems", "P139Subj", "subj", "lai")],
    "143": [("P143PresStems", "P143Pres", "pres", "ui"),
            ("P143PastStems", "P143Past", "subj", "lai")],
    # Par.131 (-au-/-a- Denominativa, Präs=Pret) teilt die Par.132-Endungstabelle
    # (Präs -i/-imai/-itei, Opt -sei, Imp -is/-iti, Subj -lai/…); nur die Stämme
    # kommen aus einem anderen Paradigma. Gleiche Endungen = gleiche Lexikon-Paare.
    "131": [("P132FinStems",  "P132Fin",  "pres", "i"),
            ("P132SubjStems", "P132Subj", "subj", "lai")],
}

# Twanksta-Paradigmen-Labels mit Varianten-Suffix (identische Flexion zur
# Basis-Nummer) bzw. Tippfehler auf die Basis normalisiert.
PARA_ALIAS = {"75b": "75", "134a": "134", "75a": "75", "76s": "76",
              "80b": "80", "81a": "81", "81b": "81", "81c": "81",
              "97a": "97", "102a": "102", "106b": "106", "137a": "137"}

# Pronomen → Person-Nummer-Tag (kanonisch, vgl. gen_lexc.PERSON_TAGS).
PRONOUN = {
    "as": "P1+Sg",
    "tū": "P2+Sg",
    "tāns/tenā/tennan": "P3",
    "mes": "P1+Pl",
    "jūs": "P2+Pl",
}
# P3 (tenēi/tennas) ist numerus-los und formgleich zum Sg. — nur EIN Abfrageschlitz.
PERSONS = ["as", "tū", "tāns/tenā/tennan", "mes", "jūs"]


def primary(cell: str) -> str:
    return (cell or "").split(" / ")[0].strip()


def strip_si(form: str) -> str:
    if form.endswith(" si"):
        return form[:-3]
    return form


def load_targets() -> tuple[list[dict], int, int]:
    """Verb-Lexeme der Ziel-Paradigmen mit zwei abgeleiteten Stämmen.

    Rückgabe (targets, excluded, data_errors). Der fin-Stamm = Present-P3 minus
    Klassenendung, der nonfin-Stamm = Subjunktiv-P3 minus deren Endung. Reflexive
    (Lemma „… si", Oberflächen mit „ si") werden abgespalten (+Refl). Mehrwort-
    Lemmata ohne „ si" (MWE) und unvollständige/inkosnistente Tabellen werden
    ausgeschlossen.
    """
    entries = json.loads(TWANKSTA.read_text())
    out, seen = [], set()
    excluded = data_errors = 0
    for e in entries:
        para = PARA_ALIAS.get(e.get("paradigm"), e.get("paradigm"))
        if para not in PARADIGMS:
            continue
        word = e.get("word", "")
        if word.endswith(" si"):
            refl, lemma = True, word[:-3]
        elif " " in word or "/" in word:
            excluded += 1
            continue
        else:
            refl, lemma = False, word
        if not lemma or " " in lemma:
            excluded += 1
            continue

        forms = e.get("forms", {})
        ind = {t["tense"]: {s["pronoun"]: primary(s["form"])
                            for s in t["forms"]}
               for t in forms.get("indicative", [])}
        subj = {s["pronoun"]: primary(s["form"])
                for s in forms.get("subjunctive", [])}
        opt = primary(forms.get("optative", ""))
        imp = {s["pronoun"]: primary(s["form"])
               for s in forms.get("imperative", [])}
        if "Present" not in ind or "Past" not in ind:
            excluded += 1
            continue

        stems = []
        ok = True
        for stem_lex, infl, src, strip in PARADIGMS[para]:
            if src == "pres":
                srcform = strip_si(ind["Present"].get("tāns/tenā/tennan", ""))
            else:
                srcform = strip_si(subj.get("tāns/tenā/tennan", ""))
            if not srcform.endswith(strip):
                ok = False
                break
            stems.append((stem_lex, infl, srcform[: -len(strip)]))
        if not ok:
            excluded += 1
            continue

        key = (lemma, para)
        if key in seen:
            continue
        seen.add(key)

        # Identitäts-Kollaps (alle Zellen gleich) = Twanksta-Datenfehler.
        cells = [strip_si(f) for t in ind.values() for f in t.values()]
        cells += [strip_si(v) for v in subj.values()]
        cells += [strip_si(opt)] + [strip_si(v) for v in imp.values()]
        if len({c for c in cells if c}) <= 1:
            data_errors += 1
            continue

        out.append({"lemma": lemma, "para": para, "refl": refl,
                    "stems": stems, "ind": ind, "subj": subj,
                    "opt": opt, "imp": imp})
    print(f"Ziel-Lexeme: {len(out)}  (ausgeschlossen: {excluded}, "
          f"Twanksta-Datenfehler: {data_errors})")
    return out, excluded, data_errors


def stems_block(targets: list[dict]) -> str:
    """Aus twanksta inventarisierte (doppelte) Stämme als LEXICON-Block.

    Jedem Stamm-Lexikon werden Einträge der Form `Lemma+V:Stamm  Endungslex ;`
    zugeordnet. Grammatik (Endungen) steht datenfrei in gen/verb.lexc; LEXICON
    Root verweist auf die hier definierten Stamm-Lexika. Reflektierte Verben
    nutzen denselben Lemma-Schlüssel (+Refl kommt über das optionale VerbEnd der
    Endungslexika) — Duplikate werden unterdrückt.
    """
    stems: dict[str, list[tuple[str, str]]] = {
        spec[0]: [] for specs in PARADIGMS.values() for spec in specs}
    seen = set()
    for t in targets:
        for stem_lex, infl, stem in t["stems"]:
            key = (t["lemma"], stem_lex, stem)
            if key in seen:
                continue
            seen.add(key)
            stems[stem_lex].append((t["lemma"], f"{t['lemma']}+V:{stem}  {infl} ;"))
    body = ["! === Aus twanksta generierte Stämme — NICHT von Hand editieren ===",
            "! (erzeugt von gen/coverage_verb.py --emit-stems; Grammatik: gen/verb.lexc)"]
    for stem_lex in _ordered_stem_lexicons():
        rows = sorted(set(stems[stem_lex]))
        body.append(f"LEXICON {stem_lex}")
        body.extend(f"  {line}" for _, line in rows if rows)
        if not rows:
            body.append("  0:0  # ;")
        body.append("")
    return "\n".join(body) + "\n"


def _ordered_stem_lexicons() -> list[str]:
    order = []
    for specs in PARADIGMS.values():
        for spec in specs:
            if spec[0] not in order:
                order.append(spec[0])
    return order


def write_combined(targets: list[dict]) -> Path:
    combined = LEXC.read_text().rstrip() + "\n\n" + stems_block(targets)
    out = BUILD / "gen-verbcov.lexc"
    out.write_text(combined)
    return out


def build(lexc: Path) -> Path:
    fst = BUILD / "gen-verbcov.fst"
    composed = BUILD / "gen-verbcov.composed.fst"
    hfstol = BUILD / "gen-verbcov.gen.hfstol"
    if not ACCENT.exists():
        subprocess.run(HFST + ["xfst", str(ROOT / "gen" / "accent.regex")], check=True)
    subprocess.run(HFST + ["lexc", str(lexc), str(fst)], check=True)
    subprocess.run(HFST + ["compose", str(composed), str(fst), str(ACCENT)], check=True)
    subprocess.run(HFST + ["hfstol-gen", str(composed), str(hfstol)], check=True)
    return hfstol


def _queries(t: dict) -> dict[str, str]:
    """Analyse-String → erwartete Oberflächenform für ein Verb."""
    refl = "+Refl" if t["refl"] else ""
    q = {}
    for mood, tense, data in (("Ind", "Pres", t["ind"].get("Present", {})),
                               ("Ind", "Pret", t["ind"].get("Past", {}))):
        for p in PERSONS:
            q[f"{t['lemma']}+V+{mood}+{tense}+{PRONOUN[p]}{refl}"] = \
                strip_si(data.get(p, ""))
    for p in PERSONS:
        q[f"{t['lemma']}+V+Subj+{PRONOUN[p]}{refl}"] = \
            strip_si(t["subj"].get(p, ""))
    q[f"{t['lemma']}+V+Opt+P3{refl}"] = strip_si(t["opt"])
    for p, tag in (("(tū)", "P2+Sg"), ("(jūs)", "P2+Pl")):
        q[f"{t['lemma']}+V+Imp+{tag}{refl}"] = strip_si(t["imp"].get(p, ""))
    return q


def slot_name(query: str, lemma: str) -> str:
    return query[len(lemma) + 2:]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--show", type=int, default=15, help="max. Abweichungen zeigen")
    ap.add_argument("--emit-stems", metavar="PATH",
                    help="nur den generierten Stamm-Block nach PATH schreiben "
                         "(für den Build) und beenden — kein Deckungstest")
    args = ap.parse_args()

    targets, _, _ = load_targets()

    if args.emit_stems:
        Path(args.emit_stems).write_text(stems_block(targets))
        print(f"Stämme geschrieben: {args.emit_stems} ({len(targets)} Lexeme)")
        return

    hfstol = build(write_combined(targets))
    queries = [q for t in targets for q in _queries(t)]
    gen = glookup_batch(queries, str(hfstol))

    total = hit = 0
    per_para = Counter(); per_para_hit = Counter()
    miss_slot = Counter(); misses = []
    for t in targets:
        for a, want in _queries(t).items():
            if not want:
                continue
            total += 1
            per_para[t["para"]] += 1
            ok = want in gen.get(a, [])
            hit += ok
            per_para_hit[t["para"]] += ok
            if not ok:
                miss_slot[slot_name(a, t["lemma"])] += 1
                misses.append(f"  {t['lemma']}[{t['para']}] {slot_name(a, t['lemma'])}: "
                              f"erwartet {want!r}, generiert {gen.get(a) or '∅'}")
    print(f"\nDeckung gesamt: {hit}/{total} ({100*hit/total:.1f}%)")
    for para in PARADIGMS:
        if per_para[para]:
            print(f"  Par.{para}: {per_para_hit[para]}/{per_para[para]} "
                  f"({100*per_para_hit[para]/per_para[para]:.1f}%)")
    if miss_slot:
        print("\nAbweichungen je Slot:", dict(miss_slot.most_common()))
    if misses:
        print(f"\nBeispiel-Abweichungen (erste {args.show}):")
        print("\n".join(misses[: args.show]))

    # Offene Paradigmen (nicht abgedeckt) — ehrliche Übersicht.
    from collections import defaultdict
    covered = set(PARADIGMS)
    open_ = defaultdict(int)
    entries = json.loads(TWANKSTA.read_text())
    for e in entries:
        para = PARA_ALIAS.get(e.get("paradigm"), e.get("paradigm"))
        if "indicative" in e.get("forms", {}) and para not in covered:
            open_[para] += 1
    if open_:
        print(f"\nOffene Paradigmen ({sum(open_.values())} Verben, "
              f"{len(open_)} Klassen):")
        for para in sorted(open_, key=lambda p: -open_[p]):
            print(f"  Par.{para}: {open_[para]}")


if __name__ == "__main__":
    main()
