#!/usr/bin/env python3
"""Werte vergleich.json aus und schlage je Inflektionszelle einen Goldstandard vor.

Liest die rohen, source-major geparsten Formen aus `vergleich.json` (erzeugt von
compare_sources.py) und klassifiziert die Quellabweichungen in drei Kategorien:

  1. ORTHOGRAPHIE – gleiche Form, nur Makron (≈len) oder Diakritika/Palatalisierung (≈dia).
                    Morphotaktisch irrelevant; eine Schreibung wird gewählt.
  2. VARIATION    – echte Formdivergenz (≠). Goldstandard-Vorschlag per Mehrheitsvotum (2/3),
                    Mažiulis-Fehlerformen werden ausgeschlossen (FEHLER).
  3. GENDER-MISMATCH – Quellen weisen demselben Lemma unterschiedliche Genera zu
                    (jede Quelle genau ein Genus, aber uneinig). Mehrheits-Genus als Vorschlag;
                    die Formen werden für den Zellvergleich auf das Mehrheits-Genus geflacht.

Output: GOLDSTANDARD.md (menschenlesbares Review-Dokument).
Kein MCP-Check (MCP = Twanksta = dritte Quelle, eigene Fehler) – reines Mehrheitsvotum.
"""
import json
import re
import unicodedata
from collections import Counter, OrderedDict
from pathlib import Path

IN = Path("vergleich.json")
OUT = Path("GOLDSTANDARD.md")
JSON_OUT = Path("goldstandard.json")

SRC = ["Tabula", "Prusaspira", "Twanksta"]
CASES = ["Nom", "Gen", "Dat", "Akk"]
NUMS = ["sg", "pl"]
CELLS = ["%s %s" % (c, n) for c in CASES for n in NUMS]

# Von Mažiulis (Historical Grammar §§59,102) bzw. TABVLA als nachweisliche Fehlerformen
# markiert. Schlüssel = fehlerhafte Form (gefoldet), Wert = (korrekte Form, §-Hinweis).
MAZIULIS_FEHLER = {
    "schisman": ("schisman→schism(an)", "§102 (Abel-Will-Zusatz -n)"),
    "gubans": ("gubans→gūbans", "§102"),
    "kirki": ("kīrki→kīrkis", "§102 (Gen.Sg.)"),
    "sounons": ("sounons→sounos", "§59"),
    "mistamans": ("mīstamans→mestammans", "TABVLA-Fehler, vgl. P35 mēstan"),
}

# Manuelle editorische Goldwahl pro Paradigma (siehe README „Editorische
# Einzelentscheidungen"). Überstimmt das Votum für echte 3-Wege-Konflikte.
#   source   = bevorzugte Quelle (Goldform je Zelle daraus)
#   genders  = (optional) nur diese Genera behalten; übrige werden verworfen
#   note     = Hinweis (erscheint in der Tabelle, verweist auf README)
MANUAL_GOLD = {
    "29": {"source": "Prusaspira",
           "note": "swint-Stamm (Prusaspira) – korpusweit am verbreitetsten; siehe README"},
    "54": {"source": "Prusaspira", "genders": ["m"], "cells": {"Dat sg": "pekūrei"},
           "note": "Mažiulis widerlegt Tabula (-jas regelhaft = -es, nicht -is); nur maskulin "
                   "(f = Parsing-Artefakt, nicht Klasse 54); Dat sg = pekūrei (-ei wie bei allen "
                   "anderen Lemmata der Klasse 54); siehe README"},
}

MACRON = str.maketrans("āēīōūĀĒĪŌŪ", "aeiouAEIOU")


def canon(s):
    """Whitespace um Slash-Varianten vereinheitlichen: 'a / b' → 'a/b' (Twanksta-Schreibweise)."""
    return re.sub(r"\s*/\s*", "/", s.strip())


def strip_macron(s):
    return s.translate(MACRON)


