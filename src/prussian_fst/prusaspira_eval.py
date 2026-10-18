#!/usr/bin/env python3
"""Evaluation der Stufen lenient / prusaspira (base .o. norm/*.regex) — Messwerkzeug.

Baut Varianten der Kette in-memory (python-hfst) und misst je Variante:

  * Paar-Recall (build/ps_pairs.tsv, split=test, nur nicht-identische Paare, deren
    twanksta-Form base-analysierbar ist): Treffer, wenn die Analysen der
    Prusaspira-Form die base-Analysen der twanksta-Form schneiden. Je Tag-Klasse.
  * Tatoeba (Prusaspira-Konvention) und YouTube: Token-/Type-Abdeckung und Lesarten
    pro abgedecktem Token.

Leave-one-out über die Prusaspira-Layer: jede einzelne Regel (``define``) wird aus
der prusaspira-Kette entfernt; die Deltas zeigen, was sie an Abdeckung bringt und an
Ambiguität kostet — Grundlage, um fragwürdige Regeln einzeln abzuwägen.

Ausgabe: build/prusaspira_eval.md

  make eval-prusaspira
"""

from __future__ import annotations

import collections
import csv
import json
import re
import sys
from pathlib import Path

import hfst

FST = Path(__file__).resolve().parents[2]
BUILD = FST / "build"
NORM = FST / "norm"
TATOEBA = (FST.parent.parent / "prussian-llm-tatoeba"
           / "Sentence pairs in Prūsų kalba-Lenkų - 2026-05-29.tsv")
YOUTUBE = FST.parent / "corpus" / "parsed" / "youtube_corpus_sentences.json"
PAIRS = BUILD / "ps_pairs.tsv"
OUT = BUILD / "prusaspira_eval.md"

# Muss zu LENIENT_LAYERS / PRUSASPIRA_LAYERS im Makefile passen.
LENIENT_CHAIN = ["macron", "degem", "ortho"]
PS_LAYERS = ["palatal", "length"]
PS_CHAIN = PS_LAYERS + LENIENT_CHAIN
OL = hfst.ImplementationType.HFST_OL_TYPE
TOKEN = re.compile(r"[^\W\d_]+(?:['’][^\W\d_]+)?")

# Dual-Mode wie cg3_pipeline: als Paketmodul relativ, als Skript flach.
try:
    from .prusaspira_pairs import tag_class
except ImportError:
    from prusaspira_pairs import tag_class


# ── Layer als Regelliste (aus den define-Zeilen der regex-Skripte) ──
def layer_rules(name: str) -> tuple[dict, list]:
    """(defines, Regel-Reihenfolge) eines norm-Skripts. Regeln = die Namen in der
    ``regex A .o. B …``-Zeile; übrige defines (Vowel, Cons) sind Hilfsmengen."""
    defines, order = {}, []
    for line in open(NORM / f"{name}.regex", encoding="utf-8"):
        line = line.split("!")[0].strip()
        m = re.match(r"define\s+(\w+)\s+(.*);$", line)
        if m:
            defines[m.group(1)] = m.group(2)
        m = re.match(r"regex\s+(.*);$", line)
        if m:
            order = [x.strip() for x in m.group(1).split(".o.")]
    return defines, order


_RULE_CACHE: dict = {}


def compile_rule(layer: str, rule: str) -> hfst.HfstTransducer:
    key = (layer, rule)
    if key not in _RULE_CACHE:
        defines, _ = layer_rules(layer)
        comp = hfst.XreCompiler()
        for n, x in defines.items():
            if n != rule:
                comp.define_xre(n, x)
        tr = comp.compile(defines[rule])
        if tr is None:
            raise ValueError(f"{layer}:{rule} kompiliert nicht")
        _RULE_CACHE[key] = tr
    return _RULE_CACHE[key]


def chain(layers: list[str], drop: tuple[str, str] | None = None) -> hfst.HfstTransducer:
    """base .o. Regeln der Layer (in Skript-Reihenfolge), optional ohne eine Regel
    (``(layer, rule)``) oder einen ganzen Layer (``(layer, "*")``)."""
    tr = hfst.HfstInputStream(str(BUILD / "base.fst")).read()
    for layer in layers:
        if drop == (layer, "*"):
            continue
        _, order = layer_rules(layer)
        for rule in order:
            if drop == (layer, rule):
                continue
            tr.compose(compile_rule(layer, rule))
    tr.minimize()
    tr.invert()
    tr.convert(OL)
    return tr


def analyses(tr, form: str) -> set[str]:
    out = {a for a, _ in tr.lookup(form) if not a.endswith("+?")}
    if not out and form[:1].isupper():
        out = {a for a, _ in tr.lookup(form.lower()) if not a.endswith("+?")}
    return out


# ── Daten ──
def tatoeba_tokens() -> collections.Counter:
    c = collections.Counter()
    seen = set()
    with open(TATOEBA, encoding="utf-8") as fh:
        for row in csv.reader(fh, delimiter="\t"):
            if len(row) > 1 and row[1] not in seen:
                seen.add(row[1])
                c.update(TOKEN.findall(row[1]))
    return c


def youtube_tokens() -> collections.Counter:
    c = collections.Counter()
    for s in json.load(open(YOUTUBE, encoding="utf-8")):
        c.update(TOKEN.findall(s.get("text_clean") or s.get("text") or ""))
    return c


