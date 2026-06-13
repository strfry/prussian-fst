"""Tagset und Tag-Builder (Giella-konform, ≈ root.lexc Multichar_Symbols).

POS (+N/+A/+Pron/+Num/+V), Genus, Kasus/Numerus, Tempus/Person, +Refl —
plus die Funktionen, die aus (Paradigma, Genus, Zelle) die Tag-Folge bauen.
Reine Strings; keine Morphophonologie (die liegt in phonology.py / oracle.py).
"""

GENDER_TAG = {"m": "+Msc", "f": "+Fem", "n": "+Neut"}

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

#: Enklitische Reflexivpartikel (Klitik/Syntax, kein Flexionssuffix): nur
#: P106b smeītwei trägt sie in den finiten Zellen (Gold-Suffix '… si'). Der
#: FST generiert die bare finite Form, das Lexem erhält stattdessen +Refl;
#: die Partikel 'si' gehört außerhalb der Verbmorphologie (function_words).
REFL_TAG = "+Refl"
_REFL_CLITIC = " si"

# POS-Klassifikation nach Paradigma-Nummer
PRON_PARADIGMS = set(str(i) for i in range(1, 21)) | {"30a"}
NUM_PARADIGMS = set(str(i) for i in range(21, 25))
ADJ_PARADIGMS = set(str(i) for i in range(25, 32)) | {"30a"}


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
    """POS- und Genus-Tagfolge zwischen Lemma und Zellen-Tag (nominal)."""
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


def verb_cell_tag(tense: str, cell: str, reflexive: bool = False) -> str:
    """Verbale Zellen-Tagfolge: +Inf bzw. +Prs/+Prt+Person (+Refl bei Klitik)."""
    base = INF_TAG if cell == "Inf" else f"{TENSE_TAG[tense]}{PERSON_TAG.get(cell, '')}"
    return base + (REFL_TAG if reflexive else "")


def split_suffix(suffix: str) -> tuple[str, str | None]:
    """Doublette 'a/stan' → ('a', 'stan'); 'as' → ('as', None)."""
    if "/" in suffix:
        std, var = suffix.split("/", 1)
        return std, var
    return suffix, None


def split_reflexive(suffix: str) -> tuple[str, bool]:
    """'eīja si' → ('eīja', True); 'eītwei' → ('eītwei', False)."""
    if suffix.endswith(_REFL_CLITIC):
        return suffix[:-len(_REFL_CLITIC)], True
    return suffix, False
