"""Nominale Morphologie (Nomen, Adjektiv, Pronomen, Numerale).

Diese Wortarten teilen die Kasus-/Numerus-/Genus-Maschinerie und bleiben
darum zusammen (anders als in GiellaLT, wo jede lexc handgeschrieben ist).
Hier: Paradigma-Routing, Archiphonem-Detektion, Wortlisten-Aufbereitung und
Suppletiv-/Steigerungs-Varianten — die Stamm-/Endungs-Emission selbst liegt
in lexd.py.
"""

from collections import defaultdict

from prussian.fst.oracle import LONG_VOWELS, fold, strip_macron
from prussian.fst.tags import ADJ_PARADIGMS, _paradigm_kind, tag_prefix

WL_GENDER = {"masc": "m", "fem": "f", "neut": "n"}

# Wortlisten-Paradigmen P9–P67 + Unterparadigmen
PAR_RANGE = set(str(i) for i in range(9, 68))
PAR_RANGE |= {"35a", "37a", "40a", "40b", "40c", "50a", "51a", "30a"}

# Paradigmen mit sibilanten-palatalisierender Untervariante
_PALA_PARADIGMS = {"40": "40a", "50": "50a", "51": "51a"}

# Suppletive Adjektive: (lemma, basis) → suppletive Paradigmen.
# NB: Laut Lehrer (HANDOFF_allomorphie_steigerung.md) deklinieren die Suppletiv-
# Komparative wie normale P26-Positive (māisess/waln-/maz-/mūises-), nicht wie der
# māldaisis-Typ — die endgültige Modellierung steht noch aus; Schlüssel hier nur
# auf die comp-Benennung gezogen.
_SUPPL_PARADIGMS: dict[tuple[str, str], list[str]] = {
    ("debīks", "25"): ["25comp_suppl", "25sup_suppl", "25adv_suppl"],
    ("līkuts", "25"): ["25comp_suppl2", "25sup_suppl2", "25adv_suppl2"],
    ("labs", "26"): ["26comp_suppl", "26sup_suppl", "26adv_suppl", "26adv_suppl2"],
}

# Paradigma-40-Routing nach Stammauslaut
_PAR40_J_CONS = set("wbpm")    # j-Einschub
_PAR40_PLAIN_CONS = set("lc")  # einfache Endungen


def detect_archiphoneme(stem_surface: str, nom_sg_suffix: str) -> str:
    """Archiphonem-Positionen (Makron in der Nom-sg-Oberfläche) markieren."""
    norm = fold(stem_surface)
    acc_positions = set()
    for i, ch in enumerate(stem_surface):
        if ch in LONG_VOWELS:
            if i < len(norm) and norm[i] in "aeiou":
                acc_positions.add(i)
    if not acc_positions:
        return stem_surface
    result = []
    for i, ch in enumerate(stem_surface):
        if i in acc_positions:
            result.append(strip_macron(ch).upper())
        else:
            result.append(ch)
    return "".join(result)


def _route_paradigm_40(stem_end: str) -> str:
    if not stem_end:
        return "40"
    last = stem_end[-1]
    if last in "sz":
        return "40a"
    if last in _PAR40_J_CONS:
        return "40b"
    if last in _PAR40_PLAIN_CONS:
        return "40c"
    return "40"


def _route_paradigm(par: str, stem: str) -> str:
    if par in _PALA_PARADIGMS and stem and stem[-1] in "sz":
        return _PALA_PARADIGMS[par]
    if par == "40":
        return _route_paradigm_40(stem[-1:] if stem else "")
    return par


def _build_paradigm_suffixe_map(gs_entries: list[dict]) -> dict[tuple[str, str], dict]:
    result: dict[tuple[str, str], dict] = {}
    for e in gs_entries:
        key = (e["paradigm"], e["gender"])
        if key not in result:
            result[key] = e["suffixe"]
    return result


def _build_paradigm_nom_sg_map(gs_entries: list[dict]) -> dict[str, list[tuple[str, str]]]:
    result: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for e in gs_entries:
        for cell, v in e["suffixe"].items():
            if cell == "Nom sg":
                result[e["paradigm"]].append((e["gender"], v["suffix"]))
    for par in result:
        result[par].sort(key=lambda x: -len(x[1]))
    return dict(result)


def _build_nom_sg_suffix_map(gs_entries: list[dict]) -> dict[tuple[str, str], str]:
    result: dict[tuple[str, str], str] = {}
    for e in gs_entries:
        for cell, v in e["suffixe"].items():
            if cell == "Nom sg":
                result[(e["paradigm"], e["gender"])] = v["suffix"]
    return result


