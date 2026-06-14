"""Morphotaktische lexd-Grammatik zusammenbauen (≈ root.lexc + stems/affixes).

POS-agnostischer Emissions-Kern: aus den (Gruppenschlüssel, Tag-Präfix,
Art, Eintrag)-Strömen von morphology.nominals und morphology.verbs entsteht
der lexd-Quelltext mit markierter Unterseite. Jeder Stamm steht genau einmal
pro Gruppe; Archiphoneme (A E I O U) und Marker (M/S/J) bleiben sichtbar, die
Auflösung zur Oberfläche übernimmt phonology.py.

Akzentklassen (vgl. docs/AKZENT.md):
  bar  Stamm immer lang   → Stamm literal mit Makron, keine Marker
  mob  Stamm alterniert   → Stamm archiphonemisch, Marker M; starke
                            Endungszellen (betont=false) erhalten S
  na   nicht beobachtbar  → Stamm literal; Wortlisten-Stämme mit
                            detektiertem Makron werden lang gehalten
                            (Baryton-Default — das frühere Kürzen in
                            allen Zellen widersprach der Nom-sg-Evidenz)

Twanksta-j- und elaktr-Quellvarianten werden als V-markierte Zeilen
emittiert (spellrelax.py); der Standard-Analysator filtert V-Pfade aus,
der nachsichtige (lenient.fst) akzeptiert sie.
"""

from collections import defaultdict
from itertools import chain

from prussian.fst.oracle import LONG, resolve_stem
from prussian.fst.spellrelax import elaktr_variant, jan_variant
from prussian.fst.tags import (
    cell_tag, split_reflexive, split_suffix, verb_cell_tag,
)
from prussian.fst.morphology import nominals, verbs


def entry_class(suffixe: dict) -> str:
    """bar / mob / na aus dem betont-Muster (mechanisch; vgl. accent.py)."""
    vals = [v["betont"] for v in suffixe.values()]
    if all(vals):
        return "bar"
    if not any(vals):
        return "na"
    return "mob"


def render_stem(stamm: str, cls: str) -> str:
    """Unterseiten-Stamm: archiphonemisch + M (mob) oder literal (bar/na)."""
    has_arch = any(c in "AEIOU" for c in stamm)
    if cls == "mob" and has_arch:
        return "M" + "".join(c if c in "AEIOU" else c.lower() for c in stamm)
    # bar: lang auflösen.  na: ebenfalls lang (Baryton-Default, s. Docstring).
    return "".join(LONG.get(c, c.lower()) for c in stamm)


def render_suffix(v: dict, cls: str) -> list[str]:
    """Unterseiten-Endungen: [Standard, ggf. Twanksta-j-Variante].

    Standard:  (J)(S)suffix — J palatalisiert den Stammauslaut.
    Variante:  V(S)j-suffix — explizites j, Stamm bleibt unpalatalisiert.
    """
    std, _variant = split_suffix(v["suffix"])
    s_marker = "S" if cls == "mob" and not v["betont"] else ""
    j_marker = "J" if v.get("palatize", False) else ""
    lowers = [f"{j_marker}{s_marker}{std}"]
    jvar = jan_variant(std)
    if jvar is not None:
        lowers.append(f"V{s_marker}{jvar}")
    return lowers


def _lexname(kind: str, par: str, sub: str) -> str:
    return f"{kind}_P{par}_{sub or 'x'}"


def _cell_tag(lexkind: str, e: dict, cell: str, v: dict) -> tuple[str, dict]:
    """Zellen-Tag + (bei Verben reflexiv-bereinigter) Endungswert."""
    if lexkind == "verb":
        bare, refl = split_reflexive(v["suffix"])
        if refl:
            v = {**v, "suffix": bare}
        return verb_cell_tag(e["tense"], cell, refl), v
    return cell_tag(cell), v