def fold(s):
    """Skelett ohne Makron, Diakritika und Palatalisierung, lowercase."""
    s = strip_macron(s)
    s = unicodedata.normalize("NFD", s)
    return "".join(c for c in s if not unicodedata.combining(c)).lower()


def depalatal(s):
    """Palatal-Diakritika entfernen (š,ž,ģ,ķ,ļ,ņ,ŕ,ŗ …), Makron (U+0304) behalten, lowercase."""
    nfd = unicodedata.normalize("NFD", s)
    kept = "".join(c for c in nfd if not unicodedata.combining(c) or ord(c) == 0x0304)
    return unicodedata.normalize("NFC", kept).lower()


def diacritic_count(s):
    return sum(1 for c in unicodedata.normalize("NFD", s) if unicodedata.combining(c))


# ── Orthographische Regelschicht (vor dem Votum, Mažiulis §§21–25, §122) ──────
# Richtung A – Palatalisierung: Twanksta schreibt sie als explizites j (sj=š, gj=ģ,
#   kj=ķ, …; §21 "Pr. *j is not marked after the letter i"). fold() reduziert die
#   präkomponierten Palatale bereits auf die Basis; nojot() tilgt zusätzlich das j.
def nojot(s):
    # Nur isoliertes Palatalisierungs-j tilgen; jj = Gemination (echte Variation) bleibt.
    return re.sub(r"(?<!j)j(?!j)", "", s)


# Richtung B – weiche Endung (§122 Fn54: -ian/-ien/-in = Allomorphe derselben
#   weichen Endung). Der Endungsvokal a/e/i wird am Wortende auf 'I' neutralisiert.
#   Stamminterne Vokale (= echte Vokalgrad-Variation ī/ē, ū/ā) bleiben unberührt,
#   da die Regeln am Wortende verankert sind.
_SOFT = [
    (re.compile(r"[aei](ns)$"), r"I\1"),    # Akk.Pl  -ans/-ins/-ens
    (re.compile(r"[aei](mans)$"), r"I\1"),  # Dat.Pl  -amans/-imans/-emans
    (re.compile(r"[aei](n)$"), r"I\1"),     # Akk/Gen.Sg  -an/-in/-en
    (re.compile(r"[aei](s)$"), r"I\1"),     # Gen.Sg/Nom.Pl  -as/-es/-is
    (re.compile(r"[ae](i)$"), r"I\1"),      # Dat.Sg/Nom.Pl  -ai/-ei
]


def soft_ending(s):
    for rx, rep in _SOFT:
        s2 = rx.sub(rep, s)
        if s2 != s:
            return s2
    return s


def ortho_norm(s):
    """Vollständige Regelschicht: fold (Länge/Diakritika) + A (Palatal-j) + B (weiche Endung)."""
    return soft_ending(nojot(fold(s)))


def applied_rule(forms):
    """Auf welcher Regelstufe fallen die Formen zusammen? Für die Tabellen-Spalte 'Regel'."""
    vals = list(forms.values())
    if len({fold(v) for v in vals}) == 1:
        return "≈ Schreibung (Länge/Diakritika)"
    if len({nojot(fold(v)) for v in vals}) == 1:
        return "A: Palatal-j (sj=š, gj=ģ)"
    if len({ortho_norm(v) for v in vals}) == 1:
        return "B: weiche Endung (-an/-in/-en)"
    return ""


def pick_ortho(forms):
    """Orthografie-Konvention wählen: Mehrheitsschreibung, sonst die diakritikreichste
    (informativste) Form; Gleichstand → Quellreihenfolge Tabula>Prusaspira>Twanksta."""
    raws = list(forms.values())
    cnt = Counter(raws)
    top, n = cnt.most_common(1)[0]
    if n >= 2:
        return top
    # keine Mehrheit: meiste Diakritika, dann Quellreihenfolge
    for s in SRC:
        if s in forms:
            forms_sorted = sorted(forms.items(), key=lambda kv: (-diacritic_count(kv[1]), SRC.index(kv[0])))
            return forms_sorted[0][1]
    return raws[0]


