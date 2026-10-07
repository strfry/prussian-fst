#!/usr/bin/env python3
"""CG3-disambiguierte Analysen aller Korpora als CoNLL-U-Silberstandard.

Quellen: youtube (Korpus-JSON), awizi + twanksta (Markdown-Artikel aus
../prussian-bert/corpus/). Rest-Ambiguität wird nicht geraten, sondern
unterspezifiziert: exportiert werden nur Merkmale, die ALLE verbleibenden
Lesarten teilen (N Pl+Gen|Sg+Akk → Number/Case leer, MISC Ambig=2). Die
3. Person ist numeruslos modelliert (+P3 ohne Sg/Pl, wie im Baltischen) —
Verben wie „ast" tragen daher schlicht kein Number-Feature, ohne Ambig.
Sätze mit >50% unbekannten Wörtern gelten als fremdsprachliches Zitat
und werden übersprungen.

  python3 src/prussian_fst/export_conllu.py --out data/prussian_silver.conllu
"""

import argparse
import json
import sys
from pathlib import Path

# Dual-Mode: als Paketmodul (prussian_fst.export_conllu) relativ, als
# direkt ausgeführtes Skript flach (dann src/prussian_fst auf den Pfad legen).
try:
    from .cg3_pipeline import (DEFAULT_CORPUS, DEFAULT_DEP_GRAMMAR,
                               DEFAULT_FST, DEFAULT_GRAMMAR, REPO,
                               SENT_PUNCT, emit_cg_stream, is_word,
                               load_markdown_sentences, load_sentences,
                               lookup_types, parse_cg_stream, run_cg_proc)
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from cg3_pipeline import (DEFAULT_CORPUS, DEFAULT_DEP_GRAMMAR,
                              DEFAULT_FST, DEFAULT_GRAMMAR, REPO,
                              SENT_PUNCT, emit_cg_stream, is_word,
                              load_markdown_sentences, load_sentences,
                              lookup_types, parse_cg_stream, run_cg_proc)

BERT_CORPUS = REPO.parent / "prussian-bert/corpus"
DEFAULT_OUT = REPO / "data/prussian_silver.conllu"
FOREIGN_UNK_RATIO = 0.5

UPOS = {"N": "NOUN", "Prop": "PROPN", "A": "ADJ", "Pron": "PRON", "Num": "NUM",
        "V": "VERB", "Adv": "ADV", "Pr": "ADP", "Adp": "ADP", "Po": "ADP",
        "CC": "CCONJ", "CS": "SCONJ", "Pcle": "PART", "Interj": "INTJ",
        "Unk": "X"}

# internes Tag → UD-Feature. Rel (Modus relativus) → Mood=Qot wie der
# baltische Renarrativ; Subj → Mood=Cnd (Konditional/Konjunktiv).
# Person/Numerus ist am Verb fusioniert (Sg1/Sg2/SP3/Pl1/Pl2); SP3 trägt
# keinen Numerus (3. Person ist im Apreußischen numeruslos).
FEAT = {"Sg": ("Number", "Sing"), "Pl": ("Number", "Plur"),
        "Nom": ("Case", "Nom"), "Gen": ("Case", "Gen"),
        "Dat": ("Case", "Dat"), "Acc": ("Case", "Acc"),
        "Msc": ("Gender", "Masc"), "Fem": ("Gender", "Fem"),
        "Neu": ("Gender", "Neut"),
        "Prs": ("Tense", "Pres"), "Prt": ("Tense", "Past"),
        "Ind": ("Mood", "Ind"), "Imprt": ("Mood", "Imp"),
        "Opt": ("Mood", "Opt"), "Subj": ("Mood", "Cnd"),
        "Rel": ("Mood", "Qot"),
        # Pronominal-Person (bleibt +P1/+P2/+P3)
        "P1": ("Person", "1"), "P2": ("Person", "2"), "P3": ("Person", "3"),
        "Inf": ("VerbForm", "Inf"),
        "PrsPrc": ("VerbForm", "Part"), "PrfPrc": ("VerbForm", "Part"),
        "Act": ("Voice", "Act"), "Pss": ("Voice", "Pass"),
        "Refl": ("Reflex", "Yes"),
        "Comp": ("Degree", "Cmp"), "Superl": ("Degree", "Sup"),
        "Card": ("NumType", "Card"), "Ord": ("NumType", "Ord"),
        "Encl": ("PronType", "Clit")}

# Fusionierte Verb-Person/-Numerus → UD-Feature-Paare.
FUSED_PERSNUM = {"Sg1": (("Person", "1"), ("Number", "Sing")),
                 "Sg2": (("Person", "2"), ("Number", "Sing")),
                 "SP3": (("Person", "3"),),
                 "Pl1": (("Person", "1"), ("Number", "Plur")),
                 "Pl2": (("Person", "2"), ("Number", "Plur"))}


def reading_feats(tags: list[str]) -> frozenset[str]:
    feats = {f"{k}={v}" for t in tags if (kv := FEAT.get(t)) for k, v in [kv]}
    for t in tags:
        for k, v in FUSED_PERSNUM.get(t, ()):
            feats.add(f"{k}={v}")
    if "Po" in tags:
        feats.add("AdpType=Post")
    return frozenset(feats)


