#!/usr/bin/env python3
"""Extract participle forms from existing raw API responses.

Reads prusaspira/{num}_{lemma}.html and twanksta/{num}_{lemma}/forms.html,
parses them with BeautifulSoup / manual split for malformed HTML,
and saves structured data as participles.json.

Usage:
  python extract_participles.py              # process all existing HTML
  python extract_participles.py --paradigm 71 # only paradigm 71
  python extract_participles.py --fetch 71     # download + process P71
"""

import argparse
import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

from bs4 import BeautifulSoup

PRUSASPIRA_DIR = Path("prusaspira")
TWANKSTA_DIR = Path("twanksta")
VERB_PARADIGMS = Path("verb_paradigms.json")
WORDLIST = Path("wordlist.json")

PRUSASPIRA_BASE = "https://www.prusaspira.org/wirdeins"
TWANKSTA_SEARCH = "https://wirdeins.twanksta.org/search/"
TWANKSTA_FORMS = "https://wirdeins.twanksta.org/more/"
UA = "Mozilla/5.0"


# ── helpers ──────────────────────────────────────────────────────────────

def strip_diacritics(word):
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFKD", word)
                   if not unicodedata.combining(c))


def alternate_inf(word):
    if word.endswith("tun"):
        return word[:-3] + "twei"
    if word.endswith("twei"):
        return word[:-4] + "tun"
    return None


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    return urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "replace")


def post(url, data):
    body = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(url, data=body, headers={
        "User-Agent": UA,
        "Content-Type": "application/x-www-form-urlencoded",
        "X-Requested-With": "XMLHttpRequest",
    })
    return urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "replace")


# ── Prusaspira parser ───────────────────────────────────────────────────

def parse_prusaspira(html):
    """Parse Prusaspira boldtable HTML into structured verb data.

    Returns dict with keys: participles (list), optative, conjunctive, imperative.
    The boldtable HTML is malformed (rows lack opening <tr>),
    so we split on </tr> and manually extract <td> contents.
    """
    m = re.search(
        r'<table[^>]*(?:class|CLASS)="?boldtable"?[^>]*>(.*?)</table>',
        html, re.DOTALL,
    )
    if not m:
        return None

    raw = m.group(1)

    # Split on </tr> to get row chunks
    row_chunks = [c.strip() for c in raw.split("</tr>") if c.strip()]

    result = {"participles": {}, "optative": None, "conjunctive": {}, "imperative": {}}

    participles_seen = {"pcps": "present", "pcptac": "past", "pcptpa": "passive"}

    conj_forms = []
    imp_forms = []

    for i, chunk in enumerate(row_chunks):
        cells = _extract_td_contents(chunk)
        if not cells:
            continue

        # ── Participle column (col 7) ──
        if len(cells) > 7:
            part_cell = cells[7]
            # Either a header <b> or an <a> link with the form
            link = re.search(
                r"""onclick="ens_str\('([^']+)'\);?"[^>]*>([^<]+)<""",
                part_cell,
            )
            if link:
                args = link.group(1)
                parts = args.split(",")
                if len(parts) >= 3:
                    form = parts[0]
                    part_type = participles_seen.get(parts[2].strip(), parts[2])
                    result["participles"][part_type] = form

        # ── Imperative / Optative column (col 5) ──
        if len(cells) > 5:
            imp_text = _strip_tags(cells[5]).strip().rstrip("!")
            if imp_text not in imp_forms:
                imp_forms.append(imp_text)

        # ── Conjunctive column (col 6) ──
        if len(cells) > 6:
            conj_text = _strip_tags(cells[6]).strip()
            if conj_text not in conj_forms:
                conj_forms.append(conj_text)

    if imp_forms:
        result["optative"] = imp_forms[0]  # first row → 3sg optative
        result["imperative"] = imp_forms

    if conj_forms:
        result["conjunctive"] = {
            "sg_3pl": conj_forms[0],
            "1pl": conj_forms[1] if len(conj_forms) > 1 else None,
            "2pl": conj_forms[2] if len(conj_forms) > 2 else None,
        }

    if not result["participles"]:
        return None
    return result

def _extract_td_contents(chunk):
    """Extract <td>...</td> contents from an HTML table row chunk."""
    cells = []
    # Find all <td> blocks — handle missing closing tags
    td_re = re.compile(r"<td\b[^>]*>(.*?)</td>", re.DOTALL)
    for m in td_re.finditer(chunk):
        cells.append(m.group(1))
    return cells


def _strip_tags(html_fragment):
    return re.sub(r"<[^>]+>", "", html_fragment)


# ── Twanksta parser ─────────────────────────────────────────────────────

