#!/usr/bin/env python3
"""Corpus → FST-Analysen → CG3-Stream → vislcg3 → Statistik.

Pipeline:
  1. Sätze aus dem YouTube-Korpus laden (text_clean)
  2. satzerhaltend tokenisieren (Wörter + Interpunktion als Cohorts)
  3. Types einmalig durch hfst-flookup batchen (Fallback: lowercase)
  4. CG3-Stream emittieren
  5. optional durch vislcg3 disambiguieren (inkl. Syntaxbaum via SETPARENT)
  6. optional Dependenz-Labels (dependency.cg3, ADDRELATION) als zweite Phase
  7. optional Ambiguitätsstatistik bzw. CoNLL-U auf stdout

Beispiele:
  python3 fst/scripts/cg3_pipeline.py --stats            # Vollkorpus, Kennzahlen
  python3 fst/scripts/cg3_pipeline.py --limit 20         # disambiguierter Stream
  python3 fst/scripts/cg3_pipeline.py --no-disamb        # roher CG-Input
  python3 fst/scripts/cg3_pipeline.py --deps --limit 20  # Stream mit R:label:ID
  echo "Labban dēinan!" | python3 fst/scripts/cg3_pipeline.py --text - --conllu
"""

import argparse
import json
import re
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

FST_DIR = Path(__file__).resolve().parents[1]
REPO = FST_DIR.parent
DEFAULT_CORPUS = REPO.parent / "prussian-corpus/parsed/youtube_corpus_sentences.json"
DEFAULT_FST = FST_DIR / "build/base.fst"
DEFAULT_LENIENT = FST_DIR / "build/lenient.fst"
DEFAULT_GRAMMAR = FST_DIR / "cg3/disambiguator.cg3"
DEFAULT_DEP_GRAMMAR = FST_DIR / "cg3/dependency.cg3"

SKIP_VIDEOS = {"qLwBCWtMuH8"}  # wie delta_review.py

# Satz-Delimiter (CG3 DELIMITERS) vs. sonstige Interpunktion
SENT_PUNCT = {".", "!", "?"}

# Kurzform-Funktionswörter (prussian-grammar syntax_rules.txt §1): einsilbige
# Präpositionen mit Langvokal verlieren die Länge vor mehrsilbigen Wörtern
# (ēn buttan → en buttan); analog belegte Adverb-Kurzformen (kwei → kwēi).
# Der FST kennt nur die Langformen.
PREP_SHORT = {"en": "ēn", "per": "pēr", "prei": "prēi",
              "sen": "sēn", "no": "nō", "er": "ēr",
              "kwei": "kwēi"}
TOKEN_RE = re.compile(r"[^\W\d_]+(?:['-][^\W\d_]+)*|[.!?,;:„“”\"()«»…—–-]", re.UNICODE)


def tokenize(text: str) -> list[str]:
    """Satzerhaltende Tokenisierung: Wörter und Interpunktion als Token."""
    return TOKEN_RE.findall(text)


def load_sentences(corpus_path: Path) -> list[dict]:
    """[{tokens, text, frequency, sent_id}] aus dem Korpus-JSON."""
    raw = json.loads(corpus_path.read_text(encoding="utf-8"))
    sentences = []
    for i, e in enumerate(raw):
        sources = e.get("sources", [])
        if sources and all(s.get("video_id") in SKIP_VIDEOS for s in sources):
            continue
        text = e.get("text_clean") or e.get("text") or ""
        toks = tokenize(text)
        if not any(t[0].isalpha() for t in toks if t):
            continue
        vid = sources[0].get("video_id", "") if sources else ""
        sentences.append({
            "text": text,
            "tokens": toks,
            "frequency": e.get("frequency", 1),
            "sent_id": f"yt-{vid}-{i}" if vid else f"yt-{i}",
        })
    return sentences


