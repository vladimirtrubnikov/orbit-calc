#!/usr/bin/env python3
"""patch_v4c.py — рефакторинг оставшихся 29 _solve_* через aero.solve_case.

Список: 4, 6, 8, 10, 14, 19, 20, 25, 26, 27, 28, 29, 30, 31, 32, 33,
        34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46 (29 функций).

47–53 уже делегируют в aero (не через solve_case) — не трогаем.

Идемпотентен. Резервные копии: *.py.v4c.bak
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

CALC = Path("cli/calculator.py")
ASTRO = Path("core/astrodynamics.py")
TESTS = Path("tests/test_v4.py")


# ═══════════════════════════════════════════════════════════════════════════
#  CORE: расширение _s26 и _s27
# ═══════════════════════════════════════════════════════════════════════════

S26_OLD = '''def _s26(H, dphi, N):
    r_c = H + R_EARTH
    T_circ = 2 * math.pi * math.sqrt(r_c ** 3 / MU_EARTH)
    T_ph = T_circ * (1 - dphi / (360 * N))
    if T_ph <= 0:
        raise ValueError("T_phase ≤ 0")
    a_ph = (MU_EARTH * (T_ph / (2 * math.pi)) ** 2) ** (1 / 3)
    v_circ = math.sqrt(MU_EARTH / r_c)
    v_ph = math.sqrt(MU_EARTH * (2 / r_c - 1 / a_ph))
    burn = abs(v_ph - v_circ)
    return {"T_circ_s": T_circ, "T_phase_s": T_ph, "a_phase_km": a_ph,
            "dv1_mps": burn * 1000, "dv_total_mps": 2 * burn * 1000,
            "n_revs": N}'''

S26_NEW = '''def _s26(H, dphi, N):
    r_c = H + R_EARTH
    T_circ = 2 * math.pi * math.sqrt(r_c ** 3 / MU_EARTH)
    T_ph = T_circ * (1 - dphi / (360 * N))
    if T_ph <= 0:
        raise ValueError("T_phase ≤ 0")
    a_ph = (MU_EARTH * (T_ph / (2 * math.pi)) ** 2) ** (1 / 3)
    v_circ = math.sqrt(MU_EARTH / r_c)
    v_ph = math.sqrt(MU_EARTH * (2 / r_c - 1 / a_ph))
    burn = abs(v_ph - v_circ)
    if a_ph > r_c:
        r_a_ph = 2 * a_ph - r_c
        r_p_ph = r_c
        type_ph = "raise"
    else:
        r_p_ph = 2 * a_ph - r_c
        r_a_ph = r_c
        type_ph = "lower"
    return {
        "r_c_km": r_c,
        "T_circ_s": T_circ, "T_phase_s": T_ph, "a_phase_km": a_ph,
        "v_circ_km_s": v_circ, "v_ph_km_s": v_ph,
        "dv1_mps": burn * 1000, "dv_total_mps": 2 * burn * 1000,
        "n_revs": N,
        "r_p_phase_km": r_p_ph, "r_a_phase_km": r_a_ph,
        "type": type_ph,
    }'''

S27_OLD = '''def _s27(H1, H2, dnu_deg, dt):
    """Ламберт: r1, r2, Δν, Δt → Δv1, Δv2."""
    r1, r2 = H1 + R_EARTH, H2 + R_EARTH
    dnu = math.radians(dnu_deg)
    if not (0 < dnu < 2 * math.pi) or dt <= 0:
        raise ValueError("0 < Δν < 360°, Δt > 0")
    res = lambert_universal(r1, r2, dnu, dt)
    if res is None:
        raise ValueError("Ламберт не сошёлся — проверьте Δν, Δt")
    v1_vec, v2_vec = res
    v1 = math.hypot(*v1_vec)
    v2 = math.hypot(*v2_vec)
    vc1 = math.sqrt(MU_EARTH / r1)
    tang2 = (-math.sin(dnu), math.cos(dnu))
    vc2 = math.sqrt(MU_EARTH / r2)
    dv1 = math.hypot(v1_vec[0], v1_vec[1] - vc1)
    dv2 = math.hypot(vc2 * tang2[0] - v2_vec[0], vc2 * tang2[1] - v2_vec[1])
    return {"dv1_mps": dv1 * 1000, "dv2_mps": dv2 * 1000,
            "dv_total_mps": (dv1 + dv2) * 1000,
            "v1_transfer_km_s": v1, "v2_transfer_km_s": v2}'''

S27_NEW = '''def _s27(H1, H2, dnu_deg, dt):
    """Ламберт: r1, r2, Δν, Δt → Δv1, Δv2."""
    r1, r2 = H1 + R_EARTH, H2 + R_EARTH
    dnu = math.radians(dnu_deg)
    if not (0 < dnu < 2 * math.pi) or dt <= 0:
        raise ValueError("0 < Δν < 360°, Δt > 0")
    res = lambert_universal(r1, r2, dnu, dt)
    if res is None:
        raise ValueError("Ламберт не сошёлся — проверьте Δν, Δt")
    v1_vec, v2_vec = res
    v1 = math.hypot(*v1_vec)
    v2 = math.hypot(*v2_vec)
    vc1 = math.sqrt(MU_EARTH / r1)
    tang2 = (-math.sin(dnu), math.cos(dnu))
    vc2 = math.sqrt(MU_EARTH / r2)
    dv1 = math.hypot(v1_vec[0], v1_vec[1] - vc1)
    dv2 = math.hypot(vc2 * tang2[0] - v2_vec[0], vc2 * tang2[1] - v2_vec[1])
    el = elements_from_state((r1, 0.0), v1_vec)
    return {
        "r1_km": r1, "r2_km": r2,
        "dv1_mps": dv1 * 1000, "dv2_mps": dv2 * 1000,
        "dv_total_mps": (dv1 + dv2) * 1000,
        "v1_km_s": v1, "v2_km_s": v2,
        "v1_x": v1_vec[0], "v1_y": v1_vec[1],
        "v2_x": v2_vec[0], "v2_y": v2_vec[1],
        "a_km": el["a"], "e": el["e"],
        "h_km2_s": el["h"], "eps_km2_s2": el["eps"],
    }'''


# ═══════════════════════════════════════════════════════════════════════════
#  CLI: 29 новых тел
# ═══════════════════════════════════════════════════════════════════════════

NEW_FUNCS = {

"_solve_r_v_gamma": '''def _solve_r_v_gamma() -> None:
    """4: известны H, v, γ."""
    print("\\n  СЛУЧАЙ 4: H, v, γ\\n")
    print("  ε = v²/2 − μ/r,  h = r·v·cos γ,  a = −μ/(2ε)")
    print("  p = h²/μ,  e = √(1 − p/a)\\n")

    H = rf("  H, км: ")
    v = rf("  v, км/с: ")
    g_in = input("  γ, ° [0]: ").strip()
    g = float(g_in.replace(",", ".")) if g_in else 0.0

    r = aero.solve_case("4", H=H, v=v, gamma=g)
    if "error" in r:
        logger.warning(f"  {r['error']}")
        return

    print(f"\\n  Шаг 1: ε = {r['eps']:.6f} км²/с²")
    print(f"  Шаг 2: h = {r['h']:.4f} км²/с")
    print(f"  Шаг 3: a = {r['a']:.3f} км")
    print(f"  Шаг 4: p = {r['p']:.3f} км")
    print(f"  Шаг 5: e = {r['e']:.6f}")
    _print_orbit_result(r["a"], r["e"])
''',

"_solve_rp_vp": '''def _solve_rp_vp() -> None:
    """6: известны H_p и v_p (эллипс/парабола/гипербола)."""
    print("\\n  СЛУЧАЙ 6: H_p и v_p\\n")
    print("  ε = v_p²/2 − μ/r_p,  p = (r_p·v_p)²/μ,  a = −μ/(2ε)")
    print("  (ε < 0 — эллипс,  ε = 0 — парабола,  ε > 0 — гипербола)\\n")

    H_p = rf("  H_p, км: ")
    v_p = rf("  v_p, км/с: ")

    r = aero.solve_case("6", H_p=H_p, v_p=v_p)
    if "error" in r:
        logger.warning(f"  {r['error']}")
        return

    kind = r.get("kind")
    if kind == "ellipse":
        print(f"\\n  ε = {r['eps']:.6f} км²/с²")
        print(f"  h = {r['h']:.4f} км²/с,  p = {r['p']:.3f} км")
        print(f"  a = {r['a']:.3f} км,  e = {r['e']:.6f}  (эллипс)")
        _print_orbit_result(r["a"], r["e"])
    elif kind == "parabola":
        print("\\n  ε = 0 → параболическая орбита (e = 1)")
        print(f"  e = 1,  r_p = {r['r_p']:.3f} км,  p = {r['p']:.3f} км")
        print(f"  C3 = 0,  v_p = v_esc = {r['v_p']:.4f} км/с\\n")
    else:
        print(f"\\n  ε > 0 → гипербола (e = {r['e']:.6f})")
        print(f"  a = {r['a']:.3f} км,  e = {r['e']:.6f},  p = {r['p']:.3f} км")
        print(f"  C3 = v_∞² = {r['C3']:.4f} км²/с²,  v_∞ = {r['v_inf']:.4f} км/с")
        print(f"  v_p = {r['v_p']:.4f} км/с,  δ = {r['delta_deg']:.4f}°\\n")
''',

"_solve_T_circular": '''def _solve_T_circular() -> None:
    """8: известен T (круговая)."""
    print("\\n  СЛУЧАЙ 8: T (круговая)\\n")
    print("  a = (μ·T²/(4π²))^(1/3),  r = a,  v = √(μ/r)\\n")

    unit = input("  Единица T — с/мин [с]: ").strip().lower() or "с"
    mult = 60.0 if unit in ("м", "мин", "m", "min") else 1.0
    T_in = rf("  T: ")
    T = T_in * mult

    r = aero.solve_case("8", T=T)
    if "error" in r:
        logger.warning(f"  {r['error']}")
        return

    print(f"\\n  Шаг 1: T = {T:.4f} с")
    print(f"  Шаг 2: a = {r['a']:.3f} км (H = {r['a'] - R_EARTH:+.3f} км)")
    print(f"  Шаг 3: v = {r['v']:.4f} км/с ({r['v'] * 1000:.1f} м/с)")
    print(f"\\n  e = 0,  T = {T / 60:.4f} мин\\n")
''',

"_solve_ra_va": '''def _solve_ra_va() -> None:
    """10: известны H_a и v_a."""
    print("\\n  СЛУЧАЙ 10: H_a и v_a\\n")
    print("  ε = v_a²/2 − μ/r_a,  h = r_a·v_a,  a = −μ/(2ε)\\n")

    H_a = rf("  H_a, км: ")
    v_a = rf("  v_a, км/с: ")

    r = aero.solve_case("10", H_a=H_a, v_a=v_a)
    if "error" in r:
        logger.warning(f"  {r['error']}")
        return

    print(f"\\n  ε = {r['eps']:.6f} км²/с²,  h = {r['h']:.4f} км²/с")
    print(f"  a = {r['a']:.3f} км,  e = {r['e']:.6f}")
    _print_orbit_result(r["a"], r["e"])
''',

"_solve_T_e": '''def _solve_T_e() -> None:
    """14: известны T и e."""
    print("\\n  СЛУЧАЙ 14: T и e\\n")
    print("  a = (μT²/(4π²))^(1/3),  далее по (a, e)\\n")

    unit = input("  Единица T — с/мин [мин]: ").strip().lower() or "мин"
    mult = 60.0 if unit in ("м", "мин", "m", "min") else 1.0
    T_in = rf("  T: ")
    e = rf("  e (0 ≤ e < 1): ")
    T = T_in * mult

    r = aero.solve_case("14", T=T, e=e)
    if "error" in r:
        logger.warning(f"  {r['error']}")
        return

    print(f"\\n  Шаг 1: T = {T:.4f} с")
    print(f"  Шаг 2: a = {r['a']:.3f} км (H_ср = {r['a'] - R_EARTH:+.3f} км)")
    _print_orbit_result(r["a"], r["e"])
''',

"_solve_T_rp": '''def _solve_T_rp() -> None:
    """19: известны T и H_p."""
    print("\\n  СЛУЧАЙ 19: T и H_p\\n")
    print("  a = (μT²/4π²)^(1/3),  e = 1 − r_p/a\\n")

    unit = input("  Единица T — с/мин/ч [мин]: ").strip().lower() or "мин"
    mult = {"с": 1.0, "s": 1.0, "мин": 60.0, "m": 60.0, "min": 60.0,
            "ч": 3600.0, "h": 3600.0}.get(unit, 60.0)
    T_in = rf("  T: ")
    H_p = rf("  H_p, км: ")
    T = T_in * mult

    r = aero.solve_case("19", T=T, H_p=H_p)
    if "error" in r:
        logger.warning(f"  {r['error']}")
        return

    r_p = H_p + R_EARTH
    print(f"\\n  Шаг 1: T = {T:.4f} с")
    print(f"  Шаг 2: a = {r['a']:.3f} км")
    print(f"  Шаг 3: r_p = {r_p:.3f} км")
    print(f"  Шаг 4: e = {r['e']:.6f}")
    _print_orbit_result(r["a"], r["e"])
''',

"_solve_T_vp": '''def _solve_T_vp() -> None:
    """20: известны T и v_p."""
    print("\\n  СЛУЧАЙ 20: T и v_p\\n")
    print("  a = (μT²/4π²)^(1/3),  e = (a·v_p² − μ)/(a·v_p² + μ)\\n")

    unit = input("  Единица T — с/мин/ч [мин]: ").strip().lower() or "мин"
    mult = {"с": 1.0, "s": 1.0, "мин": 60.0, "m": 60.0, "min": 60.0,
            "ч": 3600.0, "h": 3600.0}.get(unit, 60.0)
    T_in = rf("  T: ")
    v_p = rf("  v_p, км/с: ")
    T = T_in * mult

    r = aero.solve_case("20", T=T, v_p=v_p)
    if "error" in r:
        logger.warning(f"  {r['error']}")
        return

    print(f"\\n  Шаг 1: T = {T:.4f} с,  a = {r['a']:.3f} км")
    print(f"  Шаг 2: e = {r['e']:.6f},  r_p = {r['r_p']:.3f} км")
    _print_orbit_result(r["a"], r["e"])
''',

"_solve_hohmann_incl": '''def _solve_hohmann_incl() -> None:
    """25: Хоман + смена наклонения Δi."""
    print("\\n  ПЕРЕЛЁТ ХОМАНА СО СМЕНОЙ НАКЛОНЕНИЯ\\n")
    print("  Вариант A: Δi в 1-м импульсе;  Вариант B: Δi во 2-м\\n")

    h1 = rf("  H1, км: ")
    h2 = rf("  H2, км: ")
    di = rf("  Δi, °: ")

    r = aero.solve_case("25", H1=h1, H2=h2, di=di)
    if "error" in r:
        logger.warning(f"  {r['error']}")
        return

    print(f"\\n  Вариант A: Δv1' = {r['dv1_A_mps']:.2f},  Δv2 = {r['dv2_A_mps']:.2f},  ΣA = {r['total_A_mps']:.2f} м/с")
    print(f"  Вариант B: Δv1 = {r['dv1_B_mps']:.2f},  Δv2' = {r['dv2_B_mps']:.2f},  ΣB = {r['total_B_mps']:.2f} м/с")
    if r["best"] == "A":
        print(f"\\n  => Оптимально: A, экономия {r['total_B_mps'] - r['total_A_mps']:.2f} м/с\\n")
    else:
        print(f"\\n  => Оптимально: B, экономия {r['total_A_mps'] - r['total_B_mps']:.2f} м/с\\n")
''',

"_solve_phasing_full": '''def _solve_phasing_full() -> None:
    """26: фазирующий манёвр."""
    print("\\n  ФАЗИРУЮЩИЙ МАНЁВР\\n")
    print("  T_phase = T_circ·(1 − Δφ/(360·N)),  a_phase = (μ(T_ph/2π)²)^(1/3)\\n")

    H = rf("  H, км: ")
    dphi = rf("  Δφ, ° (положительный — цель впереди): ")
    N = rf("  N (число витков фазовой орбиты): ")

    r = aero.solve_case("26", H=H, dphi=dphi, N=N)
    if "error" in r:
        logger.warning(f"  {r['error']}")
        return

    print(f"\\n  Шаг 0: r_c = {r['r_c_km']:.3f} км")
    print(f"  Шаг 1: T_circ = {r['T_circ_s']:.4f} с")
    print(f"  Шаг 2: T_phase = {r['T_phase_s']:.4f} с")
    print(f"  Шаг 3: a_phase = {r['a_phase_km']:.3f} км")
    print(f"  Шаг 4: v_circ = {r['v_circ_km_s']:.4f},  v_phase = {r['v_ph_km_s']:.4f} км/с")
    print(f"  Шаг 5: |Δv1| = {r['dv1_mps']:.2f} м/с")
    type_str = "поднятие апогея" if r["type"] == "raise" else "опускание перигея"
    print(f"\\n  Тип: {type_str}")
    print(f"  r_p_phase = {r['r_p_phase_km']:.1f} км,  r_a_phase = {r['r_a_phase_km']:.1f} км")
    print(f"  Суммарный Δv = {r['dv_total_mps']:.2f} м/с")
    print(f"  Время: {N:.0f} витков × {r['T_phase_s'] / 60:.4f} мин = {N * r['T_phase_s'] / 60:.2f} мин\\n")
''',

"_solve_lambert": '''def _solve_lambert() -> None:
    """27: Ламберт (r1, r2, Δν, Δt → Δv)."""
    print("\\n  ЛАМБЕРТ (r1, r2, Δν, Δt → Δv)\\n")
    print("  Универсальные переменные, 0 rev, короткий путь (prograde)\\n")

    H1 = rf("  H1 (круговая орбита 1), км: ")
    H2 = rf("  H2 (круговая орбита 2), км: ")
    dnu_deg = rf("  Δν, ° [180]: ")
    dt_unit = input("  Единица Δt — с/мин/ч [ч]: ").strip().lower() or "ч"
    mult = {"с": 1.0, "s": 1.0, "мин": 60.0, "m": 60.0, "min": 60.0,
            "ч": 3600.0, "h": 3600.0}.get(dt_unit, 3600.0)
    dt_in = rf("  Δt: ")
    dt = dt_in * mult

    r = aero.solve_case("27", H1=H1, H2=H2, dnu_deg=dnu_deg, dt=dt)
    if "error" in r:
        logger.warning(f"  {r['error']}")
        return

    print(f"\\n  Шаг 0: r1 = {r['r1_km']:.3f},  r2 = {r['r2_km']:.3f} км,  Δt = {dt:.1f} с")
    print(f"  Шаг 1: v1_transfer = {r['v1_km_s']:.4f},  v2_transfer = {r['v2_km_s']:.4f} км/с")
    print(f"  Шаг 3: Δv1 = {r['dv1_mps']:.2f} м/с")
    print(f"  Шаг 4: Δv2 = {r['dv2_mps']:.2f} м/с")
    print(f"\\n  Суммарный Δv: {r['dv_total_mps']:.2f} м/с")
    print(f"  Передаточная: a = {r['a_km']:.3f} км,  e = {r['e']:.6f}\\n")
''',

"_solve_r_v_nu": '''def _solve_r_v_nu() -> None:
    """28: известны r, v, ν."""
    print("\\n  СЛУЧАЙ 28: r, v, ν\\n")
    print("  a = μr/(2μ − rv²),  два корня для e по r = a(1−e²)/(1+e·cos ν)\\n")

    H = rf("  H, км: ")
    v = rf("  v, км/с: ")
    nu_deg = rf("  ν, °: ")

    r = aero.solve_case("28", H=H, v=v, nu_deg=nu_deg)
    if "error" in r:
        logger.warning(f"  {r['error']}")
        return

    print(f"\\n  Шаг 2: a = {r['a']:.3f} км")
    print(f"  Принято: e = {r['e']:.6f} ({r['branch']})")
    _print_orbit_result(r["a"], r["e"])
''',

"_solve_sso": '''def _solve_sso() -> None:
    """29: солнечно-синхронная орбита."""
    print("\\n  СОЛНЕЧНО-СИНХРОННАЯ ОРБИТА (SSO)\\n")
    print("  cos i = −2·n_☉/(3·J2·n·(R⊕/a)²)\\n")

    H = rf("  H, км: ")

    r = aero.solve_case("29", H=H)
    if "error" in r:
        logger.warning(f"  {r['error']}")
        return

    print(f"\\n  n = {r['n_rad_s']:.8f} рад/с,  T = {r['T_s']:.2f} с = {r['T_s'] / 60:.4f} мин")
    print(f"  i_SSO = {r['i_SSO_deg']:.4f}°  (ретроградная)\\n")
''',

"_solve_repeat_track": '''def _solve_repeat_track() -> None:
    """30: повторяющаяся траектория."""
    print("\\n  ПОВТОРЯЮЩАЯСЯ ТРАЕКТОРИЯ\\n")
    print("  Режим:")
    print("    1. H → k")
    print("    2. k → H")
    mode = input("  Выбор [1]: ").strip() or "1"

    if mode == "2":
        k = ri("  k (витков за сидерические сутки): ")
        if k < 1:
            logger.warning("  k ≥ 1")
            return
        T_orb = T_SIDEREAL / k
        a = (MU_EARTH * T_orb * T_orb / (4 * math.pi ** 2)) ** (1 / 3)
        H = a - R_EARTH
        print(f"\\n  T_orb = {T_orb:.4f} с,  a = {a:.3f} км,  H = {H:+.3f} км\\n")
        return

    H = rf("  H, км: ")

    r = aero.solve_case("30", H=H)
    if "error" in r:
        logger.warning(f"  {r['error']}")
        return

    print(f"\\n  T_orb = {r['T_orb_s']:.4f} с,  k_rep = {r['k_rep']}")
    print(f"  H_rep = {r['H_rep_km']:+.3f} км\\n")
''',

"_solve_ap_pe": '''def _solve_ap_pe() -> None:
    """31: Ap/Pe."""
    print("\\n  ПАРАМЕТРЫ ОРБИТЫ ПО Ap/Pe\\n")
    print("  r_p = H_p + R⊕,  r_a = H_a + R⊕,  a = (r_p+r_a)/2\\n")

    ap = rf("  Апогей (Ap), км: ")
    pe = rf("  Перигей (Pe), км: ")
    ok, msg = check_orbit(ap, pe)
    if not ok:
        print(f"  {msg}")
        return

    r = aero.solve_case("31", Ap=ap, Pe=pe)
    if "error" in r:
        logger.warning(f"  {r['error']}")
        return

    print(f"\\n  a = {r['a']:.3f} км,  e = {r['e']:.6f}")
    _print_orbit_result(r["a"], r["e"])
''',

"_solve_velocity_at_point": '''def _solve_velocity_at_point() -> None:
    """32: скорость в точке орбиты."""
    print("\\n  СКОРОСТЬ В ТОЧКЕ ОРБИТЫ (vis-viva)\\n")
    print("  v² = μ·(2/r − 1/a)\\n")

    ap = rf("  Апогей (Ap), км: ")
    pe = rf("  Перигей (Pe), км: ")
    ok, msg = check_orbit(ap, pe)
    if not ok:
        print(f"  {msg}")
        return

    a_orb = (ap + pe) / 2 + R_EARTH
    pt = input("  Точка (p — перигей, a — апогей, r — радиус): ").strip().lower()
    if pt == "p":
        r_pt = pe + R_EARTH
        name = "перигей"
    elif pt == "a":
        r_pt = ap + R_EARTH
        name = "апогей"
    elif pt == "r":
        r_pt = rf("  Радиус от центра, км: ")
        if r_pt < R_EARTH or 2 / r_pt - 1 / a_orb < 0:
            logger.warning("  Недопустимый радиус")
            return
        name = f"r = {r_pt:.1f} км"
    else:
        logger.warning("  Введите p/a/r")
        return

    r = aero.solve_case("32", Ap=ap, Pe=pe, r=r_pt)
    if "error" in r:
        logger.warning(f"  {r['error']}")
        return

    print(f"\\n  Точка: {name}")
    print(f"  v = {r['v_km_s']:.4f} км/с ({r['v_km_s'] * 1000:.1f} м/с)\\n")
''',

"_solve_circular_full": '''def _solve_circular_full() -> None:
    """33: круговая скорость и период."""
    print("\\n  КРУГОВАЯ СКОРОСТЬ И ПЕРИОД\\n")
    print("  v = √(μ/r),  T = 2π√(r³/μ)\\n")

    alt = rf("  Высота, км: ")

    r = aero.solve_case("33", H=alt)
    if "error" in r:
        logger.warning(f"  {r['error']}")
        return

    print(f"\\n  r = {r['r_km']:.3f} км,  v = {r['v_km_s']:.4f} км/с")
    print(f"  T = {r['T_s']:.2f} с = {r['T_s'] / 60:.4f} мин")
    print(f"  n = {r['n_rad_s']:.6f} рад/с\\n")
''',

"_solve_hohmann_full": '''def _solve_hohmann_full() -> None:
    """34: перелёт Хомана."""
    print("\\n  ПЕРЕЛЁТ ХОМАНА (2 ИМПУЛЬСА)\\n")
    print("  a_t = (r1+r2)/2,  Δv1 = v1_t − v1_c,  Δv2 = v2_c − v2_t\\n")

    h1 = rf("  Высота орбиты 1, км: ")
    h2 = rf("  Высота орбиты 2, км: ")

    r = aero.solve_case("34", H1=h1, H2=h2)
    if "error" in r:
        logger.warning(f"  {r['error']}")
        return

    print(f"\\n  Δv1 = {r['dv1_mps']:+.2f} м/с,  Δv2 = {r['dv2_mps']:+.2f} м/с")
    print(f"  Σ|Δv| = {r['dv_total_mps']:.2f} м/с")
    print(f"  t = {r['t_transfer_s']:.2f} с = {r['t_transfer_s'] / 60:.2f} мин ({r['t_transfer_s'] / 3600:.2f} ч)\\n")
''',

"_solve_bielliptic_full": '''def _solve_bielliptic_full() -> None:
    """35: биэллиптический перелёт."""
    print("\\n  БИЭЛЛИПТИЧЕСКИЙ ПЕРЕЛЁТ (3 ИМПУЛЬСА)\\n")

    h1 = rf("  H1, км: ")
    h2 = rf("  H2, км: ")
    h_bi = rf("  H_rb (промежуточная), км: ")

    r = aero.solve_case("35", H1=h1, H2=h2, H_bi=h_bi)
    if "error" in r:
        logger.warning(f"  {r['error']}")
        return

    print(f"\\n  Δv1 = {r['dv1_mps']:+.2f} м/с,  Δv2 = {r['dv2_mps']:+.2f} м/с,  Δv3 = {r['dv3_mps']:+.2f} м/с")
    print(f"  Σ|Δv| = {r['dv_total_mps']:.2f} м/с  (Хоман: {r['hohmann_total_mps']:.2f} м/с)")
    verdict = "биэллиптика выгоднее" if r["bielliptic_is_better"] else "Хоман выгоднее"
    print(f"  Вывод: {verdict}\\n")
''',

"_solve_tsiolkovsky_full": '''def _solve_tsiolkovsky_full() -> None:
    """36: Циолковский."""
    print("\\n  ЦИОЛКОВСКИЙ: Δv → ТОПЛИВО\\n")

    dv = rf("  Δv, м/с: ")
    m0 = rf("  Масса начальная m0, кг: ")
    isp = rf("  Isp, с: ")

    r = aero.solve_case("36", dv=dv, m0=m0, isp=isp)
    if "error" in r:
        logger.warning(f"  {r['error']}")
        return

    print(f"\\n  v_e = {r['ve_mps']:.2f} м/с")
    print(f"  m_fuel = {r['m_fuel_kg']:.3f} кг ({r['fuel_fraction'] * 100:.2f}%)")
    print(f"  m_final = {r['m_final_kg']:.3f} кг\\n")
''',

"_solve_inverse_ts_full": '''def _solve_inverse_ts_full() -> None:
    """37: обратный Циолковский."""
    print("\\n  ОБРАТНЫЙ ЦИОЛКОВСКИЙ: ТОПЛИВО → Δv\\n")

    m_fuel = rf("  Топливо m_fuel, кг: ")
    m0 = rf("  Масса начальная m0, кг: ")
    isp = rf("  Isp, с: ")

    r = aero.solve_case("37", m_fuel=m_fuel, m0=m0, isp=isp)
    if "error" in r:
        logger.warning(f"  {r['error']}")
        return

    print(f"\\n  v_e = {r['ve_mps']:.2f} м/с")
    print(f"  m_final = {r['m_final_kg']:.3f} кг")
    print(f"  Δv = {r['dv_mps']:.2f} м/с\\n")
''',

"_solve_time_of_flight": '''def _solve_time_of_flight() -> None:
    """38: время пролёта по истинной аномалии."""
    print("\\n  ВРЕМЯ ПРОЛЁТА ПО ИСТИННОЙ АНОМАЛИИ\\n")

    a = rf("  a, км: ")
    e = rf("  e (0 ≤ e < 1): ")
    nu1 = rf("  ν1, °: ")
    nu2 = rf("  ν2, °: ")

    r = aero.solve_case("38", a=a, e=e, nu1=nu1, nu2=nu2)
    if "error" in r:
        logger.warning(f"  {r['error']}")
        return

    print(f"\\n  ΔM = {r['dM_rad']:.6f} рад,  T = {r['T_s']:.2f} с")
    print(f"  Δt = {r['dt_s']:.4f} с = {r['dt_s'] / 60:.4f} мин = {r['dt_s'] / 3600:.4f} ч\\n")
''',

"_solve_true_anomaly_by_time": '''def _solve_true_anomaly_by_time() -> None:
    """39: истинная аномалия по времени."""
    print("\\n  ИСТИННАЯ АНОМАЛИЯ ПО ВРЕМЕНИ\\n")

    a = rf("  a, км: ")
    e = rf("  e (0 ≤ e < 1): ")
    t = rf("  t (от перигея), с: ")

    r = aero.solve_case("39", a=a, e=e, t=t)
    if "error" in r:
        logger.warning(f"  {r['error']}")
        return

    print(f"\\n  E = {r['E_rad']:.8f} рад")
    print(f"  ν = {r['nu_deg']:.4f}°,  r = {r['r_km']:.3f} км")
    print(f"  v = {r['v_km_s']:.4f} км/с ({r['v_km_s'] * 1000:.1f} м/с)\\n")
''',

"_solve_hyperbolic": '''def _solve_hyperbolic() -> None:
    """40: гиперболическая орбита."""
    print("\\n  ГИПЕРБОЛИЧЕСКАЯ ОРБИТА (C3, v_∞)\\n")

    H_p = rf("  H_p, км: ")
    v_inf = rf("  v_∞, км/с: ")

    r = aero.solve_case("40", H_p=H_p, v_inf=v_inf)
    if "error" in r:
        logger.warning(f"  {r['error']}")
        return

    print(f"\\n  C3 = {r['C3_km2_s2']:.4f} км²/с²,  a = {r['a_km']:.3f} км,  e = {r['e']:.6f}")
    print(f"  p = {r['p_km']:.3f} км,  v_p = {r['v_p_km_s']:.4f} км/с")
    print(f"  δ = {r['delta_deg']:.4f}°\\n")
''',

"_solve_hill_soi": '''def _solve_hill_soi() -> None:
    """41: сфера Хилла и SOI."""
    print("\\n  СФЕРА ХИЛЛА И SOI\\n")
    print("    1. Земля — Солнце,  2. Луна — Земля,  3. Марс — Солнце")
    choice = input("  Выбор [1]: ").strip() or "1"
    smap = {"1": "earth-sun", "2": "moon-earth", "3": "mars-sun"}
    if choice not in smap:
        logger.warning("  Неверный выбор")
        return

    r = aero.solve_case("41", system=smap[choice])
    if "error" in r:
        logger.warning(f"  {r['error']}")
        return

    print(f"\\n  r_H = {r['r_H_km']:.3e} км ({r['r_H_km'] / 1e3:.1f} тыс. км)")
    print(f"  r_SOI = {r['r_SOI_km']:.3e} км ({r['r_SOI_km'] / 1e3:.1f} тыс. км)\\n")
''',

"_solve_lagrange_l1_l2": '''def _solve_lagrange_l1_l2() -> None:
    """42: L1/L2 (приближение)."""
    print("\\n  ТОЧКИ ЛАГРАНЖА L1/L2 (приближение)\\n")
    print("    1. Земля — Солнце,  2. Земля — Луна,  3. Марс — Солнце")
    choice = input("  Выбор [1]: ").strip() or "1"
    smap = {"1": "earth-sun", "2": "moon-earth", "3": "mars-sun"}
    if choice not in smap:
        logger.warning("  Неверный выбор")
        return

    r = aero.solve_case("42", system=smap[choice])
    if "error" in r:
        logger.warning(f"  {r['error']}")
        return

    print(f"\\n  μ = {r['mu']:.6e},  r_L = {r['r_L_km']:.3e} км ({r['r_L_km'] / 1e3:.1f} тыс. км)\\n")
''',

"_solve_synodic_period": '''def _solve_synodic_period() -> None:
    """43: синодический период."""
    print("\\n  СИНОДИЧЕСКИЙ ПЕРИОД\\n")

    unit = input("  Единица T — с/мин/ч [мин]: ").strip().lower() or "мин"
    mult = {"с": 1.0, "s": 1.0, "мин": 60.0, "m": 60.0, "min": 60.0,
            "ч": 3600.0, "h": 3600.0}.get(unit, 60.0)
    T1_in = rf("  T1: ")
    T2_in = rf("  T2: ")
    T1 = T1_in * mult
    T2 = T2_in * mult

    r = aero.solve_case("43", T1=T1, T2=T2)
    if "error" in r:
        logger.warning(f"  {r['error']}")
        return

    print(f"\\n  T_syn = {r['T_syn_s']:.4f} с = {r['T_syn_s'] / 60:.4f} мин")
    print(f"        = {r['T_syn_s'] / 3600:.4f} ч = {r['T_syn_s'] / 86400:.4f} сут\\n")
''',

"_solve_inclination_change": '''def _solve_inclination_change() -> None:
    """44: Δv смены наклонения."""
    print("\\n  Δv ДЛЯ СМЕНЫ НАКЛОНЕНИЯ\\n")

    alt = rf("  Высота, км: ")
    di = rf("  Δi, °: ")

    r = aero.solve_case("44", H=alt, di=di)
    if "error" in r:
        logger.warning(f"  {r['error']}")
        return

    print(f"\\n  v = {r['v_km_s']:.4f} км/с")
    print(f"  Δv = {r['dv_mps']:.1f} м/с\\n")
''',

"_solve_look_angle": '''def _solve_look_angle() -> None:
    """45: угол места и дальность."""
    print("\\n  УГОЛ МЕСТА И ДАЛЬНОСТЬ ДО СПУТНИКА\\n")

    H = rf("  H спутника, км: ")
    gamma_deg = rf("  γ, °: ")

    r = aero.solve_case("45", H=H, gamma_deg=gamma_deg)
    if "error" in r:
        logger.warning(f"  {r['error']}")
        return

    print(f"\\n  ε = {r['elev_deg']:.4f}°,  d = {r['range_km']:.3f} км\\n")
''',

"_solve_state_vector": '''def _solve_state_vector() -> None:
    """46: вектор состояния → элементы."""
    print("\\n  ВЕКТОР СОСТОЯНИЯ → ЭЛЕМЕНТЫ\\n")
    print("  h = r × v,  e = (v × h)/μ − r̂,  i = arccos(h_z/|h|)\\n")

    try:
        rx, ry, rz = rf("  x, км: "), rf("  y, км: "), rf("  z, км: ")
        vx, vy, vz = rf("  vx, км/с: "), rf("  vy, км/с: "), rf("  vz, км/с: ")
        r = aero.solve_case("46", r=(rx, ry, rz), v=(vx, vy, vz))
    except ValueError as exc:
        logger.warning(f"  {exc}")
        return
    if "error" in r:
        logger.warning(f"  {r['error']}")
        return

    print(f"\\n  |r| = {r['r']:.3f} км,  |v| = {r['v']:.4f} км/с")
    print(f"  ε = {r['eps']:.6f} км²/с²,  |h| = {r['h']:.4f} км²/с,  e = {r['e']:.6f}")
    print(f"  i = {r['i']:.4f}°,  Ω = {r['Omega']:.4f}°")
    print(f"  ω = {r['omega']:.4f}°,  ν = {r['nu']:.4f}°")

    if r["eps"] < -1e-9:
        print(f"  a = {r['a']:.3f} км  (эллипс)")
    elif abs(r["eps"]) <= 1e-9:
        print("  a = ∞  (парабола)")
    else:
        print(f"  a = {r['a']:.3f} км  (a<0, гипербола)")
    print()
''',
}

assert len(NEW_FUNCS) == 29, f"Ожидалось 29, получено {len(NEW_FUNCS)}"


# ═══════════════════════════════════════════════════════════════════════════
#  Тест
# ═══════════════════════════════════════════════════════════════════════════

NEW_TEST = '''

def test_v4c_delegation():
    """v4c: 29 оставшихся _solve_* делегируют в aero.solve_case."""
    import inspect
    from cli import calculator as calc
    expected = [
        "_solve_r_v_gamma", "_solve_rp_vp", "_solve_T_circular", "_solve_ra_va",
        "_solve_T_e", "_solve_T_rp", "_solve_T_vp", "_solve_hohmann_incl",
        "_solve_phasing_full", "_solve_lambert", "_solve_r_v_nu", "_solve_sso",
        "_solve_repeat_track", "_solve_ap_pe", "_solve_velocity_at_point",
        "_solve_circular_full", "_solve_hohmann_full", "_solve_bielliptic_full",
        "_solve_tsiolkovsky_full", "_solve_inverse_ts_full", "_solve_time_of_flight",
        "_solve_true_anomaly_by_time", "_solve_hyperbolic", "_solve_hill_soi",
        "_solve_lagrange_l1_l2", "_solve_synodic_period", "_solve_inclination_change",
        "_solve_look_angle", "_solve_state_vector",
    ]
    for name in expected:
        fn = getattr(calc, name)
        src = inspect.getsource(fn)
        assert "aero.solve_case" in src, f"{name} не делегирует в aero.solve_case"
'''


# ═══════════════════════════════════════════════════════════════════════════
#  Применение
# ═══════════════════════════════════════════════════════════════════════════


def _apply_patch(path: Path, old: str, new: str, name: str) -> bool:
    if not path.is_file():
        print(f"  [err] {path} не найден", file=sys.stderr)
        return False
    text = path.read_text(encoding="utf-8")
    if new in text and old not in text:
        print(f"  [skip] {name}")
        return True
    if old not in text:
        print(f"  [err] якорь не найден для {name}", file=sys.stderr)
        return False
    backup = path.with_suffix(path.suffix + ".v4c.bak")
    if not backup.exists():
        shutil.copy2(path, backup)
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"  [ok]   {name}")
    return True


def _replace_function(text: str, func_name: str, new_body: str) -> tuple[str, bool]:
    """Заменяет тело функции до следующего top-level def."""
    start = f"def {func_name}() -> None:"
    i = text.find(start)
    if i < 0:
        return text, False
    j = text.find("\ndef ", i + len(start))
    if j < 0:
        j = len(text)
    # Проверка: уже пропатчено?
    current = text[i:j]
    if "aero.solve_case" in current:
        return text, False
    if "_print_orbit_result" not in current and "_record(" not in current and "print(" not in current:
        return text, False
    new_clean = new_body.rstrip() + "\n\n\n" + text[j + 1:]
    return text[:i] + new_clean, True


def patch_core() -> int:
    print(f"\n[1] {ASTRO}")
    ok1 = _apply_patch(ASTRO, S26_OLD, S26_NEW, "_s26 расширен")
    ok2 = _apply_patch(ASTRO, S27_OLD, S27_NEW, "_s27 расширен")
    if not (ok1 and ok2):
        return 1
    try:
        compile(ASTRO.read_text(encoding="utf-8"), str(ASTRO), "exec")
        print("  [ok]   синтаксис корректен")
    except SyntaxError as exc:
        print(f"  [err] SyntaxError: {exc}", file=sys.stderr)
        return 2
    return 0


def patch_calc() -> int:
    print(f"\n[2] {CALC}")
    if not CALC.is_file():
        print(f"  [err] не найден", file=sys.stderr)
        return 1

    text = CALC.read_text(encoding="utf-8")

    if text.count("aero.solve_case") >= 46:  # 17 (v4b) + 29 (v4c)
        print("  [skip] v4c уже применён")
        return 0

    backup = CALC.with_suffix(".py.v4c.bak")
    if not backup.exists():
        shutil.copy2(CALC, backup)
        print(f"  [backup] {backup}")

    patched = 0
    for name in NEW_FUNCS:
        text, changed = _replace_function(text, name, NEW_FUNCS[name])
        if changed:
            print(f"  [ok]   {name}")
            patched += 1
        else:
            print(f"  [skip] {name} — уже пропатчено или маркер не найден")

    try:
        compile(text, str(CALC), "exec")
    except SyntaxError as exc:
        print(f"  [err] SyntaxError: {exc}", file=sys.stderr)
        return 2

    CALC.write_text(text, encoding="utf-8")
    print(f"  [written] {len(text)} байт ({patched}/{len(NEW_FUNCS)} заменено)")
    return 0


def patch_tests() -> int:
    print(f"\n[3] {TESTS}")
    if not TESTS.is_file():
        print(f"  [err] не найден", file=sys.stderr)
        return 1
    text = TESTS.read_text(encoding="utf-8")
    if "test_v4c_delegation" in text:
        print("  [skip] тест уже есть")
        return 0
    backup = TESTS.with_suffix(".py.v4c.bak")
    if not backup.exists():
        shutil.copy2(TESTS, backup)
    TESTS.write_text(text.rstrip() + "\n" + NEW_TEST, encoding="utf-8")
    try:
        compile(TESTS.read_text(encoding="utf-8"), str(TESTS), "exec")
    except SyntaxError as exc:
        print(f"  [err] SyntaxError: {exc}", file=sys.stderr)
        return 2
    print("  [ok]   test_v4c_delegation добавлен")
    return 0


def verify() -> int:
    import subprocess
    code = (
        "import sys; sys.path.insert(0, '.'); "
        "import inspect; "
        "from cli import calculator as calc; "
        "names = [" + ", ".join(f"'{n}'" for n in NEW_FUNCS) + "]; "
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
    print("[patch v4c] Рефакторинг оставшихся 29 _solve_* через aero.solve_case")
    print("=" * 50)

    rc = patch_core()
    if rc != 0:
        print("\n[patch v4c] Ошибки в core — файл CLI не изменён", file=sys.stderr)
        return rc

    rc = patch_calc()
    if rc != 0:
        return rc

    rc = patch_tests()
    if rc != 0:
        return rc

    print("\n[verify] делегирование 29 функций")
    rc = verify()
    if rc != 0:
        return rc

    print("\n" + "=" * 50)
    print("[patch v4c] Готово. Проверьте:")
    print("  pytest tests/ -v                              # 97 passed")
    print("  python3 cli/calculator.py --solve=34 --verbose # shadow verify молчит")
    print("  python3 cli/calculator.py --solve=27 --json")
    return 0


if __name__ == "__main__":
    sys.exit(main())