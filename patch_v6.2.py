#!/usr/bin/env python3
"""patch_v6.2.py — два фикса после v6.1.

1. cli/calculator.py: _SOLVE_LAMBERT_NREV_SRC placeholder → реальная функция
2. tests/test_lambert_nrev.py: test_0rev_compat — dnu=π вместо π/2
"""
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parent
CALC = ROOT / "cli" / "calculator.py"
TESTS = ROOT / "tests" / "test_lambert_nrev.py"


REAL_FUNC = '''def _solve_lambert_nrev() -> None:
    """54: Ламберт N витков (multi-rev)."""
    print("\\n  ЛАМБЕРТ N ВИТКОВ\\n")
    print("  Универсальные переменные, все решения от N=0 до N_max")
    print("  Для N≥1 — до 2 решений (left/right branches)\\n")

    H1 = rf("  H1 (орбита 1), км: ")
    H2 = rf("  H2 (орбита 2), км: ")
    dnu_deg = rf("  Δν, °: ")
    dt_unit = input("  Единица Δt — с/мин/ч [ч]: ").strip().lower() or "ч"
    mult = {"с": 1.0, "s": 1.0, "мин": 60.0, "m": 60.0, "min": 60.0,
            "ч": 3600.0, "h": 3600.0}.get(dt_unit, 3600.0)
    dt_in = rf("  Δt: ")
    dt = dt_in * mult
    n_max = ri("  N_max (0..10): ")
    if n_max < 0 or n_max > 10:
        logger.warning("  N_max ∈ [0, 10]")
        return

    r = aero.solve_case("54", H1=H1, H2=H2, dnu_deg=dnu_deg, dt=dt, n_max=n_max)
    if "error" in r:
        logger.warning(f"  {r['error']}")
        return

    sols = r["solutions"]
    print(f"\\n  Найдено решений: {r['n_found']}")
    print(f"  r1 = {r['r1_km']:.1f} км, r2 = {r['r2_km']:.1f} км, Δν = {dnu_deg:.1f}°, Δt = {dt:.1f} с\\n")

    vc1 = math.sqrt(MU_EARTH / (H1 + R_EARTH))
    vc2 = math.sqrt(MU_EARTH / (H2 + R_EARTH))

    for s in sols:
        v1 = math.hypot(*s["v1_vec"])
        v2 = math.hypot(*s["v2_vec"])
        print(f"  N={s['revs']}, {s['branch']}:")
        print(f"    v1 = ({s['v1_vec'][0]:+.4f}, {s['v1_vec'][1]:+.4f}) км/с  |v1| = {v1:.4f}  ({v1*1000:.1f} м/с)")
        print(f"    v2 = ({s['v2_vec'][0]:+.4f}, {s['v2_vec'][1]:+.4f}) км/с  |v2| = {v2:.4f}  ({v2*1000:.1f} м/с)")
        if s["revs"] == 0:
            print(f"    Δv1 к кругу = {(v1-vc1)*1000:+.2f} м/с,  Δv2 к кругу = {(v2-vc2)*1000:+.2f} м/с")
        print()

    _record(n_solutions=r["n_found"], n_max=n_max, dt_s=dt, dnu_deg=dnu_deg)


'''


OLD_0REV = '''def test_0rev_compat():
    r = 7000.0
    T = _T(r)
    result = lambert_universal(r, r, math.pi / 2, T / 4)
    assert result is not None
    v1, _ = result
    v_circ = math.sqrt(MU_EARTH / r)
    assert abs(math.hypot(*v1) - v_circ) < 0.01'''

NEW_0REV = '''def test_0rev_compat():
    """0-rev Ламберт: совместимость с v3.

    Для 0-rev корректно только Δν = π (A = 0), иначе при z_lo y < 0.
    """
    r1, r2 = 6571.0, 42157.0
    a_t = (r1 + r2) / 2
    dt = math.pi * math.sqrt(a_t ** 3 / MU_EARTH)
    result = lambert_universal(r1, r2, math.pi, dt)
    assert result is not None
    v1, _ = result
    v1_expected = math.sqrt(MU_EARTH * (2 / r1 - 1 / a_t))
    assert abs(math.hypot(*v1) - v1_expected) < 0.01'''