# Markdown-Aufräumen für die Artikel-Korpora (../prussian-bert/corpus/*):
# Links/Bilder auf den Linktext reduzieren, nackte URLs und Bilddateinamen raus.
MD_LINK = re.compile(r"!?\[([^\]]*)\]\([^)]*\)")
MD_URL = re.compile(r"https?://\S+|www\.\S+|\S+\.(?:jpe?g|png|gif|webp)\b\S*",
                    re.IGNORECASE)


def load_markdown_sentences(dirpath: Path) -> list[dict]:
    """[{tokens, text, frequency, sent_id}] aus einem Artikelverzeichnis.

    Überschriften (#…) und *Related*-/Metazeilen (*…) werden verworfen,
    Absätze an Satzinterpunktion getrennt."""
    sentences = []
    for f in sorted(dirpath.glob("*.md")):
        n_in_file = 0
        text = f.read_text(encoding="utf-8", errors="replace")
        lines = [l for l in text.split("\n")
                 if l.strip() and not l.strip().startswith(("#", "*"))]
        for para in lines:
            para = MD_LINK.sub(r"\1", para)
            para = MD_URL.sub(" ", para)
            for sent in re.split(r"(?<=[.!?])\s+", para):
                sent = sent.strip()
                toks = tokenize(sent)
                if not any(t[0].isalpha() for t in toks if t):
                    continue
                n_in_file += 1
                sentences.append({
                    "text": sent,
                    "tokens": toks,
                    "frequency": 1,
                    "sent_id": f"{f.stem}-{n_in_file}",
                })
    return sentences


# ── FST lookup ──

def flookup_batch(forms: list[str], fst_path: Path) -> dict[str, list[tuple[str, list[str]]]]:
    """Alle Formen einmal durch hfst-flookup; form → [(lemma, tags)]."""
    if not forms:
        return {}
    proc = subprocess.run(
        ["hfst-flookup", "-q", str(fst_path)],
        input="\n".join(forms) + "\n",
        capture_output=True, text=True, check=True,
    )
    analyses: dict[str, list[tuple[str, list[str]]]] = defaultdict(list)
    for line in proc.stdout.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        form, analysis = parts[0], parts[1]
        if analysis.endswith("+?"):
            continue  # unbekannt
        segs = analysis.split("+")
        lemma, tags = segs[0], segs[1:]
        if not tags:
            continue
        analyses[form].append((lemma, tags))
    return dict(analyses)


def titlecase(t: str) -> str:
    return t[0].upper() + t[1:]


def lookup_types(tokens: set[str], fst_path: Path,
                 lenient_path: Path | None = None) -> dict[str, list[tuple[str, list[str]]]]:
    """Lookup mit Fallback-Kaskade:
    Surface → lowercase → Titlecase → Kurzform → Korrektur-Layer (lenient).

    Titlecase fängt kleingeschriebene Vorkommen kapitalisierter Lemmata
    (Artikel schreiben 'dēiwan', der FST kennt nur 'Dēiwan' zu Dēiws)."""
    surface = flookup_batch(sorted(tokens), fst_path)
    missing = {t for t in tokens if t not in surface}
    alt_forms = ({t.lower() for t in missing if t.lower() != t}
                 | {titlecase(t) for t in missing if titlecase(t) != t})
    alt = flookup_batch(sorted(alt_forms), fst_path)
    long_preps = flookup_batch(sorted(set(PREP_SHORT.values())), fst_path)

    result = {}
    for t in tokens:
        if t in surface:
            result[t] = surface[t]
        elif t.lower() != t and t.lower() in alt:
            result[t] = alt[t.lower()]
        elif titlecase(t) != t and titlecase(t) in alt:
            result[t] = alt[titlecase(t)]
        elif t.lower() in PREP_SHORT:
            result[t] = long_preps.get(PREP_SHORT[t.lower()], [])
        else:
            result[t] = []

    # Letzte Stufe: verbleibende Unbekannte gegen den Korrektur-Layer
    # (norm.regex ∘ base.fst — orthographische Varianten)
    if lenient_path is None:
        lenient_path = DEFAULT_LENIENT
    if lenient_path.exists():
        still_missing = {t for t, a in result.items() if not a}
        variants = ({t.lower() for t in still_missing}
                    | {titlecase(t) for t in still_missing})
        lenient = flookup_batch(sorted(variants), lenient_path)
        for t in result:
            if result[t]:
                continue
            result[t] = lenient.get(t.lower()) or lenient.get(titlecase(t)) or []
    return result


