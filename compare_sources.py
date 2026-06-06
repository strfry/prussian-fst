#!/usr/bin/env python3
"""Generate side-by-side HTML comparison of tabula, prusaspira, twanksta with gender breakdown."""
import json, re, unicodedata
from pathlib import Path
from collections import OrderedDict, Counter

GENDER_MAP = {"masc": "m", "fem": "f", "neut": "n", "": "", "m/f": "m", "m/f/n": "m"}
def norm_gender(g):
    return GENDER_MAP.get(g.strip().lower(), g.strip())

TABULA = Path("tabula.html")
PRUSASPIRA = Path("prusaspira")
TWANKSTA = Path("twanksta")
OUT = Path("vergleich.html")

CASES = ["Nom", "Gen", "Dat", "Akk"]
CASE_PRU = {"Nom": "N\u014dm", "Gen": "G\u0113n", "Dat": "D\u0101t", "Akk": "Akk"}
PRU_CASE_LOOKUP = {v: k for k, v in CASE_PRU.items()}
NUMS = ["sg", "pl"]

def strip_dia(s):
    nfkd = unicodedata.normalize("NFKD", s)
    return "".join(c for c in nfkd if not unicodedata.combining(c))

def norm(s):
    return strip_dia(s).lower().replace("\u0155", "r").replace("\u0137", "k").replace("\u013c", "l").replace("\u0146", "n")

# ── Tabula ───────────────────────────────────────────────
def load_tabula():
    html = TABULA.read_text(encoding="utf-8")
    out = {}
    for m in re.finditer(r"<p[^>]*>(.*?)</p>", html, re.DOTALL):
        text = re.sub(r"<[^>]*>", "", m.group(1))
        text = text.replace("&nbsp;", " ").replace("&ndash;", "-").replace("\u2013", "-")
        text = " ".join(text.split())
        if len(text) < 3:
            continue
        mm = re.match(r"^(\d+[a-z]?)\s+([mfn/]+)?\s*:?\s*(.*)", text)
        if not mm:
            continue
        num = mm.group(1)
        gender = mm.group(2) or ""
        rest = mm.group(3)
        if rest.startswith("pnl"):
            continue
        # Expand multi-gender entries (e.g. "m/f" -> m and f) to avoid losing forms
        expanded = gender.split("/") if "/" in gender else [gender]
        for eg in expanded:
            out.setdefault(num, []).append({"gender": eg, "text": rest, "type": "pnl" if rest.startswith("pnl") else "normal"})
    return out

def parse_tabula_decl(text):
    """Parse a tabula declension string into {(case,num): form}."""
    toks = text.split()
    if not toks:
        return None
    if toks[0] == "sg/pl":
        vals = toks[1:5] if len(toks) >= 5 else []
        if len(vals) < 4:
            return None
        sg = pl = vals
    elif toks[0] == "sg" and "pl" in toks:
        i = toks.index("pl")
        sg = toks[1:i][:4]
        pl = toks[i + 1:][:4]
        if len(sg) < 4 or len(pl) < 4:
            return None
    else:
        # No sg/pl marker: treat as same for sg and pl
        vals = toks[:4]
        if len(vals) < 4:
            return None
        sg = pl = vals
    d = {}
    for c, s, p in zip(CASES, sg, pl):
        d[(c, "sg")] = s
        d[(c, "pl")] = p
    return d

