#!/usr/bin/env python3
"""Three-way verb comparison: Tabula vs Prusaspira vs Twanksta.

See AGENTS.md for protocol details.
"""
import json
import re
import unicodedata
from pathlib import Path

from bs4 import BeautifulSoup

VERB_PARADIGMS = Path("verb_paradigms.json")
PRUSASPIRA_DIR = Path("prusaspira")
TWANKSTA_DIR   = Path("twanksta")
OUT_HTML = Path("vergleich_verbs.html")
OUT_JSON  = Path("vergleich_verbs.json")

PERSON_ORDER = ["1sg", "2sg", "3sg", "1pl", "2pl"]

PRUS_PERSON_MAP = {
    "as": "1sg", "tū": "2sg", "3sg": "3sg",
    "mes": "1pl", "jūs": "2pl", "3pl": "3pl",
}
TW_PERSON_MAP = {
    "as": "1sg", "tū": "2sg",
    "tāns/tenā/tennan": "3sg",
    "tāns/tenā": "3sg",
    "tennan": "3sg",
    "mes": "1pl", "jūs": "2pl",
    "tenēi/tennas": "3pl",
    "(tū)": "2sg", "(jūs)": "2pl",
}

TENSE_LABELS = {
    "present": "Present", "preterite": "Preterite",
}

PRUS_TENSE_MAP = {
    "tēntisku": "present",
    "pragūbingisku": "preterite",
    "perfektan": "perfect",
    "perejīngisku": "future",
    "imperatīws": "imperative",
    "kōnjunktiws": "optative",
}


def strip_dia(s):
    return "".join(c for c in unicodedata.normalize("NFKD", s)
                   if not unicodedata.combining(c))


def norm(s):
    t = strip_dia(s).lower()
    for a, b in [("ŕ", "r"), ("ķ", "k"), ("ļ", "l"), ("ń", "n")]:
        t = t.replace(a, b)
    return t


def clean(val):
    """Collapse whitespace and strip."""
    return re.sub(r"\s+", " ", val).strip()


PREFIXES = ["ap", "at", "au", "eb", "en", "et", "iz", "ka", "pa", "po",
            "pra", "prei", "sen", "skre", "sur", "tra", "us", "wal"]

def get_variants(val):
    if not val:
        return set()
    raw_forms = [p for p in re.split(r"\s*/\s*", val) if p.strip()]
    variants = set()
    for raw in raw_forms:
        variants.add(norm(raw))
        for pfx in PREFIXES:
            if raw.startswith(pfx):
                variants.add(norm(raw[len(pfx):]))
    return variants


def cell(val, cls):
    if not val:
        return '<td class="empty">-</td>'
    if cls == "diff":
        return '<td class="diff">%s</td>' % val
    if cls == "partial":
        return '<td class="partial">%s</td>' % val
    return "<td>%s</td>" % val


# ── Tabula ──────────────────────────────────────────────────────────────

def read_tabula():
    vp = json.loads(VERB_PARADIGMS.read_text(encoding="utf-8"))
    out = {}
    for num, entry in vp["paradigms"].items():
        forms = {}
        for tense in ["present", "preterite"]:
            td = entry.get(tense, {})
            if td:
                forms[tense] = {}
                for p in PERSON_ORDER:
                    if p in td:
                        forms[tense][p] = td[p]
        out[num] = forms
    return out, vp["paradigms"]


# ── Prusaspira ──────────────────────────────────────────────────────────

def _fix_verb_table(html):
    return re.sub(r"</tr>\s*<td", "</tr><tr><td", html)


