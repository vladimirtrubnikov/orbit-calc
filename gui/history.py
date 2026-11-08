"""gui/history.py — панель истории расчётов."""
from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QListWidget, QListWidgetItem, QPushButton,
)
from core import astrodynamics as aero


@dataclass
class HistoryEntry:
    sid: str
    inputs: dict[str, float]
    summary: str


class HistoryPanel(QWidget):
    entry_selected = Signal(str, dict)
    cleared = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMaximumWidth(300)
        self._entries: list[HistoryEntry] = []

        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(6)

        title = QLabel("📜 История")
        title.setStyleSheet("color:#8b5cf6; font-weight:bold; font-size:13px;")
        v.addWidget(title)

        self.list = QListWidget()
        self.list.setStyleSheet(
            "QListWidget { background:#12121c; color:#d4d4d4; "
            "border:none; font-size:11px; }"
            "QListWidget::item { padding:6px 8px; }"
            "QListWidget::item:selected { background:#8b5cf6; }"
        )
        self.list.itemClicked.connect(self._on_click)
        v.addWidget(self.list, 1)

        clear_btn = QPushButton("Очистить")
        clear_btn.setStyleSheet(
            "QPushButton { background:#2a2a3a; color:#d4d4d4; "
            "border:1px solid #444; border-radius:4px; padding:4px 10px; }"
            "QPushButton:hover { background:#3a3a4a; }"
        )
        clear_btn.clicked.connect(self._clear)
        v.addWidget(clear_btn)

    def push(self, sid: str, inputs: dict[str, float], summary: str = "") -> None:
        name = aero.CASE_META.get(sid, {}).get("name", "?")
        entry = HistoryEntry(sid=sid, inputs=dict(inputs), summary=summary)
        self._entries.insert(0, entry)
        if len(self._entries) > 20:
            self._entries.pop()

        label = f"#{sid} {name}"
        if summary:
            label += f"\n   {summary}"
        item = QListWidgetItem(label)
        item.setData(Qt.UserRole, (sid, dict(inputs)))
        self.list.insertItem(0, item)
        if self.list.count() > 20:
            self.list.takeItem(self.list.count() - 1)

    def _on_click(self, item: QListWidgetItem) -> None:
        sid, inputs = item.data(Qt.UserRole)
        self.entry_selected.emit(sid, inputs)

    def _clear(self) -> None:
        self._entries.clear()
        self.list.clear()
        self.cleared.emit()