def _prep_government() -> dict[str, str]:
    """Lemma → Government-Kasus für rein regierende Präpositionen.

    Doppel-Rektierer stehen in keiner Liste und liefern keinen eindeutigen
    Kasus (Government entfällt — die Disambiguierung hat ihn am Komplement
    bereits aufgelöst)."""
    try:
        from .gen_cg3_sets import VALENCE_PATH, prep_lists
    except ImportError:
        from gen_cg3_sets import VALENCE_PATH, prep_lists
    if not VALENCE_PATH.exists():
        return {}
    preps = prep_lists(json.loads(VALENCE_PATH.read_text(encoding="utf-8")))
    return ({lm: "Acc" for lm in preps["Akk"]}
            | {lm: "Dat" for lm in preps["Dat"]})


GOVERNMENT = _prep_government()


def _reading_government(reading: dict, gov_map: dict[str, str]) -> str | None:
    tags = reading["tags"]
    if tags[0] not in ("Pr", "Adp", "Po") and "Po" not in tags:
        return None
    return gov_map.get(reading["lemma"])


def _upos(tags: list[str]) -> str:
    if tags[0] == "N" and "Prop" in tags:
        return "PROPN"
    return UPOS.get(tags[0], "X")


def unique(values: set) -> str:
    return values.pop() if len(values) == 1 else "_"


def rel_pos(i: int, dep: tuple[int, int] | None, n: int) -> int | None:
    """Fensterlokale Dependenznummern (#self->par) → satzlokale
    1-basierte Position, aufgelöst über die Differenz self−parent
    (robust gegen satzinterne Fensterneustarts)."""
    if not dep:
        return None
    self_n, par = dep
    if par in (0, self_n):
        return None
    pos = (i + 1) - (self_n - par)
    return pos if 1 <= pos <= n else None


def resolve_deps(cohorts: list[dict]) -> list[tuple[int, str] | None]:
    """(HEAD, DEPREL) pro Cohort aus #n->m und R:label:ID.

    Unangebundene Cohorts (#n->n): das erste Wort wird root, der Rest
    hängt als punct/dep daran."""
    n = len(cohorts)

    def parent_pos(i: int) -> int | None:
        return rel_pos(i, cohorts[i].get("dep"), n)

    # Wurzel: erstes unangebundenes Verb (Klauselkopf), sonst erstes
    # unangebundenes Wort (verblose Sätze), sonst Cohort 1.  Fenster
    # ganz ohne #n->m (kein SETPARENT gefeuert) laufen über denselben
    # Fallback: alles unangebunden → root + punct/dep.
    def is_verb(c: dict) -> bool:
        return any(r["tags"] and r["tags"][0] == "V" for r in c["readings"])

    candidates = [i + 1 for i, c in enumerate(cohorts)
                  if parent_pos(i) is None and is_word(c)]
    root = next((p for p in candidates if is_verb(cohorts[p - 1])),
                candidates[0] if candidates else 1)

    result: list[tuple[int, str] | None] = []
    for i, c in enumerate(cohorts):
        pos = i + 1
        par = parent_pos(i)
        if pos == root:
            result.append((0, "root"))
        elif par is None:
            tags0 = c["readings"][0]["tags"] if c["readings"] else []
            lab = "punct" if ("CLB" in tags0 or "PUNCT" in tags0) else "dep"
            result.append((root, lab))
        else:
            # Label der Relation, deren Ziel-ID die des Parents ist
            parent_rid = cohorts[par - 1].get("rid")
            rels = c.get("rels", [])
            lab = next((l for l, t in rels if t == parent_rid),
                       rels[0][0] if rels else "dep")
            result.append((par, lab))
    return result


def token_line(idx: int, cohort: dict, dep: tuple[int, str] | None = None,
               agr_parent: int | None = None) -> str:
    form = cohort["form"]
    readings = cohort["readings"]
    tags0 = readings[0]["tags"]

    if "CLB" in tags0 or "PUNCT" in tags0:
        cols = [form, form, "PUNCT", "_", "_"]
    elif "Unk" in tags0:
        cols = [form, "_", "X", "_", "_"]
    else:
        lemma = unique({r["lemma"] for r in readings})
        upos = unique({_upos(r["tags"]) for r in readings})
        xpos = unique({"+".join(r["tags"]) for r in readings})
        shared = frozenset.intersection(
            *(reading_feats(r["tags"]) for r in readings))
        feats = "|".join(sorted(shared, key=str.lower)) if shared else "_"
        cols = [form, lemma, upos, xpos, feats]

    misc = []
    gov = {g for r in readings if (g := _reading_government(r, GOVERNMENT))}
    if len(gov) == 1 and all(_reading_government(r, GOVERNMENT) for r in readings):
        misc.append(f"Gov={gov.pop()}")
    if len(readings) > 1:
        misc.append(f"Ambig={len(readings)}")
    # Regel-Provenienz (cg3_pipeline --conllu --trace): benannte
    # Grammatikregeln, die den Cohort berührt haben, und das echte
    # Kongruenz-Ziel der agr-head-Regeln (Lauf vor SECTION dep-tree).
    if cohort.get("rules"):
        misc.append("Rule=" + ",".join(cohort["rules"]))
    if agr_parent is not None:
        misc.append(f"AgrParent={agr_parent}")
    head, deprel = (str(dep[0]), dep[1]) if dep else ("_", "_")
    return "\t".join([str(idx), *cols, head, deprel, "_",
                      "|".join(misc) if misc else "_"])


