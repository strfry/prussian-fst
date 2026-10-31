# Principal-form measurement

Source: `corpus/parsed/twanksta.nvh`, cross-validated (5 folds by lemma). Cells = every slot except the principal forms; slots with variants count as overrides.

## verb (1884 lexemes)

Today's lean NVH for these lexemes: 3046 stems + 14322 override cells = **17368** (1884 entries found).

| principal forms | key | cells right | principal forms stored | overrides | cost |
|---|---|---|---|---|---|
| lemma | num | 86.08 % | 0 | 23605 | 23605 |
| lemma | none | 53.81 % | 0 | 78320 | 78320 |
| lemma | shape | 53.81 % | 0 | 78320 | 78320 |
| lemma, prs.sp3 | num | 91.43 % | 450 | 14366 | 14816 |
| lemma, prs.sp3 | none | 63.12 % | 1454 | 61834 | 63288 |
| lemma, prs.sp3 | shape | 82.02 % | 1454 | 30146 | 31600 |
| lemma, prs.sp3, prt.sp3 | num | 92.45 % | 897 | 12517 | 13414 |
| lemma, prs.sp3, prt.sp3 | none | 69.06 % | 2901 | 51288 | 54189 |
| lemma, prs.sp3, prt.sp3 | shape | 91.51 % | 2901 | 14083 | 16984 |
| lemma, prs.sp3, prt.sp3, part.prs.act.msc.sg.nom | num | 96.12 % | 1290 | 6353 | 7643 |
| lemma, prs.sp3, prt.sp3, part.prs.act.msc.sg.nom | none | 85.55 % | 4248 | 23689 | 27937 |
| lemma, prs.sp3, prt.sp3, part.prs.act.msc.sg.nom | shape | 96.31 % | 4248 | 6049 | 10297 |
| lemma, prs.sp3, prt.sp3, part.prs.act.msc.sg.nom, part.prf.act.msc.sg.nom | num | 97.64 % | 1614 | 3816 | 5430 |
| lemma, prs.sp3, prt.sp3, part.prs.act.msc.sg.nom, part.prf.act.msc.sg.nom | none | 96.40 % | 5413 | 5833 | 11246 |
| lemma, prs.sp3, prt.sp3, part.prs.act.msc.sg.nom, part.prf.act.msc.sg.nom | shape | 97.96 % | 5413 | 3306 | 8719 |

Best configuration: **lemma, prs.sp3, prt.sp3, part.prs.act.msc.sg.nom, part.prf.act.msc.sg.nom** with key **num** (cost 5430).

| slot group | right | cells |
|---|---|---|
| imprt | 96.76 % | 3768 |
| opt | 97.72 % | 1884 |
| part.prf.act | 97.82 % | 43332 |
| part.prf.pss | 97.82 % | 45216 |
| part.prs.act | 97.39 % | 43332 |
| prs | 97.86 % | 7536 |
| prt | 97.64 % | 7536 |
| subj | 97.29 % | 9420 |

Weakest paradigms (absolute overrides):