# ── CG3 stream ──

def cohort_lines(tok: str, readings: list[tuple[str, list[str]]]) -> list[str]:
    lines = [f'"<{tok}>"']
    if tok in SENT_PUNCT:
        lines.append(f'\t"{tok}" CLB')
    elif not tok[0].isalpha():
        lines.append(f'\t"{tok}" PUNCT')
    elif not readings:
        lines.append(f'\t"{tok}" Unk')
    else:
        for lemma, tags in readings:
            lines.append(f'\t"{lemma}" {" ".join(tags)}')
    return lines


def emit_cg_stream(sentences: list[dict], analyses: dict) -> str:
    out = []
    for s in sentences:
        for tok in s["tokens"]:
            out.extend(cohort_lines(tok, analyses.get(tok, [])))
        # Satzende erzwingen, falls keine Delimiter-Interpunktion vorhanden
        if not s["tokens"] or s["tokens"][-1] not in SENT_PUNCT:
            out.extend(cohort_lines(".", []))
    return "\n".join(out) + "\n"


def run_vislcg3(cg_input: str, grammar: Path, trace: bool = False) -> str:
    cmd = ["vislcg3", "-g", str(grammar), "--unsafe"]
    if trace:
        cmd.append("--trace")
    proc = subprocess.run(cmd, input=cg_input, capture_output=True,
                          text=True, check=True)
    if proc.stderr.strip():
        print(proc.stderr, file=sys.stderr)
    return proc.stdout


# ── Statistik ──

# Dependenz- und Relations-Annotationen der CG3-Dependenzschicht:
# "#n->m" (Parent, fensterlokal nummeriert), "ID:n"/"R:label:n"
# (ADDRELATION, global nummeriert), "@pred"/"@fin" (Mapping-Tags).
DEP_RE = re.compile(r"#(\d+)->(\d+)$")
REL_RE = re.compile(r"R:([A-Za-z_]+):(\d+)$")
RELID_RE = re.compile(r"ID:(\d+)$")
HIDDEN_TAGS = ("REMOVE:", "SELECT:", "ADD:", "MAP:", "SETPARENT:",
               "ADDRELATION:", "#", "ID:", "R:", "@")


def parse_cg_stream(stream: str) -> list[list[dict]]:
    """CG3-Stream → Liste von Cohorts:
    {form, readings:[{lemma,tags}], dep:(self,parent)|None, rid, rels}."""
    cohorts = []
    cur = None
    for line in stream.splitlines():
        if line.startswith('"<'):
            cur = {"form": line[2:line.rfind('>"')], "readings": [],
                   "dep": None, "rid": None, "rels": []}
            cohorts.append(cur)
        elif line.startswith("\t") and cur is not None:
            m = re.match(r'\t"(.*)" (.*)$', line)
            if m:
                raw = m.group(2).split()
                for t in raw:
                    if md := DEP_RE.match(t):
                        cur["dep"] = (int(md.group(1)), int(md.group(2)))
                    elif mi := RELID_RE.match(t):
                        cur["rid"] = int(mi.group(1))
                    elif mr := REL_RE.match(t):
                        rel = (mr.group(1), int(mr.group(2)))
                        if rel not in cur["rels"]:
                            cur["rels"].append(rel)
                tags = [t for t in raw if not t.startswith(HIDDEN_TAGS)]
                cur["readings"].append({"lemma": m.group(1), "tags": tags})
    return cohorts


