from __future__ import annotations

from PySide6.QtGui import QGuiApplication


def copy_text_to_clipboard(text: str) -> None:
    clipboard = QGuiApplication.clipboard()
    if clipboard is None:
        raise RuntimeError("Clipboard is not available.")
    clipboard.setText(text)
