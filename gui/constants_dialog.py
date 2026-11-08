"""Справочник констант — QDialog с таблицей."""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QHBoxLayout, QLabel,
)
from PySide6.QtGui import QFont


def _rows():
    from core.base import MU_EARTH, R_EARTH, G0
    from core import astrodynamics as aero
    return [
        ("── Земля ──", "", ""),
        ("μ Земли", f"{MU_EARTH:.4f}", "км³/с²"),
        ("R Земли (экв.)", f"{R_EARTH:.3f}", "км"),
        ("g₀", f"{G0:.4f}", "м/с²"),
        ("J₂", f"{aero.J2:.6e}", "—"),
        ("R⊕ / T⊕", f"{aero.R_EARTH:.3f} / {aero.T_SIDEREAL:.2f}", "км / с"),
        ("── Солнечная система ──", "", ""),
        ("AU", f"{aero.AU_KM:.1f}", "км"),
        ("μ Солнца", f"{aero.M_SUN * 6.67430e-20:.4f}", "км³/с²"),
        ("M Солнца", f"{aero.M_SUN:.4e}", "кг"),
        ("M Земли", f"{aero.M_EARTH:.4e}", "кг"),
        ("M Луны", f"{aero.M_MOON:.4e}", "кг"),
        ("M Марса", f"{aero.M_MARS:.4e}", "кг"),
        ("a Луны", f"{aero.A_MOON_KM:.1f}", "км"),
        ("a Марса", f"{aero.A_MARS_AU:.6f}", "а.е."),
        ("T сидерич. сутки", f"{aero.T_SIDEREAL:.4f}", "с"),
        ("T троп. год", f"{aero.YEAR_S:.2f}", "с"),
        ("── Сценарии ──", "", ""),
        ("Пресет GSO H", "35786", "км"),
        ("Пресет ISS", "408 × 420", "км"),
        ("Пресет SSO-700", "700, i≈98.2°", "км / °"),
        ("─────────", "", ""),
        ("Формула vis-viva", "v = √(μ(2/r − 1/a))", ""),
        ("Формула Кеплера", "T = 2π√(a³/μ)", ""),
        ("Формула Циолковского", "Δv = Isp·g₀·ln(m₀/m₁)", ""),
    ]


class ConstantsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Справочник констант")
        self.resize(640, 600)

        v = QVBoxLayout(self)

        title = QLabel("Все константы, используемые в расчётах")
        title.setStyleSheet("font-weight:bold; font-size:13px; color:#8b5cf6;")
        v.addWidget(title)

        table = QTableWidget()
        rows = _rows()
        table.setRowCount(len(rows))
        table.setColumnCount(3)
        table.setHorizontalHeaderLabels(["Параметр", "Значение", "Единица"])
        table.setStyleSheet(
            "QTableWidget { background:#0f0f18; color:#d4d4d4; "
            "gridline-color:#2a2a3a; font-family:Monospace; font-size:12px; }"
            "QHeaderView::section { background:#1a1a2e; color:#c084fc; "
            "padding:4px; border:1px solid #2a2a3a; }"
        )
        mono = QFont("Monospace", 10)
        for i, (k, val, unit) in enumerate(rows):
            for j, txt in enumerate([k, val, unit]):
                item = QTableWidgetItem(txt)
                item.setFont(mono)
                if k.startswith("─") or k.startswith("═"):
                    item.setForeground(__import__("PySide6.QtGui", fromlist=["QColor"]).QColor("#888"))
                table.setItem(i, j, item)
        table.resizeColumnsToContents()
        v.addWidget(table)

        h = QHBoxLayout()
        btn_copy = QPushButton("📋 Копировать в буфер")
        btn_copy.clicked.connect(lambda: self._copy(table))
        h.addWidget(btn_copy)
        h.addStretch(1)
        btn_close = QPushButton("Закрыть")
        btn_close.clicked.connect(self.accept)
        h.addWidget(btn_close)
        v.addLayout(h)

    def _copy(self, table):
        lines = []
        for i in range(table.rowCount()):
            row = [table.item(i, j).text() if table.item(i, j) else ""
                   for j in range(3)]
            lines.append("  ".join(row))
        from PySide6.QtWidgets import QApplication
        QApplication.clipboard().setText("\n".join(lines))
