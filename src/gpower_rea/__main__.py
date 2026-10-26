"""Allow `python -m gpower_rea ...` as an alias for the `gpower` console script."""

from __future__ import annotations

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
