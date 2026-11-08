#!/usr/bin/env python3
"""patch_v7.4_zero_button.py — кнопка «Обнулить» в InputForm.

Добавляет третью кнопку: обнуляет все поля, не трогая QSettings.
Отличие:
  💾 Сохранить — запомнить текущие значения
  🔄 Сбросить  — вернуть defaults + удалить сохранение
  ⭕ Обнулить  — установить все поля в 0 (сохранение не трогается)

Идемпотентен. Резервные копии: *.v7.4.bak
"""
from __future__ import annotations
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FORM = ROOT / "gui" / "input_form.py"
TESTS = ROOT / "tests" / "test_gui_smoke.py"


# ── 1. Правка input_form.py: добавить метод + кнопку ──────────────────────

METHOD_OLD = '''    def _on_reset(self) -> None:
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
        self._saved_hint.setText("")'''

METHOD_NEW = '''    def _on_reset(self) -> None:
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

    def _on_zero(self) -> None:
        """Устанавливает все поля в 0. Сохранённые значения не трогает."""
        if not self._sid:
            return
        for edit in self._fields.values():
            edit.setText("0")
        self._saved_hint.setText("")'''


BTN_OLD = '''        self._reset_btn = QPushButton("🔄 Сбросить")
        self._reset_btn.setToolTip(
            "Вернуть значения по умолчанию и удалить сохранённые."
        )
        self._reset_btn.clicked.connect(self._on_reset)
        self._reset_btn.setStyleSheet(self._btn_style("#fbbf24"))
        btn_row.addWidget(self._reset_btn)

        btn_row.addStretch(1)'''

BTN_NEW = '''        self._reset_btn = QPushButton("🔄 Сбросить")
        self._reset_btn.setToolTip(
            "Вернуть значения по умолчанию и удалить сохранённые."
        )
        self._reset_btn.clicked.connect(self._on_reset)
        self._reset_btn.setStyleSheet(self._btn_style("#fbbf24"))
        btn_row.addWidget(self._reset_btn)

        self._zero_btn = QPushButton("⭕ Обнулить")
        self._zero_btn.setToolTip(
            "Установить все поля в 0. Сохранённые значения не трогаются."
        )
        self._zero_btn.clicked.connect(self._on_zero)
        self._zero_btn.setStyleSheet(self._btn_style("#94a3b8"))
        btn_row.addWidget(self._zero_btn)

        btn_row.addStretch(1)'''


# ── 2. Дополнительный тест ────────────────────────────────────────────────

NEW_TEST = '''

def test_zero_button(app):
    """Кнопка Обнулить ставит все поля в 0, не трогая QSettings."""
    s = _qsettings()
    s.clear()
    s.sync()
    try:
        w = MainWindow()
        w.on_case_selected("1")
        w.form._fields["a"].setText("8000")
        w.form._fields["e"].setText("0.25")
        w.form._on_save()
        assert s.value("case_1/inputs", "", type=str)  # сохранено

        w.form._on_zero()
        assert w.form._fields["a"].text() == "0"
        assert w.form._fields["e"].text() == "0"
        # QSettings не тронут
        assert s.value("case_1/inputs", "", type=str)
        w.close()
    finally:
        s.clear()
        s.sync()
'''


def main() -> int:
    print("[patch v7.4] Кнопка «Обнулить»")
    print("=" * 60)

    # 1. input_form.py — добавить метод
    if not FORM.is_file():
        print(f"[err] {FORM} не найден", file=sys.stderr)
        return 1
    text = FORM.read_text(encoding="utf-8")
    if "_on_zero" in text and "⭕ Обнулить" in text:
        print("[skip] input_form.py уже с кнопкой")
    else:
        bak = FORM.with_suffix(".py.v7.4.bak")
        if not bak.exists():
            shutil.copy2(FORM, bak)
            print(f"[backup] {bak}")

        if METHOD_OLD not in text:
            print("[err] не найден _on_reset для вставки _on_zero", file=sys.stderr)
            return 2
        text = text.replace(METHOD_OLD, METHOD_NEW, 1)
        print("[ok] добавлен _on_zero")

        if BTN_OLD not in text:
            print("[err] не найден блок кнопок", file=sys.stderr)
            return 3
        text = text.replace(BTN_OLD, BTN_NEW, 1)
        print("[ok] добавлена кнопка ⭕ Обнулить")

        FORM.write_text(text, encoding="utf-8")

    # 2. Синтаксис
    try:
        compile(FORM.read_text(encoding="utf-8"), str(FORM), "exec")
        print("[ok] синтаксис input_form.py")
    except SyntaxError as exc:
        print(f"[err] SyntaxError: {exc}", file=sys.stderr)
        return 4

    # 3. Тест
    if not TESTS.is_file():
        print(f"[err] {TESTS} не найден", file=sys.stderr)
        return 5
    tests = TESTS.read_text(encoding="utf-8")
    if "test_zero_button" in tests:
        print("[skip] тест уже есть")
    else:
        bak = TESTS.with_suffix(".py.v7.4.bak")
        if not bak.exists():
            shutil.copy2(TESTS, bak)
            print(f"[backup] {bak}")
        TESTS.write_text(tests.rstrip() + NEW_TEST, encoding="utf-8")
        print("[ok] +1 тест test_zero_button")

    try:
        compile(TESTS.read_text(encoding="utf-8"), str(TESTS), "exec")
        print("[ok] синтаксис тестов")
    except SyntaxError as exc:
        print(f"[err] SyntaxError: {exc}", file=sys.stderr)
        return 6

    print("\n" + "=" * 60)
    print("[patch v7.4] Готово. Проверьте:")
    print("  pytest tests/test_gui_smoke.py -v")
    print("  pytest tests/ -q                    # 170 passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())