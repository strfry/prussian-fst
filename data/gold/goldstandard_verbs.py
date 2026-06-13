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
VERB_GS = Path("goldstandard_verben.json")
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
    """Verb-spezifische Normalisierung: fold + nojot + degem + Endungsvokal."""
    s = nojot(fold(s))
    s = re.sub(r"(.)\1", r"\1", s)  # degeminate
    for rx, rep in _VERB_SOFT:
        s2 = rx.sub(rep, s)
        if s2 != s:
            return s2
    return s


PREFIXES = ["ap", "at", "au", "eb", "en", "et", "iz", "ka", "pa", "po",
            "pra", "prei", "sen", "skre", "sur", "tra", "us", "wal"]

def get_variants(val):
    """Form in /-getrennte Varianten splitten und normalisieren. Inkl. prefix-freie Varianten."""
    if not val:
        return set()
    raw_forms = [p for p in re.split(r"\s*/\s*", val) if p.strip()]
    variants = set()
    for raw in raw_forms:
        variants.add(verb_norm(raw))
        for pfx in PREFIXES:
            if raw.startswith(pfx):
                variants.add(verb_norm(raw[len(pfx):]))
    return variants


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


def _sources_agree(s1, s2):
    """Stimmen zwei Quellen auf mindestens einer gemeinsamen Person überein?"""
    shared = [p for p in PERSONS if p in s1 and p in s2]
    for p in shared:
        if get_variants(s1[p]) & get_variants(s2[p]):
            return True
    return False


def _block_winner(tab, prus, tw):
    """Block-Voting: 3 Quellen = 3 Stimmen. Paarweise vergleichen.
    
    Returns (winner, status) where winner is Prusaspira or Twanksta.
    Tabula stimmt für die Quelle, die mit ihren Formen übereinstimmt.
    """
    has_tab = bool(tab)
    has_prus = bool(prus)
    has_tw = bool(tw)

    tab_prus = _sources_agree(tab, prus) if has_tab and has_prus else False
    tab_tw = _sources_agree(tab, tw) if has_tab and has_tw else False
    prus_tw = _sources_agree(prus, tw) if has_prus and has_tw else False

    # 3/3 – alle einig
    if has_tab and tab_prus and tab_tw:
        return "Prusaspira", "EINSTIMMIG"

    # Tabula + Prusaspira → Prusaspira-Block
    if tab_prus:
        return "Prusaspira", "VOTUM(T+Ps)"

    # Tabula + Twanksta → Twanksta-Block
    if tab_tw:
        return "Twanksta", "VOTUM(T+Tw)"

    # Nur PS+TW, Tabula fehlt oder keine Übereinstimmung
    if prus_tw:
        return "Prusaspira", "VOTUM(Ps+Tw)"

    # Nur Tabula (keine anderen Quellen)
    if has_tab and not has_prus and not has_tw:
        return "Tabula", "EINZEL"

    # Nur eine Quelle hat einen vollständigen Block → akzeptieren
    complete = []
    if has_prus and all(p in prus for p in PERSONS):
        complete.append(("Prusaspira", prus))
    if has_tw and all(p in tw for p in PERSONS):
        complete.append(("Twanksta", tw))
    if len(complete) == 1:
        return complete[0][0], "EINZEL"

    # Keine Koalition
    return None, "KEINE MEHRHEIT"


def vote_block(paradigm, lemma, tense, sources):
    """Block-Voting: Der gesamte Tempus-Block kommt aus einer Quelle."""
    sdata = {}
    for s in SRC:
        sdata[s] = sources.get(s, {}).get(tense, {})

    tab = sdata["Tabula"]
    prus = sdata["Prusaspira"]
    tw = sdata["Twanksta"]

    winner, status = _block_winner(tab, prus, tw)

    # Gewinner-Quelle bestimmen
    if winner == "Prusaspira":
        source_block = prus
    elif winner == "Twanksta":
        source_block = tw
    elif winner == "Tabula":
        source_block = tab
    else:
        source_block = {}

    results = []
    for person in PERSONS:
        gold = source_block.get(person, "")
        if not gold and person in tab:
            gold = tab[person]
        if not gold:
            for _, v in [("Prusaspira", prus.get(person, "")),
                         ("Twanksta", tw.get(person, "")),
                         ("Tabula", tab.get(person, ""))]:
                if v:
                    gold = v
                    break
        if not gold:
            results.append((person, "", "LÜCKE", ""))
        else:
            results.append((person, gold, status, ""))

    return results


# ── Verb-spezifische Stamm/Suffix-Extraktion (analog goldstandard.py:build_gold) ──

FST_OUT = Path("goldstandard_verben_fst.json")

PERSONS_ORDER = ["1sg", "2sg", "3sg", "1pl", "2pl"]


def verb_stem_len(forms):
    """Längste gemeinsame Präfixlänge, makron- UND diakritika-insensitiv (fold).
    Entspricht goldstandard.py:stem_len()."""
    sk = [fold(f) for f in forms if f]
    if not sk:
        return 0
    n = min(len(x) for x in sk)
    i = 0
    while i < n and len({x[i] for x in sk}) == 1:
        i += 1
    return i


