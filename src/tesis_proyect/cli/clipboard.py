"""Best-effort system clipboard adapter owned by the CLI boundary."""

from typing import Protocol

import pyperclip  # type: ignore[import-untyped]


class Clipboard(Protocol):
    def copy(self, text: str) -> None: ...


class SystemClipboard:
    def copy(self, text: str) -> None:
        pyperclip.copy(text)


system_clipboard: Clipboard = SystemClipboard()
