# Build the Prussian full-form lookup FST (python-hfst stack).
#
# Der FST-Build läuft über das python-`hfst`-Modul (src/prussian_fst/build_fst.py),
# nicht über die hfst-CLI-Werkzeuge — einzige Build-Abhängigkeit ist damit das
# pip-Paket `hfst` (bereits in pyproject.toml).  Lookup zur Laufzeit: pyhfst.
#
# Target:
#   make              — build base.fst from all .lexc files
#   make paradigms    — re-derive the paradigm table gen/paradigms.json from the lean NVH
#   make cg3-sets     — generierte CG3-Sets/-Regeln aus valence.json
#   make cg3-check    — Syntaxcheck des CG3-Disambiguators
#   make disambiguate — Vollkorpus-Lauf mit Ambiguitätsstatistik (stdout)
#   make conllu       — CoNLL-U-Silberexport aller Korpora nach data/
#   make links        — ↑-Verweise Form → Grundform → build/links.json (Input fürs
#                       Chunk-Clustering in prussian-embeddings)
#   make clean

# Python-Ersatz für die hfst-CLI-Werkzeuge (siehe src/prussian_fst/build_fst.py).
# uv run = Projekt-Env, damit hfst überall verfügbar ist (auch ohne System-Install).
HFST := uv run python src/prussian_fst/build_fst.py
# Lean NVH (word list, principal forms and overrides, invariables); defined before
# the rules because make expands prerequisites while reading.
LEAN_NVH := ../corpus/parsed/twanksta_dmlex.nvh

.PHONY: all clean cg3-sets cg3-check disambiguate conllu hfstol links paradigms analyzer analyzer-parity

all: build/base.hfstol build/macron.hfstol build/lenient.hfstol build/base.gen.hfstol

build/:
	mkdir -p build

# base.fst is compiled from the baked merged lexc: the paradigm generator
# (gen/generator.py + gen/paradigms.json) applied to the lean NVH, plus the
# hand-written closed classes (function_words, pronouns). base.hfstol (inverted)
# is the analyzer, base.gen.hfstol (not inverted) the generator, from ONE source.
# Coverage against the frozen Twanksta gold: `make analyzer-parity`.
GEN_SOURCES := gen/build_analyzer.py gen/generator.py gen/compress_forms.py gen/paradigms.json

build/analyzer.lexc: $(GEN_SOURCES) lexc/*.lexc $(LEAN_NVH) | build/
	uv run python gen/build_analyzer.py --no-compile --nvh $(LEAN_NVH)

build/base.fst: build/analyzer.lexc | build/
	$(HFST) lexc $< $@

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

# Paradigm table: per paradigm number and slot, the source principal form and its
# suffix rules, learned from the lean NVH expanded with the current table.
paradigms:
	uv run python gen/derive_paradigms.py --lean $(LEAN_NVH)

# Opt-in analyzer from the same bake (PRUSSIAN_FST=build/analyzer.hfstol).
build/analyzer.hfstol: $(GEN_SOURCES) lexc/*.lexc $(LEAN_NVH) | build/
	uv run python gen/build_analyzer.py --nvh $(LEAN_NVH)

analyzer: build/analyzer.hfstol

analyzer-parity: $(GEN_SOURCES) $(LEAN_NVH)
	uv run python gen/build_analyzer.py --parity --nvh $(LEAN_NVH)

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

# Rektion/Valenz aus den Twanksta-descs (Prä-/Postpositionen, Verben).
build/valence.json: src/prussian_fst/export_valence.py ../corpus/parsed/twanksta_entries.json | build/
	python3 src/prussian_fst/export_valence.py

cg3-sets: build/valence.json
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

# ↑-Verweise der Formeinträge (Form → Grundform-Eintrag) auflösen
# → build/links.json.  Wichtig: nach Änderungen an linker.py neu
# laufen lassen und die Kette weiterfahren (chunks bauen, Embeddings
# generieren, MCP-Server neu starten) — siehe ../embeddings/README.md.
#
# Dictionary-Änderungen sieht make über $(LEAN_NVH) (Abhängigkeit von base.fst).
links: build/base.hfstol build/macron.hfstol build/lenient.hfstol
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
