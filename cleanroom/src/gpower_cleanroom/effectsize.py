"""The effect-size drawer for two independent means (SPEC.md F-11).

Two pooled standard deviations are offered, and the equal-n one is a **root
mean square**, not the textbook pooled SD:

    n1 == n2 :  sigma = sqrt( (s1^2 + s2^2) / 2 )
    n1 != n2 :  sigma = sqrt( ((n1-1)s1^2 + (n2-1)s2^2) / (n1+n2-2) )

then ``d = (mu1 - mu2) / sigma``.  The two coincide only when ``s1 == s2`` or
``n1 == n2``; offering only one of them silently disagrees with half of all
users.
"""

from __future__ import annotations

import math
from typing import Optional

__all__ = [
    "POOLING_OPTIONS",
    "pooled_sd_equal_n",
    "pooled_sd_unequal_n",
    "cohen_d_from_means",
]

#: The two options the drawer exposes.
POOLING_OPTIONS: tuple[str, ...] = ("equal-n", "unequal-n")


def _check_sd(name: str, value: float) -> float:
    v = float(value)
    if not math.isfinite(v) or v < 0.0:
        raise ValueError("%s must be a finite non-negative number" % name)
    return v


def pooled_sd_equal_n(sd1: float, sd2: float) -> float:
    """``sqrt((sd1^2 + sd2^2) / 2)`` -- the root mean square of the two SDs.

    This is the ``n1 == n2`` option of F-11.  It is *not* the textbook pooled
    standard deviation.
    """
    s1 = _check_sd("sd1", sd1)
    s2 = _check_sd("sd2", sd2)
    return math.sqrt(0.5 * (s1 * s1 + s2 * s2))


def pooled_sd_unequal_n(sd1: float, sd2: float, n1: int, n2: int) -> float:
    """``sqrt(((n1-1)sd1^2 + (n2-1)sd2^2) / (n1+n2-2))`` -- the pooled-variance
    option of F-11."""
    s1 = _check_sd("sd1", sd1)
    s2 = _check_sd("sd2", sd2)
    if int(n1) != n1 or int(n2) != n2:
        raise ValueError("group sizes must be integers")
    a, b = int(n1), int(n2)
    if a < 1 or b < 1 or a + b - 2 <= 0:
        raise ValueError("n1 + n2 - 2 must be > 0")
    num = (a - 1) * s1 * s1 + (b - 1) * s2 * s2
    return math.sqrt(num / float(a + b - 2))


def cohen_d_from_means(mu1: float, mu2: float, sd1: float, sd2: float, *,
                       n1: Optional[int] = None, n2: Optional[int] = None,
                       option: Optional[str] = None) -> float:
    """``d = (mu1 - mu2) / sigma`` with ``sigma`` from the selected option.

    ``option`` is ``"equal-n"`` (RMS) or ``"unequal-n"`` (pooled variance).
    When it is omitted the option is inferred: ``"unequal-n"`` if group sizes
    are supplied and differ, otherwise ``"equal-n"``.
    """
    if option is None:
        if n1 is not None and n2 is not None and int(n1) != int(n2):
            option = "unequal-n"
        else:
            option = "equal-n"
    if option not in POOLING_OPTIONS:
        raise ValueError("option must be one of %s" % (", ".join(POOLING_OPTIONS),))
    if option == "equal-n":
        sigma = pooled_sd_equal_n(sd1, sd2)
    else:
        if n1 is None or n2 is None:
            raise ValueError("the unequal-n option requires n1 and n2")
        sigma = pooled_sd_unequal_n(sd1, sd2, n1, n2)
    if sigma <= 0.0:
        raise ValueError("the pooled standard deviation must be > 0")
    return (float(mu1) - float(mu2)) / sigma
