"""Erzeugt die morphotaktische lexd-Grammatik (markierte Unterseite).

Im Gegensatz zum früheren build_fst.py wird **kein** Varianten-Kreuzprodukt
mehr ausgelöst: jeder Stamm steht genau einmal pro (Paradigma, Genus),
Archiphoneme (A E I O U) und Akzentklasse (Marker M) bleiben sichtbar,
die Endungslexika tragen Stärke- (S) und Palatalisierungsmarker (J).
Die Auflösung zur Oberfläche übernimmt rules.py.

Twanksta-Orthographievarianten (explizites Palatalisierungs-j statt
palatalisiertem Konsonanten + weicher Endung, Mažiulis §§21–25, §122
Fn54) werden als zusätzliche Endungszeilen mit V-Marker emittiert
(`+Sg+Gen:Vjas` neben `+Sg+Gen:Jas`). Der Standard-Analysator filtert
V-Pfade aus, der nachsichtige Analysator (lenient.fst) akzeptiert sie —
ersetzt den früheren aufzählenden ortho.fst.

Akzentklassen (vgl. docs/AKZENT.md):
  bar  Stamm immer lang   → Stamm literal mit Makron, keine Marker
  mob  Stamm alterniert   → Stamm archiphonemisch, Marker M; starke
                            Endungszellen (betont=false) erhalten S
  na   nicht beobachtbar  → Stamm literal; Wortlisten-Stämme mit
                            detektiertem Makron werden lang gehalten
                            (Baryton-Default — das frühere Kürzen in
                            allen Zellen widersprach der Nom-sg-Evidenz)
"""

from collections import defaultdict

from prussian.fst.entries import (
    LONG,
    cell_tag, resolve_stem, split_reflexive, split_suffix,
    tag_prefix, verb_cell_tag,
)


# ── Twanksta j-Variante einer Endung (aus dem früheren ortho_rules.py) ──

#: Vokale, die den weichen Endungsvokal-Shift auslösen (→ ja).
_SOFT_VOWELS = set("ieīē")
#: Vokale, die reinen j-Einschub bekommen (→ jV).
_HARD_VOWELS = set("aāuū")
#: Endungen ohne j-Variante (reine Vokale außer 'u', Nom-sg-Endungen).
_NO_J_VARIANT = frozenset({"is", "īs", "i", "ī", "a", "ā", "e", "ē", "ū"})


def jan_variant(suffix: str) -> str | None:
    """Standard-Endung → Twanksta-j-Variante (in→jan, es→jas, u→ju, …).

    Überspringt Endungen, die bereits j enthalten (echte j-Stämme),
    sowie reine Vokalendungen.
    """
    if not suffix or "j" in suffix or suffix in _NO_J_VARIANT:
        return None
    for i, ch in enumerate(suffix):
        if ch in _SOFT_VOWELS | _HARD_VOWELS:
            prefix, rest = suffix[:i], suffix[i:]
            if rest[0] in _SOFT_VOWELS:
                return prefix + "ja" + rest[1:]
            if rest[0] in _HARD_VOWELS:
                return prefix + "j" + rest
            return None
    return None


def entry_class(suffixe: dict) -> str:
    """bar / mob / na aus dem betont-Muster (mechanisch; vgl. accent.py)."""
    vals = [v["betont"] for v in suffixe.values()]
    if all(vals):
        return "bar"
    if not any(vals):
        return "na"
    return "mob"


def render_stem(stamm: str, cls: str) -> str:
    """Unterseiten-Stamm: archiphonemisch + M (mob) oder literal (bar/na)."""
    has_arch = any(c in "AEIOU" for c in stamm)
    if cls == "mob" and has_arch:
        return "M" + "".join(c if c in "AEIOU" else c.lower() for c in stamm)
    # bar: lang auflösen.  na: ebenfalls lang (Baryton-Default, s. Docstring).
    return "".join(LONG.get(c, c.lower()) for c in stamm)


