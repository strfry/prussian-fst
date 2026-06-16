# HFST-Spike: generalisierende Leniency — pyfoma, HFST, und der Round-Trip

**Ausgangsfrage.** Schritt 3 des FST-Plans (generalisierende Ortho-/Leniency-Schicht
`lenient = ortho_variants ∘ analyser`) wurde nicht als Regelschicht gebaut, weil pyfomas
`.`-Wildcard-Arcs in verschachtelter Komposition Probleme machten (Prototyp `R_ELAKTR`;
s. `src/prussian/fst/phonology.py`). Diese Notiz klärt, was genau die Grenze ist, ob HFST
stärker ist, und wie sich beide Welten kombinieren lassen.

---

## Kurzfassung (Verdikt)

1. **Leniency geht in reinem pyfoma** — generalisierend — wenn man die spellrelax-Regel
   **sequentiell** anwendet (`rule.generate(w)` → `ana.analyze(v)`) statt sie zu komponieren.
2. Die **einzige** echte pyfoma-Grenze ist die **Komposition** einer Wildcard-Regel mit dem
   Analyser zu *einem* Transduktor (`rule @ ana → ∅`, beide Richtungen).
3. **HFST komponiert das sauber** (optionale Replace `(->)` + Unknown-Symbol-Harmonisierung)
   zu **einem** `lenient.fst` — und dieses Ergebnis lässt sich **zurück in pyfoma** holen
   (über foma-Format). HFST dient damit als reine **Kompositions-Engine**.
4. Daraus folgt: pyfoma- und HFST-Variante teilen **eine Quelle** und **einen
   Basis-Analyser**; sie unterscheiden sich nur darin, *wie* die spellrelax-Schicht
   angewandt wird (sequentiell vs. komponiert).

Es ist also **keine** prinzipielle pyfoma-Schwäche und **kein** Voll-Port nötig.

---

## Werkzeuglage

- python-hfst 3.15.4 im **System-Python 3.14** (`/usr/lib/python3.14/site-packages/hfst`,
  pacman `python-hfst`); pyfoma im **uv-venv 3.13**. Zwei Interpreter → Datei-Brücke.
- **Build immer mit pypy:** `PYTHONPATH=src pypy3 -m prussian.fst.build` (CPython-Komposition
  ist zäh). Erzeugt `build/analyser.{fst,att}` (att nach Reflexiv-Cleanup space-frei).
- Orakel: 525 eindeutige nominale Gold-Oberflächen (`/tmp/hfst-spike/gold_forms.txt`).
- Testregel: generalisierende `-as/-us`-Ortho (BACKLOG) — Epenthese `a` vor finalem `s`.
  Der Analyser kennt die `-as`-Form (`milimētras`); akzeptiert werden soll `-s` (`milimētrs`).

---

## Befund im Detail

### A. Direktvergleich der Anwendungsarten

| Ansatz | erhalten | Variante mappt? | ein FST? |
|---|---|---|---|
| **pyfoma sequentiell** (`rule.generate`→`ana.analyze`) | 525/525 | **ja** | nein |
| pyfoma `(Regel ∪ Identität)` **komponiert** | 525/525 | **nein** (Komposition verliert den Wildcard-Pfad) | ja |
| **HFST** `[. .] (->) a \|\| ? _ s .#.` komponiert | 525/525 | **ja** | ja |
| **HFST komponiert → foma → pyfoma** (Round-Trip) | 525/525 | **ja** | ja |

Methoden-Fußnote: ein früherer Test mit einer **obligatorischen** pyfoma-Regel
(`$^rewrite('':'a' / . _ s)` ohne Identitäts-Union) verlor 395/525 Pfade. Das ist korrekte
FST-Semantik (obligatorische Epenthese zerstört alle `-s`-Formen), **kein** pyfoma-Defekt:
pyfomas `$^rewrite` ist obligatorisch (Flags nur `longest/leftmost/shortest/outputcontexts`),
optionale Ersetzung baut man als `Regel ∪ Identität`.

### B. Die Grenze ist genau die Komposition

Beide Teile funktionieren in pyfoma einzeln:
```
rule("milimētrs") → "milimētras"        # Regel allein, generalisiert (deckt Makron/Palatal)
ana.analyze("milimētras") → milimētras+N+Msc+Sg+Nom
```
aber komponiert nicht:
```
(rule @ ana).analyze("milimētrs") → []   # auch (ana @ rule) → []
```
pyfoma harmonisiert die `.`-Arcs der Regel beim Komponieren mit dem (anders alphabetisierten)
Analyser nicht verlässlich. HFST hat dafür `@_UNKNOWN_@`/`@_IDENTITY_@`-Arcs und mature
`(->)`-Semantik — Reife/Idiom (Giella betreibt so dutzende Sprachen), keine prinzipielle
Mehrmächtigkeit.

### C. Round-Trip: HFST nur als Kompositions-Engine

Das in HFST komponierte `lenient.fst` läuft danach **nativ in pyfoma**:
```
milimētrs          -> milimētras+N+Msc+Sg+Nom
elektrōmagnētisks  -> elektrōmagnētiskas+A+Msc+Sg+Nom   # zwei 's', korrekt (anker .#.)
wīrs · kūģu · smeīja+Refl                                # alle ok
Regression: 525/525, 0 verloren, Variante mappt ✓
```
Pipeline:
1. Basis-Analyser in pyfoma bauen (heutige Pipeline) → `build/analyser.att`.
2. HFST (System-py3.14): `AttReader`+`invert`, spellrelax als optionale `(->)`-Replace,
   `compose`, `minimize`.
3. Export: `HfstOutputStream` → `.hfst` → `hfst-fst2fst -f foma -b` → `.foma`.
4. pyfoma (uv-3.13): `FST.from_fomastring(open(...).read())`.