def wordlist_to_entries(wl: list[dict], gs_entries: list[dict]) -> list[dict]:
    """Wortlisten-Einträge ins Goldstandard-Format überführen (mit
    Genus-Inferenz über Nom-sg-Suffixe und Paradigma-Routing)."""
    nom_sg_map = _build_nom_sg_suffix_map(gs_entries)
    suffixe_map = _build_paradigm_suffixe_map(gs_entries)
    par_nom_sg = _build_paradigm_nom_sg_map(gs_entries)
    stamm_map: dict[tuple[str, str], str] = {}
    for e in gs_entries:
        key = (e["paradigm"], e["gender"])
        if key not in stamm_map:
            stamm_map[key] = e["stamm"]

    entries: list[dict] = []
    seen: set[tuple[str, str, str]] = set()

    for w in wl:
        par = w["paradigm"]
        if not par or par not in PAR_RANGE:
            continue
        word = w["word"]
        if " " in word or "/" in word:
            continue

        wl_gender = WL_GENDER.get(w.get("gender", ""), "")

        candidates: list[tuple[str, str]] = []
        if wl_gender:
            nom_sg_suffix = nom_sg_map.get((par, wl_gender))
            if nom_sg_suffix:
                candidates.append((wl_gender, nom_sg_suffix))
        else:
            best_len = 0
            for g, sfx in par_nom_sg.get(par, []):
                if word.endswith(sfx) and len(word) > len(sfx):
                    if len(sfx) > best_len:
                        best_len = len(sfx)
                        candidates = [(g, sfx)]
                    elif len(sfx) == best_len:
                        candidates.append((g, sfx))

        for g, nom_sg_suffix in candidates:
            stem_surface = word[:-len(nom_sg_suffix)]

            available_genders = {_g for _g, _ in par_nom_sg.get(par, [])}
            if not wl_gender and len(available_genders) > 1:
                target_genders = available_genders
            else:
                target_genders = {g}

            for g2 in target_genders:
                routed_par = _route_paradigm(par, stem_surface)
                suffixe = suffixe_map.get((routed_par, g2))
                if suffixe is None:
                    continue

                stamm = detect_archiphoneme(stem_surface, nom_sg_suffix)

                key = (word, routed_par, g2)
                if key in seen:
                    continue
                seen.add(key)
                entries.append({
                    "paradigm": routed_par, "lemma": word, "gender": g2,
                    "stamm": stamm, "suffixe": suffixe,
                })

                # Adjektive: comp/sup/adv-Varianten ergänzen
                base = routed_par.rstrip("abc") if routed_par[-1] in "abc" else routed_par
                if base in ADJ_PARADIGMS and (word, base) not in _SUPPL_PARADIGMS:
                    for pfx in ("comp", "sup"):
                        variant_par = f"{base}{pfx}"
                        vsfx = suffixe_map.get((variant_par, g2))
                        if vsfx is not None:
                            vkey = (word, variant_par, g2)
                            if vkey not in seen:
                                seen.add(vkey)
                                entries.append({
                                    "paradigm": variant_par, "lemma": word,
                                    "gender": g2, "stamm": stamm,
                                    "suffixe": vsfx,
                                })
                    adv_par = f"{base}adv"
                    adv_sfx = suffixe_map.get((adv_par, ""))
                    if adv_sfx is not None:
                        akey = (word, adv_par, "")
                        if akey not in seen:
                            seen.add(akey)
                            entries.append({
                                "paradigm": adv_par, "lemma": word,
                                "gender": "", "stamm": stamm,
                                "suffixe": adv_sfx,
                            })

    # Suppletive Adjektive
    for (lemma, _base_par), variant_pars in _SUPPL_PARADIGMS.items():
        for variant_par in variant_pars:
            genders = [""] if _paradigm_kind(variant_par) == "adv" else ["m", "f", "n"]
            for g in genders:
                vsfx = suffixe_map.get((variant_par, g))
                if vsfx is None:
                    continue
                vkey = (lemma, variant_par, g)
                if vkey not in seen:
                    seen.add(vkey)
                    entries.append({
                        "paradigm": variant_par, "lemma": lemma, "gender": g,
                        "stamm": stamm_map.get((variant_par, g), ""),
                        "suffixe": vsfx,
                    })

    return entries


def combine_entries(gs_entries: list[dict], wl_entries: list[dict]) -> list[dict]:
    """Goldstandard zuerst (gewinnt bei Duplikaten), dann Wortliste."""
    seen: set[tuple[str, str, str]] = set()
    combined: list[dict] = []
    for e in gs_entries + wl_entries:
        key = (e["lemma"], e["paradigm"], e["gender"])
        if key not in seen:
            seen.add(key)
            combined.append(e)
    return combined


def groups(entries: list[dict]):
    """(Gruppenschlüssel, Tag-Präfix, 'nominal', Eintrag) je Nominaleintrag."""
    for e in entries:
        key = ("N", e["paradigm"], e["gender"])
        yield key, tag_prefix(e["paradigm"], e["gender"]), "nominal", e
