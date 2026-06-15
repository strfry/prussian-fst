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
# docs/HANDOFF_verb_modi_konditionierung.md): Inf-Stamm für Opt/Konj, Präsens-
# stamm fürs Präs.-Ptz, PRÄTERITALSTAMM fürs Akt.-Ptz. Die drei Partizipien
# DEKLINIEREN (s. _PTCP_DECL) und werden separat behandelt.
#: tense → (Leitform-Schlüssel, abzustreifendes Leitsuffix, Zellen→Suffix)
_UNIV_MOODS: dict[str, tuple] = {
    "optative":     ("optative",  "sei", OrderedDict([("Opt", "sei")])),
    "subjunctive":  ("subj_as",   "lai", OrderedDict([("1sg", "lai"), ("2sg", "lai"),
                                          ("3sg", "lai"), ("1pl", "limai"), ("2pl", "litei")])),
}

# ── Partizip-Deklination (Rollout Stufe 3) ────────────────────────────────
# Die drei Partizipien sind flektierte Adjektive (docs/gramatiki.md §§2.2/2.7/
# 2.11): Präs.-Ptz wie <29> (sēnts), Akt.-Ptz wie <68> (immuns), Pass.-Ptz wie
# <69> (īmts). Die Deklinationsendungen sind — wie bei Nomina — UNIVERSELL: ein
# Set je (Partizip, Genus); der lemmaspezifische Partizipstamm entsteht durch
# Abstreifen der Mask-Nom-Sg-Endung (_PTCP_LEAD) von der attestierten Form. Die
# Endungstabellen sind aus tabula.html (P29/P68/P69) abgeleitet; betont = der
# Stamm trägt in dieser Zelle die Langstufe (steuert M/S-Marker, phonology.py).
# Die pronominalen "pnl"-Spalten (Artikel-Definitum mit stas) sind +Def und hier
# bewusst ausgenommen. tabula = Strukturquelle → Ergebnis provisional.
#: Mask-Nom-Sg-Endung je Partizip (Strip → Stamm)
_PTCP_LEAD = {"present_ptcp": "s", "active_ptcp": "uns", "passive_ptcp": "s"}
#: Leitform-Schlüssel (für _leitform) je Partizip
_PTCP_LEITKEY = {"present_ptcp": "present_p", "active_ptcp": "past_p",
                 "passive_ptcp": "passive"}
#: tabula-Deklinationsparadigma je Partizip (Schlüssel fürs geteilte Infl)
_PTCP_DECL_PAR = {"present_ptcp": "29", "active_ptcp": "68", "passive_ptcp": "69"}

