#!/usr/bin/env python3
"""Corpus → FST-Analysen → CG3-Stream → cg-proc → Statistik.

Pipeline:
   1. Sätze aus dem YouTube-Korpus laden (text_clean)
   2. satzerhaltend tokenisieren (Wörter + Interpunktion als Cohorts)
   3. Types einmalig durch hfst-flookup batchen (Fallback: lowercase)
   4. CG3-Stream emittieren
   5. optional durch cg-proc disambiguieren (inkl. Syntaxbaum via SETPARENT)
   6. optional Dependenz-Labels (dependency.cg3, ADDRELATION) als zweite Phase
   7. optional Ambiguitätsstatistik bzw. CoNLL-U auf stdout

Beispiele:
  python3 src/prussian_fst/cg3_pipeline.py --stats            # Vollkorpus, Kennzahlen
  python3 src/prussian_fst/cg3_pipeline.py --limit 20         # disambiguierter Stream
  python3 src/prussian_fst/cg3_pipeline.py --no-disamb        # roher CG-Input
  python3 src/prussian_fst/cg3_pipeline.py --deps --limit 20  # Stream mit R:label:ID
  echo "Labban dēinan!" | python3 src/prussian_fst/cg3_pipeline.py --text - --conllu
  # --conllu --trace: zusätzlich Regel-Provenienz in MISC —
  # Rule=<name,…> (benannte Grammatikregeln laut --trace) und
  # AgrParent=<id> (Kongruenz-Ziel der agr-head-Regeln, Lauf bis
  # SECTION dep-tree).  Signatur fürs MCP-Frontend (fsg_check).
  echo "As pūwa sen laīwu." | python3 src/prussian_fst/cg3_pipeline.py --text - --validate
  # --validate: Prüf-Pass (validator.cg3, &-Fehler-Tags) → dreiwertiges
  # JSON pro Satz: violations_found / verified_in_coverage /
  # out_of_coverage.  „Kein Fehler-Tag" heißt NICHT „korrekt" —
  # out_of_coverage (Unbekannte, Kollaps, Restambiguität, keine
  # anwendbare Prüfregel) ist ein eigener Zustand.
"""

import argparse
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DEFAULT_CORPUS = REPO.parent / "corpus/parsed/youtube_corpus_sentences.json"
DEFAULT_FST = REPO / "build/base.hfstol"
DEFAULT_LENIENT = REPO / "build/lenient.hfstol"
DEFAULT_FST_GEN = REPO / "build/base.gen.hfstol"
DEFAULT_GRAMMAR = REPO / "cg3/disambiguator.cg3"
DEFAULT_DEP_GRAMMAR = REPO / "cg3/dependency.cg3"
DEFAULT_VALIDATOR_GRAMMAR = REPO / "cg3/validator.cg3"
DEFAULT_GRAMMAR_BIN = REPO / "build/cg3/disambiguator.bin"
DEFAULT_DEP_GRAMMAR_BIN = REPO / "build/cg3/dependency.bin"
DEFAULT_VALIDATOR_GRAMMAR_BIN = REPO / "build/cg3/validator.bin"

# Dual-Mode: als Paketmodul (prussian_fst.cg3_pipeline) relativ, als
# direkt ausgeführtes Skript (sys.path[0] = fst/scripts) flach.
try:
    from .fst_lookup import flookup_batch
except ImportError:
    from fst_lookup import flookup_batch

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


def text_to_sentences(text: str) -> list[dict]:
    """Freitext → Satz-Dikte ({text, tokens, frequency, sent_id}).

    An Satzinterpunktion getrennt — jeder Satz wird downstream ein
    eigener CoNLL-U-Block bzw. ein eigenes Validierungsergebnis
    (wie load_markdown_sentences).  ValueError bei leerem Input."""
    sentences = []
    for i, sent in enumerate(re.split(r"(?<=[.!?])\s+", text.strip()), 1):
        toks = tokenize(sent)
        if toks:
            sentences.append({"text": sent, "tokens": toks,
                              "frequency": 1, "sent_id": f"text-{i}"})
    if not sentences:
        raise ValueError("Kein analysierbarer Text.")
    return sentences


