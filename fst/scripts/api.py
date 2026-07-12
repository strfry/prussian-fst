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
                           DEFAULT_FST, DEFAULT_GRAMMAR, DEFAULT_GRAMMAR_BIN,
                           DEFAULT_LENIENT, DEFAULT_VALIDATOR_GRAMMAR,
                           DEFAULT_VALIDATOR_GRAMMAR_BIN, FST_DIR, SENT_PUNCT,
                           attach_agr_parents, build_cg_input,
                           parse_cg_stream, run_cg_proc, text_to_sentences,
                           validate_sentences)
from .export_conllu import conllu_output, sentence_block

# Die pyhfst-Transducer werden in einem Modul-Dict gecacht
# (fst_lookup._transducers) und pyhfst-Lookup ist nicht dokumentiert
# threadsicher; FastMCP führt synchrone Tools in einem Threadpool aus —
# daher wird die gesamte Pipeline serialisiert.
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


def check_artifacts() -> list[str]:
    """Fehlende Voraussetzungen (leer = bereit), je mit Fix-Kommando."""
    problems = []
    if not shutil.which("cg-proc"):
        problems.append("cg-proc nicht im PATH — cg3/Apertium installieren")
    for f, fix in [
        (DEFAULT_FST, f"make -C {FST_DIR} all"),
        (DEFAULT_LENIENT, f"make -C {FST_DIR} all"),
        (FST_DIR / "cg3/generated-sets.cg3", f"make -C {FST_DIR} cg3-sets"),
        (DEFAULT_GRAMMAR_BIN, f"make -C {FST_DIR} cg3-check"),
        (DEFAULT_DEP_GRAMMAR_BIN, f"make -C {FST_DIR} cg3-check"),
        (DEFAULT_VALIDATOR_GRAMMAR_BIN, f"make -C {FST_DIR} cg3-check"),
    ]:
        if not f.exists():
            problems.append(f"{f} fehlt — {fix}")
    return problems
