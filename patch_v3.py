#!/usr/bin/env python3
"""patch_v3.py — итерация v3: --latex + пункты 47-53 + импорт core/astrodynamics.

Идемпотентен. Перед изменениями делает резервную копию.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

TARGET = Path("cli/calculator.py")
ASTRO = Path("core/astrodynamics.py")
LATEX = Path("core/latex_formulas.py")


# ── 1. Imports ─────────────────────────────────────────────────────────────
PATCH_IMPORTS = (
    "from core.optimization import phasing_orbit\n",
    "from core.optimization import phasing_orbit\n"
    "from core import astrodynamics as aero\n"
    "from core.latex_formulas import get_formulas as _latex_get\n",
)

# ── 2. --latex global + helper + dispatcher ────────────────────────────────
PATCH_DISPATCH_HELPER = (
    "def calc_solve() -> None:\n",
    '''_SHOW_LATEX = False


def _print_latex(sid: str) -> None:
    """Печатает LaTeX-формулы перед расчётом."""
    if not _SHOW_LATEX:
        return
    formulas = _latex_get(sid)
    if not formulas:
        return
    print(f"\\n  {_c('LaTeX:', 'b')}")
    for f in formulas:
        print(f"    ${f}$")


def _dispatch_solve(sid: str) -> None:
    """Единая точка входа: LaTeX (если включён) + расчёт."""
    _print_latex(sid)
    _DISPATCH[sid]()


def calc_solve() -> None:
''',
)

# ── 3. Новые _solve_* (47-53) — перед _DISPATCH ─────────────────────────────
NEW_SOLVERS = r'''
# ═══════════════════════════════════════════════════════════════════════════
#  --solve: ИТЕРАЦИЯ v3 (47–53)
# ═══════════════════════════════════════════════════════════════════════════


def _solve_j2_precession() -> None:
    """47: J2-прецессия узла, перигея и среднего движения."""
    print("\n  СЛУЧАЙ 47: J2-прецессия\n")
    print("  dΩ/dt  = −(3/2)·J2·n·(R/p)²·cos i")
    print("  dω/dt  = (3/4)·J2·n·(R/p)²·(5cos²i − 1)")
    print("  dM₀/dt = (3/4)·J2·n·(R/p)²·√(1−e²)·(3cos²i − 1)\n")

    H = rf("  H, км: ")
    e = rf("  e (0 ≤ e < 1): ")
    i_deg = rf("  i, °: ")
    a = H + R_EARTH
    try:
        r = aero.j2_precession(a, e, i_deg)
    except ValueError as exc:
        logger.warning(f"  {exc}")
        return

    print(f"\n  Шаг 0: a = {H:.3f} + {R_EARTH:.3f} = {a:.3f} км")
    print(f"  Шаг 1: n = √(μ/a³) = {r['n']:.8f} рад/с,  T = {r['T']:.2f} с = {r['T']/60:.4f} мин")
    print(f"  Шаг 2: p = a(1−e²) = {r['p']:.3f} км")
    print(f"  Шаг 3: base = (3/4)·J2·n·(R/p)² = {0.75 * aero.J2 * r['n'] * (aero.R_EARTH/r['p'])**2:.6e} рад/с")
    print(f"  Шаг 4: dΩ/dt = {r['dOmega_deg_day']:+.6f}°/сут = {r['dOmega_deg_year']:+.4f}°/год")
    print(f"  Шаг 5: dω/dt = {r['domega_deg_day']:+.6f}°/сут = {r['domega_deg_year']:+.4f}°/год")
    print(f"  Шаг 6: dM₀/dt = {r['dM_deg_day']:+.6f}°/сут = {r['dM_deg_year']:+.4f}°/год")
    print(f"\n  За год узел смещается на {r['dOmega_deg_year']:+.2f}°")
    print(f"  Перигей за год: {r['domega_deg_year']:+.2f}°\n")


def _solve_radar() -> None:
    """48: оценка орбиты по измерениям радиолокатора."""
    print("\n  СЛУЧАЙ 48: Радиолокатор\n")
    print("  Дано: наклонная дальность ρ, радиальная скорость ρ̇, угол места el.")
    print("  Находим r (геометрия), даём оценки v_esc, v_circ.")
    print("  Полный вектор v требует ещё азимута или доплеровских данных.\n")

    rho = rf("  ρ (наклонная дальность), км: ")
    rho_dot = rf("  ρ̇ (радиальная скорость), км/с: ")
    el_deg = rf("  el (угол места), °: ")
    station_alt = rf("  Высота станции, км [0]: ") if input("  Указать высоту станции? [n]: ").strip().lower() == "y" else 0.0

    try:
        r = aero.radar_track(rho, rho_dot, el_deg, station_alt)
    except ValueError as exc:
        logger.warning(f"  {exc}")
        return

    print(f"\n  Шаг 0: r_st = {r['station_radius_km']:.3f} км")
    print(f"  Шаг 1: r² = r_st² + ρ² + 2·r_st·ρ·sin(el)")
    print(f"  Шаг 2: r = {r['r_km']:.3f} км  (H = {r['H_km']:+.3f} км)")
    print(f"  Шаг 3: v_esc(r) = {r['v_esc_local_km_s']:.4f} км/с")
    print(f"  Шаг 4: v_circ(r) = {r['v_circ_local_km_s']:.4f} км/с")
    print(f"\n  {r['note']}\n")


def _solve_budget_ascent() -> None:
    """49: бюджет выведения на орбиту."""
    print("\n  СЛУЧАЙ 49: Бюджет выведения на орбиту\n")
    print("  Δv_circ = √(μ/(R⊕+H)) − v_rot(φ)")
    print("  Δv_total = Δv_circ + Δv_grav + Δv_drag\n")
    print("  (Δv_grav ≈ 1.2 км/с, Δv_drag ≈ 0.15 км/с для LEO)\n")

    H = rf("  Целевая высота H, км: ")
    isp = rf("  Isp, с: ")
    m0 = rf("  Стартовая масса m0, кг: ")
    lat = rf("  Широта старта, ° [0]: ") if input("  Широта старта ≠ 0? [n]: ").strip().lower() == "y" else 0.0

    try:
        r = aero.ascent_budget(H, isp, m0, lat)
    except ValueError as exc:
        logger.warning(f"  {exc}")
        return

    print(f"\n  Шаг 0: r_target = {r['r_target_km']:.3f} км")
    print(f"  Шаг 1: v_orbit = {r['v_orbit_km_s']:.4f} км/с")
    print(f"  Шаг 2: v_rot(φ={lat:.1f}°) = {r['v_rot_km_s']:.4f} км/с")
    print(f"  Шаг 3: Δv_circ = {r['dv_circ_km_s']:.4f} км/с")
    print(f"  Шаг 4: + гравитационные потери = {r['gravity_loss_km_s']:.4f} км/с")
    print(f"  Шаг 5: + аэродинамические = {r['drag_loss_km_s']:.4f} км/с")
    print(f"  Шаг 6: Δv_total = {r['dv_total_km_s']:.4f} км/с = {r['dv_total_mps']:.1f} м/с")
    print(f"  Шаг 7: m_fuel = {r['m_fuel_kg']:.1f} кг ({r['fuel_fraction']*100:.2f}%)\n")


def _solve_payload_max() -> None:
    """50: максимальная полезная нагрузка."""
    print("\n  СЛУЧАЙ 50: Максимальная полезная нагрузка\n")
    print("  m_payload = m0 − m_fuel − m_dry")
    print("  m_fuel = m0(1 − e^(−Δv/ve))\n")

    dv = rf("  Δv, м/с: ")
    isp = rf("  Isp, с: ")
    m0 = rf("  Стартовая масса m0, кг: ")
    m_dry = rf("  Сухая масса (конструкция), кг: ")

    try:
        r = aero.max_payload(dv, isp, m0, m_dry)
    except ValueError as exc:
        logger.warning(f"  {exc}")
        return

    print(f"\n  Шаг 1: v_e = Isp·g0 = {r['ve_mps']:.2f} м/с")
    print(f"  Шаг 2: m_fuel = {r['m_fuel_kg']:.3f} кг")
    print(f"  Шаг 3: m_final = {r['m_final_kg']:.3f} кг")
    print(f"  Шаг 4: m_payload = m0 − m_fuel − m_dry = {r['m_payload_kg']:.3f} кг")
    status = "✓ возможно" if r["feasible"] else "✗ невозможно (payload < 0)"
    print(f"\n  Полезная нагрузка: {status}\n")


def _solve_staged_rocket() -> None:
    """51: ступенчатая ракета."""
    print("\n  СЛУЧАЙ 51: Ступенчатая ракета\n")
    print("  m_pl/m0 = [e^(−Δv_i/(Isp·g0)) − ε]^N")
    print("  Δv_i = Δv_total / N\n")

    dv_total = rf("  Δv_total, м/с: ")
    isp = rf("  Isp, с: ")
    epsilon = rf("  ε (доля конструкции) [0.08]: ")
    if epsilon <= 0 or epsilon >= 1:
        epsilon = 0.08

    results = aero.best_staging(dv_total, isp, epsilon, max_stages=5)
    if not results:
        logger.warning("  При таких параметрах ракета невозможна")
        return

    print(f"\n  {'N':>2}  {'Δv/ст':>10}  {'m_pl/m0':>10}  {'масса_ступ':>12}")
    print(f"  {'-'*2}  {'-'*10}  {'-'*10}  {'-'*12}")
    best = None
    for r in results:
        print(f"  {r['n_stages']:>2}  {r['dv_per_stage_mps']:>10.1f}  "
              f"{r['payload_ratio']:>10.4f}  {r['structural_ratio_total']:>12.4f}")
        if best is None or r["payload_ratio"] > best["payload_ratio"]:
            best = r

    print(f"\n  Оптимум: N = {best['n_stages']} ступеней")
    print(f"  Полезная нагрузка: {best['payload_ratio']*100:.3f}% от m0\n")


def _solve_cr3bp_lagrange() -> None:
    """52: точные L1/L2/L3 через CR3BP."""
    print("\n  СЛУЧАЙ 52: Точные L1/L2/L3 (CR3BP, Ньютон)\n")
    print("  x − (1−μ)(x+μ)/r₁³ − μ(x−1+μ)/r₂³ = 0\n")

    print("  Система:")
    print("    1. Земля — Солнце")
    print("    2. Земля — Луна")
    print("    3. Марс — Солнце")
    choice = input("  Выбор [1]: ").strip() or "1"

    if choice == "1":
        big_a, m, M, name = aero.AU_KM, aero.M_EARTH, aero.M_SUN, "Земля — Солнце"
    elif choice == "2":
        big_a, m, M, name = aero.A_MOON_KM, aero.M_MOON, aero.M_EARTH, "Земля — Луна"
    elif choice == "3":
        big_a, m, M, name = aero.A_MARS_AU * aero.AU_KM, aero.M_MARS, aero.M_SUN, "Марс — Солнце"
    else:
        logger.warning("  Неверный выбор")
        return

    mu = m / (m + M)
    print(f"\n  {name}:  μ = {mu:.6e},  a = {big_a:.3e} км")
    print(f"  (приближение (μ/3)^(1/3) = {(mu/3)**(1/3):.6e})")

    for pt in ("L1", "L2", "L3"):
        try:
            r = aero.lagrange_distance_km(mu, big_a, pt)
        except ValueError as exc:
            logger.warning(f"  {pt}: {exc}")
            continue
        print(f"\n  {pt}:  x_L = {r['x_L_normalized']:.8f}")
        print(f"       от малого тела: {r['dist_from_small_km']:.3e} км")
        print(f"       от большого:    {r['dist_from_big_km']:.3e} км")


def _solve_frozen_orbit() -> None:
    """53: замороженная орбита и критическое наклонение."""
    print("\n  СЛУЧАЙ 53: Замороженная орбита / критическое наклонение\n")
    print(f"  i_crit = arccos(1/√5) = {aero.CRITICAL_INC_DEG:.4f}°")
    print("  При i = i_crit:  dω/dt = 0 (перигей не прецессирует)\n")

    H = rf("  H, км: ")
    e = rf("  e [0.001]: ")
    if e <= 0:
        e = 0.001
    i_deg = rf("  i, °: ")
    a = H + R_EARTH

    try:
        r = aero.frozen_orbit_info(a, e, i_deg)
    except ValueError as exc:
        logger.warning(f"  {exc}")
        return

    print(f"\n  Шаг 0: a = {a:.3f} км")
    print(f"  Шаг 1: i_crit = {r['critical_inc_deg']:.4f}°")
    print(f"  Шаг 2: Δi = i − i_crit = {r['deviation_deg']:+.4f}°")
    print(f"  Шаг 3: dω/dt = {r['domega_deg_day']:+.6f}°/сут")
    print(f"  Шаг 4: dΩ/dt = {r['dOmega_deg_day']:+.6f}°/сут")
    print(f"\n  Близко к критическому: {'да' if r['is_near_critical'] else 'нет'}")
    print(f"  Замороженная (e<0.01 и i≈i_crit): {'да' if r['is_frozen_like'] else 'нет'}\n")
'''

# ── 4. _DISPATCH: добавить 47-53 ───────────────────────────────────────────
PATCH_DISPATCH = (
    '    "46": _solve_state_vector,\n}',
    '''    "46": _solve_state_vector,
    "47": _solve_j2_precession,
    "48": _solve_radar,
    "49": _solve_budget_ascent,
    "50": _solve_payload_max,
    "51": _solve_staged_rocket,
    "52": _solve_cr3bp_lagrange,
    "53": _solve_frozen_orbit,
}''',
)

# ── 5. Меню calc_solve: добавить 47-53 ────────────────────────────────────
PATCH_MENU = (
    '        print(" 46. Вектор состояния → орбитальные элементы")\n',
    '''        print(" 46. Вектор состояния → орбитальные элементы")
        print("  ── Итерация v3 ──")
        print(" 47. J2-прецессия (a, e, i → dΩ/dt, dω/dt, dM₀/dt)")
        print(" 48. Радиолокатор (ρ, ρ̇, el → r, H, v_esc)")
        print(" 49. Бюджет выведения на орбиту")
        print(" 50. Максимальная полезная нагрузка")
        print(" 51. Ступенчатая ракета (N ступеней)")
        print(" 52. Точные L1/L2/L3 (CR3BP, Ньютон)")
        print(" 53. Замороженная орбита / критическое наклонение")
''',
)

# ── 6. calc_solve: используем _dispatch_solve ─────────────────────────────
PATCH_CALC_DISPATCH = (
    '                _DISPATCH[ch]()',
    '                _dispatch_solve(ch)',
)

# ── 7. main: добавить --latex + использовать _dispatch_solve ───────────────
PATCH_MAIN_ARG = (
    '    p.add_argument("--json", action="store_true",\n'
    '                   help="JSON-вывод (только орбитальные случаи 1-24)")\n',
    '    p.add_argument("--json", action="store_true",\n'
    '                   help="JSON-вывод (только орбитальные случаи 1-24)")\n'
    '    p.add_argument("--latex", action="store_true",\n'
    '                   help="Показывать LaTeX-формулы перед расчётом")\n',
)

PATCH_MAIN_FLAG = (
    '    setup_logging(args.verbose)\n    set_lang(args.lang)\n',
    '    setup_logging(args.verbose)\n    set_lang(args.lang)\n'
    '    global _SHOW_LATEX\n    _SHOW_LATEX = args.latex\n',
)

PATCH_MAIN_DISPATCH = (
    # --preset
    '''            with _input_queue(vals):
                _DISPATCH[str(sid)]()''',
    '''            with _input_queue(vals):
                _dispatch_solve(str(sid))''',
)

PATCH_MAIN_FROM = (
    '''            print(f"\\n  --from → пункт {sid}, значения {vals}\\n")
            with _input_queue(vals):
                _DISPATCH[str(sid)]()''',
    '''            print(f"\\n  --from → пункт {sid}, значения {vals}\\n")
            with _input_queue(vals):
                _dispatch_solve(str(sid))''',
)

PATCH_MAIN_SOLVE_EQ = (
    '        elif args.solve.isdigit() and args.solve in _DISPATCH:\n            _DISPATCH[args.solve]()',
    '        elif args.solve.isdigit() and args.solve in _DISPATCH:\n            _dispatch_solve(args.solve)',
)

PATCH_DEMO = (
    '        with _input_queue(vals):\n            _DISPATCH[str(sid)]()\n    print("\\n  " + "=" * 50 + "\\n  ДЕМО завершено.\\n")',
    '        with _input_queue(vals):\n            _dispatch_solve(str(sid))\n    print("\\n  " + "=" * 50 + "\\n  ДЕМО завершено.\\n")',
)


def _apply(text, old, new, name):
    if new in text and old not in text:
        print(f"  [skip] {name}")
        return text
    if old not in text:
        raise RuntimeError(f"Якорь не найден: {name}: {old[:60]!r}")
    return text.replace(old, new, 1)


def main():
    if not TARGET.is_file():
        print(f"[patch] Не найден {TARGET}", file=sys.stderr)
        return 1

    text = TARGET.read_text(encoding="utf-8")

    if "_solve_j2_precession" in text:
        print("[patch] v3 уже применён. Ничего не меняю.")
    else:
        backup = TARGET.with_suffix(".py.v3.bak")
        shutil.copy2(TARGET, backup)
        print(f"[patch] Резервная копия: {backup}")

        try:
            text = _apply(text, *PATCH_IMPORTS, "imports")
            text = _apply(text, *PATCH_DISPATCH_HELPER, "dispatch helper")
            text = _apply(
                text,
                "_DISPATCH = {",
                NEW_SOLVERS + "\n\n_DISPATCH = {",
                "new solvers 47-53",
            )
            text = _apply(text, *PATCH_DISPATCH, "dispatch registry")
            text = _apply(text, *PATCH_MENU, "menu items")
            text = _apply(text, *PATCH_CALC_DISPATCH, "calc_solve → _dispatch_solve")
            text = _apply(text, *PATCH_MAIN_ARG, "main --latex")
            text = _apply(text, *PATCH_MAIN_FLAG, "main flag")
            text = _apply(text, *PATCH_MAIN_DISPATCH, "--preset → dispatch")
            text = _apply(text, *PATCH_MAIN_FROM, "--from → dispatch")
            text = _apply(text, *PATCH_MAIN_SOLVE_EQ, "--solve=N → dispatch")
            text = _apply(text, *PATCH_DEMO, "demo → dispatch")
        except RuntimeError as exc:
            print(f"[patch] ОШИБКА: {exc}", file=sys.stderr)
            return 2

        TARGET.write_text(text, encoding="utf-8")
        print(f"[patch] Обновлён {TARGET}")

    # Проверка существования core-файлов
    for path in (ASTRO, LATEX):
        if path.is_file():
            print(f"[patch] {path} на месте")
        else:
            print(f"[patch] ВНИМАНИЕ: {path} отсутствует — создайте его вручную")

    print("\n[patch] Готово. Проверьте:")
    print("  python cli/calculator.py --solve=47")
    print("  python cli/calculator.py --solve=47 --latex")
    print("  python cli/calculator.py --preset gso --latex")
    print("  pytest tests/ -v")
    return 0


if __name__ == "__main__":
    sys.exit(main())