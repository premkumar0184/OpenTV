"""
OpenTV Fallback Line-Oriented Prompt Engine.
PROJECT.md Feature F2.4:
Provides text-based prompts for non-TTY environments (CI runners, redirected streams, dumb terminals).
"""
from __future__ import annotations

from typing import Callable, List, Optional


class FallbackLineEngine:
    """Line-oriented prompt engine for CI, redirected stdin, and dumb terminals."""

    def __init__(
        self,
        input_fn: Optional[Callable[[str], str]] = None,
        output_fn: Optional[Callable[[str], None]] = None,
    ) -> None:
        self.input_fn = input_fn or input
        self.output_fn = output_fn or print

    def prompt_choice(self, title: str, options: List[str], default_index: int = 0) -> int:
        """Presents a numbered single-choice menu and returns selected zero-based index."""
        self.output_fn(f"\n--- {title} ---")
        for i, opt in enumerate(options):
            marker = "*" if i == default_index else " "
            self.output_fn(f"[{i + 1}] {opt} {marker}")

        while True:
            resp = self.input_fn(f"Select option [1-{len(options)}] (default: {default_index + 1}): ").strip()
            if not resp:
                return default_index
            if resp.isdigit():
                idx = int(resp) - 1
                if 0 <= idx < len(options):
                    return idx
            self.output_fn("Invalid choice. Please enter a number from the list.")

    def prompt_multiselect(
        self, title: str, options: List[str], preselected: Optional[List[int]] = None
    ) -> List[int]:
        """Presents a toggleable multi-select list and returns list of selected indices."""
        self.output_fn(f"\n--- {title} ---")
        current_selection = set(preselected or [])
        for i, opt in enumerate(options):
            mark = "[X]" if i in current_selection else "[ ]"
            self.output_fn(f"{mark} {i + 1}. {opt}")

        resp = self.input_fn("Enter comma-separated numbers to toggle, or press Enter to confirm: ").strip()
        if not resp:
            return sorted(list(current_selection))

        for part in resp.split(","):
            part = part.strip()
            if part.isdigit():
                idx = int(part) - 1
                if 0 <= idx < len(options):
                    if idx in current_selection:
                        current_selection.remove(idx)
                    else:
                        current_selection.add(idx)
        return sorted(list(current_selection))

    def prompt_text(self, title: str, default: str = "") -> str:
        """Prompts for free-form text input with default value fallback."""
        def_str = f" [{default}]" if default else ""
        resp = self.input_fn(f"{title}{def_str}: ").strip()
        return resp if resp else default