def vote(forms):
    """Mehrheitsvotum über die orthographisch normalisierten Formen.
    Gibt (gold, klassifikation, hinweis)."""
    # Fehlerformen erkennen
    fehler_src = {s: v for s, v in forms.items() if fold(v) in MAZIULIS_FEHLER}
    clean = {s: v for s, v in forms.items() if s not in fehler_src}
    pool = clean if clean else forms

    norms = Counter(ortho_norm(v) for v in pool.values())
    top, n = norms.most_common(1)[0]
    cands = {s: v for s, v in pool.items() if ortho_norm(v) == top}
    gold = pick_ortho(cands) if cands else "?"

    if fehler_src:
        hints = list(dict.fromkeys(MAZIULIS_FEHLER[fold(v)][1] for v in fehler_src.values()))
        wrong = ", ".join(sorted(set(fehler_src.values())))
        return gold, "FEHLER", "%s falsch (%s)" % (wrong, "; ".join(hints))
    if n >= 2:
        return gold, "VOTUM", ""
    return "?", "KEINE MEHRHEIT", "alle Quellen verschieden – manuell entscheiden"


def categorize(forms):
    """Klassifiziere eine Zelle. Das Votum läuft NACH der orthographischen Regelschicht.
    Gibt None (keine Divergenz / zu wenig Daten) oder (kategorie, regel, gold, klass, hinweis)."""
    if len(forms) < 2:
        return None  # Abdeckungslücke, keine Abweichung
    if len(set(forms.values())) == 1:
        return None  # volle Übereinstimmung (Rohformen identisch)
    if len({ortho_norm(v) for v in forms.values()}) == 1:
        # Nach Anwendung der Regelschicht identisch → reine Orthographie-Abweichung
        return ("ORTHO", applied_rule(forms), pick_ortho(forms), "", "")
    # Auch nach Normalisierung verschieden → echte Variation, Votum entscheidet
    gold, klass, hint = vote(forms)
    return ("VAR", "", gold, klass, hint)


def par_sort_key(key):
    num = key.split("_", 1)[0]
    head = "".join(ch for ch in num if ch.isdigit())
    return (int(head) if head else 0, num)


def cell_row(forms):
    return [forms.get(s, "—") for s in SRC]


# ── Geteilte Genus-Iteration (von MD- und JSON-Pass genutzt) ─────────────────
def detect_gmismatch(e):
    """Gibt (is_mismatch, gmap, maj_genus). Mismatch: jede vorhandene Quelle genau ein
    Genus, aber uneinig."""
    src_genders = {s: list(e.get(s, {}).keys()) for s in SRC}
    present = [s for s in SRC if src_genders[s]]
    single = present and all(len(src_genders[s]) == 1 for s in present)
    gset = {src_genders[s][0] for s in present} if single else set()
    if single and len(present) >= 2 and len(gset) > 1:
        gmap = {s: src_genders[s][0] for s in present}
        maj_g = Counter(src_genders[s][0] for s in present).most_common(1)[0][0]
        return True, gmap, maj_g
    return False, None, None


def iter_paradigm_cells(e, manual):
    """Yield (genus_label, genus_key, cell, forms) mit canon'd Quellformen je Zelle.
    Kapselt Gender-Mismatch-Flachung (nur Mehrheits-Genus) und manuellen Genus-Drop."""
    is_mm, _, maj_g = detect_gmismatch(e)
    if is_mm:
        present_maj = [s for s in SRC if e.get(s, {}).get(maj_g)]
        for cell in CELLS:
            forms = OrderedDict()
            for s in present_maj:
                v = e[s][maj_g].get(cell)
                if v:
                    forms[s] = canon(v)
            yield maj_g + "*", maj_g, cell, forms
        return
    all_g = []
    for s in SRC:
        for g in e.get(s, {}):
            if g not in all_g:
                all_g.append(g)
    for g in all_g:
        if manual and "genders" in manual and g not in manual["genders"]:
            continue
        for cell in CELLS:
            forms = OrderedDict()
            for s in SRC:
                v = e.get(s, {}).get(g, {}).get(cell)
                if v:
                    forms[s] = canon(v)
            yield (g if g else "–"), g, cell, forms


