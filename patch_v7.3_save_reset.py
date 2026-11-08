#!/usr/bin/env python3
"""patch_v7.3_save_reset.py — кнопки Сохранить/Сбросить в InputForm.

1. gui/input_form.py — перезапись: QSettings save/restore + кнопки
2. tests/test_gui_smoke.py — +2 теста (save, restore-on-load)

Идемпотентен. Резервные копии: *.v7.3.bak
"""
from __future__ import annotations
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


NEW_INPUT_FORM = r'''"""gui/input_form.py — динамическая форма по CASE_META с save/reset."""
from __future__ import annotations

import json

from PySide6.QtCore import QSettings, QTimer, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel,
    QLineEdit, QFrame, QPushButton,
)
from core import astrodynamics as aero
from .case_meta_ext import meta_for


def _settings() -> QSettings:
    return QSettings("orbit-calc", "gui")


def _saved_key(sid: str) -> str:
    return f"case_{sid}/inputs"


class InputForm(QWidget):
    changed = Signal()
    submit = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMaximumHeight(360)
        self._fields: dict[str, QLineEdit] = {}
        self._sid: str | None = None

        self._outer = QHBoxLayout(self)
        self._outer.setContentsMargins(0, 0, 0, 0)

        self._panel = QFrame()
        self._panel.setStyleSheet(
            "QFrame { background:#15151f; border-radius:8px; }"
        )
        panel_v = QVBoxLayout(self._panel)
        panel_v.setContentsMargins(12, 12, 12, 12)
        panel_v.setSpacing(6)

        self._title = QLabel("Выберите пункт слева")
        self._title.setStyleSheet(
            "color:#8b5cf6; font-size:13px; font-weight:bold;"
        )
        panel_v.addWidget(self._title)

        self._saved_hint = QLabel("")
        self._saved_hint.setStyleSheet(
            "color:#4ade80; font-size:10px; padding:0; margin-bottom:2px;"
        )
        panel_v.addWidget(self._saved_hint)

        self._form_wrap = QWidget()
        self._form_layout = QFormLayout(self._form_wrap)
        self._form_layout.setContentsMargins(0, 0, 0, 0)
        self._form_layout.setSpacing(8)
        panel_v.addWidget(self._form_wrap)

        # ── Кнопки Save/Reset ──
        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)

        self._save_btn = QPushButton("💾 Сохранить")
        self._save_btn.setToolTip(
            "Запомнить текущие значения полей для этого случая. "
            "Сохраняется между запусками."
        )
        self._save_btn.clicked.connect(self._on_save)
        self._save_btn.setStyleSheet(self._btn_style("#4ade80"))
        btn_row.addWidget(self._save_btn)

        self._reset_btn = QPushButton("🔄 Сбросить")
        self._reset_btn.setToolTip(
            "Вернуть значения по умолчанию и удалить сохранённые."
        )
        self._reset_btn.clicked.connect(self._on_reset)
        self._reset_btn.setStyleSheet(self._btn_style("#fbbf24"))
        btn_row.addWidget(self._reset_btn)

        btn_row.addStretch(1)
        panel_v.addLayout(btn_row)

        self._outer.addWidget(self._panel, 1)

    def load_case(self, sid: str) -> None:
        # Очистить старые поля
        while self._form_layout.count():
            item = self._form_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
            else:
                lay = item.layout()
                if lay is not None:
                    while lay.count():
                        sub = lay.takeAt(0)
                        sw = sub.widget()
                        if sw is not None:
                            sw.deleteLater()
        self._fields.clear()
        self._sid = sid

        meta = aero.CASE_META.get(sid)
        if not meta:
            self._title.setText(f"Случай {sid}: неизвестен")
            self._saved_hint.setText("")
            return

        self._title.setText(f"{sid}. {meta['name']}")

        # Загружаем сохранённые значения, если есть
        saved = _settings().value(_saved_key(sid), "", type=str)
        saved_dict: dict = {}
        if saved:
            try:
                saved_dict = json.loads(saved)
            except (ValueError, TypeError):
                saved_dict = {}

        for key in meta["inputs"]:
            label, unit, typ, mn, mx, default = meta_for(key)
            value = saved_dict.get(key, default)
            row = QHBoxLayout()
            edit = QLineEdit(str(value))
            edit.setPlaceholderText(
                f"{mn} … {mx}" if (mn is not None or mx is not None) else ""
            )
            edit.setStyleSheet(self._edit_style())
            edit.textChanged.connect(self._on_field_changed)
            edit.returnPressed.connect(self.submit.emit)
            row.addWidget(edit, 1)
            if unit:
                u = QLabel(unit)
                u.setStyleSheet("color:#888; font-size:11px; min-width:40px;")
                row.addWidget(u)
            self._form_layout.addRow(label, row)
            self._fields[key] = edit

        self._saved_hint.setText(
            "✓ Используются сохранённые значения" if saved_dict else ""
        )

    # ─── Кнопки ─────────────────────────────────────────────
    def _on_save(self) -> None:
        if not self._sid:
            return
        values = self.values()
        if values is None:
            return
        s = _settings()
        s.setValue(_saved_key(self._sid),
                   json.dumps(values, ensure_ascii=False))
        s.sync()
        self._saved_hint.setText("✓ Сохранено")
        orig = self._save_btn.text()
        self._save_btn.setText("✓ Сохранено")
        QTimer.singleShot(1500, lambda: self._save_btn.setText(orig))

    def _on_reset(self) -> None:
        if not self._sid:
            return
        s = _settings()
        s.remove(_saved_key(self._sid))
        s.sync()

        meta = aero.CASE_META.get(self._sid)
        if not meta:
            return
        for key, edit in self._fields.items():
            _, _, _, _, _, default = meta_for(key)
            edit.setText(str(default))
        self._saved_hint.setText("")

    def _on_field_changed(self) -> None:
        if self._saved_hint.text():
            self._saved_hint.setText("")
        self.changed.emit()

    # ─── Значения ────────────────────────────────────────────
    def values(self) -> dict[str, float | str] | None:
        out: dict[str, float | str] = {}
        ok = True
        for key, edit in self._fields.items():
            text = edit.text().strip().replace(",", ".")
            if not text:
                edit.setStyleSheet(self._edit_style(error=True))
                ok = False
                continue
            try:
                out[key] = float(text)
                edit.setStyleSheet(self._edit_style())
            except ValueError:
                # Строковое значение (например, "system" = "1"/"2"/"3")
                out[key] = text
                edit.setStyleSheet(self._edit_style())
        return out if ok else None

    def set_values(self, values: dict[str, float | str]) -> None:
        for k, v in values.items():
            if k in self._fields:
                self._fields[k].setText(str(v))

    # ── Стили ──
    def _edit_style(self, error: bool = False) -> str:
        border = "#ef4444" if error else "#333"
        return (
            f"QLineEdit {{ background:#0f0f18; color:#e0e0e0; "
            f"border:1px solid {border}; border-radius:4px; "
            f"padding:5px 8px; font-family:monospace; font-size:12px; }}"
            f"QLineEdit:focus {{ border:1px solid #8b5cf6; }}"
        )

    def _btn_style(self, accent: str) -> str:
        return (
            f"QPushButton {{ background:#1a1a2e; color:{accent}; "
            f"border:1px solid {accent}; border-radius:4px; "
            f"padding:5px 12px; font-size:11px; font-weight:bold; }}"
            f"QPushButton:hover {{ background:{accent}22; }}"
            f"QPushButton:pressed {{ background:{accent}44; }}"
        )
'''