#: tense → genus → OrderedDict[zelle → (endung, betont)]
_PTCP_DECL: dict[str, dict[str, "OrderedDict[str, tuple[str, bool]]"]] = {
    "present_ptcp": {  # <29> sēnts ~ sent (Mobile)
        "m": OrderedDict([("Nom sg", ("s", True)), ("Gen sg", ("is", True)),
                          ("Dat sg", ("ismu", False)), ("Akk sg", ("in", True)),
                          ("Nom pl", ("ei", True)), ("Gen pl", ("in", True)),
                          ("Dat pl", ("immans", True)), ("Akk pl", ("ins", True))]),
        "f": OrderedDict([("Nom sg", ("ī", False)), ("Gen sg", ("es", True)),
                          ("Dat sg", ("ei", True)), ("Akk sg", ("in", True)),
                          ("Nom pl", ("es", True)), ("Gen pl", ("in", True)),
                          ("Dat pl", ("jāmans", False)), ("Akk pl", ("ins", True))]),
        "n": OrderedDict([("Nom sg", ("i", True)), ("Gen sg", ("is", True)),
                          ("Dat sg", ("ismu", False)), ("Akk sg", ("i", True)),
                          ("Nom pl", ("ei", True)), ("Gen pl", ("in", True)),
                          ("Dat pl", ("immans", True)), ("Akk pl", ("ins", True))]),
    },
    "active_ptcp": {  # <68> immuns — konstanter Stamm (Baryton, keine Alternation)
        "m": OrderedDict([("Nom sg", ("uns", True)), ("Gen sg", ("ušas", True)),
                          ("Dat sg", ("ušasmu", True)), ("Akk sg", ("usin", True)),
                          ("Nom pl", ("usis", True)), ("Gen pl", ("usin", True)),
                          ("Dat pl", ("usimans", True)), ("Akk pl", ("usins", True))]),
        "f": OrderedDict([("Nom sg", ("usi", True)), ("Gen sg", ("ušas", True)),
                          ("Dat sg", ("ušai", True)), ("Akk sg", ("usin", True)),
                          ("Nom pl", ("ušas", True)), ("Gen pl", ("usin", True)),
                          ("Dat pl", ("usimans", True)), ("Akk pl", ("usins", True))]),
        "n": OrderedDict([("Nom sg", ("us", True)), ("Gen sg", ("ušas", True)),
                          ("Dat sg", ("ušasmu", True)), ("Akk sg", ("us", True)),
                          ("Nom pl", ("us", True)), ("Gen pl", ("usin", True)),
                          ("Dat pl", ("usimans", True)), ("Akk pl", ("us", True))]),
    },
    "passive_ptcp": {  # <69> īmts ~ imt (Mobile; = Adjektiv-Deklination P26-Typ)
        "m": OrderedDict([("Nom sg", ("s", True)), ("Gen sg", ("as", True)),
                          ("Dat sg", ("asmu", False)), ("Akk sg", ("an", True)),
                          ("Nom pl", ("āi", False)), ("Gen pl", ("an", True)),
                          ("Dat pl", ("ammans", False)), ("Akk pl", ("ans", True))]),
        "f": OrderedDict([("Nom sg", ("ā", False)), ("Gen sg", ("as", True)),
                          ("Dat sg", ("ai", True)), ("Akk sg", ("an", True)),
                          ("Nom pl", ("as", True)), ("Gen pl", ("an", True)),
                          ("Dat pl", ("āmans", False)), ("Akk pl", ("ans", True))]),
        "n": OrderedDict([("Nom sg", ("an", True)), ("Gen sg", ("as", True)),
                          ("Dat sg", ("asmu", False)), ("Akk sg", ("an", True)),
                          ("Nom pl", ("āi", False)), ("Gen pl", ("an", True)),
                          ("Dat pl", ("ammans", False)), ("Akk pl", ("ans", True))]),
    },
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


def _ptcp_route(e: dict):
    """Gruppenschlüssel für ein dekliniertes Partizip (geteiltes Infl pro
    Deklination+Genus) oder ``None`` für gewöhnliche Verbeinträge."""
    if e.get("gender") and e["tense"] in _PTCP_DECL:
        return ("Vp", _PTCP_DECL_PAR[e["tense"]], e["gender"])
    return None


def groups(verb_entries: list[dict]):
    """(Gruppenschlüssel, Tag-Präfix, Art, Eintrag) je Verbeintrag. Partizipien
    bekommen Art 'ptcp' und teilen ihr Infl-Lexikon pro (Deklination, Genus)."""
    for e in verb_entries:
        pkey = _ptcp_route(e)
        if pkey:
            yield pkey, VERB_POS, "ptcp", e
        else:
            yield ("V", e["paradigm"], e["tense"]), VERB_POS, "verb", e


def wl_groups(wl_entries: list[dict]):
    """Wie groups, aber mit separatem Schlüssel ('Vw', …) für Wortlisten-
    Verben, damit sie eigene Infl-Lexika bekommen (abweichende Inf-Endung).

    ``group`` überschreibt den Paradigma-Teil des Schlüssels (Imperativ wird nach
    Präsensklasse statt Paradigma gruppiert, damit das geteilte Infl uniform ist).
    Partizipien teilen — wie bei groups — ihr Infl pro (Deklination, Genus)."""
    for e in wl_entries:
        pkey = _ptcp_route(e)
        if pkey:
            yield pkey, VERB_POS, "ptcp", e
        else:
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


def ptcp_decline(par: str, lemma: str, tense: str, form: str | None) -> list[dict]:
    """Eine attestierte Mask-Nom-Sg-Partizipform → deklinierte Genus-Einträge.

    Stamm = Form minus Mask-Nom-Sg-Endung (_PTCP_LEAD), archiphonem-markiert;
    daran die universellen <29>/<68>/<69>-Endungen je Genus (_PTCP_DECL). Liste
    leer, wenn die Form fehlt oder nicht auf die erwartete Endung endet (z. B.
    Mehrwort-/Irregularform). Genutzt vom Wortlisten- UND Gold-Pfad."""
    form = _first(form)
    if not form:
        return []
    stamm = _mood_stem(form, _PTCP_LEAD[tense])
    if stamm is None:
        return []
    out: list[dict] = []
    for gender, table in _PTCP_DECL[tense].items():
        suffixe = OrderedDict(
            (cell, {"suffix": sfx, "betont": bet})
            for cell, (sfx, bet) in table.items())
        out.append({
            "paradigm": par, "lemma": lemma, "tense": tense,
            "gender": gender, "stamm": stamm, "suffixe": suffixe,
        })
    return out


def _ptcp_entries(word: str, par: str, forms: dict) -> list[dict]:
    """Deklinierte Partizip-Einträge (Präs./Akt./Pass.) eines Wortlisten-Verbs."""
    out: list[dict] = []
    for tense, lkey in _PTCP_LEITKEY.items():
        out.extend(ptcp_decline(par, word, tense, _leitform(forms, lkey)))
    return out


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
        if par in stumm:
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
            # Deklinierte Partizipien (Stufe 3): Genus im Dedup-Schlüssel.
            for pe in _ptcp_entries(word, par, forms):
                pk = (word, par, pe["tense"], pe["gender"])
                if pk not in seen:
                    seen.add(pk)
                    entries.append(pe)

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
