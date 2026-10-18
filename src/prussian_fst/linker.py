"""Verweis-Resolver für Twanksta-Formeinträge.

Flektierte Formen stehen in der lean NVH (twanksta_dmlex.nvh, legacy.desc
als Klartext, siehe prussian_fst.nvh) als eigene Einträge ohne Übersetzung;
ihre desc beginnt mit einem Pfeil-Verweis auf die Grundform:

  wīrans    ↑ Wīrs acc sg m [Wīrans 93(12)]
  grēki si  ↑ Grēkitwei ps 3 r [grīkisi 55]
  klāntamai ↑ Klantītun, ↑ Klantītwei ps 1 sg m [klantemmai 29]

Der Linker löst das Ziel jedes Pfeils auf NVH-Einträge auf:

  1. headword — längstes Token-Präfix nach dem Pfeil, das ein Stichwort ist
                (exakte Schreibung vor Groß-/Kleinschreibung-tolerant)
  2. macron   — dasselbe ohne Makrons (Madlitun → madlītun)
  3. exact/case/macron/lenient — Analyzer-Kaskade über das erste Token;
                Lemmata, die Stichwörter sind, gewinnen

Ein Link trägt die Einträge des Zielworts (``target_ids``).  Bei
Homographen bleiben die, deren NVH-Wortart zu den FST-Tags der Form passt
(bētas gen → bētan-1 „Abend“, nicht bētan-2 „gestern“); passt keiner oder
gibt es keine Tags, bleiben alle.  Die eckigen Klammern sind Belegschreibungen
aus den Quellen, keine Verweise — sie werden nicht ausgewertet.

Jeder Link trägt neben ``orig_lemma`` (Wort) die Eintrags-``orig_id`` der
NVH (``be-1``/``be-2``), damit Homographen getrennt bleiben, und die
FST-Tags der Form unter dem Ziel-Lemma (POS-Fallback beim Chunk-Bau).
"""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

try:
    from .fst_lookup import flookup_batch
    from .nvh import DEFAULT_LEAN_NVH, read_entries
except ImportError:  # Direktaufruf als Skript
    from fst_lookup import flookup_batch
    from nvh import DEFAULT_LEAN_NVH, read_entries

REPO = Path(__file__).resolve().parents[2]
DEFAULT_BASE = REPO / "build/base.hfstol"
DEFAULT_MACRON = REPO / "build/macron.hfstol"
DEFAULT_LENIENT = REPO / "build/lenient.hfstol"

# Ein Pfeil-Verweis reicht bis zum nächsten Pfeil, Komma oder Belegteil.
ARROW_RE = re.compile(r"↑\s*([^↑,\[]*)")
MAX_TARGET_TOKENS = 4

# Zeichen, die der FST kennt: Kleinbuchstaben a-z plus Makron-Vokale.
# Formen mit anderen Zeichen liefern im FST nur Präfix-Müll-Matches.
FST_ALPHABET = set("abcdefghijklmnopqrstuvwxyzāēīōū")
_ALLOWED_EXTRA = set(" -")


def _in_alphabet(form: str) -> bool:
    return all(ch.lower() in FST_ALPHABET or ch in _ALLOWED_EXTRA
               for ch in form)


def strip_macrons(s: str) -> str:
    return "".join(ch for ch in unicodedata.normalize("NFD", s)
                   if unicodedata.category(ch) != "Mn")


def parse_arrows(desc: str) -> list[str]:
    """Text nach jedem ``↑`` (Ziel plus Grammatik-Kürzel), ohne Belegteil."""
    return [m.group(1).strip() for m in ARROW_RE.finditer(desc)
            if m.group(1).strip()]


def _case_variants(form: str) -> list[str]:
    seen: list[str] = []
    for v in (form, form.lower(), form[:1].upper() + form[1:].lower()):
        if v not in seen:
            seen.append(v)
    return seen


def resolve_form(form: str, fsts: dict[str, Path]) -> dict:
    """Kaskade über die Analyzer-Stufen; erste Stufe mit Analysen gewinnt.

    Liefert ``{"status": "resolved", "lemmas": [...], "tags": [...],
    "method": stufe}`` oder ``{"status": "gap"}``.
    """
    if not _in_alphabet(form):
        return {"status": "gap"}
    stages = [
        ("exact", fsts["base"], [form]),
        ("case", fsts["base"], _case_variants(form)[1:]),
        ("macron", fsts["macron"], _case_variants(form)),
        ("lenient", fsts["lenient"], _case_variants(form)),
    ]
    for method, fst_path, variants in stages:
        if not variants or not fst_path.exists():
            continue
        analyses = flookup_batch(variants, fst_path)
        pairs = {(lemma, tuple(tags))
                 for hits in analyses.values() for lemma, tags in hits}
        lemmas = sorted({lemma for lemma, _ in pairs})
        if lemmas:
            tags = sorted({"+".join(t) for _, t in pairs})
            return {"status": "resolved", "lemmas": lemmas,
                    "tags": tags, "method": method}
    return {"status": "gap"}


