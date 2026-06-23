# Literatur und Quellen

## Primärquellen (Daten)

- **TABVLA NOVA** — Palmaitis, M. L. / Klusis, M.: normalisierte
  Paradigmentafeln des rekonstruierten (Neu-)Preußischen.
  `data/external/tabula.html` (handkorrigiert; gepflegt in prussian-corpus,
  siehe [PROVENANCE.md](PROVENANCE.md)).
- **Prusaspira** — <http://prusaspira.org/wirdeins> (Flexionsgenerator).
  Gescrapt/geparst in [prussian-corpus](https://github.com/strfry/prussian-corpus);
  Einträge in `data/external/prusaspira_entries.json`.
- **Twanksta** — <https://wirdeins.twanksta.org> (Wörterbuch + Formen,
  Dialekt Semba). Gescrapt/geparst in prussian-corpus; geparste Einträge in
  `data/external/twanksta_entries.json`.

Quellenverlässlichkeit und Abwägungen: [PROVENANCE.md](PROVENANCE.md),
GOLDSTANDARD-Methodik in `data/gold/GOLDSTANDARD.md`.

## Sekundärliteratur

- **Mažiulis, Vytautas**: *Prūsų kalbos istorinė gramatika* / Historische
  Grammatik des Altpreußischen. Vilnius.
  — §§21–25: Palatalisierung und weiche Endungen (Grundlage der
  J-Regel in `src/prussian/fst/rules.py` und der Twanksta-j-Varianten);
  §122 Fn. 54: weiche Endungsschreibung; §§86–138: Klassifikation von
  Quellendivergenzen (FEHLER/SCHREIBVAR/ALLOMORPH — Grundlage der
  Goldstandard-Auswahl).
- **Rinkevičius, Vytautas (2009)**: *Prūsų kalbos kirčiavimo sistema*
  („Das altpreußische Akzentsystem"). Dissertations-Zusammenfassung,
  Universität Vilnius. — Barytona/Mobilia, starke/schwache Endungen;
  Grundlage des Akzentmodells ([AKZENT.md](AKZENT.md),
  `src/prussian/gold/accent.py`).
- **Kortlandt, Frederik (2011)**: „On the orthography of the Old Prussian
  texts." *Baltistica* XLVI(2), 225–232.
  <https://www.baltistica.lt/index.php/baltistica/article/view/1944>
  — Gegenposition zu Rinkevičius (Vortondoppelung, morphologische statt
  phonetische Alternation); für die Reproduktion der TABVLA-NOVA-Norm
  nicht entscheidungsbedürftig (Diskussion in [AKZENT.md](AKZENT.md) §1).

## Werkzeuge

- **pyfoma** — Hulden, M. et al.: PyFoma, finite-state toolkit in Python.
  <https://github.com/mhulden/pyfoma> — lexd-Kompilation, Rewrite-Regeln,
  Komposition.
- **lexd-Formalismus** — Swanson, D. / Howell, N.: Lexd. Apertium.
  <https://github.com/apertium/lexd> — morphotaktische Beschreibungssprache
  (`build/morphotactics.lexd`).
