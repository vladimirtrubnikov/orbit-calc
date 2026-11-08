#!/usr/bin/env python3
"""launcher.py — интерактивный лаунчер для cli/calculator.py.

Запуск без аргументов: показывает меню.
Прямой запуск:          python launcher.py --preset gso
                        python launcher.py --solve 11
                        python launcher.py --check
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CALC = ROOT / "cli" / "calculator.py"
TESTS = ROOT / "tests"
PYPROJECT = ROOT / "pyproject.toml"

# ANSI-цвета (не работают на старом Windows — отключаются автоматически)
if os.name == "nt" and not os.environ.get("WT_SESSION"):
    _C = {"g": "", "y": "", "r": "", "b": "", "c": "", "d": "", "0": ""}
else:
    _C = {
        "g": "\033[32m", "y": "\033[33m", "r": "\033[31m",
        "b": "\033[34m", "c": "\033[36m", "d": "\033[2m", "0": "\033[0m",
    }


def _c(text: str, color: str) -> str:
    return f"{_C[color]}{text}{_C['0']}"


def _header(text: str) -> None:
    print(f"\n{_c('═' * 60, 'c')}")
    print(f"  {_c(text, 'c')}")
    print(f"{_c('═' * 60, 'c')}")


def _ok(msg: str) -> None:
    print(f"  {_c('✓', 'g')} {msg}")


def _warn(msg: str) -> None:
    print(f"  {_c('!', 'y')} {msg}")


def _err(msg: str) -> None:
    print(f"  {_c('✗', 'r')} {msg}")


# ── Проверка окружения ────────────────────────────────────────────────────


def check_environment() -> dict:
    """Проверяет Python, файлы проекта и зависимости."""
    results = {"python": sys.version.split()[0], "calc": False, "tests": False,
               "matplotlib": False, "pytest": False, "warnings": []}

    results["calc"] = CALC.is_file()
    results["tests"] = TESTS.is_dir()

    try:
        import matplotlib  # noqa: F401
        results["matplotlib"] = True
    except ImportError:
        results["warnings"].append(
            "matplotlib не установлен → графики недоступны "
            "(pip install matplotlib)"
        )

    try:
        import pytest  # noqa: F401
        results["pytest"] = True
    except ImportError:
        results["warnings"].append(
            "pytest не установлен → тесты недоступны "
            "(pip install pytest)"
        )

    try:
        import PySide6  # noqa: F401
        results["pyside6"] = True
    except ImportError:
        results["pyside6"] = False

    if sys.version_info < (3, 10):
        results["warnings"].append(
            f"Python {results['python']} < 3.10 — рекомендуется обновиться"
        )

    return results


def print_status(env: dict) -> None:
    _header("ОКРУЖЕНИЕ")
    print(f"  Python:      {env['python']}")
    print(f"  calculator:  {'cli/calculator.py' if env['calc'] else _c('НЕ НАЙДЕН', 'r')}")
    print(f"  tests:       {'tests/' if env['tests'] else _c('нет', 'y')}")
    print(f"  matplotlib:  {_c('✓', 'g') if env['matplotlib'] else _c('нет', 'y')}")
    print(f"  pytest:      {_c('✓', 'g') if env['pytest'] else _c('нет', 'y')}")
    print(f"  PySide6:     {_c('✓', 'g') if env.get('pyside6') else _c('нет', 'y')}  (GUI)")
    for w in env["warnings"]:
        _warn(w)


# ── Запуск ────────────────────────────────────────────────────────────────


def run(args: list[str], capture: bool = False) -> int:
    """Запускает cli/calculator.py как модуль из корня проекта.

    Используется `python -m cli.calculator` + cwd=ROOT + PYTHONPATH=ROOT,
    чтобы `from core import ...` резолвился в локальный core/,
    а не в чужой (например, gemini).
    """
    if not CALC.is_file():
        _err(f"Не найден {CALC}")
        return 1

    cmd = [sys.executable, "-m", "cli.calculator", *args]
    print(f"\n  {_c('$', 'd')} python -m cli.calculator {' '.join(args)}")
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
        print(f"\n  {_c('Прервано пользователем', 'y')}")
        return 130
    except FileNotFoundError:
        _err("Python не найден в PATH")
        return 1



def run_gui(args: list[str] | None = None) -> int:
    """Запускает PySide6 GUI: python -m gui с PYTHONPATH=ROOT."""
    if args is None:
        args = []

    # Проверка PySide6
    try:
        import PySide6  # noqa: F401
    except ImportError:
        _warn("PySide6 не установлен — GUI не запустится")
        print(f"  Установите: {_c('pip install PySide6 matplotlib', 'd')}")
        if _ask_str("Продолжить всё равно? (y/n)", "n").lower() != "y":
            return 1

    gui_main = ROOT / "gui" / "__main__.py"
    if not gui_main.is_file():
        _err(f"Не найден {gui_main}")
        _err("GUI не установлен в проекте")
        return 1

    cmd = [sys.executable, "-m", "gui", *args]
    print(f"\n  {_c('$', 'd')} python -m gui {' '.join(args)}")
    print()

    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")

    try:
        return subprocess.call(cmd, cwd=str(ROOT), env=env)
    except KeyboardInterrupt:
        print(f"\n  {_c('GUI закрыт', 'd')}")
        return 0
    except FileNotFoundError:
        _err("Python не найден в PATH")
        return 1

def run_pytest() -> int:
    if not TESTS.is_dir():
        _err("Директория tests/ отсутствует")
        return 1
    try:
        return subprocess.call([sys.executable, "-m", "pytest", str(TESTS), "-v"])
    except FileNotFoundError:
        _err("pytest не установлен (pip install pytest)")
        return 1


# ── Интерактивное меню ────────────────────────────────────────────────────


def _ask_int(prompt: str, lo: int, hi: int) -> int | None:
    try:
        v = int(input(f"  {prompt} [{lo}..{hi}]: ").strip())
    except (ValueError, EOFError):
        return None
    if not (lo <= v <= hi):
        _warn(f"Введите {lo}..{hi}")
        return None
    return v


def _ask_str(prompt: str, default: str = "") -> str:
    try:
        v = input(f"  {prompt}" + (f" [{default}]" if default else "") + ": ").strip()
        return v or default
    except EOFError:
        return default


def menu_presets() -> None:
    _header("PRESET — готовые сценарии")
    presets = [
        ("gso",       "Геостационарная H = 35786 км"),
        ("iss",       "МКС H = 408×420 км"),
        ("leo-550",   "LEO 550 км (Starlink)"),
        ("meo-20200", "MEO 20200 км (GPS)"),
        ("sso-700",   "Солнечно-синхронная H = 700 км"),
        ("molniya",   "HEO 500×40000 км (Молния)"),
    ]
    for i, (name, desc) in enumerate(presets, 1):
        print(f"  {i}. {name:<12} {desc}")
    print(f"  0. Назад")
    choice = _ask_int("Выбор", 0, len(presets))
    if choice is None or choice == 0:
        return
    run(["--preset", presets[choice - 1][0]])


def menu_solve() -> None:
    _header("--solve — обратные и прямые расчёты")
    groups = {
        "Обратная задача (1–16)": [
            (1, "a и e"), (2, "H_p и H_a"), (3, "H_p и e"),
            (4, "H, v, γ"), (5, "h и ε"), (6, "H_p и v_p"),
            (7, "h и a"), (8, "T → круговая"),
            (9, "H_a и e"), (10, "H_a и v_a"), (11, "v_p и v_a"),
            (12, "h и e"), (13, "p и e"), (14, "T и e"),
            (15, "H_p и h"), (16, "H_a и h"),
        ],
        "Расширение (17–30)": [
            (17, "a и H_p"), (18, "a и H_a"), (19, "T и H_p"),
            (20, "T и v_p"), (21, "e и v_p"), (22, "e и v_a"),
            (23, "H_p и v_a"), (24, "H_a и v_p"),
            (25, "Хоман + Δi"), (26, "Фазирующий манёвр"),
            (27, "Ламберт"), (28, "r, v, ν"),
            (29, "SSO"), (30, "Повторяющаяся траектория"),
        ],
        "Прямые расчёты (31–37)": [
            (31, "Ap/Pe"), (32, "Скорость в точке"),
            (33, "Круговая"), (34, "Хоман"),
            (35, "Биэллиптика"), (36, "Циолковский"),
            (37, "Обратный Циолковский"),
        ],
        "Астрономия (38–45)": [
            (38, "Время пролёта"), (39, "Обратный Кеплер"),
            (40, "Гипербола"), (41, "Хилл и SOI"),
            (42, "L1/L2"), (43, "Синодический период"),
            (44, "Δi"), (45, "Угол места"),
        ],
        "Вектор состояния (46)": [(46, "→ элементы")],
    }
    n = 1
    for group, items in groups.items():
        print(f"\n  {_c(group, 'b')}")
        for sid, title in items:
            print(f"    {n:2d}. [{sid:2d}] {title}")
            n += 1
    print(f"    {n:2d}. Открыть полное меню")
    print(f"     0. Назад")
    total = n
    choice = _ask_int("Выбор", 0, total)
    if choice is None or choice == 0:
        return
    if choice == total:
        run(["--solve"])
        return
    flat = [sid for items in groups.values() for sid, _ in items]
    run(["--solve", str(flat[choice - 1])])


def menu_from() -> None:
    _header("--from — обратная задача по параметрам")
    examples = [
        ("Ap=35786,Pe=35786", "ГСО по Ap/Pe"),
        ("vp=10.25,va=1.60",  "по скоростям"),
        ("a=7000,e=0.1",      "по a и e"),
        ("H_p=200,v_p=10.5",  "по перигею и скорости"),
        ("h=52000,a=8000",    "по h и a"),
    ]
    print("  Примеры:")
    for i, (spec, desc) in enumerate(examples, 1):
        print(f"    {i}. {spec:<22} {desc}")
    print(f"    0. Назад")
    choice = _ask_int("Выбор", 0, len(examples))
    if choice is None or choice == 0:
        return
    custom = _ask_str("Своя строка (Enter — использовать пример)")
    spec = custom if custom else examples[choice - 1][0]
    run(["--from", spec])


def menu_explain() -> None:
    _header("--explain — уровень детализации")
    levels = [
        ("full",  "формулы + шаги + итог (по умолчанию)"),
        ("brief", "без шагов и формул"),
        ("none",  "только ключевые цифры"),
    ]
    for i, (lvl, desc) in enumerate(levels, 1):
        print(f"  {i}. {lvl:<6} {desc}")
    print(f"  0. Назад")
    choice = _ask_int("Выбор", 0, len(levels))
    if choice is None or choice == 0:
        return
    sid = _ask_str("Номер пункта (1..46)", "31")
    try:
        sid_int = int(sid)
    except ValueError:
        _warn("Нужен номер 1..46")
        return
    run([f"--solve={sid_int}", "--explain", levels[choice - 1][0]])


def menu_save_json() -> None:
    _header("--save и --json")
    sid = _ask_str("Номер пункта (1..46)", "2")
    out = _ask_str("Имя файла .md", "session.md")
    want_json = _ask_str("Добавить JSON? (y/n)", "y").lower() == "y"
    args = [f"--solve={sid}", "--save", out]
    if want_json:
        args.append("--json")
    rc = run(args)
    if rc == 0 and Path(out).is_file():
        size = Path(out).stat().st_size
        _ok(f"Сохранено {out} ({size} байт)")


def menu_full_help() -> None:
    _header("Полный help")
    run(["--help"])


# ── Главное меню ──────────────────────────────────────────────────────────


def interactive_menu(env: dict) -> None:
    while True:
        _header("ЛАУНЧЕР: КАЛЬКУЛЯТОР ОРБИТАЛЬНЫХ РАСЧЁТОВ")
        print(f"  {_c('Основное', 'b')}")
        print("   1. Основное меню calculator (11 пунктов + 12 → --solve)")
        print("   2. Меню --solve (46 пунктов)")
        print(f"  {_c('Быстрый доступ', 'b')}")
        print("   3. Preset — готовые сценарии (gso, iss, sso-700, ...)")
        print("   4. --solve=N — прямой вызов пункта")
        print("   5. --from \"Ap=35786,Pe=35786\" — автоопределение случая")
        print("   6. --solve=demo — тур по 4 сценариям")
        print(f"  {_c('Управление выводом', 'b')}")
        print("   7. --explain (full / brief / none)")
        print("   8. --save + --json")
        print(f"  {_c('Проверка и справка', 'b')}")
        print("   9. pytest tests/ -v")
        print("  10. Окружение")
        print("  11. Полный --help")
        print(f"  {_c('GUI', 'b')}")
        print("  12. Запустить GUI (PySide6)")
        print("   0. Выход")

        try:
            choice = input(f"\n  {_c('Выбор', 'c')}: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return

        if choice == "0":
            return
        elif choice == "1":
            run(["--solve"]) if False else run([])  # просто интерактивное меню
        elif choice == "2":
            menu_solve()
        elif choice == "3":
            menu_presets()
        elif choice == "4":
            sid = _ask_str("Номер пункта (1..46)", "11")
            try:
                run([f"--solve={int(sid)}"])
            except ValueError:
                _warn("Нужен номер 1..46")
        elif choice == "5":
            menu_from()
        elif choice == "6":
            run(["--solve=demo"])
        elif choice == "7":
            menu_explain()
        elif choice == "8":
            menu_save_json()
        elif choice == "9":
            run_pytest()
        elif choice == "10":
            print_status(env)
        elif choice == "11":
            menu_full_help()
        elif choice == "12":
            run_gui()
        else:
            _warn("Введите 0..12")

        if choice != "0":
            try:
                input(f"\n  {_c('Enter — вернуться в меню...', 'd')}")
            except (EOFError, KeyboardInterrupt):
                return


# ── main ──────────────────────────────────────────────────────────────────


def main() -> int:
    env = check_environment()

    if not env["calc"]:
        _err(f"Не найден {CALC}")
        _err("Запустите лаунчер из корня проекта.")
        return 1

    args = sys.argv[1:]

    if args:
        # Прямой прокси-режим
        if args[0] in ("--check", "-c"):
            print_status(env)
            return 0
        if args[0] in ("--test", "-t"):
            return run_pytest()
        if args[0] in ("--gui", "-g"):
            return run_gui(args[1:])
        return run(args)

    # Интерактивный режим
    try:
        interactive_menu(env)
    except KeyboardInterrupt:
        print(f"\n  {_c('Выход', 'd')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())