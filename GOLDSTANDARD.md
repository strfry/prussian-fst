# Goldstandard – Quellabweichungen (Tabula / Prusaspira / Twanksta)

Generiert von `goldstandard.py` aus `vergleich.json`. Das Mehrheitsvotum (2/3) läuft **nach** der orthographischen Regelschicht (Mažiulis §§21–25 Palatalisierung, §122 weiche Endung): **A** Palatal-j (sj=š, gj=ģ …), **B** weiche Endung (-an/-in/-en). **Kein** MCP-Check (MCP = Twanksta). Echte Fehler vs. Allomorphe nach Mažiulis.

## Übersicht

| Kategorie | Anzahl |
|---|---|
| Paradigmen gesamt | 71 |
| **Gender-Mismatch** (Paradigmen) | 4 |
| **Variation** (Zellen, echte Entscheidung) | 129 |
| &nbsp;&nbsp;– davon VOTUM (Mehrheit klar) | 95 |
| &nbsp;&nbsp;– davon FEHLER (Mažiulis) | 1 |
| &nbsp;&nbsp;– davon MANUELL (editorisch, s. README) | 32 |
| &nbsp;&nbsp;– davon KEINE MEHRHEIT (offen) | 1 |
| **Orthographie** (Zellen, durch Regel gelöst) | 128 |
| &nbsp;&nbsp;– B: weiche Endung (-an/-in/-en) | 73 |
| &nbsp;&nbsp;– A: Palatal-j (sj=š, gj=ģ) | 31 |
| &nbsp;&nbsp;– ≈ Schreibung (Länge/Diakritika) | 24 |

## 1. Gender-Mismatch

Quellen weisen demselben Lemma unterschiedliche Genera zu. Morphotaktisch meist harmlos (steuert nur Kongruenz), außer bei echtem Klassenwechsel. Vorschlag = Mehrheits-Genus.

| Par | Lemma | Tabula | Prusaspira | Twanksta | Mehrheits-Genus |
|---|---|---|---|---|---|
| 40c | buccis | n | m | m | **m** |
| 48 | galwā | m | f | f | **f** |
| 49 | auktimmisku | f | f | n | **f** |
| 59 | kiŕksni | n | n | f | **n** |

## 2. Variation (echte Formdivergenz, auch nach Regelschicht)

Differenz besteht **nach** der orthographischen Normalisierung fort → Goldstandard per Mehrheitsvotum. `*` am Genus = auf Mehrheits-Genus geflachte Gender-Mismatch-Zelle. Spalte **Review** für die finale Entscheidung.