def sentence_block(sent: dict, cohorts: list[dict],
                   source: str | None = None) -> str | None:
    """CoNLL-U-Block oder None (fremdsprachliches Zitat)."""
    words = [c for c in cohorts if is_word(c)]
    unk = sum(1 for c in words if "Unk" in c["readings"][0]["tags"])
    if words and unk / len(words) > FOREIGN_UNK_RATIO:
        return None
    lines = [f"# sent_id = {sent.get('sent_id', '?')}",
             f"# text = {sent['text']}"]
    if source is not None:
        lines.append(f"# source = {source}")
    deps = resolve_deps(cohorts)
    agr = [rel_pos(i, c.get("agr_dep"), len(cohorts))
           for i, c in enumerate(cohorts)]
    lines += [token_line(i, c, d, a)
              for i, (c, d, a) in enumerate(zip(cohorts, deps, agr), 1)]
    return "\n".join(lines)


def conllu_output(sentences: list[dict], cohorts: list[dict]) -> str:
    """Satzweise CoNLL-U-Blöcke aus dem geparsten Stream (Slicing über
    das n_coh-Idiom: erzwungener Satzend-Delimiter zählt mit)."""
    blocks = []
    idx = 0
    for s in sentences:
        n_coh = len(s["tokens"]) + (0 if s["tokens"][-1] in SENT_PUNCT else 1)
        block = sentence_block(s, cohorts[idx:idx + n_coh])
        idx += n_coh
        if block is not None:
            blocks.append(block)
    return "\n\n".join(blocks) + "\n\n"


def export_source(name: str, sentences: list[dict], fst: Path,
                  grammar: Path, dep_grammar: Path | None = None
                  ) -> tuple[list[str], dict]:
    types = {t for s in sentences for t in s["tokens"] if t[0].isalpha()}
    analyses = lookup_types(types, fst)
    cg_input = emit_cg_stream(sentences, analyses)
    stream = run_cg_proc(cg_input, grammar)
    if dep_grammar is not None:
        stream = run_cg_proc(stream, dep_grammar)
    cohorts = parse_cg_stream(stream)

    blocks = []
    stat = {"sätze": 0, "fremd": 0, "token": 0, "unk": 0,
            "upos": 0, "voll": 0}
    idx = 0
    for s in sentences:
        n_coh = len(s["tokens"]) + (0 if s["tokens"][-1] in SENT_PUNCT else 1)
        block = sentence_block(s, cohorts[idx:idx + n_coh], name)
        sent_cohorts = cohorts[idx:idx + n_coh]
        idx += n_coh
        if block is None:
            stat["fremd"] += 1
            continue
        stat["sätze"] += 1
        blocks.append(block)
        for c in sent_cohorts:
            if not is_word(c):
                continue
            stat["token"] += 1
            rs = c["readings"]
            if "Unk" in rs[0]["tags"]:
                stat["unk"] += 1
                continue
            if len({UPOS.get(r["tags"][0], "X") for r in rs}) == 1:
                stat["upos"] += 1
            if len(rs) == 1:
                stat["voll"] += 1
    return blocks, stat


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--fst", type=Path, default=DEFAULT_FST)
    ap.add_argument("--grammar", type=Path, default=DEFAULT_GRAMMAR)
    ap.add_argument("--dep-grammar", type=Path, default=DEFAULT_DEP_GRAMMAR)
    args = ap.parse_args()

    sources = [
        ("youtube", load_sentences(DEFAULT_CORPUS)),
        ("awizi", load_markdown_sentences(BERT_CORPUS / "awizi_articles")),
        ("twanksta", load_markdown_sentences(BERT_CORPUS / "twanksta_articles")),
    ]

    all_blocks = []
    print(f"{'Quelle':<10} {'Sätze':>6} {'fremd':>6} {'Token':>7} "
          f"{'unbek.':>7} {'UPOS':>6} {'voll':>6}")
    for name, sentences in sources:
        blocks, st = export_source(name, sentences, args.fst, args.grammar,
                                   args.dep_grammar)
        all_blocks.extend(blocks)
        tok = st["token"] or 1
        print(f"{name:<10} {st['sätze']:>6} {st['fremd']:>6} {st['token']:>7} "
              f"{st['unk'] / tok:>6.1%} {st['upos'] / tok:>5.1%} "
              f"{st['voll'] / tok:>5.1%}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("\n\n".join(all_blocks) + "\n\n", encoding="utf-8")
    print(f"\n{len(all_blocks)} Sätze → {args.out}")


if __name__ == "__main__":
    main()
