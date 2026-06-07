#!/usr/bin/env python3
"""Baut einen bidirektionalen PyFoma-FST aus goldstandard.json und wordlist.json.

Erzeugt:
  1. Kanonische Giella-kompatible .lexc-Dateien (root.lexc, stems/nouns.lexc,
     affixes/nouns.lexc) und phonology.twolc — bereit fuer hfst-Port.
  2. Eine prae-aufgeloeste .lexd-Datei (nominals.lexd) fuer PyFoma-Kompilation.
  3. Den kompilierten FST (nominals.fst).

Tagset:       +N+Msc+Sg+Nom  (Giella flat-plus Format)
Marker:       %^JPal (Palatalisierung), %^VowS (Vokalkuerzung)
Archiphonem:  {A} {E} {I} {O} {U}  (Giella-Notation)
"""

import json
import unicodedata
from collections import defaultdict
from pathlib import Path

from pyfoma import lexd

# Paths are resolved relative to this script so it runs from any cwd.
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent

# Inputs (live at repo root)
GOLD = ROOT / "goldstandard.json"
WORDLIST = ROOT / "wordlist.json"

# Giella output paths (mirror lang-lav/src/fst/morphology/)
MORPH_DIR = HERE / "morphology"
STEMS_DIR = MORPH_DIR / "stems"
AFFIXES_DIR = MORPH_DIR / "affixes"
ROOT_LEXC = MORPH_DIR / "root.lexc"
STEMS_LEXC = STEMS_DIR / "nouns.lexc"
AFFIXES_LEXC = AFFIXES_DIR / "nouns.lexc"
PHON_TWOLC = MORPH_DIR / "phonology.twolc"

# PyFoma output paths
LEXDOUT = HERE / "nominals.lexd"
FSTOUT = HERE / "nominals.fst"
ATTOUT = HERE / "nominals.att"

# Vowel resolution maps
LONG = {"A": "ā", "E": "ē", "I": "ī", "O": "ō", "U": "ū"}
SHORT = {"A": "a", "E": "e", "I": "i", "O": "o", "U": "u"}

# Archiphoneme notation: raw -> Giella {X}
ARCH = {"A": "{A}", "E": "{E}", "I": "{I}", "O": "{O}", "U": "{U}"}

# Palatalization
PALATAL = {"g": "ģ", "k": "ķ", "n": "ņ", "s": "š", "t": "ţ", "z": "ž"}

VOWELS = set("aeiouāēīōūAEIOU")
LONG_VOWELS = set("āēīōū")

# Giella gender tags
GENDER_TAG = {"m": "+Msc", "f": "+Fem", "n": "+Neut"}

# wordlist gender -> goldstandard gender
WL_GENDER = {"masc": "m", "fem": "f", "neut": "n"}

# Giella cell -> tag mapping
CELL_TAG = {
    "Nom sg": "+Sg+Nom", "Nom pl": "+Pl+Nom",
    "Gen sg": "+Sg+Gen", "Gen pl": "+Pl+Gen",
    "Dat sg": "+Sg+Dat", "Dat pl": "+Pl+Dat",
    "Akk sg": "+Sg+Acc", "Akk pl": "+Pl+Acc",
}

# Adverb cell -> tag mapping
ADV_CELL_TAG = {
    "Pos": "+Pos",
    "Comp": "+Comp",
    "Superl": "+Superl",
}

# Degree/definiteness tags
DEF_TAG = "+Def"
SUPERL_TAG = "+Superl"
ADV_POS_TAG = "+Adv"

# Adjective paradigms (P9-P24 pronouns/demonstratives, P25-P31 adjectives)
ADJ_PARADIGMS = set()
for i in range(9, 32):
    ADJ_PARADIGMS.add(str(i))
ADJ_PARADIGMS |= {"30a"}


def _paradigm_base(paradigm: str) -> str:
    """Strip 'def'/'sup'/'adv' and '_suppl'/'_suppl2' suffixes."""
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
    """Return 'adv', 'def', 'sup', or '' depending on paradigm type."""
    # Check the main suffix after the base number, e.g. '25def', '25def_suppl'
    rest = paradigm
    if paradigm.endswith("_suppl") or paradigm.endswith("_suppl2"):
        rest = paradigm[:paradigm.rfind("_")]
    for kind in ("adv", "def", "sup"):
        if rest.endswith(kind):
            return kind
    return ""