def is_word(cohort: dict) -> bool:
    if not cohort["readings"]:
        return False
    tags0 = cohort["readings"][0]["tags"]
    return "CLB" not in tags0 and "PUNCT" not in tags0


def ambiguity_stats(cohorts: list[dict], weights: list[int]) -> dict:
    """Kennzahlen über Wort-Cohorts (tokengewichtet via Satzfrequenz)."""
    n = unamb = unknown = collapsed = 0
    total_readings = 0
    pos_pairs = Counter()
    sig_pairs = Counter()
    for c, w in zip(cohorts, weights):
        rs = c["readings"]
        if not rs:
            # kollabiert (--unsafe): war ein Wort-Cohort, alle Lesarten weg
            n += w
            collapsed += w
            continue
        if not is_word(c):
            continue
        n += w
        if any("Unk" in r["tags"] for r in rs):
            unknown += w
            continue
        total_readings += len(rs) * w
        if len(rs) == 1:
            unamb += w
        else:
            pos = tuple(sorted({r["tags"][0] for r in rs}))
            if len(pos) > 1:
                pos_pairs[("|".join(pos))] += w
            else:
                sigs = tuple(sorted({"+".join(r["tags"][1:]) for r in rs}))
                sig_pairs[f"{pos[0]}: " + " | ".join(sigs)] += w
    known = n - unknown - collapsed
    return {
        "word_tokens": n,
        "unknown_pct": 100 * unknown / n if n else 0,
        "collapsed": collapsed,
        "collapsed_pct": 100 * collapsed / n if n else 0,
        "avg_readings": total_readings / known if known else 0,
        "unambiguous_pct": 100 * unamb / known if known else 0,
        "pos_pairs": pos_pairs,
        "sig_pairs": sig_pairs,
    }


def print_stats(label: str, st: dict):
    print(f"── {label} ──")
    print(f"  Wort-Token:        {st['word_tokens']}")
    print(f"  unbekannt:         {st['unknown_pct']:.1f}%")
    print(f"  kollabiert (∅):    {st['collapsed_pct']:.1f}%  ({st['collapsed']})")
    print(f"  Ø Lesarten/Token:  {st['avg_readings']:.2f}")
    print(f"  eindeutig:         {st['unambiguous_pct']:.1f}%")
    if st["pos_pairs"]:
        print("  Top POS-Ambiguität:")
        for k, v in st["pos_pairs"].most_common(8):
            print(f"    {v:>7}  {k}")
    if st["sig_pairs"]:
        print("  Top Signatur-Ambiguität (POS eindeutig):")
        for k, v in st["sig_pairs"].most_common(8):
            print(f"    {v:>7}  {k[:90]}")


# ── Error Detection ──

def detect_errors(sentences: list[dict], before: list[dict],
                   after: list[dict]) -> list[dict]:
    """Vergleicht vor/nach-Cohorts und meldet:
    - Zero-Reading-Cohorts (alle Lesarten entfernt)
    - Cohorts mit Error-Tags (@Error*)

    Gibt Liste von Diktaten zurück: {satz, token, fehler, original_lesarten}.
    """
    errors = []
    idx = 0
    for s in sentences:
        n_coh = len(s["tokens"])
        if s["tokens"][-1] not in SENT_PUNCT:
            n_coh += 1
        sent_after = after[idx:idx + n_coh]
        sent_before = before[idx:idx + n_coh]
        idx += n_coh

        for coh_i, (c_bef, c_aft) in enumerate(zip(sent_before, sent_after)):
            tok = c_aft["form"]
            rs_bef = c_bef["readings"]
            rs_aft = c_aft["readings"]

            if not rs_aft:
                # Alle Lesarten entfernt → Kollaps
                orig = [f"{r['lemma']}+{'+'.join(r['tags'])}" for r in rs_bef] if rs_bef else []
                errors.append({
                    "satz": s["text"],
                    "token": tok,
                    "fehler": "kollabiert",
                    "original": orig,
                })
            else:
                # Nach Error-Tags in den überlebenden Lesarten suchen
                for r in rs_aft:
                    etags = [t for t in r["tags"] if t.startswith("@Error")]
                    if etags:
                        errors.append({
                            "satz": s["text"],
                            "token": tok,
                            "fehler": "+".join(etags),
                            "original": [],
                        })

    return errors


