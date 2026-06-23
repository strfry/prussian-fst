"""Markierte Morphotaktik als lexd-Grammatik mit Tag-Filterung (HFST-Zweig).

Erzeugt aus denselben Eintragsdaten wie der pyfoma-Build ein **lexd**-Lexikon
mit markierter Unterseite (Archiphoneme A E I O U, Marker M/S/J/·). Das
``<Tag>``-Format wird von ``lexd`` nativ als Multichar-Symbol erkannt; die
Gender-Konditionierung erfolgt über lexd-eigene ``[gFem]``/``[gMsc]``/
``[gNeut]``-Filter-Tags — **ein** Stem+Infl-Lexikon pro Paradigma statt drei.

Keine V-Varianten-Zeilen — Quellvarianten entstehen über generalisierende
spellrelax-Regeln (``rules.py``), wie im bisherigen lexc-Zweig.

Struktur:
    PATTERNS
    StemsN_P25[gMsc] InflN_P25[gMsc]
    StemsN_P25[gFem] InflN_P25[gFem]
    StemsN_P25[gNeut] InflN_P25[gNeut]

    LEXICON StemsN_P25
    labs<A><Msc>:lab[gMsc]

    LEXICON InflN_P25
    <Sg><Nom>:s[gMsc]
    <Sg><Nom>:i[gFem]
    <Sg><Nom>:an[gNeut]
    <Pl><Dat>:awāns
"""

import re
from collections import defaultdict
from itertools import chain

from prussian.fst.morphology import nominals, verbs
from prussian.fst.morphology.lexd import (
    _MERGED_SUBS,
    _cell_tag,
    _lexname,
    entry_class,
    render_stem,
)
from prussian.fst.oracle import resolve_stem
from prussian.fst.spellrelax import jan_variant
from prussian.fst.tags import split_suffix

_BD = "·"

#: Gender-Sub-Werte → lexd-Filter-Tag
_GENDER_TAG = {"m": "gMsc", "f": "gFem", "n": "gNeut"}

#: regex für +Tag → <Tag>-Ersatz in Oberseiten-Strings
_PLUS_RE = re.compile(r"\+([A-Za-z0-9]+)")

#: lexd-Meta-Zeichen, die in Unterseiten-Werten escaped werden müssen
_LEXD_META = str.maketrans(
    {
        "\\": "\\\\",
        ":": "\\:",
        "#": "\\#",
        "[": "\\[",
        "]": "\\]",
    }
)


def _to_lexd(s: str) -> str:
    """+Sg+Nom → <Sg><Nom>"""
    return _PLUS_RE.sub(r"<\1>", s)


def _esc(s: str) -> str:
    """lexd-Metazeichen (:, \\, #, [, ]) in Unterseiten-Werten escapen."""
    return s.translate(_LEXD_META)


def _render_suffix_std(v: dict, cls: str) -> str:
    """(J)(S)(·)suffix — markerhaft, keine V-Varianten."""
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
    """(Stämme, Endungen, Parallelformen) wie lexc_gen.collect, V-frei."""
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
        for cell, v in e["suffixe"].items():
            _std, variant_full = split_suffix(v["suffix"])
            if variant_full is None:
                continue
            pal = v.get("palatize", False)
            if variant_full.startswith(
                resolve_stem(e["stamm"], True, pal)
            ) or variant_full.startswith(resolve_stem(e["stamm"], False, pal)):
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


