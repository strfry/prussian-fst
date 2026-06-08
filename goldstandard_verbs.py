#!/usr/bin/env python3
"""Goldstandard-Voting für Verben (P71–144).

Liest vergleich_verbs.json (Tabula / Prusaspira / Twanksta).
Stimmt pro Person (1sg–2pl) in Blöcken (Tempus) ab:
  - 3/3 Einstimmig → übernommen
  - 2/3 Mehrheit  → VOTUM (Gewinner)
  - 1/3 oder 0/3 → KEINE MEHRHEIT, manuelle Entscheidung

Normalisierung (Sound-Regeln):
  Makron, Palatal-j-Tilgung, weiche Endung (-an/-in/-en).
"""
import json
import re
import unicodedata
from collections import Counter, OrderedDict
from pathlib import Path

VERB_IN = Path("vergleich_verbs.json")
OUT_MD  = Path("GOLDSTANDARD_VERBEN.md")
OUT_JSON = Path("goldstandard_verben.json")

SRC = ["Tabula", "Prusaspira", "Twanksta"]
TENSES = ["present", "preterite"]
PERSONS = ["1sg", "2sg", "3sg", "1pl", "2pl"]

MACRON = str.maketrans("āēīōūĀĒĪŌŪ", "aeiouAEIOU")


def strip_macron(s):
    return s.translate(MACRON)


def fold(s):
    """Makron + Diakritika entfernen, lowercase."""
    s = strip_macron(s)
    s = unicodedata.normalize("NFD", s)
    return "".join(c for c in s if not unicodedata.combining(c)).lower()


def nojot(s):
    """Palatalisierungs-j tilgen."""
    return re.sub(r"(?<!j)j(?!j)", "", s)


def depalatal(s):
    """Diakritika (außer Makron) entfernen, lowercase."""
    nfd = unicodedata.normalize("NFD", s)
    kept = "".join(c for c in nfd if not unicodedata.combining(c) or ord(c) == 0x0304)
    return unicodedata.normalize("NFC", kept).lower()


_VERB_SOFT = [
    (re.compile(r"amai$"), "imai"),     # 1pl Twanksta -amai → -imai
    (re.compile(r"atei$"), "itei"),     # 2pl Twanksta -atei → -itei
]


def verb_norm(s):
    """Verb-spezifische Normalisierung: fold + nojot + Endungsvokal."""
    s = nojot(fold(s))
    for rx, rep in _VERB_SOFT:
        s2 = rx.sub(rep, s)
        if s2 != s:
            return s2
    return s


def get_variants(val):
    """Form in /-getrennte Varianten splitten und normalisieren."""
    if not val:
        return set()
    return {verb_norm(p) for p in re.split(r"\s*/\s*", val) if p.strip()}


def pick_best(forms):
    """Schreibung wählen: Mehrheit, sonst diakritikreichste."""
    raw = list(forms.values())
    cnt = Counter(raw)
    top, n = cnt.most_common(1)[0]
    if n >= 2:
        return top
    # diakritikreichste
    def dc(s):
        return sum(1 for c in unicodedata.normalize("NFD", s) if unicodedata.combining(c))
    return max(forms.items(), key=lambda kv: (dc(kv[1]), SRC.index(kv[0])))[1]


def _tabula_agreement(tab_persons, src_forms):
    """Wie viele Tabula-Personen stimmen mit source überein (nach Normalisierung)?"""
    matches = 0
    for p, tv in tab_persons.items():
        tvn = get_variants(tv)
        sv = src_forms.get(p, "")
        if not sv:
            continue
        svn = get_variants(sv)
        if tvn & svn:
            matches += 1
    return matches


def _best_fill_source(tab, prus, tw):
    """Welche Quelle füllt Lücken, in denen Tabula fehlt?
    Die Quelle mit den meisten Übereinstimmungen mit Tabula."""
    if not tab:
        return None
    m_p = _tabula_agreement(tab, prus) if prus else -1
    m_t = _tabula_agreement(tab, tw) if tw else -1
    if m_p > m_t:
        return "Prusaspira"
    if m_t > m_p:
        return "Twanksta"
    if m_p > 0:
        return "beide"
    return None


