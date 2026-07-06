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

LEXC_FILES := symbols.lexc root.lexc function_words.lexc proper_nouns.lexc nouns.lexc adjectives.lexc \
              pronouns.lexc numerals.lexc verbs.lexc adverbs.lexc \
              prepositions.lexc conjunctions.lexc particles.lexc interjections.lexc

LEXC_MERGED := build/lexc.merged

.PHONY: all data gen clean cg3-sets cg3-check disambiguate conllu

all: build/base.fst build/lenient.fst

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

# Korrektur-Layer: orthographische Varianten (Degemination, w-Prothese,
# i-Synkope …) auf die kanonische Oberfläche komponiert. Nur als
# Fallback-Analyzer für Formen benutzen, die base.fst nicht kennt.
build/norm.hfst: norm.regex | build/
	hfst-xfst -F norm.regex

build/lenient.fst: build/base.fst build/norm.hfst
	hfst-compose -1 build/base.fst -2 build/norm.hfst | hfst-minimize -o $@

cg3-sets:
	python3 scripts/gen_cg3_sets.py

cg3-check: cg3-sets
	vislcg3 --grammar-only -g cg3/disambiguator.cg3

disambiguate: build/base.fst cg3-sets
	python3 scripts/cg3_pipeline.py --stats

conllu: build/base.fst build/lenient.fst cg3-sets
	python3 scripts/export_conllu.py --out ../data/prussian_silver.conllu

detect-errors: build/base.fst cg3-sets
	python3 scripts/cg3_pipeline.py --detect-errors --limit 200

clean:
	rm -rf build
