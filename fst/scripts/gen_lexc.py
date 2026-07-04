#!/usr/bin/env python3
"""Generate per-POS .lexc files from twanksta_entries.json.

Reads the Twanksta wordlist and outputs full-form lookup-table .lexc
files grouped by part of speech — one file per word class.
Participle forms are output as full-form entries (no stem routing).
Reflexive verbs (`` si``) get ``+Refl`` tag; the `` si`` is split off.
"""

import json
import re
from collections import defaultdict
from pathlib import Path

TWANKSTA = Path("../../data/external/twanksta_entries.json")
OUT_DIR = Path("..")

CASE_MAP = {
    "Nominative": "Nom", "Genitive": "Gen",
    "Dative": "Dat", "Accusative": "Akk",
}

GENDER_MAP = {"masc": "+Masc", "m": "+Masc",
               "fem": "+Fem", "f": "+Fem",
               "neut": "+Neut", "n": "+Neut", "": ""}

PERSON_TAGS = ["P1+Sg", "P2+Sg", "P3+Sg", "P1+Pl", "P2+Pl", "P3+Pl"]

PRONOUN_MAP = {
    "as": 0, "tū": 1,
    "tāns/tenā/tennan": 2, "tāns": 2, "tenā": 2, "tennan": 2,
    "mes": 3, "jūs": 4,
    "tenēi/tennas": 5, "tenēi": 5, "tennas": 5,
    "(tū)": 1, "(mes)": 3, "(jūs)": 4,
}

LEXICON_NAMES = {
    "noun": "Nouns",
    "adjective": "Adjectives",
    "pronoun": "Pronouns",
    "numeral": "Numerals",
    "adverb": "Adverbs",
    "preposition": "Prepositions",
    "conjunction": "Conjunctions",
    "particle": "Particles",
    "interjection": "Interjections",
}

POS_TAGS = {
    "noun": "+N",
    "adjective": "+Adj",
    "pronoun": "+Pron",
    "numeral": "+Num",
    "adverb": "+Adv",
    "preposition": "+Prp",
    "conjunction": "+Cnj",
    "particle": "+Pcl",
    "interjection": "+IJ",
}


def lexc_esc(s: str) -> str:
    s = s.replace(" ", "% ")
    s = s.replace("!", "%!")
    return s


def paradigm_int(par: str) -> int | None:
    num = ""
    for ch in par:
        if ch.isdigit():
            num += ch
        else:
            break
    return int(num) if num else None


def desc_gram(desc: str) -> str:
    """Grammatical part of the desc field (source refs ``[...]`` stripped)."""
    return re.sub(r"\[.*?\]", "", desc).strip()


def prep_gov_tags(desc: str) -> list[str]:
    """Governed-case tags for a preposition, from ``prp acc`` / ``prp dat`` desc."""
    g = desc_gram(desc)
    if not g.startswith("prp"):
        return []
    tags = []
    if re.search(r"\bacc\b", g):
        tags.append("+GovAkk")
    if re.search(r"\bdat\b", g):
        tags.append("+GovDat")
    return tags


def classify(e: dict) -> str:
    desc = e.get("desc", "").strip()
    par = e.get("paradigm", "")
    forms = e.get("forms", {})

    if "indicative" in forms:
        return "verb"

    first = desc.split()[0].lower().rstrip(",.()") if desc else ""
    if first in ("aj", "aj,"):
        return "adjective"
    if first in ("av", "av,"):
        return "adverb"
    if first in ("pn", "pn,"):
        return "pronoun"
    if first in ("crd", "crd,"):
        return "numeral"
    if first in ("ord", "ord,"):
        return "numeral"
    if first in ("prp", "prp,"):
        return "preposition"
    if first in ("ij", "ij,", "ij)"):
        return "interjection"
    if first in ("cj", "cj,"):
        return "conjunction"
    if first in ("pcl", "pcl,"):
        return "particle"
    if first in ("encl", "encl,"):
        return "particle"
    if first == "pc":
        return "adjective"

    pi = paradigm_int(par)
    if pi is not None:
        if 1 <= pi <= 20:
            return "pronoun"
        if 21 <= pi <= 24:
            return "numeral"
        if 25 <= pi <= 31:
            return "adjective"
        if 32 <= pi <= 70:
            return "noun"
        if pi >= 71:
            return "verb"

    if "declension" in forms and forms["declension"]:
        return "noun"

    return "unknown"


