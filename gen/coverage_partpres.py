"""Nicht-zirkulärer Deckungstest für das Präsens-Partizip (-nts, drei Genera).

Das Präsens-Partizip deklinert adjektivisch nach dem mobilen i-Stamm-Muster
(Par.29), ein Ntr.Acc.Sg. -in ausgenommen. Die Stämme kommen NICHT aus Adjektiven,
sondern aus den VERB-Einträgen: Twanksta `forms.participles[type=Present]`
trägt `full_declension` (3 Genusblöcke) — der Stamm = Masc.Gen.Sg. minus -is
(kalbantis → kalbant). Die Grammatik (Endungen) steht datenfrei in gen/adj.lexc
(LEXICON PartPres*); hier wird nur die STAMM-Inventarisierung skaliert: für jedes
reale Verb wird der Präsens-Partizip-Stamm abgeleitet, an die Grammatik gehängt,
kompiliert, mit gen/accent.regex komponiert und die 24 Formen exakt gegen Twanksta
verglichen. Tag-Format kanonisch: `+V+Part+Pres+{G}+{Num}+{Case}` (wie base.gen).

Wie beim Adverb: Regel-Deckung wird getrennt von gelisteten Ausnahmen ausgewiesen;
derzeit gibt es keine irrationale Präsens-Partizip-Bildung (Verben ohne -nts-Form
wie dirtun/dirtwei haben gar kein eigenes Präsens-Partizip → ausgeschlossen, kein
LUT). KEIN Voll-Inventar-LUT — die Grammatik generalisiert, twanksta ist nur Test.

    uv run python gen/coverage_partpres.py [--show N]
    uv run python gen/coverage_partpres.py --emit-stems build/gen-partpres-stems.lexc
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
LEXC = ROOT / "gen" / "adj.lexc"
ACCENT = ROOT / "build" / "gen-accent.hfst"
BUILD = ROOT / "build"
HFST = ["uv", "run", "python", str(ROOT / "src" / "prussian_fst" / "build_fst.py")]

# Alle Stamm-Lexika, auf die LEXICON Root in gen/adj.lexc verweist — nur PartPres
# wird hier befüllt, der Rest (ggf. leer) damit die Referenzen auflösen.
STEM_LEXICONS = ["AdjFixed", "AdjMobile", "AdjI", "AdjIMob", "AdjUMob",
                 "PartPass", "PartAct", "PartPres", "AdjCmpStems", "AdjSupStems"]

GEN = {"masc": "Masc", "fem": "Fem", "neut": "Neut"}
CASES = ["Nom", "Gen", "Dat", "Acc"]
CA = {"Nominative": "Nom", "Genitive": "Gen", "Dative": "Dat", "Accusative": "Acc"}


def primary(cell: str) -> str:
    return (cell or "").split(" / ")[0].strip()


def gem_keep_lemmas() -> set[str]:
    """Verben mit lexikalischer (nicht akzent-beweglicher) Gemination — LEXICON PartPresGemKeep.

    jj/cc-Doppelkonsonanten sind ins Grundmorphem eingebacken und werden im
    akzentverschobenen Dat.Pl. NICHT reduziert (anders als die degeminierenden
    Geminaten-Verben). Der emittierte Stamm bekommt den Schutzmarker ~ angehängt;
    gen/accent.regex sperrt daraufhin Degem (Shorten bleibt). LEXICON PartPresGemKeep
    wird NICHT von LEXICON Root referenziert — reine Ausnahmeliste, hier als
    Lemma-Quelle gelesen.
    """
    text = LEXC.read_text()
    m = re.search(r"^LEXICON PartPresGemKeep\b(.*?)(?=^LEXICON |\Z)",
                  text, re.M | re.S)
    if not m:
        return set()
    return set(re.findall(r"^\s*(\S+?)\+V\+Part\+Pres", m.group(1), re.M))


def load_targets(gem_keep: set[str]) -> tuple[list[dict], int, int]:
    """Präsens-Partizip-Lexeme aus den Verb-Einträgen (rule, excluded, nostem).

    Der Stamm = Masc.Gen.Sg. des Present-full_declension minus -is. Ausgeschlossen:
    Mehrwort/Slash-Lemma (z. B. reflexive „… si", Tremata), fehlender 3-Genus-Block.
    Verben ohne ableitbaren -nts-Stamm (dirtun/dirtwei u. ä. — kein eigenes
    Präsens-Partizip) zählen separat als `nostem` (kein LUT, kein Regel-Lexem).
    Lemmata aus LEXICON PartPresGemKeep tragen die lexikalische Gemination und
    werden als `gem_keep=True` markiert (Stamm bekommt Schutzmarker ~).
    """
    entries = json.loads(TWANKSTA.read_text())
    rule, seen = [], set()
    excluded = nostem = 0
    for e in entries:
        pres = [p for p in e.get("forms", {}).get("participles", [])
                if p.get("type") == "Present" and p.get("full_declension")]
        if not pres:
            continue
        lemma = e.get("word", "")
        fd = pres[0]["full_declension"]
        blocks = {b.get("gender"): b for b in fd}
        if " " in lemma or "/" in lemma or {"masc", "fem", "neut"} - set(blocks):
            excluded += 1
            continue
        gsrc = ""
        for c in blocks["masc"].get("cases", []):
            if c.get("case") == "Genitive":
                gsrc = primary(c.get("singular"))
        if not gsrc.endswith("is"):
            nostem += 1
            continue
        stem = gsrc[: -len("is")]
        forms = {}
        for g, b in blocks.items():
            for c in b.get("cases", []):
                ca = CA.get(c.get("case", ""))
                if not ca:
                    continue
                forms[(GEN[g], f"Sg+{ca}")] = primary(c.get("singular"))
                forms[(GEN[g], f"Pl+{ca}")] = primary(c.get("plural"))
        if len(forms) < 24:
            excluded += 1
            continue
        if (lemma,) in seen:
            continue
        seen.add((lemma,))
        rule.append({"lemma": lemma, "stem": stem, "forms": forms,
                     "gem_keep": lemma in gem_keep})
    print(f"Regel-Lexeme (Präsens-Partizip): {len(rule)}  "
          f"(ausgeschlossen: {excluded}, ohne -nts-Stamm: {nostem})")
    return rule, excluded, nostem


def stems_block(targets: list[dict]) -> str:
    """Inventarisierte Präsens-Partizip-Stämme als LEXICON-Block (Lemma:Stamm).

    Nur PartPres wird befüllt; alle übrigen STEM_LEXICONS werden (leer) definiert,
    damit die Root-Referenzen in gen/adj.lexc auflösen. Lemma = Verb-Lemma (für
    das kanonische `+V+Part+Pres+…`-Tag), Stamm = Present-Stamm aus twanksta.
    """
    stems: dict[str, list[str]] = {sl: [] for sl in STEM_LEXICONS}
    for t in targets:
        stem = t["stem"] + ("%~" if t["gem_keep"] else "")
        stems["PartPres"].append(f"  {t['lemma']}:{stem}  PartPresInfl ;")
    body = ["! === Aus twanksta generierte Stämme — NICHT von Hand editieren ===",
            "! (erzeugt von gen/coverage_partpres.py --emit-stems; Grammatik: gen/adj.lexc)"]
    for stem_lex in STEM_LEXICONS:
        body.append(f"LEXICON {stem_lex}")
        body.extend(stems[stem_lex] or ["  0:0  # ;"])
        body.append("")
    return "\n".join(body) + "\n"


def write_combined(targets: list[dict]) -> Path:
    combined = LEXC.read_text().rstrip() + "\n\n" + stems_block(targets)
    out = BUILD / "gen-partprescov.lexc"
    out.write_text(combined)
    return out


def build(lexc: Path) -> Path:
    fst = BUILD / "gen-partprescov.fst"
    composed = BUILD / "gen-partprescov.composed.fst"
    hfstol = BUILD / "gen-partprescov.gen.hfstol"
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

    gem_keep = gem_keep_lemmas()
    targets, _, _ = load_targets(gem_keep)

    if args.emit_stems:
        Path(args.emit_stems).write_text(stems_block(targets))
        print(f"Stämme geschrieben: {args.emit_stems} ({len(targets)} Lexeme)")
        return

    hfstol = build(write_combined(targets))
    queries = [f"{t['lemma']}+V+Part+Pres+{g}+{n}+{c}"
               for t in targets for g in ("Masc", "Fem", "Neut")
               for n in ("Sg", "Pl") for c in CASES]
    gen = glookup_batch(queries, str(hfstol))

    rule_targets = [t for t in targets if not t["gem_keep"]]
    listed_targets = [t for t in targets if t["gem_keep"]]
    total = hit = 0
    miss_slot = Counter(); misses = []
    for t in rule_targets:
        for g in ("Masc", "Fem", "Neut"):
            for n in ("Sg", "Pl"):
                for c in CASES:
                    want = t["forms"].get((g, f"{n}+{c}"))
                    if not want:
                        continue
                    total += 1
                    a = f"{t['lemma']}+V+Part+Pres+{g}+{n}+{c}"
                    ok = want in gen.get(a, [])
                    hit += ok
                    if not ok:
                        miss_slot[f"{g} {n}+{c}"] += 1
                        misses.append(f"  {t['lemma']} {g} {n}+{c}: {want!r} ≠ "
                                      f"{(gen.get(a) or ['∅'])[0]!r}")
    print(f"\nRegel-Deckung (Präsens-Partizip, -nts): {hit}/{total} "
          f"({100*hit/total:.1f}%)  [aus {len(rule_targets)} Regel-Lexemen × 24]")
    if miss_slot:
        print("\nAbweichungen je Slot:", dict(miss_slot.most_common()))
    if misses:
        print(f"\nBeispiele (erste {args.show}):")
        print("\n".join(misses[: args.show]))

    # Gelistete Ausnahmen (lexikalische Gemination jj/cc) — getrennt ausgewiesen.
    exc_hit = exc_ok = 0
    for t in listed_targets:
        for g in ("Masc", "Fem", "Neut"):
            for n in ("Sg", "Pl"):
                for c in CASES:
                    want = t["forms"].get((g, f"{n}+{c}"))
                    if not want:
                        continue
                    exc_ok += 1
                    a = f"{t['lemma']}+V+Part+Pres+{g}+{n}+{c}"
                    exc_hit += want in gen.get(a, [])
    print(f"\nGelistete Ausnahmen (LEXICON PartPresGemKeep, jj/cc-Gemination): "
          f"{len(listed_targets)} Lemmata, {exc_hit}/{exc_ok} Formen erzeugt")
    for t in listed_targets:
        print(f"  {t['lemma']} → {t['forms'][('Masc', 'Sg+Nom')]}")


if __name__ == "__main__":
    main()
