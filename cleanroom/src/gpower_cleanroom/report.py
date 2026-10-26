"""Display rounding (SPEC.md F-12).

F-12 is explicit that rounding is *for display only*: the search itself uses
unrounded values, so the result dictionaries returned by the analysis
functions carry full-precision doubles.  Rounding happens here and nowhere
else.

    delta, critical t and power  -> 7 decimals
    nu                           -> integer when the design is integral
"""

from __future__ import annotations

__all__ = ["DISPLAY_DECIMALS", "round_for_display", "format_result"]

#: Number of decimals SPEC.md F-12 reports delta, critical t and power to.
DISPLAY_DECIMALS = 7

_ROUNDED_KEYS = ("ncp", "critical_t", "power", "target_power", "beta")


def round_for_display(result: dict) -> dict:
    """A copy of ``result`` with F-12's display rounding applied."""
    out = dict(result)
    for key in _ROUNDED_KEYS:
        if key in out and out[key] is not None:
            out[key] = round(float(out[key]), DISPLAY_DECIMALS)
    if "df" in out:
        nu = float(out["df"])
        out["df"] = int(nu) if nu == int(nu) else nu
    return out


def format_result(result: dict) -> str:
    """A short human-readable rendering using F-12's display precision."""
    r = round_for_display(result)
    lines = ["test            = %s" % r.get("test", "?")]
    if r.get("total"):
        if r.get("n2"):
            lines.append("n1, n2          = %d, %d" % (r["n1"], r["n2"]))
        lines.append("total N         = %d" % r["total"])
    lines.append("df (nu)         = %s" % (r["df"],))
    lines.append("noncentrality   = %.*f" % (DISPLAY_DECIMALS, r["ncp"]))
    lines.append("critical t      = %.*f" % (DISPLAY_DECIMALS, r["critical_t"]))
    lines.append("alpha           = %.10g" % r["alpha"])
    if "target_power" in r:
        lines.append("target power    = %.*f" % (DISPLAY_DECIMALS, r["target_power"]))
    lines.append("power           = %.*f" % (DISPLAY_DECIMALS, r["power"]))
    if "beta" in r:
        lines.append("beta            = %.*f" % (DISPLAY_DECIMALS, r["beta"]))
    lines.append("effect size %-3s = %.10g" % (r.get("effect_size_name", "es"),
                                               r["effect_size"]))
    for w in r.get("warnings", ()):
        lines.append("warning         = %s" % w)
    return "\n".join(lines)
