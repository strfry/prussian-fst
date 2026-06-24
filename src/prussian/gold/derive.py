"""Paradigmentabellen gold-frei aus den Wörterbüchern ableiten.

Statt des hand-kuratierten Goldstandards (data/gold/goldstandard.json) werden
die Suffixtabellen je Paradigma direkt aus den Prusaspira-Deklinationstabellen
gewonnen — Twanksta faltet via prussian.fst.ortho auf denselben Standard
(brauchen Gold nicht mehr). Die Faltung liefert die orthographische
Normalisierung; die Morphotaktik kommt aus der Evidenz der Wörterbücher.

Ansatz (nominal):
  1. je Lemma die Deklinationstabelle (Kasus×Numerus×Genus) einlesen,
  2. Stammgrenze = längster gemeinsamer Präfix der Formen, **makron- und
     palatalisierungs-insensitiv** (CHAR_FOLD längenerhaltend) — exakt die
     Gold-Stammdefinition,
  3. Suffix je Zelle = Form minus Stamm (Standardschreibung, ungefaltet),
  4. Mehrheitsvotum je Zelle über alle Lemmata des Paradigmas.

Reproduktion roh (ohne FST-Regelschicht) ≈ 82 % der Prusaspira-Formen; die
Lücke sind stamm-konditionierte Allomorphe (Gemination, Palatalisierung), die
im FST die Regelschicht (phonology/rules: JPAL, SHORTEN/LENGTHEN) auflöst.

Aufruf:  python -m prussian.gold.derive   # Reproduktionsstatistik
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent.parent
PR_PATH = ROOT / "data/external/prusaspira_entries.json"

#: Längenerhaltende Diakritika- + Palatalisierungs-Faltung für die Stammgrenze
#: (= makron-/palatal-insensitiver gemeinsamer Präfix, Gold-Stammdefinition).
#: Die *verlustbehafteten* Falt-Schritte (themat. -s, -an~-u) aus
#: prussian.fst.ortho gehören NICHT hierher — sie zerstören die Endung.
CHAR_FOLD = str.maketrans({
    "ā": "a", "ē": "e", "ī": "i", "ō": "o", "ū": "u",        # Makron
    "š": "s", "ž": "z", "ź": "z", "č": "c",                  # Caron
    "à": "a", "è": "e", "ì": "i", "ò": "o", "ù": "u",        # Gravis
    "á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u", "ǹ": "n",  # Akut
    "ŕ": "r", "ĺ": "l", "ľ": "l",                            # Rhotik/Lateral
    "ģ": "g", "ķ": "k", "ņ": "n", "ţ": "t", "ļ": "l", "ŗ": "r",  # Palatale
    "c": "k",                                               # Lehnwort-c
})

_CASE = {"Nominative": "Nom", "Genitive": "Gen",
         "Dative": "Dat", "Accusative": "Akk"}
_NUM = {"singular": "sg", "plural": "pl"}
CELLS = ["Nom sg", "Gen sg", "Dat sg", "Akk sg",
         "Nom pl", "Gen pl", "Dat pl", "Akk pl"]


def char_fold(s: str) -> str:
    """Längenerhaltende Skelettform (nur Diakritika/Palatale) für die Stammgrenze."""
    return s.lower().translate(CHAR_FOLD)


def declension_cells(entry: dict) -> dict[str, str]:
    """{'Nom sg': Form, …} aus der ``forms.declension`` eines Dict-Eintrags."""
    f = entry.get("forms")
    if not isinstance(f, dict):
        return {}
    out: dict[str, str] = {}
    for block in (f.get("declension") or []):
        for ci in block.get("cases", []):
            case = _CASE.get(ci.get("case", ""))
            if not case:
                continue
            for num_name, num in _NUM.items():
                v = (ci.get(num_name) or "").strip()
                if v and v != "—":
                    out.setdefault(f"{case} {num}", v)
    return out


def stem_boundary(forms: list[str]) -> int:
    """Länge des makron-/palatal-insensitiven gemeinsamen Präfixes der Formen."""
    folded = [char_fold(x) for x in forms]
    lo, hi = min(folded), max(folded)
    i = 0
    while i < len(lo) and i < len(hi) and lo[i] == hi[i]:
        i += 1
    return i


def derive_suffix_tables(
    entries: list[dict],
) -> dict[str, dict[str, str]]:
    """Paradigma → {Zelle: Mehrheits-Suffix} aus den Deklinationstabellen."""
    votes: dict[str, dict[str, Counter]] = defaultdict(
        lambda: defaultdict(Counter))
    for e in entries:
        par = e.get("paradigm")
        if not par:
            continue
        cells = declension_cells(e)
        if len(cells) < 6:
            continue
        L = stem_boundary(list(cells.values()))
        if L < 1:
            continue
        for cell, form in cells.items():
            votes[par][cell][form[L:]] += 1
    return {
        par: {cell: cnt.most_common(1)[0][0] for cell, cnt in cells.items()}
        for par, cells in votes.items()
    }


def derive_twanksta_j_pairs(
    prusaspira: list[dict], twanksta: list[dict],
) -> dict[str, list[str]]:
    """{Twanksta-Endung: [Standardendungen]} — weichvokalische Twanksta-j-Varianten.

    Die Twanksta-Wörterbücher schreiben die Palatalisierung/Weichheit am
    Stamm-Endungs-Übergang als explizites ``j`` (``-jas`` für Standard ``-es``,
    ``-jan`` für ``-in`` …). Diese **morphologische** Alternation (ja↔e/i) ist
    keine Faltung; sie wird hier aus dem Vergleich der je-Paradigma abgeleiteten
    Suffixtabellen beider Dicts gewonnen (j in Twanksta, nicht im Standard) und
    speist die nachsichtige Analyse — datengetrieben, kein generatives
    Regel-Listing.
    """
    std = derive_suffix_tables(prusaspira)
    var = derive_suffix_tables(twanksta)
    grouped: dict[str, set[str]] = defaultdict(set)
    for par, s_table in std.items():
        v_table = var.get(par, {})
        for cell in CELLS:
            sc, vc = s_table.get(cell), v_table.get(cell)
            if not sc or not vc or any(x in sc + vc for x in " /"):
                continue
            if (char_fold(sc) != char_fold(vc)
                    and "j" in vc and "j" not in sc and len(vc) <= 8):
                grouped[vc].add(sc)
    return {tw: sorted(stds) for tw, stds in sorted(grouped.items())}


def _report() -> None:
    pr = json.loads(PR_PATH.read_text(encoding="utf-8"))
    tables = derive_suffix_tables(pr)

    by_par: dict[str, list[dict]] = defaultdict(list)
    for e in pr:
        if e.get("paradigm"):
            by_par[e["paradigm"]].append(e)

    tot = ok = perfect = npar = 0
    for par, table in tables.items():
        f_tot = f_ok = 0
        for e in by_par[par]:
            cells = declension_cells(e)
            if len(cells) < 6:
                continue
            L = stem_boundary(list(cells.values()))
            if L < 1:
                continue
            stem = next(iter(cells.values()))[:L]
            for cell, form in cells.items():
                f_tot += 1
                if stem + table.get(cell, "\0") == form:
                    f_ok += 1
        if not f_tot:
            continue
        npar += 1
        tot += f_tot
        ok += f_ok
        if f_ok / f_tot > 0.995:
            perfect += 1

    print(f"Prusaspira-Einträge: {len(pr)}")
    print(f"Paradigmen mit Tabelle: {npar} (davon ≥99.5% roh reproduziert: "
          f"{perfect})")
    print(f"Formen roh reproduziert (ohne FST-Regelschicht): "
          f"{ok}/{tot} ({100*ok/tot:.1f}%)")
    print("Die Lücke schließt im FST die Regelschicht (Palatalisierung, "
          "Gemination, Archiphonem).")


if __name__ == "__main__":
    _report()