def parse_prusaspira_verb(num, lemma):
    path = PRUSASPIRA_DIR / f"{num}_{lemma}.html"
    if not path.exists():
        return None
    html = _fix_verb_table(path.read_text(encoding="utf-8"))
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table", class_="boldtable")
    if not table:
        return None

    ths = table.find_all("th")
    # 8 THs: [empty, present, preterite, perfect, future, imperative, optative, participles]
    # Only use first 6 content columns (skip 0 and 7)
    cols = []
    for th in ths[1:7]:
        t = th.get_text(strip=True).lower().rstrip(":")
        cols.append(PRUS_TENSE_MAP.get(t, t))

    rows = {}
    for tr in table.find_all("tr"):
        tds = tr.find_all("td")
        if len(tds) < 7:
            continue
        label = tds[0].get_text(strip=True).rstrip(":")
        person = PRUS_PERSON_MAP.get(label.lower())
        if not person:
            continue
        # tds[1]–tds[6] correspond to the 6 tenses
        rows[person] = [clean(td.get_text(strip=True)) for td in tds[1:7]]

    if not cols or not rows:
        return None

    out = {}
    for j, tense in enumerate(cols):
        td = {}
        for person, vals in rows.items():
            if j < len(vals) and vals[j]:
                td[person] = vals[j]
        if td:
            # Strip trailing "!" from imperative
            if tense == "imperative":
                td = {p: v.rstrip("!") for p, v in td.items()}
            out[tense] = td
    return out


# ── Twanksta ────────────────────────────────────────────────────────────

def parse_twanksta_verb(num, lemma):
    path = TWANKSTA_DIR / f"{num}_{lemma}" / "forms.html"
    if not path.exists():
        return None
    soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
    out = {}

    # Main tense table (Present, Past, Perfect, Future)
    rt = soup.find("table", class_="response")
    if rt:
        for td in rt.find_all("td"):
            head = td.find("span", class_="head")
            if not head:
                continue
            tense_label = head.get_text(strip=True).lower()
            tense = {"present": "present", "past": "preterite",
                     "perfect": "perfect", "future": "future"}.get(tense_label)
            if not tense:
                continue
            forms = {}
            for sp in td.find_all("span", class_="pronoun"):
                ptext = sp.get_text(strip=True)
                person = TW_PERSON_MAP.get(ptext.lower())
                if not person:
                    continue
                ve = sp.find_next("span", class_="verb")
                if ve:
                    forms[person] = clean(ve.get_text(strip=True))
            if forms:
                out[tense] = forms

    # Optative / Imperative sections (each in its own <td>)
    for heading, key in [("optative", "optative"), ("imperative", "imperative")]:
        h3 = soup.find("h3", string=re.compile(re.escape(heading), re.I))
        if not h3:
            continue
        parent_td = h3.find_parent("td")
        if not parent_td:
            continue
        if key == "optative":
            # Single form (no pronoun)
            vs = parent_td.find_all("span", class_="verb")
            forms = [clean(v.get_text(strip=True)) for v in vs if v.get_text(strip=True)]
            if forms:
                out[key] = {"form": " / ".join(forms)}
        elif key == "imperative":
            # Pronoun–verb pairs: (tū) → 2sg, (jūs) → 2pl
            forms = {}
            for sp in parent_td.find_all("span", class_="pronoun"):
                ptext = sp.get_text(strip=True)
                person = TW_PERSON_MAP.get(ptext.lower())
                if not person:
                    continue
                ve = sp.find_next("span", class_="verb")
                if ve:
                    forms[person] = clean(ve.get_text(strip=True))
            if forms:
                out[key] = forms

    return out if out else None


# ── Comparison ──────────────────────────────────────────────────────────