# ── Form extraction ──────────────────────────────────────────────

def refl_tag(word: str) -> tuple[str, str]:
    """If *word* ends with `` si``, strip it and return ``+Refl`` tag.

    Returns ``(clean_word, tag_suffix)``.
    """
    if word.endswith(" si"):
        return word[:-3], "+Refl"
    return word, ""


def strip_si(form: str) -> str:
    """Strip trailing `` si`` from a surface form."""
    if form.endswith(" si"):
        return form[:-3]
    return form


def nominal_forms(entry: dict, pos_tag: str) -> list[tuple[str, str]]:
    results = []
    for decl_key, deg_tag in [("declension", ""), ("comparative", "+Cmp"),
                              ("superlative", "+Sup")]:
        for gen_decl in entry.get("forms", {}).get(decl_key, []):
            g = gen_decl.get("gender", "masc")
            g_tag = GENDER_MAP.get(g, "")
            for case_entry in gen_decl.get("cases", []):
                c = case_entry.get("case", "")
                c_tag = CASE_MAP.get(c, c[:3])
                for num_attr, num_tag in [("singular", "Sg"), ("plural", "Pl")]:
                    form = case_entry.get(num_attr, "")
                    if form:
                        for variant in form.split(" / "):
                            if " " not in variant:
                                results.append((f"{pos_tag}{deg_tag}+{num_tag}+{c_tag}{g_tag}", variant))
    return results


def adverb_forms(entry: dict) -> list[str]:
    """Derived adverb lines (``+Adv``/``+Adv+Cmp``/``+Adv+Sup``) from the
    ``forms.adverb`` degree table of an adjective entry.

    Lemma is the positive adverb form (falls back to the entry word).
    """
    adv = entry.get("forms", {}).get("adverb")
    if not isinstance(adv, dict):
        return []
    pos_form = (adv.get("positive") or "").strip()
    lemma = pos_form or entry.get("word", "")
    if not lemma or " " in lemma:
        return []
    lines = []
    for key, deg_tag in [("positive", ""), ("comparative", "+Cmp"),
                         ("superlative", "+Sup")]:
        form = (adv.get(key) or "").strip()
        for variant in form.split(" / "):
            variant = variant.strip()
            if variant and " " not in variant:
                lines.append(f"{lexc_esc(lemma)}+Adv{deg_tag}:{lexc_esc(variant)}")
    return lines