def _pos(paradigm: str) -> str:
    """Return Giella POS tag (+A or +N) for a paradigm."""
    return "+A" if _paradigm_base(paradigm) in ADJ_PARADIGMS else "+N"


# Paradigms to include from wordlist (P9-P67 + sub-paradigms)
PAR_RANGE = set()
for i in range(9, 68):
    PAR_RANGE.add(str(i))
# Add known sub-paradigms
PAR_RANGE |= {"35a", "37a", "40a", "40b", "40c", "50a", "51a", "30a"}

# Paradigms with sibilant-palatalizing sub-variants: base -> a-variant
_PALA_PARADIGMS = {"40": "40a", "50": "50a", "51": "51a"}

# Suppletive adjective map: (lemma, base_paradigm) → [suppletive paradigm names]
_SUPPL_PARADIGMS: dict[tuple[str, str], list[str]] = {
    ("debīks", "25"): ["25def_suppl", "25sup_suppl", "25adv_suppl"],
    ("līkuts", "25"): ["25def_suppl2", "25sup_suppl2", "25adv_suppl2"],
    ("labs", "26"): ["26def_suppl", "26sup_suppl", "26adv_suppl", "26adv_suppl2"],
}

# Paradigm 40 sub-variant routing by stem-final consonant
_PAR40_J_CONS = set("wbpm")   # j-insertion
_PAR40_PLAIN_CONS = set("lc")  # plain endings (including buccis, dāncis)


def _last_consonant_idx(s: str) -> int | None:
    for i in range(len(s) - 1, -1, -1):
        if s[i] not in VOWELS:
            return i
    return None


def resolve_stem(stamm: str, betont: bool, palatize: bool) -> str:
    vmap = LONG if betont else SHORT
    stem = "".join(vmap.get(c, c.lower()) for c in stamm)
    if palatize and stem:
        idx = _last_consonant_idx(stem)
        if idx is not None and stem[idx] in PALATAL:
            stem = stem[:idx] + PALATAL[stem[idx]] + stem[idx + 1 :]
    return stem


def split_suffix(suffix: str) -> tuple[str, str | None]:
    """Doublette 'a/stan' -> ('a', 'stan'); 'as' -> ('as', None).

    Erster Teil = Standardfall (echtes Suffix, an den Stamm angehaengt);
    zweiter Teil = literale Vollform-Variante (Doublette).
    """
    if "/" in suffix:
        std, var = suffix.split("/", 1)
        return std, var
    return suffix, None


def _stem_to_archiphoneme(stamm: str) -> str:
    return "".join(ARCH.get(c, c.lower()) for c in stamm)


def _variant_code(betont: bool, palatize: bool) -> str:
    if betont and not palatize:
        return "str"
    elif betont and palatize:
        return "stp"
    elif not betont and palatize:
        return "wep"
    else:
        return "wek"


# ═══════════════════════════════════════════════════════════════════════════
# Wordlist processing: extract stems and detect archiphoneme
# ═══════════════════════════════════════════════════════════════════════════

def strip_macron(s: str) -> str:
    return s.translate(str.maketrans("āēīōūĀĒĪŌŪ", "aeiouAEIOU"))


def fold(s: str) -> str:
    """Skeleton without macron, diacritics, lowercase. Same as goldstandard.py."""
    s = strip_macron(s)
    s = unicodedata.normalize("NFD", s)
    return "".join(c for c in s if not unicodedata.combining(c)).lower()


def detect_archiphoneme(stem_surface: str, nom_sg_suffix: str) -> str:
    """Detect archiphoneme position from a Nom-sg surface form.

    Returns a raw stamm string (lowercase with uppercase archiphoneme letters).
    If no long vowel is detected, returns the plain folded stem.
    """
    norm = fold(stem_surface)
    # Find which vowel position(s) bear a macron in the surface form
    acc_positions = set()
    for i, ch in enumerate(stem_surface):
        if ch in LONG_VOWELS:
            # Map to position in the folded stem
            # The macron and folded stem should align position-wise
            if i < len(norm) and norm[i] in "aeiou":
                acc_positions.add(i)

    if not acc_positions:
        return norm  # no archiphoneme detectable

    # Build raw stamm: lowercase except at accented positions
    result = []
    for i, ch in enumerate(norm):
        if i in acc_positions:
            result.append(ch.upper())
        else:
            result.append(ch)
    return "".join(result)