def build_cg_input(sentences: list[dict], fst_path: Path | None = None) -> str:
    """Satz-Dikte → FST-Lookup (Types einmalig) → roher CG3-Stream."""
    types = {t for s in sentences for t in s["tokens"] if t[0].isalpha()}
    analyses = lookup_types(types, fst_path or DEFAULT_FST)
    return emit_cg_stream(sentences, analyses)


def grammar_bin_path(grammar_cg3: Path) -> Path:
    """Derive compiled binary path from a text .cg3 path:
    cg3/disambiguator.cg3 → build/cg3/disambiguator.bin"""
    return REPO / "build" / "cg3" / (grammar_cg3.stem + ".bin")


def run_cg_proc(cg_input: str, grammar: Path, trace: bool = False,
                sections: int | None = None,
                timeout: float | None = None) -> str:
    cmd = ["cg-proc", "-f", "0"]
    if trace:
        cmd.append("-t")
    if sections is not None:
        cmd += ["-s", str(sections)]
    # Accept .cg3 (derive .bin) or .bin directly
    if grammar.suffix == ".cg3":
        grammar = grammar_bin_path(grammar)
    cmd.append(str(grammar))
    proc = subprocess.run(cmd, input=cg_input, capture_output=True,
                          text=True, check=True, timeout=timeout)
    if proc.stderr.strip():
        print(proc.stderr, file=sys.stderr)
    return proc.stdout


def sections_before(grammar: Path, name: str = "dep-tree") -> int | None:
    """Ordinal der letzten Sektion VOR der benannten Sektion (für
    --sections): Cohort-Parents bis dahin stammen allein aus den
    agr-head-Regeln (BEFORE-SECTIONS + Refresh), nicht aus der
    Baumschicht."""
    n = 0
    for line in grammar.read_text(encoding="utf-8").splitlines():
        m = re.match(r"SECTION(?:\s+(\S+)\s*;?)?\s*$", line.strip())
        if m:
            if m.group(1) == name:
                return n
            n += 1
    return None


def attach_agr_parents(cg_input: str, cohorts: list[dict],
                       grammar: Path | None = None,
                       timeout: float | None = None) -> None:
    """AgrParent-Provenienz: Zweitlauf, der VOR der Baumschicht
    (SECTION dep-tree) abbricht — Parents stammen dort allein aus den
    agr-head-Regeln.  Der Ziel-Index wandert als c["agr_dep"] in die
    Cohorts (export_conllu.token_line rendert ihn als AgrParent=…)."""
    grammar = grammar or DEFAULT_GRAMMAR
    n_pre = sections_before(grammar)
    if not n_pre:
        return
    pre = parse_cg_stream(
        run_cg_proc(cg_input, grammar, sections=n_pre, timeout=timeout))
    assert len(pre) == len(cohorts), \
        f"Cohort-Zählung Vorlauf: {len(pre)}/{len(cohorts)}"
    for c, p in zip(cohorts, pre):
        d = p.get("dep")
        if d and d[1] not in (0, d[0]):
            c["agr_dep"] = d


# ── Statistik ──

# Dependenz- und Relations-Annotationen der CG3-Dependenzschicht:
# "#n->m" (Parent, fensterlokal nummeriert), "ID:n"/"R:label:n"
# (ADDRELATION, global nummeriert), "@pred"/"@fin" (Mapping-Tags).
DEP_RE = re.compile(r"#(\d+)(?:->|→)(\d+)$")
REL_RE = re.compile(r"R:([A-Za-z_]+):(\d+)$")
RELID_RE = re.compile(r"ID:(\d+)$")
# --trace-Tags: TYPE[(param)]:ZEILE[:NAME] — z. B. "SELECT:573",
# "ADDRELATION(nsubj):108", "SELECT:305:ka-complementizer".
TRACE_RE = re.compile(r"([A-Z]+)(\([^)]*\))?:(\d+)(?::(\S+))?$")
HIDDEN_TAGS = ("REMOVE:", "SELECT:", "ADD:", "MAP:", "SETPARENT:",
               "ADDRELATION:", "ADDRELATION(", "#", "ID:", "R:", "@")