| par. | right | cells | examples (lemma, slot, Twanksta != rule) |
|---|---|---|---|
| 84 | 0.00 % | 258 | justun imprt.pl2: jāutjaiti != justun; justun imprt.sg2: jāutjais != justun; justun opt: jāutsei != justun |
| 85 | 99.51 % | 49278 | akkintwei part.prs.act.fem.sg.nom: akkinantī != akinantī; enbuttintun part.prs.act.fem.sg.nom: enbuttinantī != enbutinantī; deggintun part.prs.act.fem.sg.nom: degginantī != deginantī |
| 93 | 72.79 % | 860 | auprestun imprt.pl2: auprestaiti != auprestun; auprestun imprt.sg2: auprestais != auprestun; auprestun opt: aupretsei != auprestun |
| 140 | 27.13 % | 258 | aumadlītun imprt.pl2: aumadlīti != None; aumadlītun imprt.sg2: aumadlīs != None; aumadlītun opt: aumadlīsei != None |
| 89 | 93.17 % | 2752 | laztwei opt: lazsei != lāzsei; laztwei part.prf.act.fem.pl.acc: lazzusjans != lāzusjans; laztwei part.prf.act.fem.pl.dat: lazzusjamans != lāzusjamans |
| 88 | 0.00 % | 172 | gestwei imprt.pl2: gessaiti != None; gestwei imprt.sg2: gessais != None; gestwei opt: gessei != None |
| 107 | 0.00 % | 172 | sklāitun imprt.pl2: sklajjaiti != None; sklāitun imprt.sg2: sklajjais != None; sklāitun opt: sklāisei != None |
| 104 | 16.86 % | 172 | austātun opt: aust�sei != None; austātun part.prf.act.fem.pl.acc: auirdusjans != None; austātun part.prf.act.fem.pl.dat: auirdusjamans != None |
| 97 | 96.84 % | 4300 | klīmptwei imprt.pl2: klīmptwei != klīmptweiiti; klīmptwei imprt.sg2: klīmptwei != klīmptweiis; klīmptwei opt: klīmptwei != klīmpsei |
| 125 | 66.57 % | 344 | jāstun imprt.pl2: jāseiti != None; jāstun imprt.sg2: jāseis != None; jāstun opt: jāssei != None |
| 108 | 77.71 % | 516 | sensētun imprt.pl2: sensejjaiti != None; sensētun imprt.sg2: sensejjais != None; sensētun part.prf.act.fem.pl.acc: sensijjusjans != sensejjusjans |
| 80b | 89.05 % | 1032 | kartun part.prf.act.fem.pl.acc: kārusjans != None; kartun part.prf.act.fem.pl.dat: kārusjamans != None; kartun part.prf.act.fem.pl.gen: kārusjan != None |
| 81b | 83.58 % | 688 | wemtwei imprt.pl2: wemjaiti != None; wemtwei imprt.sg2: wemjais != None; wemtwei opt: wemsei != None |
| 99 | 34.88 % | 172 | gibtwei imprt.pl2: gēibaiti != None; gibtwei imprt.sg2: gēibais != None; gibtwei part.prf.act.fem.pl.acc: gibbusjans != gibgusjans |
| 143 | 99.15 % | 11782 | awwautun part.prs.act.fem.sg.nom: awwawintī != awawintī; izdrukkautun part.prs.act.fem.sg.nom: izdrukkawintī != izdrukawintī; etwippjautwei part.prs.act.fem.sg.nom: etwippjawintī != etwipjawintī |

## noun (5921 lexemes)

Today's lean NVH for these lexemes: 354 stems + 863 override cells = **1217** (5920 entries found).

| principal forms | key | cells right | principal forms stored | overrides | cost |
|---|---|---|---|---|---|
| lemma | num | 95.12 % | 0 | 2285 | 2285 |
| lemma | none | 39.66 % | 0 | 28251 | 28251 |
| lemma | shape | 89.97 % | 0 | 4695 | 4695 |
| lemma, sg.gen | num | 97.84 % | 250 | 886 | 1136 |
| lemma, sg.gen | none | 78.58 % | 3955 | 8789 | 12744 |
| lemma, sg.gen | shape | 97.21 % | 567 | 1145 | 1712 |
| lemma, pl.dat | num | 97.69 % | 330 | 945 | 1275 |
| lemma, pl.dat | none | 65.74 % | 4037 | 14012 | 18049 |
| lemma, pl.dat | shape | 94.38 % | 787 | 2297 | 3084 |
| lemma, sg.gen, pl.dat | num | 98.93 % | 580 | 377 | 957 |
| lemma, sg.gen, pl.dat | none | 80.07 % | 7992 | 7000 | 14992 |
| lemma, sg.gen, pl.dat | shape | 97.88 % | 1354 | 745 | 2099 |

Best configuration: **lemma, sg.gen, pl.dat** with key **num** (cost 957).

| slot group | right | cells |
|---|---|---|
| pos | 98.93 % | 35115 |

Weakest paradigms (absolute overrides):