def _route_paradigm_40(stem_end: str) -> str:
    """Route paradigm-40 word to correct sub-paradigm by stem-final."""
    if not stem_end:
        return "40"
    last = stem_end[-1]
    if last in "sz":
        return "40a"  # sibilant palatalization (s→š, z→ž)
    if last in _PAR40_J_CONS:
        return "40b"  # j-insertion (-jai, -jas, -ju, -jamans)
    if last in _PAR40_PLAIN_CONS:
        return "40c"  # plain (-ai, -as, -u, -amans)
    return "40"  # default e-type (vowel palatalization)


def _route_paradigm(par: str, stem: str) -> str:
    """Route a base paradigm to its correct sub-paradigm by stem-final."""
    if par in _PALA_PARADIGMS and stem and stem[-1] in "sz":
        return _PALA_PARADIGMS[par]
    if par == "40":
        return _route_paradigm_40(stem[-1:] if stem else "")
    return par


def _build_nom_sg_suffix_map(gs_entries: list[dict]) -> dict[tuple[str, str], str]:
    """Build (paradigm, gender) -> Nom sg suffix map from goldstandard."""
    result: dict[tuple[str, str], str] = {}
    for e in gs_entries:
        for cell, v in e["suffixe"].items():
            if cell == "Nom sg":
                result[(e["paradigm"], e["gender"])] = v["suffix"]
    return result


def _build_paradigm_suffixe_map(gs_entries: list[dict]) -> dict[tuple[str, str], dict]:
    """Build (paradigm, gender) -> full suffixe dict from goldstandard."""
    result: dict[tuple[str, str], dict] = {}
    for e in gs_entries:
        key = (e["paradigm"], e["gender"])
        if key not in result:
            # Take the first entry's suffixe for this paradigm+gender
            result[key] = e["suffixe"]
    return result


def _build_paradigm_nom_sg_map(gs_entries: list[dict]) -> dict[str, list[tuple[str, str]]]:
    """Build paradigm -> [(gender, Nom sg suffix), ...] sorted by suffix length desc."""
    result: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for e in gs_entries:
        for cell, v in e["suffixe"].items():
            if cell == "Nom sg":
                result[e["paradigm"]].append((e["gender"], v["suffix"]))
    for par in result:
        result[par].sort(key=lambda x: -len(x[1]))
    return dict(result)