# ── Prusaspira ───────────────────────────────────────────
def detect_prusaspira_genders(lines):
    """Detect gender column structure from prusaspira header lines.
    Returns (gender_list, ng) where ng is the number of value slots per case.
    Only considers lines before the second prūsiskai lemma (first paradigm only)."""
    prusiskai_indices = [i for i, l in enumerate(lines) if re.search(r"\bpr\u016bsiskai:\s", l)]
    end = prusiskai_indices[1] if len(prusiskai_indices) >= 2 else len(lines)

    # 1) Scan standalone gender header lines (m sg / m pl etc.) before case lines
    # Stop at the first case line or section header to avoid picking up pronominal headers.
    # Skip leading case lines that are left over from an inline prūsiskai on the previous block.
    header_parts = []
    in_header = False
    for l in lines[:end]:
        s = l.strip()
        if re.match(r'^(N\u014dm|G\u0113n|D\u0101t|Akk):', s):
            if not header_parts and not in_header:
                continue  # skip leftover case line from inline prūsiskai
            break
        if re.match(r'^(Pr\u014dnomin\u0101las|K\u014dmparatiwan|Superlat\u012bwan|Adjakt\u012bwan|Adwerban)', s, re.I):
            break
        if re.match(r'^[mfn]\s+(?:sg|pl)', s):
            in_header = True
            header_parts.append(s)
        elif in_header and not s:
            break
        elif in_header:
            break

    # 2) Check the first prūsiskai lemma line for trailing gender info (e.g. "m pl  f pl")
    #    Only consider tokens after the last `]` (after the reference bracket),
    #    to avoid picking up grammatical annotation tags like "sg m" from "1 SG NOM sg m".
    if prusiskai_indices:
        lemma_line = lines[prusiskai_indices[0]]
        # Find text after the last `]`
        after_ref = lemma_line.split("]")[-1] if "]" in lemma_line else lemma_line
        parts = after_ref.split()
        spec = []
        for p in reversed(parts):
            if p in ("sg", "pl"):
                spec.insert(0, p)
            elif p in ("m", "f", "n") and len(spec) > 0:
                spec.insert(0, p)
            elif spec:
                break
        if spec:
            # Validate: first token must be gender, second must be number (if spec has ≥2)
            if not (spec and spec[0] in ("m", "f", "n") and (len(spec) == 1 or spec[1] in ("sg", "pl"))):
                spec = []
        if spec:
            # Normalize shorthand: ["f", "sg", "pl"] → ["f", "sg", "f", "pl"]
            expanded = []
            i = 0
            while i < len(spec):
                t = spec[i]
                if t in ("m", "f", "n") and i + 2 < len(spec) and spec[i+1] in ("sg", "pl") and spec[i+2] not in ("m", "f", "n") and spec[i+2] in ("sg", "pl"):
                    expanded.extend([t, spec[i+1], t, spec[i+2]])
                    i += 3
                else:
                    expanded.append(t)
                    i += 1
            header_parts.append(" ".join(expanded))

    # Merge: standalone header lines
    all_tokens = []
    if header_parts:
        full = "  ".join(header_parts)
        all_tokens.extend(full.split())

    # Count sg/pl to determine ng (number of value slots per case)
    num_tokens = [t for t in all_tokens if t in ("sg", "pl")]
    ng = len(num_tokens) if num_tokens else 0

    seen = set()
    merged = []
    for t in all_tokens:
        if t in ("m", "f", "n") and t not in seen:
            seen.add(t)
            merged.append(t)
    if merged:
        return merged, ng

    # 3) Fallback: any gender tokens anywhere in first paradigm
    for l in lines[:end]:
        s = l.strip()
        tokens = s.split()
        genders = [t for t in tokens if t in ("m", "f", "n")]
        if genders:
            return genders, 0
    return None

