#!/usr/bin/env python3
"""patch_v6.3.py — перемещает _solve_lambert_nrev перед _DISPATCH.

Причина NameError: _DISPATCH = {"54": _solve_lambert_nrev, ...}
вычисляет имя на уровне модуля; если функция определена ПОСЛЕ,
Python ещё не видит её — NameError при импорте.

Фикс: перенести определение функции ВЫШЕ _DISPATCH.
"""
from pathlib import Path
import re
import shutil
import sys

ROOT = Path(__file__).resolve().parent
CALC = ROOT / "cli" / "calculator.py"

FUNC_MARKER = "def _solve_lambert_nrev() -> None:"
DISP_MARKER = "_DISPATCH = {"


def _find_function_bounds(text: str, marker: str):
    idx = text.find(marker)
    if idx < 0:
        return None, None
    lines = text[idx:].split("\n")
    offset = 0
    for i, line in enumerate(lines):
        line_end = offset + len(line) + 1
        if i == 0:
            offset = line_end
            continue
        if line and not line[0].isspace() and not line.startswith("#"):
            return idx, idx + offset
        offset = line_end
    return idx, len(text)


def _verify() -> int:
    print("\n[verify]")
    for mod in list(sys.modules.keys()):
        if mod == "cli" or mod.startswith("cli.") or mod == "core" or mod.startswith("core."):
            del sys.modules[mod]
    sys.path.insert(0, str(ROOT))
    try:
        from cli.calculator import _solve_lambert_nrev, _DISPATCH
        assert callable(_solve_lambert_nrev), "не callable"
        assert _DISPATCH["54"] is _solve_lambert_nrev, "не совпадает"
        print("  ✓ _solve_lambert_nrev + _DISPATCH['54']")

        from core.astrodynamics import solve_case
        r = solve_case("54", H1=622, H2=622, dnu_deg=90, dt=1457, n_max=2)
        assert "error" not in r, r
        print(f"  ✓ solve_case('54'): {r['n_found']} решений")
        for s in r["solutions"]:
            v1 = (s["v1_vec"][0] ** 2 + s["v1_vec"][1] ** 2) ** 0.5
            print(f"    N={s['revs']} {s['branch']}: |v1|={v1:.4f}")
        return 0
    except Exception as exc:
        import traceback
        print(f"  [err] {type(exc).__name__}: {exc}", file=sys.stderr)
        traceback.print_exc()
        return 6


def main() -> int:
    print("[patch v6.3] Перенос _solve_lambert_nrev перед _DISPATCH")
    print("=" * 50)

    if not CALC.is_file():
        print(f"[err] {CALC} не найден", file=sys.stderr)
        return 1

    text = CALC.read_text(encoding="utf-8")

    # 1. Удалить остатки placeholder, если есть
    ph_pat = re.compile(r'_SOLVE_LAMBERT_NREV_SRC = """__PLACEHOLDER__"""\n+')
    text, n_ph = ph_pat.subn("", text)
    if n_ph:
        print(f"[ok] удалено {n_ph} placeholder")

    # 2. Проверить порядок
    f_start, f_end = _find_function_bounds(text, FUNC_MARKER)
    d_idx = text.find(DISP_MARKER)

    if f_start is None:
        print(f"[err] {FUNC_MARKER} не найден", file=sys.stderr)
        return 2
    if d_idx < 0:
        print(f"[err] {DISP_MARKER} не найден", file=sys.stderr)
        return 3

    print(f"[info] функция: pos {f_start}, _DISPATCH: pos {d_idx}")

    if f_start < d_idx:
        print("[skip] функция уже ДО _DISPATCH — порядок правильный")
        return _verify()

    print("[info] функция ПОСЛЕ _DISPATCH → перемещаю")

    # 3. Извлечь функцию
    func_block = text[f_start:f_end].rstrip() + "\n"
    if "_record(" not in func_block:
        print("[warn] в блоке функции нет _record — возможно, обрезано", file=sys.stderr)

    # 4. Удалить из старого места
    text_without = text[:f_start] + text[f_end:]

    # 5. Найти новое место (после удаления позиция изменилась)
    d_idx_new = text_without.find(DISP_MARKER)
    if d_idx_new < 0:
        print("[err] _DISPATCH исчез после удаления", file=sys.stderr)
        return 4

    # 6. Вставить перед _DISPATCH
    new_text = (
        text_without[:d_idx_new]
        + func_block + "\n\n"
        + text_without[d_idx_new:]
    )

    # 7. Нормализовать пустые строки
    new_text = re.sub(r"\n{4,}", "\n\n\n", new_text)

    # 8. Бэкап + запись
    bak = CALC.with_suffix(".py.v6.3.bak")
    if not bak.exists():
        shutil.copy2(CALC, bak)
        print(f"[backup] {bak}")

    # 9. Синтаксис до записи
    try:
        compile(new_text, str(CALC), "exec")
    except SyntaxError as exc:
        print(f"[err] SyntaxError: {exc}", file=sys.stderr)
        return 5

    CALC.write_text(new_text, encoding="utf-8")
    print("[ok] функция перемещена перед _DISPATCH")
    print("[ok] синтаксис корректен")

    # Финальная проверка
    return _verify()


if __name__ == "__main__":
    sys.exit(main())