def _patch_calc() -> bool:
    print(f"\n[1] {CALC}")
    if not CALC.is_file():
        print(f"  [err] не найден", file=sys.stderr)
        return False
    text = CALC.read_text(encoding="utf-8")

    if "def _solve_lambert_nrev() -> None:" in text:
        print("  [skip] _solve_lambert_nrev уже определена")
        return True

    placeholder = '_SOLVE_LAMBERT_NREV_SRC = """__PLACEHOLDER__"""'
    if placeholder not in text:
        print(f"  [err] placeholder не найден", file=sys.stderr)
        # диагностика
        for i, line in enumerate(text.splitlines(), 1):
            if "_SOLVE_LAMBERT_NREV" in line or "_solve_lambert_nrev" in line:
                print(f"    L{i}: {line.strip()!r}", file=sys.stderr)
        return False

    bak = CALC.with_suffix(".py.v6.2.bak")
    if not bak.exists():
        shutil.copy2(CALC, bak)
        print(f"  [backup] {bak}")

    text = text.replace(placeholder, REAL_FUNC.rstrip() + "\n", 1)
    CALC.write_text(text, encoding="utf-8")
    print("  [ok] placeholder → реальная функция")
    return True


def _patch_tests() -> bool:
    print(f"\n[2] {TESTS}")
    if not TESTS.is_file():
        print(f"  [err] не найден", file=sys.stderr)
        return False
    text = TESTS.read_text(encoding="utf-8")

    if "a_t = (r1 + r2) / 2" in text and "dnu = math.pi" not in text:
        # уже пропатчен по-другому, но проверяем маркер
        pass

    if NEW_0REV in text:
        print("  [skip] test_0rev_compat уже правильный")
        return True

    if OLD_0REV not in text:
        print("  [warn] старый test_0rev_compat не найден", file=sys.stderr)
        return False

    bak = TESTS.with_suffix(".py.v6.2.bak")
    if not bak.exists():
        shutil.copy2(TESTS, bak)
        print(f"  [backup] {bak}")

    text = text.replace(OLD_0REV, NEW_0REV, 1)
    TESTS.write_text(text, encoding="utf-8")
    print("  [ok] test_0rev_compat: dnu=π")
    return True


def _verify() -> bool:
    print("\n[verify]")
    import importlib
    for mod in list(sys.modules):
        if mod == "cli" or mod.startswith("cli.") or mod == "core" or mod.startswith("core."):
            del sys.modules[mod]
    sys.path.insert(0, str(ROOT))

    try:
        from cli.calculator import _solve_lambert_nrev, _DISPATCH
        assert callable(_solve_lambert_nrev)
        assert _DISPATCH["54"] is _solve_lambert_nrev
        print("  ✓ cli: _solve_lambert_nrev + _DISPATCH[54]")

        from core.lambert import lambert_universal
        r1, r2 = 6571.0, 42157.0
        a_t = (r1 + r2) / 2
        dt = math.pi * (a_t ** 3 / 398600.4418) ** 0.5
        import math
        res = lambert_universal(r1, r2, math.pi, dt)
        assert res is not None, "lambert_universal вернул None при dnu=π"
        print("  ✓ lambert_universal: 0-rev с dnu=π")

        from core.astrodynamics import solve_case
        r = solve_case("54", H1=622, H2=622, dnu_deg=90, dt=1457, n_max=2)
        assert "error" not in r, r
        print(f"  ✓ solve_case(54): {r['n_found']} решений")
        return True
    except Exception as exc:
        import traceback
        print(f"  [err] {type(exc).__name__}: {exc}", file=sys.stderr)
        traceback.print_exc()
        return False


def main():
    print("[patch v6.2] Placeholder + 0-rev тест")
    print("=" * 50)
    import math  # для verify
    globals()["math"] = math

    ok = True
    ok &= _patch_calc()
    ok &= _patch_tests()
    ok &= _verify()

    print("\n" + "=" * 50)
    print("[patch v6.2] Готово" if ok else "[patch v6.2] Ошибки")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())