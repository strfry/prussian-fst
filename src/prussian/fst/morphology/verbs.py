"""Verbale Morphologie.

Verb-Einträge kommen aus data/gold/goldstandard_verben_fst.json als
{paradigm, lemma, tense, stamm, suffixe} und brauchen aktuell keine
Aufbereitung. Die reflexive Enklitik ` si` (nur P106b smeītwei) wird bei
der Emission (lexd.py) via tags.split_reflexive abgespalten und als +Refl
getaggt — Klitik = Syntax, außerhalb der Verbmorphologie.

Die Funktion `wordlist_to_verb_entries` inferiert Stämme aus Twanksta-3sg-
Formen: -tun/-twei vom Infinitiv abstreifen, finite Stämme über 3sg aus
prussian_dictionary.json gewinnen, Archiphoneme erkennen.  Suppletive und
"stumme" Paradigmen (Stamm < 2 Buchstaben) werden übersprungen.

Künftiger Ausbau (Partizipien/Modi, docs/ORTHO_RULES.md §2) gehört hierher.
"""

import re

from prussian.fst.oracle import LONG_VOWELS, fold, strip_macron
from prussian.fst.tags import split_reflexive

VERB_POS = "+V"

# Paradigmen, deren GS-Präsensstamm != Präteritumstamm (suppletiv)
_SUPPL_PARADIGMS: set[str] = set()

# Paradigmen mit "stummem" Stamm (< 2 Buchstaben im GS)
_STUMME_PARADIGMS: set[str] = set()


def groups(verb_entries: list[dict]):
    """(Gruppenschlüssel, Tag-Präfix, 'verb', Eintrag) je Verbeintrag."""
    for e in verb_entries:
        key = ("V", e["paradigm"], e["tense"])
        yield key, VERB_POS, "verb", e


def wl_groups(wl_entries: list[dict]):
    """Wie groups, aber mit separatem Schlüssel ('Vw', …) für Wortlisten-
    Verben, damit sie eigene Infl-Lexika bekommen (abweichende Inf-Endung)."""
    for e in wl_entries:
        key = ("Vw", e["paradigm"], e["tense"])
        yield key, VERB_POS, "verb", e


def _is_verb_paradigm(par: str) -> bool:
    try:
        return int(re.match(r"\d+", par).group()) >= 71  # type: ignore[union-attr]
    except (ValueError, AttributeError):
        return False


def _get_3sg(indicative: list, tense: str) -> str | None:
    for block in indicative:
        if block.get("tense") == tense:
            forms = block.get("forms", [])
            if len(forms) >= 3:
                return forms[2].get("form", "")
    return None


def _clean_form(form: str) -> str:
    bare, _ = split_reflexive(form)
    return bare.strip()


def _detect_archiphoneme(stem_surface: str) -> str:
    """Archiphonem-Positionen (Makron) in einem Verb-Stamm markieren."""
    norm = fold(stem_surface)
    acc_positions = set()
    for i, ch in enumerate(stem_surface):
        if ch in LONG_VOWELS:
            if i < len(norm) and norm[i] in "aeiou":
                acc_positions.add(i)
    if not acc_positions:
        return stem_surface
    result: list[str] = []
    for i, ch in enumerate(stem_surface):
        if i in acc_positions:
            result.append(strip_macron(ch).upper())
        else:
            result.append(ch)
    return "".join(result)


def _build_gs_maps(gsv_entries: list[dict]):
    """Suffix-Map und Analyse der Paradigmen-Eigenschaften."""
    suffixe_map: dict[tuple[str, str], dict] = {}
    stem_map: dict[tuple[str, str], str] = {}
    for e in gsv_entries:
        key = (e["paradigm"], e["tense"])
        suffixe_map[key] = e["suffixe"]
        stem_map[key] = e["stamm"]

    suppletiv: set[str] = set()
    for e in gsv_entries:
        if e["tense"] == "present":
            pret_key = (e["paradigm"], "preterite")
            if pret_key in stem_map and stem_map[pret_key] != e["stamm"]:
                suppletiv.add(e["paradigm"])

    stumm: set[str] = set()
    for e in gsv_entries:
        if len(e["stamm"]) < 2:
            stumm.add(e["paradigm"])

    return suffixe_map, suppletiv, stumm


def wordlist_to_verb_entries(
    dict_data: list[dict],
    gsv_entries: list[dict],
) -> list[dict]:
    """Inferiert finite Stämme aus Twanksta-3sg-Formen (prussian_dictionary.json).

    Für jeden Wortlisten-Verbeintrag mit Paradigma im GS-Bereich:
      1. -tun/-twei-Endung bestimmen (aus dem Wort)
      2. 3sg Präsens/Präteritum aus ``forms.indicative`` extrahieren
      3. GS-3sg-Suffix abstreifen → finiter Stamm
      4. Archiphoneme erkennen (Makron → Großbuchstabe)
      5. Goldstandard-kompatible Einträge (present + preterite) erzeugen

    Suppletive Paradigmen (P115 būtwei u.a.) und "stumme" Stämme (P106d laītun,
    Stamm ``l``, u.a.) werden übergangen.
    """
    suffixe_map, suppletiv, stumm = _build_gs_maps(gsv_entries)

    entries: list[dict] = []
    seen: set[tuple[str, str, str]] = set()

    for w in dict_data:
        par = w.get("paradigm", "")
        if not par or not _is_verb_paradigm(par):
            continue
        if par in suppletiv or par in stumm:
            continue

        word = w["word"]
        if " " in word or "/" in word:
            continue

        if word.endswith("tun"):
            inf_suffix = "tun"
        elif word.endswith("twei"):
            inf_suffix = "twei"
        else:
            continue

        forms = w.get("forms", {})
        indicative = forms.get("indicative", [])
        pres_3sg = _get_3sg(indicative, "Present")
        pret_3sg = _get_3sg(indicative, "Past")

        if not pres_3sg:
            continue

        pres_raw = _clean_form(pres_3sg)
        pret_raw = _clean_form(pret_3sg) if pret_3sg else None

        for tense, raw in [("present", pres_raw), ("preterite", pret_raw)]:
            if not raw:
                continue

            gs_key = (par, tense)
            gs_suffixe = suffixe_map.get(gs_key)
            if gs_suffixe is None:
                continue

            sg3_suffix = gs_suffixe.get("3sg", {}).get("suffix", "")
            if not raw.endswith(sg3_suffix):
                continue

            stem_surface = raw[: -len(sg3_suffix)] if sg3_suffix else raw
            if len(stem_surface) < 2:
                continue

            stamm = _detect_archiphoneme(stem_surface)

            new_suffixe: dict[str, dict] = {}
            for cell, v in gs_suffixe.items():
                if cell == "Inf":
                    new_suffixe[cell] = {
                        "suffix": inf_suffix,
                        "betont": v.get("betont", False),
                        "palatize": False,
                    }
                else:
                    new_suffixe[cell] = dict(v)

            key = (word, par, tense)
            if key not in seen:
                seen.add(key)
                entries.append({
                    "paradigm": par,
                    "lemma": word,
                    "tense": tense,
                    "stamm": stamm,
                    "suffixe": new_suffixe,
                })

    return entries
