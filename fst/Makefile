# Build the Prussian morphological FST (HFST stack).
#
# Targets:
#   make           — build prusaspira (default standard)
#   make twanksta  — build twanksta
#   make clean

LEXC_FILES := symbols.lexc root.lexc nom_stems.lexc pronouns.lexc numerals.lexc verb_stems.lexc verb_participles.lexc adverbs.lexc conjunctions.lexc prepositions.lexc particles.lexc interjections.lexc
LEXC_MERGED := build/lexc.merged

TWOL_STRESS := stress.twolc

.PHONY: all prusaspira twanksta clean

all: prusaspira

build:
	mkdir -p build

$(LEXC_MERGED): $(LEXC_FILES) | build
	cat $(LEXC_FILES) > $@

build/base.hfst: $(LEXC_MERGED) | build
	hfst-lexc -o $@ $(LEXC_MERGED)

build/stress.twolc.hfst: $(TWOL_STRESS)
	hfst-twolc -o $@ $(TWOL_STRESS)

prusaspira: build/base.hfst build/stress.twolc.hfst
	hfst-compose -o build/prusaspira.hfst build/base.hfst build/stress.twolc.hfst
	@echo "Built build/prusaspira.hfst"

twanksta: build/base.hfst build/stress.twolc.hfst
	hfst-compose -o build/twanksta.hfst build/base.hfst build/stress.twolc.hfst
	@echo "Built build/twanksta.hfst"

clean:
	rm -rf build