| Par | Lemma | Genus | Kasus | Tabula | Prusaspira | Twanksta | Klassifik. | Goldstandard | Hinweis | Review |
|---|---|---|---|---|---|---|---|---|---|---|
| 17 | wiss | f | Dat sg | wissai | wissai | wisssai | VOTUM | **wissai** |  |  |
| 17 | wiss | f | Akk pl | wissans | wissans | wisans | VOTUM | **wissans** |  |  |
| 18 | kits | f | Akk pl | kittans | kittans | kitans | VOTUM | **kittans** |  |  |
| 20 | majs | n | Akk pl | majjans | majjans | majans | VOTUM | **majjans** |  |  |
| 21 | aīns | n | Gen sg | ainasse | ainasse | aīnase | VOTUM | **ainasse** |  |  |
| 26 | labs | f | Dat sg | labbai | labbai | labai | VOTUM | **labbai** |  |  |
| 28 | māldaisis | m | Dat sg | māldaišasmu | māldaišu | māldaisju | VOTUM | **māldaišu** |  |  |
| 28 | māldaisis | m | Dat pl | māldaisimans | māldaišamans | māldaisjamans | VOTUM | **māldaišamans** |  |  |
| 29 | sēnts | m | Nom sg | sēnts | swints | swents | MANUELL | **swints** | swint-Stamm (Prusaspira) – korpusweit am verbreitetsten; siehe README |  |
| 29 | sēnts | m | Nom pl | sēntei | swintai | swentai | MANUELL | **swintai** | swint-Stamm (Prusaspira) – korpusweit am verbreitetsten; siehe README |  |
| 29 | sēnts | m | Gen sg | sēntis | swintas | swentas | MANUELL | **swintas** | swint-Stamm (Prusaspira) – korpusweit am verbreitetsten; siehe README |  |
| 29 | sēnts | m | Gen pl | sēntin | swintan | swentan | MANUELL | **swintan** | swint-Stamm (Prusaspira) – korpusweit am verbreitetsten; siehe README |  |
| 29 | sēnts | m | Dat sg | sentismu | swintasmu | swentasmu | MANUELL | **swintasmu** | swint-Stamm (Prusaspira) – korpusweit am verbreitetsten; siehe README |  |
| 29 | sēnts | m | Dat pl | sentimmans | swintamans | swentamans | MANUELL | **swintamans** | swint-Stamm (Prusaspira) – korpusweit am verbreitetsten; siehe README |  |
| 29 | sēnts | m | Akk sg | sēntin | swintan | swentan | MANUELL | **swintan** | swint-Stamm (Prusaspira) – korpusweit am verbreitetsten; siehe README |  |
| 29 | sēnts | m | Akk pl | sēntins | swintans | swentans | MANUELL | **swintans** | swint-Stamm (Prusaspira) – korpusweit am verbreitetsten; siehe README |  |
| 29 | sēnts | f | Nom sg | sentī | swinta | swenta | MANUELL | **swinta** | swint-Stamm (Prusaspira) – korpusweit am verbreitetsten; siehe README |  |
| 29 | sēnts | f | Nom pl | sēntes | swintas | swentas | MANUELL | **swintas** | swint-Stamm (Prusaspira) – korpusweit am verbreitetsten; siehe README |  |
| 29 | sēnts | f | Gen sg | sēntes | swintas | swentas | MANUELL | **swintas** | swint-Stamm (Prusaspira) – korpusweit am verbreitetsten; siehe README |  |
| 29 | sēnts | f | Gen pl | sēntin | swintan | swentan | MANUELL | **swintan** | swint-Stamm (Prusaspira) – korpusweit am verbreitetsten; siehe README |  |
| 29 | sēnts | f | Dat sg | sēntei | swintai | swentai | MANUELL | **swintai** | swint-Stamm (Prusaspira) – korpusweit am verbreitetsten; siehe README |  |
| 29 | sēnts | f | Dat pl | sentjāmans | swintamans | swentamans | MANUELL | **swintamans** | swint-Stamm (Prusaspira) – korpusweit am verbreitetsten; siehe README |  |
| 29 | sēnts | f | Akk sg | sēntin | swintan | swentan | MANUELL | **swintan** | swint-Stamm (Prusaspira) – korpusweit am verbreitetsten; siehe README |  |
| 29 | sēnts | f | Akk pl | sēntins | swintans | swentans | MANUELL | **swintans** | swint-Stamm (Prusaspira) – korpusweit am verbreitetsten; siehe README |  |
| 29 | sēnts | n | Nom sg | sēnti | swintan | swentan | MANUELL | **swintan** | swint-Stamm (Prusaspira) – korpusweit am verbreitetsten; siehe README |  |
| 29 | sēnts | n | Nom pl | sēntei | swintai | swentai | MANUELL | **swintai** | swint-Stamm (Prusaspira) – korpusweit am verbreitetsten; siehe README |  |
| 29 | sēnts | n | Gen sg | sēntis | swintas | swentas | MANUELL | **swintas** | swint-Stamm (Prusaspira) – korpusweit am verbreitetsten; siehe README |  |
| 29 | sēnts | n | Gen pl | sēntin | swintan | swentan | MANUELL | **swintan** | swint-Stamm (Prusaspira) – korpusweit am verbreitetsten; siehe README |  |
| 29 | sēnts | n | Dat sg | sentismu | swintasmu | swentasmu | MANUELL | **swintasmu** | swint-Stamm (Prusaspira) – korpusweit am verbreitetsten; siehe README |  |
| 29 | sēnts | n | Dat pl | sēntimmans | swintamans | swentamans | MANUELL | **swintamans** | swint-Stamm (Prusaspira) – korpusweit am verbreitetsten; siehe README |  |
| 29 | sēnts | n | Akk sg | sēnti | swintan | swentan | MANUELL | **swintan** | swint-Stamm (Prusaspira) – korpusweit am verbreitetsten; siehe README |  |
| 29 | sēnts | n | Akk pl | sēntins | swintans | swentans | MANUELL | **swintans** | swint-Stamm (Prusaspira) – korpusweit am verbreitetsten; siehe README |  |
| 30 | āngus | f | Dat pl | āngemans | āngemans | āngjamans | VOTUM | **āngemans** |  |  |
| 30a | stāws | m | Nom sg | staūs | stāws | stāws | VOTUM | **stāws** |  |  |
| 30a | stāws | m | Nom pl | staūwai | staūwai | stāwai | VOTUM | **staūwai** |  |  |
| 30a | stāws | m | Gen sg | staūwas | staūwas | stāwas | VOTUM | **staūwas** |  |  |
| 30a | stāws | m | Gen pl | stāwun | stāwun | stāwan | VOTUM | **stāwun** |  |  |
| 30a | stāws | m | Dat sg | stāwusmu | stāwusmu | stāwasmu | VOTUM | **stāwusmu** |  |  |
| 30a | stāws | m | Dat pl | stāwumans | stāwumans | stāwamans | VOTUM | **stāwumans** |  |  |
| 30a | stāws | m | Akk sg | stāwun | stāwun | stāwan | VOTUM | **stāwun** |  |  |
| 30a | stāws | m | Akk pl | stāwuns | stāwuns | stāwans | VOTUM | **stāwuns** |  |  |
| 30a | stāws | f | Nom sg | stāwi | stāwi | stāwa | VOTUM | **stāwi** |  |  |
| 30a | stāws | n | Nom sg | stāwu | stāwu | stāwan | VOTUM | **stāwu** |  |  |
| 30a | stāws | n | Nom pl | staūwai | staūwai | stāwai | VOTUM | **staūwai** |  |  |
| 30a | stāws | n | Gen sg | staūwas | staūwas | stāwas | VOTUM | **staūwas** |  |  |
| 30a | stāws | n | Gen pl | stāwun | stāwun | stāwan | VOTUM | **stāwun** |  |  |
| 30a | stāws | n | Dat sg | stāwusmu | stāwusmu | stāwasmu | VOTUM | **stāwusmu** |  |  |
| 30a | stāws | n | Dat pl | stāwumans | stāwumans | stāwamans | VOTUM | **stāwumans** |  |  |
| 30a | stāws | n | Akk sg | stāwu | stāwu | stāwan | VOTUM | **stāwu** |  |  |
| 30a | stāws | n | Akk pl | stāwuns | stāwuns | stāwans | VOTUM | **stāwuns** |  |  |
| 33 | šmaws | m | Dat pl | šmāumans | šmāumans | šmāuamans | VOTUM | **šmāumans** |  |  |
| 35 | mīstan | n | Dat pl | mīstamans | mistammans | mīstamans | FEHLER | **mistammans** | mīstamans falsch (TABVLA-Fehler, vgl. P35 mēstan) |  |
| 35a | interwallin | n | Nom pl | interwalāi | interwallai | interwalāi | VOTUM | **interwalāi** |  |  |
| 35a | interwallin | n | Dat pl | interwalimmans | interwallamans | interwalammans | KEINE MEHRHEIT | **?** | alle Quellen verschieden – manuell entscheiden |  |
| 37 | pannin | n | Dat pl | panemmans | panemmans | panjammans | VOTUM | **panemmans** |  |  |
| 37a | amzin | n | Dat pl | amzimmans | amžammans | amzjammans | VOTUM | **amžammans** |  |  |
| 39 | rikīs | m | Dat pl | rikīmans | Rikkijmans | Rikkimans | VOTUM | **Rikkijmans** |  |  |
| 40 | kūgis | m | Dat pl | kūgemans | kūgemans | kūgjamans | VOTUM | **kūgemans** |  |  |
| 41 | klākis | m | Nom sg | klākis | klākis | tlākis | VOTUM | **klākis** |  |  |
| 41 | klākis | m | Nom pl | klakēi | klakēi | tlakjāi | VOTUM | **klakēi** |  |  |
| 41 | klākis | m | Gen sg | klākes | klākes | tlākjas | VOTUM | **klākes** |  |  |
| 41 | klākis | m | Gen pl | klākin | klākin | tlākjan | VOTUM | **klākin** |  |  |
| 41 | klākis | m | Dat sg | klāķu | klāķu | tlākju | VOTUM | **klāķu** |  |  |
| 41 | klākis | m | Dat pl | klakemmans | klakemmans | tlakjammans | VOTUM | **klakemmans** |  |  |
| 41 | klākis | m | Akk sg | klākin | klākin | tlākjan | VOTUM | **klākin** |  |  |
| 41 | klākis | m | Akk pl | klākins | klākins | tlākjans | VOTUM | **klākins** |  |  |
| 46 | spigsnā | f | Nom sg | spigsnā | spigsnā | spegsnā | VOTUM | **spigsnā** |  |  |
| 46 | spigsnā | f | Nom pl | spīgsnas | spīgsnas | spēgsnas | VOTUM | **spīgsnas** |  |  |
| 46 | spigsnā | f | Gen sg | spīgsnas | spīgsnas | spēgsnas | VOTUM | **spīgsnas** |  |  |
| 46 | spigsnā | f | Gen pl | spīgsnan | spīgsnan | spēgsnan | VOTUM | **spīgsnan** |  |  |
| 46 | spigsnā | f | Dat sg | spīgsnai | spīgsnai | spēgsnai | VOTUM | **spīgsnai** |  |  |
| 46 | spigsnā | f | Dat pl | spigsnāmans | spigsnāmans | spegsnāmans | VOTUM | **spigsnāmans** |  |  |
| 46 | spigsnā | f | Akk sg | spīgsnan | spīgsnan | spēgsnan | VOTUM | **spīgsnan** |  |  |
| 46 | spigsnā | f | Akk pl | spīgsnans | spīgsnans | spēgsnans | VOTUM | **spīgsnans** |  |  |
| 50 | garkīti | f | Dat pl | garkītemans | garkītemans | garkītjamans | VOTUM | **garkītemans** |  |  |
| 54 | pekūri | m | Nom sg | pekūri | pekūris | pekāris | MANUELL | **pekūris** | Mažiulis widerlegt Tabula (-jas regelhaft = -es, nicht -is); nur maskulin (f = Parsing-Artefakt, nicht Klasse 54); Dat sg = pekūrei (-ei wie bei allen anderen Lemmata der Klasse 54); siehe README |  |
| 54 | pekūri | m | Nom pl | pekūris | pekūrei | pekārjai | MANUELL | **pekūrei** | Mažiulis widerlegt Tabula (-jas regelhaft = -es, nicht -is); nur maskulin (f = Parsing-Artefakt, nicht Klasse 54); Dat sg = pekūrei (-ei wie bei allen anderen Lemmata der Klasse 54); siehe README |  |
| 54 | pekūri | m | Gen sg | pekūris | pekūres | pekārjas | MANUELL | **pekūres** | Mažiulis widerlegt Tabula (-jas regelhaft = -es, nicht -is); nur maskulin (f = Parsing-Artefakt, nicht Klasse 54); Dat sg = pekūrei (-ei wie bei allen anderen Lemmata der Klasse 54); siehe README |  |
| 54 | pekūri | m | Gen pl | pekūrin | pekūrin | pekārjan | MANUELL | **pekūrin** | Mažiulis widerlegt Tabula (-jas regelhaft = -es, nicht -is); nur maskulin (f = Parsing-Artefakt, nicht Klasse 54); Dat sg = pekūrei (-ei wie bei allen anderen Lemmata der Klasse 54); siehe README |  |
| 54 | pekūri | m | Dat sg | pekūrei | pekūŗu | pekārju | MANUELL | **pekūrei** | Mažiulis widerlegt Tabula (-jas regelhaft = -es, nicht -is); nur maskulin (f = Parsing-Artefakt, nicht Klasse 54); Dat sg = pekūrei (-ei wie bei allen anderen Lemmata der Klasse 54); siehe README |  |
| 54 | pekūri | m | Dat pl | pekūrimans | pekūremans | pekārjamans | MANUELL | **pekūremans** | Mažiulis widerlegt Tabula (-jas regelhaft = -es, nicht -is); nur maskulin (f = Parsing-Artefakt, nicht Klasse 54); Dat sg = pekūrei (-ei wie bei allen anderen Lemmata der Klasse 54); siehe README |  |
| 54 | pekūri | m | Akk sg | pekūrin | pekūrin | pekārjan | MANUELL | **pekūrin** | Mažiulis widerlegt Tabula (-jas regelhaft = -es, nicht -is); nur maskulin (f = Parsing-Artefakt, nicht Klasse 54); Dat sg = pekūrei (-ei wie bei allen anderen Lemmata der Klasse 54); siehe README |  |
| 54 | pekūri | m | Akk pl | pekūrins | pekūrins | pekārjans | MANUELL | **pekūrins** | Mažiulis widerlegt Tabula (-jas regelhaft = -es, nicht -is); nur maskulin (f = Parsing-Artefakt, nicht Klasse 54); Dat sg = pekūrei (-ei wie bei allen anderen Lemmata der Klasse 54); siehe README |  |
| 57 | dānts | m | Nom pl | dāntei | dāntei | dāntes/dāntjai | VOTUM | **dāntei** |  |  |
| 58 | klīts | f | Nom sg | klīts | klīts | klēts | VOTUM | **klīts** |  |  |
| 58 | klīts | f | Nom pl | klītis | klītis | klētis | VOTUM | **klītis** |  |  |
| 58 | klīts | f | Gen sg | klītis | klītis | klētis | VOTUM | **klītis** |  |  |
| 58 | klīts | f | Gen pl | klītin | klītin | klētin | VOTUM | **klītin** |  |  |
| 58 | klīts | f | Dat sg | klītei | klītei | klētei | VOTUM | **klītei** |  |  |
| 58 | klīts | f | Dat pl | klītimans | klītimans | klētimans | VOTUM | **klītimans** |  |  |
| 58 | klīts | f | Akk sg | klītin | klītin | klētin | VOTUM | **klītin** |  |  |
| 58 | klīts | f | Akk pl | klītins | klītins | klētins | VOTUM | **klītins** |  |  |
| 61 | kērmens | m | Nom pl | kērmenei | kērmenei | kērmenes/kērmenjai | VOTUM | **kērmenei** |  |  |
| 62 | emmens | m | Nom pl | emnei | emnei | emnes/emnjai | VOTUM | **emnei** |  |  |
| 62 | emmens | m | Dat pl | emnimans | emnimmans | emnimans | VOTUM | **emnimans** |  |  |
| 63 | sīmen | n | Nom sg | sīmen | sīmen | sēmen | VOTUM | **sīmen** |  |  |
| 63 | sīmen | n | Nom pl | simenēi | simenēi | sēmenes/semenjāi | VOTUM | **simenēi** |  |  |
| 63 | sīmen | n | Gen sg | sīmenes | sīmenes | sēmenes | VOTUM | **sīmenes** |  |  |
| 63 | sīmen | n | Gen pl | sīmenin | sīmenin | sēmenin | VOTUM | **sīmenin** |  |  |
| 63 | sīmen | n | Dat sg | sīmeni | sīmeni | sēmeni | VOTUM | **sīmeni** |  |  |
| 63 | sīmen | n | Dat pl | simenimmans | simenimmans | semenimmans | VOTUM | **simenimmans** |  |  |
| 63 | sīmen | n | Akk sg | sīmen | sīmen | sēmen | VOTUM | **sīmen** |  |  |
| 63 | sīmen | n | Akk pl | sīmenins | sīmenins | sēmenins | VOTUM | **sīmenins** |  |  |
| 64 | zmūi | m | Nom sg | zmūi | zmūi | zmōi | VOTUM | **zmūi** |  |  |
| 64 | zmūi | m | Nom pl | zmūnei | zmūnei | zmānes/zmōnjai | VOTUM | **zmūnei** |  |  |
| 64 | zmūi | m | Gen sg | zmūnes | zmūnes | zmānes | VOTUM | **zmūnes** |  |  |
| 64 | zmūi | m | Gen pl | zmūnin | zmūnin | zmānin | VOTUM | **zmūnin** |  |  |
| 64 | zmūi | m | Dat sg | zmūni | zmūni | zmāni | VOTUM | **zmūni** |  |  |
| 64 | zmūi | m | Dat pl | zmūnimans | zmūnimans | zmānimans | VOTUM | **zmūnimans** |  |  |
| 64 | zmūi | m | Akk sg | zmūnin | zmūnin | zmānin | VOTUM | **zmūnin** |  |  |
| 64 | zmūi | m | Akk pl | zmūnins | zmūnins | zmānins | VOTUM | **zmūnins** |  |  |
| 65 | brāti | m | Nom pl | brātei | brātei | brātjai/brātres | VOTUM | **brātei** |  |  |
| 65 | brāti | m | Gen sg | brātis | brātis | brātis/brātris | VOTUM | **brātis** |  |  |
| 65 | brāti | m | Gen pl | brātin | brātin | brātin/brātran | VOTUM | **brātin** |  |  |
| 65 | brāti | m | Akk sg | brātin | brātin | brātin/brātrin | VOTUM | **brātin** |  |  |
| 65 | brāti | m | Akk pl | brātins | brātins | brātins/brātrins | VOTUM | **brātins** |  |  |
| 66 | mūti | f | Nom sg | mūti | mūti | māti | VOTUM | **mūti** |  |  |
| 66 | mūti | f | Nom pl | mūtis | mūtis | mātes/māteres | VOTUM | **mūtis** |  |  |
| 66 | mūti | f | Gen sg | mūtis | mūtis | mātis/māteris | VOTUM | **mūtis** |  |  |
| 66 | mūti | f | Gen pl | mūtin | mūtin | mātin/māteran | VOTUM | **mūtin** |  |  |
| 66 | mūti | f | Dat sg | mūterei | mūterei | māterei | VOTUM | **mūterei** |  |  |
| 66 | mūti | f | Dat pl | mūterimans | mūterimans | māterimans | VOTUM | **mūterimans** |  |  |
| 66 | mūti | f | Akk sg | mūtin | mūtin | mātin/māterin | VOTUM | **mūtin** |  |  |
| 66 | mūti | f | Akk pl | mūtins | mūtins | mātins/māterins | VOTUM | **mūtins** |  |  |
| 67 | dukti | f | Nom pl | duktis | duktis | duktes/dukteres | VOTUM | **duktis** |  |  |
| 67 | dukti | f | Gen sg | duktis | duktis | duktis/dukteris | VOTUM | **duktis** |  |  |
| 67 | dukti | f | Gen pl | duktin | duktin | duktin/dukteran | VOTUM | **duktin** |  |  |
| 67 | dukti | f | Akk sg | duktin | duktin | duktin/dukterin | VOTUM | **duktin** |  |  |
| 67 | dukti | f | Akk pl | duktins | duktins | duktins/dukterins | VOTUM | **duktins** |  |  |