def verb_forms(entry: dict) -> tuple[str, dict]:
    """Extract verb inflectional forms and participle full forms.

    Returns ``(base_word, {full_line: True})`` where *base_word* is
    the lemma without any `` si`` suffix.
    """
    word = entry.get("word", "")
    forms = entry.get("forms", {})
    base, refl = refl_tag(word)
    upper = lexc_esc(base)
    results = {}

    # Infinitive
    inf_form = strip_si(word)
    results[f"{upper}+V+Inf{refl}:{lexc_esc(inf_form)}"] = True

    # Indicative (present / past / perfect / future)
    for tense_entry in forms.get("indicative", []):
        tname = tense_entry.get("tense", "")
        tense = "Pres" if tname == "Present" else "Pret" if tname == "Past" else None
        if not tense:
            continue
        for sub in tense_entry.get("forms", []):
            f = sub.get("form", "").strip()
            for variant in f.split(" / "):
                f_clean = strip_si(variant.strip())
                if " " in f_clean or "\n" in f_clean:
                    continue
                idx = PRONOUN_MAP.get(sub.get("pronoun", ""))
                if idx is None:
                    continue
                results[f"{upper}+V+Ind+{tense}+{PERSON_TAGS[idx]}{refl}:{lexc_esc(f_clean)}"] = True

    # Optative (single string)
    opt = forms.get("optative")
    if isinstance(opt, str) and opt.strip():
        for variant in opt.split(" / "):
            f_clean = strip_si(variant.strip())
            if " " in f_clean or "\n" in f_clean:
                continue
            results[f"{upper}+V+Opt+P3+Sg{refl}:{lexc_esc(f_clean)}"] = True

    # Imperative
    for sub in forms.get("imperative", []):
        if isinstance(sub, dict):
            f = sub.get("form", "").strip()
            for variant in f.split(" / "):
                f_clean = strip_si(variant.strip())
                if " " in f_clean or "\n" in f_clean:
                    continue
                idx = PRONOUN_MAP.get(sub.get("pronoun", ""))
                if idx is None or idx not in (1, 4):
                    continue
                tag = "P2+Sg" if idx == 1 else "P2+Pl"
                results[f"{upper}+V+Imp+{tag}{refl}:{lexc_esc(f_clean)}"] = True

    # Subjunctive
    for sub in forms.get("subjunctive", []):
        if isinstance(sub, dict):
            f = sub.get("form", "").strip()
            for variant in f.split(" / "):
                f_clean = strip_si(variant.strip())
                if " " in f_clean or "\n" in f_clean:
                    continue
                idx = PRONOUN_MAP.get(sub.get("pronoun", ""))
                if idx is None:
                    continue
                results[f"{upper}+V+Subj+{PERSON_TAGS[idx]}{refl}:{lexc_esc(f_clean)}"] = True

    # Participle full forms (no stem extraction, no routing)
    for p in entry.get("forms", {}).get("participles", []):
        frm = p.get("form", "").strip()
        bare = strip_si(frm)
        if " " in bare:
            continue

        if bare.endswith("uns"):
            tag = "Pret"
        elif bare.endswith("nts"):
            tag = "Pres"
        elif bare.endswith("ts"):
            tag = "Pass"
        elif bare.endswith("s") and len(bare) > 3:
            tag = "Pres"
        else:
            continue

        results[f"{upper}+V+Part+{tag}+Masc+Sg+Nom{refl}:{lexc_esc(bare)}"] = True

    return base, results


# ═══════════════════════════════════════════════════════════════════
#  Main
# ═══════════════════════════════════════════════════════════════════

