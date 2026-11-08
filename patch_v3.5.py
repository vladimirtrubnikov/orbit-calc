#!/usr/bin/env python3
"""patch_v3.5.py — regression-тесты для _c и _print_latex.

Добавляет в tests/test_solvers.py:
  - test_color_helper       — _c возвращает str
  - test_latex_helper       — _print_latex не падает при _SHOW_LATEX=True
  - test_latex_formulas_known — core.latex_formulas.get_formulas для 47-53
  - test_dispatch_47_53_present — все новые пункты есть в _DISPATCH

Идемпотентен. Резервная копия: tests/test_solvers.py.v3.5.bak
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

TESTS = Path("tests/test_solvers.py")

NEW_TESTS = '''

# ═══════════════════════════════════════════════════════════════════════════
#  v3.5: regression-тесты для _c / _print_latex / LaTeX-формул
# ═══════════════════════════════════════════════════════════════════════════


def test_color_helper():
    """_c возвращает str и не падает для любого разумного входа."""
    from cli import calculator as calc
    for color in ("g", "y", "r", "b", "c", "d", "0", "unknown"):
        result = calc._c("x", color)
        assert isinstance(result, str), f"color={color!r}"
        assert "x" in result, f"color={color!r}"


def test_latex_helper(capsys):
    """_print_latex не падает при _SHOW_LATEX=True (ловит NameError: _c)."""
    from cli import calculator as calc
    old = calc._SHOW_LATEX
    calc._SHOW_LATEX = True
    try:
        calc._print_latex("47")
        calc._print_latex("1")
        calc._print_latex("999")   # неизвестный — не должен падать
    finally:
        calc._SHOW_LATEX = old
    out = capsys.readouterr().out
    assert "LaTeX" in out or out == ""  # для "999" — пусто, допустимо


def test_latex_formulas_known():
    """LaTeX определён для новых пунктов 47, 49, 51, 52, 53."""
    from core import latex_formulas as lf
    for sid in ("47", "49", "51", "52", "53"):
        formulas = lf.get_formulas(sid)
        assert isinstance(formulas, list), f"sid={sid}"
        assert len(formulas) > 0, f"Нет LaTeX для случая {sid}"
        for f in formulas:
            assert isinstance(f, str) and f, f"пустая формула в {sid}"


def test_latex_formulas_unknown_empty():
    """Для неизвестного sid get_formulas возвращает []."""
    from core import latex_formulas as lf
    assert lf.get_formulas("nonexistent") == []
    assert lf.get_formulas("54") == []   # 54 пока не реализован


def test_dispatch_47_53_present():
    """Все новые пункты 47-53 зарегистрированы в _DISPATCH."""
    from cli import calculator as calc
    for i in range(47, 54):
        sid = str(i)
        assert sid in calc._DISPATCH, f"Отсутствует пункт {sid}"
        assert callable(calc._DISPATCH[sid]), f"Пункт {sid} не callable"


def test_dispatch_solve_dispatcher():
    """_dispatch_solve зовёт _DISPATCH[sid] без падения."""
    from cli import calculator as calc

    called = []
    original = calc._DISPATCH["47"]
    calc._DISPATCH["47"] = lambda: called.append("ok")
    old = calc._SHOW_LATEX
    calc._SHOW_LATEX = False
    try:
        calc._dispatch_solve("47")
    finally:
        calc._DISPATCH["47"] = original
        calc._SHOW_LATEX = old
    assert called == ["ok"]
'''


def main() -> int:
    if not TESTS.is_file():
        print(f"[err] {TESTS} не найден", file=sys.stderr)
        return 1

    text = TESTS.read_text(encoding="utf-8")

    if "def test_color_helper()" in text:
        print("[skip] v3.5-тесты уже добавлены")
        return 0

    # Якорь: конец файла (последняя строка test_from_parse_gso).
    # Вставляем после последней непустой строки.
    backup = TESTS.with_suffix(TESTS.suffix + ".v3.5.bak")
    if not backup.exists():
        shutil.copy2(TESTS, backup)
        print(f"[backup] {backup}")

    # Убираем trailing whitespace и гарантируем ровно одну пустую строку
    text = text.rstrip() + "\n"
    new_text = text + NEW_TESTS
    TESTS.write_text(new_text, encoding="utf-8")
    print(f"[ok] добавлено {NEW_TESTS.count('def test_')} новых тестов")

    # Проверка синтаксиса
    try:
        compile(new_text, str(TESTS), "exec")
        print("[ok] синтаксис корректен")
    except SyntaxError as exc:
        print(f"[err] SyntaxError: {exc}", file=sys.stderr)
        return 3

    # Проверка, что pytest найдёт новые тесты
    try:
        import subprocess
        r = subprocess.run(
            [sys.executable, "-m", "pytest", str(TESTS), "--collect-only", "-q"],
            capture_output=True, text=True,
        )
        lines = [ln for ln in r.stdout.splitlines() if "::" in ln]
        new_names = {
            "test_color_helper", "test_latex_helper",
            "test_latex_formulas_known", "test_latex_formulas_unknown_empty",
            "test_dispatch_47_53_present", "test_dispatch_solve_dispatcher",
        }
        found = {ln.rsplit("::", 1)[-1] for ln in lines} & new_names
        missing = new_names - found
        if missing:
            print(f"[warn] pytest не увидел: {missing}", file=sys.stderr)
        else:
            print(f"[ok] pytest видит все {len(new_names)} новых тестов")
    except Exception as exc:
        print(f"[warn] не удалось запустить pytest --collect-only: {exc}",
              file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())