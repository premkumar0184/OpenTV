"""
OpenTV Cross-Platform Terminal Controller.
PROJECT.md Feature F2.4:
ANSI VT100 control sequences for text inversion, bold, color, cursor control,
and clean fallback when executed in non-TTY or automated test environments.
"""
from __future__ import annotations

import shutil
import sys
from typing import Any, Optional, Tuple


class TerminalController:
    """Controls ANSI VT100 cursor movement, text styling, screen clearing, and dimension clamping."""

    def __init__(self, stdin: Optional[Any] = None, stdout: Optional[Any] = None) -> None:
        self.stdin = stdin or sys.stdin
        self.stdout = stdout or sys.stdout

    def get_size(self) -> Tuple[int, int]:
        """Returns clamped terminal dimensions as (columns, lines), minimum (80, 24)."""
        size = shutil.get_terminal_size(fallback=(80, 24))
        return (max(80, size.columns), max(24, size.lines))

    @property
    def is_tty(self) -> bool:
        """Determines whether both stdin and stdout are attached to an interactive terminal."""
        try:
            return bool(self.stdin.isatty() and self.stdout.isatty())
        except (AttributeError, ValueError):
            return False

    def clear_screen(self) -> str:
        """Returns terminal escape code to clear screen and move cursor to home position."""
        return "\033[2J\033[H" if self.is_tty else ""

    def invert(self, text: str) -> str:
        """Inverts foreground and background colors for highlighted selection."""
        return f"\033[7m{text}\033[0m" if self.is_tty else f"[{text}]"

    def bold(self, text: str) -> str:
        """Applies bold font weight."""
        return f"\033[1m{text}\033[0m" if self.is_tty else text

    def color(self, text: str, code: int) -> str:
        """Applies ANSI color code."""
        return f"\033[{code}m{text}\033[0m" if self.is_tty else text

    def hide_cursor(self) -> str:
        """Hides the terminal cursor."""
        return "\033[?25l" if self.is_tty else ""

    def show_cursor(self) -> str:
        """Restores cursor visibility."""
        return "\033[?25h" if self.is_tty else ""