def manual_gold(manual, forms, cell):
    """Editorische Goldwahl: zellenspezifischer Override (manual['cells']), sonst die
    bevorzugte Quelle (manual['source'])."""
    cells = manual.get("cells", {})
    if cell in cells:
        return cells[cell]
    return forms.get(manual["source"]) or (pick_ortho(forms) if forms else None)


def resolve_gold(forms, manual, cell):
    """Goldform für EINE Zelle – auch bei Übereinstimmung/Einzelquelle. Gibt (gold, status)."""
    if manual and cell in manual.get("cells", {}):
        return manual["cells"][cell], "manuell"
    if not forms:
        return None, None
    if manual:
        return manual_gold(manual, forms, cell), "manuell"
    if len(forms) == 1:
        return next(iter(forms.values())), "single"
    if len(set(forms.values())) == 1:
        return next(iter(forms.values())), "agree"
    cat, _, gold, klass, _ = categorize(forms)
    if gold == "?":
        return None, "offen"
    return gold, ("ortho" if cat == "ORTHO" else klass.lower())


# ── Stamm + JSON ────────────────────────────────────────────────────────────
def stem_len(forms):
    """Längste gemeinsame Präfixlänge, makron- UND palatalisierungs-insensitiv (fold).
    So bricht weder Vokallänge (ī/i) noch Palatalisierung (ŗ/r, š/s) den Stamm."""
    sk = [fold(f) for f in forms if f]
    if not sk:
        return 0
    n = min(len(x) for x in sk)
    i = 0
    while i < n and len({x[i] for x in sk}) == 1:
        i += 1
    return i


def stem_representative(by_g):
    """Form, deren Schreibung (inkl. Makron) den Stamm liefert: maskulines Nom sg (= Lemma-
    Zitierform), sonst Nom sg / Nom pl eines anderen Genus, sonst irgendeine Zelle."""
    for g in ("m", "f", "n", ""):
        if g in by_g and by_g[g].get("Nom sg"):
            return by_g[g]["Nom sg"]
    for cell in ("Nom sg", "Nom pl"):
        for cells in by_g.values():
            if cells.get(cell):
                return cells[cell]
    for cells in by_g.values():
        if cells:
            return next(iter(cells.values()))
    return ""


def build_gold(data):
    """Vollständige Goldstandard-Liste: ein Eintrag pro (Paradigma, Genus) mit Stamm + Suffixen.
    Der Stamm wird über ALLE Genera des Paradigmas gescannt und ist für alle Genera gleich."""
    entries = []
    for key in sorted(data, key=par_sort_key):
        e = data[key]
        par, lemma = e["paradigm"], e["lemma"]
        manual = MANUAL_GOLD.get(par)
        by_g = OrderedDict()
        for _, gkey, cell, forms in iter_paradigm_cells(e, manual):
            gold, _ = resolve_gold(forms, manual, cell)
            if gold is None:
                continue
            by_g.setdefault(gkey, OrderedDict())[cell] = gold
        if not by_g:
            continue
        # Gemeinsamer Stamm über alle Genera: makron- UND palatalisierungs-insensitiver LCP
        # aller Goldformen; nachgestellte (thematische) Vokale werden abgeschnitten, sodass
        # der Stamm auf einem Konsonanten endet (deren Länge steht dann im Suffix).
        all_golds = [g for cells in by_g.values() for g in cells.values()]
        L = stem_len(all_golds)
        rep = stem_representative(by_g)
        Lp = L
        while Lp > 0 and strip_macron(rep[Lp - 1]).lower() in "aeiou":
            Lp -= 1
        base = strip_macron(rep[:Lp]).lower()  # makronloses Skelett (Palatale bleiben)
        # Akzentfähige Vokalposition(en): Vokal, der in ≥1 Zelle lang (Makron) ist
        regions = [g[:Lp] for cells in by_g.values() for g in cells.values()]
        acc = {p for p in range(Lp)
               if base[p] in "aeiou" and any(r[p] != strip_macron(r[p]) for r in regions)}
        stamm = "".join(ch.upper() if p in acc else ch for p, ch in enumerate(base))
        for gkey, cells in by_g.items():
            suffixe = OrderedDict()
            for cell in CELLS:
                g = cells.get(cell)
                if g is None:
                    continue
                region = g[:Lp]
                entry = {"suffix": g[Lp:],
                         "betont": any(region[p] != strip_macron(region[p]) for p in acc)}
                if strip_macron(region).lower() != base:  # Stamm-Region palatalisiert
                    entry["palatize"] = True
                suffixe[cell] = entry
            entries.append(OrderedDict([
                ("paradigm", par), ("lemma", lemma), ("gender", gkey),
                ("stamm", stamm), ("suffixe", suffixe),
            ]))
    return entries