def _parse_one_paradigm(lines, start, end):
    """Parse a single paradigm within line range [start, end). Returns {gender: {(case,num): form}} or None."""
    lines_slice = lines[start:end]
    detected = detect_prusaspira_genders(lines_slice)
    if detected:
        genders, ng = detected
    else:
        genders, ng = None, 0

    # Collect case lines (handling continuation lines for n forms)
    case_lines = {}
    skip_section = False
    for i, line in enumerate(lines_slice):
        s = line.strip()
        ls = s.lower()
        if any(x in ls for x in ["pr\u014dnomin\u0101las", "k\u014dmparatiwan", "superlat\u012bwan", "adjakt\u012bwan", "adwerban"]):
            skip_section = True
        if skip_section:
            continue
        mm = re.match(r"^(N\u014dm|G\u0113n|D\u0101t|Akk):\s+(.*)", s)
        if not mm:
            continue
        case_pru = mm.group(1)
        case_en = PRU_CASE_LOOKUP.get(case_pru)
        if not case_en:
            continue
        rest = mm.group(2).split("pr\u016bsiskai:")[0]
        vals = rest.split()
        # If this case was already seen, only replace if we get more values (closer to ng)
        if case_en in case_lines:
            if len(vals) <= len(case_lines[case_en]):
                continue
        case_lines[case_en] = vals
        # Check next line(s) for continuation (n forms without case marker)
        j = i + 1
        while j < len(lines_slice):
            ns = lines_slice[j].strip()
            if not ns:
                j += 1
                continue
            if re.match(r"^(N\u014dm|G\u0113n|D\u0101t|Akk):", ns):
                break
            if re.match(r"^[mfn]\s+(?:sg|pl)", ns) or ns.startswith("pr\u016bsiskai:"):
                break
            vals.extend(ns.split())
            break
        case_lines[case_en] = vals

    if not case_lines:
        return None

    # Determine gender structure
    if ng == 6:
        result = {"m": {}, "f": {}, "n": {}}
        for c in CASES:
            vals = case_lines.get(c, [])
            if len(vals) >= 6:
                for i, g in enumerate(["m", "m", "f", "f", "n", "n"]):
                    n = "sg" if i % 2 == 0 else "pl"
                    result[g][(c, n)] = vals[i]
            elif len(vals) >= 4:
                for i, g in enumerate(["m", "m", "f", "f"]):
                    n = "sg" if i % 2 == 0 else "pl"
                    result[g][(c, n)] = vals[i]
        return result
    elif ng == 4:
        result = {"m": {}, "f": {}}
        for c in CASES:
            vals = case_lines.get(c, [])
            if len(vals) >= 4:
                for i, g in enumerate(["m", "m", "f", "f"]):
                    n = "sg" if i % 2 == 0 else "pl"
                    result[g][(c, n)] = vals[i]
        return result
    elif ng == 3:
        num = "pl" if re.search(r"\b[mn]\s+pl\b", "  ".join(lines_slice[:30])) else "sg"
        result = {"m": {}, "f": {}, "n": {}}
        for c in CASES:
            vals = case_lines.get(c, [])
            if len(vals) >= 3:
                for i, g in enumerate(["m", "f", "n"]):
                    result[g][(c, num)] = vals[i]
        return result
    else:
        head = next((l for l in lines_slice if re.search(r"\bpr\u016bsiskai:\s", l.strip())), "")
        gm = re.search(r'\b([mfn])\s+sg\s+pl', head)
        gender = gm.group(1) if gm else ""
        result = {gender: {}}
        for c in CASES:
            vals = case_lines.get(c, [])
            if len(vals) >= 1:
                result[gender][(c, "sg")] = vals[0]
            if len(vals) >= 2:
                result[gender][(c, "pl")] = vals[1]
        return result


def parse_prusaspira_multi(num, lemma):
    fp = PRUSASPIRA / f"{num}_{lemma}.txt"
    if not fp.exists():
        return None
    lines = fp.read_text(encoding="utf-8").splitlines()

    # Find all prūsiskai lemma boundaries
    prusiskai_indices = [i for i, l in enumerate(lines) if re.search(r"\bpr\u016bsiskai:\s", l)]
    if not prusiskai_indices:
        return _parse_one_paradigm(lines, 0, len(lines))

    # Parse each paradigm and pick the best match
    def extract_lemma_word(line):
        m = re.search(r"pr\u016bsiskai:\s+(\S+)", line)
        return m.group(1) if m else ""

    def lemma_score(found_lemma):
        """Score how well a found lemma matches the expected one (0–110)."""
        if not found_lemma:
            return 0
        # Exact (diacritic-sensitive) match is always best
        if found_lemma.lower() == lemma.lower():
            return 110
        fn = norm(found_lemma)
        en = norm(lemma)
        if fn == en:
            return 100
        # Accept prefix match only if expected is a prefix of found
        # AND the extra part looks like a derivational suffix (≤ 6 chars)
        if fn.startswith(en) and len(fn) - len(en) <= 6:
            return 80
        return 0

    best = None
    best_score = -1
    best_richness = -1
    boundaries = prusiskai_indices + [len(lines)]
    for pi in range(len(boundaries) - 1):
        s = boundaries[pi]
        e = boundaries[pi + 1]
        res = _parse_one_paradigm(lines, s, e)
        if res:
            found_lemma = extract_lemma_word(lines[s])
            lscore = lemma_score(found_lemma)
            richness = sum(len(forms) for forms in res.values())
            if lscore > best_score or (lscore == best_score and richness > best_richness):
                best = res
                best_score = lscore
                best_richness = richness
    # Merge gender-complementary siblings that share the same stem AND meaning.
    # This handles cases like pekūri (f) + pekūris (m) where both are attested
    # as gender pairs of the same noun. Only triggered when the sibling's
    # English translation matches the best lemma's translation.
    if best and best_score >= 80:
        best_genders = set(best)
        en = norm(lemma)
        merged = dict(best)
        # Get English meaning of the best lemma
        def get_engl(line):
            m = re.search(r"\u0113ngliskai:\s*(.+?)\s*\[", line)
            return norm(m.group(1)) if m else ""
        best_engl = get_engl(lines[boundaries[0]])
        for pi in range(len(boundaries) - 1):
            s = boundaries[pi]
            e = boundaries[pi + 1]
            res = _parse_one_paradigm(lines, s, e)
            if not res or res is best:
                continue
            found_lemma = extract_lemma_word(lines[s])
            if lemma_score(found_lemma) < 80:
                continue
            genders = set(res)
            if not genders - best_genders:
                continue
            fn = norm(found_lemma)
            if not (fn == en or (fn.startswith(en) and len(fn) - len(en) <= 1)):
                continue
            ls = lines[s] if s < len(lines) else ""
            if re.search(r"\b(GEN ATTR|AV|PN|ATTRIBUTIV|POSTPOSITION)\b", ls, re.I):
                continue
            # Only merge if the English translation matches the best lemma
            # (same meaning → same word, different gender).
            # Strip trailing gender marker (f/m/n) from English for comparison.
            def strip_gender(e):
                return re.sub(r"\s+[fm]\s*$", "", e).strip()
            sibling_engl = get_engl(ls)
            if sibling_engl and strip_gender(sibling_engl) != strip_gender(best_engl):
                continue
            for g, forms in res.items():
                if g not in merged:
                    merged[g] = forms
        if len(merged) > len(best):
            return merged
    return best