| par. | right | cells | examples (lemma, slot, Twanksta != rule) |
|---|---|---|---|
| 46 | 98.58 % | 2529 | bēgas sg.nom: bēgas != begā; stangas pl.acc: stangans != None; stangas pl.gen: stangan != None |
| 57 | 83.33 % | 162 | dānts pl.nom: None != None; tridānts pl.nom: None != None; nepāts pl.nom: None != None |
| 36 | 96.04 % | 681 | zeimādeināi pl.acc: zeimādeinans != None; zeimādeināi pl.gen: zeimādeinan != None; tūlāi pl.acc: tūlans != None |
| 35 | 99.48 % | 3861 | nōpeisan pl.nom: nōpeisai != nōpeisamans; sprangāi pl.acc: sprangāi != None; fōrum pl.acc: fōrans != fōrums |
| 18 | 0.00 % | 18 | jūss pl.acc: None != None; jūss pl.gen: None != None; jūss pl.nom: None != None |
| 61 | 80.65 % | 93 | līgmens pl.nom: None != None; mēnss pl.nom: None != None; stāmens pl.nom: None != None |
| 19 | 50.00 % | 36 | ainuntkawīds pl.nom: None != None; ainuntkawīds sg.dat: None != None; ainuntkawīds sg.nom: None != None |
| 20 | 16.67 % | 18 | swajs pl.acc: None != None; swajs pl.gen: None != None; swajs pl.nom: None != None |
| 35a | 97.94 % | 678 | Kirsnagārbija pl.acc: Kirsnagārbija != None; Kirsnagārbija pl.gen: Kirsnagārbija != None; Kirsnagārbija pl.nom: Kirsnagārbija != None |
| 10 | 0.00 % | 12 | dis pl.acc: None != None; dis pl.gen: None != None; dis pl.nom: None != None |
| 9 | 0.00 % | 12 | nika pl.acc: None != None; nika pl.gen: None != None; nika pl.nom: None != None |
| 64 | 0.00 % | 12 | zmōi pl.acc: zmānins != None; zmōi pl.gen: zmānin != None; zmōi pl.nom: None != None |
| 62 | 16.67 % | 12 | emmens pl.acc: emnins != emmnins; emmens pl.gen: emnin != emmnin; emmens pl.nom: None != None |
| 60 | 97.03 % | 303 | dwarris pl.acc: dwarrins != None; dwarris pl.gen: dwarrin != None; dwarris pl.nom: dwarris != None |
| 17 | 0.00 % | 9 | wiss pl.acc: None != None; wiss pl.gen: None != None; wiss pl.nom: None != None |

## adj (1167 lexemes)

Today's lean NVH for these lexemes: 202 stems + 1746 override cells = **1948** (1166 entries found).

| principal forms | key | cells right | principal forms stored | overrides | cost |
|---|---|---|---|---|---|
| lemma | num | 94.46 % | 0 | 4414 | 4414 |
| lemma | none | 69.16 % | 0 | 24563 | 24563 |
| lemma | shape | 92.59 % | 0 | 5901 | 5901 |
| lemma, comp.msc.sg.nom | num | 97.19 % | 46 | 2213 | 2259 |
| lemma, comp.msc.sg.nom | none | 90.96 % | 302 | 7111 | 7413 |
| lemma, comp.msc.sg.nom | shape | 95.49 % | 40 | 3546 | 3586 |
| lemma, comp.msc.sg.nom, msc.pl.dat | num | 97.61 % | 109 | 1850 | 1959 |
| lemma, comp.msc.sg.nom, msc.pl.dat | none | 91.59 % | 792 | 6514 | 7306 |
| lemma, comp.msc.sg.nom, msc.pl.dat | shape | 96.21 % | 246 | 2932 | 3178 |
| lemma, comp.msc.sg.nom, msc.sg.gen | num | 98.38 % | 132 | 1256 | 1388 |
| lemma, comp.msc.sg.nom, msc.sg.gen | none | 92.85 % | 662 | 5542 | 6204 |
| lemma, comp.msc.sg.nom, msc.sg.gen | shape | 97.26 % | 176 | 2121 | 2297 |
| lemma, comp.msc.sg.nom, fem.sg.nom | num | 97.56 % | 95 | 1891 | 1986 |
| lemma, comp.msc.sg.nom, fem.sg.nom | none | 92.48 % | 784 | 5830 | 6614 |
| lemma, comp.msc.sg.nom, fem.sg.nom | shape | 97.00 % | 228 | 2321 | 2549 |
| lemma, comp.msc.sg.nom, msc.pl.nom | num | 97.65 % | 101 | 1821 | 1922 |
| lemma, comp.msc.sg.nom, msc.pl.nom | none | 91.97 % | 786 | 6218 | 7004 |
| lemma, comp.msc.sg.nom, msc.pl.nom | shape | 96.56 % | 230 | 2663 | 2893 |
| lemma, comp.msc.sg.nom, neu.sg.nom | num | 98.12 % | 97 | 1455 | 1552 |
| lemma, comp.msc.sg.nom, neu.sg.nom | none | 92.39 % | 467 | 5897 | 6364 |
| lemma, comp.msc.sg.nom, neu.sg.nom | shape | 97.35 % | 130 | 2053 | 2183 |

