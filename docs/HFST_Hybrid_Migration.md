# Generalisierende Leniency in die Architektur integrieren (H2 + V-Zeilen-Migration)

> **Status:** ⤳ überholt. Statt des Hybrid-Round-Trips (H2: HFST nur als
> Kompositions-Engine, Ergebnis zurück nach pyfoma) wurde ein **vollständig
> HFST-nativer Paralleler Zweig** umgesetzt — dieselbe Sprachbeschreibung
> durchgängig in HFST komponiert, die V-Zeilen durch generalisierende Regeln
> ersetzt. Siehe **[docs/HFST_BRANCH.md](HFST_BRANCH.md)**. Der pyfoma-Zweig
> bleibt unverändert als Vergleichsbasis. Diese Notiz dokumentiert den
> ursprünglichen H1/H2/H3-Entscheidungsraum (Hintergrund).

## Context

Der HFST-Spike ([HFST_SPIKE.md](HFST_SPIKE.md)) hat gezeigt: generalisierende Leniency
(spellrelax-Regeln, die auf unbekanntes Vokabular greifen) ist machbar — pyfoma kann
Wildcard-Regeln zwar nicht **komponieren**, aber HFST kann es, und das komponierte Ergebnis
lässt sich via foma-Format **zurück nach pyfoma** holen (`from_fomastring`). Heute wird
`build/lenient.fst` per **V-Zeilen-Aufzählung** im lexd gebaut (deckt nur belegte Varianten,
generalisiert nicht; BACKLOG `-as/-us` offen).

**Entscheidung (User):**
- **H2** — `lenient.fst` in HFST komponieren und als pyfoma-natives FST zurückholen;
  Konsumenten (`analyze.py`, `match_forms.py`, `tests/`) bleiben unverändert (`FST.load` +
  `.analyze`).
- **Migration** — die bisherigen V-Zeilen-Varianten (Twanksta-j, elaktr) **und** die neue
  Lücke (`-as/-us`) als **generalisierende Regeln** in HFST formulieren; V-Zeilen entfallen.

**Ergebnis:** `analyser.fst` = pyfoma (unverändert); `lenient.fst` = `analyser ∘ spellrelax`
(HFST → foma → pyfoma-nativ). Eine Regel-Quelle, generalisiert auf neues Vokabular.

## Zielarchitektur

```
gold/*.json → morphology/lexd.py → morphotactics.lexd   (jetzt V-frei)
      │ pyfoma.lexd ∘ phonology.py            (pypy)
      ▼
  build/analyser.fst  (+ .att)                 unverändert (≈13530 Zustände)
      │ ∘ spellrelax-Regeln                    (HFST, System-py3.14)
      ▼  hfst-fst2fst -f foma -b
  build/lenient.foma → FST.from_fomastring → save  build/lenient.fst   (pyfoma-nativ)
```

`spellrelax.py` wird **die** Regel-Quelle (HFST `(->)`-Regex-Strings; reines Python,
importierbar auch unter System-py3.14, keine pyfoma-Importe beim Laden).

## Arbeitsschritte

**1. spellrelax.py → Regel-Spec.** Die Variantenphänomene als HFST-optionale Replace
(`(->)`) formulieren, jeweils mit Wortend-/Kontext-Anker:
- **Twanksta-j** (ersetzt `jan_variant`): explizites `j` ↔ palatalisierter Konsonant /
  weiche Endung. Übersetzung der bestehenden `jan_variant`-Logik in Kontextregeln; die
  Rückrichtung ist mehrdeutig (`ja → i|e|…`) — **Über-Generierung ist ok**, der Analyser
  filtert. Die Fälle aus `tests/test_ortho.py` sind das Korrektheits-Orakel.
- **elektr- ↔ elaktr-** (ersetzt `elaktr_variant`): literaler Replace.
- **`-as/-us` ↔ `-s`** Nom sg (P25/P32, neu): Epenthese `a/u` vor finalem `s` nach
  Konsonant, `… _ s .#.`.
Alte Helfer (`jan_variant`, `elaktr_variant`) bleiben, bis die Regeln verifiziert sind,
dann entfernen.

**2. V-Zeilen aus dem lexd entfernen.** `morphology/lexd.py`: die V-Marker-Emission
(`render_suffix`-jvar + elaktr-Stammzeile) streichen → `morphotactics.lexd` wird V-frei.
`build.py`: zweiten Build-Zweig (`lexd mit V-Zeilen`) und `strip_variant_lines` entfernen;
`build.py` baut nur noch `analyser.fst` (+ `.att`). `analyser.fst` bleibt unverändert
(es enthielt nie V-Zeilen).