def build_lexd(
    entries: list[dict],
    verb_entries: list[dict],
    verb_wl_entries: list[dict] | None = None,
    closed_entries: list[dict] | None = None,
    function_words: list[tuple[str, str]] | None = None,
    adverbs: list[tuple[str, str]] | None = None,
) -> str:
    """Eintragsdaten → lexd-Quelltext (``<Tag>``-Format, Gender-Tag-Filterung)."""
    stems, infls, variants = collect(
        entries, verb_entries, verb_wl_entries, closed_entries
    )

    # ── Gender-Merging: (kind, par, gender) → (kind, par) je Paradigma ──
    # Jede nominale Gruppe mit Gender-Sub wird in eine gemeinsame Gruppe
    # kollabiert; der Gender-Unterschied steckt in [gFem]/[gMsc]/[gNeut]-Tags
    # je Eintrag. Verb-Gruppen und adverbielle nominale (gender="") bleiben
    # unberührt.
    merged_stems = defaultdict(list)
    merged_infls = defaultdict(lambda: defaultdict(dict))
    merged_genders = defaultdict(set)  # (kind, par) → {gFem, gMsc, …}
    unmerged_keys = []  # keys that don't get gender-merged

    for key in sorted(stems):
        kind, par, sub = key
        if kind == "N" and sub in _GENDER_TAG:
            gkey = (kind, par)
            gtag = _GENDER_TAG[sub]
            merged_genders[gkey].add(gtag)
            for upper, lower in stems[key]:
                merged_stems[gkey].append((_to_lexd(upper), lower, gtag))
            for tag, lower in infls[key].items():
                merged_infls[gkey][tag][sub] = lower
        else:
            unmerged_keys.append(key)

    lines = ["PATTERNS"]

    # Gender-merged nominal groups
    for gkey in sorted(merged_stems):
        kind, par = gkey
        stem_name = _lexname(f"Stems{kind}", par, "")
        infl_name = _lexname(f"Infl{kind}", par, "")
        for gtag in sorted(merged_genders.get(gkey, set())):
            lines.append(f"{stem_name}[{gtag}] {infl_name}[{gtag}]")

    # Non-gender groups (verbs, adverbs, etc.) — own pattern per key
    for key in sorted(unmerged_keys):
        kind, par, sub = key
        lines.append(
            f"{_lexname(f'Stems{kind}', par, sub)} {_lexname(f'Infl{kind}', par, sub)}"
        )

    if function_words:
        lines.append("FuncWords")
    if adverbs:
        lines.append("Adverbs")
    if variants:
        lines.append("Variants")
    lines.append("")

    # ── Gender-merged Stem+Infl-Lexika ──
    for gkey in sorted(merged_stems):
        kind, par = gkey
        stem_name = _lexname(f"Stems{kind}", par, "")
        infl_name = _lexname(f"Infl{kind}", par, "")
        lines.append(f"LEXICON {stem_name}")
        seen = set()
        for upper, lower, gtag in sorted(merged_stems[gkey]):
            entry = f"{upper}:{_esc(lower)}[{gtag}]"
            if entry not in seen:
                seen.add(entry)
                lines.append(entry)
        lines.append("")
        lines.append(f"LEXICON {infl_name}")
        # Zuerst gender-spezifische, dann geteilte Endungen
        for tag in sorted(merged_infls[gkey]):
            by_gender = merged_infls[gkey][tag]
            # Check ob Endung über alle Gender identisch ist
            unique_values = set(by_gender.values())
            if len(unique_values) == 1 and len(by_gender) >= 2:
                # Gleiche Endung in mehreren Genera → ein Eintrag mit allen Tags
                gtags = ",".join(_GENDER_TAG[s] for s in by_gender)
                lines.append(f"{_to_lexd(tag)}:{_esc(list(unique_values)[0])}[{gtags}]")
            else:
                for sub, lower in sorted(by_gender.items()):
                    gtag = _GENDER_TAG.get(sub, sub)
                    lines.append(f"{_to_lexd(tag)}:{_esc(lower)}[{gtag}]")
        lines.append("")

    # ── Unveränderte Lexika (Verben, Adverbien etc.) ──
    for key in sorted(unmerged_keys):
        kind, par, sub = key
        stem_lex = _lexname(f"Stems{kind}", par, sub)
        infl_lex = _lexname(f"Infl{kind}", par, sub)
        lines.append(f"LEXICON {stem_lex}")
        for upper, lower in sorted(stems[key]):
            lines.append(f"{_to_lexd(upper)}:{_esc(lower)}")
        lines.append("")
        lines.append(f"LEXICON {infl_lex}")
        for tag, lower in sorted(infls[key].items()):
            lines.append(f"{_to_lexd(tag)}:{_esc(lower)}")
        lines.append("")

    if function_words:
        lines.append("LEXICON FuncWords")
        for w, tag in sorted(function_words):
            lines.append(f"{_esc(w)}{_to_lexd(tag)}:{_esc(w)}")
        lines.append("")

    if adverbs:
        lines.append("LEXICON Adverbs")
        for w, tag in sorted(set(adverbs)):
            lines.append(f"{_esc(w)}{_to_lexd(tag)}:{_esc(w)}")
        lines.append("")

    if variants:
        lines.append("LEXICON Variants")
        for upper, surface in sorted(variants):
            lines.append(f"{_to_lexd(upper)}:{_esc(surface)}")
        lines.append("")

    return "\n".join(lines)