def wordlist_to_entries(
    wl: list[dict],
    gs_entries: list[dict],
) -> list[dict]:
    """Convert wordlist entries to goldstandard-like format.

    For entries without gender, the gender is inferred by matching the
    word against the paradigm's Nom sg suffixes.
    """

    nom_sg_map = _build_nom_sg_suffix_map(gs_entries)
    suffixe_map = _build_paradigm_suffixe_map(gs_entries)
    par_nom_sg = _build_paradigm_nom_sg_map(gs_entries)
    # Build stamm map for suppletive paradigms
    stamm_map: dict[tuple[str, str], str] = {}
    for e in gs_entries:
        key = (e["paradigm"], e["gender"])
        if key not in stamm_map:
            stamm_map[key] = e["stamm"]

    entries: list[dict] = []
    seen: set[tuple[str, str, str]] = set()  # (lemma, paradigm, gender)

    for w in wl:
        par = w["paradigm"]
        if not par or par not in PAR_RANGE:
            continue
        word = w["word"]

        # Skip multi-word entries and entries with problematic characters
        if " " in word or "/" in word:
            continue

        wl_gender_raw = w.get("gender", "")
        wl_gender = WL_GENDER.get(wl_gender_raw, "")

        # Determine candidate (gender, nom_sg_suffix) pairs
        candidates: list[tuple[str, str]] = []
        if wl_gender:
            # Gender is known from wordlist
            nom_sg_suffix = nom_sg_map.get((par, wl_gender))
            if nom_sg_suffix:
                candidates.append((wl_gender, nom_sg_suffix))
        else:
            # Infer gender: try all Nom sg suffixes for this paradigm.
            # Only consider the longest matching suffix to avoid false
            # matches (e.g. 'is' vs 'i' for P27 masc vs fem/neut).
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

            # For paradigms with multiple genders (adjectives, pronouns),
            # generate entries for ALL genders from a single matched form.
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
                    "paradigm": routed_par,
                    "lemma": word,
                    "gender": g2,
                    "stamm": stamm,
                    "suffixe": suffixe,
                })

                # Expand adjective entries with def/sup/adv variants
                # if goldstandard templates exist for them.
                base = routed_par.rstrip("abc") if routed_par[-1] in "abc" else routed_par
                suppl_key = (word, base)
                if base in ADJ_PARADIGMS and suppl_key not in _SUPPL_PARADIGMS:
                    for pfx in ("def", "sup"):
                        variant_par = f"{base}{pfx}"
                        vsfx = suffixe_map.get((variant_par, g2))
                        if vsfx is not None:
                            vkey = (word, variant_par, g2)
                            if vkey not in seen:
                                seen.add(vkey)
                                entries.append({
                                    "paradigm": variant_par,
                                    "lemma": word,
                                    "gender": g2,
                                    "stamm": stamm,
                                    "suffixe": vsfx,
                                })
                    adv_par = f"{base}adv"
                    adv_sfx = suffixe_map.get((adv_par, ""))
                    if adv_sfx is not None:
                        akey = (word, adv_par, "")
                        if akey not in seen:
                            seen.add(akey)
                            entries.append({
                                "paradigm": adv_par,
                                "lemma": word,
                                "gender": "",
                                "stamm": stamm,
                                "suffixe": adv_sfx,
                            })

    # Post-pass: suppletive adjective expansion
    for (lemma, base_par), variant_pars in _SUPPL_PARADIGMS.items():
        for variant_par in variant_pars:
            if _paradigm_kind(variant_par) == "adv":
                vsfx = suffixe_map.get((variant_par, ""))
                if vsfx is not None:
                    akey = (lemma, variant_par, "")
                    if akey not in seen:
                        seen.add(akey)
                        entries.append({
                            "paradigm": variant_par,
                            "lemma": lemma,
                            "gender": "",
                            "stamm": stamm_map.get((variant_par, ""), ""),
                            "suffixe": vsfx,
                        })
            else:
                for g in ("m", "f", "n"):
                    vsfx = suffixe_map.get((variant_par, g))
                    if vsfx is not None:
                        vkey = (lemma, variant_par, g)
                        if vkey not in seen:
                            seen.add(vkey)
                            entries.append({
                                "paradigm": variant_par,
                                "lemma": lemma,
                                "gender": g,
                                "stamm": stamm_map.get((variant_par, g), ""),
                                "suffixe": vsfx,
                            })

    return entries


# ═══════════════════════════════════════════════════════════════════════════
# Giella canonical .lexc file generation
# ═══════════════════════════════════════════════════════════════════════════

def write_root_lexc() -> None:
    lines = []
    lines.append("Multichar_Symbols")
    lines.append(" %^VowS  %^JPal")
    lines.append(" +A  +N  +Adv  +Msc  +Fem  +Neut")
    lines.append(" +Sg  +Pl  +Nom  +Gen  +Dat  +Acc")
    lines.append(" +Def  +Superl  +Comp  +Pos")
    lines.append(" {A}  {E}  {I}  {O}  {U}")
    lines.append("")
    lines.append("LEXICON Root")
    lines.append(" Adjectives ;")
    lines.append(" Nouns ;")
    lines.append("")
    lines.append("LEXICON K")
    lines.append(" # ;")
    ROOT_LEXC.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Written {ROOT_LEXC}")


