#!/usr/bin/env python3
"""patch_v7.2_fix_nfound.py — добавляет n_found в _record _solve_lambert_nrev.

Проблема: cli._solve_lambert_nrev делает
  _record(n_solutions=r["n_found"], ...)
а тест и GUI ожидают n_found (как в aero.solve_case).

Фикс: _record с ОБОИМИ ключами — n_found и n_solutions — для совместимости.

Идемпотентен. Резервная копия: cli/calculator.py.v7.2.bak
"""
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parent
CALC = ROOT / "cli" / "calculator.py"

OLD = '_record(n_solutions=r["n_found"], n_max=n_max, dt_s=dt, dnu_deg=dnu_deg)'
NEW = (
    '_record(n_found=r["n_found"], n_solutions=r["n_found"], '
    'n_max=n_max, dt_s=dt, dnu_deg=dnu_deg)'
)


def main() -> int:
    print("[patch v7.2] n_found в _RESULT _solve_lambert_nrev")
    print("=" * 50)

    if not CALC.is_file():
        print(f"[err] {CALC} не найден", file=sys.stderr)
        return 1

    text = CALC.read_text(encoding="utf-8")
    if NEW in text:
        print("[skip] n_found уже есть в _record")
        return 0
    if OLD not in text:
        print("[err] якорь не найден", file=sys.stderr)
        # показать строку
        for i, line in enumerate(text.splitlines(), 1):
            if "_record(" in line and ("n_solutions" in line or "n_found" in line):
                print(f"  L{i}: {line.strip()!r}", file=sys.stderr)
        return 2

    bak = CALC.with_suffix(".py.v7.2.bak")
    if not bak.exists():
        shutil.copy2(CALC, bak)
        print(f"[backup] {bak}")

    new_text = text.replace(OLD, NEW, 1)

    try:
        compile(new_text, str(CALC), "exec")
    except SyntaxError as exc:
        print(f"[err] SyntaxError: {exc}", file=sys.stderr)
        return 3

    CALC.write_text(new_text, encoding="utf-8")
    print("[ok] n_found добавлен (и n_solutions для совместимости)")

    print("\n" + "=" * 50)
    print("[patch v7.2] Готово. Проверьте:")
    print("  pytest tests/test_gui_smoke.py -v       # 6 passed")
    print("  pytest tests/ -q                        # 112 passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())