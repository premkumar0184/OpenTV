"""
OpenTV Companion Main Entry Point.
PROJECT.md Feature F2.1 & Architecture:
Allows standalone execution via `python3 -m opentv` or direct execution of `__main__.py`.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Ensure repository root and package directory are in sys.path when executed directly
_CURRENT_DIR = Path(__file__).resolve().parent
_COMPANION_ROOT = _CURRENT_DIR.parent
if str(_COMPANION_ROOT) not in sys.path:
    sys.path.insert(0, str(_COMPANION_ROOT))

from opentv.cli import EXIT_ERROR, main

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.", file=sys.stderr)
        sys.exit(130)
    except Exception as exc:
        print(f"Fatal error: {exc}", file=sys.stderr)
        sys.exit(EXIT_ERROR)