def write_stems_lexc(entries: list[dict]) -> None:
    par_gender_stems: dict[tuple[str, str], list[tuple[str, str, str]]] = defaultdict(list)

    for e in entries:
        par, g = e["paradigm"], e["gender"]
        raw_stamm = e["stamm"]
        arch_stem = _stem_to_archiphoneme(raw_stamm)
        par_gender_stems[(par, g)].append((e["lemma"], raw_stamm, arch_stem))

    lines = []
    lines.append("LEXICON Nouns")

    for (par, g) in sorted(par_gender_stems.keys(),
                           key=lambda x: (int(_paradigm_base(x[0]).rstrip("abc")) if _paradigm_base(x[0]).rstrip("abc").isdigit() else 0, x[0], x[1])):
        gtag = GENDER_TAG.get(g, "")
        pos = _pos(par)
        prefix = pos.lstrip("+")
        cont_class = f"{prefix}-P{par}-{gtag.lstrip('+').upper()}"
        for lemma, raw_stamm, arch_stem in sorted(par_gender_stems[(par, g)]):
            kind = _paradigm_kind(par)
            if kind == "adv":
                tag_prefix = f"{pos}{ADV_POS_TAG}"
            elif kind == "def":
                tag_prefix = f"{pos}{DEF_TAG}{gtag}"
            elif kind == "sup":
                tag_prefix = f"{pos}{SUPERL_TAG}{gtag}"
            else:
                tag_prefix = f"{pos}{gtag}"
            lines.append(f" {lemma}{tag_prefix}:{arch_stem} {cont_class} ;")
    lines.append("")

    STEMS_LEXC.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Written {STEMS_LEXC}")


def write_affixes_lexc(entries: list[dict]) -> None:
    par_gender_cells: dict[tuple[str, str], set[tuple[str, str, bool, bool]]] = defaultdict(set)

    for e in entries:
        par, g = e["paradigm"], e["gender"]
        for cell, v in e["suffixe"].items():
            betont = v["betont"]
            pal = v.get("palatize", False)
            # Nur der Standardteil ist als Affix darstellbar; die literale
            # Doubletten-Vollform wird ausschliesslich im kompilierten
            # nominals.lexd/FST realisiert.
            std_suffix, _variant = split_suffix(v["suffix"])
            par_gender_cells[(par, g)].add((cell, std_suffix, betont, pal))

    lines = []

    for (par, g) in sorted(par_gender_cells.keys()):
        gtag = GENDER_TAG.get(g, "")
        pos = _pos(par)
        prefix = pos.lstrip("+")
        cont_class = f"{prefix}-P{par}-{gtag.lstrip('+').upper()}"
        lines.append(f"LEXICON {cont_class}")

        for cell, suffix, betont, pal in sorted(par_gender_cells[(par, g)]):
            tag = CELL_TAG.get(cell, ADV_CELL_TAG.get(cell, ""))
            parts = []
            if pal:
                parts.append("%^JPal")
            if not betont:
                parts.append("%^VowS")
            parts.append(suffix)
            lower = "".join(parts)
            lines.append(f" {tag}:{lower} K ;")
        lines.append("")

    AFFIXES_LEXC.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Written {AFFIXES_LEXC}")


def write_phonology_twolc() -> None:
    lines = []
    lines.append("Alphabet")
    lines.append(" %^VowS:0  %^JPal:0")
    lines.append(" %>   %<")
    lines.append(" ;")
    lines.append("")

    lines.append('"Default vowel lengthening"')
    lines.append("!! **@DEFAULT_LONG@**")
    for arch, long in [("{A}", "ā"), ("{E}", "ē"), ("{I}", "ī"), ("{O}", "ō"), ("{U}", "ū")]:
        lines.append(f" {arch}:{long} ;")
    lines.append("")

    lines.append('"Vowel shortening"')
    lines.append("!! **@VOW_SHORTEN@**")
    for arch, short in [("{A}", "a"), ("{E}", "e"), ("{I}", "i"), ("{O}", "o"), ("{U}", "u")]:
        lines.append(f" {arch}:{short} <=> _  ? - %^VowS * %^VowS: ;")
    lines.append("")

    lines.append('"J-Palatalization"')
    lines.append("!! **@JPAL@**")
    for cons, pal in [("g", "ģ"), ("k", "ķ"), ("n", "ņ"), ("s", "š"), ("t", "ţ"), ("z", "ž")]:
        lines.append(f" {cons}:{pal} <=> _  %^JPal: ;")
    lines.append("")

    lines.append('"Pre-J-Palatalization"')
    lines.append("!! **@JPAL_PRE@** (if marker precedes consonant)")
    for cons, pal in [("g", "ģ"), ("k", "ķ"), ("n", "ņ"), ("s", "š"), ("t", "ţ"), ("z", "ž")]:
        lines.append(f" {cons}:{pal} <=> %^JPal: _ ;")
    lines.append("")

    PHON_TWOLC.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Written {PHON_TWOLC}")