def print_errors(errors: list[dict]):
    if not errors:
        print("Keine Fehler gefunden.")
        return
    print(f"── Fehler ({len(errors)}) ──")
    for e in errors:
        print(f"\n  Satz: {e['satz']}")
        print(f"  Token: {e['token']}")
        print(f"  Fehler: {e['fehler']}")
        if e["original"]:
            print(f"  entfernte Lesarten: {', '.join(e['original'][:5])}"
                  f"{' …' if len(e['original']) > 5 else ''}")


# ── Top ambige Sätze ──

def top_ambiguous(sentences: list[dict], before: list[dict],
                  after: list[dict], limit: int = 20) -> list[dict]:
    """Findet Sätze mit den meisten mehrdeutigen Token nach Disambiguierung.

    Zurück: [{satz, freq, n_ambig, n_unk, n_collapsed, token_details}],
    sortiert nach n_ambig (absteigend), maximal *limit* Sätze.
    """
    results = []
    idx = 0
    for s in sentences:
        n_coh = len(s["tokens"]) + (0 if s["tokens"][-1] in SENT_PUNCT else 1)
        sent_before = before[idx:idx + n_coh]
        sent_after = after[idx:idx + n_coh]
        idx += n_coh

        details = []
        n_ambig = n_unk = n_collapsed = 0
        for c_bef, c_aft in zip(sent_before, sent_after):
            if not is_word(c_aft):
                continue
            rs_bef = c_bef["readings"]
            rs_aft = c_aft["readings"]
            if not rs_aft:
                n_collapsed += 1
                details.append((c_aft["form"], "KOLLABIERT", rs_bef))
            elif any("Unk" in r["tags"] for r in rs_aft):
                n_unk += 1
            elif len(rs_aft) > 1:
                n_ambig += 1
                details.append((c_aft["form"], rs_aft, rs_bef))

        if n_ambig + n_collapsed > 0:
            results.append({
                "satz": s["text"],
                "freq": s["frequency"],
                "n_ambig": n_ambig,
                "n_unk": n_unk,
                "n_collapsed": n_collapsed,
                "details": details,
            })

    results.sort(key=lambda x: (x["n_ambig"] + x["n_collapsed"]), reverse=True)
    return results[:limit]


def print_top_ambiguous(results: list[dict], top_n: int = 10):
    for i, r in enumerate(results[:top_n], 1):
        total = r["n_ambig"] + r["n_collapsed"]
        print(f"\n── #{i}  ({total} ambig, freq={r['freq']}) ──")
        print(f"  {r['satz']}")
        for tok, rs_aft, rs_bef in r["details"]:
            if rs_aft == "KOLLABIERT":
                orig = " | ".join(f"{r['lemma']}+{'+'.join(r['tags'])}"
                                  for r in rs_bef)
                print(f"  ❌ {tok}  — kollabiert (vorher: {orig})")
            else:
                aft = " | ".join(f"{r['lemma']}+{'+'.join(r['tags'])}"
                                for r in rs_aft)
                bef = len(rs_bef)
                print(f"  ⚠ {tok}  → {aft}  ({bef}→{len(rs_aft)})")