def render_suffix(v: dict, cls: str) -> list[str]:
    """Unterseiten-Endungen: [Standard, ggf. Twanksta-j-Variante].

    Standard:  (J)(S)suffix — J palatalisiert den Stammauslaut.
    Variante:  V(S)j-suffix — explizites j, Stamm bleibt unpalatalisiert.
    """
    std, _variant = split_suffix(v["suffix"])
    s_marker = "S" if cls == "mob" and not v["betont"] else ""
    j_marker = "J" if v.get("palatize", False) else ""
    lowers = [f"{j_marker}{s_marker}{std}"]
    jvar = jan_variant(std)
    if jvar is not None:
        lowers.append(f"V{s_marker}{jvar}")
    return lowers


def _lexname(kind: str, par: str, sub: str) -> str:
    return f"{kind}_P{par}_{sub or 'x'}"


def build_lexd(entries: list[dict], verb_entries: list[dict]) -> str:
    """Nominale + verbale Einträge → lexd-Quelltext."""
    # Gruppen: (paradigm, gender) bzw. (paradigm, tense) teilen Endungslexikon
    stems: dict[tuple, list[str]] = defaultdict(list)
    infls: dict[tuple, dict[str, list[str]]] = {}
    variants: set[tuple[str, str]] = set()

    def add_group(key, lexkind, e, upper_prefix):
        cls = entry_class(e["suffixe"])
        if key not in infls:
            infl = {}
            for cell, v in e["suffixe"].items():
                if lexkind == "verb":
                    bare, refl = split_reflexive(v["suffix"])
                    if refl:
                        v = {**v, "suffix": bare}
                    tag = verb_cell_tag(e["tense"], cell, refl)
                else:
                    tag = cell_tag(cell)
                infl[tag] = render_suffix(v, cls)
            infls[key] = infl
        stem = render_stem(e["stamm"], cls)
        lines = [f"{e['lemma']}{upper_prefix}:{stem}"]
        # Stammvariante elektr- ↔ elaktr- (Prusaspira-Schreibung,
        # docs/BACKLOG.md) — über denselben V-Mechanismus wie die
        # Endungsvarianten, nur im nachsichtigen Analysator.
        if "elektr" in stem:
            lines.append(
                f"{e['lemma']}{upper_prefix}:V{stem.replace('elektr', 'elaktr')}")
        for line in lines:
            if line not in stems[key]:
                stems[key].append(line)

        # Doubletten: literale Vollformen, sofern sie zum Stamm passen
        for cell, v in e["suffixe"].items():
            _std, variant_full = split_suffix(v["suffix"])
            if variant_full is None:
                continue
            pal = v.get("palatize", False)
            if (variant_full.startswith(resolve_stem(e["stamm"], True, pal))
                    or variant_full.startswith(resolve_stem(e["stamm"], False, pal))):
                if lexkind == "verb":
                    _bare, refl = split_reflexive(v["suffix"])
                    tag = verb_cell_tag(e["tense"], cell, refl)
                else:
                    tag = cell_tag(cell)
                variants.add((f"{e['lemma']}{upper_prefix}{tag}", variant_full))

    for e in entries:
        key = ("N", e["paradigm"], e["gender"])
        add_group(key, "nominal", e, tag_prefix(e["paradigm"], e["gender"]))

    for e in verb_entries:
        key = ("V", e["paradigm"], e["tense"])
        add_group(key, "verb", e, "+V")

    # ── lexd-Text ──
    lines = ["PATTERNS"]
    for key in sorted(infls):
        kind, par, sub = key
        lines.append(f"{_lexname(f'Stems{kind}', par, sub)} "
                     f"{_lexname(f'Infl{kind}', par, sub)}")
    if variants:
        lines.append("Variants")
    lines.append("")

    for key in sorted(infls):
        kind, par, sub = key
        lines.append(f"LEXICON {_lexname(f'Stems{kind}', par, sub)}")
        lines.extend(sorted(stems[key]))
        lines.append("")
        lines.append(f"LEXICON {_lexname(f'Infl{kind}', par, sub)}")
        for tag, lowers in sorted(infls[key].items()):
            for lower in lowers:
                lines.append(f"{tag}:{lower}")
        lines.append("")

    if variants:
        lines.append("LEXICON Variants")
        for upper, surface in sorted(variants):
            lines.append(f"{upper}:{surface}")
        lines.append("")

    return "\n".join(lines)