NEW_TESTS = '''

# ═══════════════════════════════════════════════════════════════════════════
#  v7.3: кнопки Save / Reset в InputForm
# ═══════════════════════════════════════════════════════════════════════════


def _qsettings():
    from PySide6.QtCore import QSettings
    return QSettings("orbit-calc", "gui")


def test_save_button(app):
    """Кнопка Сохранить пишет значения в QSettings."""
    s = _qsettings()
    s.clear()
    s.sync()
    try:
        w = MainWindow()
        w.on_case_selected("1")
        w.form._fields["a"].setText("8000")
        w.form._fields["e"].setText("0.2")
        w.form._on_save()
        raw = s.value("case_1/inputs", "", type=str)
        assert raw, "QSettings не сохранил значения"
        import json
        data = json.loads(raw)
        assert data["a"] == 8000.0
        assert data["e"] == 0.2
        w.close()
    finally:
        s.clear()
        s.sync()


def test_reset_button(app):
    """Кнопка Сбросить возвращает defaults и удаляет сохранение."""
    s = _qsettings()
    s.clear()
    s.sync()
    try:
        w = MainWindow()
        w.on_case_selected("1")
        w.form._fields["a"].setText("8000")
        w.form._on_save()
        assert s.value("case_1/inputs", "", type=str)
        w.form._on_reset()
        assert s.value("case_1/inputs", "", type=str) == ""
        assert float(w.form._fields["a"].text()) == 7000.0
        assert float(w.form._fields["e"].text()) == 0.0
        w.close()
    finally:
        s.clear()
        s.sync()


def test_saved_values_restored_on_load(app):
    """Сохранённые значения подгружаются при переключении case."""
    s = _qsettings()
    s.clear()
    s.sync()
    try:
        w = MainWindow()
        w.on_case_selected("1")
        w.form._fields["a"].setText("8000")
        w.form._fields["e"].setText("0.25")
        w.form._on_save()

        # Переключение на другой case и обратно
        w.on_case_selected("2")
        w.on_case_selected("1")

        assert float(w.form._fields["a"].text()) == 8000.0
        assert float(w.form._fields["e"].text()) == 0.25
        w.close()
    finally:
        s.clear()
        s.sync()
'''


