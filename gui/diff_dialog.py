"""Сравнение двух расчётов A/B — diff по числовым полям."""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QTableWidget, QTableWidgetItem, QLabel, QPushButton,
)
from PySide6.QtGui import QFont, QColor


class DiffDialog(QDialog):
    def __init__(self, result_a, result_b, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Сравнение A/B — case {result_a.sid} vs {result_b.sid}")
        self.resize(720, 500)

        v = QVBoxLayout(self)
        title = QLabel(
            f"A: #{result_a.sid}  ·  B: #{result_b.sid}"
        )
        title.setStyleSheet("font-weight:bold; font-size:13px; color:#8b5cf6;")
        v.addWidget(title)

        out_a = result_a.output or {}
        out_b = result_b.output or {}
        keys = sorted(set(out_a.keys()) | set(out_b.keys()))

        table = QTableWidget()
        table.setRowCount(len(keys))
        table.setColumnCount(4)
        table.setHorizontalHeaderLabels(["Параметр", "A", "B", "Δ / %"])
        table.setStyleSheet(
            "QTableWidget { background:#0f0f18; color:#d4d4d4; "
            "gridline-color:#2a2a3a; font-family:Monospace; font-size:12px; }"
            "QHeaderView::section { background:#1a1a2e; color:#c084fc; padding:4px; }"
        )
        mono = QFont("Monospace", 10)

        for i, k in enumerate(keys):
            va = out_a.get(k)
            vb = out_b.get(k)
            a_s = f"{va:.6g}" if isinstance(va, (int, float)) else str(va or "—")
            b_s = f"{vb:.6g}" if isinstance(vb, (int, float)) else str(vb or "—")

            d_s = ""
            color = None
            if isinstance(va, (int, float)) and isinstance(vb, (int, float)):
                diff = vb - va
                if abs(va) > 1e-12:
                    pct = diff / va * 100
                    d_s = f"{diff:+.4g} ({pct:+.2f}%)"
                    color = "#4ade80" if abs(diff) < 1e-9 else "#fbbf24"
                else:
                    d_s = f"{diff:+.4g}"
                    color = "#fbbf24"

            for j, txt in enumerate([k, a_s, b_s, d_s]):
                item = QTableWidgetItem(txt)
                item.setFont(mono)
                if j == 3 and color:
                    item.setForeground(QColor(color))
                table.setItem(i, j, item)

        table.resizeColumnsToContents()
        v.addWidget(table)

        btn = QPushButton("Закрыть")
        btn.clicked.connect(self.accept)
        v.addWidget(btn)