def vote_block(paradigm, lemma, tense, sources):
    """Block-Voting: Tabula liefert Goldstandard für eigene Personen;
    Lücken werden von der am besten passenden Quelle gefüllt."""
    sdata = {}
    for s in SRC:
        sdata[s] = sources.get(s, {}).get(tense, {})

    tab = sdata["Tabula"]
    prus = sdata["Prusaspira"]
    tw = sdata["Twanksta"]

    fill_source = _best_fill_source(tab, prus, tw)

    results = []
    for person in PERSONS:
        tab_v = tab.get(person, "")
        prus_v = prus.get(person, "")
        tw_v = tw.get(person, "")

        forms_present = [(s, v) for s, v in
                         [("Tabula", tab_v), ("Prusaspira", prus_v), ("Twanksta", tw_v)] if v]

        if not forms_present:
            results.append((person, "", "LÜCKE", ""))
            continue

        # Tabula hat die Form → übernehmen
        if tab_v:
            results.append((person, tab_v, "TABULA", ""))
            continue

        # Nur 1 Quelle für diese Person
        if len(forms_present) == 1:
            results.append((person, forms_present[0][1], "EINZEL", ""))
            continue

        # 2+ Quellen (beide online), Tabula fehlt → Block-Entscheidung
        src_vars = {s: get_variants(v) for s, v in forms_present}
        all_vars = set()
        for vv in src_vars.values():
            all_vars.update(vv)

        cnt = Counter()
        for v in all_vars:
            cnt[v] = sum(1 for vv in src_vars.values() if v in vv)

        top_val, top_n = cnt.most_common(1)[0]

        if top_n >= len(forms_present):
            winners = {s for s in src_vars if top_val in src_vars[s]}
            gold = pick_best({s: forms_present[[x[0] for x in forms_present].index(s)][1] for s in winners})
            results.append((person, gold, "EINSTIMMIG", ""))
        elif top_n >= 2:
            winners = {s for s in src_vars if top_val in src_vars[s]}
            gold = pick_best({s: forms_present[[x[0] for x in forms_present].index(s)][1] for s in winners})
            results.append((person, gold, "VOTUM", " / ".join("%s=%s" % (s, v) for s, v in forms_present)))
        else:
            # Uneinig: Fill-Source-Entscheidung
            if fill_source in ("Prusaspira", "beide") and prus_v:
                results.append((person, prus_v, "BLOCK(T→Ps)", " / ".join("%s=%s" % (s, v) for s, v in forms_present)))
            elif fill_source == "Twanksta" and tw_v:
                results.append((person, tw_v, "BLOCK(T→Tw)", " / ".join("%s=%s" % (s, v) for s, v in forms_present)))
            elif fill_source == "beide" and tw_v and not prus_v:
                results.append((person, tw_v, "BLOCK(both→Tw)", ""))
            else:
                results.append((person, "?", "KEINE MEHRHEIT",
                                " / ".join("%s=%s" % (s, v) for s, v in forms_present)))

    return results


