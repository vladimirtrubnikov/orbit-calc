#!/usr/bin/env python3
"""patch_v7_gui.py — создаёт полноценный GUI orbit-calc (PySide6).

Создаёт:
  gui/__init__.py
  gui/__main__.py
  gui/app.py
  gui/case_sidebar.py
  gui/case_meta_ext.py
  gui/html_render.py
  gui/history.py
  gui/input_form.py
  gui/result_view.py
  gui/runner.py
  gui/theme.py
  gui/launch_gui.sh
  gui/launch_gui.bat
  build/orbit-calc-gui.spec
  tests/test_gui_smoke.py

Обновляет:
  pyproject.toml — [project.optional-dependencies] gui = ["PySide6>=6.5"]

Идемпотентен. Резервные копии: *.v7.bak
"""

from __future__ import annotations

import os
import shutil
import stat
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


# ═══════════════════════════════════════════════════════════════════════════
#  FILES — каждый записывается как raw-строка r'''...'''
# ═══════════════════════════════════════════════════════════════════════════

FILES: dict[str, str] = {

"gui/__init__.py": r'''"""gui — GUI и визуализация orbit-calc."""

try:
    import matplotlib  # noqa: F401
    HAS_PLOT = True
except ImportError:
    HAS_PLOT = False

__all__ = ["HAS_PLOT"]
''',

"gui/__main__.py": r'''"""gui/__main__.py — запуск через python -m gui."""
import sys
from .app import main

if __name__ == "__main__":
    sys.exit(main())
''',

"gui/runner.py": r'''"""gui/runner.py — вызов _solve_* из CLI с перехватом stdout."""
from __future__ import annotations

import io
from contextlib import redirect_stdout
from dataclasses import dataclass, field
from typing import Any

from cli import calculator as calc
from core import astrodynamics as aero


@dataclass
class RunResult:
    sid: str
    inputs: dict[str, float]
    stdout: str = ""
    output: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    latex: list[str] = field(default_factory=list)


def run_case(sid: str, inputs: dict[str, float]) -> RunResult:
    """Запускает пункт sid с параметрами inputs, перехватывает stdout."""
    res = RunResult(sid=sid, inputs=dict(inputs))

    try:
        res.latex = calc._latex_get(sid)
    except Exception:
        res.latex = []

    meta = aero.CASE_META.get(sid)
    if meta is None:
        res.error = f"Неизвестный случай {sid}"
        return res

    order = meta["inputs"]
    try:
        vals = [float(inputs[k]) for k in order]
    except KeyError as exc:
        res.error = f"Не задан параметр {exc}"
        return res
    except (TypeError, ValueError) as exc:
        res.error = f"Некорректное значение: {exc}"
        return res

    old_ask = getattr(calc, "_ask_plot", None)
    calc._ask_plot = lambda: False

    buf = io.StringIO()
    try:
        with redirect_stdout(buf):
            with calc._input_queue(vals):
                calc._dispatch_solve(sid)
    except SystemExit:
        pass
    except Exception as exc:
        res.error = f"{type(exc).__name__}: {exc}"
    finally:
        if old_ask is not None:
            calc._ask_plot = old_ask

    res.stdout = buf.getvalue()
    r = getattr(calc, "_RESULT", {})
    res.output = dict(r.get("output") or {})
    if res.error is None and r.get("error"):
        res.error = r["error"]
    return res
''',

"gui/case_meta_ext.py": r'''"""gui/case_meta_ext.py — метаданные полей ввода + пресеты."""
from __future__ import annotations

# key → (label, unit, type, min, max, default)
INPUT_META: dict[str, tuple] = {
    "a":       ("Большая полуось a", "км", "float", 1, None, 7000.0),
    "e":       ("Эксцентриситет e",  "", "float", 0, 0.999, 0.0),
    "H":       ("Высота H",          "км", "float", 0, None, 400.0),
    "H_p":     ("Высота перигея H_p", "км", "float", 0, None, 200.0),
    "H_a":     ("Высота апогея H_a",  "км", "float", 0, None, 420.0),
    "Ap":      ("Апогей Ap",         "км", "float", 0, None, 420.0),
    "Pe":      ("Перигей Pe",        "км", "float", 0, None, 408.0),
    "r_p":     ("Радиус перигея",    "км", "float", 6378.1, None, 6578.0),
    "r_a":     ("Радиус апогея",     "км", "float", 6378.1, None, 6798.0),
    "p":       ("Фокальный параметр", "км", "float", 1, None, 6800.0),
    "h":       ("Момент импульса h", "км²/с", "float", 0.001, None, 52000.0),
    "eps":     ("Уд. энергия ε",     "км²/с²", "float", None, -0.001, -28.5),
    "T":       ("Период T",          "с",   "float", 0.001, None, 5400.0),
    "v":       ("Скорость v",        "км/с", "float", 0.001, None, 7.8),
    "v_p":     ("Скорость v_p",      "км/с", "float", 0.001, None, 7.9),
    "v_a":     ("Скорость v_a",      "км/с", "float", 0.001, None, 7.6),
    "v_inf":   ("Скорость v_∞",      "км/с", "float", 0.001, None, 3.0),
    "gamma":   ("Угол траектории γ", "°",   "float", -90, 90, 0.0),
    "gamma_deg": ("Угол γ",          "°",   "float", 0, 180, 10.0),
    "i":       ("Наклонение i",      "°",   "float", 0, 180, 51.6),
    "di":      ("Δi",                "°",   "float", 0, 180, 28.5),
    "dnu_deg": ("Δν",                "°",   "float", 0.001, 359.999, 180.0),
    "nu_deg":  ("Истинная аномалия ν", "°", "float", 0, 360, 0.0),
    "nu1":     ("ν1 (начало)",       "°",   "float", 0, 360, 0.0),
    "nu2":     ("ν2 (конец)",        "°",   "float", 0, 360, 180.0),
    "dphi":    ("Фазовый угол Δφ",   "°",   "float", -360, 360, 30.0),
    "el":      ("Угол места el",     "°",   "float", -90, 90, 30.0),
    "rho":     ("Наклонная дальность ρ", "км", "float", 0.001, None, 1000.0),
    "rho_dot": ("Радиальная скорость ρ̇", "км/с", "float", None, None, 0.5),
    "t":       ("Время t",           "с",   "float", 0, None, 1000.0),
    "dt":      ("Время перелёта Δt", "с",   "float", 0.001, None, 18929.0),
    "T1":      ("Период T1",         "с",   "float", 0.001, None, 5400.0),
    "T2":      ("Период T2",         "с",   "float", 0.001, None, 86164.0),
    "dv":      ("Δv",                "м/с", "float", 0, None, 1500.0),
    "m0":      ("Масса m0",          "кг",  "float", 0.001, None, 1000.0),
    "m_fuel":  ("Топливо",           "кг",  "float", 0, None, 400.0),
    "m_dry":   ("Сухая масса",       "кг",  "float", 0, None, 100.0),
    "isp":     ("Уд. импульс Isp",   "с",   "float", 0.001, None, 320.0),
    "epsilon": ("Доля конструкции ε", "",  "float", 0.001, 0.999, 0.08),
    "N":       ("Число витков N",    "",    "int", 1, 20, 3),
    "n_max":   ("N_max",             "",    "int", 0, 10, 2),
    "r":       ("Радиус r",          "км",  "float", 6378.1, None, 6785.0),
    "H1":      ("Высота орбиты 1",   "км",  "float", 0, None, 200.0),
    "H2":      ("Высота орбиты 2",   "км",  "float", 0, None, 35786.0),
    "H_bi":    ("Промежуточная высота", "км", "float", 0, None, 200000.0),
    "H_rb":    ("Промежуточная высота", "км", "float", 0, None, 200000.0),
}


PRESETS: list[tuple[str, str, str, list]] = [
    ("GSO",        "Геостационарная H_p = H_a = 35786",  "2", [35786.0, 35786.0]),
    ("ISS",        "МКС H_p = 408, H_a = 420",           "2", [408.0, 420.0]),
    ("LEO-550",    "Starlink LEO 550",                   "2", [550.0, 550.0]),
    ("MEO-20200",  "GPS MEO 20200",                      "2", [20200.0, 20200.0]),
    ("SSO-700",    "Солнечно-синхронная 700",            "29", [700.0]),
    ("Molniya",    "Молния 500×40000",                   "2", [500.0, 40000.0]),
]


def meta_for(key: str) -> tuple:
    return INPUT_META.get(key, (key, "", "float", None, None, 0.0))
''',

"gui/html_render.py": r'''"""gui/html_render.py — stdout _solve_* → цветной HTML."""
from __future__ import annotations

import html as _html
import json
import re
from typing import Any


COLOR = {
    "h2":    "#c084fc",
    "step":  "#60a5fa",
    "final": "#4ade80",
    "err":   "#ef4444",
    "vec":   "#fbbf24",
    "info":  "#94a3b8",
    "num":   "#fbbf24",
}


def _esc(s: str) -> str:
    return _html.escape(s)


def render(stdout: str, output: dict[str, Any], error: str | None = None) -> str:
    parts: list[str] = []
    if error:
        parts.append(f'<div class="err"><b>Ошибка:</b> {_esc(error)}</div>')

    in_final = False
    in_table = False

    for raw in stdout.splitlines():
        line = raw.rstrip()
        if not line.strip():
            if in_table:
                parts.append("</table>")
                in_table = False
            in_final = False
            parts.append("<div style='height:4px'></div>")
            continue

        m = re.match(r"\s*(СЛУЧАЙ \d+:[^─]+)", line)
        if m:
            parts.append(
                f'<h2 style="color:{COLOR["h2"]};border-bottom:1px solid #333;'
                f'padding:6px 0;">{_esc(m.group(1).strip())}</h2>'
            )
            continue

        if line.strip().startswith("──"):
            title = line.strip().strip("─ ").strip()
            if title:
                color = COLOR["final"] if "ИТОГ" in title.upper() else COLOR["h2"]
                parts.append(f'<h3 style="color:{color};margin-top:14px;">'
                             f'{_esc(title)}</h3>')
            if "ИТОГ" in title.upper():
                in_final = True
            continue

        m = re.match(r"\s*Шаг (\d+):\s*(.*)", line)
        if m:
            n, body = m.groups()
            parts.append(
                f'<div style="color:{COLOR["step"]};padding:2px 0 2px 8px;'
                f'font-family:monospace;"><b>Шаг {n}:</b> '
                f'<span style="color:#d4d4d4">{_esc(body)}</span></div>'
            )
            continue

        m = re.match(r"\s*(N=\d+,\s*\w+:)", line)
        if m:
            parts.append(f'<div style="color:{COLOR["vec"]};margin-top:6px;">'
                         f'<b>{_esc(m.group(1))}</b></div>')
            continue

        if re.match(r"\s*v[12]\s*=", line):
            parts.append(f'<div style="color:#d4d4d4;font-family:monospace;'
                         f'padding-left:16px;">{_esc(line.strip())}</div>')
            continue

        if "Найдено решений" in line:
            parts.append(f'<div style="color:{COLOR["info"]};font-style:italic;">'
                         f'{_esc(line.strip())}</div>')
            continue

        m = re.match(r"\s*([^:]+):\s+([-+]?[\d.,]+(?:\s+\S+)?)\s*$", line)
        if m and in_final:
            k, v = m.groups()
            if not in_table:
                parts.append('<table style="border-collapse:collapse;margin:6px 0;">')
                in_table = True
            parts.append(
                f'<tr><td style="padding:2px 20px 2px 0;color:#94a3b8;">'
                f'{_esc(k.strip())}</td>'
                f'<td style="padding:2px 0;color:{COLOR["num"]};'
                f'font-family:monospace;font-weight:bold;">{_esc(v.strip())}</td></tr>'
            )
            continue

        parts.append(f'<div style="color:#c0c0c0;font-family:monospace;">'
                     f'{_esc(line)}</div>')

    if in_table:
        parts.append("</table>")

    if output:
        parts.append(
            '<div style="margin-top:20px;padding:12px;background:#1a1a2e;'
            'border-left:3px solid #8b5cf6;border-radius:4px;">'
            '<div style="color:#8b5cf6;font-weight:bold;margin-bottom:6px;">'
            'Данные для экспорта (JSON)</div>'
            f'<pre style="color:#d4d4d4;margin:0;font-size:11px;">'
            f'{_esc(json.dumps(output, indent=2, ensure_ascii=False, default=str))}'
            '</pre></div>'
        )

    style = """
    <style>
        body { background:#0f0f18; color:#d4d4d4;
               font-family:'Monospace','Consolas',monospace;
               font-size:12px; line-height:1.55; }
        table { border-collapse:collapse; }
        .err { background:#3a0f0f; color:#ef4444; padding:10px;
               border-radius:6px; border-left:3px solid #ef4444;
               margin-bottom:12px; }
    </style>
    """
    return style + "<body>" + "".join(parts) + "</body>"
''',

"gui/case_sidebar.py": r'''"""gui/case_sidebar.py — дерево 54 случаев + поиск."""
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
''',

"gui/input_form.py": r'''"""gui/input_form.py — динамическая форма по CASE_META."""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QWidget, QFormLayout, QLabel, QLineEdit, QHBoxLayout, QFrame,
)
from core import astrodynamics as aero
from .case_meta_ext import meta_for


class InputForm(QWidget):
    changed = Signal()
    submit = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMaximumHeight(300)
        self._fields: dict[str, QLineEdit] = {}
        self._sid: str | None = None

        self._outer = QHBoxLayout(self)
        self._outer.setContentsMargins(0, 0, 0, 0)

        self._panel = QFrame()
        self._panel.setStyleSheet(
            "QFrame { background:#15151f; border-radius:8px; }"
        )
        self._panel_layout = QFormLayout(self._panel)
        self._panel_layout.setContentsMargins(12, 12, 12, 12)
        self._panel_layout.setSpacing(8)

        self._title = QLabel("Выберите пункт слева")
        self._title.setStyleSheet(
            "color:#8b5cf6; font-size:13px; font-weight:bold;"
        )
        self._panel_layout.addRow(self._title)
        self._outer.addWidget(self._panel, 1)

    def load_case(self, sid: str) -> None:
        while self._panel_layout.count() > 1:
            item = self._panel_layout.takeAt(1)
            if item.widget():
                item.widget().deleteLater()
        self._fields.clear()
        self._sid = sid

        meta = aero.CASE_META.get(sid)
        if not meta:
            self._title.setText(f"Случай {sid}: неизвестен")
            return

        self._title.setText(f"{sid}. {meta['name']}")

        for key in meta["inputs"]:
            label, unit, typ, mn, mx, default = meta_for(key)
            row = QHBoxLayout()
            edit = QLineEdit(str(default))
            edit.setPlaceholderText(
                f"{mn} … {mx}" if (mn is not None or mx is not None) else ""
            )
            edit.setStyleSheet(self._edit_style())
            edit.textChanged.connect(self.changed.emit)
            edit.returnPressed.connect(self.submit.emit)
            row.addWidget(edit, 1)
            if unit:
                u = QLabel(unit)
                u.setStyleSheet("color:#888; font-size:11px; min-width:40px;")
                row.addWidget(u)
            self._panel_layout.addRow(label, row)
            self._fields[key] = edit

    def values(self) -> dict[str, float] | None:
        out = {}
        ok = True
        for key, edit in self._fields.items():
            text = edit.text().strip().replace(",", ".")
            try:
                out[key] = float(text)
                edit.setStyleSheet(self._edit_style())
            except ValueError:
                edit.setStyleSheet(self._edit_style(error=True))
                ok = False
        return out if ok else None

    def set_values(self, values: dict[str, float]) -> None:
        for k, v in values.items():
            if k in self._fields:
                self._fields[k].setText(str(v))

    def _edit_style(self, error: bool = False) -> str:
        border = "#ef4444" if error else "#333"
        return (
            f"QLineEdit {{ background:#0f0f18; color:#e0e0e0; "
            f"border:1px solid {border}; border-radius:4px; "
            f"padding:5px 8px; font-family:monospace; font-size:12px; }}"
            f"QLineEdit:focus {{ border:1px solid #8b5cf6; }}"
        )
''',

"gui/result_view.py": r'''"""gui/result_view.py — правая панель с результатом."""
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
''',

"gui/history.py": r'''"""gui/history.py — панель истории расчётов."""
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
''',

"gui/theme.py": r'''"""gui/theme.py — QSS и палитра."""
from PySide6.QtGui import QColor, QPalette


def apply_theme(app) -> None:
    app.setStyle("Fusion")
    p = app.palette()
    p.setColor(QPalette.Window, QColor("#0f0f18"))
    p.setColor(QPalette.WindowText, QColor("#d4d4d4"))
    p.setColor(QPalette.Base, QColor("#12121c"))
    p.setColor(QPalette.AlternateBase, QColor("#1a1a2e"))
    p.setColor(QPalette.Text, QColor("#d4d4d4"))
    p.setColor(QPalette.Button, QColor("#2a2a3a"))
    p.setColor(QPalette.ButtonText, QColor("#d4d4d4"))
    p.setColor(QPalette.Highlight, QColor("#8b5cf6"))
    p.setColor(QPalette.HighlightedText, QColor("#ffffff"))
    p.setColor(QPalette.ToolTipBase, QColor("#1a1a2e"))
    p.setColor(QPalette.ToolTipText, QColor("#d4d4d4"))
    app.setPalette(p)

    app.setStyleSheet("""
    QToolBar { background:#15151f; border:none; padding:4px; spacing:6px; }
    QPushButton {
        background:#2a2a3a; color:#d4d4d4;
        border:1px solid #3a3a4a; border-radius:6px;
        padding:6px 14px; font-size:12px;
    }
    QPushButton:hover { background:#3a3a4a; }
    QPushButton:pressed { background:#8b5cf6; }
    QPushButton#primary {
        background:#8b5cf6; color:white;
        border:none; font-weight:bold;
    }
    QPushButton#primary:hover { background:#9d6bff; }
    QSplitter::handle { background:#1a1a2e; width:2px; }
    QStatusBar { background:#15151f; color:#888; }
    QScrollBar:vertical { background:#12121c; width:10px; border:none; }
    QScrollBar::handle:vertical { background:#3a3a4a; border-radius:5px; min-height:20px; }
    QScrollBar::handle:vertical:hover { background:#8b5cf6; }
    """)
''',

"gui/app.py": r'''"""gui/app.py — главное окно orbit-calc GUI."""
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
    app = QApplication(sys.argv)
    apply_theme(app)
    w = MainWindow()
    w.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
''',

"gui/launch_gui.sh": r'''#!/usr/bin/env bash
set -e
cd "$(dirname "$0")/.."
exec python3 -m gui "$@"
''',

"gui/launch_gui.bat": r'''@echo off
chcp 65001 >nul
cd /d "%~dp0\.."
python -m gui %*
if errorlevel 1 pause
''',

"build/orbit-calc-gui.spec": r'''# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec для orbit-calc GUI (PySide6)."""
import os
from pathlib import Path

ROOT = Path(SPECPATH).parent.parent.resolve()

hiddenimports = [
    "core", "core.base", "core.astrodynamics", "core.lambert",
    "core.latex_formulas", "core.optimization",
    "cli", "cli.calculator",
    "gui", "gui.app", "gui.case_sidebar", "gui.input_form",
    "gui.result_view", "gui.history", "gui.runner",
    "gui.html_render", "gui.case_meta_ext", "gui.theme",
    "gui.plots", "gui.animations",
]

excludes = [
    "tkinter", "PyQt5", "PyQt6", "PySide2",
    "test", "tests", "unittest", "pytest",
    "IPython", "jupyter", "notebook",
    "matplotlib.tests",
]

datas = []
for pkg in ("core", "gui", "cli"):
    d = ROOT / pkg
    if d.is_dir():
        datas.append((str(d), pkg))

a = Analysis(
    [str(ROOT / "gui" / "__main__.py")],
    pathex=[str(ROOT)], binaries=[], datas=datas,
    hiddenimports=hiddenimports, hookspath=[],
    runtime_hooks=[], excludes=excludes,
    noarchive=False, optimize=0,
)
pyz = PYZ(a.pure, a.zipped_data)
exe = EXE(
    pyz, a.scripts, a.binaries, a.zipfiles, a.datas, [],
    name="orbit-calc-gui", debug=False, bootloader_ignore_signals=False,
    strip=False, upx=False, console=False, windowed=True, icon=None,
)
''',

"tests/test_gui_smoke.py": r'''"""tests/test_gui_smoke.py — smoke-тесты GUI (offscreen)."""
import json
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")
from PySide6.QtWidgets import QApplication

from gui.app import MainWindow


@pytest.fixture(scope="module")
def app():
    a = QApplication.instance() or QApplication([])
    yield a


def test_window_creates(app):
    w = MainWindow()
    assert w._current_sid == "1"
    w.close()


def test_all_cases_in_sidebar(app):
    w = MainWindow()
    assert len(w.sidebar._items) == 54
    w.close()


def test_case_switch(app):
    w = MainWindow()
    w.on_case_selected("11")
    assert w._current_sid == "11"
    assert "v_p" in w.form._fields
    w.close()


def test_run_case(app):
    w = MainWindow()
    w.on_case_selected("1")
    w.form.set_values({"a": 7000, "e": 0.1})
    w._run_live()
    assert w._current_result is not None
    assert w._current_result.error is None
    assert "a" in w._current_result.output
    w.close()


def test_lambert_54(app):
    w = MainWindow()
    w.on_case_selected("54")
    w.form.set_values(
        {"H1": 622, "H2": 622, "dnu_deg": 90, "dt": 1457, "n_max": 2}
    )
    w._run_live()
    assert w._current_result is not None
    assert w._current_result.error is None
    assert "n_found" in w._current_result.output
    w.close()


def test_export_json(app, tmp_path):
    w = MainWindow()
    w.on_case_selected("2")
    w.form.set_values({"H_p": 408, "H_a": 420})
    w._run_live()
    out = tmp_path / "result.json"
    w._export_json(str(out), w._current_result)
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["case"] == "2"
    assert "a" in data["output"]
    w.close()
''',
}