def parse_cg_stream(stream: str) -> list[list[dict]]:
    """CG3-Stream → Liste von Cohorts:
    {form, readings:[{lemma,tags}], dep:(self,parent)|None, rid, rels,
     rules, errtags}.  rules: Namen benannter Grammatikregeln
    (KEYWORD:name), die den Cohort laut --trace berührt haben — auch
    auf entfernten (";"-)Lesarten, in Feuer-Reihenfolge, dedupliziert.
    errtags: &-Fehler-Tags des Validator-Passes (validator.cg3),
    dedupliziert und aus den Lesarten-Tags herausgefiltert (der
    CoNLL-U-Export bleibt davon unberührt)."""
    cohorts = []
    cur = None
    for line in stream.splitlines():
        if line.startswith('"<'):
            cur = {"form": line[2:line.rfind('>"')], "readings": [],
                   "dep": None, "rid": None, "rels": [], "rules": [],
                   "errtags": []}
            cohorts.append(cur)
        elif line.startswith(("\t", ";\t")) and cur is not None:
            removed = line.startswith(";")
            m = re.match(r';?\t"(.*)" (.*)$', line)
            if m:
                raw = m.group(2).split()
                for t in raw:
                    if md := DEP_RE.match(t):
                        if not removed:
                            cur["dep"] = (int(md.group(1)), int(md.group(2)))
                    elif mi := RELID_RE.match(t):
                        if not removed:
                            cur["rid"] = int(mi.group(1))
                    elif mr := REL_RE.match(t):
                        rel = (mr.group(1), int(mr.group(2)))
                        if not removed and rel not in cur["rels"]:
                            cur["rels"].append(rel)
                    elif t.startswith("&"):
                        if not removed and t not in cur["errtags"]:
                            cur["errtags"].append(t)
                    elif (mt := TRACE_RE.match(t)) and mt.group(4):
                        if mt.group(4) not in cur["rules"]:
                            cur["rules"].append(mt.group(4))
                if not removed:
                    tags = [t for t in raw if not t.startswith(HIDDEN_TAGS)
                            and not t.startswith("&")]
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


# ── Validierung (validator.cg3, Phase 3) ──

# Fehlertyp (&-Tag ohne Präfix) → menschenlesbare Meldung.
# §-Verweise: prussian-grammar/syntax_rules.txt
MESSAGES = {
    "prep-akk-dat": "Akkusativ-Präposition mit dativischem Komplement (§6b).",
    "pp-nom": "Nominativ innerhalb einer Präpositionalphrase.",
    "agr-adj-case": "Adjektiv kongruiert im Kasus nicht mit seinem Kopf.",
    "agr-adj-num": "Adjektiv kongruiert im Numerus nicht mit seinem Kopf.",
    "agr-adj-gend": "Adjektiv kongruiert im Genus nicht mit seinem Kopf.",
    "pred-nom-akk": "Prädikatsnomen unter Kopula steht im Akkusativ "
                    "statt Nominativ (§2).",
    "genverb-akk": "Genitiv-Verb mit akkusativischem Objekt (§6a).",
    "agr-subj-verb-pers": "Person des finiten Verbs widerspricht dem "
                          "Pronomen-Subjekt.",
    "agr-subj-verb-num": "Numerus des finiten Verbs widerspricht dem "
                         "Pronomen-Subjekt.",
    "subj-dup": "Zwei Nominativ-Subjekte in derselben Klausel — "
                "eines wäre als Objekt Akkusativ.",
    "steisan-nongen": "stēisan-Periphrase ohne folgendes Genitiv-Nominal (§4).",
    "pred-adj-gend": "Prädikativ-Adjektiv nach Kopula ist nicht Neutrum (§9).",
    "akkverb-nom": "Akkusativ-Verb mit nominativischem Objekt.",
}

# Bulk-Regression: Kongruenz- und PP-Nominativ-Flags entstehen auf
# attestiertem Text überwiegend durch Paradigmen-Lücken bei Lehn-
# wörtern (kultūri, interessants, zūpi …) — für Filter-Consumer als
# warning abgestuft; die Rektions-/Valenzregeln sind error.
# subj-dup startet als warning (Apposition/Asyndese-Restrisiko);
# auf error promoten, wenn die Bulk-Regression sauber bleibt.
WARN_RULES = {"agr-adj-case", "agr-adj-num", "agr-adj-gend", "pp-nom",
              "subj-dup"}

# Ab diesem Anteil mehrdeutiger Wort-Token gilt die Analyse als zu
# unsicher für ein „verified"-Urteil (Restambiguität → out_of_coverage).
AMBIG_MAX = 0.34

COPULA_LEMMAS = {"būtwei", "pastātwei"}