# ── Twanksta ────────────────────────────────────────────
def parse_twanksta_multi(num, lemma, tabula_entries=None):
    fp = TWANKSTA / f"{num}_{lemma}" / "lemma.json"
    if not fp.exists():
        return None
    data = json.loads(fp.read_bytes())
    if not data:
        return None
    if isinstance(data, dict):
        entries = data.get("entries", [])
    elif isinstance(data, list):
        entries = data
    else:
        return None
    result = {}
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        gender = entry.get("gender", "")
        forms = entry.get("forms", {})
        decl = forms.get("declension", [])
        if not decl and entry.get("paradigm") and tabula_entries:
            # Fallback: synthesize forms from tabula paradigm
            for te in tabula_entries:
                tab_forms = parse_tabula_decl(te["text"])
                if tab_forms:
                    g = norm_gender(te["gender"])
                    if g not in result:
                        result[g] = {}
                    for key, val in tab_forms.items():
                        if val:
                            result[g][key] = val
        seen_genders = set()
        for g in decl:
            g_gender = g.get("gender", gender)
            gk = norm_gender(g_gender) if g_gender else ""
            if gk in seen_genders:
                continue
            seen_genders.add(gk)
            for c in g.get("cases", []):
                cn = c.get("case", "")
                abbr = {"Nominative": "Nom", "Genitive": "Gen", "Dative": "Dat", "Accusative": "Akk"}.get(cn)
                if not abbr:
                    continue
                sg_val = c.get("singular", "").strip()
                pl_val = c.get("plural", "").strip()
                if gk not in result:
                    result[gk] = {}
                if sg_val:
                    result[gk][(abbr, "sg")] = sg_val
                if pl_val:
                    result[gk][(abbr, "pl")] = pl_val
    return result if result else None

# ── Collect all paradigms ────────────────────────────────
tab = load_tabula()
pairs = []
for fp in sorted(PRUSASPIRA.glob("*.txt")):
    if fp.name.startswith("_"):
        continue
    m = re.match(r"(\d+[a-z]?)_(.+)\.txt$", fp.name)
    if m:
        pairs.append((m.group(1), m.group(2)))

def cell(val, css_class):
    if not val:
        return '<td class="empty">-</td>'
    if css_class == "diff":
        return '<td class="diff">%s</td>' % val
    if css_class == "partial":
        return '<td class="partial">%s</td>' % val
    return "<td>%s</td>" % val

def get_variants(val):
    if not val:
        return set()
    return {norm(p) for p in re.split(r"\s*/\s*", val) if p.strip()}

