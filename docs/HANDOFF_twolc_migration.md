# Handoff: twolc-Migration der Phonologie-Ebene (Ebene 3)

**Für:** nächster Agent in einer Umgebung **mit** `hfst-twolc`, `lexd`,
`hfst-txt2fst`, `python-hfst` (z. B. nach `scripts/build_hfst.sh`-Setup).
**Status:** vorbereitet, **noch nicht umgesetzt**. Die vorherige Session hatte
keine HFST/twolc-Tools und konnte daher nichts kompilieren/testen.

## Kontext / wo wir stehen

Schritte 1–5 des Aufräum-Handoffs sind **erledigt und gepusht** (Branch
`claude/gracious-wozniak-jbvhm5`, Commit „pyfoma-Zweig + lexc-Backend
entfernen…"): pyfoma-Zweig, lexc-Backend, `spellrelax.py`, `data/paradigms.lexd`
und der `·`-Grenzmarker sind weg. HFST/lexd ist der einzige Zweig.

Jetzt **Schritt 6**: die Phonologie-Ebene von HFST-Regex-Strings (`hfst/rules.py`)
auf **deklaratives twolc** umstellen — vom Nutzer als bestes Werkzeug bestätigt.
Begründung: auditierbar, Standard-Format (Apertium/Giella), skaliert für die
kommende Partizip-Allomorphie (docs/ORTHO_RULES.md §2/§4-NEU), wo geordnete
Replace-Kaskaden fragil werden.

## Scope dieses Schritts (eng halten!)

Nur die **aktuell implementierte** Regelschicht portieren — das ist
`hfst/rules.py` → `PHONOLOGY = [SHORTEN, LENGTHEN, JPAL, CLEANUP]`. Die
Partizip-Regeln aus docs/ORTHO_RULES.md §2/§4-NEU (`%^NtLong`, `%^GlideW`, …)
sind **nicht** im Code und bleiben außen vor.

Die **Faltung** (`hfst/fold.py`, Lenient-Pfad) bleibt vorerst Replace-basiert —
sie ist optionale, übergenerierende Oberflächen-Relaxation (variant→standard +
datengetriebene Twanksta-j-Endungen), kein sauberer Zwei-Ebenen-Constraint. Nur
der **Generator/Standard-Analysator** (`generator`/`analyser`) wird auf twolc
umgestellt.

## Die aktuelle Regelschicht (Quelle der Wahrheit: `src/prussian/fst/hfst/rules.py`)

Markierte Unterseite (lexikalisch): Buchstaben + Archiphoneme `Â Ê Î Ô Û` +
Marker `M` (Mobile, vor Stamm), `S` (starke Endung), `J` (palatalisierende
Endung). **`V` kommt NICHT mehr vor** (lexd_gen emittiert keine V-Marker;
`CLEANUP` hat `V->0` nur als toten Klausel-Rest — bei der Migration weglassen).

```python
SHORTEN  = "Â->a, Ê->e, Î->i, Ô->o, Û->u  || M ?* _ ?* S ;"
LENGTHEN = "Â->ā, Ê->ē, Î->ī, Ô->ō, Û->ū ;"     # default elsewhere
JPAL     = "g->ģ, k->ķ, n->ņ, s->š, t->ţ, z->ž  || _ J ;"
CLEANUP  = "M->0, S->0, J->0, V->0 ;"
```

Wichtige Invarianten (verifiziert in `morphology/lexd.render_stem`):
- Archiphoneme `Â…` treten **nur in Mobile-Stämmen** auf (immer mit `M`); bar/na
  haben literale Langvokale. ⇒ `Â` koexistiert immer mit `M`.
- `S` nur bei Mobile-Einträgen (`cls=="mob" and not betont`) ⇒ `S` impliziert `M`.
- `J` steht direkt **nach** dem Stammkonsonanten, am Endungsanfang: `…gJ<endung>`.

## twolc-Übersetzung (Entwurf — bitte verifizieren)

Zentrale Einsicht: mit `<=>` (Restriktion **und** Koerzion) genügt **eine**
Regel pro Alternation; der „elsewhere"-Fall ist automatisch, sofern beide
Realisierungen im `Alphabet` als feasible pairs deklariert sind.

```twolc
Alphabet
 Â:a Â:ā  Ê:e Ê:ē  Î:i Î:ī  Ô:o Ô:ō  Û:u Û:ū   ! Archiphoneme
 M:0 S:0 J:0                                    ! Marker-Tilgung
 g:ģ k:ķ n:ņ s:š t:ţ z:ž                        ! Palatalisierungs-Paare
 <ALLE übrigen Buchstaben als Identität, inkl. g k n s t z, ā ē ī ō ū, ģ ķ ņ š ţ ž>
 ;

Rules

"Mobile-Archiphonem kurz vor starker Endung"
 Â:a <=> M: ?* _ ?* S: ;
 Ê:e <=> M: ?* _ ?* S: ;
 Î:i <=> M: ?* _ ?* S: ;
 Ô:o <=> M: ?* _ ?* S: ;
 Û:u <=> M: ?* _ ?* S: ;
! elsewhere → Â:ā … automatisch (einzig übrige feasible-Realisierung)

"J-Palatalisierung des Stammauslauts"
 g:ģ <=> _ J: ;
 k:ķ <=> _ J: ;
 n:ņ <=> _ J: ;
 s:š <=> _ J: ;
 t:ţ <=> _ J: ;
 z:ž <=> _ J: ;
! g:g … elsewhere automatisch
```

`M:`/`S:`/`J:` in Kontexten meinen `M:0` etc. (einzige Realisierung). Marker
löschen sich durch ihre Alphabet-Deklaration selbst — keine eigene Regel nötig.

### ⚠️ Kritischer Punkt: Alphabet-Vollständigkeit

hfst-twolc-Transducer haben ein **festes** Alphabet. Komponiert man das Lexikon
mit einem twol, das einen vorkommenden Buchstaben **nicht** kennt, fällt diese
Form **still** weg (keine Identity-Fallback). Daher MUSS das `Alphabet` jeden
Buchstaben der markierten Unterseite **und** der Oberfläche enthalten.

Empfohlenes Vorgehen, robust + auditierbar:
1. Lexikalisches Alphabet **datengetrieben** ermitteln (rein Python, kein Build):
   `lexd_gen.build_lexd(...)` auf gold-only laufen lassen, Lower-Seiten-Symbole
   einsammeln; Oberflächen-Alphabet = lexikalisch minus `{Â Ê Î Ô Û M S J}` plus
   `{ā ē ī ō ū ģ ķ ņ š ţ ž}`. Für den Vollbau zusätzlich gegen ein paar
   Wortlisten-Stämme prüfen (gleiches Orthographie-Standard wie Gold → praktisch
   identisches Inventar, aber gegenchecken).
2. Die **Regeln + Spezialpaare** von Hand schreiben (das ist der auditierbare
   Teil); die langweilige Identity-Buchstabenliste darf aus (1) stammen.
3. Nach dem Build die `analyser`-Sigma gegen die `lexicon`-Sigma diffen, um
   stille Drops auszuschließen.

## Build-Integration (`src/prussian/fst/hfst/lexd_build.py`)

Heute:
```python
generator = _compose_chain(lexicon, rules.PHONOLOGY)   # regex-Kaskade
```
Neu (twolc):
```python
# twol kompilieren: hfst-twolc data/twol/phonology.twol -o build/hfst/phonology.hfst
subprocess.run(["hfst-twolc", str(TWOL_SRC), "-o", str(TWOL_OUT)], check=True)
twol = hfst.HfstInputStream(str(TWOL_OUT)).read(); twol.convert(FOMA)
generator = hfst.HfstTransducer(lexicon)
generator.compose(twol)        # lexicon.lower (markiert) ∘ twol.upper (markiert)
generator.minimize()
```
Komposition: lexicon-Lower (markierte Strings) = twol-Upper (lexikalisch);
Ergebnis lexicon-Upper(Analyse) : twol-Lower(saubere Oberfläche). Richtung passt.
`analyser = generator invertiert`. Der **Lenient-Pfad bleibt unverändert** (nutzt
`generator` + `fold` weiter).

## Verifikation (das kann der nächste Agent, diese Session nicht)

1. `hfst-twolc data/twol/phonology.twol -o …` → kompiliert ohne Konflikt-Fehler.
   twolc meldet Regelkonflikte/Tippfehler hier zuerst.
2. `scripts/build_hfst.sh --gold-only` dann `python -m prussian.fst.hfst.check`.
   **Zielwert unverändert:** 1471/1471 nominale Gold-Zellen, 18/18 Doubletten,
   verbale no_gen-Baseline. Jede Abweichung = twol falsch (wahrscheinlich
   Alphabet-Lücke oder Kontext-Operator `?*` vs. erwartet).
3. Spot-Checks aus `check.py`: `wāiks`, `kūģu` (JPAL), `mistāi`/`mīstan`
   (SHORTEN/LENGTHEN-Alternation), `kūgju`→Dat (Lenient/fold unberührt).

## Nach erfolgreichem Build aufräumen

- `hfst/rules.py`: `PHONOLOGY`/`SHORTEN`/`LENGTHEN`/`JPAL`/`CLEANUP` entfernen
  (oder Datei löschen, falls nichts anderes mehr importiert — prüfen:
  `grep -rn "hfst.rules\|rules.PHONOLOGY" src/`). `lexd_build` importiert es dann
  nicht mehr.
- `docs/ORTHO_RULES.md §4`: auf die neue Marker-/Symbolnotation (`Â…`, `M/S/J`)
  aktualisieren — §4 steht noch in alter `%^VowS`/`{A}`-Notation.
- `docs/HFST_BRANCH.md`: „Ebene 3 deklarativ als twol" von „offene Punkte" nach
  „umgesetzt" verschieben.

## Harte Regeln (aus dem Ursprungs-Handoff, weiter gültig)

- Wörterbuch nie ganz laden; an Schema/Stichproben arbeiten.
- Keine Phono-Regeln in lexc/lexd; **twol ist der einzige Ort** dafür.
- Generierte lexd nicht handeditieren; nur Generator ändern.
- Teure Builds startet der Nutzer (`make`/`scripts/build_hfst.sh`).
- Pro Schritt **eine** Datei/Ebene.

## Referenzen
- twolc-Syntax: HFST `hfst-twolc`, GiellaLT phonology-Twol-Beispiele.
- Akzentmodell: docs/AKZENT.md. Bestehende (alte) twolc-Skizze: docs/ORTHO_RULES.md §4.
- Aktuelle Regeln: `src/prussian/fst/hfst/rules.py`. Build: `…/hfst/lexd_build.py`.
