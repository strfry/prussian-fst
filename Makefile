# Build the Prussian full-form lookup FST (python-hfst stack).
#
# Der FST-Build läuft über das python-`hfst`-Modul (src/prussian_fst/build_fst.py),
# nicht über die hfst-CLI-Werkzeuge — einzige Build-Abhängigkeit ist damit das
# pip-Paket `hfst` (bereits in pyproject.toml).  Lookup zur Laufzeit: pyhfst.
#
# Target:
#   make              — build base.fst from all .lexc files
#   make gen          — generiere .lexc-Dateien aus dem Dictionary
#                       (kanonische Quelle: ../corpus/parsed/twanksta_entries.json)
#   make cg3-sets     — generierte CG3-Sets/-Regeln aus valence.json
#   make cg3-check    — Syntaxcheck des CG3-Disambiguators
#   make disambiguate — Vollkorpus-Lauf mit Ambiguitätsstatistik (stdout)
#   make conllu       — CoNLL-U-Silberexport aller Korpora nach data/
#   make links        — desc-Ref-Resolver → build/links.json (Input fürs
#                       Chunk-Clustering in prussian-embeddings)
#   make clean

LEXC_FILES := lexc/symbols.lexc lexc/root.lexc lexc/function_words.lexc lexc/proper_nouns.lexc lexc/proper_nouns_auto.lexc lexc/nouns.lexc lexc/adjectives.lexc \
              lexc/pronouns.lexc lexc/numerals.lexc lexc/verbs.lexc lexc/adverbs.lexc \
              lexc/prepositions.lexc lexc/conjunctions.lexc lexc/particles.lexc lexc/interjections.lexc

LEXC_MERGED := build/lexc.merged

# Python-Ersatz für die hfst-CLI-Werkzeuge (siehe src/prussian_fst/build_fst.py).
# uv run = Projekt-Env, damit hfst überall verfügbar ist (auch ohne System-Install).
HFST := uv run python src/prussian_fst/build_fst.py

.PHONY: all gen clean cg3-sets cg3-check disambiguate conllu hfstol links astem adj istem ustem

all: build/base.hfstol build/macron.hfstol build/lenient.hfstol build/base.gen.hfstol

build/:
	mkdir -p build

gen:
	python3 src/prussian_fst/gen_lexc.py

$(LEXC_MERGED): $(LEXC_FILES) | build/
	cat $(LEXC_FILES) > $@

build/base.fst: $(LEXC_MERGED) | build/
	$(HFST) lexc $(LEXC_MERGED) $@

# Optimized-lookup transducer für pyhfst (invertiert: surface → analysis).
# build/base.fst bildet analysis → surface ab, für Lookup brauchen wir
# surface → analysis; build_fst.py invertiert vor dem Format-Export.
build/base.hfstol: build/base.fst
	$(HFST) hfstol $< $@

# Generation FST (analysis→surface, un-inverted) — counterpart to
# build/base.hfstol.  Used by api.generate() for paradigm queries
# (lemma+tags → surface form).
build/base.gen.hfstol: build/base.fst
	$(HFST) hfstol-gen $< $@

# ── Handgeschriebener generativer Prototyp: bewegliche a-Stämme (Neutrum) ──
# Nicht-zirkuläres Gegenstück zu gen/paradigm_survey.py: eine von Hand
# formulierte Stammklasse (gen/astem.lexc, Stamm+Endung mit Akzentgrenze ^)
# komponiert mit der Akzentregel (gen/accent.regex, Makron-/Geminaten-
# reduktion vor ^) → Generierungs-FST analysis→surface.
#   make astem                    # baut build/gen-astem.gen.hfstol
# Test (analysis→surface, nicht-zirkulär gegen Twanksta) z. B. mit:
#   uv run python -c "import sys; sys.path.insert(0,'src'); \
#     from prussian_fst.fst_lookup import glookup_batch; \
#     print(glookup_batch(['ōriganan+N+Neut+Pl+Nom'], 'build/gen-astem.gen.hfstol'))"
#   → {'ōriganan+N+Neut+Pl+Nom': ['origanāi']}
astem: build/gen-astem.gen.hfstol

build/gen-astem.fst: gen/astem.lexc | build/
	$(HFST) lexc $< $@

build/gen-accent.hfst: gen/accent.regex | build/
	$(HFST) xfst $<

build/gen-astem.composed.fst: build/gen-astem.fst build/gen-accent.hfst
	$(HFST) compose $@ build/gen-astem.fst build/gen-accent.hfst

build/gen-astem.gen.hfstol: build/gen-astem.composed.fst
	$(HFST) hfstol-gen $< $@

# Erweiterung auf Adjektive (drei Genera, feste + mobile Klasse); teilt sich
# die Akzentregel gen/accent.regex mit dem Nomen-Prototyp.
#   make adj                      # baut build/gen-adj.gen.hfstol
adj: build/gen-adj.gen.hfstol

build/gen-adj.fst: gen/adj.lexc | build/
	$(HFST) lexc $< $@

build/gen-adj.composed.fst: build/gen-adj.fst build/gen-accent.hfst
	$(HFST) compose $@ build/gen-adj.fst build/gen-accent.hfst

build/gen-adj.gen.hfstol: build/gen-adj.composed.fst
	$(HFST) hfstol-gen $< $@