def load_genverbs(path: Path = REPO / "cg3/generated-sets.cg3") -> set[str]:
    """GenVerb-Lemmata aus dem autogenerierten CG3-Set (valence.json)."""
    m = re.search(r'LIST GenVerb\s*=\s*([^;]+);', path.read_text(encoding="utf-8"))
    return set(re.findall(r'"([^"]+)"', m.group(1))) if m else set()


def relevant_checks(cohorts: list[dict], genverbs: set[str]) -> list[str]:
    """Grobe Coverage-Heuristik: welche Prüf-Familien hatten in diesem
    Satz überhaupt eine Ankerstruktur?  Bewusst konservativ — nur wenn
    mindestens eine Familie anschlägt, kann ein Satz ohne Fehler-Tags
    als verified_in_coverage gelten."""
    checks = set()
    n = len(cohorts)
    # Finites Verb im Satz — Anker-Voraussetzung für subj-verb.
    has_finite = any(
        r["tags"] and r["tags"][0] == "V"
        and "Inf" not in r["tags"] and "Part" not in r["tags"]
        for c in cohorts for r in c["readings"])
    for i, c in enumerate(cohorts):
        for r in c["readings"]:
            tags = r["tags"]
            pos = tags[0] if tags else ""
            if pos in ("Prp", "Psp"):
                checks.add("prep-case")
            if pos == "V" and r["lemma"] in COPULA_LEMMAS \
                    and "Inf" not in tags and "Part" not in tags:
                checks.add("pred-nom")
            if r["lemma"] in genverbs:
                checks.add("genverb")
            if r["lemma"] == "stas" and "Gen" in tags:
                checks.add("steisan")
            # Nicht über @SUBJ testen: die @-Tags werden beim Parsen
            # aus den Lesarten gefiltert (HIDDEN_TAGS) — Anker ist das
            # nominativische P1/P2-Pronomen plus finites Verb im Satz.
            if pos == "Pron" and "Nom" in tags \
                    and ("P1" in tags or "P2" in tags) and has_finite:
                checks.add("subj-verb")
            if pos == "Adj":
                # Agreement prüfbar, wenn das Adjektiv einen Nominal-
                # Parent hat (agr-head-Relation, fensterlokal).
                par = rel_idx(i, c.get("dep"), n)
                if par is not None and any(
                        pr["tags"] and pr["tags"][0] in ("N", "Pron")
                        for pr in cohorts[par]["readings"]):
                    checks.add("adj-agr")
    return sorted(checks)


def rel_idx(i: int, dep: tuple[int, int] | None, n: int) -> int | None:
    """Fensterlokale Dependenz (#self->par) → 0-basierter Satz-Index
    des Parents (None: unangebunden/außerhalb)."""
    if not dep:
        return None
    self_n, par = dep
    if par in (0, self_n):
        return None
    pos = i - (self_n - par)
    return pos if 0 <= pos < n else None


def sentence_status(violations: list[dict], coverage: dict) -> str:
    """Dreiwertiges Urteil.  Kernprinzip: „kein Fehler-Tag" ist NICHT
    „korrekt" — ohne anwendbare Prüfregeln, mit unbekannten Wörtern,
    Kollaps oder hoher Restambiguität lautet das Urteil out_of_coverage."""
    if violations:
        return "violations_found"
    reasons = coverage["reasons"]
    if coverage["oov"]:
        reasons.append("oov")
    if coverage["collapsed"]:
        reasons.append("collapsed")
    if not coverage["checks_relevant"]:
        reasons.append("no_applicable_checks")
    if coverage["unlicensed"]:
        reasons.append("unlicensed_case")
    n = coverage["word_tokens"]
    if n and len(coverage["ambig"]) / n > AMBIG_MAX:
        reasons.append("residual_ambiguity")
    return "out_of_coverage" if reasons else "verified_in_coverage"


