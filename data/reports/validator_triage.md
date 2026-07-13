# Validator-Triage: FST-/Twanksta-Lücken

Laufendes Triage-Log für OOV-Formen aus realen Agenten-/Validatorläufen.
Bucket-Entscheidung pro Eintrag: **Twanksta-Bug** (Paradigma im Wörterbuch
falsch/lückenhaft → upstream melden), **legitime Variante** (Form ist
belegt/regulär, gen_lexc müsste sie erzeugen) oder **Modellfehler**
(Agent hat die Form erfunden — kein FST-Handlungsbedarf).

Nicht hier hand-patchen: die `.lexc`-Dateien sind aus
`data/external/twanksta_entries.json` generiert; Fixes gehören in die
Quelle oder in `fst/scripts/gen_lexc.py`.

| Datum | Form | Erwartete Analyse | FST-Ergebnis | Verdacht | Entscheidung |
|---|---|---|---|---|---|
| 2026-07-13 | `ēimi` | ēitwei+V+Ind+Pres+P1+Sg | OOV (`ēimi+?`); Paradigma hat `ēima` = P1 Sg, `ēit` = P3 Sg/Pl | Twanksta modelliert P1 Präs. von *ēitwei* als `ēima`; `ēimi` ist die athematische mi-Form (vgl. lit. *eimì*) — Variante vs. Neopreußisch-Norm klären | offen: gegen Twanksta-Paradigma + Enchiridion-Belege prüfen; falls Norm `ēima` ist, ist `ēimi` ein Modellfehler des Agenten |
| 2026-07-13 | `kruwīns` | kruwīns+Adj+Sg+Nom+Masc | OOV — Lemma fehlt komplett (auch `kruwīnan` OOV) | Adjektivderivation zu *krawjā/krāujan* ‚Blut' fehlt in Twanksta | offen: upstream als fehlendes Lemma melden; kein gen_lexc-Bug |
