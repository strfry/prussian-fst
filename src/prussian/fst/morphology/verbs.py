"""Verbale Morphologie.

Verb-Einträge kommen aus data/gold/goldstandard_verben_fst.json als
{paradigm, lemma, tense, stamm, suffixe} und brauchen aktuell keine
Aufbereitung. Die reflexive Enklitik ` si` (nur P106b smeītwei) wird bei
der Emission (lexd.py) via tags.split_reflexive abgespalten und als +Refl
getaggt — Klitik = Syntax, außerhalb der Verbmorphologie.

Die Funktion `wordlist_to_verb_entries` inferiert Stämme aus Twanksta-3sg-
Formen: -tun/-twei vom Infinitiv abstreifen, finite Stämme über 3sg aus
twanksta_entries.json gewinnen, Archiphoneme erkennen.  Suppletive und
"stumme" Paradigmen (Stamm < 2 Buchstaben) werden übersprungen.

Künftiger Ausbau (Partizipien/Modi, docs/ORTHO_RULES.md §2) gehört hierher.
"""

import json
import re
from collections import OrderedDict, defaultdict
from pathlib import Path

from prussian.fst.oracle import LONG_VOWELS, fold, strip_macron
from prussian.fst.tags import split_reflexive

VERB_POS = "+V"

# Linguistische SPEC (Modi, Partizip-Deklination, Imperativ-Klassen) liegt
# ausgelagert in data/spec/verb_inflection.json — inkl. Modell-Begründung, Quelle
# und Status (_meta). Drei-Stamm-Modell (Inf-Stamm für Opt/Konj, Präsensstamm fürs
# Präs.-Ptz, Präteritalstamm fürs Akt.-Ptz); die drei Partizipien DEKLINIEREN
# (_PTCP_DECL) und werden separat behandelt.
_SPEC_DATA = json.loads(
    Path("data/spec/verb_inflection.json").read_text(encoding="utf-8"))

#: tense → (Leitform-Schlüssel, abzustreifendes Leitsuffix, Zellen→Suffix)
_UNIV_MOODS: dict[str, tuple] = {
    t: (m["leitkey"], m["lead"], OrderedDict(m["cells"]))
    for t, m in _SPEC_DATA["universal_moods"].items()
}

# Partizip-Deklination (Rollout Stufe 3): drei flektierte Adjektive (Präs.-Ptz
# <29>, Akt.-Ptz <68>, Pass.-Ptz <69>). Stamm = attestierte Form minus Mask-Nom-
# Sg-Endung (_PTCP_LEAD); Endungen + Begründung in der SPEC-JSON.
_PTCP = _SPEC_DATA["participles"]
#: Mask-Nom-Sg-Endung je Partizip (Strip → Stamm)
_PTCP_LEAD = {t: p["lead"] for t, p in _PTCP.items()}
#: Leitform-Schlüssel (für _leitform) je Partizip
_PTCP_LEITKEY = {t: p["leitkey"] for t, p in _PTCP.items()}
#: tabula-Deklinationsparadigma je Partizip (Schlüssel fürs geteilte Infl)
_PTCP_DECL_PAR = {t: p["decl_par"] for t, p in _PTCP.items()}

#: tense → genus → OrderedDict[zelle → (endung, betont)]
_PTCP_DECL: dict[str, dict[str, "OrderedDict[str, tuple[str, bool]]"]] = {
    t: {g: OrderedDict((cell, (v["suffix"], v["betont"]))
                       for cell, v in table.items())
        for g, table in p["decl"].items()}
    for t, p in _PTCP.items()
}

