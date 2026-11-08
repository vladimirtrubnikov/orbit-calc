"""gui/app.py — главное окно orbit-calc GUI."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QToolBar, QLabel, QStatusBar, QMessageBox,
    QFileDialog, QTabWidget, QPushButton, QSizePolicy,
)

from core import astrodynamics as aero
from .case_sidebar import CaseSidebar
from .case_meta_ext import PRESETS
from .history import HistoryPanel
from .html_render import render as render_html
from .input_form import InputForm
from .result_view import ResultView
from .runner import RunResult, run_case
from .theme import apply_theme


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("orbit-calc · GUI")
        self.resize(1400, 880)

        self._current_sid: str | None = None
        self._current_result: RunResult | None = None
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(250)
        self._debounce.timeout.connect(self._run_live)

        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        splitter = QSplitter(Qt.Horizontal)
        root.addWidget(splitter, 1)

        self.sidebar = CaseSidebar()
        self.sidebar.case_selected.connect(self.on_case_selected)
        splitter.addWidget(self.sidebar)

        center = QWidget()
        cv = QVBoxLayout(center)
        cv.setContentsMargins(0, 0, 0, 0)
        cv.setSpacing(6)

        self.form = InputForm()
        self.form.changed.connect(self._on_form_changed)
        self.form.submit.connect(self._on_form_changed)
        cv.addWidget(self.form)

        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(
            "QTabWidget::pane { border:none; }"
            "QTabBar::tab { background:#1a1a2e; color:#888; "
            "padding:6px 16px; border-top-left-radius:6px; "
            "border-top-right-radius:6px; margin-right:2px; }"
            "QTabBar::tab:selected { background:#8b5cf6; color:white; }"
        )
        self.result_view = ResultView()
        self.tabs.addTab(self.result_view, "Результат")
        self.json_view = ResultView()
        self.tabs.addTab(self.json_view, "JSON")
        self.latex_view = ResultView()
        self.tabs.addTab(self.latex_view, "LaTeX")
        cv.addWidget(self.tabs, 1)
        splitter.addWidget(center)

        self.history = HistoryPanel()
        self.history.entry_selected.connect(self._on_history_click)
        splitter.addWidget(self.history)

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)
        splitter.setSizes([280, 900, 280])

        self._build_toolbar()

        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.status.showMessage("Готов. Выберите пункт слева или нажмите на пресет.")

        self.on_case_selected("1")

    def _build_toolbar(self) -> None:
        tb = QToolBar("Presets")
        tb.setMovable(False)
        self.addToolBar(tb)

        label = QLabel("  Пресеты:  ")
        label.setStyleSheet("color:#888;font-size:11px;")
        tb.addWidget(label)

        for name, tip, sid, vals in PRESETS:
            btn = QPushButton(name)
            btn.setToolTip(tip)
            btn.setStyleSheet(
                "QPushButton { background:#1a1a2e; color:#d4d4d4; "
                "border:1px solid #333; border-radius:4px; "
                "padding:4px 10px; font-size:11px; }"
                "QPushButton:hover { border-color:#8b5cf6; }"
            )
            btn.clicked.connect(
                lambda _=False, s=sid, v=vals: self._apply_preset(s, v)
            )
            tb.addWidget(btn)

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        tb.addWidget(spacer)

        export_btn = QPushButton("📋 Экспорт")
        export_btn.setObjectName("primary")
        export_btn.clicked.connect(self._export_menu)
        tb.addWidget(export_btn)

    def _apply_preset(self, sid: str, values: list[float]) -> None:
        self.on_case_selected(sid)
        meta = aero.CASE_META[sid]
        self.form.set_values(dict(zip(meta["inputs"], values)))
        self._run_live()

    def on_case_selected(self, sid: str) -> None:
        self._current_sid = sid
        self.form.load_case(sid)
        meta = aero.CASE_META[sid]
        self.status.showMessage(f"Случай #{sid}: {meta['name']}")
        self._run_live()

    def _on_form_changed(self) -> None:
        self._debounce.start()

    def _on_history_click(self, sid: str, inputs: dict) -> None:
        self.on_case_selected(sid)
        self.form.set_values(inputs)
        self._run_live()

    def _run_live(self) -> None:
        if self._current_sid is None:
            return
        values = self.form.values()
        if values is None:
            self.status.showMessage("⚠ Проверьте ввод — есть некорректные поля")
            return

        res = run_case(self._current_sid, values)
        self._current_result = res

        self.result_view.show_html(render_html(res.stdout, res.output, res.error))
        self.json_view.show_html(self._json_html(res))
        self.latex_view.show_html(self._latex_html(res))

        if not res.error:
            summary = self._summary(res)
            self.history.push(self._current_sid, values, summary)
            self.status.showMessage(f"✓ {summary}")
        else:
            self.status.showMessage(f"✗ {res.error}")

    def _json_html(self, res: RunResult) -> str:
        payload = {"case": res.sid, "inputs": res.inputs,
                   "output": res.output, "error": res.error}
        pretty = json.dumps(payload, indent=2, ensure_ascii=False)
        return (
            '<body style="background:#0f0f18;color:#d4d4d4;'
            'font-family:Monospace;padding:12px;font-size:12px;">'
            f'<pre style="margin:0;">{pretty}</pre></body>'
        )

    def _latex_html(self, res: RunResult) -> str:
        if not res.latex:
            return ('<body style="color:#888;padding:12px;">'
                    'Для этого случая LaTeX не определён.</body>')
        rows = "".join(
            f'<div style="padding:4px 0;border-bottom:1px solid #1a1a2e;">'
            f'<code style="color:#fbbf24;">{f}</code></div>'
            for f in res.latex
        )
        return ('<body style="background:#0f0f18;color:#d4d4d4;'
                'font-family:Monospace;padding:12px;font-size:12px;">'
                f'{rows}</body>')

    def _summary(self, res: RunResult) -> str:
        o = res.output
        if "a" in o and "e" in o:
            return f"a={o['a']:.1f} км, e={o['e']:.4f}"
        if "dv_total_mps" in o:
            return f"ΣΔv = {o['dv_total_mps']:.1f} м/с"
        if "n_found" in o:
            return f"{o['n_found']} решений"
        if "dv_mps" in o:
            return f"Δv = {o['dv_mps']:.1f} м/с"
        return f"выполнено ({len(o)} полей)"

    def _export_menu(self) -> None:
        if not self._current_result:
            QMessageBox.information(self, "Экспорт", "Сначала выполните расчёт")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Сохранить результат",
            str(Path.home() / f"orbit_case_{self._current_sid}.json"),
            "JSON (*.json);;Markdown (*.md);;LaTeX (*.tex);;Все (*)",
        )
        if not path:
            return
        ext = Path(path).suffix.lower()
        try:
            if ext == ".md":
                self._export_md(path, self._current_result)
            elif ext == ".tex":
                self._export_tex(path, self._current_result)
            else:
                self._export_json(path, self._current_result)
            self.status.showMessage(f"✓ Сохранено: {path}")
        except Exception as exc:
            QMessageBox.critical(self, "Экспорт", f"Ошибка: {exc}")

    def _export_json(self, path: str, res: RunResult) -> None:
        payload = {"case": res.sid, "inputs": res.inputs,
                   "output": res.output, "latex": res.latex}
        Path(path).write_text(
            json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    def _export_md(self, path: str, res: RunResult) -> None:
        meta = aero.CASE_META.get(res.sid, {})
        lines = [f"# Случай {res.sid}: {meta.get('name', '?')}", "", "## Входные данные", ""]
        for k, v in res.inputs.items():
            lines.append(f"- **{k}** = {v}")
        lines += ["", "## Шаги", "", "```", res.stdout, "```", "", "## JSON", "", "```json"]
        lines.append(json.dumps(res.output, indent=2, ensure_ascii=False))
        lines.append("```")
        Path(path).write_text("\n".join(lines), encoding="utf-8")

    def _export_tex(self, path: str, res: RunResult) -> None:
        body = "\n".join(f"\\[ {f} \\]" for f in res.latex)
        Path(path).write_text(body, encoding="utf-8")

    def closeEvent(self, event) -> None:
        self._debounce.stop()
        super().closeEvent(event)


def main() -> int:
    if "--version" in sys.argv:
        print("orbit-calc-gui 0.8.0")
        return 0
    app = QApplication(sys.argv)
    apply_theme(app)
    w = MainWindow()
    w.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
