"""Sweep: x (любой вход) → y (любой выход) с графиком."""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QComboBox, QLineEdit,
    QPushButton, QLabel,
)
from PySide6.QtCore import Qt
from core import astrodynamics as aero
from gui.runner import run_case

try:
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
    from matplotlib.figure import Figure
    HAS_MPL = True
except ImportError:
    HAS_MPL = False


class SweepTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        v = QVBoxLayout(self)
        v.setContentsMargins(8, 8, 8, 8)

        title = QLabel("📊 Sweep: зависимость y(x)")
        title.setStyleSheet("font-size:15px; font-weight:bold; color:#c084fc;")
        v.addWidget(title)

        hint = QLabel(
            "Выберите случай, входной параметр для оси X и выходной для Y. "
            "Диапазон X разбивается на N точек, для каждой выполняется расчёт."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#888; font-size:11px;")
        v.addWidget(hint)

        # Case
        h1 = QHBoxLayout()
        h1.addWidget(QLabel("Случай:"))
        self.case_combo = QComboBox()
        for sid in sorted(aero.CASE_META.keys(), key=int):
            name = aero.CASE_META[sid]["name"]
            self.case_combo.addItem(f"#{sid}. {name}", sid)
        self.case_combo.currentIndexChanged.connect(self._on_case_changed)
        h1.addWidget(self.case_combo, 1)
        v.addLayout(h1)

        # X параметр
        h2 = QHBoxLayout()
        h2.addWidget(QLabel("X (вход):"))
        self.x_combo = QComboBox()
        h2.addWidget(self.x_combo, 1)
        h2.addWidget(QLabel("от:"))
        self.xmin = QLineEdit()
        self.xmin.setMaximumWidth(90)
        h2.addWidget(self.xmin)
        h2.addWidget(QLabel("до:"))
        self.xmax = QLineEdit()
        self.xmax.setMaximumWidth(90)
        h2.addWidget(self.xmax)
        h2.addWidget(QLabel("N:"))
        self.xn = QLineEdit("20")
        self.xn.setMaximumWidth(50)
        h2.addWidget(self.xn)
        v.addLayout(h2)

        # Y параметр
        h3 = QHBoxLayout()
        h3.addWidget(QLabel("Y (выход):"))
        self.y_combo = QComboBox()
        h3.addWidget(self.y_combo, 1)
        self.run_btn = QPushButton("▶ Построить график")
        self.run_btn.clicked.connect(self._run_sweep)
        self.run_btn.setStyleSheet(
            "QPushButton { background:#7c3aed; color:white; "
            "font-weight:bold; padding:8px 16px; border-radius:6px; }"
            "QPushButton:hover { background:#8b5cf6; }"
        )
        h3.addWidget(self.run_btn)
        v.addLayout(h3)

        # Plot
        if HAS_MPL:
            self.fig = Figure(figsize=(8, 5), tight_layout=True)
            self.canvas = FigureCanvasQTAgg(self.fig)
            v.addWidget(self.canvas, 1)
        else:
            v.addWidget(QLabel("matplotlib не установлен"))
            self.canvas = None

        self._status = QLabel("")
        self._status.setStyleSheet("color:#4ade80; font-size:11px;")
        v.addWidget(self._status)

        # Заполнение X при первом case
        self._on_case_changed()

    def _on_case_changed(self):
        sid = self.case_combo.currentData()
        meta = aero.CASE_META.get(sid, {})
        inputs = meta.get("inputs", [])

        self.x_combo.clear()
        for k in inputs:
            self.x_combo.addItem(k)

        # Y — все числовые выходные ключи; заполним после первого прогона
        self.y_combo.clear()
        # Заполняем defaults из case_meta_ext
        from gui.case_meta_ext import meta_for
        if inputs:
            k0 = inputs[0]
            _, _, _, mn, mx, default = meta_for(k0)
            default_min = default * 0.5 if default else 0
            default_max = default * 1.5 if default else 100
            self.xmin.setText(str(default_min))
            self.xmax.setText(str(default_max))
            self.y_combo.addItem("(выполните расчёт)")

    def _run_sweep(self):
        sid = self.case_combo.currentData()
        if not sid:
            return
        meta = aero.CASE_META.get(sid, {})
        inputs = meta.get("inputs", [])
        if not inputs:
            self._status.setText("Нет входных параметров")
            return

        x_key = self.x_combo.currentText()
        try:
            x_lo = float(self.xmin.text().replace(",", "."))
            x_hi = float(self.xmax.text().replace(",", "."))
            n = int(self.xn.text())
            if n < 2 or n > 200:
                raise ValueError
        except ValueError:
            self._status.setText("Ошибка ввода диапазона")
            return

        # Базовые значения — из формы или из case_meta_ext
        from gui.case_meta_ext import meta_for
        base = {}
        for k in inputs:
            if k == x_key:
                continue
            _, _, _, mn, mx, default = meta_for(k)
            base[k] = default

        # Первый прогон — узнать Y-ключи
        test_inputs = dict(base)
        test_inputs[x_key] = x_lo
        try:
            r = run_case(sid, test_inputs)
            if r.error:
                self._status.setText(f"Ошибка: {r.error}")
                return
            out_keys = [k for k, v in r.output.items()
                        if isinstance(v, (int, float))]
        except Exception as exc:
            self._status.setText(f"Ошибка: {exc}")
            return

        if not out_keys:
            self._status.setText("Нет числовых выходных параметров")
            return

        # Y-комбо: обновляем
        current_y = self.y_combo.currentText()
        self.y_combo.clear()
        for k in out_keys:
            self.y_combo.addItem(k)
        if current_y in out_keys:
            self.y_combo.setCurrentText(current_y)
        y_key = self.y_combo.currentText()

        # Прогон
        xs, ys = [], []
        errors = 0
        for i in range(n):
            xv = x_lo + (x_hi - x_lo) * i / (n - 1)
            inp = dict(base)
            inp[x_key] = xv
            try:
                r = run_case(sid, inp)
                if r.error or y_key not in r.output:
                    errors += 1
                    continue
                yv = r.output[y_key]
                if not isinstance(yv, (int, float)):
                    errors += 1
                    continue
                xs.append(xv)
                ys.append(yv)
            except Exception:
                errors += 1

        if not xs:
            self._status.setText("Не удалось получить данные")
            return

        self._draw(x_key, y_key, sid, xs, ys)
        self._status.setText(
            f"✓ {len(xs)} точек ({errors} ошибок). "
            f"Y: [{min(ys):.4g} .. {max(ys):.4g}]"
        )

    def _draw(self, x_key, y_key, sid, xs, ys):
        if not self.canvas:
            return
        self.fig.clear()
        ax = self.fig.add_subplot(111)
        ax.plot(xs, ys, "b-o", lw=1.5, ms=4)
        name = aero.CASE_META.get(sid, {}).get("name", "")
        ax.set_xlabel(x_key)
        ax.set_ylabel(y_key)
        ax.set_title(f"#{sid} {name}: {y_key}({x_key})")
        ax.grid(True, alpha=0.3)
        self.canvas.draw()
