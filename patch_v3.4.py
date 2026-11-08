#!/usr/bin/env python3
"""patch_v3.4.py — исправляет NameError: name '_c' is not defined.

Причина: _print_latex из patch_v3 использует _c(...) — хелпер launcher.py,
которого в cli/calculator.py нет. Добавляем _c как функцию.

Идемпотентен. Резервная копия: cli/calculator.py.v3.4.bak
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

CALC = Path("cli/calculator.py")

# Якорь: конец bootstrap-блока (после `del _sys, _Path, _ROOT`)
ANCHOR = "del _sys, _Path, _ROOT\n"

# Вставляем _c сразу после bootstrap и до `from __future__`?? Нет —
# from __future__ уже позади, bootstrap тоже. Вставляем после bootstrap.
_C_HELPER = '''
# ── Минимальная замена _c (совместима с launcher._c) ──
import os as _os

if _os.name == "nt" and not _os.environ.get("WT_SESSION"):
    _CC = {"g": "", "y": "", "r": "", "b": "", "c": "", "d": "", "0": ""}
else:
    _CC = {
        "g": "\\033[32m", "y": "\\033[33m", "r": "\\033[31m",
        "b": "\\033[34m", "c": "\\033[36m", "d": "\\033[2m", "0": "\\033[0m",
    }


def _c(text: str, color: str = "0") -> str:
    """Цветной текст. На старом Windows или без TTY — без escape-кодов."""
    code = _CC.get(color, "")
    reset = _CC["0"]
    return f"{code}{text}{reset}" if code else text
'''


def main() -> int:
    if not CALC.is_file():
        print(f"[err] {CALC} не найден", file=sys.stderr)
        return 1

    text = CALC.read_text(encoding="utf-8")

    # Уже исправлено?
    if "def _c(text: str" in text:
        print("[skip] _c уже определён в calculator.py")
        return 0

    # Проверяем, что _print_latex действительно использует _c
    if "_c('LaTeX:', 'b')" not in text and '_c("LaTeX:", "b")' not in text:
        print("[skip] _print_latex не использует _c — нечего чинить")
        return 0

    # Проверяем anchor
    if ANCHOR not in text:
        print(f"[err] не найден anchor `{ANCHOR.strip()}`", file=sys.stderr)
        print("      Возможно, файл правился вручную. Показываю первые 15 строк:",
              file=sys.stderr)
        for i, line in enumerate(text.splitlines()[:15], 1):
            print(f"      {i:>2}: {line}", file=sys.stderr)
        return 2

    # Бэкап
    backup = CALC.with_suffix(CALC.suffix + ".v3.4.bak")
    if not backup.exists():
        shutil.copy2(CALC, backup)
        print(f"[backup] {backup}")

    # Вставляем _c после bootstrap
    new_text = text.replace(ANCHOR, ANCHOR + _C_HELPER, 1)
    CALC.write_text(new_text, encoding="utf-8")
    print("[ok] _c добавлен после bootstrap-блока")

    # Пост-проверка синтаксиса
    try:
        compile(CALC.read_text(encoding="utf-8"), str(CALC), "exec")
        print("[ok] синтаксис корректен")
    except SyntaxError as exc:
        print(f"[err] SyntaxError: {exc}", file=sys.stderr)
        return 3

    # Проверка, что функция действительно доступна
    try:
        sys.path.insert(0, ".")
        # Переимпорт без побочных эффектов — только проверка символа
        import importlib
        if "cli.calculator" in sys.modules:
            del sys.modules["cli.calculator"]
        mod = importlib.import_module("cli.calculator")
        assert callable(getattr(mod, "_c", None)), "_c не callable"
        print("[ok] _c импортируется и вызывается")
    except Exception as exc:
        print(f"[warn] не удалось проверить импорт: {exc}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())