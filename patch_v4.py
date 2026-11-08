#!/usr/bin/env python3
"""patch_v4.py — рефакторинг: aero.solve_case + --json для всех 53.

Идемпотентен. Резервные копии: *.py.v4.bak
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

CALC = Path("cli/calculator.py")
ASTRO = Path("core/astrodynamics.py")


# ── 1. core/astrodynamics.py: вставить блок solve_case ────────────────────
SOLVE_CASE_BLOCK = r'''
# ═══════════════════════════════════════════════════════════════════════════
#  ЕДИНАЯ ТОЧКА ВХОДА: solve_case (v4)
# ═══════════════════════════════════════════════════════════════════════════

CASE_META = {
    "1":  {"name": "a и e", "inputs": ["a", "e"]},
    "2":  {"name": "H_p и H_a", "inputs": ["H_p", "H_a"]},
    "3":  {"name": "H_p и e", "inputs": ["H_p", "e"]},
    "4":  {"name": "H, v, γ", "inputs": ["H", "v", "gamma"]},
    "5":  {"name": "h и ε", "inputs": ["h", "eps"]},
    "6":  {"name": "H_p и v_p", "inputs": ["H_p", "v_p"]},
    "7":  {"name": "h и a", "inputs": ["h", "a"]},
    "8":  {"name": "T (круговая)", "inputs": ["T"]},
    "9":  {"name": "H_a и e", "inputs": ["H_a", "e"]},
    "10": {"name": "H_a и v_a", "inputs": ["H_a", "v_a"]},
    "11": {"name": "v_p и v_a", "inputs": ["v_p", "v_a"]},
    "12": {"name": "h и e", "inputs": ["h", "e"]},
    "13": {"name": "p и e", "inputs": ["p", "e"]},
    "14": {"name": "T и e", "inputs": ["T", "e"]},
    "15": {"name": "H_p и h", "inputs": ["H_p", "h"]},
    "16": {"name": "H_a и h", "inputs": ["H_a", "h"]},
    "17": {"name": "a и H_p", "inputs": ["a", "H_p"]},
    "18": {"name": "a и H_a", "inputs": ["a", "H_a"]},
    "19": {"name": "T и H_p", "inputs": ["T", "H_p"]},
    "20": {"name": "T и v_p", "inputs": ["T", "v_p"]},
    "21": {"name": "e и v_p", "inputs": ["e", "v_p"]},
    "22": {"name": "e и v_a", "inputs": ["e", "v_a"]},
    "23": {"name": "H_p и v_a", "inputs": ["H_p", "v_a"]},
    "24": {"name": "H_a и v_p", "inputs": ["H_a", "v_p"]},
    "25": {"name": "Хоман + Δi", "inputs": ["H1", "H2", "di"]},
    "26": {"name": "Фазирование", "inputs": ["H", "dphi", "N"]},
    "27": {"name": "Ламберт", "inputs": ["H1", "H2", "dnu_deg", "dt"]},
    "28": {"name": "r, v, ν", "inputs": ["H", "v", "nu_deg"]},
    "29": {"name": "SSO", "inputs": ["H"]},
    "30": {"name": "Повторяющаяся", "inputs": ["H"]},
    "31": {"name": "Ap/Pe", "inputs": ["Ap", "Pe"]},
    "32": {"name": "v в точке", "inputs": ["Ap", "Pe", "r"]},
    "33": {"name": "Круговая", "inputs": ["H"]},
    "34": {"name": "Хоман", "inputs": ["H1", "H2"]},
    "35": {"name": "Биэллиптика", "inputs": ["H1", "H2", "H_bi"]},
    "36": {"name": "Циолковский", "inputs": ["dv", "m0", "isp"]},
    "37": {"name": "Обратный Ц.", "inputs": ["m_fuel", "m0", "isp"]},
    "38": {"name": "Время пролёта", "inputs": ["a", "e", "nu1", "nu2"]},
    "39": {"name": "Обратный Кеплер", "inputs": ["a", "e", "t"]},
    "40": {"name": "Гипербола", "inputs": ["H_p", "v_inf"]},
    "41": {"name": "Хилл/SOI", "inputs": ["system"]},
    "42": {"name": "L1/L2 (прибл.)", "inputs": ["system"]},
    "43": {"name": "Синодический", "inputs": ["T1", "T2"]},
    "44": {"name": "Δi", "inputs": ["H", "di"]},
    "45": {"name": "Угол места", "inputs": ["H", "gamma_deg"]},
    "46": {"name": "Вектор → элементы", "inputs": ["r", "v"]},
    "47": {"name": "J2-прецессия", "inputs": ["H", "e", "i"]},
    "48": {"name": "Радар", "inputs": ["rho", "rho_dot", "el"]},
    "49": {"name": "Бюджет", "inputs": ["H", "isp", "m0"]},
    "50": {"name": "Payload", "inputs": ["dv", "isp", "m0", "m_dry"]},
    "51": {"name": "Ступени", "inputs": ["dv", "isp", "epsilon"]},
    "52": {"name": "CR3BP", "inputs": ["mu", "point"]},
    "53": {"name": "Frozen", "inputs": ["H", "e", "i"]},
}


def _s1(a, e): return elements_from_a_e(a, e)
def _s2(H_p, H_a): return elements_from_rp_ra(H_p + R_EARTH, H_a + R_EARTH)
def _s3(H_p, e): return elements_from_rp_e(H_p + R_EARTH, e)
def _s4(H, v, gamma): return elements_from_r_v_gamma(H + R_EARTH, v, gamma)
def _s5(h, eps): return elements_from_h_eps(h, eps)
def _s6(H_p, v_p): return elements_from_rp_vp(H_p + R_EARTH, v_p)
def _s7(h, a): return elements_from_h_a(h, a)
def _s8(T): return elements_from_T_circular(T)
def _s9(H_a, e): return elements_from_ra_e(H_a + R_EARTH, e)


def _s10(H_a, v_a):
    r_a = H_a + R_EARTH
    eps = v_a * v_a / 2 - MU_EARTH / r_a
    if eps >= 0:
        raise ValueError("ε ≥ 0 — незамкнутая орбита")
    return elements_from_h_eps(r_a * v_a, eps)


def _s11(v_p, v_a): return elements_from_vp_va(v_p, v_a)
def _s12(h, e): return elements_from_h_e(h, e)
def _s13(p, e): return elements_from_p_e(p, e)
def _s14(T, e): return elements_from_T_e(T, e)


def _s15(H_p, h):
    r_p = H_p + R_EARTH
    p = h * h / MU_EARTH
    e = p / r_p - 1
    if e < 0 or e >= 1:
        raise ValueError(f"e = {e:.6f} вне [0,1)")
    return elements_from_a_e(p / (1 - e * e), e)


def _s16(H_a, h):
    r_a = H_a + R_EARTH
    p = h * h / MU_EARTH
    e = 1 - p / r_a
    if e < 0 or e >= 1:
        raise ValueError(f"e = {e:.6f} вне [0,1)")
    return elements_from_a_e(p / (1 - e * e), e)


def _s17(a, H_p):
    r_p = H_p + R_EARTH
    e = 1 - r_p / a
    if e < 0 or e >= 1:
        raise ValueError(f"e = {e:.6f} вне [0,1)")
    return elements_from_a_e(a, e)


def _s18(a, H_a):
    r_a = H_a + R_EARTH
    e = r_a / a - 1
    if e < 0 or e >= 1:
        raise ValueError(f"e = {e:.6f} вне [0,1)")
    return elements_from_a_e(a, e)


def _s19(T, H_p):
    a = (MU_EARTH * T * T / (4 * math.pi ** 2)) ** (1 / 3)
    r_p = H_p + R_EARTH
    e = 1 - r_p / a
    if e < 0 or e >= 1:
        raise ValueError(f"e = {e:.6f} вне [0,1)")
    return elements_from_a_e(a, e)


def _s20(T, v_p):
    a = (MU_EARTH * T * T / (4 * math.pi ** 2)) ** (1 / 3)
    av2 = a * v_p * v_p
    return elements_from_a_e(a, (av2 - MU_EARTH) / (av2 + MU_EARTH))


def _s21(e, v_p): return elements_from_rp_e(MU_EARTH * (1 + e) / (v_p * v_p), e)
def _s22(e, v_a): return elements_from_ra_e(MU_EARTH * (1 - e) / (v_a * v_a), e)


def _s23(H_p, v_a):
    r_p = H_p + R_EARTH
    v2 = v_a * v_a
    disc = r_p * r_p * v2 * v2 + 8 * MU_EARTH * r_p * v2
    a = (r_p * v2 + math.sqrt(disc)) / (4 * v2)
    e = 1 - r_p / a
    if e < 0 or e >= 1:
        raise ValueError(f"e = {e:.6f} вне [0,1)")
    return elements_from_a_e(a, e)


def _s24(H_a, v_p):
    r_a = H_a + R_EARTH
    v2 = v_p * v_p
    disc = r_a * r_a * v2 * v2 + 8 * MU_EARTH * r_a * v2
    a = (r_a * v2 + math.sqrt(disc)) / (4 * v2)
    e = r_a / a - 1
    if e < 0 or e >= 1:
        raise ValueError(f"e = {e:.6f} вне [0,1)")
    return elements_from_a_e(a, e)


def _s25(H1, H2, di):
    r1, r2 = H1 + R_EARTH, H2 + R_EARTH
    a_t = (r1 + r2) / 2
    v1c, v2c = math.sqrt(MU_EARTH / r1), math.sqrt(MU_EARTH / r2)
    v1t = math.sqrt(MU_EARTH * (2 / r1 - 1 / a_t))
    v2t = math.sqrt(MU_EARTH * (2 / r2 - 1 / a_t))
    cos_di = math.cos(math.radians(abs(di)))
    dv1_A = math.sqrt(v1c * v1c + v1t * v1t - 2 * v1c * v1t * cos_di)
    dv2_A = abs(v2c - v2t)
    dv1_B = abs(v1t - v1c)
    dv2_B = math.sqrt(v2t * v2t + v2c * v2c - 2 * v2t * v2c * cos_di)
    return {
        "dv1_A_mps": dv1_A * 1000, "dv2_A_mps": dv2_A * 1000,
        "total_A_mps": (dv1_A + dv2_A) * 1000,
        "dv1_B_mps": dv1_B * 1000, "dv2_B_mps": dv2_B * 1000,
        "total_B_mps": (dv1_B + dv2_B) * 1000,
        "best": "A" if dv1_A + dv2_A < dv1_B + dv2_B else "B",
    }


def _s26(H, dphi, N):
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
            "n_revs": N}


def _s28(H, v, nu_deg):
    r = H + R_EARTH
    rv2 = r * v * v
    if rv2 >= 2 * MU_EARTH:
        raise ValueError("r·v² ≥ 2μ")
    a = MU_EARTH * r / (2 * MU_EARTH - rv2)
    nu = math.radians(nu_deg)
    cos_nu = math.cos(nu)
    disc = r * r * cos_nu * cos_nu + 4 * a * (a - r)
    if disc < -1e-9:
        raise ValueError("D < 0")
    sqrt_d = math.sqrt(max(0.0, disc))
    for sign, label in ((1, "восходящая"), (-1, "нисходящая")):
        e_val = (-r * cos_nu + sign * sqrt_d) / (2 * a)
        if 0 <= e_val < 1 and a * (1 - e_val) >= R_EARTH:
            return {**elements_from_a_e(a, e_val), "branch": label}
    raise ValueError("Нет физически допустимых корней")


def _s29(H):
    a = H + R_EARTH
    n = math.sqrt(MU_EARTH / a ** 3)
    cos_i = -2 * N_SUN / (3 * J2 * n * (R_EARTH / a) ** 2)
    if not (-1 <= cos_i <= 1):
        raise ValueError(f"cos i = {cos_i:.6f}")
    return {"i_SSO_deg": math.degrees(math.acos(cos_i)), "n_rad_s": n,
            "T_s": 2 * math.pi / n}


def _s30(H):
    a = H + R_EARTH
    T_orb = 2 * math.pi * math.sqrt(a ** 3 / MU_EARTH)
    k_ideal = T_SIDEREAL / T_orb
    k_rep = max(1, round(k_ideal))
    T_rep = T_SIDEREAL / k_rep
    a_rep = (MU_EARTH * T_rep * T_rep / (4 * math.pi ** 2)) ** (1 / 3)
    return {"T_orb_s": T_orb, "k_rep": k_rep, "H_rep_km": a_rep - R_EARTH}


def _s31(Ap, Pe):
    if Ap < Pe or Pe < 0:
        raise ValueError("Некорректные Ap/Pe")
    return elements_from_rp_ra(Pe + R_EARTH, Ap + R_EARTH)


def _s32(Ap, Pe, r):
    a = (Ap + Pe) / 2 + R_EARTH
    if r < R_EARTH or 2 / r - 1 / a < 0:
        raise ValueError("r вне орбиты")
    return {"r_km": r, "v_km_s": vis_viva(r, a), "a_km": a}


def _s33(H):
    r = H + R_EARTH
    v = math.sqrt(MU_EARTH / r)
    T = 2 * math.pi * math.sqrt(r ** 3 / MU_EARTH)
    return {"r_km": r, "v_km_s": v, "T_s": T, "n_rad_s": 2 * math.pi / T}


def _s34(H1, H2): return hohmann(H1 + R_EARTH, H2 + R_EARTH)
def _s35(H1, H2, H_bi): return bielliptic(H1 + R_EARTH, H2 + R_EARTH, H_bi + R_EARTH)
def _s36(dv, m0, isp): return tsiolkovsky(dv, m0, isp)
def _s37(m_fuel, m0, isp): return inverse_tsiolkovsky(m_fuel, m0, isp)


def _s38(a, e, nu1, nu2):
    def _E(nu_deg):
        nu = math.radians(nu_deg)
        return 2 * math.atan2(math.sqrt(1 - e) * math.sin(nu / 2),
                              math.sqrt(1 + e) * math.cos(nu / 2))
    E1, E2 = _E(nu1) % (2 * math.pi), _E(nu2) % (2 * math.pi)
    M1 = (E1 - e * math.sin(E1)) % (2 * math.pi)
    M2 = (E2 - e * math.sin(E2)) % (2 * math.pi)
    n = math.sqrt(MU_EARTH / a ** 3)
    dM = M2 - M1
    if dM < 0:
        dM += 2 * math.pi
    return {"dt_s": dM / n, "T_s": 2 * math.pi / n}


def _s39(a, e, t):
    n = math.sqrt(MU_EARTH / a ** 3)
    M = (n * t) % (2 * math.pi)
    E = M
    for _ in range(100):
        dE = (E - e * math.sin(E) - M) / (1 - e * math.cos(E))
        E -= dE
        if abs(dE) < 1e-12:
            break
    nu = 2 * math.atan2(math.sqrt(1 + e) * math.sin(E / 2),
                        math.sqrt(1 - e) * math.cos(E / 2))
    r = a * (1 - e * math.cos(E))
    return {"E_rad": E, "nu_deg": math.degrees(nu) % 360,
            "r_km": r, "v_km_s": vis_viva(r, a)}


def _s40(H_p, v_inf):
    r_p = H_p + R_EARTH
    C3 = v_inf ** 2
    a = -MU_EARTH / C3
    e = 1 + r_p * v_inf ** 2 / MU_EARTH
    return {"C3_km2_s2": C3, "a_km": a, "e": e,
            "p_km": a * (1 - e * e),
            "v_p_km_s": math.sqrt(v_inf ** 2 + 2 * MU_EARTH / r_p),
            "delta_deg": math.degrees(2 * math.asin(1 / e))}


def _s41(system="earth-sun"):
    systems = {"earth-sun": (AU_KM, M_EARTH, M_SUN),
               "moon-earth": (A_MOON_KM, M_MOON, M_EARTH),
               "mars-sun": (A_MARS_AU * AU_KM, M_MARS, M_SUN)}
    if system not in systems:
        raise ValueError("system ∈ " + str(list(systems)))
    a, m, M = systems[system]
    return {"r_H_km": a * (m / (3 * M)) ** (1 / 3),
            "r_SOI_km": a * (m / M) ** (2 / 5), "system": system}


def _s42(system="earth-sun"):
    systems = {"earth-sun": (AU_KM, M_EARTH, M_SUN),
               "moon-earth": (A_MOON_KM, M_MOON, M_EARTH),
               "mars-sun": (A_MARS_AU * AU_KM, M_MARS, M_SUN)}
    if system not in systems:
        raise ValueError("system ∈ " + str(list(systems)))
    R, m, M = systems[system]
    mu = m / (m + M)
    return {"mu": mu, "r_L_km": R * (mu / 3) ** (1 / 3), "system": system}


def _s43(T1, T2):
    if T1 <= 0 or T2 <= 0 or abs(T1 - T2) < 1e-12:
        raise ValueError("T1, T2 > 0 и T1 ≠ T2")
    return {"T_syn_s": T1 * T2 / abs(T1 - T2), "T1_s": T1, "T2_s": T2}


def _s44(H, di):
    r = H + R_EARTH
    v = math.sqrt(MU_EARTH / r)
    dv = 2 * v * math.sin(math.radians(abs(di)) / 2)
    return {"v_km_s": v, "dv_mps": dv * 1000, "di_deg": di}


def _s45(H, gamma_deg):
    r_s = H + R_EARTH
    gamma = math.radians(gamma_deg)
    cos_g, sin_g = math.cos(gamma), math.sin(gamma)
    if abs(sin_g) < 1e-12:
        elev = 90.0 if gamma_deg < 1e-9 else -90.0
    else:
        elev = math.degrees(math.atan2(cos_g - R_EARTH / r_s, sin_g))
    d = math.sqrt(r_s ** 2 + R_EARTH ** 2 - 2 * r_s * R_EARTH * cos_g)
    return {"elev_deg": elev, "range_km": d}


def _s46(r, v): return elements_from_state(r, v)
def _s47(H, e, i): return j2_precession(H + R_EARTH, e, i)
def _s48(rho, rho_dot, el): return radar_track(rho, rho_dot, el)
def _s49(H, isp, m0): return ascent_budget(H, isp, m0)
def _s50(dv, isp, m0, m_dry): return max_payload(dv, isp, m0, m_dry)


def _s51(dv, isp, epsilon):
    results = best_staging(dv, isp, epsilon, max_stages=5)
    if not results:
        raise ValueError("Ни одна ступенчатость невозможна")
    best = max(results, key=lambda r: r["payload_ratio"])
    return {"results": results, "best": best}


def _s52(mu=None, point="L1", system="earth-sun"):
    if mu is None:
        systems = {"earth-sun": M_EARTH / (M_SUN + M_EARTH),
                   "moon-earth": M_MOON / (M_EARTH + M_MOON),
                   "mars-sun": M_MARS / (M_SUN + M_MARS)}
        if system not in systems:
            raise ValueError("system ∈ " + str(list(systems)))
        mu = systems[system]
    return {"mu": mu, "point": point, "x_L": cr3bp_lagrange(mu, point)}


def _s53(H, e, i): return frozen_orbit_info(H + R_EARTH, e, i)


_SOLVERS = {str(i): globals()[f"_s{i}"] for i in range(1, 54)}


def solve_case(sid, **kwargs):
    """Единая точка: расчёт по номеру случая и именованным аргументам.

    Никогда не бросает — при ошибке возвращает {"error": str}.
    """
    sid = str(sid)
    if sid not in _SOLVERS:
        return {"error": f"Неизвестный случай {sid}"}
    try:
        return _SOLVERS[sid](**kwargs)
    except TypeError as exc:
        return {"error": f"Неверные аргументы для {sid}: {exc}"}
    except ValueError as exc:
        return {"error": str(exc)}
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}
'''


# ── 2. cli/calculator.py: _RESULT + _record ───────────────────────────────
PATCH_RESULT_INIT = (
    "_LAST_RESULT = None\n",
    '''_LAST_RESULT = None
_RESULT = {"case": None, "output": {}, "error": None, "kind": None}


def _record(**kwargs):
    """Записывает результаты в _RESULT для --json."""
    if _RESULT["output"] is None:
        _RESULT["output"] = {}
    for k, v in kwargs.items():
        if isinstance(v, (int, float)):
            _RESULT["output"][k] = round(float(v), 10)
        else:
            _RESULT["output"][k] = v


def _set_kind(kind):
    _RESULT["kind"] = kind
''',
)

# ── 3. _print_orbit_result: _set_kind + _record ───────────────────────────
PATCH_PRINT_ORBIT_START = (
    '''def _print_orbit_result(a: float, e: float) -> None:
    """Печатает полный набор параметров эллиптической орбиты по (a, e)."""
    global _LAST_RESULT
    if a > 0 and 0 <= e < 1:''',
    '''def _print_orbit_result(a: float, e: float) -> None:
    """Печатает полный набор параметров эллиптической орбиты по (a, e)."""
    global _LAST_RESULT
    _set_kind("orbit")
    if a > 0 and 0 <= e < 1:''',
)

PATCH_PRINT_ORBIT_END = (
    '''    print(f"  n  (ср. движение): {2 * math.pi / T:12.6f} рад/с")
    print()
    if _ask_plot():
        plot_orbit_params(r_a - R_EARTH, r_p - R_EARTH)''',
    '''    print(f"  n  (ср. движение): {2 * math.pi / T:12.6f} рад/с")
    print()
    _record(a=a, e=e, r_p=r_p, r_a=r_a, p=p, h=h, eps=eps,
            T=T, v_p=v_p, v_a=v_a, n=2 * math.pi / T)
    if _ask_plot():
        plot_orbit_params(r_a - R_EARTH, r_p - R_EARTH)''',
)

# ── 4. _dispatch_solve ────────────────────────────────────────────────────
PATCH_DISPATCH = (
    '''def _dispatch_solve(sid: str) -> None:
    """Единая точка входа: LaTeX (если включён) + расчёт."""
    _print_latex(sid)
    _DISPATCH[sid]()''',
    '''def _dispatch_solve(sid: str) -> None:
    """Единая точка: сброс _RESULT + LaTeX + расчёт + перехват ошибок."""
    global _RESULT
    _RESULT = {"case": sid, "output": {}, "error": None, "kind": None}
    _print_latex(sid)
    try:
        _DISPATCH[sid]()
    except SystemExit:
        raise
    except Exception as exc:
        _RESULT["error"] = f"{type(exc).__name__}: {exc}"
        raise''',
)

# ── 5. main(): --json печатает _RESULT ───────────────────────────────────
PATCH_MAIN_JSON = (
    '''        if args.json and _LAST_RESULT is not None:
            print(json.dumps(_LAST_RESULT, indent=2, ensure_ascii=False))''',
    '''        if args.json:
            payload = {k: v for k, v in _RESULT.items() if v not in (None, {}, [])}
            if not payload.get("output") and _LAST_RESULT:
                payload["output"] = _LAST_RESULT
            print(json.dumps(payload, indent=2, ensure_ascii=False))''',
)


# ── 6. _record(...) в прямых расчётах ─────────────────────────────────────
RECORD_PATCHES = [
    # 32
    ('    print(f"  Скорость: {v:.4f} км/с ({v * 1000:.1f} м/с)\\n")\n    if _ask_plot():\n        plot_velocity_point(ap, pe, r, v, name)',
     '    print(f"  Скорость: {v:.4f} км/с ({v * 1000:.1f} м/с)\\n")\n    _record(r_km=r, v_km_s=v, point=name)\n    if _ask_plot():\n        plot_velocity_point(ap, pe, r, v, name)'),
    # 33
    ('    print(f"  n:            {2 * math.pi / T:.6f} рад/с\\n")\n    if _ask_plot():\n        plot_circular(alt)',
     '    print(f"  n:            {2 * math.pi / T:.6f} рад/с\\n")\n    _record(r_km=r, v_km_s=v, T_s=T, n_rad_s=2 * math.pi / T)\n    if _ask_plot():\n        plot_circular(alt)'),
    # 34
    ('    print(f"  Промежуточная:      {max(h1, h2):.1f} × {min(h1, h2):.1f} км\\n")\n    if _ask_plot():\n        plot_hohmann(h1, h2, dv1, dv2)',
     '    print(f"  Промежуточная:      {max(h1, h2):.1f} × {min(h1, h2):.1f} км\\n")\n    _record(r1_km=r1, r2_km=r2, a_t_km=a_trans, dv1_mps=dv1, dv2_mps=dv2,\n            dv_total_mps=abs(dv1) + abs(dv2), t_transfer_s=t_trans)\n    if _ask_plot():\n        plot_hohmann(h1, h2, dv1, dv2)'),
    # 36
    ('        print(f"  Время работы:      {burn_time:.2f} с")\n    print()',
     '        print(f"  Время работы:      {burn_time:.2f} с")\n    _record(ve_mps=ve, m_fuel_kg=fuel, m_final_kg=mass - fuel, fuel_fraction=fuel / mass)\n    print()'),
    # 37
    ('    print(f"  dv:                {dv:.2f} м/с\\n")',
     '    print(f"  dv:                {dv:.2f} м/с\\n")\n    _record(ve_mps=ve, m_final_kg=mass - fuel, dv_mps=dv)'),
    # 43
    ('    print(f"  T_syn = {T_syn:.4f} с = {T_syn / 60:.4f} мин = {T_syn / 86400:.4f} сут\\n")',
     '    print(f"  T_syn = {T_syn:.4f} с = {T_syn / 60:.4f} мин = {T_syn / 86400:.4f} сут\\n")\n    _record(T_syn_s=T_syn, T1_s=T1, T2_s=T2)'),
    # 44
    ('    print(f"  Δv = {dv:.4f} км/с = {dv * 1000:.1f} м/с\\n")',
     '    print(f"  Δv = {dv:.4f} км/с = {dv * 1000:.1f} м/с\\n")\n    _record(v_km_s=v, dv_mps=dv * 1000, di_deg=di)'),
    # 45
    ('    print(f"\\n  ε = {elev:.4f}°,  d = {d:.3f} км\\n")',
     '    print(f"\\n  ε = {elev:.4f}°,  d = {d:.3f} км\\n")\n    _record(elev_deg=elev, range_km=d)'),
    # 47
    ('    print(f"  Перигей за год: {r[\'domega_deg_year\']:+.2f}°\\n")',
     '    print(f"  Перигей за год: {r[\'domega_deg_year\']:+.2f}°\\n")\n    _record(r)'),
    # 49
    ('    print(f"  Шаг 7: m_fuel = {r[\'m_fuel_kg\']:.1f} кг ({r[\'fuel_fraction\']*100:.2f}%)\\n")',
     '    print(f"  Шаг 7: m_fuel = {r[\'m_fuel_kg\']:.1f} кг ({r[\'fuel_fraction\']*100:.2f}%)\\n")\n    _record(r)'),
    # 50
    ('    print(f"\\n  Полезная нагрузка: {status}\\n")',
     '    print(f"\\n  Полезная нагрузка: {status}\\n")\n    _record(r)'),
    # 53
    ('    print(f"  Замороженная (e<0.01 и i≈i_crit): {\'да\' if r[\'is_frozen_like\'] else \'нет\'}\\n")',
     '    print(f"  Замороженная (e<0.01 и i≈i_crit): {\'да\' if r[\'is_frozen_like\'] else \'нет\'}\\n")\n    _record(r)'),
]


def _apply(text, old, new, name):
    if new in text and old not in text:
        print(f"  [skip] {name}")
        return text
    if old not in text:
        raise RuntimeError(f"Якорь не найден для {name}: {old[:80]!r}")
    print(f"  [ok]   {name}")
    return text.replace(old, new, 1)


def patch_astrodynamics():
    print(f"\n[1] {ASTRO}")
    if not ASTRO.is_file():
        print(f"  [err] не найден")
        return 1
    text = ASTRO.read_text(encoding="utf-8")
    if "def solve_case(" in text:
        print("  [skip] solve_case уже есть")
        return 0
    backup = ASTRO.with_suffix(".py.v4.bak")
    if not backup.exists():
        shutil.copy2(ASTRO, backup)
        print(f"  [backup] {backup}")
    text = text.rstrip() + "\n\n" + SOLVE_CASE_BLOCK
    ASTRO.write_text(text, encoding="utf-8")
    print("  [ok]   solve_case добавлен")
    return 0


def patch_calc():
    print(f"\n[2] {CALC}")
    if not CALC.is_file():
        print(f"  [err] не найден")
        return 1
    text = CALC.read_text(encoding="utf-8")

    if 'def _record(' in text and '"case": None, "output": {}' in text:
        print("  [skip] _RESULT уже есть")
    else:
        backup = CALC.with_suffix(".py.v4.bak")
        if not backup.exists():
            shutil.copy2(CALC, backup)
            print(f"  [backup] {backup}")

        try:
            text = _apply(text, *PATCH_RESULT_INIT, "_RESULT + _record")
            text = _apply(text, *PATCH_PRINT_ORBIT_START, "_print_orbit_result start")
            text = _apply(text, *PATCH_PRINT_ORBIT_END, "_print_orbit_result end")
            text = _apply(text, *PATCH_DISPATCH, "_dispatch_solve")
            text = _apply(text, *PATCH_MAIN_JSON, "main --json")
            for i, (old, new) in enumerate(RECORD_PATCHES, 1):
                try:
                    text = _apply(text, old, new, f"_record #{i}")
                except RuntimeError as exc:
                    print(f"  [warn] {exc} — пропускаю")
        except RuntimeError as exc:
            print(f"  [err] {exc}")
            return 2

        CALC.write_text(text, encoding="utf-8")

    # Проверка синтаксиса
    try:
        compile(CALC.read_text(encoding="utf-8"), str(CALC), "exec")
        print("  [ok]   синтаксис корректен")
    except SyntaxError as exc:
        print(f"  [err] SyntaxError: {exc}")
        return 3
    return 0


def main():
    print("[patch v4] aero.solve_case + --json для всех 53")
    print("=" * 50)
    rc = 0
    rc |= patch_astrodynamics()
    rc |= patch_calc()
    print("\n" + "=" * 50)
    if rc == 0:
        print("[patch v4] Готово. Проверьте:")
        print("  pytest tests/ -v                       # 29+8 = 37 passed")
        print("  python3 cli/calculator.py --solve=47 --latex --json")
        print("  python3 cli/calculator.py --preset gso --json")
        print("  python3 -c \"from core.astrodynamics import solve_case; "
              "print(solve_case('1', a=7000, e=0.1))\""       )
    return rc


if __name__ == "__main__":
    sys.exit(main())