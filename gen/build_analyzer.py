#!/usr/bin/env python3
"""Gebackener, lemma-fähiger Giella-Analyzer (Option B).

Quelle der Open-Class-Morphologie sind die handgeschriebenen ``gen/*.lexc``
Grammatiken (native Giella-+Tags). Die Lexem-Stämme kommen aus der **lean NVH**
(``../corpus/parsed/twanksta_dmlex.nvh``): Stufe 1 als ``stemOverrides: ROLE=STEM``,
Stufe 3 als ``inflectedForm`` + ``tag``. Der Kompressor hat sie bereits so
verdichtet, dass ``generate(lemma, stems) ⊕ overrides == Twanksta-Zellen`` gilt
(⊕ = ein Override ersetzt den Slot) — deshalb erreicht der gebackene Analyzer
dieselbe Oberflächen-Deckung wie die Twanksta-Zellen, ohne Vollform-Expansion und
ohne falsche Regelformen in gelisteten Slots.

Aufbau::

    lean NVH  --parse_nvh-->  Entry(lemma, pos, paradigm, gender, stems, attested)
              --generate(pos, paradigm, lemma, stems)-->  slot → Oberflächen (dotted)
              --slot_tag(slot)-->  Giella-+Tag           (Nomen: Genus eingefügt)
              --Overrides ersetzen ihren Slot-->         lemma+Tags:surface
    ∪ Closed-Class-lexc (re-getaggt)  --lexc-Compile, invert-->  build/analyzer.hfstol

``--parity`` vergleicht die Oberflächenmenge mit ``build/lexc.merged`` (den
Quellen von ``base.hfstol``) und benennt jede verlorene Form.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

import compress_forms as cf  # noqa: E402
import generator as gen  # noqa: E402

PARSED = ROOT.parent / "corpus" / "parsed"
LEAN_NVH = PARSED / "twanksta_dmlex.nvh"
LEXC_DIR = ROOT / "lexc"
BUILD = ROOT / "build"
OPEN_LEXC = BUILD / "analyzer-open.lexc"
MERGED_LEXC = BUILD / "analyzer.lexc"
ANALYZER_FST = BUILD / "analyzer.fst"
ANALYZER_OL = BUILD / "analyzer.hfstol"
BASE_MERGED = BUILD / "lexc.merged"

GENDER_TAG = {"masc": "Msc", "fem": "Fem", "neut": "Neu"}
OPEN_POS = {"noun": ("Nouns", "+N"), "adj": ("Adjectives", "+A"),
            "verb": ("Verbs", "+V"), "invar": ("Invariables", "")}
NUMTYPE_TAG = {"card": "+Card", "ord": "+Ord"}
# Invariable NVH-Wortart (kein Paradigma) → FST-Tag (WS3; Vokabular wie K3).
INVARIABLE_TAG = {"adv": "+Adv", "prep": "+Pr", "postp": "+Po", "intj": "+Interj",
                  "part": "+Pcle", "cconj": "+CC", "sconj": "+CS", "num": "+Num",
                  "pron": "+Pron"}

# Handgeschriebene Closed-Class-Quellen; alles andere wird aus der NVH gebacken.
CLOSED_CLASS = [
    "symbols.lexc", "root.lexc", "function_words.lexc", "pronouns.lexc",
]


def lexc_esc(text: str) -> str:
    return text.replace(" ", "% ").replace("!", "%!")


def split_si(lemma: str) -> tuple[str, bool]:
    """``"perwaidīntun si"`` → ``("perwaidīntun", True)``."""
    if lemma.endswith(" si"):
        return lemma[:-3], True
    return lemma, False


def is_proper(entry: cf.Entry) -> bool:
    """Eigenname = großgeschriebenes Lemma (WS2a). NICHT mehr Pit/Per: Pit markiert
    modernen Wortschatz (246/363 Pit-Nomen sind Appellative), Per existiert nicht.
    Großgeschriebene Nomen bekommen beim Backen +N+Prop."""
    return bool(entry.lemma) and entry.lemma[:1].isupper()


def paradigm_int(par: str) -> int | None:
    num = ""
    for ch in par:
        if ch.isdigit():
            num += ch
        else:
            break
    return int(num) if num else None


def classify_entry(entry: cf.Entry) -> str | None:
    """Flexionsfamilie des Eintrags: ``noun``/``adj``/``verb``/``invar`` oder ``None``.

    Die Wortart steht in der NVH (``pos``, ggf. per Hand-Tabelle); die Familie sagt
    nur, über welche Atome/welches Lexikon gebacken wird. Pronomina/Numeralia mit
    Formtabelle (P21–24: ``pos: pron|num``) flektieren adjektivisch. Einträge ohne
    Paradigma mit invariabler Wortart (``INVARIABLE_TAG``) oder als indeklinables
    Nomen werden ``invar``. Nomen-Range 1–20 (Pronomina) liegt in der Hand-lexc →
    ``None``.
    """
    if not entry.paradigm and (entry.pos in INVARIABLE_TAG or entry.pos == "noun"):
        return "invar"
    if entry.pos in ("adj", "verb"):
        return entry.pos
    if entry.pos in ("pron", "num"):
        return "adj"
    if entry.pos != "noun":
        return None
    pi = paradigm_int(entry.paradigm)
    if pi is None:
        return "noun"
    if 1 <= pi <= 20:      # Pronomina → pronouns.lexc
        return None
    if 25 <= pi <= 31:     # Adjektivparadigmen
        return "adj"
    return "noun"


def pos_head(entry: cf.Entry) -> str | None:
    """Tag-Kopf aus der NVH-Wortart, ``None`` = der der Familie (+N/+A).

    ``numtype`` (card|ord) macht jedes Lexem zum Numerale (Ordinalia-Adjektive,
    Kardinalia-Nomen); sonst ``pos: num`` → ``+Num``, ``pos: pron`` → ``+Pron``.
    """
    if entry.numtype:
        return "+Num" + NUMTYPE_TAG[entry.numtype]
    if entry.pos == "num":
        return "+Num"
    if entry.pos == "pron":
        return "+Pron"
    return None


FORM_RELATIONS = ("relation: attestedFormOf", "relation: variantOf")


def entry_id(entry: cf.Entry) -> str:
    for line in entry.head:
        if line.startswith("  id: "):
            return line[len("  id: "):].strip()
    return entry.lemma


def form_of(entry: cf.Entry) -> str | None:
    """ID des Ziel-Lexems eines Verweis-Eintrags (``attestedFormOf``/``variantOf``,
    ``member: X role: lemma``) — ``labban-4`` „↑ Labs n (av)“ → ``labs``."""
    in_relation = False
    for line in entry.head + entry.tail:
        if not line.startswith("    "):
            in_relation = line.strip() in FORM_RELATIONS
            continue
        text = line.strip()
        if in_relation and text.startswith("member: ") and text.endswith(" role: lemma"):
            return text[len("member: "):-len(" role: lemma")]
    return None


def invariable_tags(entry: cf.Entry) -> str:
    """Tag eines invariablen Eintrags: Wortart (+ numtype); indeklinables Nomen
    ``+N(+Prop)(+Genus)`` ohne Numerus/Kasus (``Mālis+N+Prop+Msc``)."""
    if entry.pos == "noun":
        g = GENDER_TAG.get(entry.gender, "")
        return "+N" + ("+Prop" if is_proper(entry) else "") + (f"+{g}" if g else "")
    return INVARIABLE_TAG[entry.pos] + NUMTYPE_TAG.get(entry.numtype, "")


def analysis_tags(pos: str, gender: str, slot: str, proper: bool = False,
                  head: str | None = None) -> str:
    """Dotted Slot-Key → Giella-+Tag.  Nomen: Genus (Entry-Fakt) einfügen; Eigennamen
    zusätzlich +Prop direkt nach +N (Giella, wie das alte proper_nouns_auto.lexc).
    ``head`` (``pos_head``) ersetzt den Familien-Marker +N/+A: ``sīmtan`` sg.gen →
    ``+Num+Card+Neu+Sg+Gen``, ``eraīns`` msc.sg.gen → ``+Pron+Msc+Sg+Gen``."""
    tag = gen.slot_tag(slot)
    if pos == "noun":
        g = GENDER_TAG.get(gender, "")
        prop = "+Prop" if proper else ""
        tag = "+N" + prop + (f"+{g}" if g else "") + tag[len("+N"):]
    if head:
        for marker in ("+N+", "+A+"):
            if tag.startswith(marker):
                return head + tag[len(marker) - 1:]
        raise ValueError(f"Slot {slot!r} hat keinen +N/+A-Kopf für {head}")
    return tag


def entry_forms(entry: cf.Entry) -> dict[str, frozenset[str]]:
    """slot → Oberflächen: Stufe 0/1 (generate) ⊕ Overrides — ein Override **ersetzt**
    den Slot (``cf._merged``), damit er eine falsche Regelform unterdrückt."""
    generated: dict[str, tuple[str, ...]] = {}
    try:
        generated = cf.regenerate(entry.pos, entry.paradigm, entry.lemma,
                                  entry.stems)
    except (KeyError, ValueError) as exc:
        print(f"  ! generate {entry.pos}/{entry.paradigm} {entry.lemma!r}: {exc}",
              file=sys.stderr)
    return cf._merged(generated, entry.attested)


def bake_open(entries: list[cf.Entry]) -> tuple[str, dict]:
    """Open-Class-Lexikone aus lean NVH + gen-Grammatiken erzeugen."""
    by_lexicon: dict[str, list[str]] = {name: [] for name, _ in OPEN_POS.values()}
    stats = defaultdict(int)
    skipped_unknown_slot = 0
    # Adverbien mit eigenem NVH-Eintrag (eigene Senses, z. B. prūsiskai „auf Prußisch“)
    # sind eigenes Lemma; die gleichlautende Positiv-Form der Adjektivtabelle
    # (prūsisks+Adv) wird dann nicht zusätzlich gebacken. Grade bleiben am Adjektiv.
    own_adverbs = {e.lemma for e in entries if e.pos == "adv" and not e.paradigm}
    # Verweis-Einträge (``attestedFormOf``/``variantOf``) sind Formen eines anderen
    # Lexems: erzeugt das Ziel dieselbe Oberfläche schon, gehört die Lesart ihm
    # (labban-4 „↑ Labs n (av)“ = labs+A+Neu…, kein eigenes labban+Adv). Neue
    # Oberflächen (stu ← stas, pa ← pas) bleiben. Deshalb Invariable zuletzt.
    surfaces_of_id: dict[str, set[str]] = defaultdict(set)
    invariable_seen: set[str] = set()
    ordered = sorted(entries, key=lambda e: classify_entry(e) == "invar")
    for entry in ordered:
        pos = classify_entry(entry)
        if pos is None:
            stats["closedclass"] += 1
            continue
        base_lemma, refl = split_si(entry.lemma)
        if pos == "invar" and entry.pos == "intj":
            base_lemma = base_lemma.rstrip("!")    # Wörterbuch-Lemma „ērdiw!“ → ērdiw
        if " " in base_lemma:
            stats["multiword"] += 1
            continue
        # WS2a: großgeschriebene Nomen → +N+Prop, direkt aus den Noun-Atomen gebacken
        # (statt der früheren Frozen-Liste proper_nouns_auto.lexc).
        proper = pos == "noun" and is_proper(entry)
        if proper:
            stats["proper"] += 1
        lexicon, _ = OPEN_POS[pos]
        lemma = lexc_esc(base_lemma)
        if pos == "invar":
            target = form_of(entry)
            if target and base_lemma in surfaces_of_id.get(target, ()):
                stats["form_of_known"] += 1
                continue
            # Invariable (WS3): Lemma selbst, nur Wortart (+ numtype/Genus).
            body = f"{lemma}{invariable_tags(entry)}:{lemma}"
            if body not in invariable_seen:          # Homographen (pa-1, pa-2 …)
                invariable_seen.add(body)
                by_lexicon[lexicon].append(body)
            stats[f"invar.{entry.pos}"] += 1
            continue
        head = pos_head(entry)
        cells = entry_forms(entry)
        if head:
            # Numeralia/Pronomina steigern nicht: nur Positiv- bzw. Nomen-Slots.
            keep = set(gen.NOUN_SLOTS if pos == "noun" else gen.ADJ_POS_SLOTS)
            cells = {slot: forms for slot, forms in cells.items() if slot in keep}
            stats["num" if head.startswith("+Num") else "pron"] += 1
        seen: set[str] = set()
        # Infinitiv ist kein generator-Slot: Lemma selbst, optional +Refl.
        if pos == "verb" and cells:
            inf = f"{lemma}+V+Inf{'+Refl' if refl else ''}:{lemma}"
            seen.add(inf)
            by_lexicon[lexicon].append(inf)
        if not cells:
            stats["leer"] += 1
            continue
        junk = entry.lemma + entry.paradigm  # Parse-Artefakt der vollen NVH
        for slot, surfaces in cells.items():
            try:
                tags = analysis_tags(pos, entry.gender, slot, proper, head)
            except ValueError:
                skipped_unknown_slot += 1
                continue
            for surface in surfaces:
                if " " in surface or surface == junk:
                    continue
                if pos == "adj" and slot == "adv" and surface in own_adverbs:
                    stats["adv_own_entry"] += 1
                    continue
                surfaces_of_id[entry_id(entry)].add(surface)
                body = f"{lemma}{tags}:{lexc_esc(surface)}"
                if body not in seen:
                    seen.add(body)
                    by_lexicon[lexicon].append(body)
        stats[pos] += 1
    out = ["! analyzer — baked from twanksta_dmlex.nvh + gen/*.lexc", ""]
    for lexicon, _ in OPEN_POS.values():
        out.append(f"LEXICON {lexicon}")
        out.extend(f"  {body}  # ;" for body in by_lexicon[lexicon])
        out.append("")
    stats["unknown_slot"] = skipped_unknown_slot
    return "\n".join(out) + "\n", stats


def build_merged(open_text: str) -> None:
    parts = []
    for name in CLOSED_CLASS:
        parts.append((LEXC_DIR / name).read_text(encoding="utf-8"))
    parts.append(open_text)
    MERGED_LEXC.write_text("".join(parts), encoding="utf-8")


def compile_analyzer() -> None:
    import hfst

    tr = hfst.compile_lexc_file(str(MERGED_LEXC))
    if tr is None or tr.number_of_states() == 0:
        raise SystemExit(f"lexc-Compile leer: {MERGED_LEXC}")
    tr.invert()
    tr.convert(hfst.ImplementationType.HFST_OL_TYPE)
    out = hfst.HfstOutputStream(filename=str(ANALYZER_OL),
                                type=hfst.ImplementationType.HFST_OL_TYPE)
    out.write(tr)
    out.flush()
    out.close()


_SURFACE = re.compile(r":\s*([^ \t#]+)")


def surfaces_of(path: Path) -> set[str]:
    """Alle Oberflächen (Lower sides) einer lexc-Datei."""
    out: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.rstrip()
        if not line or line.lstrip().startswith("!") or line.startswith("LEXICON"):
            continue
        m = _SURFACE.search(line)
        if m:
            out.add(m.group(1))
    return out


GAPS_REVIEW = BUILD / "review_analyzer_gaps.tsv"
# Eingefrorenes, non-circular Gold (WS0): die twanksta-Oberflächen des alten
# gen_lexc-Vollform-Builds, einmal nach tests/gold/ eingefroren, bevor base.fst auf
# die Atom-Bäckerei umgestellt wurde. Eine Oberfläche je Zeile (kein lexc).
GOLD = ROOT / "tests" / "gold" / "twanksta_surfaces.txt"


def gold_surfaces() -> set[str]:
    """Die eingefrorenen Gold-Oberflächen; Fallback auf live build/lexc.merged,
    solange die Gold-Datei fehlt (= gen_lexc-Open-Class noch vorhanden)."""
    if GOLD.exists():
        return {ln for ln in GOLD.read_text(encoding="utf-8").splitlines() if ln}
    return surfaces_of(BASE_MERGED)


def parity() -> int:
    ref = gold_surfaces()
    got = surfaces_of(MERGED_LEXC)
    missing = ref - got
    extra = got - ref
    print(f"Deckung: {len(ref) - len(missing)}/{len(ref)} "
          f"({100 * (len(ref) - len(missing)) / max(len(ref), 1):.2f}%) "
          f"base-Oberflächen; fehlend {len(missing)}, extra {len(extra)}")
    for surface in sorted(missing)[:40]:
        print(f"  FEHLT  {surface}")
    for surface in sorted(extra)[:10]:
        print(f"  EXTRA  {surface}")
    # Review: verbleibende Deckungslücken + Analyzer-Extra-Lesarten zum Abgleich.
    lines = ["# Analysator-Parität vs. eingefrorenem twanksta-Gold (tests/gold/twanksta_surfaces.txt)\n",
             "# FEHLT = im Gold, nicht im gebackenen Analyzer (Review: Lemma/Daten prüfen)\n",
             "# EXTRA = im gebackenen Analyzer, nicht im Gold (Varianten-Lesarten verifizieren)\n",
             "kategorie\tsurface\n"]
    lines += [f"FEHLT\t{s}\n" for s in sorted(missing)]
    lines += [f"EXTRA\t{s}\n" for s in sorted(extra)]
    GAPS_REVIEW.write_text("".join(lines), encoding="utf-8")
    print(f"→ {GAPS_REVIEW} ({len(missing)} FEHLT, {len(extra)} EXTRA)")
    return 1 if missing else 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--parity", action="store_true",
                    help="nur Deckung vs. build/lexc.merged messen")
    ap.add_argument("--no-compile", action="store_true")
    ap.add_argument("--nvh", type=Path, default=LEAN_NVH,
                    help="lean NVH (default: %(default)s)")
    args = ap.parse_args(argv)

    entries = cf.read_nvh(args.nvh)
    open_text, stats = bake_open(entries)
    OPEN_LEXC.write_text(open_text, encoding="utf-8")
    build_merged(open_text)
    print(f"lean NVH: {len(entries)} Einträge; open-class gebacken: "
          f"noun={stats['noun']} adj={stats['adj']} verb={stats['verb']} "
          f"(davon +Prop {stats['proper']}, +Num {stats['num']}, +Pron {stats['pron']}, "
          f"closed-class {stats['closedclass']}, multiword {stats['multiword']}, "
          f"leer {stats['leer']}, unbek. Slot {stats['unknown_slot']}, "
          f"Adv mit eigenem Eintrag {stats['adv_own_entry']}, "
          f"Verweis auf bekannte Form {stats['form_of_known']}); invariabel: "
          + " ".join(f"{k[6:]}={v}" for k, v in sorted(stats.items())
                     if k.startswith("invar.")))
    if not args.no_compile and not args.parity:
        compile_analyzer()
        print(f"→ {ANALYZER_OL}")
    if args.parity:
        return parity()
    return 0


if __name__ == "__main__":
    sys.exit(main())