def build_lexd(
    entries: list[dict],
    verb_entries: list[dict],
    verb_wl_entries: list[dict] | None = None,
    closed_entries: list[dict] | None = None,
    function_words: list[tuple[str, str]] | None = None,
    adverbs: list[tuple[str, str]] | None = None,
) -> str:
    """Nominale + verbale Einträge → lexd-Quelltext.

    ``verb_wl_entries`` werden mit eigenem Gruppenschlüssel (Vw statt V)
    eingefügt, damit sie separate Infl-Lexika erhalten (erforderlich,
    weil Wortlisten-Verben eine abweichende Infinitiv-Endung ``tun``/``twei``
    anstelle von ``un``/``wei`` im Goldstandard verwenden).

    ``closed_entries``: handkuratierte Einträge (Personalpronomen) im
    Goldstandard-Format — durchlaufen denselben Stem+Infl-Mechanismus.

    ``function_words``: (Wort, POS-Tag)-Paare für uninflected closed-class
    words — werden als einzelne lexd-Einträge ``Wort+Tag:Wort`` emittiert
    (POS-Tag auf der Analyse-Oberseite, Wort als Surface-Unterseite).

    ``adverbs``: ebensolche (Wort, +Adv)-Paare; eigene geschlossene Klasse
    (eigenes Lexikon ``Adverbs``), da altpreußische Adverbien überwiegend
    lexikalisiert sind und nicht aus dem Adjektivsystem abgeleitet werden.
    """
    # Gruppen: (paradigm, gender) bzw. (paradigm, tense) teilen Endungslexikon
    stems: dict[tuple, list[str]] = defaultdict(list)
    infls: dict[tuple, dict[str, list[str]]] = {}
    variants: set[tuple[str, str]] = set()

    def add_group(key, upper_prefix, lexkind, e):
        cls = entry_class(e["suffixe"])
        if key not in infls:
            infl = {}
            for cell, v in e["suffixe"].items():
                tag, v = _cell_tag(lexkind, e, cell, v)
                infl[tag] = render_suffix(v, cls)
            infls[key] = infl
        stem = render_stem(e["stamm"], cls)
        lines = [f"{e['lemma']}{upper_prefix}:{stem}"]
        # Stammvariante elektr- ↔ elaktr- (Prusaspira-Schreibung,
        # docs/BACKLOG.md) — über denselben V-Mechanismus wie die
        # Endungsvarianten, nur im nachsichtigen Analysator.
        ev = elaktr_variant(stem)
        if ev is not None:
            lines.append(f"{e['lemma']}{upper_prefix}:V{ev}")
        for line in lines:
            if line not in stems[key]:
                stems[key].append(line)

        # Doubletten: literale Vollformen, sofern sie zum Stamm passen
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

    # ── lexd-Text ──
    lines = ["PATTERNS"]
    for key in sorted(infls):
        kind, par, sub = key
        lines.append(f"{_lexname(f'Stems{kind}', par, sub)} "
                     f"{_lexname(f'Infl{kind}', par, sub)}")
    if function_words:
        lines.append("FuncWords")
    if adverbs:
        lines.append("Adverbs")
    if variants:
        lines.append("Variants")
    lines.append("")

    for key in sorted(infls):
        kind, par, sub = key
        lines.append(f"LEXICON {_lexname(f'Stems{kind}', par, sub)}")
        lines.extend(sorted(stems[key]))
        lines.append("")
        lines.append(f"LEXICON {_lexname(f'Infl{kind}', par, sub)}")
        for tag, lowers in sorted(infls[key].items()):
            for lower in lowers:
                lines.append(f"{tag}:{lower}")
        lines.append("")

    if function_words:
        lines.append("LEXICON FuncWords")
        for w, tag in sorted(function_words):
            lines.append(f"{w}{tag}:{w}")
        lines.append("")

    if adverbs:
        lines.append("LEXICON Adverbs")
        for w, tag in sorted(set(adverbs)):
            lines.append(f"{w}{tag}:{w}")
        lines.append("")

    if variants:
        lines.append("LEXICON Variants")
        for upper, surface in sorted(variants):
            lines.append(f"{upper}:{surface}")
        lines.append("")

    return "\n".join(lines)
