#!/usr/bin/env python3
"""HFST-nativer Build via lexd: lexd-Quelltext ∘ Regeln → analyser/lenient.

    morphotactics.lexd                     (markierte Unterseite, Tag-Filterung)
        │  lexd CLI → .att
        │  hfst-txt2fst
        ▼
    lexicon.hfst
        ∘  rules.PHONOLOGY   (SHORTEN ∘ LENGTHEN ∘ JPAL ∘ CLEANUP)
        =  generator.hfst    (Analyse → Standardoberfläche)
        ∘  fold.FOLD_SURFACE (Orthographie-Faltung + Twanksta-j-Endungen)
        =  lenient (Oberfläche + Quellvarianten → Analyse)

Gespeichert werden (alle als HFST-Transducer, FOMA-Backend):
    build/hfst/morphotactics.lexd    lexd-Quelltext
    build/hfst/morphotactics.att     ATT-Zwischenformat
    build/hfst/lexicon.hfst          lexd → hfst
    build/hfst/generator.hfst        Analyse → Oberfläche  (Standard)
    build/hfst/analyser.hfst         Oberfläche → Analyse  (Standard)
    build/hfst/lenient.hfst          Oberfläche(+Varianten) → Analyse

Aufruf (im hfst-venv, Python 3.12):
    PYTHONPATH=src python -m prussian.fst.hfst.lexd_build [--gold-only | --sample N]
"""

import argparse
import json
import random
import re
import subprocess
from pathlib import Path

import hfst

from prussian.fst.hfst.lexd_gen import build_lexd
from prussian.fst.hfst import fold as fold_mod
from prussian.fst.hfst import rules
from prussian.gold import derive
from prussian.fst.morphology import adverbs as adv_mod
from prussian.fst.morphology import function_words as fw_mod
from prussian.fst.morphology import verbs as verb_morph
from prussian.fst.morphology.nominals import combine_entries, wordlist_to_entries
from prussian.fst.tags import _pos


def _handwritten_closed(paradigm: str) -> bool:
    """Geschlossene Klassen, die im Vollbau handgeschrieben in data/lexd/*
    stehen (nicht aus den Eintragsdaten zu generieren):
      * Pronomen (30-pronouns.lexd) — ``_pos == +Pron``
      * suppletive Steigerung (35-suppletives.lexd) — Paradigmen ``*_suppl*``
    Numeralia/Funktionswörter/Adverbien laufen ohnehin über eigene Lexika;
    hier zählt nur, was sonst über die Paradigma-Stämme generiert würde."""
    return _pos(paradigm) == "+Pron" or "suppl" in paradigm

ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
GOLD = ROOT / "data/gold/goldstandard.json"
VERB_GOLD = ROOT / "data/gold/goldstandard_verben_fst.json"
TWANKSTA = ROOT / "data/external/twanksta_entries.json"
PRUSASPIRA = ROOT / "data/external/prusaspira_entries.json"
CLOSED_FW = ROOT / "data/closed/function_words.json"
CLOSED_PRONOUNS = ROOT / "data/closed/personal_pronouns.json"
LEXD_DIR = ROOT / "data/lexd"
BUILD = ROOT / "build/hfst"

LEXD_OUT = BUILD / "morphotactics.lexd"
ATT_OUT = BUILD / "morphotactics.att"
LEXICON_OUT = BUILD / "lexicon.hfst"
GEN_OUT = BUILD / "generator.hfst"
ANA_OUT = BUILD / "analyser.hfst"
LEN_OUT = BUILD / "lenient.hfst"

FOMA = hfst.ImplementationType.FOMA_TYPE


def sample_by_lemma(entries, n, rng):
    lemmas = list(dict.fromkeys(e["lemma"] for e in entries))
    if n >= len(lemmas):
        return entries
    keep = set(rng.sample(lemmas, n))
    return [e for e in entries if e["lemma"] in keep]