rows_html = []
for num, lemma in sorted(pairs, key=lambda x: (int(x[0].rstrip("abc")), x[0])):
    tab_entries = tab.get(num, [])
    pru_data = parse_prusaspira_multi(num, lemma) or {}
    twa_data = parse_twanksta_multi(num, lemma, tab_entries) or {}

    # Collect all genders across sources
    all_genders = OrderedDict()
    for te in tab_entries:
        g = norm_gender(te["gender"])
        tab_forms = parse_tabula_decl(te["text"])
        if tab_forms:
            all_genders.setdefault(g, {}).setdefault("tabula", tab_forms)
    for g, forms in pru_data.items():
        all_genders.setdefault(g, {}).setdefault("prusaspira", forms)
    for g, forms in twa_data.items():
        all_genders.setdefault(g, {}).setdefault("twanksta", forms)

    if not all_genders:
        continue

    # Merge empty-gender twanksta data into all existing gender rows
    if "" in all_genders and "twanksta" in all_genders[""]:
        empty_twa = all_genders.pop("").pop("twanksta")
        for g, sources in all_genders.items():
            if "twanksta" not in sources:
                sources["twanksta"] = empty_twa

    r = '<tr class="paradigm-header"><td colspan="7"><b>%s %s</b></td></tr>\n' % (num, lemma)
    for g, sources in all_genders.items():
        gdisp = g if g else "-"
        # Check if tabula has pnl for this gender too
        has_pnl = any(te["gender"] == g and te["type"] == "pnl" for te in tab_entries)
        glabel = "%s %s" % (num, gdisp) if gdisp else num

        # Detect pl-only paradigms: suppress tabula sg if other sources only have pl
        pru_has_sg = any("sg" in k for k in sources.get("prusaspira", {}))
        twa_has_sg = any("sg" in k for k in sources.get("twanksta", {}))
        pru_has_pl = any("pl" in k for k in sources.get("prusaspira", {}))
        twa_has_pl = any("pl" in k for k in sources.get("twanksta", {}))
        pl_only = (pru_has_pl or twa_has_pl) and not pru_has_sg and not twa_has_sg

        for c in CASES:
            for n in NUMS:
                if pl_only and n == "sg":
                    continue
                ta = sources.get("tabula", {}).get((c, n), "")
                pr = sources.get("prusaspira", {}).get((c, n), "")
                tw = sources.get("twanksta", {}).get((c, n), "")

                ta_vars = get_variants(ta)
                pr_vars = get_variants(pr)
                tw_vars = get_variants(tw)

                # Count each variant across all sources
                all_variants = []
                for vs in [ta_vars, pr_vars, tw_vars]:
                    all_variants.extend(vs)
                majority_variants = {v for v, c in Counter(all_variants).items() if c >= 2}

                def cell_class(val, varset):
                    if not val:
                        return "empty"
                    if not majority_variants:
                        return ""
                    shared = varset & majority_variants
                    if not shared:
                        return "diff"
                    if varset.issubset(majority_variants):
                        return ""
                    return "partial"

                r += "<tr><td>%s %s %s</td>%s%s%s</tr>\n" % (
                    gdisp, c, n,
                    cell(ta, cell_class(ta, ta_vars)),
                    cell(pr, cell_class(pr, pr_vars)),
                    cell(tw, cell_class(tw, tw_vars)),
                )
    rows_html.append(r)

TPL = """<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="utf-8">
<title>Vergleich: tabula / prusaspira / twanksta</title>
<style>
body { font-family: sans-serif; margin: 1rem; }
table { border-collapse: collapse; width: 100%%; }
th, td { border: 1px solid #ccc; padding: 4px 8px; text-align: left; vertical-align: top; white-space: nowrap; }
th { background: #eee; position: sticky; top: 0; }
.paradigm-header td { background: #ddeeff; font-weight: bold; font-size: 1.1em; padding: 8px; }
.diff { background: #ffdddd; color: #cc0000; font-weight: bold; }
.partial { background: #ffffcc; color: #996600; }
.empty { color: #999; font-style: italic; }
.legend { margin: 1em 0; padding: 0.5em 1em; border: 1px solid #ccc; background: #fafafa; font-size: 0.9em; }
.legend .diff { padding: 0 4px; }
</style>
</head>
<body>
<h1>Vergleich der drei Quellen (nach Genus aufgeschl\u00fcsselt)</h1>
<div class="legend">
<b>Legende:</b> <span class="diff">Rot</span> = weicht von der Mehrheit ab (2+ Quellen &uuml;berstimmen). 
<span class="partial">Gelb</span> = enth&auml;lt die Mehrheitsform als Variante, aber mit zus&auml;tzlichen Schreibvarianten.<br>
Leere Zellen (<span class="empty">-</span>) = Quelle hat f&uuml;r dieses Genus/Kasus keine Form.
</div>
<table>
<thead><tr>
<th>Kasus</th>
<th>Tabula</th>
<th>Prusaspira</th>
<th>Twanksta</th>
</tr></thead>
<tbody>
%s
</tbody>
</table>
</body>
</html>"""
html = TPL % "\n".join(rows_html)
OUT.write_text(html, encoding="utf-8")
print("Written to", OUT, "(%d rows)" % len(rows_html))
