#!/usr/bin/env python3
"""patch_v4b.py — рефакторинг 17 простейших _solve_* через aero.solve_case.

Список: 1, 2, 3, 5, 7, 9, 11, 12, 13, 15, 16, 17, 18, 21, 22, 23, 24.
Вычисления уходят в aero.solve_case; шаги печати сохранены.

Идемпотентен. Резервная копия: cli/calculator.py.v4b.bak
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

CALC = Path("cli/calculator.py")
TESTS = Path("tests/test_v4.py")


# ── Полный порядок функций между _solve_a_e и _solve_hohmann_incl ─────────
ALL_FUNCS_ORDER = [
    "_solve_a_e", "_solve_rp_ra", "_solve_rp_e", "_solve_r_v_gamma",
    "_solve_h_eps", "_solve_rp_vp", "_solve_h_a", "_solve_T_circular",
    "_solve_ra_e", "_solve_ra_va", "_solve_vp_va", "_solve_h_e",
    "_solve_p_e", "_solve_T_e", "_solve_rp_h", "_solve_ra_h",
    "_solve_a_rp", "_solve_a_ra", "_solve_T_rp", "_solve_T_vp",
    "_solve_e_vp", "_solve_e_va", "_solve_rp_va", "_solve_ra_vp",
    "_solve_hohmann_incl",
]


# ═══════════════════════════════════════════════════════════════════════════
#  17 новых тел
# ═══════════════════════════════════════════════════════════════════════════

NEW_FUNCTIONS = {

    "_solve_a_e": '''def _solve_a_e() -> None:
    """1: известны a и e."""
    print("\\n  СЛУЧАЙ 1: a и e\\n")
    print("  r_p = a·(1 − e),  r_a = a·(1 + e),  p = a·(1 − e²)")
    print("  h = √(μ·p),  ε = −μ/(2a),  T = 2π·√(a³/μ)\\n")

    a = rf("  a, км: ")
    e = rf("  e (0 ≤ e < 1): ")

    r = aero.solve_case("1", a=a, e=e)
    if "error" in r:
        logger.warning(f"  {r['error']}")
        return

    print(f"\\n  Шаг 1: r_p = {a:.3f}·(1 − {e:.6f}) = {r['r_p']:.3f} км")
    print(f"  Шаг 1: r_a = {a:.3f}·(1 + {e:.6f}) = {r['r_a']:.3f} км")
    print(f"  Шаг 2: p = {a:.3f}·(1 − {e * e:.6f}) = {r['p']:.3f} км")
    print(f"  Шаг 3: h = √({MU_EARTH:.4f}·{r['p']:.3f}) = {r['h']:.4f} км²/с")
    print(f"  Шаг 4: ε = −{MU_EARTH:.4f}/(2·{a:.3f}) = {r['eps']:.4f} км²/с²")
    _print_orbit_result(r["a"], r["e"])
''',

    "_solve_rp_ra": '''def _solve_rp_ra() -> None:
    """2: известны H_p и H_a."""
    print("\\n  СЛУЧАЙ 2: H_p и H_a\\n")
    print("  a = (r_p + r_a)/2,  e = (r_a − r_p)/(r_a + r_p)\\n")

    H_p = rf("  H_p, км: ")
    H_a = rf("  H_a, км: ")
    if H_p < 0 or H_a < 0:
        logger.warning("  Высоты должны быть ≥ 0")
        return
    if H_a < H_p:
        print("  (меняем местами)")
        H_p, H_a = H_a, H_p

    r = aero.solve_case("2", H_p=H_p, H_a=H_a)
    if "error" in r:
        logger.warning(f"  {r['error']}")
        return

    print(f"\\n  Шаг 0: r_p = {H_p:.3f} + {R_EARTH:.3f} = {r['r_p']:.3f} км")
    print(f"  Шаг 0: r_a = {H_a:.3f} + {R_EARTH:.3f} = {r['r_a']:.3f} км")
    print(f"  Шаг 1: a = {r['a']:.3f} км")
    print(f"  Шаг 2: e = {r['e']:.6f}")
    _print_orbit_result(r["a"], r["e"])
''',

    "_solve_rp_e": '''def _solve_rp_e() -> None:
    """3: известны H_p и e."""
    print("\\n  СЛУЧАЙ 3: H_p и e\\n")
    print("  a = r_p/(1 − e),  r_a = a·(1 + e)\\n")

    H_p = rf("  H_p, км: ")
    e = rf("  e: ")

    r = aero.solve_case("3", H_p=H_p, e=e)
    if "error" in r:
        logger.warning(f"  {r['error']}")
        return

    r_p = H_p + R_EARTH
    print(f"\\n  Шаг 0: r_p = {r_p:.3f} км")
    print(f"  Шаг 1: a = {r_p:.3f}/(1 − {e:.6f}) = {r['a']:.3f} км")
    print(f"  Шаг 2: r_a = {r['a']:.3f}·(1 + {e:.6f}) = {r['r_a']:.3f} км")
    _print_orbit_result(r["a"], r["e"])
''',

    "_solve_h_eps": '''def _solve_h_eps() -> None:
    """5: известны h и ε."""
    print("\\n  СЛУЧАЙ 5: h и ε\\n")
    print("  a = −μ/(2ε),  p = h²/μ,  e = √(1 − p/a)\\n")

    h = rf("  h, км²/с: ")
    eps = rf("  ε, км²/с²: ")

    r = aero.solve_case("5", h=h, eps=eps)
    if "error" in r:
        logger.warning(f"  {r['error']}")
        return

    print(f"\\n  Шаг 1: a = {r['a']:.3f} км")
    print(f"  Шаг 2: p = {r['p']:.3f} км")
    print(f"  Шаг 3: e = {r['e']:.6f}")
    _print_orbit_result(r["a"], r["e"])
''',

    "_solve_h_a": '''def _solve_h_a() -> None:
    """7: известны h и a."""
    print("\\n  СЛУЧАЙ 7: h и a\\n")
    print("  p = h²/μ,  e = √(1 − p/a)\\n")

    h = rf("  h, км²/с: ")
    a = rf("  a, км: ")

    r = aero.solve_case("7", h=h, a=a)
    if "error" in r:
        logger.warning(f"  {r['error']}")
        return

    print(f"\\n  Шаг 1: p = {r['p']:.3f} км")
    print(f"  Шаг 2: e = {r['e']:.6f}")
    _print_orbit_result(r["a"], r["e"])
''',

    "_solve_ra_e": '''def _solve_ra_e() -> None:
    """9: известны H_a и e."""
    print("\\n  СЛУЧАЙ 9: H_a и e\\n")
    print("  a = r_a/(1 + e),  r_p = a·(1 − e),  p = a·(1 − e²)")
    print("  h = √(μp),  ε = −μ/(2a),  T = 2π√(a³/μ)\\n")

    H_a = rf("  H_a, км: ")
    e = rf("  e (0 ≤ e < 1): ")

    r = aero.solve_case("9", H_a=H_a, e=e)
    if "error" in r:
        logger.warning(f"  {r['error']}")
        return

    r_a = H_a + R_EARTH
    print(f"\\n  Шаг 0: r_a = {H_a:.3f} + {R_EARTH:.3f} = {r_a:.3f} км")
    print(f"  Шаг 1: a = r_a/(1 + e) = {r_a:.3f}/(1 + {e:.6f}) = {r['a']:.3f} км")
    print(f"  Шаг 2: r_p = a·(1 − e) = {r['a']:.3f}·(1 − {e:.6f}) = {r['r_p']:.3f} км")
    print(f"  Шаг 3: p = {r['p']:.3f} км")
    print(f"  Шаг 4: h = {r['h']:.4f} км²/с")
    print(f"  Шаг 5: ε = {r['eps']:.4f} км²/с²")
    _print_orbit_result(r["a"], r["e"])
''',

    "_solve_vp_va": '''def _solve_vp_va() -> None:
    """11: известны v_p и v_a."""
    print("\\n  СЛУЧАЙ 11: v_p и v_a\\n")
    print("  v_p/v_a = (1+e)/(1−e)  ⟹  e = (v_p − v_a)/(v_p + v_a)")
    print("  a = μ/(v_p·v_a),  p = a·(1 − e²)\\n")

    v_p = rf("  v_p, км/с: ")
    v_a = rf("  v_a, км/с: ")

    r = aero.solve_case("11", v_p=v_p, v_a=v_a)
    if "error" in r:
        logger.warning(f"  {r['error']}")
        return

    print(f"\\n  Шаг 1: e = ({v_p:.4f} − {v_a:.4f})/({v_p:.4f} + {v_a:.4f}) = {r['e']:.6f}")
    print(f"  Шаг 2: a = {MU_EARTH:.4f}/({v_p:.4f}·{v_a:.4f}) = {r['a']:.3f} км")
    print(f"  Шаг 3: p = {r['a']:.3f}·(1 − {r['e'] * r['e']:.6f}) = {r['p']:.3f} км")
    print(f"  Проверка: r_p = {r['r_p']:.3f} км,  r_a = {r['r_a']:.3f} км")
    print(f"           h = r_p·v_p = {r['r_p'] * v_p:.4f} = r_a·v_a = {r['r_a'] * v_a:.4f}")
    _print_orbit_result(r["a"], r["e"])
''',

    "_solve_h_e": '''def _solve_h_e() -> None:
    """12: известны h и e."""
    print("\\n  СЛУЧАЙ 12: h и e\\n")
    print("  p = h²/μ,  a = p/(1 − e²)")
    print("  r_p = p/(1 + e),  r_a = p/(1 − e)\\n")

    h = rf("  h, км²/с: ")
    e = rf("  e (0 ≤ e < 1): ")

    r = aero.solve_case("12", h=h, e=e)
    if "error" in r:
        logger.warning(f"  {r['error']}")
        return

    print(f"\\n  Шаг 1: p = {h:.4f}²/{MU_EARTH:.4f} = {r['p']:.3f} км")
    print(f"  Шаг 2: a = {r['p']:.3f}/(1 − {e * e:.6f}) = {r['a']:.3f} км")
    print(f"  Шаг 3: r_p = {r['r_p']:.3f} км,  r_a = {r['r_a']:.3f} км")
    _print_orbit_result(r["a"], r["e"])
''',

    "_solve_p_e": '''def _solve_p_e() -> None:
    """13: известны p и e."""
    print("\\n  СЛУЧАЙ 13: p и e\\n")
    print("  a = p/(1 − e²),  h = √(μp)")
    print("  r_p = p/(1 + e),  r_a = p/(1 − e)\\n")

    p_in = rf("  p, км: ")
    e = rf("  e (0 ≤ e < 1): ")

    r = aero.solve_case("13", p=p_in, e=e)
    if "error" in r:
        logger.warning(f"  {r['error']}")
        return

    print(f"\\n  Шаг 1: a = {p_in:.3f}/(1 − {e * e:.6f}) = {r['a']:.3f} км")
    print(f"  Шаг 2: h = √({MU_EARTH:.4f}·{p_in:.3f}) = {r['h']:.4f} км²/с")
    print(f"  Шаг 3: r_p = {r['r_p']:.3f} км,  r_a = {r['r_a']:.3f} км")
    _print_orbit_result(r["a"], r["e"])
''',

    "_solve_rp_h": '''def _solve_rp_h() -> None:
    """15: известны H_p и h."""
    print("\\n  СЛУЧАЙ 15: H_p и h\\n")
    print("  p = h²/μ,  r_p = p/(1+e)  ⟹  e = p/r_p − 1")
    print("  a = p/(1 − e²)\\n")

    H_p = rf("  H_p, км: ")
    h = rf("  h, км²/с: ")

    r = aero.solve_case("15", H_p=H_p, h=h)
    if "error" in r:
        logger.warning(f"  {r['error']}")
        return

    r_p = H_p + R_EARTH
    print(f"\\n  Шаг 0: r_p = {H_p:.3f} + {R_EARTH:.3f} = {r_p:.3f} км")
    print(f"  Шаг 1: p = {h:.4f}²/{MU_EARTH:.4f} = {r['p']:.3f} км")
    print(f"  Шаг 2: e = p/r_p − 1 = {r['p']:.3f}/{r_p:.3f} − 1 = {r['e']:.6f}")
    print(f"  Шаг 3: a = p/(1 − e²) = {r['a']:.3f} км")
    _print_orbit_result(r["a"], r["e"])
''',

    "_solve_ra_h": '''def _solve_ra_h() -> None:
    """16: известны H_a и h."""
    print("\\n  СЛУЧАЙ 16: H_a и h\\n")
    print("  p = h²/μ,  r_a = p/(1−e)  ⟹  e = 1 − p/r_a")
    print("  a = p/(1 − e²)\\n")

    H_a = rf("  H_a, км: ")
    h = rf("  h, км²/с: ")

    r = aero.solve_case("16", H_a=H_a, h=h)
    if "error" in r:
        logger.warning(f"  {r['error']}")
        return

    r_a = H_a + R_EARTH
    print(f"\\n  Шаг 0: r_a = {H_a:.3f} + {R_EARTH:.3f} = {r_a:.3f} км")
    print(f"  Шаг 1: p = {h:.4f}²/{MU_EARTH:.4f} = {r['p']:.3f} км")
    print(f"  Шаг 2: e = 1 − p/r_a = 1 − {r['p']:.3f}/{r_a:.3f} = {r['e']:.6f}")
    print(f"  Шаг 3: a = p/(1 − e²) = {r['a']:.3f} км")
    _print_orbit_result(r["a"], r["e"])
''',

    "_solve_a_rp": '''def _solve_a_rp() -> None:
    """17: известны a и H_p."""
    print("\\n  СЛУЧАЙ 17: a и H_p\\n")
    print("  e = 1 − r_p/a,  r_a = a·(1 + e) = 2a − r_p\\n")

    a = rf("  a, км: ")
    H_p = rf("  H_p, км: ")

    r = aero.solve_case("17", a=a, H_p=H_p)
    if "error" in r:
        logger.warning(f"  {r['error']}")
        return

    r_p = H_p + R_EARTH
    print(f"\\n  Шаг 0: r_p = {r_p:.3f} км")
    print(f"  Шаг 1: e = 1 − {r_p:.3f}/{a:.3f} = {r['e']:.6f}")
    print(f"  Шаг 2: r_a = 2a − r_p = {2 * a - r_p:.3f} км")
    _print_orbit_result(r["a"], r["e"])
''',

    "_solve_a_ra": '''def _solve_a_ra() -> None:
    """18: известны a и H_a."""
    print("\\n  СЛУЧАЙ 18: a и H_a\\n")
    print("  e = r_a/a − 1,  r_p = a·(1 − e) = 2a − r_a\\n")

    a = rf("  a, км: ")
    H_a = rf("  H_a, км: ")

    r = aero.solve_case("18", a=a, H_a=H_a)
    if "error" in r:
        logger.warning(f"  {r['error']}")
        return

    r_a = H_a + R_EARTH
    print(f"\\n  Шаг 0: r_a = {r_a:.3f} км")
    print(f"  Шаг 1: e = {r_a:.3f}/{a:.3f} − 1 = {r['e']:.6f}")
    print(f"  Шаг 2: r_p = 2a − r_a = {2 * a - r_a:.3f} км")
    _print_orbit_result(r["a"], r["e"])
''',

    "_solve_e_vp": '''def _solve_e_vp() -> None:
    """21: известны e и v_p."""
    print("\\n  СЛУЧАЙ 21: e и v_p\\n")
    print("  v_p² = μ(1+e)/r_p  ⟹  r_p = μ(1+e)/v_p²")
    print("  a = r_p/(1 − e)\\n")

    e = rf("  e (0 ≤ e < 1): ")
    v_p = rf("  v_p, км/с: ")

    r = aero.solve_case("21", e=e, v_p=v_p)
    if "error" in r:
        logger.warning(f"  {r['error']}")
        return

    print(f"\\n  Шаг 1: r_p = {MU_EARTH:.4f}·(1+{e:.6f})/{v_p:.4f}² = {r['r_p']:.3f} км")
    print(f"  Шаг 2: a = {r['r_p']:.3f}/(1 − {e:.6f}) = {r['a']:.3f} км")
    _print_orbit_result(r["a"], r["e"])
''',

    "_solve_e_va": '''def _solve_e_va() -> None:
    """22: известны e и v_a."""
    print("\\n  СЛУЧАЙ 22: e и v_a\\n")
    print("  v_a² = μ(1−e)/r_a  ⟹  r_a = μ(1−e)/v_a²")
    print("  a = r_a/(1 + e)\\n")

    e = rf("  e (0 ≤ e < 1): ")
    v_a = rf("  v_a, км/с: ")

    r = aero.solve_case("22", e=e, v_a=v_a)
    if "error" in r:
        logger.warning(f"  {r['error']}")
        return

    print(f"\\n  Шаг 1: r_a = {MU_EARTH:.4f}·(1−{e:.6f})/{v_a:.4f}² = {r['r_a']:.3f} км")
    print(f"  Шаг 2: a = {r['r_a']:.3f}/(1 + {e:.6f}) = {r['a']:.3f} км")
    _print_orbit_result(r["a"], r["e"])
''',

    "_solve_rp_va": '''def _solve_rp_va() -> None:
    """23: известны H_p и v_a."""
    print("\\n  СЛУЧАЙ 23: H_p и v_a\\n")
    print("  Из v_a² = μ·r_p/(a(2a − r_p)):")
    print("    2a²·v_a² − r_p·v_a²·a − μ·r_p = 0")
    print("  a = (r_p·v_a² + √(r_p²v_a⁴ + 8μr_pv_a²))/(4v_a²)")
    print("  e = 1 − r_p/a\\n")

    H_p = rf("  H_p, км: ")
    v_a = rf("  v_a, км/с: ")

    r = aero.solve_case("23", H_p=H_p, v_a=v_a)
    if "error" in r:
        logger.warning(f"  {r['error']}")
        return

    r_p = H_p + R_EARTH
    print(f"\\n  Шаг 0: r_p = {r_p:.3f} км")
    print(f"  Шаг 1: v_a² = {v_a * v_a:.6f}")
    print(f"  Шаг 3: a = {r['a']:.3f} км")
    print(f"  Шаг 4: e = 1 − {r_p:.3f}/{r['a']:.3f} = {r['e']:.6f}")
    _print_orbit_result(r["a"], r["e"])
''',

    "_solve_ra_vp": '''def _solve_ra_vp() -> None:
    """24: известны H_a и v_p."""
    print("\\n  СЛУЧАЙ 24: H_a и v_p\\n")
    print("  Из v_p² = μ·r_a/(a(2a − r_a)):")
    print("    2a²·v_p² − r_a·v_p²·a − μ·r_a = 0")
    print("  a = (r_a·v_p² + √(r_a²v_p⁴ + 8μr_av_p²))/(4v_p²)")
    print("  e = r_a/a − 1\\n")

    H_a = rf("  H_a, км: ")
    v_p = rf("  v_p, км/с: ")

    r = aero.solve_case("24", H_a=H_a, v_p=v_p)
    if "error" in r:
        logger.warning(f"  {r['error']}")
        return

    r_a = H_a + R_EARTH
    print(f"\\n  Шаг 0: r_a = {r_a:.3f} км")
    print(f"  Шаг 1: v_p² = {v_p * v_p:.6f}")
    print(f"  Шаг 3: a = {r['a']:.3f} км")
    print(f"  Шаг 4: e = {r_a:.3f}/{r['a']:.3f} − 1 = {r['e']:.6f}")
    _print_orbit_result(r["a"], r["e"])
''',
}


NEW_TEST = '''

def test_simplified_use_aero():
    """v4b: 17 простейших _solve_* делегируют в aero.solve_case."""
    import inspect
    from cli import calculator as calc
    names = [
        "_solve_a_e", "_solve_rp_ra", "_solve_rp_e", "_solve_h_eps",
        "_solve_h_a", "_solve_ra_e", "_solve_vp_va", "_solve_h_e",
        "_solve_p_e", "_solve_rp_h", "_solve_ra_h", "_solve_a_rp",
        "_solve_a_ra", "_solve_e_vp", "_solve_e_va", "_solve_rp_va",
        "_solve_ra_vp",
    ]
    for name in names:
        fn = getattr(calc, name)
        src = inspect.getsource(fn)
        assert "aero.solve_case" in src, f"{name} не использует aero.solve_case"
        # Inline-формулы не должны остаться:
        assert "math.sqrt(MU_EARTH" not in src, f"{name} ещё содержит inline-формулы"
'''


# ═══════════════════════════════════════════════════════════════════════════
#  Применение
# ═══════════════════════════════════════════════════════════════════════════


def _find_function_range(text: str, func_name: str) -> tuple[int, int] | None:
    """Возвращает (start, end) для функции по маркеру и следующей в ALL_FUNCS_ORDER."""
    start_marker = f"def {func_name}() -> None:"
    i = text.find(start_marker)
    if i < 0:
        return None
    try:
        idx = ALL_FUNCS_ORDER.index(func_name)
    except ValueError:
        return None
    if idx + 1 >= len(ALL_FUNCS_ORDER):
        return None
    next_name = ALL_FUNCS_ORDER[idx + 1]
    next_marker = f"def {next_name}() -> None:"
    j = text.find(next_marker, i + len(start_marker))
    if j < 0:
        return None
    return i, j


def patch_calc() -> int:
    print(f"\n[1] {CALC}")
    if not CALC.is_file():
        print(f"  [err] не найден", file=sys.stderr)
        return 1

    text = CALC.read_text(encoding="utf-8")

    # Проверка: уже пропатчено?
    sample_src = NEW_FUNCTIONS["_solve_a_e"].splitlines()[1]
    if 'aero.solve_case("1", a=a, e=e)' in text:
        print("  [skip] v4b уже применён (все 17 тел)")
        return 0

    backup = CALC.with_suffix(".py.v4b.bak")
    if not backup.exists():
        shutil.copy2(CALC, backup)
        print(f"  [backup] {backup}")

    patched = 0
    for func_name in ALL_FUNCS_ORDER:
        if func_name not in NEW_FUNCTIONS:
            continue

        new_body = NEW_FUNCTIONS[func_name]
        if f"def {func_name}() -> None:" in text and "aero.solve_case" in text[
            text.find(f"def {func_name}() -> None:"):
            text.find(f"def {func_name}() -> None:") + 2000
        ]:
            print(f"  [skip] {func_name} — уже с aero.solve_case")
            continue

        rng = _find_function_range(text, func_name)
        if rng is None:
            print(f"  [err] не удалось найти диапазон для {func_name}", file=sys.stderr)
            return 2

        s, e = rng
        old_body = text[s:e]
        if "aero.solve_case" in old_body:
            print(f"  [skip] {func_name} — уже пропатчено")
            continue

        # Проверка: старая функция должна содержать _print_orbit_result
        if "_print_orbit_result" not in old_body:
            print(f"  [warn] {func_name}: нет _print_orbit_result — пропускаю",
                  file=sys.stderr)
            continue

        new_text = text[:s] + new_body + "\n\n" + text[e:]
        text = new_text
        print(f"  [ok]   {func_name}")
        patched += 1

    if patched == 0:
        print("  [skip] ничего не изменено")
        return 0

    try:
        compile(text, str(CALC), "exec")
    except SyntaxError as exc:
        print(f"  [err] SyntaxError после правок: {exc}", file=sys.stderr)
        return 3

    CALC.write_text(text, encoding="utf-8")
    print(f"  [written] {len(text)} байт ({patched} функций заменено)")
    return 0


def patch_tests() -> int:
    print(f"\n[2] {TESTS}")
    if not TESTS.is_file():
        print(f"  [err] не найден", file=sys.stderr)
        return 1

    text = TESTS.read_text(encoding="utf-8")
    if "test_simplified_use_aero" in text:
        print("  [skip] тест уже есть")
        return 0

    backup = TESTS.with_suffix(".py.v4b.bak")
    if not backup.exists():
        shutil.copy2(TESTS, backup)

    TESTS.write_text(text.rstrip() + "\n" + NEW_TEST, encoding="utf-8")
    try:
        compile(TESTS.read_text(encoding="utf-8"), str(TESTS), "exec")
    except SyntaxError as exc:
        print(f"  [err] SyntaxError в TESTS: {exc}", file=sys.stderr)
        return 3
    print("  [ok]   test_simplified_use_aero добавлен")
    return 0


def verify() -> int:
    import subprocess
    code = (
        "import sys; sys.path.insert(0, '.'); "
        "import inspect; "
        "from cli import calculator as calc; "
        "names = ['_solve_a_e', '_solve_rp_ra', '_solve_rp_e', "
        "'_solve_h_eps', '_solve_h_a', '_solve_ra_e', '_solve_vp_va', "
        "'_solve_h_e', '_solve_p_e', '_solve_rp_h', '_solve_ra_h', "
        "'_solve_a_rp', '_solve_a_ra', '_solve_e_vp', '_solve_e_va', "
        "'_solve_rp_va', '_solve_ra_vp']; "
        "bad = [n for n in names if 'aero.solve_case' not in inspect.getsource(getattr(calc, n))]; "
        "assert not bad, f'не делегируют: {bad}'; "
        "print(f'OK: {len(names)} функций делегируют в aero.solve_case')"
    )
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    if r.returncode == 0:
        print(f"  [ok] {r.stdout.strip()}")
        return 0
    print(f"  [err] {r.stderr.strip()}", file=sys.stderr)
    return 4


def main() -> int:
    print("[patch v4b] Рефакторинг 17 простейших _solve_* через aero.solve_case")
    print("=" * 50)

    rc = patch_calc()
    if rc != 0:
        print("\n[patch v4b] Правки не применены — файл не изменён", file=sys.stderr)
        return rc

    rc = patch_tests()
    if rc != 0:
        return rc

    print("\n[verify] делегирование")
    rc = verify()
    if rc != 0:
        return rc

    print("\n" + "=" * 50)
    print("[patch v4b] Готово. Проверьте:")
    print("  pytest tests/ -v                              # 96 passed")
    print("  python3 cli/calculator.py --solve=1 --verbose # shadow verify молчит")
    print("  python3 cli/calculator.py --solve=11 --verbose")
    return 0


if __name__ == "__main__":
    sys.exit(main())