def _compose_chain(base, regex_strings):
    """base ∘ regex_strings[0] ∘ … (alle als hfst.regex kompiliert)."""
    result = hfst.HfstTransducer(base)
    for src in regex_strings:
        r = hfst.regex(src)
        r.convert(FOMA)
        result.compose(r)
        result.minimize()
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gold-only", action="store_true")
    ap.add_argument("--sample", type=int, metavar="N")
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    hfst.set_default_fst_type(FOMA)

    gs_data = json.loads(GOLD.read_text(encoding="utf-8"))
    verb_data = json.loads(VERB_GOLD.read_text(encoding="utf-8"))
    print(f"Goldstandard: {len(gs_data)} nominal, {len(verb_data)} verbal")

    verb_wl = closed = fw_words = adv_words = None
    if args.gold_only:
        combined = gs_data
        wl_entries = []
    else:
        rng = random.Random(args.seed) if args.sample else None
        wl_data = json.loads(TWANKSTA.read_text(encoding="utf-8"))
        wl_entries = wordlist_to_entries(wl_data, gs_data)
        if rng is not None:
            wl_entries = sample_by_lemma(wl_entries, args.sample, rng)
        combined = combine_entries(gs_data, wl_entries)
        verb_wl = verb_morph.wordlist_to_verb_entries(wl_data, verb_data)
        if rng is not None:
            verb_wl = sample_by_lemma(verb_wl, args.sample, rng)
        closed = json.loads(CLOSED_PRONOUNS.read_text(encoding="utf-8"))
        fw_words = fw_mod.load(CLOSED_FW)
        adv_words = adv_mod.load(TWANKSTA)
        print(
            f"Wortliste: {len(wl_entries)} nominal, "
            f"{len(verb_wl)} verbal; +{len(closed)} Pronomen, "
            f"{len(fw_words)} FW, {len(adv_words)} Adv"
        )

    BUILD.mkdir(parents=True, exist_ok=True)

    if args.gold_only:
        # gold-only: alles inline generieren (keine lexd/* nötig)
        lexd_text = build_lexd(
            combined,
            verb_data,
            verb_wl,
            closed_entries=closed,
            function_words=fw_words,
            adverbs=adv_words,
        )
    else:
        # voller Build: handgeschriebene Tabellen (data/lexd/*) + Generat.
        # Geschlossene Klassen (Pronomen/Suppletive) kommen handgeschrieben
        # aus data/lexd/ — daher aus den generierten Stämmen herausfiltern.
        open_entries = [
            e for e in combined if not _handwritten_closed(e["paradigm"])
        ]
        # Welche Infl-Lexika sind in data/lexd/* schon handgeschrieben? Für
        # diese Paradigmen generiert build_lexd nur das Stem-Lexikon (kein
        # PATTERN/Infl-Duplikat); alle übrigen offenen Paradigmen werden lean
        # generiert (gender-gemergt), sodass der Vollbau die ganze Wortliste
        # abdeckt.
        lexd_parts = [f.read_text(encoding="utf-8")
                      for f in sorted(LEXD_DIR.glob("*.lexd"))]
        handwritten = set(re.findall(
            r"^LEXICON\s+(Infl\S+)", "\n".join(lexd_parts), re.MULTILINE))
        # function_words/adverbs/Pronomen/Numeralia: alle handgeschrieben in
        # data/lexd/* — daher hier None; Doubletten (Variants) ebenso.
        stems_text = build_lexd(
            open_entries,
            verb_data,
            verb_wl,
            closed_entries=None,
            function_words=None,
            adverbs=None,
            skip_infl=handwritten,
            emit_variants=False,
        )
        lexd_parts.append(stems_text)
        lexd_text = "\n".join(lexd_parts)

    LEXD_OUT.write_text(lexd_text, encoding="utf-8")
    total = len(lexd_text.splitlines())
    if args.gold_only:
        n_stems = sum(
            1 for l in lexd_text.splitlines() if l.startswith("LEXICON Stems")
        )
        print(f"lexd → {LEXD_OUT} ({total} Zeilen, {n_stems} Stems-Lexika, gold-only)")
    else:
        n_pfiles = len(lexd_parts) - 1  # ohne den generierten Stems-Teil
        n_stems = sum(
            1 for l in stems_text.splitlines() if l.startswith("LEXICON Stems")
        )
        print(
            f"lexd → {LEXD_OUT} ({total} Zeilen, "
            f"{n_pfiles} Paradigmen-Dateien, {n_stems} Stems-Lexika)"
        )

    # lexd CLI: Quelltext → ATT
    subprocess.run(
        ["lexd", str(LEXD_OUT), str(ATT_OUT)],
        check=True,
        stdout=subprocess.DEVNULL,
    )
    print(f"lexd → {ATT_OUT}")

    # hfst-txt2fst: ATT → HFST-Transducer
    subprocess.run(
        ["hfst-txt2fst", str(ATT_OUT), "-o", str(LEXICON_OUT)],
        check=True,
        stdout=subprocess.DEVNULL,
    )

    lexicon = hfst.HfstInputStream(str(LEXICON_OUT)).read()
    lexicon.convert(FOMA)
    print(f"Lexikon: {lexicon.number_of_states()} Zustände")

    # generator = lexicon ∘ Phonologie  (Analyse → Standardoberfläche)
    generator = _compose_chain(lexicon, rules.PHONOLOGY)
    print(f"generator (∘ Phonologie): {generator.number_of_states()} Zustände")

    analyser = hfst.HfstTransducer(generator)
    analyser.invert()
    analyser.minimize()

    # lenient = (T ∘ Faltung) ∘ (generator ∘ Faltung)⁻¹
    #   Variante → [Twanksta-j-Endung→Standard] → Skelett → Analyse.
    # Faltung (hfst/fold.FOLD_SURFACE): ortho-
    # SICHERE Teilmenge (Diakritika, palatales Twanksta-j gj/sj…, elaktr) ohne
    # Kasus-Vermischung. T: die weichvokalischen Twanksta-j-Flexionsendungen
    # (-jas~-es …), DATENGETRIEBEN aus beiden Wörterbüchern abgeleitet
    # (derive.derive_twanksta_j_pairs) — ersetzt die frühere generative
    # spellrelax-Schicht durch native, evidenzbasierte Endungen.
    fold = _compose_chain(hfst.regex(fold_mod.FOLD_SURFACE[0]),
                          fold_mod.FOLD_SURFACE[1:])
    input_fold = hfst.HfstTransducer(fold)
    if PRUSASPIRA.exists() and TWANKSTA.exists():
        pr = json.loads(PRUSASPIRA.read_text(encoding="utf-8"))
        tw = json.loads(TWANKSTA.read_text(encoding="utf-8"))
        pairs = derive.derive_twanksta_j_pairs(pr, tw)
        t_regex = fold_mod.twanksta_j_replace(pairs)
        if t_regex:
            T = hfst.regex(t_regex)
            T.convert(FOMA)
            input_fold = hfst.HfstTransducer(T)
            input_fold.compose(fold)   # Twanksta-j-Endung → Standard → Skelett
            input_fold.minimize()
            print(f"Twanksta-j-Endungen (abgeleitet): {len(pairs)} Muster")
    gen_skel = hfst.HfstTransducer(generator)
    gen_skel.compose(fold)        # Analyse → Skelett
    gen_skel.minimize()
    gen_skel.invert()             # Skelett → Analyse
    lenient = hfst.HfstTransducer(input_fold)
    lenient.compose(gen_skel)     # Oberfläche → (Std-Endung) → Skelett → Analyse
    lenient.minimize()
    print(f"lenient (∘ Faltung + Twanksta-j): {lenient.number_of_states()} Zustände")

    for fst, path in ((generator, GEN_OUT), (analyser, ANA_OUT), (lenient, LEN_OUT)):
        out = hfst.HfstOutputStream(filename=str(path), type=FOMA)
        out.write(fst)
        out.flush()
        out.close()
    print(f"Gespeichert: {GEN_OUT.name}, {ANA_OUT.name}, {LEN_OUT.name}")


if __name__ == "__main__":
    main()
