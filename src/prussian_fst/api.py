"""Stabile In-Process-API über die FST/CG3-Pipeline.

Für Embedder wie prussian-mcp: kein Subprozess-Umweg über
cg3_pipeline.py — die pyhfst-Transducer bleiben im Prozess gecacht,
nur cg-proc läuft weiterhin als (billiger) Subprozess pro Pass.

Drei Einstiege:
  analyze(text)  → (sentences, cohorts) nach Disambiguierung + Dependenz
  validate(text) → dreiwertiges Validierungsergebnis pro Satz
                   (violations_found / verified_in_coverage / out_of_coverage)
  conllu(text)   → CoNLL-U mit Regel-Provenienz (fsg_check-Payload)

Voraussetzungen (nicht auto-gebaut — check_artifacts() liefert die
konkreten make-Kommandos): cg-proc im PATH, build/*.hfstol,
build/cg3/*.bin, cg3/generated-sets.cg3.
"""

import shutil
import threading
from pathlib import Path

from .cg3_pipeline import (DEFAULT_DEP_GRAMMAR, DEFAULT_DEP_GRAMMAR_BIN,
                           DEFAULT_FST, DEFAULT_FST_GEN, DEFAULT_GRAMMAR,
                           DEFAULT_GRAMMAR_BIN, DEFAULT_LENIENT,
                           DEFAULT_VALIDATOR_GRAMMAR,
                           DEFAULT_VALIDATOR_GRAMMAR_BIN, REPO, SENT_PUNCT,
                           attach_agr_parents, build_cg_input,
                           parse_cg_stream, run_cg_proc, text_to_sentences,
                           tokenize, validate_sentences)
from .export_conllu import conllu_output, sentence_block
from .fst_lookup import flookup_batch, glookup_batch

# pyhfst transducers are cached in a module dict (fst_lookup._transducers)
# and pyhfst lookup is not documented as thread-safe; FastMCP runs sync tools
# in a thread pool, so the entire pipeline is serialized.
_PIPELINE_LOCK = threading.Lock()


def _run_passes(text: str, *, trace: bool, validator: bool,
                timeout: float | None) -> tuple[list[dict], str, str]:
    """Gemeinsamer Kern: (sentences, cg_input, Stream nach den Pässen)."""
    sentences = text_to_sentences(text)
    cg_input = build_cg_input(sentences)
    out = run_cg_proc(cg_input, DEFAULT_GRAMMAR, trace=trace, timeout=timeout)
    out = run_cg_proc(out, DEFAULT_DEP_GRAMMAR, trace=trace, timeout=timeout)
    if validator:
        out = run_cg_proc(out, DEFAULT_VALIDATOR_GRAMMAR, trace=trace,
                          timeout=timeout)
    return sentences, cg_input, out


def analyze(text: str, *, trace: bool = False,
            timeout: float | None = 60.0) -> tuple[list[dict], list[dict]]:
    """Tokenisierung → FST-Lookup → Disambiguierung + Dependenz.

    Rückgabe: (sentences, cohorts) — Cohorts über alle Sätze, Slicing
    via cg3_pipeline-n_coh-Idiom bzw. export_conllu.conllu_output."""
    with _PIPELINE_LOCK:
        sentences, _, out = _run_passes(text, trace=trace, validator=False,
                                        timeout=timeout)
        return sentences, parse_cg_stream(out)


def validate(text: str, *, conllu: bool = False,
             timeout: float | None = 60.0) -> list[dict]:
    """Drei Pässe (Disambiguator → Dependenz → Validator) → ein Dikt pro
    Satz: {sent_id, text, status, violations, coverage}.

    status=verified_in_coverage ist die EINZIGE positive Evidenz;
    out_of_coverage heißt „nicht prüfbar", nicht „korrekt".

    Mit conllu=True bekommt jeder Satz zusätzlich seinen CoNLL-U-Block
    (Feld "conllu", inkl. Rule=/AgrParent=-Provenienz; None bei
    fremdsprachlichem Zitat) — aus demselben Pipeline-Lauf, die Pässe
    laufen dann mit Trace."""
    with _PIPELINE_LOCK:
        sentences, cg_input, out = _run_passes(text, trace=conllu,
                                               validator=True,
                                               timeout=timeout)
        cohorts = parse_cg_stream(out)
        results = validate_sentences(sentences, cohorts)
        if conllu:
            attach_agr_parents(cg_input, cohorts, timeout=timeout)
            idx = 0
            for s, r in zip(sentences, results):
                n_coh = len(s["tokens"]) + (
                    0 if s["tokens"][-1] in SENT_PUNCT else 1)
                r["conllu"] = sentence_block(s, cohorts[idx:idx + n_coh])
                idx += n_coh
        return results


def conllu(text: str, *, trace: bool = True,
           timeout: float | None = 60.0) -> str:
    """CoNLL-U-Blöcke (fsg_check-Payload); mit trace inkl. Rule=/
    AgrParent=-Provenienz in MISC (Zweitlauf bis SECTION dep-tree)."""
    with _PIPELINE_LOCK:
        sentences, cg_input, out = _run_passes(text, trace=trace,
                                               validator=False,
                                               timeout=timeout)
        cohorts = parse_cg_stream(out)
        if trace:
            attach_agr_parents(cg_input, cohorts, timeout=timeout)
        return conllu_output(sentences, cohorts)


def tags(words: list[str], *,
         fst_path: Path | None = None,
         timeout: float | None = None) -> dict[str, dict]:
    """Nicht-disambiguierte FST-Analysen pro Wort (Exact-Lookup, keine
    Kaskade).  Rückgabe: {wort: {"analyses": [(lemma, tags)], …}}.

    Analysen sind die rohen pyhfst-Ergebnisse, unabhängig voneinander
    (keine Disambiguierung).  Der Aufrufer ist für die Kaskade
    (lowercase/titlecase/lenient) zuständig."""
    fst = fst_path or DEFAULT_FST
    with _PIPELINE_LOCK:
        raw = flookup_batch(words, fst)
    return {
        w: {"analyses": raw.get(w, [])}
        for w in words
    }


def generate(queries: list[str], *,
             fst_path: Path | None = None) -> dict[str, list[str]]:
    """Generation direction: analysis string → surface form(s).

    Thin batch wrapper over glookup_batch, counterpart to tags().  No
    paradigm enumeration here — caller builds *queries* (e.g. via
    prussian_fst.paradigms) in the tag order used during lexc build.
    Returns {query: [surface, ...]} — empty list means the tag
    combination does not exist in the lexicon, not an error.
    """
    fst = fst_path or DEFAULT_FST_GEN
    with _PIPELINE_LOCK:
        raw = glookup_batch(queries, fst)
    return {q: raw.get(q, []) for q in queries}


def check_artifacts() -> list[str]:
    """Missing prerequisites (empty = ready), each with a fix command."""
    problems = []
    if not shutil.which("cg-proc"):
        problems.append("cg-proc nicht im PATH — cg3/Apertium installieren")
    for f, fix in [
        (DEFAULT_FST, f"make all"),
        (DEFAULT_LENIENT, f"make all"),
        (DEFAULT_FST_GEN, f"make all"),
        (REPO / "cg3/generated-sets.cg3", f"make cg3-sets"),
        (DEFAULT_GRAMMAR_BIN, f"make cg3-check"),
        (DEFAULT_DEP_GRAMMAR_BIN, f"make cg3-check"),
        (DEFAULT_VALIDATOR_GRAMMAR_BIN, f"make cg3-check"),
    ]:
        if not f.exists():
            problems.append(f"{f} fehlt — {fix}")
    return problems