def main():
    data = json.loads(VERB_IN.read_text(encoding="utf-8"))

    def sort_key(k):
        num = k.split("_", 1)[0]
        m = re.match(r"(\d+)([a-z]*)", num)
        return (int(m.group(1)), m.group(2) or "")

    all_blocks = []
    gs_entries = []

    for key in sorted(data, key=sort_key):
        e = data[key]
        num = key.split("_", 1)[0]
        lemma = key.split("_", 1)[1] if "_" in key else key

        block_entry = {"paradigm": num, "lemma": lemma, "tenses": {}}

        for tense in TENSES:
            tab = e.get("Tabula", {}).get(tense, {})
            prus = e.get("Prusaspira", {}).get(tense, {})
            tw = e.get("Twanksta", {}).get(tense, {})

            if not tab and not prus and not tw:
                continue

            sources = {"Tabula": {tense: tab}, "Prusaspira": {tense: prus}, "Twanksta": {tense: tw}}
            results = vote_block(num, lemma, tense, sources)

            block_entry["tenses"][tense] = {
                "persons": {p: {"form": f, "status": s, "detail": d}
                           for p, f, s, d in results}
            }

        if block_entry["tenses"]:
            all_blocks.append(block_entry)
            gs_e = {"paradigm": num, "lemma": lemma, "tenses": {}}
            for tense, td in block_entry["tenses"].items():
                gs_e["tenses"][tense] = {}
                for p, r in td["persons"].items():
                    if r["status"] not in ("KEINE MEHRHEIT", "LÜCKE"):
                        gs_e["tenses"][tense][p] = r["form"]
            gs_entries.append(gs_e)

    OUT_JSON.write_text(json.dumps(gs_entries, ensure_ascii=False, indent=2), encoding="utf-8")

    # MD rausschreiben
    L = []
    L.append("# Goldstandard Verben (P71–144)\n")
    L.append("Voting pro Person (1sg–2pl) in Tempus-Blöcken. "
             "Normalisierung: Makron, Palatal-j, Endungsvokal.\n")
    L.append("| Status | Bedeutung |")
    L.append("|--------|-----------|")
    L.append("| EINSTIMMIG | alle Quellen identisch (nach Normalisierung) |")
    L.append("| VOTUM | 2/3 Mehrheit |")
    L.append("| BLOCK(Tabula→Ps/Tw) | Tabula entscheidet für Quelle → deren Block übernommen |")
    L.append("| EINZEL | nur 1 Quelle vorhanden |")
    L.append("| LÜCKE | keine Quelle für diese Person |")
    L.append("| KEINE MEHRHEIT | keine Einigung – manuell entscheiden |")
    L.append("")

    for be in all_blocks:
        L.append("---")
        L.append("## P%s %s\n" % (be["paradigm"], be["lemma"]))
        for tense in TENSES:
            if tense not in be["tenses"]:
                continue
            td = be["tenses"][tense]
            L.append("### %s\n" % tense.capitalize())
            L.append("| Person | Tabula | Prusaspira | Twanksta | Status | Gold |")
            L.append("|--------|--------|------------|----------|--------|------|")
            for p in PERSONS:
                r = td["persons"].get(p, {"form": "", "status": "LÜCKE", "detail": ""})
                tab_f = be.get("tenses", {}).get(tense, {}).get("persons", {}).get(p, {}).get("detail", "")
                f_tab = ""
                f_prus = ""
                f_tw = ""
                # Reconstruct from data
                data_key = "%s_%s" % (be["paradigm"], be["lemma"])
                if data_key in data:
                    det = data[data_key]
                    f_tab = det.get("Tabula", {}).get(tense, {}).get(p, "—")
                    f_prus = det.get("Prusaspira", {}).get(tense, {}).get(p, "—")
                    f_tw = det.get("Twanksta", {}).get(tense, {}).get(p, "—")
                gold = r["form"] if r["status"] != "LÜCKE" else "—"
                status = r["status"]
                L.append("| %s | %s | %s | %s | %s | **%s** |" % (
                    p, f_tab, f_prus, f_tw, status, gold))
            L.append("")

    # Zusammenfassung
    votes = Counter()
    open_blocks = 0
    for be in all_blocks:
        for td in be["tenses"].values():
            for r in td["persons"].values():
                votes[r["status"]] += 1
                if r["status"] == "KEINE MEHRHEIT":
                    open_blocks += 1

    L.append("## Zusammenfassung\n")
    L.append("| Status | Anzahl |")
    L.append("|--------|-------|")
    for s, n in votes.most_common():
        L.append("| %s | %d |" % (s, n))
    L.append("")
    if open_blocks:
        L.append("**%d Personen-Formen ohne Mehrheit – manuelle Entscheidung nötig.**" % open_blocks)
    L.append("")

    OUT_MD.write_text("\n".join(L), encoding="utf-8")
    print("Written", OUT_JSON)
    print("Written", OUT_MD)
    print("  Blöcke:", len(all_blocks))
    print("  Votes:", dict(votes))


if __name__ == "__main__":
    main()