def main():
    raw = json.loads(TWANKSTA.read_text(encoding="utf-8"))

    by_pos = defaultdict(list)
    stats = defaultdict(int)
    verb_data = {}  # orig_word -> (base_word, {line: True})
    seen_bases = set()

    for e in raw:
        word = e.get("word", "")
        if not word or "/" in word:
            continue
        base = word[:-3] if word.endswith(" si") else word
        if " " in base:
            continue

        pos = classify(e)
        if pos == "unknown":
            stats["unknown"] += 1
            continue
        stats[pos] += 1

        if pos == "verb":
            base_w, vf = verb_forms(e)
            if vf:
                key = word
                verb_data[key] = (base_w, vf)
                seen_bases.add(base_w)
        else:
            by_pos[pos].append((word, e))

    # Derived adverbs (degree table on adjective entries) → adverbs.lexc
    derived_adverbs = []
    for pos_entries in by_pos.values():
        for _word, e in pos_entries:
            derived_adverbs.extend(adverb_forms(e))

    # ── Nominal POS files ──
    for pos in ["noun", "adjective", "pronoun", "numeral",
                "adverb", "preposition", "conjunction", "particle", "interjection"]:
        entries = by_pos.get(pos, [])
        tag = POS_TAGS[pos]
        lex_name = LEXICON_NAMES[pos]
        out_path = OUT_DIR / f"{pos}s.lexc"

        lines = [f"! {pos}s — generated from Twanksta data"]
        lines.append(f"! Source: {TWANKSTA}")
        lines.append("")
        lines.append(f"LEXICON {lex_name}")

        total = 0
        seen_bodies = set()
        invariable = pos in ("adverb", "preposition", "conjunction", "particle", "interjection")
        for word, e in entries or []:
            forms = nominal_forms(e, tag)
            if not forms:
                if pos == "preposition":
                    gov_tags = prep_gov_tags(e.get("desc", "")) or [""]
                    for gov in gov_tags:
                        body = f"{lexc_esc(word)}{tag}{gov}:{lexc_esc(word)}"
                        if body not in seen_bodies:
                            seen_bodies.add(body)
                            lines.append(f"  {body}  # ;")
                            total += 1
                elif invariable:
                    body = f"{lexc_esc(word)}{tag}:{lexc_esc(word)}"
                    if body not in seen_bodies:
                        seen_bodies.add(body)
                        lines.append(f"  {body}  # ;")
                        total += 1
                else:
                    gender = GENDER_MAP.get(e.get("gender", ""), "")
                    lines.append(f"  {lexc_esc(word)}{tag}+Sg+Nom{gender}:{lexc_esc(word)}  # ;")
                    total += 1
            else:
                for tt, form in forms:
                    lines.append(f"  {lexc_esc(word)}{tt}:{lexc_esc(form)}  # ;")
                    total += 1

        if pos == "adverb":
            for body in derived_adverbs:
                if body not in seen_bodies:
                    seen_bodies.add(body)
                    lines.append(f"  {body}  # ;")
                    total += 1

        lines.append("")
        out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"Wrote {out_path}  ({total} form entries)")

    # ── Verb file ──
    v_lines = []
    v_lines.append("! verbs — generated from Twanksta data")
    v_lines.append(f"! Source: {TWANKSTA}")
    v_lines.append("")
    v_lines.append("LEXICON Verbs")

    vstats = {"inf": 0, "pres": 0, "pret": 0, "opt": 0, "imp": 0, "subj": 0,
              "part_pres": 0, "part_past": 0, "part_pass": 0}

    for _key in sorted(verb_data):
        _base, vf = verb_data[_key]
        for line in sorted(vf):
            if "+Part+Pres+" in line:
                vstats["part_pres"] += 1
            elif "+Part+Pret+" in line:
                vstats["part_past"] += 1
            elif "+Part+Pass+" in line:
                vstats["part_pass"] += 1
            elif "+Inf:" in line:
                vstats["inf"] += 1
            elif "+Pres+" in line:
                vstats["pres"] += 1
            elif "+Pret+" in line:
                vstats["pret"] += 1
            elif "+Opt+" in line:
                vstats["opt"] += 1
            elif "+Imp+" in line:
                vstats["imp"] += 1
            elif "+Subj+" in line:
                vstats["subj"] += 1
            v_lines.append(f"  {line}  # ;")

    v_lines.append("")
    v_path = OUT_DIR / "verbs.lexc"
    v_path.write_text("\n".join(v_lines) + "\n", encoding="utf-8")
    print(f"Wrote {v_path}  ({len(v_lines)} lines)")
    print(f"  Verb stats: inf={vstats['inf']} pres={vstats['pres']} pret={vstats['pret']} "
          f"opt={vstats['opt']} imp={vstats['imp']} subj={vstats['subj']} "
          f"part_pres={vstats['part_pres']} part_past={vstats['part_past']} "
          f"part_pass={vstats['part_pass']}")

    print(f"\nStats by POS: {dict(sorted((k,v) for k,v in stats.items() if k != 'unknown'))}")
    print(f"Skipped (↑-refs/unclassified): {stats.get('unknown', 0)}")
    print(f"Total entries: {sum(stats.values()) + len(verb_data)}")


if __name__ == "__main__":
    main()
