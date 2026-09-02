"""Kompatibilitäts-Survey: passen die Twanksta-Nomen in ein Stamm+Endung-Modell?

Statt Vollformen zu listen (lexc/nouns.lexc) fragt dieses Werkzeug: Wie weit
lässt sich der Twanksta-Nominaldatensatz *generativ* nachbauen — EIN gespeicherter
Stamm plus fester Endungssatz je Paradigma, exakt bis zur Makronsetzung? Es lernt
das Modell pro Twanksta-Paradigma aus den Daten und testet es per Rekonstruktion.

Vorgehen je Deklinationsblock (8 Formen: Sg/Pl × Nom/Gen/Dat/Akk):

  1. Endungssatz inferieren: obliquer Stamm = längster gemeinsamer Präfix der 7
     obliquen Formen (Nom.Sg. ausgenommen) auf MAKRON-normalisierten Formen —
     so verschiebt eine Akzent/Makron-Alternation im Stamm die Endungsgrenze
     nicht. Der dominante Endungssatz je Paradigma ist damit stabil.
  2. Rekonstruktion testen: als Basisstamm dient der ROHE Gen.Sg.-Stamm (trägt
     den Grundakzent). Vorhersage = Basisstamm + gelernte Endung. Stimmt sie mit
     der echten Form überein, ist die Form rein konkatenativ generierbar; stimmt
     sie erst nach Makron-Normalisierung, fehlt genau eine Akzent/Makron-Regel
     (vgl. gen/stress.regex — dāngu+mmans → dangummans).

Paradigmen-Klassifikation (absteigende Regelmäßigkeit, Schwelle THRESHOLD):

  CLEAN       Endungssatz + Nom.Sg. reproduzieren die Formen exakt → heute
              rein konkatenativ generierbar.
  NOMSG-ALT   oblique Formen exakt, aber Nom.Sg. braucht eine Ableitungsregel.
  MORPHOPHON  Formen erst nach Makron-Normalisierung exakt → eine Akzent/Makron-
              Regelstufe fehlt (betrifft z. B. die beweglichen u-Stämme).
  IRREGULAR   kein dominanter Endungssatz — echter Rest.

    uv run python gen/paradigm_survey.py            # Übersichtstabelle + Rollup
    uv run python gen/paradigm_survey.py 42 43       # Detail für Paradigmen
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from prussian_fst.gen_lexc import classify  # noqa: E402

TWANKSTA = ROOT.parent / "corpus" / "parsed" / "twanksta_entries.json"

# Anteil der Blöcke, den die dominante Signatur / Rekonstruktion erreichen muss.
THRESHOLD = 0.85

CASE_ABBR = {"Nominative": "Nom", "Genitive": "Gen",
             "Dative": "Dat", "Accusative": "Akk"}
MACRONS = str.maketrans("āēīōū", "aeiou")


def morphnorm(s: str) -> str:
    """Neutralisiert die bewegliche Betonung: Makronverlust + Degemination.

    Beide sind Marker des Akzentwechsels in Twanksta (Makron fällt, Geminate
    vereinfacht sich in akzentverschobenen Slots). Wer hierunter übereinstimmt,
    ist mit EINER Akzent/Morphophonologie-Regelstufe reproduzierbar.
    """
    return re.sub(r"(.)\1", r"\1", s.translate(MACRONS))


def stem_class(endings_canon: tuple, base_stem: str) -> str:
    """Kompaktes Deklinationsklassen-Label aus der kanonischen Signatur.

    Themavokal aus der (klassendiagnostischen) Gen.Sg.-Endung -as/-is/-es …
    bzw. dem Stammauslaut bei endungslosem -s (u-Stamm dāngu-s vs. Konsonant-
    stamm); jo-Präfix bei palatalisierter Endung (-jas/-ju …).
    """
    gen = endings_canon[OBLIQUE_SLOTS.index("Sg+Gen")]
    jo = gen.startswith("j")
    core = gen[1:] if jo else gen
    theme = {"as": "a", "is": "i", "es": "e", "os": "o"}.get(core)
    if theme is None:
        if core == "s":
            theme = base_stem[-1] if base_stem[-1:] in "aeiou" else "kons"
        else:
            theme = core or "?"
    return ("jo-" if jo else "") + theme

# Slot-Reihenfolge der 8 Formen; Nom.Sg. wird gesondert behandelt.
SLOTS = [f"{num}+{CASE_ABBR[c]}"
         for c in ("Nominative", "Genitive", "Dative", "Accusative")
         for num in ("Sg", "Pl")]
OBLIQUE_SLOTS = [s for s in SLOTS if s != "Sg+Nom"]
GEN_SG = OBLIQUE_SLOTS.index("Sg+Gen")  # Basisstamm-Referenz (Grundakzent)


def lcp(strings: list[str]) -> str:
    """Längster gemeinsamer Präfix (leere Strings ignoriert)."""
    xs = [s for s in strings if s]
    if not xs:
        return ""
    p = xs[0]
    for s in xs[1:]:
        i = 0
        while i < len(p) and i < len(s) and p[i] == s[i]:
            i += 1
        p = p[:i]
    return p


def primary(cell: str) -> str:
    """Erste Variante einer ` / `-getrennten Zelle (dīmenes / dīmenjai)."""
    return (cell or "").split(" / ")[0].strip()


def block_forms(block: dict) -> dict[str, str]:
    """slot -> Form (erste Variante) für einen declension-Block."""
    out: dict[str, str] = {}
    for c in block.get("cases", []):
        case = CASE_ABBR.get(c.get("case", ""))
        if not case:
            continue
        out[f"Sg+{case}"] = primary(c.get("singular"))
        out[f"Pl+{case}"] = primary(c.get("plural"))
    return out


def analyze_block(forms: dict[str, str]) -> dict | None:
    """Inferiere Endungssatz, Basisstamm, jo-Klasse und Nom.Sg.-Regel.

    Die Stammgrenze wird auf der KANONISCHEN Form (makron-neutral UND
    degeminiert) bestimmt, damit Akzentalternationen (Makronverlust,
    Degemination) sie nicht verschieben — sonst zerbricht sie z. B. bei
    jo-Stämmen mit Basis-Geminate (azzegjas vs. azegjāi).
    """
    oblique = [forms.get(s, "") for s in OBLIQUE_SLOTS]
    if not all(oblique):
        return None
    canon = [morphnorm(f) for f in oblique]
    stem_c = lcp(canon)
    # jo-/Palatal-Klasse: ein gemeinsames stammauslautendes j gehört zur
    # Endung, nicht zum Stamm (rūsj- → Stamm rūs-, Endungen -jas/-ju/…).
    jo = stem_c.endswith("j")
    if jo:
        stem_c = stem_c[:-1]
    length = len(stem_c)
    endings_canon = tuple(c[length:] for c in canon)      # kanonische Endungen

    # Basisstamm (roh, mit Grundakzent) aus dem Gen.Sg.: dieser Slot trägt
    # keinen verschobenen Akzent, seine rohe Endung ist so lang wie die
    # kanonische. Rohe Endungen der übrigen Slots relativ dazu (in akzent-
    # verschobenen Slots ggf. fehlausgerichtet — für den Exakt-Test genügt's,
    # da solche Blöcke ohnehin nur modulo Morphophonologie stimmen).
    base_stem = oblique[GEN_SG][:len(oblique[GEN_SG]) - len(endings_canon[GEN_SG])]
    endings_raw = tuple(f[len(base_stem):] for f in oblique)

    nomsg = morphnorm(forms.get("Sg+Nom", ""))
    stem_n = morphnorm(base_stem)
    common = len(lcp([stem_n, nomsg]))
    nomsg_rule = (stem_n[common:], nomsg[common:])

    return {"base_stem": base_stem, "endings": endings_canon,
            "endings_raw": endings_raw, "jo": jo,
            "nomsg_rule": nomsg_rule, "oblique": oblique}


def survey() -> dict[str, dict]:
    entries = json.loads(TWANKSTA.read_text())
    per_para: dict[str, list[dict]] = defaultdict(list)
    for e in entries:
        if classify(e) not in ("noun", "proper_noun"):
            continue
        for block in e.get("forms", {}).get("declension", []):
            info = analyze_block(block_forms(block))
            if info is None:
                continue
            info["word"] = e.get("word", "")
            per_para[e.get("paradigm", "?")].append(info)

    result: dict[str, dict] = {}
    for para, blocks in per_para.items():
        n = len(blocks)
        # Gelernter Endungssatz = häufigste KANONISCHE Signatur; als konkrete
        # (rohe) Endungen der häufigste rohe Vertreter innerhalb dieser Klasse.
        canon_sigs = Counter(b["endings"] for b in blocks)
        dom_canon, dom_canon_n = canon_sigs.most_common(1)[0]
        in_dom = [b for b in blocks if b["endings"] == dom_canon]
        learned_raw = Counter(b["endings_raw"] for b in in_dom).most_common(1)[0][0]
        klasse = stem_class(dom_canon, in_dom[0]["base_stem"])
        nom_rules = Counter(b["nomsg_rule"] for b in blocks)
        learned_nom, nom_n = nom_rules.most_common(1)[0]

        # Rekonstruktion: Basisstamm + gelernte Endung == echte Form?
        #   exact : rohe Endungen, Zeichen für Zeichen (rein konkatenativ)
        #   morph : kanonische Endungen modulo Akzent-Morphophonologie
        exact = morph = 0
        for b in blocks:
            if all(b["base_stem"] + e == a
                   for e, a in zip(learned_raw, b["oblique"])):
                exact += 1
            if all(morphnorm(b["base_stem"] + e) == morphnorm(a)
                   for e, a in zip(dom_canon, b["oblique"])):
                morph += 1

        end_share = dom_canon_n / n    # Endungen (kanonisch) lernbar?
        exact_share = exact / n        # exakt konkatenativ reproduzierbar?
        morph_share = morph / n        # reproduzierbar modulo Akzent-Morphophon.?
        nom_share = nom_n / n

        if exact_share >= THRESHOLD and nom_share >= THRESHOLD:
            cls = "CLEAN"
        elif exact_share < THRESHOLD and morph_share >= THRESHOLD:
            cls = "MORPHOPHON"
        elif exact_share >= THRESHOLD:
            cls = "NOMSG-ALT"
        else:
            cls = "IRREGULAR"

        result[para] = {
            "n": n, "class": cls, "klasse": klasse, "end_share": end_share,
            "exact_share": exact_share, "morph_share": morph_share,
            "nom_share": nom_share, "endings": learned_raw,
            "nomsg_rule": learned_nom,
            "examples": [b["word"] for b in blocks[:6]], "blocks": blocks,
        }
    return result


def print_overview(result: dict[str, dict]) -> None:
    total = sum(r["n"] for r in result.values())
    print(f"Nomen-Deklinationsblöcke: {total}   Paradigmen: {len(result)}\n")
    print(f"{'para':>5} {'n':>5} {'end%':>5} {'exact':>6} {'+mph':>5} {'nom%':>5}  "
          f"{'Klasse':<7} {'Regelstufe':<11} Beispiele")
    for para, r in sorted(result.items(), key=lambda kv: -kv[1]["n"]):
        print(f"{para:>5} {r['n']:>5} {r['end_share']*100:>4.0f}% "
              f"{r['exact_share']*100:>5.0f}% {r['morph_share']*100:>4.0f}% "
              f"{r['nom_share']*100:>4.0f}%  {r['klasse']:<7} {r['class']:<11} "
              f"{', '.join(r['examples'][:2])}")

    rollup: Counter = Counter()
    for r in result.values():
        rollup[r["class"]] += r["n"]
    print("\nRollup (Anteil der Nomen-Blöcke je Regelstufe):")
    for cls in ("CLEAN", "NOMSG-ALT", "MORPHOPHON", "IRREGULAR"):
        n = rollup[cls]
        print(f"  {cls:<11} {n:>5}  {100*n/total:>4.0f}%")
    gen = rollup["CLEAN"] + rollup["NOMSG-ALT"] + rollup["MORPHOPHON"]
    print(f"\n  generierbar mit Stamm+Endung (+ Nom.Sg-/Makron-Regel): "
          f"{100*gen/total:.0f}%")


def print_detail(result: dict[str, dict], paras: list[str]) -> None:
    for para in paras:
        r = result.get(para)
        if r is None:
            print(f"\n=== Paradigma {para}: nicht gefunden ===")
            continue
        print(f"\n=== Paradigma {para} — Klasse {r['klasse']} / {r['class']} "
              f"(n={r['n']}, end={r['end_share']*100:.0f}%, "
              f"exact={r['exact_share']*100:.0f}%, +mph={r['morph_share']*100:.0f}%, "
              f"nom={r['nom_share']*100:.0f}%) ===")
        drop, suf = r["nomsg_rule"]
        print(f"  Nom.Sg-Regel: Stamm − {drop!r} + {suf!r}")
        print("  gelernte Endungen (roh):")
        for slot, end in zip(OBLIQUE_SLOTS, r["endings"]):
            print(f"    {slot:<8} -{end}")
        outliers = [b for b in r["blocks"]
                    if not all(b["base_stem"] + e == a
                               for e, a in zip(r["endings"], b["oblique"]))]
        if outliers:
            print(f"  nicht exakt rekonstruierbar ({len(outliers)}), erste 8:")
            for b in outliers[:8]:
                print(f"    {b['word']:>16}  Stamm={b['base_stem']!r}  "
                      f"Formen={b['oblique']}")


def main() -> None:
    result = survey()
    if len(sys.argv) > 1:
        print_detail(result, sys.argv[1:])
    else:
        print_overview(result)


if __name__ == "__main__":
    main()
