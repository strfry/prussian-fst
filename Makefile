# Build the Prussian full-form lookup FST (HFST stack).
#
# Target:
#   make              — build base.fst from all .lexc files
#   make data         — download current twanksta_entries.json from GitHub release
#   make gen          — generiere .lexc-Dateien aus twanksta_entries.json
#   make cg3-sets     — generierte CG3-Sets/-Regeln aus valence.json
#   make cg3-check    — Syntaxcheck des CG3-Disambiguators
#   make disambiguate — Vollkorpus-Lauf mit Ambiguitätsstatistik (stdout)
#   make conllu       — CoNLL-U-Silberexport aller Korpora nach data/
#   make clean

RELEASE_TAG := $(shell curl -sL "https://api.github.com/repos/strfry/prussian-corpus/releases/latest" | \
                python3 -c "import json,sys; print(json.load(sys.stdin)['tag_name'])" 2>/dev/null)
DATA_DIR    := data/external
TWANKSTA_URL := https://github.com/strfry/prussian-corpus/releases/download/$(RELEASE_TAG)/twanksta_entries.json

LEXC_FILES := lexc/symbols.lexc lexc/root.lexc lexc/function_words.lexc lexc/proper_nouns.lexc lexc/proper_nouns_auto.lexc lexc/nouns.lexc lexc/adjectives.lexc \
              lexc/pronouns.lexc lexc/numerals.lexc lexc/verbs.lexc lexc/adverbs.lexc \
              lexc/prepositions.lexc lexc/conjunctions.lexc lexc/particles.lexc lexc/interjections.lexc

LEXC_MERGED := build/lexc.merged

.PHONY: all data gen clean cg3-sets cg3-check disambiguate conllu hfstol

all: build/base.hfstol build/macron.hfstol build/lenient.hfstol

data:
	curl -fsSL "$(TWANKSTA_URL)" -o $(DATA_DIR)/twanksta_entries.json

build/:
	mkdir -p build

gen:
	python3 src/prussian_fst/gen_lexc.py

$(LEXC_MERGED): $(LEXC_FILES) | build/
	cat $(LEXC_FILES) > $@

build/base.fst: $(LEXC_MERGED) | build/
	hfst-lexc -o $@ $(LEXC_MERGED)

# Optimized-lookup transducer für pyhfst (invertiert: surface → analysis)
# build/base.fst bildet analysis → surface ab, für Lookup brauchen wir
# surface → analysis, also wird vor dem Format-Export invertiert.
build/base.hfstol: build/base.fst
	hfst-invert -i $< -o $(basename $@)_inv.fst
	hfst-fst2fst -f optimized-lookup-unweighted -o $@ $(basename $@)_inv.fst
	rm -f $(basename $@)_inv.fst

# Korrektur-Layer, eine Stufe pro Phänomen (norm/*.regex → build/norm-*.hfst).
# Auf die kanonische Oberfläche komponiert; nur als Fallback-Analyzer für
# Formen benutzen, die die strengeren Stufen nicht kennen.
build/norm-%.hfst: norm/%.regex | build/
	hfst-xfst -F $<

# Stufe 1: nur Makron-Verlust (ā ē ī ō ū → a e i o u)
build/macron.fst: build/base.fst build/norm-macron.hfst
	hfst-compose -1 build/base.fst -2 build/norm-macron.hfst | hfst-minimize -o $@

# Stufe 2: Makron + Degemination + sonstige Orthographie-Varianten
build/lenient.fst: build/base.fst build/norm-macron.hfst build/norm-degem.hfst build/norm-ortho.hfst
	hfst-compose -1 build/norm-macron.hfst -2 build/norm-degem.hfst -o build/norm-tmp1.fst
	hfst-compose -1 build/norm-tmp1.fst -2 build/norm-ortho.hfst -o build/norm-tmp2.fst
	hfst-compose -1 build/base.fst -2 build/norm-tmp2.fst | hfst-minimize -o $@
	rm -f build/norm-tmp1.fst build/norm-tmp2.fst

build/macron.hfstol build/lenient.hfstol: build/%.hfstol: build/%.fst
	hfst-invert -i $< -o $(basename $@)_inv.fst
	hfst-fst2fst -f optimized-lookup-unweighted -o $@ $(basename $@)_inv.fst
	rm -f $(basename $@)_inv.fst

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

# Bulk-Zero-False-Alarm-Regression: Validator über die attestierten
# Korpora — Flags auf attestiertem Text sind (fast immer) Fehlalarme.
validate-corpus: build/base.hfstol cg3-sets $(CG3_BINS)
	python3 src/prussian_fst/cg3_pipeline.py --validate --validate-summary
	python3 src/prussian_fst/cg3_pipeline.py --validate --validate-summary \
	    --corpus-md ../corpus/parsed/awizi_articles \
	    --corpus-md ../corpus/parsed/twanksta_articles

clean:
	rm -rf build