Best configuration: **lemma, comp.msc.sg.nom, msc.sg.gen** with key **num** (cost 1388).

| slot group | right | cells |
|---|---|---|
| adv | 99.28 % | 3054 |
| comp | 99.23 % | 23414 |
| pos | 96.73 % | 26577 |
| superl | 99.25 % | 24432 |

Weakest paradigms (absolute overrides):

| par. | right | cells | examples (lemma, slot, Twanksta != rule) |
|---|---|---|---|
| 27 | 96.45 % | 16702 | aulāikingis neu.sg.acc: None != None; aulāikingis neu.sg.nom: None != None; niaumenewīngis neu.sg.acc: None != None |
| 25 | 99.57 % | 49475 | debīks adv: tūlan != māises; debīks adv.comp: tūls != māisess; debīks adv.superl: ukatūls != ukamāisess |
| 26 | 97.94 % | 6751 | bass neu.pl.nom: bassāi != basāi; dwejāi fem.pl.acc: dwejjans != None; dwejāi fem.pl.dat: dwejāmans != None |
| 30 | 72.80 % | 511 | izraūjakiskan adv: izraūjakiskan != None; izraūjakiskan comp.fem.pl.acc: izraūjakiskan != izraūjakiskanjans; izraūjakiskan comp.fem.pl.dat: izraūjakiskan != izraūjakiskanjamans |
| 68 | 85.58 % | 437 | embaddusīs fem.pl.acc: embaddusīans != embaddusīs; embaddusīs fem.pl.dat: embaddusīamans != embaddusīs; embaddusīs fem.pl.gen: embaddusīan != embaddusīs |
| 29 | 95.13 % | 759 | gailarūkins fem.pl.acc: gailarūkins != gailarūkinjans; gailarūkins fem.pl.dat: gailarūkins != gailarukinjāmans; gailarūkins fem.pl.gen: gailarūkins != gailarūkinjan |
| 21 | 13.04 % | 23 | aīns fem.pl.acc: aīnans != ainasse; aīns fem.pl.dat: aināmans != ainasse; aīns fem.pl.gen: aīnan != ainasse |
| 70 | 13.04 % | 23 | tīrts fem.pl.acc: tīrtjans != tīrtse; tīrts fem.pl.dat: tirtjāmans != tīrtse; tīrts fem.pl.gen: tīrtjan != tīrtse |
| 69 | 98.47 % | 782 | nipagattawints fem.pl.dat: nipagattawintāmans != nipagatawintāmans; nipagattawints fem.sg.nom: nipagattawintā != nipagatawintā; nipagattawints msc.pl.dat: nipagattawintammans != nipagatawintammans |
| 24 | 0.00 % | 12 | trīs fem.pl.acc: trins != None; trīs fem.pl.dat: trimmans != None; trīs fem.pl.gen: trijjan != None |
| 23 | 16.67 % | 12 | dwāi fem.pl.acc: dwāi != None; dwāi fem.pl.dat: dwēimas != None; dwāi fem.pl.gen: dwejjan != None |
| 28 | 100.00 % | 92 |  |
| 31 | 100.00 % | 1898 |  |

