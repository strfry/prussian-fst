"""Verbale Morphologie.

Verb-Einträge kommen aus data/gold/goldstandard_verben_fst.json als
{paradigm, lemma, tense, stamm, suffixe} und brauchen aktuell keine
Aufbereitung. Die reflexive Enklitik ` si` (nur P106b smeītwei) wird bei
der Emission (lexd.py) via tags.split_reflexive abgespalten und als +Refl
getaggt — Klitik = Syntax, außerhalb der Verbmorphologie.

Künftiger Ausbau (Partizipien/Modi, docs/ORTHO_RULES.md §2) gehört hierher.
"""

VERB_POS = "+V"


def groups(verb_entries: list[dict]):
    """(Gruppenschlüssel, Tag-Präfix, 'verb', Eintrag) je Verbeintrag."""
    for e in verb_entries:
        key = ("V", e["paradigm"], e["tense"])
        yield key, VERB_POS, "verb", e