def parse_twanksta(html):
    """Parse Twanksta forms.html into structured verb data.

    Uses BeautifulSoup.  Returns dict with participles (and declension),
    optative, imperative, subjunctive.
    """
    soup = BeautifulSoup(html, "html.parser")
    result = {"participles": {}, "optative": None, "imperative": {}, "subjunctive": {}}

    # ── Optative ── h3 → next free-standing verb span
    opt_h3 = soup.find("h3", string="Optative")
    if opt_h3:
        v = opt_h3.find_next("span", class_="verb")
        if v:
            result["optative"] = v.get_text(strip=True)

    # ── Imperative ── h3 → pronoun + verb pairs
    imp_h3 = soup.find("h3", string="Imperative")
    if imp_h3:
        pron = imp_h3.find_next("span", class_="pronoun")
        if pron:
            # Walk siblings in the parent <td>
            container = pron.find_parent("td") or pron.find_parent("span")
            if container:
                pronoun_map = {"(tū)": "2sg", "(jūs)": "2pl"}
                for sp in container.find_all("span", class_="pronoun"):
                    person = pronoun_map.get(sp.get_text(strip=True), sp.get_text(strip=True))
                    ve = sp.find_next("span", class_="verb")
                    if ve:
                        result["imperative"][person] = ve.get_text(strip=True)

    # ── Participles ── h3 → all following spoiler-title2 elements
    part_h3 = soup.find("h3", string="Participle")
    if part_h3:
        head_map = {"Present": "present", "Past": "past", "Passive": "passive"}
        spoilers = part_h3.find_all_next("span", class_=re.compile(r"spoiler-title2"))
        for spoiler in spoilers:
            # Find the nearest preceding head to know which participle type
            head = spoiler.find_previous("span", class_="head")
            if not head:
                continue
            htext = head.get_text(strip=True)
            key = head_map.get(htext)
            if not key or key in result["participles"]:
                continue
            # The form is the inner <span> without a class (second span)
            spans = spoiler.find_all("span")
            form = None
            for sp in spans:
                txt = sp.get_text(strip=True)
                if not sp.get("class") and txt not in ("►", "▶", ""):
                    form = txt
                    break
            if form:
                entry = {"form": form}
                # Declension from following .spoiler-body2
                body = spoiler.find_next("div", class_="spoiler-body2")
                if body:
                    decl = _parse_declension_tables(body)
                    if decl:
                        entry["declension"] = decl
                result["participles"][key] = entry

    # ── Subjunctive ── h3 → pronoun + verb pairs
    sub_h3 = soup.find("h3", string="Subjunctive")
    if sub_h3:
        pron = sub_h3.find_next("span", class_="pronoun")
        if pron:
            container = pron.find_parent("td")
            if container:
                forms = []
                for sp in container.find_all("span", class_="pronoun"):
                    ptext = sp.get_text(strip=True)
                    ve = sp.find_next("span", class_="verb")
                    if ve:
                        forms.append((ptext, ve.get_text(strip=True)))
                if forms:
                    result["subjunctive"]["forms"] = forms

    if not result["participles"]:
        return None
    return result


def _parse_declension_tables(body_elem):
    """Parse participle declension tables (.spoiler-body2).

    Returns dict keyed by gender (masc/fem/neut), each containing
    {case: {sg: …, pl: …}}.
    """
    cases_map = {"Nominative": "Nom", "Genitive": "Gen", "Dative": "Dat", "Accusative": "Akk"}
    out = {}

    for table in body_elem.find_all("table", id="subst"):
        # Determine gender from the first th.null
        null_th = table.find("th", class_="null")
        gender = null_th.get_text(strip=True).lower() if null_th else "unknown"

        decl = {}
        rows = table.find_all("tr")
        for row in rows:
            headers = row.find_all("th", class_="hea")
            if not headers:
                continue
            case_name = headers[0].get_text(strip=True)
            abbr = cases_map.get(case_name)
            if not abbr:
                continue
            verb_spans = row.find_all("span", class_="verb")
            if len(verb_spans) >= 2:
                sg = verb_spans[0].get_text(strip=True)
                pl = verb_spans[1].get_text(strip=True)
                if sg or pl:
                    decl[abbr] = {"sg": sg, "pl": pl}
        if decl:
            out[gender] = decl

    return out if out else None


# ── Missing data fetch ──────────────────────────────────────────────────

def fetch_paradigm(num, lemma):
    """Fetch missing raw data for a paradigm.  Returns (prus_ok, twank_ok)."""
    prus_ok = _fetch_prusaspira(num, lemma)
    time.sleep(1.2)
    twank_ok = _fetch_twanksta(num, lemma)
    return prus_ok, twank_ok