def write_json(entries):
    JSON_OUT.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Written to", JSON_OUT, "(%d Einträge)" % len(entries))


def main():
    data = json.load(open(IN, encoding="utf-8"))

    gender_mismatch = []   # (par, lemma, {src: genus}, maj_genus)
    variation = []         # (par, lemma, genus, cell, [T,P,Tw], regel, gold, klass, hint)
    ortho = []             # (par, lemma, genus, cell, [T,P,Tw], regel, gold)

    for key in sorted(data, key=par_sort_key):
        e = data[key]
        par, lemma = e["paradigm"], e["lemma"]
        manual = MANUAL_GOLD.get(par)

        is_mm, gmap, maj_g = detect_gmismatch(e)
        if is_mm:
            gender_mismatch.append((par, lemma, gmap, maj_g))

        for glabel, _, cell, forms in iter_paradigm_cells(e, manual):
            res = categorize(forms)
            if not res:
                continue
            row = cell_row(forms)
            if res[0] == "VAR":
                _, regel, gold, klass, hint = res
                if manual:  # editorische Goldwahl überstimmt das Votum
                    gold = manual_gold(manual, forms, cell)
                    klass, hint = "MANUELL", manual["note"]
                variation.append((par, lemma, glabel, cell, row, regel, gold, klass, hint))
            else:
                _, regel, gold, _, _ = res
                ortho.append((par, lemma, glabel, cell, row, regel, gold))

    write_md(data, gender_mismatch, variation, ortho)
    write_json(build_gold(data))


