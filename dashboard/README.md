# Prūsiskan FST Dashboard

Statisches Fortschritts-Dashboard. **Keine Abhängigkeiten** — kein React, kein
Build, kein Server, kein `support.js`.

## Dateien
- `index.html` — die Seite (Vanilla-JS, ~30 Zeilen Render-Logik).
- `data.js` — generierte Daten (`window.DASHBOARD_DATA = …`), erzeugt von
  `prussian.report.dashboard`. Kanonische JSON-Kopie: `data/derived/dashboard.json`.

## Aktualisieren
```bash
PYTHONPATH=src pypy3 -m prussian.fst.build          # FSTs (falls nötig)
PYTHONPATH=src pypy3 -m prussian.report.dashboard   # schreibt data/derived/ + dashboard/data.js
```

## Ansehen
`index.html` **doppelklicken** — `data.js` wird per `<script src>` geladen, das
funktioniert auch unter `file://`. (Ein Server ist nicht nötig.)

## Altes Design-Component-Original
`index.dc.html` ist die ursprüngliche Claude-Design-Variante (`<x-dc>`/`DCLogic`).
Sie braucht die DC-Runtime (`support.js`) **plus** React/ReactDOM und einen
HTTP-Server — daher als Quelle aufgehoben, aber nicht der Weg zum Ansehen.
`index.html` ist das pixelgleiche, dependency-freie Äquivalent.
