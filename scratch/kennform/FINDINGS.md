# Principal forms instead of roles: findings

Measured with `measure.py` (full numbers in `REPORT.md`), cross-validated by lemma
(5 folds). Cost = information a lean NVH has to store:
- principal forms that the lemma rule does not predict, plus
- cells that no rule hits (overrides)

"Today" is the current lean NVH (`twanksta_dmlex.nvh`: stemOverrides + override cells)
for the same lexemes. The comparison favours today, because today's rules were tuned
in-sample.

## 1. Principal forms + paradigm number are cheaper than roles + stems

| pos | principal forms | cost | today | change |
|---|---|---|---|---|
| verb | lemma, prs.sp3, prt.sp3, part.prs.act.msc.sg.nom, part.prf.act.msc.sg.nom | 5 430 | 17 368 | −69 % |
| verb | lemma, prs.sp3, prt.sp3 (the Palmaitis triple) | 13 414 | 17 368 | −23 % |
| noun | lemma, sg.gen, pl.dat | 957 | 1 217 | −21 % |
| adj | lemma, comp.msc.sg.nom, msc.sg.gen | 1 388 | 1 948 | −29 % |

The rule model is deliberately primitive: one cell = one principal form + "drop x, add
y", optionally an `uka` prefix and a destressed stem. Nothing per lexeme.

## 2. What the paradigm number is for

Compare the keys: `num` = Twanksta number, `shape` = last two letters of every
principal form (a data-driven stem class), `none` = no key.

- **Once the principal forms are given, shape almost replaces the number.** Cells
  right: verb 97.96 % (shape) vs 97.64 % (num); noun 97.88 vs 98.93 %; adj 97.26 vs
  98.38 %.
- **The number earns its keep in stage 0.** It predicts the principal forms from the
  lemma: verb 1 614 vs 5 413 forms stored, noun 580 vs 1 354.
- **Without any key everything collapses** (noun 80 %, verb finite ≈ 63–69 % with
  three forms).

So the number is mostly a *principal-form predictor* (what is the gen.sg / prs.sp3 /
prt.sp3 of this lemma), and only secondarily an ending-set selector. That matches
Mažiulis: he classifies by stem class, which is visible in the principal forms. The
numbers encode which stem class a lemma belongs to.

## 3. The accent rule stays, as one function

Shortening every macron and simplifying every geminate of the stem (`destress`, the
same reduction as `gen/accent.regex` Shorten + Degem) is needed. Without it:
- verb cost 11 972 instead of 5 430 (passive participles `akkintwei → akintā`)
- noun cost 2 087 instead of 957 (mobile ā-stems `bilā / billas`)

It is one string function, not a transducer, and it applies per rule: the rule says
whether the stem is destressed. No `^ ~ >` markers in stems.

## 4. Size of a hard-coded table

Rules that actually fire (all data, key `num`):

| pos | (number, slot) pairs | rules |
|---|---|---|
| verb | 6 708 | 10 392 |
| noun | 265 | 328 |
| adj | 523 | 773 |

Most verb pairs are the 72 participle cells × 78 numbers. Participles decline like
adjectives once their msc.sg.nom is known, so a factored table would be:
- finite verb: number × 21 slots
- participle declension: a few adjective-like types
- noun: 55 numbers × 8 slots
- adjective: 13 numbers × ≈ 75 slots

That is small enough to write as a Python table instead of lexc + roles + atoms.

## 5. TODO

- [ ] Factor participle declension out of the verb table and re-measure. The
      expectation is the same cost with far fewer rules.
- [ ] Map every Twanksta number to its Mažiulis stem class. Use `palmaitis2006.json`
      guide forms and the grammar ch. 3/4/7. Flag numbers whose `shape` rules
      coincide; these are candidates for merging or for later re-decisions.
- [ ] Lowest-coverage numbers. They have no or a wrong rule; check each against
      Twanksta:
  - verb 84, 88, 107, 140, 99, 104
  - adj 21, 23, 24, 70
  - noun 9, 10, 17, 18, 20, 64
- [ ] Verb 84 `justun` (pres `jāut-`): suppletive present. It needs a 4th principal
      form or stays an override.
- [ ] Check whether part.prs.act length/gemination (`akkinantī` vs `akinantī`) follows
      from the present-stem gemination rule (memory: participle length). If it does,
      the 4th principal form drops out.
- [ ] Decide: lean NVH format `stemOverrides` → principal forms (corpus repo change).