**Interop-Hinweise (wichtig für Reproduktion):**
- pyfomas `FST.load_foma()` verschluckt sich an HFSTs foma-Header (sucht den Netznamen in
  `##props##`, Token 12, den HFST nicht schreibt) → stattdessen **`FST.from_fomastring()`**
  auf dem (un-gzippten) Text verwenden.
- HFSTs `-f foma -b` schreibt **un-komprimiert**; `from_fomastring` will den reinen Text.
- **Anwendungsrichtung:** je nach `invert` im HFST-Schritt liegt die Analyse auf pyfomas
  `generate()`- statt `analyze()`-Seite. Funktional identisch; ggf. im HFST-Build nicht
  invertieren oder in pyfoma nach dem Laden `fst.invert()` — kurz prüfen, welche Seite passt.
- HFSTs Identity-Arcs überleben den Transfer: pyfoma mappt `@_IDENTITY_SYMBOL_@`/
  `@_UNKNOWN_SYMBOL_@` auf sein `.` (s. `pyfoma/fst.py`).

### D. Wildcard ist der richtige Ansatz

Wildcard-Kontext-Regeln sind genau Giellas `orthography/spellrelax.regex`. Die grobe pyfoma-
Testregel `'':'a' / . _ s` über-appliziert (zwei `s` in `elektrōmagnētisks` → `[]`); die
**wortend-verankerte** HFST-Regel (`?  _ s .#.`) macht es richtig. Das ist Regel-Design,
kein Tool-Problem. Konkrete spellrelax-Regeln (aus `ORTHO_RULES.md §3` + BACKLOG):

| Regel | Beispiel |
|---|---|
| `-as/-us ↔ -s` Nom sg (P25/P32) | milimētras ↔ milimētrs |
| Twanksta-j | `-in↔-jan`, `-es↔-jas` |
| elektr- ↔ elaktr- | elektrō ↔ elaktrō |
| ī↔ē, -tas↔-ts, jj↔ā/w | Partizipien |

---

## Architektur: eine Quelle, zwei Backends

Die pyfoma- und die HFST-Variante divergieren an der **Quelle gar nicht**:

```
                    data/gold/*.json                (EINE Quelle)
                          │  morphology/{nominals,verbs}.py → lexd.py
                          ▼
                  morphotactics.lexd
                          │  pyfoma.lexd ∘ phonology.py
                          ▼
              build/analyser.fst   (Basis-Analyser, EINMAL abgeleitet)
                    │                         │  Export .att/.foma
       spellrelax   │ sequentiell             │  spellrelax komponiert
       (rule.generate→analyze)                ▼
                    ▼                   HFST (->)  →  lenient.fst  →  zurück nach pyfoma
              pyfoma-lenient (H1)            HFST/Hybrid-lenient (H2)
```

- **Morphotaktik + Basis-Phonologie:** single-source (`gold → lexd → analyser`), backend-neutral.
- **spellrelax-Schicht:** dieselben wenigen Regeln, anwendbar als (H1) sequentiell in pyfoma
  oder (H2) komponiert in HFST → optional zurück nach pyfoma. Die Regel-**Spec** selbst kann
  einmal deklarativ gehalten und in beide Notationen (`$^rewrite` / `(->)`) emittiert werden.

### Optionen (Entscheidung bewusst offen)

- **H1 — pyfoma sequentiell:** kleinster Eingriff, kein HFST, generalisiert sofort;
  `lenient` ist eine Lookup-Funktion statt eines Einzel-FST.
- **H2 — Hybrid (HFST komponiert, foma-Round-Trip):** ein Einzel-`lenient.fst`, das in pyfoma
  läuft; HFST nur im Build. Zweiter Interpreter + Interop-Sorgfalt (s. C).
- **H3 — voll HFST/twolc:** nativer Giella-Stack wie `lang-lit`/`lang-lav`; reproduzierbar/
  publikabel, größter Umbau.

---

## Reproduktion

Skripte liegen (ephemer) in `/tmp/hfst-spike/`: `gen_gold.py`, `spike.py`, `export.py`.

```bash
# 0) Build (pypy) → build/analyser.{fst,att}
PYTHONPATH=src pypy3 -m prussian.fst.build

# 1) Goldformen-Orakel (uv/pyfoma) → /tmp/hfst-spike/gold_forms.txt
uv run python /tmp/hfst-spike/gen_gold.py

# 2a) pyfoma SEQUENTIELL (generalisiert, kein HFST):
uv run python - <<'PY'
from pyfoma import FST
ana  = FST.load("build/analyser.fst")
rule = FST.re("$^rewrite('':'a' / . _ s)")          # grobe Demo-Regel
def lenient(w):
    out = set(ana.analyze(w))
    for v in rule.generate(w): out |= set(ana.analyze(v))
    return sorted(out)
print("milimētrs →", lenient("milimētrs"))            # ['milimētras+N+Msc+Sg+Nom']
print("komponiert →", list((rule @ ana).analyze("milimētrs")))   # []  ← Grenze
PY

# 2b) HFST komponiert → foma → pyfoma (Round-Trip):
python3 /tmp/hfst-spike/export.py                     # baut lenient, schreibt lenient.hfst
hfst-fst2fst -f foma -b /tmp/hfst-spike/lenient.hfst -o /tmp/hfst-spike/lenient.foma
uv run python - <<'PY'
from pyfoma import FST
fst = FST.from_fomastring(open("/tmp/hfst-spike/lenient.foma").read())
ana = lambda w: sorted(set(fst.generate(w)))          # diese FST: generate = surface→analyse
print("milimētrs →", ana("milimētrs"))
print("elektrōmagnētisks →", ana("elektrōmagnētisks"))
PY
```
