"""gui/case_sidebar.py — дерево 54 случаев + поиск."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLineEdit, QTreeWidget, QTreeWidgetItem,
)
from core import astrodynamics as aero


GROUPS = [
    ("Обратная задача (1–16)",    list(range(1, 17))),
    ("Расширение (17–30)",        list(range(17, 31))),
    ("Прямые расчёты (31–37)",    list(range(31, 38))),
    ("Астрономия (38–45)",        list(range(38, 46))),
    ("Вектор состояния (46)",     [46]),
    ("v3: J2 / бюджет (47–53)",   list(range(47, 54))),
    ("v6: Ламберт N витков (54)", [54]),
]


class CaseSidebar(QWidget):
    case_selected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(260)
        self.setMaximumWidth(360)

        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(6)

        self.search = QLineEdit()
        self.search.setPlaceholderText("🔍 Поиск (a и e, ламберт, J2, ...)")
        self.search.setStyleSheet(
            "QLineEdit { background:#1a1a2e; color:#e0e0e0; "
            "border:1px solid #333; border-radius:6px; padding:6px 10px; }"
        )
        self.search.textChanged.connect(self._filter)
        v.addWidget(self.search)

        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setStyleSheet(
            "QTreeWidget { background:#12121c; color:#d4d4d4; "
            "border:none; font-size:12px; }"
            "QTreeWidget::item { padding:4px 2px; }"
            "QTreeWidget::item:selected { background:#8b5cf6; color:white; }"
            "QTreeWidget::item:hover { background:#2a2a3a; }"
        )
        self.tree.itemClicked.connect(self._on_click)
        v.addWidget(self.tree, 1)

        self._items: list[tuple[QTreeWidgetItem, str]] = []
        self._build_tree()

    def _build_tree(self) -> None:
        self.tree.clear()
        self._items.clear()
        for group_name, sids in GROUPS:
            group_item = QTreeWidgetItem([group_name])
            group_item.setFlags(Qt.ItemIsEnabled)
            group_item.setForeground(0, QColor("#888"))
            group_item.setExpanded(True)
            self.tree.addTopLevelItem(group_item)

            for sid in sids:
                sid_s = str(sid)
                name = aero.CASE_META.get(sid_s, {}).get("name", "?")
                item = QTreeWidgetItem([f"{sid:>2d}. {name}"])
                item.setData(0, Qt.UserRole, sid_s)
                group_item.addChild(item)
                searchable = f"{sid} {name} {group_name}".lower()
                self._items.append((item, searchable))

    def _filter(self, text: str) -> None:
        needle = text.strip().lower()
        for item, searchable in self._items:
            item.setHidden(bool(needle) and needle not in searchable)

    def _on_click(self, item: QTreeWidgetItem, _col: int) -> None:
        sid = item.data(0, Qt.UserRole)
        if sid:
            self.case_selected.emit(str(sid))

    def select_case(self, sid: str) -> None:
        for item, _ in self._items:
            if item.data(0, Qt.UserRole) == sid:
                self.tree.setCurrentItem(item)
                item.setSelected(True)
                self.tree.scrollToItem(item)
                return
