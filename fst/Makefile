# Build the Prussian full-form lookup FST (HFST stack).
#
# Target:
#   make         — build base.fst from all .lexc files
#   make clean

LEXC_FILES := symbols.lexc root.lexc function_words.lexc nouns.lexc adjectives.lexc \
              pronouns.lexc numerals.lexc verbs.lexc adverbs.lexc \
              prepositions.lexc conjunctions.lexc particles.lexc interjections.lexc

LEXC_MERGED := build/lexc.merged

.PHONY: all gen clean

all: build/base.fst

build/:
	mkdir -p build

gen:
	python3 scripts/gen_lexc.py

$(LEXC_MERGED): $(LEXC_FILES) | build/
	cat $(LEXC_FILES) > $@

build/base.fst: $(LEXC_MERGED) | build/
	hfst-lexc -o $@ $(LEXC_MERGED)

clean:
	rm -rf build
