"""prussian_fst — importierbare API über die FST/CG3-Pipeline.

Nur als EDITABLE-Installation nutzbar (uv-Path-Dependency mit
editable=true): die Artefakt-Pfade (build/*.hfstol, build/cg3/*.bin,
cg3/*.cg3) werden relativ zum echten Quellbaum aufgelöst; ein reguläres
Wheel würde die Artefakte nicht mitbringen.  Bereitschaft prüfbar via
prussian_fst.check_artifacts().
"""

from .api import analyze, check_artifacts, conllu, tags, tokenize, validate  # noqa: F401
