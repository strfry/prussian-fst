"""Markierte Morphotaktik als lexc-Lexikon (HFST-Zweig).

Erzeugt aus denselben Eintragsdaten wie der pyfoma-Build (gold + Wortliste)
ein **lexc**-Lexikon mit markierter Unterseite (Archiphoneme A E I O U,
Marker M/S/J). Die Auflösung zur Oberfläche übernehmen die Regeln in
``rules.PHONOLOGY``. Anders als ``morphology.lexd`` werden **keine**
V-Varianten-Zeilen emittiert — die Quellschreibungen entstehen im lenient-
Build als generalisierende spellrelax-Regeln (``rules.SPELLRELAX``).

Struktur (Giella-nah):
    Multichar_Symbols  +N +Msc … +Sg +Nom …
    LEXICON Root           → je Stamm-Lexikon eine Continuation
    LEXICON StemsN_P40_m   → ``kūgis+N+Msc:kūg  InflN_P40_m ;``
    LEXICON InflN_P40_m    → ``+Sg+Nom:is  # ;`` …
    LEXICON Variants       → literale Parallel-/Doublettenformen (Standard)
"""

import re
from collections import defaultdict
from itertools import chain

from prussian.fst.morphology import nominals, verbs
from prussian.fst.morphology.lexd import (
    _MERGED_SUBS, _cell_tag, _lexname, entry_class, render_stem,
)
from prussian.fst.oracle import resolve_stem
from prussian.fst.spellrelax import jan_variant
from prussian.fst.tags import split_suffix

#: Grenzmarker Stamm|Endung — nur auf j-relaxbaren, nicht-palatalen Endungen.
#: Die generalisierenden Grenzregeln (rules.HARD_J/SOFT_J) hängen daran; der
#: Marker selbst wird von rules.CLEANUP getilgt. ``jan_variant`` liefert nur das
#: Prädikat »diese Endung bildet eine j-Variante« (Endungsklasse), nicht die
#: aufgezählte Form — die berechnet die Regel.
_BD = "·"

#: lexc-Sonderzeichen, die in Wort-/Tagliteralen mit ``%`` zu escapen sind.
_LEXC_SPECIAL = set(" !\"#$%&'()*+,-/:;<=>?@[\\]^`{|}~")
_TAG_RE = re.compile(r"\+[A-Za-z0-9]+")


def _render_suffix_std(v: dict, cls: str) -> str:
    """Unterseiten-Endung ``(J)(S)(·)suffix``.

    ``J`` palatalisiert den Stammauslaut (Standard), ``S`` markiert die starke
    Endung (Akzent). ``·`` ist der Grenzmarker für die generalisierenden
    j-Einschubregeln — gesetzt genau dann, wenn die Endung eine (nicht-
    palatale) Twanksta-j-Variante bildet. Keine V-Aufzählung.
    """
    std, _variant = split_suffix(v["suffix"])
    palatize = v.get("palatize", False)
    s_marker = "S" if cls == "mob" and not v["betont"] else ""
    j_marker = "J" if palatize else ""
    bd = _BD if (not palatize and jan_variant(std) is not None) else ""
    return f"{j_marker}{s_marker}{bd}{std}"


def collect(
    entries: list[dict],
    verb_entries: list[dict],
    verb_wl_entries: list[dict] | None = None,
    closed_entries: list[dict] | None = None,
) -> tuple[dict, dict, set]:
    """(Stämme, Endungen, Parallelformen) wie ``morphology.lexd``, V-frei.

    ``stems[key]``  : Liste von (upper, lower_stem)-Paaren (Stamm 1×/Gruppe).
    ``infls[key]``  : ``{cell_tag: lower_suffix}`` (Endungen 1×/Gruppe).
    ``variants``    : Menge von (upper_full, surface)-Paaren — literale
                      Doubletten-Vollformen (echte Standard-Parallelformen,
                      **keine** Quellvarianten; vgl. README »Doubletten«).
    """
    stems: dict[tuple, list[tuple[str, str]]] = defaultdict(list)
    infls: dict[tuple, dict[str, str]] = {}
    variants: set[tuple[str, str]] = set()

    def add_group(key, upper_prefix, lexkind, e):
        cls = entry_class(e["suffixe"])
        merged = key[-1] in _MERGED_SUBS
        infl = infls.setdefault(key, {})
        if merged or not infl:
            for cell, v in e["suffixe"].items():
                tag, v = _cell_tag(lexkind, e, cell, v)
                infl.setdefault(tag, _render_suffix_std(v, cls))
        stem = render_stem(e["stamm"], cls)
        pair = (f"{e['lemma']}{upper_prefix}", stem)
        if pair not in stems[key]:
            stems[key].append(pair)
        # Doubletten: literale Vollformen, sofern sie zum Stamm passen.
        for cell, v in e["suffixe"].items():
            _std, variant_full = split_suffix(v["suffix"])
            if variant_full is None:
                continue
            pal = v.get("palatize", False)
            if (variant_full.startswith(resolve_stem(e["stamm"], True, pal))
                    or variant_full.startswith(resolve_stem(e["stamm"], False, pal))):
                tag, _v = _cell_tag(lexkind, e, cell, v)
                variants.add((f"{e['lemma']}{upper_prefix}{tag}", variant_full))

    sources = [nominals.groups(entries), verbs.groups(verb_entries)]
    if verb_wl_entries:
        sources.append(verbs.wl_groups(verb_wl_entries))
    if closed_entries:
        sources.append(nominals.groups(closed_entries))

    for key, upper_prefix, lexkind, e in chain(*sources):
        add_group(key, upper_prefix, lexkind, e)

    return stems, infls, variants