def write_md(data, gender_mismatch, variation, ortho):
    klass_counts = Counter(r[7] for r in variation)
    rule_counts = Counter(r[5] for r in ortho)
    L = []
    L.append("# Goldstandard – Quellabweichungen (Tabula / Prusaspira / Twanksta)\n")
    L.append("Generiert von `goldstandard.py` aus `vergleich.json`. "
             "Das Mehrheitsvotum (2/3) läuft **nach** der orthographischen Regelschicht "
             "(Mažiulis §§21–25 Palatalisierung, §122 weiche Endung): "
             "**A** Palatal-j (sj=š, gj=ģ …), **B** weiche Endung (-an/-in/-en). "
             "**Kein** MCP-Check (MCP = Twanksta). Echte Fehler vs. Allomorphe nach Mažiulis.\n")
    L.append("## Übersicht\n")
    L.append("| Kategorie | Anzahl |")
    L.append("|---|---|")
    L.append("| Paradigmen gesamt | %d |" % len(data))
    L.append("| **Gender-Mismatch** (Paradigmen) | %d |" % len(gender_mismatch))
    L.append("| **Variation** (Zellen, echte Entscheidung) | %d |" % len(variation))
    L.append("| &nbsp;&nbsp;– davon VOTUM (Mehrheit klar) | %d |" % klass_counts.get("VOTUM", 0))
    L.append("| &nbsp;&nbsp;– davon FEHLER (Mažiulis) | %d |" % klass_counts.get("FEHLER", 0))
    L.append("| &nbsp;&nbsp;– davon MANUELL (editorisch, s. README) | %d |" % klass_counts.get("MANUELL", 0))
    L.append("| &nbsp;&nbsp;– davon KEINE MEHRHEIT (offen) | %d |" % klass_counts.get("KEINE MEHRHEIT", 0))
    L.append("| **Orthographie** (Zellen, durch Regel gelöst) | %d |" % len(ortho))
    for rule, n in rule_counts.most_common():
        L.append("| &nbsp;&nbsp;– %s | %d |" % (rule or "—", n))
    L.append("")

    # 1. Gender-Mismatch
    L.append("## 1. Gender-Mismatch\n")
    L.append("Quellen weisen demselben Lemma unterschiedliche Genera zu. Morphotaktisch meist "
             "harmlos (steuert nur Kongruenz), außer bei echtem Klassenwechsel. "
             "Vorschlag = Mehrheits-Genus.\n")
    L.append("| Par | Lemma | Tabula | Prusaspira | Twanksta | Mehrheits-Genus |")
    L.append("|---|---|---|---|---|---|")
    for par, lemma, gmap, maj in gender_mismatch:
        L.append("| %s | %s | %s | %s | %s | **%s** |" % (
            par, lemma, gmap.get("Tabula", "–"), gmap.get("Prusaspira", "–"),
            gmap.get("Twanksta", "–"), maj))
    L.append("")

    # 2. Variation
    L.append("## 2. Variation (echte Formdivergenz, auch nach Regelschicht)\n")
    L.append("Differenz besteht **nach** der orthographischen Normalisierung fort → "
             "Goldstandard per Mehrheitsvotum. `*` am Genus = auf Mehrheits-Genus geflachte "
             "Gender-Mismatch-Zelle. Spalte **Review** für die finale Entscheidung.\n")
    L.append("| Par | Lemma | Genus | Kasus | Tabula | Prusaspira | Twanksta | Klassifik. | Goldstandard | Hinweis | Review |")
    L.append("|---|---|---|---|---|---|---|---|---|---|---|")
    for par, lemma, g, cell, row, regel, gold, klass, hint in variation:
        L.append("| %s | %s | %s | %s | %s | %s | %s | %s | **%s** | %s |  |" % (
            par, lemma, g, cell, row[0], row[1], row[2], klass, gold, hint))
    L.append("")

    # 3. Orthographie
    L.append("## 3. Orthographie-Abweichung (durch Regelschicht gelöst)\n")
    L.append("Nach Anwendung der Regel identisch → gleiches Morphem. Spalte **Regel** zeigt, "
             "welche Regel die Formen zusammenführt. Goldstandard = gewählte Schreibkonvention.\n")
    L.append("| Par | Lemma | Genus | Kasus | Tabula | Prusaspira | Twanksta | Regel | Goldstandard |")
    L.append("|---|---|---|---|---|---|---|---|---|")
    for par, lemma, g, cell, row, regel, gold in ortho:
        L.append("| %s | %s | %s | %s | %s | %s | %s | %s | **%s** |" % (
            par, lemma, g, cell, row[0], row[1], row[2], regel, gold))
    L.append("")

    OUT.write_text("\n".join(L), encoding="utf-8")
    print("Written to", OUT)
    print("  Gender-Mismatch: %d Paradigmen" % len(gender_mismatch))
    print("  Variation:       %d Zellen (%s)" % (len(variation), dict(klass_counts)))
    print("  Orthographie:    %d Zellen" % len(ortho))


if __name__ == "__main__":
    main()
