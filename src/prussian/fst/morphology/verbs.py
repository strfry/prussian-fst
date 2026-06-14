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
from collections import OrderedDict

from prussian.fst.oracle import LONG_VOWELS, fold, strip_macron
from prussian.fst.tags import split_reflexive

VERB_POS = "+V"

# Universelle Modus-Kategorien (Rollout Stufe 1+2). Die Suffixe sind über ALLE
# Paradigmen identisch; der lemmaspezifische Stamm wird gewonnen, indem das
# universelle (Leit-)Suffix von der jeweils attestierten Leitform abgestreift
# wird. So absorbiert der Stamm Grenz-Sandhi, Themavokal UND Hiatus-w, und
# stem+suffix == attestierte Form gilt per Konstruktion — keine Extraregel nötig
# (-st-Wurzel: bredlai→bred-; i-Klasse: abōnints→abōni-, abōniwuns→abōniw-).
#
# Stamm-tragende Prinzipalform je Kategorie (Drei-Stamm-Modell, Lehrer-Antwort
# docs/HANDOFF_verb_modi_konditionierung.md): Inf-Stamm für Opt/Konj/Pass.-Ptz,
# Präsensstamm fürs Präs.-Ptz, PRÄTERITALSTAMM fürs Akt.-Ptz (nicht aus dem
# Präsens ableitbar — Ablaut/Nasalinfix/ja-Schwund; daher attestiert abstreifen).
#: tense → (Leitform-Schlüssel, abzustreifendes Leitsuffix, Zellen→Suffix)
_UNIV_MOODS: dict[str, tuple] = {
    "optative":     ("optative",  "sei", OrderedDict([("Opt", "sei")])),
    "subjunctive":  ("subj_as",   "lai", OrderedDict([("1sg", "lai"), ("2sg", "lai"),
                                          ("3sg", "lai"), ("1pl", "limai"), ("2pl", "litei")])),
    "passive_ptcp": ("passive",   "ts",  OrderedDict([("PssPrc", "ts")])),
    "active_ptcp":  ("past_p",    "uns", OrderedDict([("PstPrc", "uns")])),
    "present_ptcp": ("present_p",  "nts", OrderedDict([("PrsPrc", "nts")])),
}

# Imperativ: eine Kategorie, zwei Zellen (2sg/2pl), die EINEN Stamm teilen, aber
# klassenabhängige Suffixe haben → Klasse am 2sg-Auslaut erkennen, Stamm = 2sg
# minus 2sg-Suffix, Gruppierung nach Klasse (geteiltes Infl bleibt uniform).
# Reihenfolge: spezifisch vor generisch (jais/āis/ais vor is; s = au-Klasse).
_IMP_CLASSES: list[tuple[str, tuple[str, str]]] = [
    ("jais", ("jais", "jaiti")),
    ("āis",  ("āis",  "āiti")),
    ("ais",  ("ais",  "aiti")),
    ("is",   ("is",   "iti")),
    ("s",    ("s",    "iti")),   # au-Klasse (āustabaus)
]


def _leitform(forms: dict, key: str) -> str | None:
    """Attestierte Leitform einer Modus-Kategorie aus dem Wörterbuch-Eintrag."""
    if key == "optative":
        return _first(forms.get("optative"))
    if key == "subj_as":
        return next((_first(p.get("form")) for p in forms.get("subjunctive", [])
                     if p.get("pronoun") == "as"), None)
    ptype = {"passive": "Passive", "past_p": "Past", "present_p": "Present"}.get(key)
    if ptype:
        return next((_first(p.get("form")) for p in forms.get("participles", [])
                     if p.get("type") == ptype), None)
    return None

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
    Verben, damit sie eigene Infl-Lexika bekommen (abweichende Inf-Endung).

    ``group`` überschreibt den Paradigma-Teil des Schlüssels (Imperativ wird nach
    Präsensklasse statt Paradigma gruppiert, damit das geteilte Infl uniform ist)."""
    for e in wl_entries:
        key = ("Vw", e.get("group", e["paradigm"]), e["tense"])
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


def _first(form: str | None) -> str | None:
    """Erste Variante (vor '/'); Mehrwort-/Reflexivformen verwerfen."""
    if not isinstance(form, str):
        return None
    f = form.split("/", 1)[0].strip()
    if not f or " " in f or f == "—":
        return None
    return f


def _mood_stem(form: str, suffix: str) -> str | None:
    """Inf-Stamm = attestierte Form minus universelles Suffix, archiphonem-
    markiert. ``None``, wenn die Form nicht auf das Suffix endet (Irregularität)
    oder der Reststamm zu kurz ist."""
    if not form.endswith(suffix) or len(form) <= len(suffix) + 1:
        return None
    stem = _detect_archiphoneme(form[: -len(suffix)])
    return stem if len(stem) >= 2 else None


def _mood_entries(word: str, par: str, forms: dict) -> list[dict]:
    """Modus-/Partizip-Einträge eines Verbs (Rollout Stufe 1+2).

    Universelle Kategorien (Opt/Konj/Pass.-Ptz/Akt.-Ptz/Präs.-Ptz): Stamm =
    attestierte Leitform minus universelles Suffix → stem+suffix==Form. Imperativ:
    klassenkonditioniert (2sg/2pl), Stamm aus der 2sg-Form, Gruppierung (``group``)
    nach Klasse, damit das geteilte Infl uniform bleibt. ``betont`` (= Stamm trägt
    ein Archiphonem) steuert Akzentklasse/Längung.
    """
    out: list[dict] = []

    for tense, (lkey, lead, suffixe) in _UNIV_MOODS.items():
        form = _leitform(forms, lkey)
        if not form:
            continue
        stamm = _mood_stem(form, lead)
        if stamm is None:
            continue
        betont = any(c in "AEIOU" for c in stamm)
        out.append({
            "paradigm": par, "lemma": word, "tense": tense, "stamm": stamm,
            "suffixe": OrderedDict(
                (cell, {"suffix": sfx, "betont": betont})
                for cell, sfx in suffixe.items()),
        })

    im = next((_first(p.get("form")) for p in forms.get("imperative", [])
               if "t" in p.get("pronoun", "")), None)
    if im:
        for marker, (s2sg, s2pl) in _IMP_CLASSES:
            if im.endswith(marker) and len(im) > len(marker) + 1:
                stamm = _detect_archiphoneme(im[: -len(marker)])
                if len(stamm) >= 2:
                    betont = any(c in "AEIOU" for c in stamm)
                    out.append({
                        "paradigm": par, "lemma": word, "tense": "imperative",
                        "stamm": stamm, "group": f"imp_{marker}",
                        "suffixe": OrderedDict([
                            ("2sg", {"suffix": s2sg, "betont": betont}),
                            ("2pl", {"suffix": s2pl, "betont": betont})]),
                    })
                break
    return out


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

        # Modi/Partizipien (Rollout Stufe 1: Optativ/Konjunktiv/Passivpartizip).
        # Unabhängig vom Präsens-3sg — sitzen auf dem Inf-Stamm.
        if isinstance(forms, dict):
            for me in _mood_entries(word, par, forms):
                mkey = (word, par, me["tense"])
                if mkey not in seen:
                    seen.add(mkey)
                    entries.append(me)

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
