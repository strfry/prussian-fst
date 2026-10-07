# Build the Prussian full-form lookup FST (python-hfst stack).
#
# Der FST-Build läuft über das python-`hfst`-Modul (src/prussian_fst/build_fst.py),
# nicht über die hfst-CLI-Werkzeuge — einzige Build-Abhängigkeit ist damit das
# pip-Paket `hfst` (bereits in pyproject.toml).  Lookup zur Laufzeit: pyhfst.
#
# Target:
#   make              — build base.fst from all .lexc files
#   make atoms        — datenfreie Atome des Kern-Generators (gen/atom_fst.py)
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

.PHONY: all gen clean cg3-sets cg3-check disambiguate conllu hfstol links atoms atom analyzer analyzer-parity

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

# ── Generativer FST: datenfreie Atome (kein twanksta, keine Wortliste) ──
# Die datenfreie Kern des Generators: gen/generator.py kennt nur die HAND-
# geschriebenen Grammatiken gen/*.lexc. Jedes Atom ist eine Endungstabelle
# (gen/<fam>.lexc, gen/adj.lexc, gen/verb.lexc) mit zyklischem Stamm-Kopierer
# ("STEM* + tag"), komponiert mit gen/accent.hfst und als OL exportiert:
#   build/gen-<family>-<paradigm>[-<role>].hfstol
build/gen-accent.hfst: gen/accent.regex | build/
	$(HFST) xfst $<

# Genau das liest der Generator zur Laufzeit (pyhfst.lookup(stem + tag)) — die
# Atome sind der einzige Build-Output des Kern-Generators. Ein hfst.compile_lexc_file
# funktioniert pro Prozess nur einmal, deshalb baut --all je Atom einen Subprozess.
#   make atoms                                       # alle 245 Atome
#   make atom POS=verb PARADIGM=132 ROLE=nonfin      # ein einzelnes
atoms: build/gen-accent.hfst
	uv run python gen/atom_fst.py --all -j$$(nproc)

# ── Option B: gebackener, lemma-fähiger Giella-Analyzer ──
# Open-Class-Morphologie aus gen/*.lexc, Stämme/Overrides aus der lean NVH
# (Twanksta-DMLex).  Default-Analyzer bleibt base.hfstol, bis das B-Gate
# (Deckungsparität) erfüllt ist; umschalten mit PRUSSIAN_FST=build/analyzer.hfstol.
LEAN_NVH := ../corpus/parsed/twanksta_dmlex.nvh

build/analyzer.hfstol: gen gen/build_analyzer.py gen/*.lexc $(LEAN_NVH) | build/
	uv run python gen/build_analyzer.py

analyzer: build/analyzer.hfstol

analyzer-parity: gen/build_analyzer.py $(LEAN_NVH)
	uv run python gen/build_analyzer.py --parity

atom: build/gen-accent.hfst
	@test -n "$(POS)" -a -n "$(PARADIGM)" -a -n "$(ROLE)" || \
	    { echo "Aufruf: make atom POS=noun PARADIGM=53 ROLE=obl"; exit 1; }
	uv run python gen/atom_fst.py $(POS) $(PARADIGM) $(ROLE)

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
