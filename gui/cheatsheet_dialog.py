"""Шпаргалка формул — все LaTeX из core.latex_formulas.LATEX."""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QTreeWidget, QTreeWidgetItem, QPushButton,
    QHBoxLayout, QLabel, QApplication,
)
from PySide6.QtGui import QFont
from PySide6.QtCore import Qt


class CheatsheetDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Шпаргалка формул (LaTeX)")
        self.resize(720, 640)

        v = QVBoxLayout(self)
        title = QLabel("Все формулы по всем случаям (LaTeX)")
        title.setStyleSheet("font-weight:bold; font-size:13px; color:#8b5cf6;")
        v.addWidget(title)

        try:
            from core.latex_formulas import LATEX
            from core.astrodynamics import CASE_META
        except Exception as exc:
            v.addWidget(QLabel(f"Ошибка загрузки: {exc}"))
            return

        tree = QTreeWidget()
        tree.setHeaderLabels(["Случай", "Формулы"])
        tree.setStyleSheet(
            "QTreeWidget { background:#0f0f18; color:#d4d4d4; "
            "font-family:Monospace; font-size:12px; }"
            "QTreeWidget::item { padding:2px; }"
        )
        tree.setFont(QFont("Monospace", 10))

        for sid in sorted(LATEX.keys(), key=lambda s: int(s) if s.isdigit() else 999):
            formulas = LATEX[sid]
            if not formulas:
                continue
            meta = CASE_META.get(sid, {})
            name = meta.get("name", "")
            top = QTreeWidgetItem([f"#{sid}. {name}", f"({len(formulas)})"])
            for f in formulas:
                child = QTreeWidgetItem(["", f])
                child.setForeground(1, __import__("PySide6.QtGui", fromlist=["QColor"]).QColor("#fbbf24"))
                top.addChild(child)
            tree.addTopLevelItem(top)
            top.setExpanded(False)

        v.addWidget(tree)

        h = QHBoxLayout()
        btn_copy = QPushButton("📋 Копировать всё (LaTeX)")
        btn_copy.clicked.connect(lambda: self._copy_all(LATEX))
        h.addWidget(btn_copy)
        h.addStretch(1)
        btn_close = QPushButton("Закрыть")
        btn_close.clicked.connect(self.accept)
        h.addWidget(btn_close)
        v.addLayout(h)

    def _copy_all(self, latex):
        lines = []
        for sid in sorted(latex.keys(), key=lambda s: int(s) if s.isdigit() else 999):
            for f in latex[sid]:
                lines.append(f"  {f}")
        QApplication.clipboard().setText("\n".join(lines))
