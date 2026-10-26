"""A clean-room implementation of the G*Power 3.1 ``t tests`` family.

Written from SPEC.md (v1.0, updated to v1.3) and INTERFACE.md only.  Standard library only.

Public surface (INTERFACE.md)
-----------------------------
``TESTS``                   the six test keys, in order
``required_sample_size``    a priori
``achieved_power``          post hoc
``required_alpha``          criterion
``detectable_effect_size``  sensitivity
``compromise``              compromise

Also exported, because SPEC.md F-11 specifies behaviour that INTERFACE.md
gives no name for (see SPEC-GAPS-v1.2.md / SPEC-GAPS-v1.3.md):

``cohen_d_from_means``, ``pooled_sd_equal_n``, ``pooled_sd_unequal_n``,
``POOLING_OPTIONS``, ``ALLOCATION_RULES``.
"""

from __future__ import annotations

from ._designs import ALLOCATION_RULES, TESTS
from ._analyses import (
    achieved_power,
    compromise,
    detectable_effect_size,
    required_alpha,
    required_sample_size,
)
from .effectsize import (
    POOLING_OPTIONS,
    cohen_d_from_means,
    pooled_sd_equal_n,
    pooled_sd_unequal_n,
)

__version__ = "1.3.0"

__all__ = [
    "TESTS",
    "required_sample_size",
    "achieved_power",
    "required_alpha",
    "detectable_effect_size",
    "compromise",
    "ALLOCATION_RULES",
    "POOLING_OPTIONS",
    "cohen_d_from_means",
    "pooled_sd_equal_n",
    "pooled_sd_unequal_n",
]
