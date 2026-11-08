#!/usr/bin/env python3
"""patch_v4.4b.py — позиционный фикс _input_queue → _ask_plot.

Не зависит от точного форматирования тела _input_queue.
Находит функцию по началу, конец — по `mod.rf = original`.
Три точечные замены внутри.

Идемпотентен. Резервная копия: cli/calculator.py.v4.4b.bak
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

CALC = Path("cli/calculator.py")


def _find_function(text: str, start_marker: str, end_marker: str):
    """Возвращает (start, end) границы функции или (None, None)."""
    i = text.find(start_marker)
    if i < 0:
        return None, None
    # Найти конец — первую строку с end_marker (с отступом 4 или 8 пробелов)
    for prefix in ("        ", "    "):
        j = text.find(f"{prefix}{end_marker}", i)
        if j >= 0:
            # Расширяем до конца строки включительно
            newline = text.find("\n", j)
            if newline < 0:
                return i, len(text)
            return i, newline + 1
    return None, None


def _patch(text: str) -> tuple[str, str]:
    """Возвращает (new_text, status)."""
    start_marker = "def _input_queue(values):"
    end_marker = "mod.rf = original"

    s, e = _find_function(text, start_marker, end_marker)
    if s is None or e is None:
        return text, "not_found"

    func = text[s:e]

    # Уже пропатчено?
    if "_ask_plot" in func:
        return text, "already"

    # 1) Сохраняем original _ask_plot
    anchor = "    original = mod.rf\n"
    if anchor not in func:
        return text, "anchor1_not_found"
    func = func.replace(
        anchor,
        anchor + '    original_ask = getattr(mod, "_ask_plot", None)\n',
        1,
    )

    # 2) Подменяем mod._ask_plot после установки mod.rf
    anchor = "    mod.rf = mock_rf\n"
    if anchor not in func:
        return text, "anchor2_not_found"
    func = func.replace(
        anchor,
        anchor
        + "    if original_ask is not None:\n"
        + "        mod._ask_plot = lambda: False\n",
        1,
    )

    # 3) Восстанавливаем в finally
    # end_marker уже содержит "        mod.rf = original\n" (8 пробелов)
    anchor = "        mod.rf = original\n"
    if anchor not in func:
        return text, "anchor3_not_found"
    func = func.replace(
        anchor,
        anchor
        + "        if original_ask is not None:\n"
        + "            mod._ask_plot = original_ask\n",
        1,
    )

    new_text = text[:s] + func + text[e:]
    return new_text, "patched"


def main() -> int:
    print("[patch v4.4b] Позиционный фикс _input_queue → _ask_plot")
    print("=" * 50)

    if not CALC.is_file():
        print(f"[err] {CALC} не найден", file=sys.stderr)
        return 1

    text = CALC.read_text(encoding="utf-8")

    if "def _input_queue" not in text:
        print("[err] _input_queue не найден в файле", file=sys.stderr)
        return 2

    new_text, status = _patch(text)

    if status == "already":
        print("[skip] _input_queue уже мокает _ask_plot")
        return 0

    if status != "patched":
        print(f"[err] не удалось: {status}", file=sys.stderr)
        print("\nДиагностика: показать _input_queue (первые 30 строк):",
              file=sys.stderr)
        idx = text.find("def _input_queue")
        print(text[idx:idx + 1500], file=sys.stderr)
        return 3

    # Синтаксис
    try:
        compile(new_text, str(CALC), "exec")
    except SyntaxError as exc:
        print(f"[err] SyntaxError после правки: {exc}", file=sys.stderr)
        return 4

    backup = CALC.with_suffix(CALC.suffix + ".v4.4b.bak")
    if not backup.exists():
        shutil.copy2(CALC, backup)
        print(f"[backup] {backup}")

    CALC.write_text(new_text, encoding="utf-8")
    print("[ok] _input_queue теперь мокает _ask_plot")
    print("[ok] синтаксис корректен")
    print("\n" + "=" * 50)
    print("Готово. Проверьте:")
    print("  pytest tests/ -v                              # 95 passed")
    print("  python3 cli/calculator.py --solve=1 --verbose # shadow verify")
    return 0


if __name__ == "__main__":
    sys.exit(main())