# ═══════════════════════════════════════════════════════════════════════════
# PyFoma pre-resolved .lexd generation (+Tag format)
# ═══════════════════════════════════════════════════════════════════════════

def build_lexd(entries: list[dict]) -> str:
    """Generate pre-resolved nominals.lexd with Giella +Tag format.

    Each word gets per-variant stem forms.  Words sharing the same stem
    surface share a stem lexicon.  Inflection lexicons are shared per
    (paradigm, gender, variant).
    """
    # Shared inflection entries:  (par, g, var) -> [(tag, suffix), ...]
    infl_data: dict[tuple[str, str, str], list[tuple[str, str]]] = defaultdict(list)
    # Per-word stem variants:  (lemma, par, g, var) -> stem_surface
    word_var_stems: dict[tuple[str, str, str, str], str] = {}
    # All (par, g, var) combinations that have entries
    known_infls: set[tuple[str, str, str]] = set()
    # Literale Doubletten-Vollformen:  (upper_tag_string, surface)
    variant_forms: list[tuple[str, str]] = []

    for e in entries:
        par, g = e["paradigm"], e["gender"]
        stamm = e["stamm"]
        lemma = e["lemma"]

        for cell, v in e["suffixe"].items():
            betont: bool = v["betont"]
            pal: bool = v.get("palatize", False)
            prefix = v.get("prefix", "")
            var = _variant_code(betont, pal)
            if prefix:
                var = f"p{prefix}_{var}"
            infl_key = (par, g, var)
            known_infls.add(infl_key)

            std_suffix, variant_full = split_suffix(v["suffix"])

            stem_surface = prefix + resolve_stem(stamm, betont, pal)
            word_var_stems[(lemma, par, g, var)] = stem_surface

            is_adv = cell in ADV_CELL_TAG
            if is_adv:
                tag = ADV_CELL_TAG[cell]
            else:
                tag = CELL_TAG[cell]
            entry = (tag, std_suffix)
            if entry not in infl_data[infl_key]:
                infl_data[infl_key].append(entry)

            # Doublette: zweiter Teil ist eine literale Vollform.  Nur emittieren,
            # wenn sie zum Stamm dieses Lemmas passt — schuetzt vor faelschlich
            # geerbten Wortlisten-Lemmata (z.B. eraīns, jūss), die das gold
            # suffixe (mit der stas/kits/aīns-spezifischen Variante) kopieren.
            if variant_full is not None and (
                variant_full.startswith(resolve_stem(stamm, True, pal))
                or variant_full.startswith(resolve_stem(stamm, False, pal))
            ):
                kind = _paradigm_kind(par)
                if kind == "adv":
                    upper = f"{lemma}{_pos(par)}{ADV_POS_TAG}{tag}"
                elif kind == "def":
                    upper = f"{lemma}{_pos(par)}{DEF_TAG}{GENDER_TAG[g]}{tag}"
                elif kind == "sup":
                    upper = f"{lemma}{_pos(par)}{SUPERL_TAG}{GENDER_TAG[g]}{tag}"
                else:
                    upper = f"{lemma}{_pos(par)}{GENDER_TAG[g]}{tag}"
                variant_forms.append((upper, variant_full))

    # Group stems by (par, g, var) — one stem lexicon per inflection group.
    # This avoids O(n²) blowup from too many top-level PATTERNS lines.
    stem_lex_entries: dict[tuple[str, str, str], list[tuple[str, str, str]]] = defaultdict(list)
    for (lemma, par, g, var), stem_surface in word_var_stems.items():
        kind = _paradigm_kind(par)
        if kind == "adv":
            tag_prefix = f"{_pos(par)}{ADV_POS_TAG}"
        elif kind == "def":
            tag_prefix = f"{_pos(par)}{DEF_TAG}{GENDER_TAG[g]}"
        elif kind == "sup":
            tag_prefix = f"{_pos(par)}{SUPERL_TAG}{GENDER_TAG[g]}"
        else:
            tag_prefix = f"{_pos(par)}{GENDER_TAG.get(g, '')}"
        stem_lex_entries[(par, g, var)].append((lemma, tag_prefix, stem_surface))

    # Deduplicate
    for key in stem_lex_entries:
        stem_lex_entries[key] = sorted(set(stem_lex_entries[key]))

    lines: list[str] = []
    lines.append("PATTERNS")

    # Write pattern lines: one per (par, g, var)
    for infl_key in sorted(infl_data.keys()):
        par, g, var = infl_key
        stem_name = f"Stems_{par}_{g}_{var}"
        infl_name = f"Infl_{par}_{g}_{var}"
        lines.append(f"{stem_name} {infl_name}")

    # Doubletten-Vollformen als zusaetzliches Single-Lexikon-Pattern
    if variant_forms:
        lines.append("Variants")

    lines.append("")

    # Write Stem lexicons
    for infl_key in sorted(stem_lex_entries.keys()):
        par, g, var = infl_key
        stem_name = f"Stems_{par}_{g}_{var}"
        lines.append(f"LEXICON {stem_name}")
        for lemma, tag_prefix, stem_surface in stem_lex_entries[infl_key]:
            lines.append(f"{lemma}{tag_prefix}:{stem_surface}")
        lines.append("")

    # Write shared Infl lexicons
    for infl_key in sorted(infl_data.keys()):
        par, g, var = infl_key
        infl_name = f"Infl_{par}_{g}_{var}"
        lines.append(f"LEXICON {infl_name}")
        for tag, suffix in sorted(infl_data[infl_key]):
            lines.append(f"{tag}:{suffix}")
        lines.append("")

    # Write Variants lexicon (literale Doubletten-Vollformen)
    if variant_forms:
        lines.append("LEXICON Variants")
        for upper, surface in sorted(set(variant_forms)):
            lines.append(f"{upper}:{surface}")
        lines.append("")

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════

