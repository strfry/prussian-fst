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

.PHONY: all gen clean cg3-sets cg3-check disambiguate conllu hfstol links

all: build/base.hfstol build/macron.hfstol build/lenient.hfstol

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

# Korrektur-Layer, eine Stufe pro Phänomen (norm/*.regex → build/norm-*.hfst).
# Auf die kanonische Oberfläche komponiert; nur als Fallback-Analyzer für
# Formen benutzen, die die strengeren Stufen nicht kennen.  Das xfst-Skript
# schreibt sein Ergebnis selbst (`save stack build/norm-<phänomen>.hfst`).
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