# Imperativ-Klassen: Reihenfolge SIGNIFIKANT (spezifisch vor generisch).
_IMP_CLASSES: list[tuple[str, tuple[str, str]]] = [
    (c["marker"], (c["2sg"], c["2pl"])) for c in _SPEC_DATA["imperative_classes"]
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
    """Gruppenschlüssel für ein dekliniertes Partizip oder ``None`` für
    gewöhnliche Verbeinträge.

    Genus ist Kongruenz (das Partizip flektiert für alle drei Genera mit
    identischem Stamm), nicht lexikalisch — daher KEINE Genus-Achse im
    Gruppenschlüssel: alle Genera teilen ein Stems+Infl je Deklination, der
    Genus sitzt allein im Zellen-Tag (ptcp_cell_tag). Fester Sub-Key 'decl'
    erhält die von build_lexd erwartete 3-Tupel-Struktur. Das Infl wird über
    die Genus-Einträge akkumuliert (lexd.add_group, lexkind=='ptcp')."""
    if e.get("gender") and e["tense"] in _PTCP_DECL:
        return ("Vp", _PTCP_DECL_PAR[e["tense"]], "decl")
    return None


# Modi auf dem Inf-Stamm (Infinitiv + Optativ + Konjunktiv) teilen je Lexem
# Stamm UND Akzentklasse → ein gemeinsames Stems+Infl-Lexikon je Paradigma
# (sub="inf_stem") statt drei nahezu identischer. Präsens+Präteritum teilen den
# Präsensstamm, aber NUR bei nicht-suppletiven Lexemen gleicher Klasse
# (sub="pres_stem"); sonst getrennt (sonst nähme der Präteritalstamm das
# Präsenssuffix an — Übergenerierung). Imperativ bleibt klassen-gruppiert
# (group=imp_*), weil sein Suffix pro Verb konditioniert ist und ein geteiltes
# Infl ihn nicht uniform aufnehmen kann.
_INF_STEM_TENSES = frozenset({"infinitive", "optative", "subjunctive"})
_PRES_STEM_TENSES = frozenset({"present", "preterite"})


def _acc_class(suffixe: dict) -> str:
    """bar / mob / na aus dem betont-Muster (Spiegel von lexd.entry_class; hier
    lokal gehalten, um den Importzyklus lexd→verbs zu vermeiden)."""
    vals = [v["betont"] for v in suffixe.values()]
    if all(vals):
        return "bar"
    if not any(vals):
        return "na"
    return "mob"


def _pres_collapsible(entries: list[dict], base_of) -> set:
    """(base, lemma)-Paare, deren Präsens UND Präteritum Stamm und Klasse teilen
    → sicher auf einen Präsensstamm zusammenzulegen. Suppletive Lexeme (präs ≠
    prät) und Klassendivergenz bleiben getrennt."""
    seen: dict = defaultdict(dict)
    for e in entries:
        if e["tense"] in _PRES_STEM_TENSES and not _ptcp_route(e):
            seen[(base_of(e), e["lemma"])][e["tense"]] = (
                e["stamm"], _acc_class(e["suffixe"]))
    return {k for k, t in seen.items()
            if t.get("present") is not None and t["present"] == t.get("preterite")}


def _verb_sub(e: dict, base, collapsible: set) -> str:
    """Lexikon-Sub-Schlüssel: kollabierte Modus-/Tempusgruppe oder roher tense."""
    t = e["tense"]
    if t in _INF_STEM_TENSES:
        return "inf_stem"
    if t in _PRES_STEM_TENSES and (base, e["lemma"]) in collapsible:
        return "pres_stem"
    return t


def _verb_groups(entries: list[dict], kind: str):
    """Routing-Kern für Gold- (kind='V') und Wortlisten-Pfad (kind='Vw').

    Partizipien bekommen Art 'ptcp' und teilen ihr Infl pro (Deklination, Genus).
    Inf-Stamm-Modi und nicht-suppletive Präsens/Präteritum werden über
    ``_verb_sub`` auf ein geteiltes Stems+Infl je Paradigma kollabiert. ``group``
    (Imperativ-Präsensklasse) überschreibt im Vw-Pfad den Paradigma-Teil."""
    def base_of(e):
        par = e.get("group", e["paradigm"]) if kind == "Vw" else e["paradigm"]
        return (kind, par)

    collapsible = _pres_collapsible(entries, base_of)
    for e in entries:
        pkey = _ptcp_route(e)
        if pkey:
            yield pkey, VERB_POS, "ptcp", e
        else:
            base = base_of(e)
            yield (kind, base[1], _verb_sub(e, base, collapsible)), \
                VERB_POS, "verb", e


def groups(verb_entries: list[dict]):
    """(Gruppenschlüssel, Tag-Präfix, Art, Eintrag) je Gold-Verbeintrag."""
    yield from _verb_groups(verb_entries, "V")


def wl_groups(wl_entries: list[dict]):
    """Wie groups, aber eigener Schlüssel ('Vw', …) für Wortlisten-Verben (eigene
    Infl-Lexika wegen abweichender Inf-Endung tun/twei)."""
    yield from _verb_groups(wl_entries, "Vw")


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
    """Inferiert finite Stämme aus Twanksta-3sg-Formen (twanksta_entries.json).

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
