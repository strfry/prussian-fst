# Build the Prussian full-form lookup FST (HFST stack).
#
# Target:
#   make              — build base.fst from all .lexc files
#   make data         — download current twanksta_entries.json from GitHub release
#   make cg3-sets     — generierte CG3-Sets/-Regeln aus valence.json
#   make cg3-check    — Syntaxcheck des CG3-Disambiguators
#   make disambiguate — Vollkorpus-Lauf mit Ambiguitätsstatistik (stdout)
#   make conllu       — CoNLL-U-Silberexport aller Korpora nach ../data/
#   make clean

RELEASE_TAG := $(shell curl -sL "https://api.github.com/repos/strfry/prussian-corpus/releases/latest" | \
                python3 -c "import json,sys; print(json.load(sys.stdin)['tag_name'])" 2>/dev/null)
DATA_DIR    := ../data/external
TWANKSTA_URL := https://github.com/strfry/prussian-corpus/releases/download/$(RELEASE_TAG)/twanksta_entries.json

LEXC_FILES := symbols.lexc root.lexc function_words.lexc proper_nouns.lexc proper_nouns_auto.lexc nouns.lexc adjectives.lexc \
              pronouns.lexc numerals.lexc verbs.lexc adverbs.lexc \
              prepositions.lexc conjunctions.lexc particles.lexc interjections.lexc

LEXC_MERGED := build/lexc.merged

.PHONY: all data gen clean cg3-sets cg3-check disambiguate conllu hfstol

all: build/base.hfstol build/lenient.hfstol

data:
	curl -fsSL "$(TWANKSTA_URL)" -o $(DATA_DIR)/twanksta_entries.json

build/:
	mkdir -p build

gen:
	python3 scripts/gen_lexc.py

$(LEXC_MERGED): $(LEXC_FILES) | build/
	cat $(LEXC_FILES) > $@

build/base.fst: $(LEXC_MERGED) | build/
	hfst-lexc -o $@ $(LEXC_MERGED)

# Optimized-lookup transducer für pyhfst (invertiert: surface → analysis)
# build/base.fst bildet analysis → surface ab, für Lookup brauchen wir
# surface → analysis, also wird vor dem Format-Export invertiert.
build/base.hfstol: build/base.fst
	python3 -c "import hfst; tr = hfst.HfstInputStream('$<').read(); tr.invert(); hfst.HfstOutputStream(filename='$(basename $@)_inv.fst').write(tr);"
	hfst-fst2fst -f optimized-lookup-unweighted -o $@ $(basename $@)_inv.fst
	rm -f $(basename $@)_inv.fst

# Korrektur-Layer: orthographische Varianten (Degemination, w-Prothese,
# i-Synkope …) auf die kanonische Oberfläche komponiert. Nur als
# Fallback-Analyzer für Formen benutzen, die base.fst nicht kennt.
build/norm.hfst: norm.regex | build/
	hfst-xfst -F norm.regex

build/lenient.fst: build/base.fst build/norm.hfst
	hfst-compose -1 build/base.fst -2 build/norm.hfst | hfst-minimize -o $@

build/lenient.hfstol: build/lenient.fst
	python3 -c "import hfst; tr = hfst.HfstInputStream('$<').read(); tr.invert(); hfst.HfstOutputStream(filename='$(basename $@)_inv.fst').write(tr);"
	hfst-fst2fst -f optimized-lookup-unweighted -o $@ $(basename $@)_inv.fst
	rm -f $(basename $@)_inv.fst

cg3-sets:
	python3 scripts/gen_cg3_sets.py

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
	python3 scripts/cg3_pipeline.py --stats

conllu: build/base.hfstol build/lenient.hfstol cg3-sets $(CG3_BINS)
	python3 scripts/export_conllu.py --out ../data/prussian_silver.conllu

detect-errors: build/base.hfstol cg3-sets $(CG3_BINS)
	python3 scripts/cg3_pipeline.py --detect-errors --limit 200

# Bulk-Zero-False-Alarm-Regression: Validator über die attestierten
# Korpora — Flags auf attestiertem Text sind (fast immer) Fehlalarme.
validate-corpus: build/base.hfstol cg3-sets $(CG3_BINS)
	python3 scripts/cg3_pipeline.py --validate --validate-summary
	python3 scripts/cg3_pipeline.py --validate --validate-summary \
	    --corpus-md ../../prussian-corpus/parsed/awizi_articles \
	    --corpus-md ../../prussian-corpus/parsed/twanksta_articles

clean:
	rm -rf build
