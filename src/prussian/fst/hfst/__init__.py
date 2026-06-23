"""HFST-nativer Analysatorzweig (paralleler Track zu pyfoma).

Dieselbe Datenquelle (data/gold + Wortliste) und dieselbe markierte
Morphotaktik wie der pyfoma-Build, aber durchgängig in HFST komponiert:

    lexc-Lexikon  ∘  Phonologie-/Akzentregeln          = analyser
                  ∘  spellrelax (generalisierende Regeln) = lenient

Im Unterschied zum pyfoma-Zweig werden die Quellvarianten (Twanksta-j,
elaktr-, -as/-us) **nicht** als V-Zeilen pro Stamm/Endung aufgezählt,
sondern als generalisierende optionale Replace-Regeln (`(->)`) auf der
Oberfläche komponiert (echte Komposition statt Aufzählung).

Lauf im hfst-venv (Python 3.12, ``python-hfst``):
    PYTHONPATH=src python -m prussian.fst.hfst.build [--gold-only]
"""
