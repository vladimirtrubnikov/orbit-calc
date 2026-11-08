#!/usr/bin/env python3
"""patch_v4.4.py — 3 фикса после v4.3.

1. core/lambert.py: z_hi = 4π² → 4π²·0.99 (C ≠ 0, бисекция сходится)
2. tests/test_v4.py: EXAMPLES["16"], ["18"] — корректные данные
3. cli/calculator.py: _input_queue мокает _ask_plot (нет OSError в pytest)

Идемпотентен. Резервные копии: *.py.v4.4.bak
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

LAMBERT = Path("core/lambert.py")
TESTS = Path("tests/test_v4.py")
CALC = Path("cli/calculator.py")


# ── 1. core/lambert.py: z_hi → 4π²·0.99 ───────────────────────────────────
P_LAMBERT_OLD = "    z_lo, z_hi = -4 * math.pi ** 2, 4 * math.pi ** 2\n"
P_LAMBERT_NEW = """    # v4.4: z_hi = 4π² даёт C = 0 (деление на ноль). Сдвигаем вниз.
    z_lo, z_hi = -4 * math.pi ** 2, 4 * math.pi ** 2 * 0.99
"""


# ── 2. tests/test_v4.py: EXAMPLES ─────────────────────────────────────────
P_16_OLD = '"16": {"H_a": 400, "h": 52000},'
P_16_NEW = '"16": {"H_a": 400, "h": 51500},   # v4.4: 52000 → e<0; 51500 → e≈0.018'

P_18_OLD = '"18": {"a": 7000, "H_a": 400},'
P_18_NEW = '"18": {"a": 6600, "H_a": 400},    # v4.4: 7000 → e<0; 6600 → e≈0.027'


# ── 3. cli/calculator.py: _input_queue мокает _ask_plot ───────────────────
P_QUEUE_OLD = '''@contextlib.contextmanager
def _input_queue(values):
    """Temporarily replace module-level rf() with a queue of values."""
    mod = sys.modules[__name__]
    original = mod.rf
    queue = list(values)
    idx = [0]

    def mock_rf(prompt=""):
        if idx[0] < len(queue):
            v = queue[idx[0]]
            idx[0] += 1
            print(f"{prompt}{v}")
            return float(v)
        return original(prompt)

    mod.rf = mock_rf
    try:
        yield
    finally:
        mod.rf = original'''

P_QUEUE_NEW = '''@contextlib.contextmanager
def _input_queue(values):
    """Temporarily replace module-level rf() и _ask_plot() с моками."""
    mod = sys.modules[__name__]
    original_rf = mod.rf
    original_ask = getattr(mod, "_ask_plot", None)
    queue = list(values)
    idx = [0]

    def mock_rf(prompt=""):
        if idx[0] < len(queue):
            v = queue[idx[0]]
            idx[0] += 1
            print(f"{prompt}{v}")
            return float(v)
        return original_rf(prompt)

    def mock_ask_plot():
        return False

    mod.rf = mock_rf
    if original_ask is not None:
        mod._ask_plot = mock_ask_plot
    try:
        yield
    finally:
        mod.rf = original_rf
        if original_ask is not None:
            mod._ask_plot = original_ask'''


def _apply(path: Path, old: str, new: str, name: str) -> bool:
    if not path.is_file():
        print(f"  [err] {path} не найден", file=sys.stderr)
        return False
    text = path.read_text(encoding="utf-8")
    if new in text and old not in text:
        print(f"  [skip] {name}")
        return True
    if old not in text:
        print(f"  [err] якорь не найден для {name}: {old[:70]!r}", file=sys.stderr)
        return False
    backup = path.with_suffix(path.suffix + ".v4.4.bak")
    if not backup.exists():
        shutil.copy2(path, backup)
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"  [ok]   {name}")
    return True


def main() -> int:
    print("[patch v4.4] 3 фикса: lambert, EXAMPLES, _ask_plot")
    print("=" * 50)

    print(f"\n[1] {LAMBERT}")
    ok1 = _apply(LAMBERT, P_LAMBERT_OLD, P_LAMBERT_NEW,
                 "z_hi = 4π² → 4π²·0.99")

    print(f"\n[2] {TESTS}")
    ok2a = _apply(TESTS, P_16_OLD, P_16_NEW, "EXAMPLES[16]: h 52000 → 51500")
    ok2b = _apply(TESTS, P_18_OLD, P_18_NEW, "EXAMPLES[18]: a 7000 → 6600")

    print(f"\n[3] {CALC}")
    ok3 = _apply(CALC, P_QUEUE_OLD, P_QUEUE_NEW,
                 "_input_queue мокает _ask_plot")

    if not all([ok1, ok2a, ok2b, ok3]):
        print("\n[patch v4.4] Есть ошибки — см. выше", file=sys.stderr)
        return 2

    # Синтаксис
    for p in (LAMBERT, TESTS, CALC):
        try:
            compile(p.read_text(encoding="utf-8"), str(p), "exec")
        except SyntaxError as exc:
            print(f"  [err] SyntaxError в {p}: {exc}", file=sys.stderr)
            return 3
    print("\n[ok] синтаксис всех трёх файлов корректен")

    print("\n" + "=" * 50)
    print("[patch v4.4] Готово. Проверьте:")
    print("  pytest tests/ -v                              # 95 passed")
    print("  python3 -c \"from core.lambert import lambert_universal; "
          "import math; r=lambert_universal(6571, 42157, math.pi, 18929); "
          "print('OK' if r else 'FAIL')\"")
    return 0


if __name__ == "__main__":
    sys.exit(main())