# ═══════════════════════════════════════════════════════════════════════════
#  pyproject.toml patch
# ═══════════════════════════════════════════════════════════════════════════

PYPROJECT = ROOT / "pyproject.toml"

PYPROJECT_OLD = 'dev = ["pytest>=7"]'
PYPROJECT_NEW = 'dev = ["pytest>=7"]\ngui = ["PySide6>=6.5"]'


# ═══════════════════════════════════════════════════════════════════════════
#  Применение
# ═══════════════════════════════════════════════════════════════════════════


def _write(rel: str, content: str) -> bool:
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        existing = path.read_text(encoding="utf-8")
        if existing == content:
            print(f"  [skip] {rel} (совпадает)")
            return False
        print(f"  [update] {rel} (перезапись)")
        bak = path.with_suffix(path.suffix + ".v7.bak")
        if not bak.exists():
            shutil.copy2(path, bak)
    else:
        print(f"  [new]    {rel}")
    path.write_text(content, encoding="utf-8")
    return True


def _chmod_exec(rel: str) -> None:
    path = ROOT / rel
    if path.exists():
        path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _patch_pyproject() -> None:
    print(f"\n[pyproject.toml]")
    if not PYPROJECT.is_file():
        print(f"  [err] не найден — пропускаю")
        return
    text = PYPROJECT.read_text(encoding="utf-8")
    if 'gui = ["PySide6' in text:
        print("  [skip] gui extra уже есть")
        return
    if PYPROJECT_OLD not in text:
        print(f"  [warn] якорь {PYPROJECT_OLD!r} не найден — добавьте вручную:")
        print(f"         {PYPROJECT_NEW}")
        return
    bak = PYPROJECT.with_suffix(".toml.v7.bak")
    if not bak.exists():
        shutil.copy2(PYPROJECT, bak)
    PYPROJECT.write_text(text.replace(PYPROJECT_OLD, PYPROJECT_NEW, 1), encoding="utf-8")
    print("  [ok] gui = [\"PySide6>=6.5\"]")