def validate_sentences(sentences: list[dict],
                       cohorts: list[dict]) -> list[dict]:
    """Cohorts (Output des Validator-Passes) satzweise auswerten →
    ein Ergebnis-Dikt pro Satz (status/violations/coverage)."""
    genverbs = load_genverbs()
    results = []
    idx = 0
    for s in sentences:
        n_coh = len(s["tokens"]) + (0 if s["tokens"][-1] in SENT_PUNCT else 1)
        sent_cohorts = cohorts[idx:idx + n_coh]
        idx += n_coh

        violations = []
        oov, collapsed, ambig = [], [], []
        word_tokens = 0
        for i, c in enumerate(sent_cohorts, 1):
            rs = c["readings"]
            if not rs:
                # kollabiert (--unsafe): war ein Wort-Cohort
                word_tokens += 1
                collapsed.append({"index": i, "form": c["form"]})
                continue
            if not is_word(c):
                continue
            word_tokens += 1
            if any("Unk" in r["tags"] for r in rs):
                oov.append({"index": i, "form": c["form"]})
                continue
            if len(rs) > 1:
                ambig.append({"index": i, "form": c["form"],
                              "n_readings": len(rs)})
            for tag in c["errtags"]:
                rule = tag.lstrip("&")
                violations.append({
                    "rule": rule,
                    "tag": tag,
                    "index": i,
                    "form": c["form"],
                    "severity": "warning" if rule in WARN_RULES else "error",
                    "reading": " | ".join(
                        "+".join([r["lemma"]] + r["tags"]) for r in rs),
                    "message": MESSAGES.get(rule, ""),
                })

        # Unlizenzierter Kasus: ein eindeutig disambiguiertes Pronomen,
        # das die Baumschicht nicht anbinden konnte (self-parented),
        # während der Satz noch weitere Wort-Wurzeln hat — d. h. der
        # Baum ist fragmentiert und das Pronomen schwebt ohne kasus-
        # lizenzierenden Kontext (Verb, Adposition, Kongruenzkopf,
        # Prädikativ), wie „stan" im Repro „As asma stan autōmatikin
        # rekōnstruiwuns …".  Bewusst nur Pron: frei stehende N-Wurzeln
        # sind auf attestiertem Text überwiegend legitime Fragmente
        # (Titel, verblose Aufzählungen) — N einzubeziehen halbiert
        # die verified-Quote der Bulk-Regression.  Verblose Einzel-
        # Wurzel-Sätze („Labban dēinan!") bleiben unberührt.
        # Degradiert auf out_of_coverage, nie Violation.
        word_roots = [
            (i, c) for i, c in enumerate(sent_cohorts, 1)
            if is_word(c) and c["dep"] and c["dep"][1] in (0, c["dep"][0])
        ]
        unlicensed = []
        if len(word_roots) > 1:
            unlicensed = [
                {"index": i, "form": c["form"]}
                for i, c in word_roots
                if len(c["readings"]) == 1
                and c["readings"][0]["tags"][:1] == ["Pron"]
            ]

        coverage = {
            "word_tokens": word_tokens,
            "oov": oov,
            "collapsed": collapsed,
            "ambig": ambig,
            "unlicensed": unlicensed,
            "checks_relevant": relevant_checks(sent_cohorts, genverbs),
            "reasons": [],
        }
        status = sentence_status(violations, coverage)
        results.append({
            "sent_id": s.get("sent_id", "?"),
            "text": s["text"],
            "status": status,
            "violations": violations,
            "coverage": coverage,
        })
    return results


def print_validate_summary(results: list[dict]):
    """Aggregat für die Bulk-Regression (make validate-corpus):
    Status-Verteilung, Flags pro Regel, Out-of-Coverage-Gründe."""
    status_counts = Counter(r["status"] for r in results)
    rule_counts = Counter(v["rule"] for r in results for v in r["violations"])
    reason_counts = Counter(reason for r in results
                            for reason in r["coverage"]["reasons"])
    n = len(results) or 1
    print(f"Sätze: {len(results)}")
    for st in ("verified_in_coverage", "out_of_coverage", "violations_found"):
        print(f"  {st:<22} {status_counts.get(st, 0):>6}"
              f"  ({100 * status_counts.get(st, 0) / n:.1f}%)")
    if reason_counts:
        print("Out-of-Coverage-Gründe:")
        for reason, cnt in reason_counts.most_common():
            print(f"  {reason:<22} {cnt:>6}")
    if rule_counts:
        print("Flags pro Regel:")
        for rule, cnt in rule_counts.most_common():
            print(f"  {rule:<22} {cnt:>6}")
    else:
        print("Keine Flags.")
    # Fehlalarm-Sichtung: die geflaggten Sätze selbst
    flagged = [r for r in results if r["violations"]]
    for r in flagged[:50]:
        rules = ", ".join(v["rule"] + ":" + v["form"] for v in r["violations"])
        print(f"  ⚑ [{r['sent_id']}] {r['text']}  → {rules}")
    if len(flagged) > 50:
        print(f"  … und {len(flagged) - 50} weitere")


