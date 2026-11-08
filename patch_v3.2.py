#!/usr/bin/env python3
"""patch_v3.2.py — исправляет ImportError: cannot import name 'astrodynamics'.

Причины: cli/calculator.py запускается как скрипт, sys.path[0] = cli/,
поэтому `from core import ...` резолвится в чужой core/ (например, gemini).

Правки:
  1. bootstrap sys.path в cli/calculator.py (insert(0, ROOT))
  2. launcher.py: запуск через `python -m cli.calculator` с cwd=ROOT + PYTHONPATH
  3. (опционально) pyproject.toml — если не существует

Идемпотентен. Резервные копии: *.py.v3.2.bak
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

CALC = Path("cli/calculator.py")
LAUNCHER = Path("launcher.py")
PYPROJECT = Path("pyproject.toml")


# ── Правка 1: bootstrap в cli/calculator.py ────────────────────────────────
BOOTSTRAP_OLD = '''"""cli/calculator.py — Интерактивный калькулятор орбитальных и астрономических расчётов."""

from __future__ import annotations
'''

BOOTSTRAP_NEW = '''"""cli/calculator.py — Интерактивный калькулятор орбитальных и астрономических расчётов."""

# ── bootstrap sys.path: работает при `python cli/calculator.py` из любого CWD ──
import sys as _sys
from pathlib import Path as _Path

_ROOT = _Path(__file__).resolve().parent.parent
if str(_ROOT) not in _sys.path:
    _sys.path.insert(0, str(_ROOT))
del _sys, _Path, _ROOT

from __future__ import annotations
'''


# ── Правка 2: launcher.run() ───────────────────────────────────────────────
RUN_OLD = '''def run(args: list[str], capture: bool = False) -> int:
    """Запускает cli/calculator.py с аргументами через subprocess."""
    if not CALC.is_file():
        _err(f"Не найден {CALC}")
        return 1

    cmd = [sys.executable, str(CALC), *args]
    print(f"\\n  {_c('$', 'd')} python {CALC.relative_to(ROOT)} {' '.join(args)}")
    print()

    try:
        if capture:
            r = subprocess.run(cmd, capture_output=True, text=True)
            print(r.stdout)
            if r.stderr:
                print(_c(r.stderr, "r"))
            return r.returncode
        return subprocess.call(cmd)
    except KeyboardInterrupt:
        print(f"\\n  {_c('Прервано пользователем', 'y')}")
        return 130
    except FileNotFoundError:
        _err("Python не найден в PATH")
        return 1
'''

RUN_NEW = '''def run(args: list[str], capture: bool = False) -> int:
    """Запускает cli/calculator.py как модуль из корня проекта.

    Используется `python -m cli.calculator` + cwd=ROOT + PYTHONPATH=ROOT,
    чтобы `from core import ...` резолвился в локальный core/,
    а не в чужой (например, gemini).
    """
    if not CALC.is_file():
        _err(f"Не найден {CALC}")
        return 1

    cmd = [sys.executable, "-m", "cli.calculator", *args]
    print(f"\\n  {_c('$', 'd')} python -m cli.calculator {' '.join(args)}")
    print()

    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")

    try:
        if capture:
            r = subprocess.run(cmd, capture_output=True, text=True,
                               cwd=str(ROOT), env=env)
            print(r.stdout)
            if r.stderr:
                print(_c(r.stderr, "r"))
            return r.returncode
        return subprocess.call(cmd, cwd=str(ROOT), env=env)
    except KeyboardInterrupt:
        print(f"\\n  {_c('Прервано пользователем', 'y')}")
        return 130
    except FileNotFoundError:
        _err("Python не найден в PATH")
        return 1
'''


# ── Правка 3: pyproject.toml (создаётся только если нет) ───────────────────
PYPROJECT_TEXT = '''[project]
name = "orbit-calc"
version = "0.3.0"
description = "Универсальный калькулятор орбитальных и астрономических расчётов"
readme = "README.md"
requires-python = ">=3.10"
license = {text = "MIT"}
dependencies = ["matplotlib>=3.5"]

[project.optional-dependencies]
dev = ["pytest>=7"]

[project.scripts]
orbit-calc = "cli.calculator:main"
orbit-launcher = "launcher:main"

[build-system]
requires = ["setuptools>=61"]
build-backend = "setuptools.build_meta"

[tool.setuptools]
packages = ["core", "cli", "gui"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-v"
'''


def _backup(path: Path) -> Path:
    bak = path.with_suffix(path.suffix + ".v3.2.bak")
    if not bak.exists():
        shutil.copy2(path, bak)
        print(f"  [backup] {bak}")
    return bak


def _apply(text: str, old: str, new: str, name: str) -> tuple[str, bool]:
    """Возвращает (text, changed). Пропускает если уже применено."""
    if new in text and old not in text:
        print(f"  [skip]   {name} — уже применён")
        return text, False
    if old not in text:
        raise RuntimeError(f"Якорь не найден для {name}: {old[:70]!r}")
    print(f"  [ok]     {name}")
    return text.replace(old, new, 1), True


def fix_calc() -> int:
    print(f"\n[1] {CALC}")
    if not CALC.is_file():
        print(f"  [err] файл не найден")
        return 1

    text = CALC.read_text(encoding="utf-8")

    # Проверка: уже есть bootstrap?
    if "_ROOT = _Path(__file__).resolve().parent.parent" in text:
        print("  [skip]   bootstrap уже есть")
        return 0

    if "_ROOT = _Path(__file__).resolve().parent.parent" in text:
        return 0

    # Порядок: сначала проверяем что old есть, потом бэкапим
    if BOOTSTRAP_OLD not in text:
        print("  [err] шапка файла не соответствует ожидаемой")
        print("        ожидалось начало:")
        print("        " + BOOTSTRAP_OLD.splitlines()[0])
        print("        фактически:")
        for line in text.splitlines()[:3]:
            print(f"        {line!r}")
        return 2

    _backup(CALC)
    text = text.replace(BOOTSTRAP_OLD, BOOTSTRAP_NEW, 1)
    CALC.write_text(text, encoding="utf-8")
    print("  [ok]     bootstrap sys.path вставлен")
    return 0


def fix_launcher() -> int:
    print(f"\n[2] {LAUNCHER}")
    if not LAUNCHER.is_file():
        print("  [skip]   launcher.py отсутствует")
        return 0

    text = LAUNCHER.read_text(encoding="utf-8")

    if '"cwd=str(ROOT)"' in text and '"-m", "cli.calculator"' in text:
        print("  [skip]   run() уже исправлен")
        return 0

    if RUN_OLD not in text:
        print("  [err] run() не найден в ожидаемом виде")
        print("        возможно, launcher.py уже правился вручную")
        print("        проверьте, что функция run() содержит:")
        print("          cmd = [sys.executable, str(CALC), *args]")
        return 2

    _backup(LAUNCHER)
    text = text.replace(RUN_OLD, RUN_NEW, 1)

    # Убедимся, что os импортирован (RUN_NEW использует os.environ)
    if "\nimport os\n" not in text and "import os\n" not in text.split("\n\n")[0]:
        # добавляем import os после первого import
        lines = text.splitlines()
        for i, line in enumerate(lines):
            if line.startswith("import "):
                lines.insert(i + 1, "import os")
                break
        text = "\n".join(lines) + "\n"
        print("  [ok]     import os добавлен")

    LAUNCHER.write_text(text, encoding="utf-8")
    print("  [ok]     run() → python -m cli.calculator")
    return 0


def ensure_pyproject() -> int:
    print(f"\n[3] {PYPROJECT}")
    if PYPROJECT.is_file():
        print("  [skip]   уже существует (не перезаписываю)")
        return 0
    PYPROJECT.write_text(PYPROJECT_TEXT, encoding="utf-8")
    print("  [ok]     создан")
    return 0


def verify() -> None:
    """Пост-проверка: импорт локального core."""
    print("\n[verify] проверка импорта")
    import subprocess

    # Проверяем, что локальный core/astrodynamics.py существует
    astro = Path("core/astrodynamics.py")
    latex = Path("core/latex_formulas.py")
    if astro.is_file():
        print(f"  [ok]     {astro}")
    else:
        print(f"  [err]    {astro} ОТСУТСТВУЕТ — скопируйте из ответа v3")
    if latex.is_file():
        print(f"  [ok]     {latex}")
    else:
        print(f"  [err]    {latex} ОТСУТСТВУЕТ — скопируйте из ответа v3")

    # Проверяем, что calc импортируется как модуль
    r = subprocess.run(
        [sys.executable, "-c",
         "import sys; sys.path.insert(0, '.'); "
         "from core import astrodynamics; "
         "print('OK:', astrodynamics.__file__)"],
        capture_output=True, text=True,
    )
    if r.returncode == 0:
        print(f"  [ok]     {r.stdout.strip()}")
    else:
        print(f"  [err]    импорт падает:\n{r.stderr.strip()}")


def main() -> int:
    print("[patch v3.2] Исправление ImportError")
    print("=" * 50)

    rc = 0
    rc |= fix_calc()
    rc |= fix_launcher()
    rc |= ensure_pyproject()
    verify()

    print("\n" + "=" * 50)
    if rc == 0:
        print("[patch v3.2] Готово. Проверьте:")
        print("  python3 cli/calculator.py --solve=47 --latex")
        print("  python3 cli/calculator.py --preset gso")
        print("  python3 launcher.py --solve 47")
        print("  pytest tests/ -v")
    else:
        print(f"[patch v3.2] Завершён с ошибками (rc={rc}).")
    return rc


if __name__ == "__main__":
    sys.exit(main())