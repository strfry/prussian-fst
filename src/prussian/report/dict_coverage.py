"""Wörterbuch-Coverage: flektierte Twanksta-Formen aus prussian_dictionary.json
gegen Haupt-FST (Fallback lenient.fst) matchen.

Drei Schichten:
  run_nominal  Deklinationsformen, Paradigmen P9–P70  (Kern aus match_forms.py)
  run_verbal   finite Indikativ-Formen + Infinitiv, Verbparadigmen P71+
  run_closed   46 Funktionswörter aus data/closed/function_words.json
"""

import json
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent.parent
DICT = ROOT / "data/external/prussian_dictionary.json"
GOLD = ROOT / "data/gold/goldstandard.json"
WORDLIST = ROOT / "data/external/wordlist.json"

CASE_MAP = {"Nominative": "Nom", "Genitive": "Gen",
            "Dative": "Dat", "Accusative": "Acc"}
NUM_MAP = {"singular": "sg", "plural": "pl"}
GENDER_MAP = {"masc": "m", "fem": "f", "neut": "n"}


def _par_int(p: str) -> int:
    m = re.match(r"(\d+)", p)
    return int(m.group(1)) if m else 999


def fst_nominal_paradigms() -> set[str]:
    """Paradigmen, die die nominale FST-Morphologie abdeckt (P9–P70)."""
    pars: set[str] = set()
    for e in json.loads(GOLD.read_text(encoding="utf-8")):
        pars.add(e["paradigm"])
    for w in json.loads(WORDLIST.read_text(encoding="utf-8")):
        if w["paradigm"] and _par_int(w["paradigm"]) <= 70:
            pars.add(w["paradigm"])
    return pars


def _analyze(main_fst, lenient_fst, form: str) -> tuple[list, bool]:
    """(Analysen, nur_über_lenient?) — Haupt-FST zuerst, dann lenient."""
    f = form.lower()
    direct = list(main_fst.analyze(f))
    if direct:
        return direct, False
    return list(lenient_fst.analyze(f)), True


def _load_dict() -> list[dict]:
    return json.loads(DICT.read_text(encoding="utf-8"))


def run_nominal(main_fst, lenient_fst, words: list[dict] | None = None) -> dict:
    """Deklinationsformen (P9–P70) ∘ FST."""
    words = words if words is not None else _load_dict()
    pars = fst_nominal_paradigms()

    total = direct_match = ortho_match = no_match = 0
    par_stats: dict[str, dict] = defaultdict(
        lambda: {"total": 0, "direct": 0, "ortho": 0, "no": 0})
    samples: list[dict] = []

    for w in words:
        par = w.get("paradigm", "")
        if par not in pars:
            continue
        forms = w.get("forms")
        if not isinstance(forms, dict) or "declension" not in forms:
            continue
        for decl in forms["declension"]:
            for case_info in decl.get("cases", []):
                if case_info.get("case", "") not in CASE_MAP:
                    continue
                for num_name in NUM_MAP:
                    form = case_info.get(num_name, "").strip()
                    if not form or form == "—":
                        continue
                    total += 1
                    par_stats[par]["total"] += 1
                    results, via_lenient = _analyze(main_fst, lenient_fst, form)
                    if not results:
                        no_match += 1
                        par_stats[par]["no"] += 1
                        if len(samples) < 30:
                            samples.append({"form": form, "lemma": w["word"],
                                            "paradigm": par})
                    elif via_lenient:
                        ortho_match += 1
                        par_stats[par]["ortho"] += 1
                    else:
                        direct_match += 1
                        par_stats[par]["direct"] += 1

    return {
        "total": total, "direct": direct_match, "ortho": ortho_match,
        "no": no_match, "par_stats": {k: v for k, v in par_stats.items()},
        "no_match_samples": samples,
    }


def run_verbal(main_fst, lenient_fst, words: list[dict] | None = None) -> dict:
    """Finite Indikativ-Formen + Infinitiv (P71+) ∘ FST; Treffer = +V-Analyse."""
    words = words if words is not None else _load_dict()

    total = direct_match = ortho_match = no_match = 0
    par_stats: dict[str, dict] = defaultdict(
        lambda: {"total": 0, "direct": 0, "ortho": 0, "no": 0})
    samples: list[dict] = []

    for w in words:
        par = w.get("paradigm", "")
        if not par or _par_int(par) < 71:
            continue
        forms = w.get("forms")
        if not isinstance(forms, dict) or "indicative" not in forms:
            continue

        word = w["word"]
        candidates: list[str] = []
        if (word.endswith("tun") or word.endswith("twei")) and " " not in word:
            candidates.append(word)          # Infinitiv = Lemma
        for block in forms["indicative"]:
            for slot in block.get("forms", []):
                f = slot.get("form", "").strip()
                if f and f != "—" and " " not in f:
                    candidates.append(f)

        for form in candidates:
            total += 1
            par_stats[par]["total"] += 1
            results, via_lenient = _analyze(main_fst, lenient_fst, form)
            verb_hit = any("+V" in r for r in results)
            if not verb_hit:
                no_match += 1
                par_stats[par]["no"] += 1
                if len(samples) < 30:
                    samples.append({"form": form, "lemma": word, "paradigm": par})
            elif via_lenient:
                ortho_match += 1
                par_stats[par]["ortho"] += 1
            else:
                direct_match += 1
                par_stats[par]["direct"] += 1

    return {
        "total": total, "direct": direct_match, "ortho": ortho_match,
        "no": no_match, "par_stats": {k: v for k, v in par_stats.items()},
        "no_match_samples": samples,
    }


_CLOSED_POS_TOTAL = {"prepositions": "+Pr", "conjunctions": "+Cjn",
                     "particles": "+Pcl", "interrogatives": "+Pron"}


def run_closed(main_fst, function_words: list[tuple[str, str]]) -> dict:
    """Funktionswort-Erkennung: analysiert jedes (Wort, POS-Tag)-Paar."""
    per_pos: dict[str, dict] = defaultdict(lambda: {"recognized": 0, "total": 0})
    recognized = 0
    unmatched: list[dict] = []
    for word, tag in function_words:
        per_pos[tag]["total"] += 1
        if list(main_fst.analyze(word.lower())):
            per_pos[tag]["recognized"] += 1
            recognized += 1
        else:
            unmatched.append({"word": word, "tag": tag})
    return {
        "total": len(function_words), "recognized": recognized,
        "per_pos": {k: dict(v) for k, v in per_pos.items()},
        "unmatched": unmatched,
    }
