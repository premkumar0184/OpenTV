"""
OpenTV Companion Package.
Zero-dependency cross-platform Android TV manager, debloat engine, and launcher configurator.
"""
from __future__ import annotations

__version__ = "1.0.0"

from opentv.cli import main

__all__ = [
    "__version__",
    "main",
]