# ── Main ──

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    ap.add_argument("--corpus-md", type=Path, action="append", metavar="DIR",
                    help="Markdown-Artikelverzeichnis statt Korpus-JSON "
                         "(wiederholbar)")
    ap.add_argument("--fst", type=Path, default=DEFAULT_FST)
    ap.add_argument("--grammar", type=Path, default=DEFAULT_GRAMMAR)
    ap.add_argument("--dep-grammar", type=Path, default=DEFAULT_DEP_GRAMMAR)
    ap.add_argument("--text", help="Einzeltext statt Korpus ('-' = stdin)")
    ap.add_argument("--limit", type=int, help="nur die ersten N Sätze")
    ap.add_argument("--no-disamb", action="store_true",
                    help="rohen CG-Input ausgeben (ohne vislcg3)")
    ap.add_argument("--deps", action="store_true",
                    help="Label-Phase (dependency.cg3) auf den Stream anwenden")
    ap.add_argument("--conllu", action="store_true",
                    help="CoNLL-U ausgeben (impliziert --deps)")
    ap.add_argument("--trace", action="store_true", help="vislcg3 --trace")
    ap.add_argument("--stats", action="store_true",
                    help="nur Kennzahlen (vorher/nachher) auf stdout")
    ap.add_argument("--detect-errors", action="store_true",
                    help="Fehlererkennung: Kollaps/Error-Tags pro Satz")
    ap.add_argument("--top-ambig", type=int, nargs="?", const=20, metavar="N",
                    help="Top N Sätze mit den meisten ambigen Token anzeigen "
                         "(Default: 20)")
    args = ap.parse_args()

    if args.text is not None:
        text = sys.stdin.read() if args.text == "-" else args.text
        sentences = [{"text": text, "tokens": tokenize(text), "frequency": 1}]
    elif args.corpus_md:
        sentences = [s for d in args.corpus_md for s in load_markdown_sentences(d)]
        if args.limit:
            sentences = sentences[:args.limit]
    else:
        sentences = load_sentences(args.corpus)
        if args.limit:
            sentences = sentences[:args.limit]

    types = {t for s in sentences for t in s["tokens"] if t[0].isalpha()}
    analyses = lookup_types(types, args.fst)
    cg_input = emit_cg_stream(sentences, analyses)

    if args.no_disamb:
        sys.stdout.write(cg_input)
        return

    output = run_vislcg3(cg_input, args.grammar, trace=args.trace)
    if args.deps or args.conllu:
        output = run_vislcg3(output, args.dep_grammar, trace=args.trace)

    if args.conllu:
        from export_conllu import sentence_block
        cohorts = parse_cg_stream(output)
        blocks = []
        idx = 0
        for s in sentences:
            n_coh = len(s["tokens"]) + (0 if s["tokens"][-1] in SENT_PUNCT else 1)
            block = sentence_block(s, cohorts[idx:idx + n_coh])
            idx += n_coh
            if block is not None:
                blocks.append(block)
        sys.stdout.write("\n\n".join(blocks) + "\n\n")
        return

    # Gewichte: Cohort → Frequenz seines Satzes
    weights = []
    for s in sentences:
        n_coh = len(s["tokens"]) + (0 if s["tokens"][-1] in SENT_PUNCT else 1)
        weights.extend([s["frequency"]] * n_coh)

    before = parse_cg_stream(cg_input)
    after = parse_cg_stream(output)
    assert len(before) == len(after) == len(weights), \
        f"Cohort-Zählung inkonsistent: {len(before)}/{len(after)}/{len(weights)}"

    if args.stats:
        src = (", ".join(d.name for d in args.corpus_md) if args.corpus_md
               else args.corpus.name)
        print(f"Sätze: {len(sentences)}  (Korpus: {src})")
        print_stats("vor Disambiguierung", ambiguity_stats(before, weights))
        print_stats("nach Disambiguierung", ambiguity_stats(after, weights))

    if args.top_ambig:
        top = top_ambiguous(sentences, before, after, args.top_ambig)
        print_top_ambiguous(top, top_n=min(20, args.top_ambig))

    if args.detect_errors:
        errors = detect_errors(sentences, before, after)
        print_errors(errors)

    if not args.stats and not args.top_ambig and not args.detect_errors:
        sys.stdout.write(output)


if __name__ == "__main__":
    main()
