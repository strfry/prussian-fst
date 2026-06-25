"""Gemeinsame Morphotaktik-Helfer für den lexd-Generator (hfst.lexd_gen).

Akzentklassen-Logik und Unterseiten-Rendering (markierte Stämme/Endungen mit
Archiphonemen Â Ê Î Ô Û und Markern M/S/J), geteilt vom HFST-lexd-Generator.
Die Auflösung zur Oberfläche übernimmt die Regelschicht (hfst.rules).

Akzentklassen (vgl. docs/AKZENT.md):
  bar  Stamm immer lang   → Stamm literal mit Makron, keine Marker
  mob  Stamm alterniert   → Stamm archiphonemisch, Marker M; starke
                            Endungszellen (betont=false) erhalten S
  na   nicht beobachtbar  → Stamm literal; Wortlisten-Stämme mit
                            detektiertem Makron werden lang gehalten
                            (Baryton-Default — das frühere Kürzen in
                            allen Zellen widersprach der Nom-sg-Evidenz)
"""

from prussian.fst.oracle import ARCHI_SET, LONG
from prussian.fst.tags import (
    cell_tag, ptcp_cell_tag, split_reflexive, verb_cell_tag,
)


# Verb-Sub-Schlüssel, deren Gruppen Endungen mehrerer Einträge bündeln (s.
# verbs._verb_sub): Inf-Stamm-Modi und nicht-suppletives Präsens+Präteritum.
_MERGED_SUBS = frozenset({"inf_stem", "pres_stem"})


def entry_class(suffixe: dict) -> str:
    """bar / mob / na aus dem betont-Muster (mechanisch; vgl. accent.py)."""
    vals = [v["betont"] for v in suffixe.values()]
    if all(vals):
        return "bar"
    if not any(vals):
        return "na"
    return "mob"


def render_stem(stamm: str, cls: str) -> str:
    """Unterseiten-Stamm: archiphonemisch + M (mob) oder literal (bar/na).

    Archiphoneme sind die distinkten Symbole ``ÂÊÎÔÛ`` (oracle.ARCHI); übrige
    Zeichen werden casegefaltet (Großschreibung als eigene Eigenschaft: s.
    docs/BACKLOG.md, eigener Folgeschritt).
    """
    has_arch = any(c in ARCHI_SET for c in stamm)
    if cls == "mob" and has_arch:
        return "M" + "".join(c if c in ARCHI_SET else c.lower() for c in stamm)
    # bar: lang auflösen.  na: ebenfalls lang (Baryton-Default, s. Docstring).
    return "".join(LONG.get(c, c.lower()) for c in stamm)


def _lexname(kind: str, par: str, sub: str) -> str:
    return f"{kind}_P{par}_{sub or 'x'}"


def _cell_tag(lexkind: str, e: dict, cell: str, v: dict) -> tuple[str, dict]:
    """Zellen-Tag + (bei Verben reflexiv-bereinigter) Endungswert."""
    if lexkind == "ptcp":
        return ptcp_cell_tag(e["tense"], e["gender"], cell), v
    if lexkind == "verb":
        bare, refl = split_reflexive(v["suffix"])
        if refl:
            v = {**v, "suffix": bare}
        return verb_cell_tag(e["tense"], cell, refl), v
    return cell_tag(cell), v