# Dritte Stammklasse: i-Stämme (fest Par.52 + mobil Par.53); teilt sich
# gen/accent.regex. Erweiterter, nicht-zirkulärer Deckungstest gegen ALLE
# i-Stamm-Einträge: uv run python gen/coverage_gen.py
#   make istem                    # baut build/gen-istem.gen.hfstol
istem: build/gen-istem.gen.hfstol

build/gen-istem.fst: gen/istem.lexc | build/
	$(HFST) lexc $< $@

build/gen-istem.composed.fst: build/gen-istem.fst build/gen-accent.hfst
	$(HFST) compose $@ build/gen-istem.fst build/gen-accent.hfst

build/gen-istem.gen.hfstol: build/gen-istem.composed.fst
	$(HFST) hfstol-gen $< $@

# u-Stämme (fest Par.42 + mobil Par.43 + Neut Par.44); teilt sich gen/accent.regex.
# Deckungstest: uv run python gen/coverage_gen.py --family ustem
#   make ustem                    # baut build/gen-ustem.gen.hfstol
ustem: build/gen-ustem.gen.hfstol

build/gen-ustem.fst: gen/ustem.lexc | build/
	$(HFST) lexc $< $@

build/gen-ustem.composed.fst: build/gen-ustem.fst build/gen-accent.hfst
	$(HFST) compose $@ build/gen-ustem.fst build/gen-accent.hfst

build/gen-ustem.gen.hfstol: build/gen-ustem.composed.fst
	$(HFST) hfstol-gen $< $@

# Correction layers, one stage per phenomenon (norm/*.regex → build/norm-*.hfst).
# Composed onto the canonical surface; use only as fallback analyzer for
# forms not covered by the stricter stages.  The xfst script writes its
# own output (`save stack build/norm-<phenomenon>.hfst`).
build/norm-%.hfst: norm/%.regex | build/
	$(HFST) xfst $<

# Stufe 1: nur Makron-Verlust (ā ē ī ō ū → a e i o u)
build/macron.fst: build/base.fst build/norm-macron.hfst
	$(HFST) compose $@ build/base.fst build/norm-macron.hfst

# Stufe 2: Makron + Degemination + sonstige Orthographie-Varianten.
# Komposition ist assoziativ, daher in einem Rutsch base .o. macron .o. degem
# .o. ortho, minimiert.
build/lenient.fst: build/base.fst build/norm-macron.hfst build/norm-degem.hfst build/norm-ortho.hfst
	$(HFST) compose $@ build/base.fst build/norm-macron.hfst build/norm-degem.hfst build/norm-ortho.hfst

build/macron.hfstol build/lenient.hfstol: build/%.hfstol: build/%.fst
	$(HFST) hfstol $< $@

cg3-sets:
	python3 src/prussian_fst/gen_cg3_sets.py

build/cg3/:
	mkdir -p build/cg3

build/cg3/disambiguator.bin: cg3/disambiguator.cg3 cg3/generated-sets.cg3 | build/cg3/
	cg-comp cg3/disambiguator.cg3 build/cg3/disambiguator.bin

build/cg3/dependency.bin: cg3/dependency.cg3 | build/cg3/
	cg-comp cg3/dependency.cg3 build/cg3/dependency.bin

build/cg3/validator.bin: cg3/validator.cg3 | build/cg3/
	cg-comp cg3/validator.cg3 build/cg3/validator.bin

CG3_BINS = build/cg3/disambiguator.bin build/cg3/dependency.bin build/cg3/validator.bin

cg3-check: cg3-sets $(CG3_BINS)
	@echo "Alle Grammatiken syntaktisch OK."

disambiguate: build/base.hfstol cg3-sets $(CG3_BINS)
	python3 src/prussian_fst/cg3_pipeline.py --stats

conllu: build/base.hfstol build/lenient.hfstol cg3-sets $(CG3_BINS)
	uv run python src/prussian_fst/export_conllu.py --out data/prussian_silver.conllu

detect-errors: build/base.hfstol cg3-sets $(CG3_BINS)
	python3 src/prussian_fst/cg3_pipeline.py --detect-errors --limit 200

# desc-Ref-Resolver: Verweise in twanksta-descs über die Analyzer-Kaskade
# auflösen → build/links.json.  Wichtig: nach Änderungen an linker.py neu
# laufen lassen und die Kette weiterfahren (chunks bauen, Embeddings
# generieren, MCP-Server neu starten) — siehe ../embeddings/README.md.
#
# Die Abhängigkeit von `gen` macht Dictionary-Änderungen für make sichtbar:
# gen_lexc schreibt nur tatsächlich geänderte .lexc-Dateien, daher läuft die
# FST-Kette nur an, wenn sich der Inhalt von ../corpus/parsed/... änderte.
links: gen build/base.hfstol build/macron.hfstol build/lenient.hfstol
	uv run python -m prussian_fst.linker --stats

# Bulk-Zero-False-Alarm-Regression: Validator über die attestierten
# Korpora — Flags auf attestiertem Text sind (fast immer) Fehlalarme.
validate-corpus: build/base.hfstol cg3-sets $(CG3_BINS)
	python3 src/prussian_fst/cg3_pipeline.py --validate --validate-summary
	python3 src/prussian_fst/cg3_pipeline.py --validate --validate-summary \
	    --corpus-md ../corpus/parsed/awizi_articles \
	    --corpus-md ../corpus/parsed/twanksta_articles

clean:
	rm -rf build