**3. Kompositionsstufe (System-py3.14, python-hfst).** Neues Modul
`src/prussian/fst/compose_lenient.py`:
- `analyser.att` via `AttReader`+`invert` laden,
- aus `spellrelax`-Regel-Spec die `(->)`-Regeln bauen, mit `analyser` komponieren, minimieren,
- `HfstOutputStream` → `build/lenient.hfst`, dann `hfst-fst2fst -f foma -b` →
  `build/lenient.foma`. (Snippet-Vorlage: `/tmp/hfst-spike/export.py`.)

**4. foma → pyfoma-nativ.** Modul `src/prussian/fst/foma_to_fst.py` (pyfoma):
`FST.from_fomastring(open(lenient.foma).read())`, **Orientierung so einstellen, dass
`.analyze(form)` die Analyse liefert** (Round-Trip-Experiment: ohne invert lag sie auf
`generate()` — also entweder im HFST-Schritt nicht invertieren oder hier `fst.invert()`;
empirisch festziehen), dann `.save(build/lenient.fst)`. `load_foma` meiden (Header-Bug) →
`from_fomastring`.

**5. Build-Orchestrierung über 3 Interpreter.** Da python-hfst nur im System-Python 3.14
liegt, pyfoma im uv-venv/pypy, kann der Build kein einzelnes `python -m` mehr sein. Dünner
Treiber `scripts/build.sh` (Giella-nah; oder Makefile):
```
PYTHONPATH=src pypy3  -m prussian.fst.build            # analyser.fst + .att   (V-frei)
PYTHONPATH=src python3 -m prussian.fst.compose_lenient  # → lenient.hfst/.foma  (HFST)
PYTHONPATH=src pypy3  -m prussian.fst.foma_to_fst       # → lenient.fst (pyfoma-nativ)
```
README/docs auf den mehrstufigen Build + Interpreter-Anforderungen anpassen.

## Empfohlene Phasierung (Risiko klein halten)

1. Erst **Parität**: Twanksta-j + elaktr als Regeln, V-Zeilen noch drin lassen, neues
   `lenient.fst` parallel bauen und gegen das alte diffen / `test_ortho.py` grün.
2. Dann **Umstellung**: V-Zeilen entfernen, `lenient.fst` nur noch regelbasiert.
3. Dann **Gewinn**: `-as/-us`-Regel ergänzen; `match_forms` zeigt neue Treffer.

## Kritische Dateien

- `src/prussian/fst/spellrelax.py` — Regel-Spec (HFST `(->)`), ersetzt `jan_variant`/`elaktr_variant`.
- `src/prussian/fst/morphology/lexd.py` — V-Marker-Emission entfernen.
- `src/prussian/fst/build.py` — V-Zeilen-Zweig + `strip_variant_lines` entfernen.
- **neu** `src/prussian/fst/compose_lenient.py` (HFST), `src/prussian/fst/foma_to_fst.py` (pyfoma).
- **neu** `scripts/build.sh` (3-stufige Orchestrierung).
- Konsumenten **unverändert**: `analyze.py`, `match_forms.py`, `tests/conftest.py`,
  `tests/test_ortho.py`.
- Referenz: `/tmp/hfst-spike/{spike,export,gen_gold}.py`; [`HFST_SPIKE.md`](HFST_SPIKE.md).

## Risiken

- **Orientierung/foma-Interop** (`.analyze`-Richtung) — Hauptrisiko; per Round-Trip-Experiment
  empirisch festziehen, Konsumenten dürfen sich nicht ändern.
- **jan_variant → Regel-Treue:** bidirektionale Mehrdeutigkeit (`ja→i|e`); Über-Generierung
  zulässig (Analyser filtert). `test_ortho.py` ist die Absicherung.
- **3-Interpreter-Build / Portabilität:** python-hfst nur System-3.14 → Build nicht mehr
  ein-Kommando; CI/andere Maschinen brauchen HFST. Dokumentieren.

## Verifikation (End-zu-Ende)

1. `analyser.fst` unverändert: ≈13530 Zustände; `gen_check` 967/967 + 18/18.
2. `uv run pytest` 26/26 — insbesondere `test_ortho.py` (kūgjan→kūgis, elaktr) jetzt über das
   **regelbasierte** `lenient.fst`.
3. `match_forms.py`: Ortho-Trefferquote **≥** bisher; `milimētrs`/`elektrōmagnētisks` (P25/P32)
   neu erkannt (vorher unmatched).
4. CLI: `analyze "kūgjan milimētrs elektrōmagnētisks"` → alle mit `~` (lenient) analysiert.
