"""Eintrags-Aufbereitung für den FST-Bau.

Lädt goldstandard.json und wordlist.json und liefert vereinheitlichte
Einträge {paradigm, lemma, gender, stamm, suffixe}. Übernommen aus dem
früheren fst/build_fst.py (Wortlisten-Routing, Archiphonem-Detektion);
die Stamm-Auflösung (resolve_stem) bleibt hier nur als **Orakel** für
die Validierung — der FST selbst löst Akzent/Palatalisierung über die
Regelschicht (rules.py) auf.
"""

import unicodedata
from collections import defaultdict

# Vokal-Auflösung (nur noch fürs Orakel resolve_stem)
LONG = {"A": "ā", "E": "ē", "I": "ī", "O": "ō", "U": "ū"}
SHORT = {"A": "a", "E": "e", "I": "i", "O": "o", "U": "u"}

# Palatalisierung (Mažiulis §§21–25)
PALATAL = {"g": "ģ", "k": "ķ", "n": "ņ", "s": "š", "t": "ţ", "z": "ž"}

VOWELS = set("aeiouāēīōūAEIOU")
LONG_VOWELS = set("āēīōū")

GENDER_TAG = {"m": "+Msc", "f": "+Fem", "n": "+Neut"}
WL_GENDER = {"masc": "m", "fem": "f", "neut": "n"}

CELL_TAG = {
    "Nom sg": "+Sg+Nom", "Nom pl": "+Pl+Nom",
    "Gen sg": "+Sg+Gen", "Gen pl": "+Pl+Gen",
    "Dat sg": "+Sg+Dat", "Dat pl": "+Pl+Dat",
    "Akk sg": "+Sg+Acc", "Akk pl": "+Pl+Acc",
}
ADV_CELL_TAG = {"Pos": "+Pos", "Comp": "+Comp", "Superl": "+Superl"}

TENSE_TAG = {"present": "+Prs", "preterite": "+Prt"}
PERSON_TAG = {"1sg": "+1Sg", "2sg": "+2Sg", "3sg": "+3",
              "1pl": "+1Pl", "2pl": "+2Pl"}
INF_TAG = "+Inf"

DEF_TAG = "+Def"
SUPERL_TAG = "+Superl"
ADV_POS_TAG = "+Adv"

PRON_PARADIGMS = set(str(i) for i in range(9, 21))
NUM_PARADIGMS = set(str(i) for i in range(21, 25))
ADJ_PARADIGMS = set(str(i) for i in range(25, 32)) | {"30a"}

# Wortlisten-Paradigmen P9–P67 + Unterparadigmen
PAR_RANGE = set(str(i) for i in range(9, 68))
PAR_RANGE |= {"35a", "37a", "40a", "40b", "40c", "50a", "51a", "30a"}

# Paradigmen mit sibilanten-palatalisierender Untervariante
_PALA_PARADIGMS = {"40": "40a", "50": "50a", "51": "51a"}

# Suppletive Adjektive: (lemma, basis) → suppletive Paradigmen
_SUPPL_PARADIGMS: dict[tuple[str, str], list[str]] = {
    ("debīks", "25"): ["25def_suppl", "25sup_suppl", "25adv_suppl"],
    ("līkuts", "25"): ["25def_suppl2", "25sup_suppl2", "25adv_suppl2"],
    ("labs", "26"): ["26def_suppl", "26sup_suppl", "26adv_suppl", "26adv_suppl2"],
}

# Paradigma-40-Routing nach Stammauslaut
_PAR40_J_CONS = set("wbpm")    # j-Einschub
_PAR40_PLAIN_CONS = set("lc")  # einfache Endungen


def _paradigm_base(paradigm: str) -> str:
    base = paradigm
    for sfx in ("_suppl2", "_suppl"):
        if base.endswith(sfx):
            base = base[:-len(sfx)]
            break
    for sfx in ("def", "sup", "adv"):
        if base.endswith(sfx):
            base = base[:-len(sfx)]
            break
    return base


def _paradigm_kind(paradigm: str) -> str:
    rest = paradigm
    if paradigm.endswith("_suppl") or paradigm.endswith("_suppl2"):
        rest = paradigm[:paradigm.rfind("_")]
    for kind in ("adv", "def", "sup"):
        if rest.endswith(kind):
            return kind
    return ""


def _pos(paradigm: str) -> str:
    base = _paradigm_base(paradigm)
    if base in PRON_PARADIGMS:
        return "+Pron"
    if base in NUM_PARADIGMS:
        return "+Num"
    if base in ADJ_PARADIGMS:
        return "+A"
    return "+N"


def tag_prefix(paradigm: str, gender: str) -> str:
    """POS- und Genus-Tagfolge zwischen Lemma und Zellen-Tag."""
    kind = _paradigm_kind(paradigm)
    gtag = GENDER_TAG.get(gender, "")
    pos = _pos(paradigm)
    if kind == "adv":
        return f"{pos}{ADV_POS_TAG}"
    if kind == "def":
        return f"{pos}{DEF_TAG}{gtag}"
    if kind == "sup":
        return f"{pos}{SUPERL_TAG}{gtag}"
    return f"{pos}{gtag}"


def cell_tag(cell: str) -> str:
    return ADV_CELL_TAG[cell] if cell in ADV_CELL_TAG else CELL_TAG[cell]


def _last_consonant_idx(s: str) -> int | None:
    for i in range(len(s) - 1, -1, -1):
        if s[i] not in VOWELS:
            return i
    return None


def resolve_stem(stamm: str, betont: bool, palatize: bool) -> str:
    """ORAKEL (frühere Bake-Logik): Archiphonem + Palatalisierung auflösen."""
    vmap = LONG if betont else SHORT
    stem = "".join(vmap.get(c, c.lower()) for c in stamm)
    if palatize and stem:
        idx = _last_consonant_idx(stem)
        if idx is not None and stem[idx] in PALATAL:
            stem = stem[:idx] + PALATAL[stem[idx]] + stem[idx + 1:]
    return stem


def split_suffix(suffix: str) -> tuple[str, str | None]:
    """Doublette 'a/stan' → ('a', 'stan'); 'as' → ('as', None)."""
    if "/" in suffix:
        std, var = suffix.split("/", 1)
        return std, var
    return suffix, None


def strip_macron(s: str) -> str:
    return s.translate(str.maketrans("āēīōūĀĒĪŌŪ", "aeiouAEIOU"))


def fold(s: str) -> str:
    s = strip_macron(s)
    s = unicodedata.normalize("NFD", s)
    return "".join(c for c in s if not unicodedata.combining(c)).lower()


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

                # Adjektive: def/sup/adv-Varianten ergänzen
                base = routed_par.rstrip("abc") if routed_par[-1] in "abc" else routed_par
                if base in ADJ_PARADIGMS and (word, base) not in _SUPPL_PARADIGMS:
                    for pfx in ("def", "sup"):
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
