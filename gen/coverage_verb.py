"""Nicht-zirkulärer Deckungstest für die finiten Verben (synthetische Formen).

Wie bei den Nomen/Adjektiven ist die Grammatik (Endungstabellen) datenfrei in
gen/verb.lexc formuliert; hier wird nur die STAMM-Inventarisierung skaliert. Verben
haben je Lexem ein bis drei Stämme, die mechanisch aus je einer Prinzipalform
abgeleitet werden (Present-P3 → Präsens-Stamm, Past-P3 → Präterital-Stamm, Subj-P3
→ Infinitiv-/Optativ-/Subjunktiv-Stamm). Der Präterital-Stamm wird NIE aus dem
Präsens vorhergesagt — er trägt so Ablaut, Nasal-Infix, -st- und mobile Kürzung
als fertige Stamm-Allomorphie (Phase 4a: reguläre Klassen, Phase 4b: starke
Verben mit drei Prinzipalformen). Die Stämme werden an die handgeschriebenen
Endungslexika gehängt; gemessen wird die exakte Reproduktion aller synthetischen
Formen. Deckung wird als REGEL-Deckung (Endungen) geführt, die Stämme sind
gelistete Prinzipalformen; das nicht gedeckte RESIDUUM wird berichtet (nicht
hand-gelistet), Twanksta-Datenfehler werden geflaggt (nicht modelliert).

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

    # ── Phase 4a (Tier A, reguläre Klassen) ─────────────────────────────────
    # Par.144 (-ja-/-wa-): drei Stämme auf den Tier-B-Tafeln.
    "144": [("P144InfStems",  "InfSubjOpt", "subj", "lai"),
            ("P144PresStems", "PresImp",     "pres", "a"),
            ("P144PretStems", "PretInd",     "pret", "a")],
    # Par.142 (akzent-mobiles ā): Präs/Imp auf akzent-mobilem Stamm,
    # Prät/Opt/Subj auf dem -ā- Stamm.
    "142": [("P142FinStems", "PresImp",    "pres", "a"),
            ("P142NfStems",  "P142Nonfin", "subj", "lai")],
    # Par.136 (ī-Klasse, Prät -ēi): drei Stämme — Kons-Stamm (Präs/Imp über
    # PresImp), Präterital-Stamm (Prät -i, mobile Vokalkürzung), ī-Stamm (Opt/Subj).
    "136": [("P136FinStems",  "PresImp",    "pres", "a"),
            ("P136PretStems", "P136Pret",   "pret", "i"),
            ("P136NfStems",   "InfSubjOpt", "subj", "lai")],
    # Par.111 (n-Infix -nja-/-wa-): Präs -ja- + Imp -j-, Prät -a-/-amai/-atei.
    "111": [("P111InfStems",  "InfSubjOpt", "subj", "lai"),
            ("P111PresStems", "P111Pres",   "pres", "ja"),
            ("P111PretStems", "PretInd",    "pret", "a")],
    # Par.71 (Geminaten-Alternanz, kein -j-): geminierter fin-Stamm trägt
    # Präs/Prät/Imp; un-geminierter Stamm trägt Opt/Subj.
    "71":  [("P71FinStems", "P71Fin",     "pres", "a"),
            ("P71NfStems",  "InfSubjOpt", "subj", "lai")],
    # Par.75 (Geminaten-Alternanz, -ja-): geminierter fin-Stamm (Präs -ja-/Prät
    # -i), un-geminierter Stamm (Opt/Subj/Imp -j-).
    "75":  [("P75FinStems", "P75Fin",    "pres", "ja"),
            ("P75NfStems",  "P75Nonfin", "subj", "lai")],

    # ── Phase 4b (Tier B, starke Verben, drei Prinzipalformen) ──────────────
    # Ein Lemma = drei Stämme (Infinitiv-, Präsens-, Präteritalstamm) auf die
    # gemeinsamen Tafeln InfSubjOpt / PresImp / PretInd. Ablaut/Nasal-Infix/-st-
    # sitzen in genau einer Prinzipalform; Prät-Stamm wird NICHT aus dem Präsens
    # vorhergesagt. Allesamt ein LEXICON VerbStrongStems.
    "97":  [("VerbStrongStems", "InfSubjOpt", "subj", "lai"),
            ("VerbStrongStems", "PresImp",     "pres", "a"),
            ("VerbStrongStems", "PretInd",     "pret", "a")],
    "89":  [("VerbStrongStems", "InfSubjOpt", "subj", "lai"),
            ("VerbStrongStems", "PresImp",     "pres", "a"),
            ("VerbStrongStems", "PretInd",     "pret", "a")],
    "92":  [("VerbStrongStems", "InfSubjOpt", "subj", "lai"),
            ("VerbStrongStems", "PresImp",     "pres", "a"),
            ("VerbStrongStems", "PretInd",     "pret", "a")],
    "81":  [("VerbStrongStems", "InfSubjOpt", "subj", "lai"),
            ("VerbStrongStems", "PresImp",     "pres", "a"),
            ("VerbStrongStems", "PretInd",     "pret", "a")],
    "87":  [("VerbStrongStems", "InfSubjOpt", "subj", "lai"),
            ("VerbStrongStems", "PresImp",     "pres", "a"),
            ("VerbStrongStems", "PretInd",     "pret", "a")],
}

# Weitere Klassen (Ablaut/Nasal-Infix/-st-, teils -ī-/-ū- schwache), die exakt
# die drei gemeinsamen Tier-B-Tafeln teilen — datenbasiert geprüft (identische
# Endungen, Präterital-Stamm eigenständig aus der Prät.-P3 abgeleitet).
_THREE_STEM_EXTRA = ["88", "90", "91", "93", "94", "96", "99", "100", "102",
                     "106", "107", "108", "109", "113", "122", "141"]
for _p in _THREE_STEM_EXTRA:
    PARADIGMS[_p] = [
        ("VerbStrongStems", "InfSubjOpt", "subj", "lai"),
        ("VerbStrongStems", "PresImp",     "pres", "a"),
        ("VerbStrongStems", "PretInd",     "pret", "a"),
    ]

# Twanksta-Paradigmen-Labels mit Varianten-Suffix (identische Flexion zur
# Basis-Nummer) bzw. Tippfehler auf die Basis normalisiert.
PARA_ALIAS = {"75b": "75", "134a": "134", "75a": "75", "76s": "76",
              "80b": "80", "81a": "81", "81b": "81", "81c": "81",
              "97a": "97", "102a": "102", "106b": "106", "137a": "137"}

# Twanksta-Datenfehler: sämtliche synthetischen Formen = Infinitiv (kein echtes
# Paradigma). Werden FLAGGEN, NICHT modelliert — nicht als Stämme emittiert und
# nicht als Ausnahme gelistet. (Schreibweise wie in twanksta, mit Makrone.)
DATA_ERRORS = frozenset({
    "dirtwei", "dirtun", "kāistwei", "enkāistwei", "prakāistwei",
    "klīmptwei", "tilptwei", "skrabtwei", "rjaūgitwei", "preijustwei",
})

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


def scan_data_errors() -> list[str]:
    """Twanksta-Datenfehler über ALLE Verb-Einträge (jedes Paradigma).

    Ein Verb, dessen sämtliche synthetischen Formen (Präsens/Präteritum Indikativ,
    Optativ, Subjunktiv, Imperativ) mit dem Infinitiv identisch sind, ist kein
    echtes Paradigma, sondern ein Datensatz-Fehler. Diese Lemmata werden geflaggt
    und NICHT modelliert (kein Stamm-Emit, keine Ausnahme-Liste).
    """
    entries = json.loads(TWANKSTA.read_text())
    out: list[str] = []
    for e in entries:
        forms = e.get("forms", {})
        if "indicative" not in forms:
            continue
        ind = {t["tense"]: {s["pronoun"]: primary(s["form"])
                            for s in t["forms"]}
               for t in forms.get("indicative", [])}
        if "Present" not in ind or "Past" not in ind:
            continue
        subj = {s["pronoun"]: primary(s["form"])
                for s in forms.get("subjunctive", [])}
        opt = primary(forms.get("optative", ""))
        imp = {s["pronoun"]: primary(s["form"])
               for s in forms.get("imperative", [])}
        cells = [strip_si(f) for t in ("Present", "Past")
                 for f in ind.get(t, {}).values()]
        cells += [strip_si(v) for v in subj.values()]
        cells += [strip_si(opt)] + [strip_si(v) for v in imp.values()]
        if len({c for c in cells if c}) <= 1:
            out.append(e.get("word", ""))
    return sorted(set(out))


def load_targets() -> tuple[list[dict], int, list[dict]]:
    """Verb-Lexeme der Ziel-Paradigmen mit ihren abgeleiteten Stämmen.

    Rückgabe (targets, excluded, residuum). Pro Paradigma werden ein bis drei
    Stämme mechanisch aus je einer Prinzipalform abgeleitet:
      present-P3 (Präsens-Stamm), past-P3 (Präteritalstamm, NICHT aus dem
      Präsens vorhergesagt), subj-P3 (Infinitiv-/Optativ-/Subjunktiv-Stamm).
    Reflexive (Lemma „… si", Oberflächen mit „ si") werden abgespalten (+Refl).
    Mehrwort-/Slash-Lemmata (MWE) und unvollständige Tabellen zählen als
    ausgeschlossen. Verben, deren Stämme sich unter der Klassenregel NICHT
    ableiten lassen, landen im RESIDUUM (Bericht, kein Handlisten).
    """
    entries = json.loads(TWANKSTA.read_text())
    data_errors = set(scan_data_errors())
    out, seen = [], set()
    excluded = 0
    residuum: list[dict] = []
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

        if lemma in data_errors:
            continue

        key = (lemma, para)
        if key in seen:
            continue
        seen.add(key)

        srcmap = {
            "pres": ind["Present"].get("tāns/tenā/tennan", ""),
            "pret": ind["Past"].get("tāns/tenā/tennan", ""),
            "subj": subj.get("tāns/tenā/tennan", ""),
            "opt": opt,
        }
        stems = []
        ok = True
        for stem_lex, infl, src, strip in PARADIGMS[para]:
            srcform = strip_si(srcmap[src])
            if not srcform.endswith(strip):
                ok = False
                residuum.append({
                    "lemma": lemma, "para": para, "slot": f"Stamm({src})",
                    "want": f"…{strip}", "got": srcform or "∅",
                })
                break
            stems.append((stem_lex, infl, srcform[: -len(strip)]))
        if not ok:
            continue

        out.append({"lemma": lemma, "para": para, "refl": refl,
                    "stems": stems, "ind": ind, "subj": subj,
                    "opt": opt, "imp": imp})
    print(f"Ziel-Lexeme: {len(out)}  (ausgeschlossen: {excluded}, "
          f"Residuum: {len(residuum)})")
    return out, excluded, residuum


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
            key = (t["lemma"], stem_lex, infl, stem)
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

    targets, _, residuum = load_targets()

    if args.emit_stems:
        Path(args.emit_stems).write_text(stems_block(targets))
        print(f"Stämme geschrieben: {args.emit_stems} ({len(targets)} Lexeme)")
        return

    # ── Datenfehler (alle Formen = Infinitiv): flaggen, nicht modellieren. ───
    data_errors = scan_data_errors()
    if data_errors:
        print(f"\nTwanksta-Datenfehler ({len(data_errors)}, geflaggt, nicht modelliert):")
        for lemma in data_errors:
            marker = "  ← erwartet" if lemma in DATA_ERRORS else "  ← NEU/unerwartet"
            print(f"  {lemma}{marker}")
        missing = DATA_ERRORS - set(data_errors)
        if missing:
            print("  (in DATA_ERRORS erwartet, aber nicht als Kollaps erkannt): "
                  + ", ".join(sorted(missing)))

    n_stems = sum(len(t["stems"]) for t in targets)
    print(f"\nRegel vs. gelistet: {n_stems} gelistete Stämme aus Prinzipalformen "
          f"(Infinitiv-/Präsens-/Präterital-P3); Endungen = datenfreie Regel "
          f"(gen/verb.lexc).")

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
                misses.append({"lemma": t["lemma"], "para": t["para"],
                               "slot": slot_name(a, t["lemma"]),
                               "want": want, "got": (" / ".join(gen.get(a, [])) or "∅")})
    print(f"\nRegel-Deckung: {hit}/{total} ({100*hit/total:.1f}%)")
    for para in PARADIGMS:
        if per_para[para]:
            print(f"  Par.{para}: {per_para_hit[para]}/{per_para[para]} "
                  f"({100*per_para_hit[para]/per_para[para]:.1f}%)")
    if miss_slot:
        print("\nAbweichungen je Slot:", dict(miss_slot.most_common()))

    # ── Residuum: NICHT eigenmächtig handlisten, sondern berichten. ─────────
    # (a) Stamm-Ableitung scheiterte unter der Klassenregel (kein FST-Eintrag).
    # (b) Endungstafeln erzeugten die erwartete Form nicht (Lemma + Slot + erwartet/erzeugt).
    residuum += misses
    if residuum:
        print(f"\nRESIDUUM ({len(residuum)} — wird berichtet, NICHT gelistet):")
        for r in residuum[:args.show]:
            label = f"{r['lemma']}[{r['para']}] {r['slot']}"
            print(f"  {label}: erwartet {r['want']!r}, erzeugt {r['got']!r}")
        if len(residuum) > args.show:
            print(f"  … und {len(residuum) - args.show} weitere.")

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