def test_pairs(base) -> list[tuple[str, str, str, set]]:
    out = []
    for line in open(PAIRS, encoding="utf-8"):
        tw, ps, tag, _lemma, split = line.rstrip("\n").split("\t")
        if split != "test" or tw == ps:
            continue
        gold = analyses(base, tw)
        if gold:
            out.append((tw, ps, tag_class(tag), gold))
    return out


# ── Metriken ──
def corpus_metrics(tr, toks: collections.Counter) -> dict:
    cov_tok = cov_typ = readings = 0
    for form, n in toks.items():
        a = analyses(tr, form)
        if a:
            cov_typ += 1
            cov_tok += n
            readings += n * len(a)
    total = sum(toks.values())
    return {"tok": cov_tok / total, "typ": cov_typ / len(toks),
            "amb": readings / cov_tok if cov_tok else 0.0}


def pair_metrics(tr, pairs) -> dict:
    hit, tot = collections.Counter(), collections.Counter()
    for _tw, ps, cls, gold in pairs:
        tot[cls] += 1
        if analyses(tr, ps) & gold:
            hit[cls] += 1
    res = {c: hit[c] / tot[c] for c in tot}
    res["all"] = sum(hit.values()) / sum(tot.values())
    return res


def evaluate(tr, data) -> dict:
    tat, yt, pairs = data
    return {"pairs": pair_metrics(tr, pairs), "tat": corpus_metrics(tr, tat),
            "yt": corpus_metrics(tr, yt)}


def main() -> None:
    base = chain([])
    data = (tatoeba_tokens(), youtube_tokens(), test_pairs(base))
    classes = sorted(collections.Counter(p[2] for p in data[2]).items(),
                     key=lambda kv: -kv[1])
    variants = {"base": base, "lenient": chain(LENIENT_CHAIN),
                "prusaspira": chain(PS_CHAIN)}
    res = {name: evaluate(tr, data) for name, tr in variants.items()}
    full = res["prusaspira"]

    loo = {}
    for layer in PS_LAYERS:
        loo[(layer, "*")] = evaluate(chain(PS_CHAIN, (layer, "*")), data)
        for rule in layer_rules(layer)[1]:
            loo[(layer, rule)] = evaluate(chain(PS_CHAIN, (layer, rule)), data)
            print(f"  loo {layer}:{rule}", file=sys.stderr)

    L = ["# Evaluation lenient / prusaspira", "",
         f"Testpaare (nicht-identisch, twanksta-Form base-analysierbar): {len(data[2])} · "
         f"Tatoeba: {sum(data[0].values())} Tokens / {len(data[0])} Types · "
         f"YouTube: {sum(data[1].values())} Tokens / {len(data[1])} Types", "",
         f"prusaspira: base .o. {' .o. '.join(PS_CHAIN)}", "",
         "## Varianten", "",
         "| Variante | Paar-Recall | " + " | ".join(c for c, _ in classes)
         + " | Tatoeba tok | Tatoeba typ | Tatoeba Lesarten | YT tok | YT typ | YT Lesarten |",
         "|---|" + "---:|" * (len(classes) + 7)]
    for name, r in res.items():
        L.append(f"| {name} | {r['pairs']['all']:.1%} | "
                 + " | ".join(f"{r['pairs'].get(c, 0):.1%}" for c, _ in classes)
                 + f" | {r['tat']['tok']:.1%} | {r['tat']['typ']:.1%} | {r['tat']['amb']:.2f}"
                 + f" | {r['yt']['tok']:.1%} | {r['yt']['typ']:.1%} | {r['yt']['amb']:.2f} |")
    L += ["", "Klassen-Größen: " + ", ".join(f"{c} {n}" for c, n in classes), "",
          "## Leave-one-out (Delta gegenüber „prusaspira“, Prozentpunkte)", "",
          "Positiv bei Recall/Abdeckung = die Regel bringt so viel; positiv bei Lesarten =",
          "die Regel kostet so viel Ambiguität.", "",
          "| Layer | Regel | Paar-Recall | Tatoeba tok | Tatoeba typ | Tatoeba Lesarten "
          "| YT tok | YT typ | YT Lesarten |",
          "|---|---|---:|---:|---:|---:|---:|---:|---:|"]
    for (layer, rule), r in loo.items():
        d = lambda a, b: 100 * (a - b)  # noqa: E731
        L.append(f"| {layer} | {rule if rule != '*' else '**ganzer Layer**'} "
                 f"| {d(full['pairs']['all'], r['pairs']['all']):+.2f} "
                 f"| {d(full['tat']['tok'], r['tat']['tok']):+.2f} "
                 f"| {d(full['tat']['typ'], r['tat']['typ']):+.2f} "
                 f"| {full['tat']['amb'] - r['tat']['amb']:+.3f} "
                 f"| {d(full['yt']['tok'], r['yt']['tok']):+.2f} "
                 f"| {d(full['yt']['typ'], r['yt']['typ']):+.2f} "
                 f"| {full['yt']['amb'] - r['yt']['amb']:+.3f} |")

    # Rest-OOV Tatoeba
    tr = variants["prusaspira"]
    oov = [(n, f) for f, n in data[0].items() if not analyses(tr, f)]
    oov.sort(reverse=True)
    L += ["", "## Tatoeba: häufigste Rest-OOV (prusaspira)", "",
          ", ".join(f"{f} ({n})" for n, f in oov[:50])]
    OUT.write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L[:14 + len(res)]))
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
