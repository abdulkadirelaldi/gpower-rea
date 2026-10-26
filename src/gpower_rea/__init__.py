"""gpower-rea -- a clean-room reimplementation of G*Power's t-test family.

Built from ``SPEC.md`` only (see docs/CLEANROOM-PROTOCOL.md).  The package
contains no decompiler output and no part of the original binary.

Typical use::

    from gpower_rea import solve
    r = solve("ttest-indep-means", "n", alpha=0.05, power_target=0.95,
              effect_size=0.5, tails=2)
    r.sample_size["total"]   # -> 210
"""

from __future__ import annotations

from .engine import (
    ALLOCATION_RULES,
    DEFAULT_ALLOCATION_RULE,
    ENGINE_VERSION,
    SOLVE_MODES,
    SPEC_VERSION,
    NoSolutionError,
    PowerPoint,
    Result,
    power,
    power_curve,
    solve,
)
from .procedures import PROCEDURES, Procedure, Sample, ValidationError, resolve
from .report import apa_sentence, text_block

__version__ = ENGINE_VERSION

__all__ = [
    "__version__",
    "ALLOCATION_RULES",
    "DEFAULT_ALLOCATION_RULE",
    "ENGINE_VERSION",
    "SOLVE_MODES",
    "SPEC_VERSION",
    "NoSolutionError",
    "PROCEDURES",
    "PowerPoint",
    "Procedure",
    "Result",
    "Sample",
    "ValidationError",
    "apa_sentence",
    "power",
    "power_curve",
    "resolve",
    "solve",
    "text_block",
]