def _esc(token: str) -> str:
    """lexc-Literal escapen (Tags via Multichar_Symbols geschützt, Rest Zeichen)."""
    out = []
    i = 0
    while i < len(token):
        m = _TAG_RE.match(token, i)
        if m:                       # +N, +Sg … bleiben als Multichar-Symbol
            out.append(m.group())
            i = m.end()
            continue
        ch = token[i]
        if ch in _LEXC_SPECIAL:
            out.append("%" + ch)
        else:
            out.append(ch)
        i += 1
    return "".join(out)


def _entry(upper: str, lower: str, cont: str) -> str:
    """Eine lexc-Zeile ``upper:lower  cont ;`` (leere Unterseite → 0)."""
    lo = _esc(lower) if lower else "0"
    return f"{_esc(upper)}:{lo} {cont} ;"


def build_lexc(
    entries: list[dict],
    verb_entries: list[dict],
    verb_wl_entries: list[dict] | None = None,
    closed_entries: list[dict] | None = None,
    function_words: list[tuple[str, str]] | None = None,
    adverbs: list[tuple[str, str]] | None = None,
) -> str:
    """Eintragsdaten → lexc-Quelltext (markierte Unterseite, V-frei)."""
    stems, infls, variants = collect(
        entries, verb_entries, verb_wl_entries, closed_entries
    )

    # ── Multichar-Inventar: alle +Tags aus allen Oberseiten ──
    multichar: set[str] = set()
    for key, pairs in stems.items():
        for upper, _lo in pairs:
            multichar.update(_TAG_RE.findall(upper))
    for key, infl in infls.items():
        for tag in infl:
            multichar.update(_TAG_RE.findall(tag))
    for upper, _surf in variants:
        multichar.update(_TAG_RE.findall(upper))
    for w, tag in (function_words or []):
        multichar.update(_TAG_RE.findall(tag))
    for w, tag in (adverbs or []):
        multichar.update(_TAG_RE.findall(tag))

    lines = ["Multichar_Symbols " + " ".join(sorted(multichar)), ""]

    # ── Root: Continuations zu allen Stamm-Lexika + geschlossene Klassen ──
    lines.append("LEXICON Root")
    for key in sorted(infls):
        kind, par, sub = key
        lines.append(f"{_lexname(f'Stems{kind}', par, sub)} ;")
    if function_words:
        lines.append("FuncWords ;")
    if adverbs:
        lines.append("Adverbs ;")
    if variants:
        lines.append("Variants ;")
    lines.append("")

    # ── Stamm- + Endungs-Lexika je Gruppe ──
    for key in sorted(infls):
        kind, par, sub = key
        stem_lex = _lexname(f"Stems{kind}", par, sub)
        infl_lex = _lexname(f"Infl{kind}", par, sub)
        lines.append(f"LEXICON {stem_lex}")
        for upper, lower in sorted(stems[key]):
            lines.append(_entry(upper, lower, infl_lex))
        lines.append("")
        lines.append(f"LEXICON {infl_lex}")
        for tag, lower in sorted(infls[key].items()):
            lines.append(_entry(tag, lower, "#"))
        lines.append("")

    if function_words:
        lines.append("LEXICON FuncWords")
        for w, tag in sorted(function_words):
            lines.append(_entry(f"{w}{tag}", w, "#"))
        lines.append("")

    if adverbs:
        lines.append("LEXICON Adverbs")
        for w, tag in sorted(set(adverbs)):
            lines.append(_entry(f"{w}{tag}", w, "#"))
        lines.append("")

    if variants:
        lines.append("LEXICON Variants")
        for upper, surface in sorted(variants):
            lines.append(_entry(upper, surface, "#"))
        lines.append("")

    return "\n".join(lines)