def compare():
    tabula_data, raw_entries = read_tabula()

    def sort_key(n):
        m = re.match(r"(\d+)([a-z]*)", n)
        return (int(m.group(1)), m.group(2) or "")

    nums = sorted(tabula_data.keys(), key=sort_key)
    json_out = {}

    for num in nums:
        lemma = raw_entries[num]["lemma"]
        tab_forms = tabula_data[num]
        prus_forms = parse_prusaspira_verb(num, lemma)
        tw_forms = parse_twanksta_verb(num, lemma)

        # Only keep present/preterite in JSON (filters out perfect/future/optative/imperative)
        keep = {"present", "preterite"}
        tab_f = {t: v for t, v in (tab_forms or {}).items() if t in keep}
        prus_f = {t: v for t, v in (prus_forms or {}).items() if t in keep} if prus_forms else {}
        tw_f = {t: v for t, v in (tw_forms or {}).items() if t in keep} if tw_forms else {}

        entry = {}
        if tab_f:
            entry["Tabula"] = tab_f
        if prus_f:
            entry["Prusaspira"] = prus_f
        if tw_f:
            entry["Twanksta"] = tw_f
        json_out[f"{num}_{lemma}"] = entry

    OUT_JSON.write_text(
        json.dumps(json_out, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Written {OUT_JSON} ({len(json_out)} entries)")

    # HTML
    h = [
        '<!DOCTYPE html><html lang="de"><head><meta charset="utf-8">',
        "<title>Vergleich Verben (3 Quellen)</title>",
        "<style>",
        "body{font-family:sans-serif;margin:20px}",
        "table{border-collapse:collapse;width:100%;margin-bottom:6px}",
        "td,th{border:1px solid #ccc;padding:4px 8px;text-align:left}",
        "th{position:sticky;top:0;background:#eee}",
        ".paradigm-header{background:#ddeeff;font-weight:bold;text-align:center}",
        ".tense-header{background:#eef;font-style:italic}",
        ".diff{background:#ffdddd;color:#cc0000;font-weight:bold}",
        ".partial{background:#ffffcc;color:#996600}",
        ".empty{color:#999;font-style:italic}",
        ".missing{color:#999}",
        "</style></head><body>",
        "<h1>Vergleich der drei Quellen — Verben (P71–144)</h1>",
        "<p>Farblegende: <span class='diff'>rot</span> = abweichend, "
        "<span class='partial'>gelb</span> = teilweise abweichend, "
        "schwarz = übereinstimmend (Mehrheit).</p>",
    ]
    for num in nums:
        lemma = raw_entries[num]["lemma"]
        tab_forms = tabula_data[num]
        prus_forms = parse_prusaspira_verb(num, lemma)
        tw_forms = parse_twanksta_verb(num, lemma)

        h.append(
            f'<table><tr class="paradigm-header"><td colspan="4">P{num} {lemma}</td></tr>'
        )

        for tense in ["present", "preterite"]:
            label = TENSE_LABELS.get(tense, tense.capitalize())
            ta = tab_forms.get(tense, {})
            pr = prus_forms.get(tense, {}) if prus_forms else {}
            tw = tw_forms.get(tense, {}) if tw_forms else {}

            if not ta and not pr and not tw:
                continue

            h.append(
                f'<tr class="tense-header"><td colspan="4"><b>{label}</b></td></tr>'
            )

            for person in PERSON_ORDER:
                va = ta.get(person, "")
                vb = pr.get(person, "")
                vc = tw.get(person, "")

                vars_a = get_variants(va)
                vars_b = get_variants(vb)
                vars_c = get_variants(vc)
                all_vars = vars_a | vars_b | vars_c
                if not all_vars:
                    continue

                majority = set()
                for v in all_vars:
                    count = (v in vars_a) + (v in vars_b) + (v in vars_c)
                    if count >= 2:
                        majority.add(v)

                def classify(vals):
                    if not vals:
                        return "empty"
                    vs = get_variants(vals)
                    if not majority:
                        return ""
                    if not (vs & majority):
                        return "diff"
                    if not vs.issubset(majority):
                        return "partial"
                    return ""

                h.append("<tr>")
                h.append(f"<td>{person}</td>")
                h.append(cell(va, classify(va)))
                h.append(cell(vb, classify(vb)))
                h.append(cell(vc, classify(vc)))
                h.append("</tr>")

        h.append("</table>")

    h.append("</body></html>")
    OUT_HTML.write_text("\n".join(h), encoding="utf-8")
    print(f"Written {OUT_HTML}")


if __name__ == "__main__":
    compare()