class Headwords:
    """Stichwort-Index der NVH: Schreibung → Eintrags-IDs."""

    def __init__(self, entries: list[dict]):
        self.exact: dict[str, list[str]] = defaultdict(list)
        self.fold: dict[str, list[str]] = defaultdict(list)
        self.bare: dict[str, list[str]] = defaultdict(list)
        self.word: dict[str, str] = {}
        for e in entries:
            eid, w = e.get("id", e["word"]), e["word"]
            self.word[eid] = w
            self.exact[w].append(eid)
            self.fold[w.casefold()].append(eid)
            self.bare[strip_macrons(w).casefold()].append(eid)

    def match(self, form: str, *, macron: bool = False) -> list[str]:
        if macron:
            return self.bare.get(strip_macrons(form).casefold(), [])
        return self.exact.get(form) or self.fold.get(form.casefold(), [])


def resolve_target(text: str, heads: Headwords, fsts: dict[str, Path]) -> dict:
    """Ziel eines Pfeil-Verweises (``"Wīrs acc sg m"``) auf Einträge auflösen."""
    tokens = text.split()
    prefixes = [" ".join(tokens[:n])
                for n in range(min(MAX_TARGET_TOKENS, len(tokens)), 0, -1)]
    for method, macron in (("headword", False), ("macron", True)):
        for ref in prefixes:
            ids = heads.match(ref, macron=macron)
            if ids:
                return {"status": "resolved", "ref": ref, "target_ids": ids,
                        "method": method}
    if not tokens:
        return {"status": "gap", "ref": ""}
    ref = tokens[0]
    res = resolve_form(ref, fsts)
    if res["status"] == "resolved":
        ids = [i for lemma in res["lemmas"] for i in heads.match(lemma)]
        if ids:
            return {"status": "resolved", "ref": ref,
                    "target_ids": list(dict.fromkeys(ids)),
                    "method": res["method"]}
    return {"status": "gap", "ref": ref}


# Wortart-Tag des FST (erstes Tag) → passende NVH-pos-Werte.
FST_TO_NVH_POS = {"N": {"noun"}, "V": {"verb"}, "A": {"adj"}, "Adv": {"adv"},
                  "Num": {"num", "adj"}, "Pron": {"pron"}}


def _filter_homographs(link: dict, pos_by_id: dict[str, str]) -> None:
    """``target_ids`` auf die Homographen mit zur Form passender Wortart."""
    ids = link["target_ids"]
    wanted = set().union(*(FST_TO_NVH_POS.get(t.split("+")[0], set())
                           for t in link["tags"]))
    kept = [i for i in ids if pos_by_id.get(i) in wanted]
    if len(ids) > 1 and kept:
        link["target_ids"] = kept


def _form_tags(links: list[dict], fst: Path) -> None:
    """``tags`` jedes Links: Analysen der Form unter dem Ziel-Lemma."""
    words = sorted({l["orig_lemma"] for l in links})
    analyses = flookup_batch(words, fst) if words and fst.exists() else {}
    for link in links:
        targets = set(link["lemmas"])
        link["tags"] = sorted({"+".join(tags)
                               for lemma, tags in analyses.get(link["orig_lemma"], [])
                               if lemma in targets})


def resolve_corpus(entries: list[dict], fsts: dict[str, Path]) -> tuple[list, list]:
    heads = Headwords(entries)
    pos_by_id = {e.get("id", e["word"]): e.get("pos", "") for e in entries}
    links, unresolved = [], []
    for entry in entries:
        desc = entry.get("desc", "")
        for text in parse_arrows(desc):
            res = resolve_target(text, heads, fsts)
            record = {"orig_lemma": entry.get("word"),
                      "orig_id": entry.get("id", entry.get("word")),
                      "ref": res["ref"], "desc": desc}
            if res["status"] == "resolved":
                ids = res["target_ids"]
                links.append({**record, "target_ids": ids,
                              "lemmas": list(dict.fromkeys(heads.word[i] for i in ids)),
                              "method": res["method"]})
            else:
                unresolved.append({**record, "status": res["status"]})
    _form_tags(links, fsts["base"])
    for link in links:
        _filter_homographs(link, pos_by_id)
    return links, unresolved


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--nvh", type=Path, default=DEFAULT_LEAN_NVH,
                    help="lean NVH (Default: ../corpus/parsed/twanksta_dmlex.nvh)")
    ap.add_argument("--out-dir", type=Path, default=REPO / "build")
    ap.add_argument("--stats", action="store_true")
    args = ap.parse_args()

    entries = read_entries(args.nvh)
    fsts = {"base": DEFAULT_BASE, "macron": DEFAULT_MACRON,
            "lenient": DEFAULT_LENIENT}
    links, unresolved = resolve_corpus(entries, fsts)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "links.json").write_text(
        json.dumps(links, ensure_ascii=False, indent=1))
    (args.out_dir / "links_unresolved.json").write_text(
        json.dumps(unresolved, ensure_ascii=False, indent=1))

    if args.stats:
        methods = Counter(l["method"] for l in links)
        homographs = sum(1 for l in links if len(l["target_ids"]) > 1)
        total = len(links) + len(unresolved)
        print(f"Verweise gesamt: {total}")
        print(f"aufgelöst: {len(links)} "
              f"({', '.join(f'{m}={n}' for m, n in methods.most_common())})")
        print(f"  davon auf Homographen (mehrere Einträge): {homographs}")
        print(f"offen: {len(unresolved)}")


if __name__ == "__main__":
    main()
