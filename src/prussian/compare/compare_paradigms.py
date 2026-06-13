#!/usr/bin/env python3
"""Compare tabula paradigm forms against prusaspira.org tables.

For each paradigm with a fetched declension table, line up the four cases
(Nōm/Gēn/Dāt/Akk) in sg and pl and flag where tabula and prusaspira differ.
Comparison is reported at three levels: exact, vowel-length-only (macron),
and real divergence.
"""
import json
import re
import unicodedata
from pathlib import Path

CASES = ["Nōm", "Gēn", "Dāt", "Akk"]
MACRON = str.maketrans("āēīōūĀĒĪŌŪ", "aeiouAEIOU")


def strip_macron(s: str) -> str:
    return s.translate(MACRON)


def fold(s: str) -> str:
    """Drop all combining marks + macrons -> bare ASCII-ish skeleton."""
    s = strip_macron(s)
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.lower()


# ---- tabula forms -----------------------------------------------------------
def tabula_forms():
    html = open("tabula.html", encoding="utf-8").read()
    out = {}
    for m in re.finditer(r"<p[^>]*>(.*?)</p>", html, re.DOTALL):
        text = re.sub(r"<[^>]*>", "", m.group(1))
        text = text.replace("&nbsp;", " ").replace("&ndash;", "-").replace("–", "-")
        text = " ".join(text.split())
        if len(text) < 3:
            continue
        mm = re.match(r"^(\d+[a-z]?)\s+([mfn/]+)?\s*:?\s*(.*)", text)
        if not mm:
            continue
        num = mm.group(1)
        try:
            if not (1 <= int(num.rstrip("abc")) <= 144):
                continue
        except ValueError:
            continue
        if num not in out:
            out[num] = mm.group(3)
    return out


def parse_tabula_decl(rest):
    """Return {('Nōm','sg'):form, ...} or None."""
    toks = rest.split()
    if not toks:
        return None
    if toks[0] == "sg/pl":
        vals = toks[1:5]
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
        return None
    d = {}
    for c, s, p in zip(CASES, sg, pl):
        d[(c, "sg")] = s
        d[(c, "pl")] = p
    return d


# ---- prusaspira table -------------------------------------------------------
def parse_prusaspira(num, lemma):
    p = Path(f"prusaspira/{num}_{lemma}.txt")
    if not p.exists():
        return None, "missing"
    lines = p.read_text(encoding="utf-8").splitlines()
    # confirm first entry lemma roughly matches
    head = next((l for l in lines if l.strip().startswith("prūsiskai:")), "")
    d = {}
    seen = set()
    for line in lines:
        s = line.strip()
        mm = re.match(r"^(Nōm|Gēn|Dāt|Akk):\s+(.*)", s)
        if not mm:
            continue
        case = mm.group(1)
        if case in seen:
            continue  # only first table
        seen.add(case)
        # cut off a trailing new dictionary entry on the same line
        rest = mm.group(2).split("prūsiskai:")[0]
        vals = rest.split()
        if len(vals) >= 1:
            d[(case, "sg")] = vals[0]
        if len(vals) >= 2:
            d[(case, "pl")] = vals[1]
    if not d:
        return None, "no-table"
    return d, head


def classify(a, b):
    if a is None or b is None:
        return "—"
    if a == b:
        return "="
    if strip_macron(a) == strip_macron(b):
        return "≈len"  # differs only in vowel length
    if fold(a) == fold(b):
        return "≈dia"  # differs only in diacritics/palatalization
    return "≠"


# ---- run --------------------------------------------------------------------
pairs = json.load(open("/tmp/lemmas.json"))
# 27 now points at the adverb wesselingi (no decl); these have no table
EXCLUDE = {"27", "29", "30a", "55"}
tf = tabula_forms()

report = []
stats = {"=": 0, "≈len": 0, "≈dia": 0, "≠": 0, "—": 0}
diffs = []

for num, lemma in pairs:
    if num in EXCLUDE:
        continue
    tab = parse_tabula_decl(tf.get(num, ""))
    pru, head = parse_prusaspira(num, lemma)
    if not tab or not pru:
        report.append((num, lemma, "skip", tab is not None, pru is not None))
        continue
    rows = []
    for c in CASES:
        for n in ("sg", "pl"):
            a = tab.get((c, n))
            b = pru.get((c, n))
            cls = classify(a, b)
            stats[cls] += 1
            rows.append((c, n, a, b, cls))
            if cls in ("≈dia", "≠"):
                diffs.append((num, lemma, c, n, a, b, cls))
    report.append((num, lemma, "ok", rows, None))

json.dump(
    {"stats": stats, "diffs": diffs},
    open("prusaspira/_compare.json", "w"),
    ensure_ascii=False,
    indent=2,
)

# ---- markdown report --------------------------------------------------------
lines = ["# Abgleich tabula ↔ prusaspira\n"]
lines.append(
    f"Zellen gesamt — `=` identisch: {stats['=']}, "
    f"`≈len` nur Vokallänge: {stats['≈len']}, "
    f"`≈dia` nur Diakritika: {stats['≈dia']}, "
    f"`≠` echte Abweichung: {stats['≠']}\n"
)
for num, lemma, st, rows, _ in report:
    if st != "ok":
        lines.append(f"## {num} {lemma} — übersprungen\n")
        continue
    has = any(r[4] != "=" for r in rows)
    flag = "" if not has else "  ⚠"
    lines.append(f"## {num} {lemma}{flag}\n")
    lines.append("| Kasus | tabula | prusaspira |  |")
    lines.append("|---|---|---|---|")
    for c, n, a, b, cls in rows:
        mark = "" if cls == "=" else cls
        lines.append(f"| {c} {n} | {a or ''} | {b or ''} | {mark} |")
    lines.append("")

Path("prusaspira/ABGLEICH.md").write_text("\n".join(lines), encoding="utf-8")

print("Zellen:", stats)
print(f"\nParadigmen verglichen: {sum(1 for r in report if r[2]=='ok')}")
print(f"Übersprungen: {[ (r[0],r[1]) for r in report if r[2]!='ok']}")
print(f"\nEchte/diakritische Abweichungen (≠/≈dia): {len(diffs)}")
for num, lemma, c, n, a, b, cls in diffs:
    print(f"  {num:5} {lemma:14} {c} {n}: {a!r} vs {b!r}  [{cls}]")