# ── Error Detection (Kurzreport über errtags/Kollaps) ──

def detect_errors(sentences: list[dict], before: list[dict],
                   after: list[dict]) -> list[dict]:
    """Vergleicht vor/nach-Cohorts und meldet:
    - Zero-Reading-Cohorts (alle Lesarten entfernt)
    - Cohorts mit &-Fehler-Tags (validator.cg3)

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
            for tag in c_aft["errtags"]:
                errors.append({
                    "satz": s["text"],
                    "token": tok,
                    "fehler": tag,
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
    ap.add_argument("--validator-grammar", type=Path,
                    default=DEFAULT_VALIDATOR_GRAMMAR)
    ap.add_argument("--text", help="Einzeltext statt Korpus ('-' = stdin)")
    ap.add_argument("--limit", type=int, help="nur die ersten N Sätze")
    ap.add_argument("--no-disamb", action="store_true",
                    help="rohen CG-Input ausgeben (ohne cg-proc)")
    ap.add_argument("--deps", action="store_true",
                    help="Label-Phase (dependency.cg3) auf den Stream anwenden")
    ap.add_argument("--conllu", action="store_true",
                    help="CoNLL-U ausgeben (impliziert --deps)")
    ap.add_argument("--trace", action="store_true",
                    help="cg-proc -t; mit --conllu: Regel-Provenienz "
                         "(Rule=/AgrParent=) in MISC")
    ap.add_argument("--stats", action="store_true",
                    help="nur Kennzahlen (vorher/nachher) auf stdout")
    ap.add_argument("--validate", action="store_true",
                    help="Validator-Pass (validator.cg3) nach der Dependenz-"
                         "Phase; JSON pro Satz auf stdout (status/violations/"
                         "coverage).  status=verified_in_coverage NUR bei "
                         "sauberer, abgedeckter Analyse — out_of_coverage "
                         "heißt nicht „korrekt“.")
    ap.add_argument("--validate-summary", action="store_true",
                    help="mit --validate: Aggregat statt JSON (Status-"
                         "Verteilung, Flags pro Regel) — Bulk-Regression")
    ap.add_argument("--detect-errors", action="store_true",
                    help="Fehlererkennung: Kollaps/&-Fehler-Tags pro Satz")
    ap.add_argument("--top-ambig", type=int, nargs="?", const=20, metavar="N",
                    help="Top N Sätze mit den meisten ambigen Token anzeigen "
                         "(Default: 20)")
    args = ap.parse_args()

    if args.text is not None:
        text = sys.stdin.read() if args.text == "-" else args.text
        try:
            sentences = text_to_sentences(text)
        except ValueError as e:
            sys.exit(str(e))
    elif args.corpus_md:
        sentences = [s for d in args.corpus_md for s in load_markdown_sentences(d)]
        if args.limit:
            sentences = sentences[:args.limit]
    else:
        sentences = load_sentences(args.corpus)
        if args.limit:
            sentences = sentences[:args.limit]

    cg_input = build_cg_input(sentences, args.fst)

    if args.no_disamb:
        sys.stdout.write(cg_input)
        return

    output = run_cg_proc(cg_input, args.grammar, trace=args.trace)
    if args.deps or args.conllu or args.validate or args.detect_errors:
        output = run_cg_proc(output, args.dep_grammar, trace=args.trace)
    if args.validate or args.detect_errors:
        output = run_cg_proc(output, args.validator_grammar, trace=args.trace)

    if args.validate:
        results = validate_sentences(sentences, parse_cg_stream(output))
        if args.validate_summary:
            print_validate_summary(results)
        else:
            json.dump(results, sys.stdout, ensure_ascii=False, indent=2)
            sys.stdout.write("\n")
        return

    if args.conllu:
        try:
            from .export_conllu import conllu_output
        except ImportError:
            from export_conllu import conllu_output
        cohorts = parse_cg_stream(output)
        if args.trace:
            attach_agr_parents(cg_input, cohorts, args.grammar)
        sys.stdout.write(conllu_output(sentences, cohorts))
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