def _fetch_prusaspira(num, lemma):
    html_file = PRUSASPIRA_DIR / f"{num}_{lemma}.html"
    if html_file.exists() and 'prūsiskai' in html_file.read_text():
        return True
    # Try lemma first, then alternate infinitive
    candidates = [lemma]
    alt = alternate_inf(lemma)
    if alt:
        candidates.append(alt)
    for cand in candidates:
        url = f"{PRUSASPIRA_BASE}?{urllib.parse.urlencode({'wirds': cand, 'akc': 'Iz', 'bila': '1'})}"
        try:
            raw = get(url)
            if 'prūsiskai' in raw and 'boldtable' in raw:
                PRUSASPIRA_DIR.mkdir(exist_ok=True)
                html_file.write_text(raw, encoding="utf-8")
                return True
        except Exception:
            pass
        time.sleep(1.2)
    return False


def _fetch_twanksta(num, lemma):
    tw_dir = TWANKSTA_DIR / f"{num}_{lemma}"
    forms_file = tw_dir / "forms.html"
    if forms_file.exists():
        return True

    # 1) Search
    search_url = f"{TWANKSTA_SEARCH}?dia=semba&s={urllib.parse.quote(lemma)}&language=engl"
    try:
        search_raw = get(search_url)
    except Exception:
        return False
    time.sleep(1.2)

    # Extract desc and numb
    m_desc = re.search(r"<span class='desc'>([^<]+)</span>", search_raw)
    desc = m_desc.group(1) if m_desc else f"[{lemma}]"
    m_numb = re.search(r"<span class='numb'>([^<]+)</span>", search_raw)
    numb = m_numb.group(1) if m_numb else num

    # 2) POST forms
    try:
        forms_raw = post(TWANKSTA_FORMS, {
            "word": lemma, "numb": numb, "desc": desc, "dia": "semba",
        })
    except Exception:
        return False

    tw_dir.mkdir(parents=True, exist_ok=True)
    forms_file.write_text(forms_raw, encoding="utf-8")
    # Save search.html too
    search_file = tw_dir / "search.html"
    search_file.write_text(search_raw, encoding="utf-8")
    return True


# ── Main ─────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="Extract participle forms from raw API data")
    ap.add_argument("--paradigm", "-p", type=str, help="Only process this paradigm number")
    ap.add_argument("--fetch", "-f", action="store_true", help="Fetch missing raw data first")
    args = ap.parse_args()

    vp = json.loads(VERB_PARADIGMS.read_text(encoding="utf-8"))
    paradigms = vp["paradigms"]

    def sort_key(n):
        m = re.match(r"(\d+)([a-z]*)", n)
        return (int(m.group(1)), m.group(2) or "")

    items = sorted(paradigms.items(), key=lambda kv: sort_key(kv[0]))

    prus_ok = twank_ok = prus_fail = twank_fail = skipped = 0
    target = args.paradigm

    for num, entry in items:
        if target and num != target:
            continue
        lemma = entry["lemma"]
        print(f"[P{num}] {lemma} ", end="")

        # ── Fetch if needed ──
        if args.fetch:
            pok, tok = fetch_paradigm(num, lemma)
        else:
            pok = (PRUSASPIRA_DIR / f"{num}_{lemma}.html").exists()
            tok = (TWANKSTA_DIR / f"{num}_{lemma}" / "forms.html").exists()

        # ── Parse Prusaspira ──
        prus_data = None
        if pok:
            html = (PRUSASPIRA_DIR / f"{num}_{lemma}.html").read_text(encoding="utf-8")
            prus_data = parse_prusaspira(html)
            if prus_data:
                prus_ok += 1
                print("P✓", end="")
            else:
                prus_fail += 1
                print("P✗", end="")
        else:
            print("P-", end="")

        # ── Parse Twanksta ──
        twank_data = None
        twank_dir = TWANKSTA_DIR / f"{num}_{lemma}"
        if tok:
            html = (twank_dir / "forms.html").read_text(encoding="utf-8")
            twank_data = parse_twanksta(html)
            if twank_data:
                twank_ok += 1
                print(" T✓", end="")
            else:
                twank_fail += 1
                print(" T✗", end="")
        else:
            print(" T-", end="")

        # ── Save participles.json ──
        output = {
            "lemma": lemma,
            "paradigm": num,
            "infinitive_stem": _inf_stem(lemma),
        }
        if prus_data:
            output["prusaspira"] = prus_data
        if twank_data:
            output["twanksta"] = twank_data

        if tok:
            out_path = twank_dir / "participles.json"
        else:
            out_path = PRUSASPIRA_DIR / f"{num}_{lemma}_participles.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")

        print()

    print(f"\nDone: prus={prus_ok}✓/{prus_fail}✗  twank={twank_ok}✓/{twank_fail}✗")


def _inf_stem(lemma):
    """Derive infinitive stem: strip -tun/-twei/-stwei."""
    for suffix in ("stwei", "twei", "tun"):
        if lemma.endswith(suffix):
            return lemma[:-len(suffix)]
    return lemma


if __name__ == "__main__":
    main()