def _verify() -> bool:
    print("\n[verify]")
    import subprocess
    checks = [
        ("PySide6 установлен",
         "import PySide6; print(PySide6.__version__)"),
        ("gui.app импортируется",
         "import sys; sys.path.insert(0, '.'); "
         "import gui.app; print('OK')"),
        ("54 case в CASE_META",
         "import sys; sys.path.insert(0, '.'); "
         "from core.astrodynamics import CASE_META; "
         "assert len(CASE_META) == 54, len(CASE_META); print('OK')"),
    ]
    ok = True
    for name, code in checks:
        r = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True, text=True, cwd=str(ROOT),
            env={**os.environ, "QT_QPA_PLATFORM": "offscreen"},
        )
        if r.returncode == 0:
            out = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else "OK"
            print(f"  ✓ {name}: {out}")
        else:
            err = r.stderr.strip().splitlines()[-1] if r.stderr.strip() else "?"
            if name == "PySide6 установлен":
                print(f"  ! {name}: {err}")
                print(f"    Установите: pip install 'PySide6>=6.5'")
                ok = False
            else:
                print(f"  ✗ {name}: {err}")
                ok = False
    return ok


def main() -> int:
    print("[patch v7] GUI для orbit-calc")
    print("=" * 60)

    # 1. Создать все файлы
    print(f"\n[1] Файлы GUI ({len(FILES)} артефактов)")
    n_written = 0
    for rel, content in FILES.items():
        if _write(rel, content):
            n_written += 1

    # 2. chmod +x
    print(f"\n[2] Права исполнения")
    _chmod_exec("gui/launch_gui.sh")
    print(f"  [ok]   gui/launch_gui.sh")

    # 3. pyproject.toml
    _patch_pyproject()

    # 4. Синтаксис
    print(f"\n[3] Синтаксис Python")
    syntax_ok = True
    for rel in FILES:
        if not rel.endswith(".py"):
            continue
        path = ROOT / rel
        try:
            compile(path.read_text(encoding="utf-8"), str(path), "exec")
            print(f"  [ok]   {rel}")
        except SyntaxError as exc:
            print(f"  [err]  {rel}: {exc}")
            syntax_ok = False

    if not syntax_ok:
        return 2

    # 5. Verify
    print("\n[4] Проверка")
    ok = _verify()

    print("\n" + "=" * 60)
    if n_written:
        print(f"[patch v7] Создано/обновлено: {n_written} файлов")
    else:
        print("[patch v7] Все файлы уже на месте")
    print("\nЗапуск GUI:")
    print("  python3 -m gui")
    print("  ./gui/launch_gui.sh")
    print("  gui\\launch_gui.bat  (Windows)")
    print("\nТесты:")
    print("  pytest tests/test_gui_smoke.py -v")
    print("  pytest tests/ -q                    # 112 passed")
    print("\nСборка бинарника:")
    print("  pyinstaller build/orbit-calc-gui.spec "
          "--distpath build/dist --workpath build/work")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())