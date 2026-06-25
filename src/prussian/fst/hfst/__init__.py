"""HFST-nativer Analysatorzweig (lexd-Backend).

Aus data/gold + Wortliste wird eine markierte Morphotaktik als lexd-Grammatik
generiert und durchgängig in HFST komponiert:

    lexd-Lexikon  ∘  Phonologie-/Akzentregeln (hfst.rules)   = analyser
                  ∘  Orthographie-Faltung     (hfst.fold)     = lenient

Die Quellvarianten (Diakritika, palatales Twanksta-j, elaktr-) werden nicht
als Varianten-Zeilen pro Stamm/Endung aufgezählt, sondern als
generalisierende Faltungsregeln auf der Oberfläche komponiert.

Lauf im hfst-venv (Python 3.12, ``python-hfst``):
    PYTHONPATH=src python -m prussian.fst.hfst.lexd_build [--gold-only]
"""