def main() -> None:
    gs_data = json.loads(GOLD.read_text(encoding="utf-8"))
    print(f"Loaded {len(gs_data)} goldstandard entries from {GOLD}")

    wl_data = json.loads(WORDLIST.read_text(encoding="utf-8"))
    print(f"Loaded {len(wl_data)} wordlist entries from {WORDLIST}")

    # Convert wordlist entries to goldstandard-like format
    wl_entries = wordlist_to_entries(wl_data, gs_data)
    print(f"Wordlist entries in range P9-P67: {len(wl_entries)}")

    # Combine: goldstandard first (for correct suffixe data), then wordlist
    all_entries = gs_data + wl_entries
    # Deduplicate by (lemma, paradigm, gender) — goldstandard wins
    seen: set[tuple[str, str, str]] = set()
    combined: list[dict] = []
    for e in all_entries:
        key = (e["lemma"], e["paradigm"], e["gender"])
        if key not in seen:
            seen.add(key)
            combined.append(e)
    print(f"Combined unique entries: {len(combined)}")

    # 1. Write canonical Giella files
    STEMS_DIR.mkdir(parents=True, exist_ok=True)
    AFFIXES_DIR.mkdir(parents=True, exist_ok=True)
    write_root_lexc()
    write_stems_lexc(combined)
    write_affixes_lexc(combined)
    write_phonology_twolc()

    # 2. Build pre-resolved lexd and compile
    lexd_text = build_lexd(combined)
    LEXDOUT.write_text(lexd_text, encoding="utf-8")
    print(f"\nWritten lexd to {LEXDOUT} ({len(lexd_text.splitlines())} lines)")

    fst = lexd.compile(lexd_text)
    n_states = len(fst.states)
    print(f"Compiled FST: {n_states} states")

    fst.save_att(str(ATTOUT))
    fst.save(str(FSTOUT))
    print(f"Saved {FSTOUT} and {ATTOUT}")
    print("Done.")


if __name__ == "__main__":
    main()