def main() -> int:
    print("[patch v7.3] Save/Reset в InputForm")
    print("=" * 60)

    # 1. Перезаписать gui/input_form.py
    form_path = ROOT / "gui" / "input_form.py"
    if not form_path.is_file():
        print(f"[err] {form_path} не найден", file=sys.stderr)
        return 1
    old = form_path.read_text(encoding="utf-8")
    if "_on_save" in old and "case_" in old:
        print("[skip] gui/input_form.py уже с save/reset")
    else:
        bak = form_path.with_suffix(".py.v7.3.bak")
        if not bak.exists():
            shutil.copy2(form_path, bak)
            print(f"[backup] {bak}")
        form_path.write_text(NEW_INPUT_FORM, encoding="utf-8")
        print("[ok] gui/input_form.py перезаписан")

    # 2. Синтаксис
    try:
        compile(form_path.read_text(encoding="utf-8"), str(form_path), "exec")
        print("[ok] синтаксис input_form.py")
    except SyntaxError as exc:
        print(f"[err] SyntaxError: {exc}", file=sys.stderr)
        return 2

    # 3. Добавить тесты
    tests_path = ROOT / "tests" / "test_gui_smoke.py"
    if not tests_path.is_file():
        print(f"[err] {tests_path} не найден", file=sys.stderr)
        return 3
    tests = tests_path.read_text(encoding="utf-8")
    if "test_save_button" in tests:
        print("[skip] тесты уже добавлены")
    else:
        bak = tests_path.with_suffix(".py.v7.3.bak")
        if not bak.exists():
            shutil.copy2(tests_path, bak)
            print(f"[backup] {bak}")
        tests_path.write_text(tests.rstrip() + NEW_TESTS, encoding="utf-8")
        print("[ok] +3 теста в test_gui_smoke.py")

    try:
        compile(tests_path.read_text(encoding="utf-8"), str(tests_path), "exec")
        print("[ok] синтаксис test_gui_smoke.py")
    except SyntaxError as exc:
        print(f"[err] SyntaxError в тестах: {exc}", file=sys.stderr)
        return 4

    print("\n" + "=" * 60)
    print("[patch v7.3] Готово. Проверьте:")
    print("  pytest tests/test_gui_smoke.py -v")
    print("  pytest tests/ -q                    # 169 passed")
    print("\nВ GUI:")
    print("  - Ввести нестандартные значения → 💾 Сохранить")
    print("  - Переключиться на другой case и обратно → значения восстановятся")
    print("  - 🔄 Сбросить → вернуть defaults и удалить сохранение")
    return 0


if __name__ == "__main__":
    sys.exit(main())