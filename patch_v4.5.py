#!/usr/bin/env python3
"""patch_v4.5.py — синхронизация R_EARTH между core.base и core.astrodynamics.

Причина: core.base.R_EARTH = 6378, core.astrodynamics.R_EARTH = 6371.
Расхождение 7 км → shadow verify падает для case 3 и 17.

Правки:
  1. core/astrodynamics.py — импорт MU_EARTH/R_EARTH/G0 из core.base с fallback
  2. tests/test_astrodynamics.py — test_iss_from_rp_ra: ожидание = 414 + R

Идемпотентен. Резервные копии: *.py.v4.5.bak
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

ASTRO = Path("core/astrodynamics.py")
TESTS = Path("tests/test_astrodynamics.py")


CONST_OLD = '''# ── Константы ──────────────────────────────────────────────────────────────
MU_EARTH = 398_600.4418       # км³/с²
R_EARTH = 6_371.0             # км
G0 = 9.80665                  # м/с²
J2 = 1.08263e-3               # зональный коэффициент
'''

CONST_NEW = '''# ── Константы ──────────────────────────────────────────────────────────────
# v4.5: синхронизированы с core.base (единый источник истины).
# Fallback — если core.base недоступен (автономный импорт).
try:
    from core.base import MU_EARTH, R_EARTH, G0  # noqa: F401
except ImportError:
    MU_EARTH = 398_600.4418       # км³/с²
    R_EARTH = 6_378.0             # км (экваториальный радиус)
    G0 = 9.80665                  # м/с²

J2 = 1.08263e-3               # зональный коэффициент
'''


TEST_ISS_OLD = '''def test_iss_from_rp_ra():
    el = aero.elements_from_rp_ra(408 + R, 420 + R)
    assert abs(el["a"] - 6785.0) < 1
    assert 0 < el["e"] < 0.01
'''

TEST_ISS_NEW = '''def test_iss_from_rp_ra():
    el = aero.elements_from_rp_ra(408 + R, 420 + R)
    a_expected = 414 + R   # v4.5: независимо от значения R_EARTH
    assert abs(el["a"] - a_expected) < 1
    assert 0 < el["e"] < 0.01
'''


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
    backup = path.with_suffix(path.suffix + ".v4.5.bak")
    if not backup.exists():
        shutil.copy2(path, backup)
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"  [ok]   {name}")
    return True


def verify() -> int:
    import subprocess
    code = (
        "import sys; sys.path.insert(0, '.'); "
        "from core.base import R_EARTH as R_base; "
        "from core.astrodynamics import R_EARTH as R_aero, solve_case; "
        "assert abs(R_base - R_aero) < 1e-6, f'{R_base} != {R_aero}'; "
        "r1 = solve_case('3', H_p=200, e=0.01); "
        "r2 = solve_case('17', a=7000, H_p=200); "
        "assert 'error' not in r1, r1; "
        "assert 'error' not in r2, r2; "
        "print(f'OK: R_aero={R_aero} = R_base={R_base}')"
    )
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    if r.returncode == 0:
        print(f"  [ok] {r.stdout.strip()}")
        return 0
    print(f"  [err] {r.stderr.strip()}", file=sys.stderr)
    return 2


def main() -> int:
    print("[patch v4.5] Синхронизация R_EARTH")
    print("=" * 50)

    print(f"\n[1] {ASTRO}")
    ok1 = _apply(ASTRO, CONST_OLD, CONST_NEW, "R_EARTH → из core.base")

    print(f"\n[2] {TESTS}")
    ok2 = _apply(TESTS, TEST_ISS_OLD, TEST_ISS_NEW,
                 "test_iss_from_rp_ra — независим от R")

    if not (ok1 and ok2):
        print("\n[patch v4.5] Ошибки — см. выше", file=sys.stderr)
        return 2

    for p in (ASTRO, TESTS):
        try:
            compile(p.read_text(encoding="utf-8"), str(p), "exec")
        except SyntaxError as exc:
            print(f"  [err] SyntaxError в {p}: {exc}", file=sys.stderr)
            return 3

    print("\n[verify] синхронизация")
    rc = verify()
    if rc != 0:
        return rc

    print("\n" + "=" * 50)
    print("[patch v4.5] Готово. Проверьте:")
    print("  pytest tests/ -v                              # 95 passed")
    print("  python3 cli/calculator.py --solve=3 --verbose")
    print("  python3 cli/calculator.py --solve=17 --verbose")
    return 0


if __name__ == "__main__":
    sys.exit(main())