## 3. Orthographie-Abweichung (durch Regelschicht gelöst)

Nach Anwendung der Regel identisch → gleiches Morphem. Spalte **Regel** zeigt, welche Regel die Formen zusammenführt. Goldstandard = gewählte Schreibkonvention.

| Par | Lemma | Genus | Kasus | Tabula | Prusaspira | Twanksta | Regel | Goldstandard |
|---|---|---|---|---|---|---|---|---|
| 15 | šis | m | Akk pl | šans | šans | šins | B: weiche Endung (-an/-in/-en) | **šans** |
| 15 | šis | n | Akk pl | šans | šans | šins | B: weiche Endung (-an/-in/-en) | **šans** |
| 21 | aīns | n | Dat sg | ainasmu | ainasmu | aīnasmu | ≈ Schreibung (Länge/Diakritika) | **ainasmu** |
| 21 | aīns | n | Dat pl | ainasmu/ainammans | aīnasmu/ainammans | ainasmu/ainammans | ≈ Schreibung (Länge/Diakritika) | **ainasmu/ainammans** |
| 26 | labs | m | Dat sg | labasmu | labàsmu | labàsmu | ≈ Schreibung (Länge/Diakritika) | **labàsmu** |
| 26 | labs | n | Dat sg | labasmu | labàsmu | labàsmu | ≈ Schreibung (Länge/Diakritika) | **labàsmu** |
| 28 | māldaisis | m | Nom pl | māldaišai | māldaišai | māldaisjai | A: Palatal-j (sj=š, gj=ģ) | **māldaišai** |
| 28 | māldaisis | m | Gen sg | māldaišas | māldaišas | māldaisjas | A: Palatal-j (sj=š, gj=ģ) | **māldaišas** |
| 28 | māldaisis | m | Gen pl | māldaisin | māldaisin | māldaisjan | B: weiche Endung (-an/-in/-en) | **māldaisin** |
| 28 | māldaisis | m | Akk sg | māldaisin | māldaisin | māldaisjan | B: weiche Endung (-an/-in/-en) | **māldaisin** |
| 28 | māldaisis | m | Akk pl | māldaisins | māldaisins | māldaisjans | B: weiche Endung (-an/-in/-en) | **māldaisins** |
| 30 | āngus | f | Nom pl | ānges | ānges | āngjas | B: weiche Endung (-an/-in/-en) | **ānges** |
| 30 | āngus | f | Gen sg | ānges | ānges | āngjas | B: weiche Endung (-an/-in/-en) | **ānges** |
| 30 | āngus | f | Gen pl | āngin | āngin | āngjan | B: weiche Endung (-an/-in/-en) | **āngin** |
| 30 | āngus | f | Dat sg | āngei | āngei | āngjai | B: weiche Endung (-an/-in/-en) | **āngei** |
| 30 | āngus | f | Akk sg | āngin | āngin | āngjan | B: weiche Endung (-an/-in/-en) | **āngin** |
| 30 | āngus | f | Akk pl | āngins | āngins | āngjans | B: weiche Endung (-an/-in/-en) | **āngins** |
| 30a | stāws | f | Nom pl | stāwjas | stāwjas | stāwas | A: Palatal-j (sj=š, gj=ģ) | **stāwjas** |
| 30a | stāws | f | Gen sg | stāwjas | stāwjas | stāwas | A: Palatal-j (sj=š, gj=ģ) | **stāwjas** |
| 30a | stāws | f | Gen pl | stāwin | stāwin | stāwan | B: weiche Endung (-an/-in/-en) | **stāwin** |
| 30a | stāws | f | Dat sg | stāwjai | stāwjai | stāwai | A: Palatal-j (sj=š, gj=ģ) | **stāwjai** |
| 30a | stāws | f | Dat pl | stāwjamans | stāwjamans | stāwamans | A: Palatal-j (sj=š, gj=ģ) | **stāwjamans** |
| 30a | stāws | f | Akk sg | stāwin | stāwin | stāwan | B: weiche Endung (-an/-in/-en) | **stāwin** |
| 30a | stāws | f | Akk pl | stāwins | stāwins | stāwans | B: weiche Endung (-an/-in/-en) | **stāwins** |
| 31 | līgus | m | Gen sg | līgwas | līgwas | ligwas | ≈ Schreibung (Länge/Diakritika) | **līgwas** |
| 31 | līgus | m | Dat sg | ligusmu | līgusmu | līgusmu | ≈ Schreibung (Länge/Diakritika) | **līgusmu** |
| 31 | līgus | f | Nom pl | līges | līges | līgjas | B: weiche Endung (-an/-in/-en) | **līges** |
| 31 | līgus | f | Gen sg | līges | līges | līgjas | B: weiche Endung (-an/-in/-en) | **līges** |
| 31 | līgus | f | Gen pl | līgin | līgin | līgjan | B: weiche Endung (-an/-in/-en) | **līgin** |
| 31 | līgus | f | Dat sg | līgei | līgei | līgjai | B: weiche Endung (-an/-in/-en) | **līgei** |
| 31 | līgus | f | Dat pl | liģāmans | liģāmans | ligjāmans | A: Palatal-j (sj=š, gj=ģ) | **liģāmans** |
| 31 | līgus | f | Akk sg | līgin | līgin | līgjan | B: weiche Endung (-an/-in/-en) | **līgin** |
| 31 | līgus | f | Akk pl | līgins | līgins | līgjans | B: weiche Endung (-an/-in/-en) | **līgins** |
| 31 | līgus | n | Gen sg | līgwas | līgwas | ligwas | ≈ Schreibung (Länge/Diakritika) | **līgwas** |
| 31 | līgus | n | Dat sg | ligusmu | līgusmu | līgusmu | ≈ Schreibung (Länge/Diakritika) | **līgusmu** |
| 35a | interwallin | n | Nom sg | interwallin | interwallin | interwallan | B: weiche Endung (-an/-in/-en) | **interwallin** |
| 35a | interwallin | n | Gen pl | interwallin | interwallin | interwallan | B: weiche Endung (-an/-in/-en) | **interwallin** |
| 35a | interwallin | n | Akk sg | interwallin | interwallin | interwallan | B: weiche Endung (-an/-in/-en) | **interwallin** |
| 35a | interwallin | n | Akk pl | interwallins | interwallins | interwallans | B: weiche Endung (-an/-in/-en) | **interwallins** |
| 37 | pannin | n | Nom sg | pannin | pannin | pannjan | B: weiche Endung (-an/-in/-en) | **pannin** |
| 37 | pannin | n | Nom pl | panēi | panēi | panjāi | B: weiche Endung (-an/-in/-en) | **panēi** |
| 37 | pannin | n | Gen sg | pannes | pannes | pannjas | B: weiche Endung (-an/-in/-en) | **pannes** |
| 37 | pannin | n | Gen pl | pannin | pannin | pannjan | B: weiche Endung (-an/-in/-en) | **pannin** |
| 37 | pannin | n | Dat sg | paņņu | paņņu | pannju | A: Palatal-j (sj=š, gj=ģ) | **paņņu** |
| 37 | pannin | n | Akk sg | pannin | pannin | pannjan | B: weiche Endung (-an/-in/-en) | **pannin** |
| 37 | pannin | n | Akk pl | pannins | pannins | pannjans | B: weiche Endung (-an/-in/-en) | **pannins** |
| 37a | amzin | n | Nom sg | amzin | amzin | amzjan | B: weiche Endung (-an/-in/-en) | **amzin** |
| 37a | amzin | n | Nom pl | amžāi | amžāi | amzjāi | A: Palatal-j (sj=š, gj=ģ) | **amžāi** |
| 37a | amzin | n | Gen sg | amžas | amžas | amzjas | A: Palatal-j (sj=š, gj=ģ) | **amžas** |
| 37a | amzin | n | Gen pl | amzin | amzin | amzjan | B: weiche Endung (-an/-in/-en) | **amzin** |
| 37a | amzin | n | Dat sg | amžu | amžu | amzju | A: Palatal-j (sj=š, gj=ģ) | **amžu** |
| 37a | amzin | n | Akk sg | amzin | amzin | amzjan | B: weiche Endung (-an/-in/-en) | **amzin** |
| 37a | amzin | n | Akk pl | amzins | amzins | amzjans | B: weiche Endung (-an/-in/-en) | **amzins** |
| 39 | rikīs | m | Nom sg | rikīs | Rikīs | Rikīs | ≈ Schreibung (Länge/Diakritika) | **Rikīs** |
| 39 | rikīs | m | Nom pl | rikijjai | Rikijjai | Rikijjai | ≈ Schreibung (Länge/Diakritika) | **Rikijjai** |
| 39 | rikīs | m | Gen sg | rikijjas | Rikijjas | Rikijjas | ≈ Schreibung (Länge/Diakritika) | **Rikijjas** |
| 39 | rikīs | m | Gen pl | rikijjan | Rikijjan | Rikijjan | ≈ Schreibung (Länge/Diakritika) | **Rikijjan** |
| 39 | rikīs | m | Dat sg | rikijju | Rikijju | Rikijju | ≈ Schreibung (Länge/Diakritika) | **Rikijju** |
| 39 | rikīs | m | Akk sg | rikijjan | Rikijjan | Rikijjan | ≈ Schreibung (Länge/Diakritika) | **Rikijjan** |
| 39 | rikīs | m | Akk pl | rikijjans | Rikijjans | Rikijjans | ≈ Schreibung (Länge/Diakritika) | **Rikijjans** |
| 40 | kūgis | m | Nom pl | kūgei | kūgei | kūgjai | B: weiche Endung (-an/-in/-en) | **kūgei** |
| 40 | kūgis | m | Gen sg | kūges | kūges | kūgjas | B: weiche Endung (-an/-in/-en) | **kūges** |
| 40 | kūgis | m | Gen pl | kūgin | kūgin | kūgjan | B: weiche Endung (-an/-in/-en) | **kūgin** |
| 40 | kūgis | m | Dat sg | kūģu | kūģu | kūgju | A: Palatal-j (sj=š, gj=ģ) | **kūģu** |
| 40 | kūgis | m | Akk sg | kūgin | kūgin | kūgjan | B: weiche Endung (-an/-in/-en) | **kūgin** |
| 40 | kūgis | m | Akk pl | kūgins | kūgins | kūgjans | B: weiche Endung (-an/-in/-en) | **kūgins** |
| 40a | dulzis | m | Nom pl | dulžai | dulžai | dulzjai | A: Palatal-j (sj=š, gj=ģ) | **dulžai** |
| 40a | dulzis | m | Gen sg | dulžas | dulžas | dulzjas | A: Palatal-j (sj=š, gj=ģ) | **dulžas** |
| 40a | dulzis | m | Gen pl | dulzin | dulzin | dulzjan | B: weiche Endung (-an/-in/-en) | **dulzin** |
| 40a | dulzis | m | Dat sg | dulžu | dulžu | dulzju | A: Palatal-j (sj=š, gj=ģ) | **dulžu** |
| 40a | dulzis | m | Dat pl | dulžamans | dulžamans | dulzjamans | A: Palatal-j (sj=š, gj=ģ) | **dulžamans** |
| 40a | dulzis | m | Akk sg | dulzin | dulzin | dulzjan | B: weiche Endung (-an/-in/-en) | **dulzin** |
| 40a | dulzis | m | Akk pl | dulzins | dulzins | dulzjans | B: weiche Endung (-an/-in/-en) | **dulzins** |
| 40b | gīrbis | m | Gen pl | gīrbin | gīrbin | gīrbjan | B: weiche Endung (-an/-in/-en) | **gīrbin** |
| 40b | gīrbis | m | Akk sg | gīrbin | gīrbin | gīrbjan | B: weiche Endung (-an/-in/-en) | **gīrbin** |
| 40b | gīrbis | m | Akk pl | gīrbins | gīrbins | gīrbjans | B: weiche Endung (-an/-in/-en) | **gīrbins** |
| 40c | buccis | m* | Nom pl | — | buccai | buccjai | A: Palatal-j (sj=š, gj=ģ) | **buccai** |
| 40c | buccis | m* | Gen sg | — | buccas | buccjas | A: Palatal-j (sj=š, gj=ģ) | **buccas** |
| 40c | buccis | m* | Gen pl | — | buccin | buccjan | B: weiche Endung (-an/-in/-en) | **buccin** |
| 40c | buccis | m* | Dat sg | — | buccu | buccju | A: Palatal-j (sj=š, gj=ģ) | **buccu** |
| 40c | buccis | m* | Dat pl | — | buccamans | buccjamans | A: Palatal-j (sj=š, gj=ģ) | **buccamans** |
| 40c | buccis | m* | Akk sg | — | buccin | buccjan | B: weiche Endung (-an/-in/-en) | **buccin** |
| 40c | buccis | m* | Akk pl | — | buccins | buccjans | B: weiche Endung (-an/-in/-en) | **buccins** |
| 50 | garkīti | f | Nom pl | garkītes | garkītes | garkītjas | B: weiche Endung (-an/-in/-en) | **garkītes** |
| 50 | garkīti | f | Gen sg | garkītes | garkītes | garkītjas | B: weiche Endung (-an/-in/-en) | **garkītes** |
| 50 | garkīti | f | Gen pl | garkītin | garkītin | garkītjan | B: weiche Endung (-an/-in/-en) | **garkītin** |
| 50 | garkīti | f | Dat sg | garkītei | garkītei | garkītjai | B: weiche Endung (-an/-in/-en) | **garkītei** |
| 50 | garkīti | f | Akk sg | garkītin | garkītin | garkītjan | B: weiche Endung (-an/-in/-en) | **garkītin** |
| 50 | garkīti | f | Akk pl | garkītins | garkītins | garkītjans | B: weiche Endung (-an/-in/-en) | **garkītins** |
| 50a | ķāsi | f | Nom sg | ķāsi | ķāsi | kjāsi | A: Palatal-j (sj=š, gj=ģ) | **ķāsi** |
| 50a | ķāsi | f | Nom pl | ķāšas | ķāšas | kjāsjas | A: Palatal-j (sj=š, gj=ģ) | **ķāšas** |
| 50a | ķāsi | f | Gen sg | ķāšas | ķāšas | kjāsjas | A: Palatal-j (sj=š, gj=ģ) | **ķāšas** |
| 50a | ķāsi | f | Gen pl | ķāsin | ķāsin | kjāsjan | B: weiche Endung (-an/-in/-en) | **ķāsin** |
| 50a | ķāsi | f | Dat sg | ķāšai | ķāšai | kjāsjai | A: Palatal-j (sj=š, gj=ģ) | **ķāšai** |
| 50a | ķāsi | f | Dat pl | ķāšamans | ķāšamans | kjāsjamans | A: Palatal-j (sj=š, gj=ģ) | **ķāšamans** |
| 50a | ķāsi | f | Akk sg | ķāsin | ķāsin | kjāsjan | B: weiche Endung (-an/-in/-en) | **ķāsin** |
| 50a | ķāsi | f | Akk pl | ķāsins | ķāsins | kjāsjans | B: weiche Endung (-an/-in/-en) | **ķāsins** |
| 51 | martī | f | Nom pl | mārtes | mārtes | mārtjas | B: weiche Endung (-an/-in/-en) | **mārtes** |
| 51 | martī | f | Gen sg | mārtes | mārtes | mārtjas | B: weiche Endung (-an/-in/-en) | **mārtes** |
| 51 | martī | f | Gen pl | mārtin | mārtin | mārtjan | B: weiche Endung (-an/-in/-en) | **mārtin** |
| 51 | martī | f | Dat sg | mārtei | mārtei | mārtjai | B: weiche Endung (-an/-in/-en) | **mārtei** |
| 51 | martī | f | Dat pl | marţāmans | marțāmans | martjāmans | A: Palatal-j (sj=š, gj=ģ) | **marţāmans** |
| 51 | martī | f | Akk sg | mārtin | mārtin | mārtjan | B: weiche Endung (-an/-in/-en) | **mārtin** |
| 51 | martī | f | Akk pl | mārtins | mārtins | mārtjans | B: weiche Endung (-an/-in/-en) | **mārtins** |
| 51a | zansī | f | Nom pl | zānšas | zānšas | zānsjas | A: Palatal-j (sj=š, gj=ģ) | **zānšas** |
| 51a | zansī | f | Gen sg | zānšas | zānšas | zānsjas | A: Palatal-j (sj=š, gj=ģ) | **zānšas** |
| 51a | zansī | f | Gen pl | zānsin | zānsin | zānsjan | B: weiche Endung (-an/-in/-en) | **zānsin** |
| 51a | zansī | f | Dat sg | zānšai | zānšai | zānsjai | A: Palatal-j (sj=š, gj=ģ) | **zānšai** |
| 51a | zansī | f | Dat pl | zanšāmans | zanšāmans | zansjāmans | A: Palatal-j (sj=š, gj=ģ) | **zanšāmans** |
| 51a | zansī | f | Akk sg | zānsin | zānsin | zānsjan | B: weiche Endung (-an/-in/-en) | **zānsin** |
| 51a | zansī | f | Akk pl | zānsins | zānsins | zānsjans | B: weiche Endung (-an/-in/-en) | **zānsins** |
| 56 | gigānts | m | Nom pl | gigāntei | gigāntei | gigāntjai | B: weiche Endung (-an/-in/-en) | **gigāntei** |
| 59 | kiŕksni | n* | Nom sg | kiŕksni | kirksni | — | ≈ Schreibung (Länge/Diakritika) | **kiŕksni** |
| 59 | kiŕksni | n* | Nom pl | kiŕksni | kirksni | — | ≈ Schreibung (Länge/Diakritika) | **kiŕksni** |
| 59 | kiŕksni | n* | Gen sg | kiŕksnis | kirksnis | — | ≈ Schreibung (Länge/Diakritika) | **kiŕksnis** |
| 59 | kiŕksni | n* | Gen pl | kiŕksnis | kirksnis | — | ≈ Schreibung (Länge/Diakritika) | **kiŕksnis** |
| 59 | kiŕksni | n* | Dat sg | kiŕksni | kirksni | — | ≈ Schreibung (Länge/Diakritika) | **kiŕksni** |
| 59 | kiŕksni | n* | Dat pl | kiŕksni | kirksni | — | ≈ Schreibung (Länge/Diakritika) | **kiŕksni** |
| 59 | kiŕksni | n* | Akk sg | kiŕksni | kirksni | — | ≈ Schreibung (Länge/Diakritika) | **kiŕksni** |
| 59 | kiŕksni | n* | Akk pl | kiŕksni | kirksni | — | ≈ Schreibung (Länge/Diakritika) | **kiŕksni** |
| 70 | tīrts | f | Nom sg | tirtī | tirtī | tīrtī | ≈ Schreibung (Länge/Diakritika) | **tirtī** |
| 70 | tīrts | f | Nom pl | tīrtes | tīrtes | tīrtjas | B: weiche Endung (-an/-in/-en) | **tīrtes** |
| 70 | tīrts | f | Gen sg | tīrtes | tīrtes | tīrtjas | B: weiche Endung (-an/-in/-en) | **tīrtes** |
| 70 | tīrts | f | Gen pl | tīrtin | tīrtin | tīrtjan | B: weiche Endung (-an/-in/-en) | **tīrtin** |
| 70 | tīrts | f | Dat sg | tīrtei | tīrtei | tīrtjai | B: weiche Endung (-an/-in/-en) | **tīrtei** |
| 70 | tīrts | f | Dat pl | tirtjāmans | tirtāmans | tirtjāmans | A: Palatal-j (sj=š, gj=ģ) | **tirtjāmans** |
| 70 | tīrts | f | Akk sg | tīrtin | tīrtin | tīrtjan | B: weiche Endung (-an/-in/-en) | **tīrtin** |
| 70 | tīrts | f | Akk pl | tīrtins | tīrtins | tīrtjans | B: weiche Endung (-an/-in/-en) | **tīrtins** |
