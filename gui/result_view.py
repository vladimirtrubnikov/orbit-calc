"""gui/result_view.py — правая панель с результатом."""
from __future__ import annotations

from PySide6.QtWidgets import QTextBrowser


class ResultView(QTextBrowser):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setOpenExternalLinks(False)
        self.setStyleSheet(
            "QTextBrowser { background:#0f0f18; color:#d4d4d4; "
            "border:none; padding:12px; }"
        )

    def show_html(self, html: str) -> None:
        self.setHtml(html)

    def show_message(self, text: str, color: str = "#888") -> None:
        self.setHtml(
            f'<body style="background:#0f0f18;color:{color};'
            f'font-family:Monospace;padding:12px;">{text}</body>'
        )