def _first_variant(s):
    """Schrägstrich-Varianten auflösen: 'lassi/lassē' → 'lassi'."""
    return s.split("/", 1)[0].strip() if s else s


def verb_build_entry(forms_dict, lemma=None):
    """Stamm + Suffixe aus einem Tempusblock extrahieren.

    forms_dict: {"1sg": gold_form, "2sg": gold_form, …}
    lemma:      Infinitiv (nur für present). NICHT im LCP für den Stamm,
                sondern nur für die Inf-Suffix-Ableitung verwendet.

    Returns {"stamm": …, "suffixe": {person: {suffix, betont, …}}}
    """
    # Varianten auflösen: nur erste Form vor '/'
    fd = {p: _first_variant(forms_dict[p]) for p in forms_dict}
    persons = [p for p in PERSONS_ORDER if p in fd and fd[p]]
    golds = [fd[p] for p in persons]
    if lemma:
        lemma = _first_variant(lemma)
    if not golds:
        return {"stamm": "", "suffixe": {}}

    L = verb_stem_len(golds)
    if L == 0:
        base = ""
        stamm = ""
        regions = {}
        acc = set()
    else:
        # Repräsentant für die Vokal-Trimmung: immer die erste Goldform,
        # da sie garantiert ≥ L ist (L = LCP aller Goldformen)
        rep = golds[0]
        Lp = L
        while Lp > 0 and strip_macron(rep[Lp - 1]).lower() in "aeiou":
            Lp -= 1
        if Lp == 0 and L > 0:
            Lp = L

        base = strip_macron(rep[:Lp]).lower()
        regions = {}
        for p in persons:
            regions[p] = golds[persons.index(p)][:Lp]
        acc = set()
        for pos in range(Lp):
            if base[pos] in "aeiou":
                for r in regions.values():
                    if len(r) > pos and r[pos] != strip_macron(r[pos]):
                        acc.add(pos)
                        break

        stamm = "".join(ch.upper() if p in acc else ch for p, ch in enumerate(base))

    suffixe = {}
    if lemma:
        inf_suff = lemma[Lp:] if Lp > 0 else lemma
        suffixe["Inf"] = {"suffix": inf_suff}
        if Lp > 0:
            region_lemma = lemma[:Lp]
            suffixe["Inf"]["betont"] = any(
                len(region_lemma) > p and region_lemma[p] != strip_macron(region_lemma[p])
                for p in acc
            )
            region_lc = strip_macron(region_lemma).lower()
            if region_lc != base:
                suffixe["Inf"]["palatize"] = True

    for p in persons:
        g = golds[persons.index(p)]
        entry = {"suffix": g[Lp:]}
        if Lp > 0:
            region = regions[p]
            entry["betont"] = any(
                len(region) > pos and region[pos] != strip_macron(region[pos])
                for pos in acc
            )
            if strip_macron(region).lower() != base:
                entry["palatize"] = True
        suffixe[p] = entry

    return {"stamm": stamm, "suffixe": suffixe}


def build_verb_fst_entries():
    """Liest goldstandard_verben.json → pro Paradigma+Tempus Stamm+Suffixe → schreibt JSON."""
    data = json.loads(VERB_GS.read_text(encoding="utf-8"))
    entries = []

    def sort_key(e):
        num = e["paradigm"]
        m = re.match(r"(\d+)([a-z]*)", num)
        return (int(m.group(1)), m.group(2) or "")

    for e in sorted(data, key=sort_key):
        par = e["paradigm"]
        lemma = e["lemma"]
        tenses = e.get("tenses", {})

        for tense in ("present", "preterite"):
            td = tenses.get(tense)
            if not td:
                continue
            L_lemma = lemma if tense == "present" else None
            res = verb_build_entry(td, lemma=L_lemma)
            if not res["suffixe"]:
                continue
            entries.append(OrderedDict([
                ("paradigm", par),
                ("lemma", lemma),
                ("tense", tense),
                ("stamm", res["stamm"]),
                ("suffixe", res["suffixe"]),
            ]))

    FST_OUT.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Written to", FST_OUT, "(%d Einträge)" % len(entries))
    return entries


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
    L.append("| EINSTIMMIG | alle 3 Quellen einig (3/3) |")
    L.append("| VOTUM(T+Ps) | Tabula + Prusaspira → Prusaspira-Block (2/3) |")
    L.append("| VOTUM(T+Tw) | Tabula + Twanksta → Twanksta-Block (2/3) |")
    L.append("| VOTUM(Ps+Tw) | Prusaspira + Twanksta (Tabula fehlt) |")
    L.append("| EINZEL | nur Tabula vorhanden |")
    L.append("| LÜCKE | keine Quelle für diese Person |")
    L.append("| KEINE MEHRHEIT | keine Koalition – manuell entscheiden |")
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

    build_verb_fst_entries()


if __name__ == "__main__":
    main()
