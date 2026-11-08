"""core/astrodynamics.py — Чистые функции орбитальных и астрономических расчётов.

Без I/O, без print, без global state. Каждая функция возвращает dict
с результатами. Используется CLI и тестами.

Константы — земные (если не указано иное).
"""

from __future__ import annotations

import math

from core.lambert import lambert_universal, lambert_universal_nrev  # noqa: E402

# ── Константы ──────────────────────────────────────────────────────────────
# v4.5: синхронизированы с core.base (единый источник истины).
# Fallback — если core.base недоступен (автономный импорт).
try:
    from core.base import MU_EARTH, R_EARTH, G0  # noqa: F401
except ImportError:
    MU_EARTH = 398_600.4418       # км³/с²
    R_EARTH = 6_378.0             # км (экваториальный радиус)
    G0 = 9.80665                  # м/с²

J2 = 1.08263e-3               # зональный коэффициент
T_SIDEREAL = 86_164.0905      # сидерические сутки, с
YEAR_S = 365.2422 * 86_400    # тропический год, с
N_SUN = 2 * math.pi / YEAR_S  # среднее движение Солнца, рад/с

AU_KM = 149_597_870.7
M_SUN = 1.98892e30
M_EARTH = 5.9722e24
M_MOON = 7.342e22
M_MARS = 6.4171e23
A_MOON_KM = 384_400.0
A_MARS_AU = 1.523679


# ═══════════════════════════════════════════════════════════════════════════
#  БАЗОВЫЕ ОРБИТАЛЬНЫЕ ЭЛЕМЕНТЫ
# ═══════════════════════════════════════════════════════════════════════════


def elements_from_a_e(a: float, e: float) -> dict:
    """Полные элементы эллиптической орбиты по (a, e)."""
    if a <= 0:
        raise ValueError("a должна быть > 0")
    if not (0 <= e < 1):
        raise ValueError("Нужно 0 ≤ e < 1")
    r_p = a * (1 - e)
    r_a = a * (1 + e)
    p = a * (1 - e * e)
    h = math.sqrt(MU_EARTH * p)
    eps = -MU_EARTH / (2 * a)
    T = 2 * math.pi * math.sqrt(a ** 3 / MU_EARTH)
    v_p = math.sqrt(MU_EARTH * (2 / r_p - 1 / a))
    v_a = math.sqrt(MU_EARTH * (2 / r_a - 1 / a))
    return {
        "a": a, "e": e, "r_p": r_p, "r_a": r_a, "p": p,
        "h": h, "eps": eps, "T": T, "v_p": v_p, "v_a": v_a,
        "n": 2 * math.pi / T,
    }


def elements_from_rp_ra(r_p: float, r_a: float) -> dict:
    """Полные элементы по радиусам перигея и апогея."""
    if r_p <= 0 or r_a < r_p:
        raise ValueError("Требуется r_p > 0 и r_a ≥ r_p")
    a = (r_p + r_a) / 2
    e = (r_a - r_p) / (r_a + r_p)
    return elements_from_a_e(a, e)


def elements_from_rp_e(r_p: float, e: float) -> dict:
    """По радиусу перигея и эксцентриситету."""
    if r_p <= 0 or not (0 <= e < 1):
        raise ValueError("r_p > 0, 0 ≤ e < 1")
    a = r_p / (1 - e)
    return elements_from_a_e(a, e)


def elements_from_ra_e(r_a: float, e: float) -> dict:
    """По радиусу апогея и эксцентриситету."""
    if r_a <= 0 or not (0 <= e < 1):
        raise ValueError("r_a > 0, 0 ≤ e < 1")
    a = r_a / (1 + e)
    return elements_from_a_e(a, e)


def elements_from_h_e(h: float, e: float) -> dict:
    """По моменту импульса и эксцентриситету."""
    if h <= 0 or not (0 <= e < 1):
        raise ValueError("h > 0, 0 ≤ e < 1")
    p = h * h / MU_EARTH
    a = p / (1 - e * e)
    return elements_from_a_e(a, e)


def elements_from_p_e(p: float, e: float) -> dict:
    """По фокальному параметру и эксцентриситету."""
    if p <= 0 or not (0 <= e < 1):
        raise ValueError("p > 0, 0 ≤ e < 1")
    a = p / (1 - e * e)
    return elements_from_a_e(a, e)


def elements_from_h_eps(h: float, eps: float) -> dict:
    """По моменту и удельной энергии (эллипс: eps < 0)."""
    if h == 0 or eps >= 0:
        raise ValueError("h ≠ 0, eps < 0")
    a = -MU_EARTH / (2 * eps)
    p = h * h / MU_EARTH
    val = 1 - p / a
    if val < -1e-9:
        raise ValueError("Данные несовместны (1 - p/a < 0)")
    e = math.sqrt(max(0.0, val))
    return elements_from_a_e(a, e)


def elements_from_h_a(h: float, a: float) -> dict:
    """По моменту и большой полуоси."""
    if h < 0 or a <= 0:
        raise ValueError("h ≥ 0, a > 0")
    p = h * h / MU_EARTH
    val = 1 - p / a
    if val < -1e-9:
        raise ValueError("Эллипса не существует (1 - p/a < 0)")
    e = math.sqrt(max(0.0, val))
    return elements_from_a_e(a, e)


def elements_from_T_circular(T: float) -> dict:
    """Круговая орбита по периоду (e = 0)."""
    if T <= 0:
        raise ValueError("T > 0")
    a = (MU_EARTH * T * T / (4 * math.pi ** 2)) ** (1 / 3)
    v = math.sqrt(MU_EARTH / a)
    return {"a": a, "e": 0.0, "r": a, "v": v, "T": T,
            "n": 2 * math.pi / T}


def elements_from_T_e(T: float, e: float) -> dict:
    """По периоду и эксцентриситету."""
    if T <= 0 or not (0 <= e < 1):
        raise ValueError("T > 0, 0 ≤ e < 1")
    a = (MU_EARTH * T * T / (4 * math.pi ** 2)) ** (1 / 3)
    return elements_from_a_e(a, e)


def elements_from_vp_va(v_p: float, v_a: float) -> dict:
    """По скоростям перигея и апогея."""
    if v_p <= 0 or v_a <= 0 or v_p <= v_a:
        raise ValueError("Нужно v_p > v_a > 0")
    e = (v_p - v_a) / (v_p + v_a)
    a = MU_EARTH / (v_p * v_a)
    return elements_from_a_e(a, e)


def elements_from_r_v_gamma(r: float, v: float, gamma_deg: float) -> dict:
    """По радиусу, скорости и углу траектории γ."""
    if r <= 0 or v <= 0:
        raise ValueError("r > 0, v > 0")
    eps = v * v / 2 - MU_EARTH / r
    if eps >= 0:
        raise ValueError("ε ≥ 0 — незамкнутая орбита")
    h = r * v * math.cos(math.radians(gamma_deg))
    if abs(h) < 1e-9:
        raise ValueError("γ = ±90° — радиальная траектория")
    a = -MU_EARTH / (2 * eps)
    p = h * h / MU_EARTH
    val = 1 - p / a
    if val < -1e-9:
        raise ValueError("Данные несовместны")
    e = math.sqrt(max(0.0, val))
    r_p, r_a = a * (1 - e), a * (1 + e)
    if not (r_p - 1e-3 <= r <= r_a + 1e-3):
        raise ValueError(f"r = {r:.1f} вне [{r_p:.1f}, {r_a:.1f}]")
    return elements_from_a_e(a, e)


def elements_from_rp_vp(r_p: float, v_p: float) -> dict:
    """По r_p и v_p — эллипс / парабола / гипербола."""
    if r_p <= 0 or v_p <= 0:
        raise ValueError("r_p > 0, v_p > 0")
    eps = v_p * v_p / 2 - MU_EARTH / r_p
    h = r_p * v_p
    p = h * h / MU_EARTH
    if eps < -1e-9:
        a = -MU_EARTH / (2 * eps)
        val = 1 - p / a
        if val < -1e-9:
            raise ValueError("Данные несовместны")
        e = math.sqrt(max(0.0, val))
        return {"kind": "ellipse", **elements_from_a_e(a, e)}
    elif abs(eps) <= 1e-9:
        return {"kind": "parabola", "e": 1.0, "r_p": r_p, "p": p,
                "C3": 0.0, "v_p": math.sqrt(2 * MU_EARTH / r_p)}
    else:
        a = -MU_EARTH / (2 * eps)
        val = 1 - p / a
        e = math.sqrt(max(1.0, val))
        C3 = 2 * eps
        v_inf = math.sqrt(C3)
        delta = 2 * math.asin(1 / e)
        return {"kind": "hyperbola", "a": a, "e": e, "p": p, "r_p": r_p,
                "C3": C3, "v_inf": v_inf, "v_p": v_p,
                "delta_deg": math.degrees(delta)}


def elements_from_state(r_vec, v_vec) -> dict:
    """Полные элементы из вектора состояния (2D или 3D, ECI)."""
    if len(r_vec) == 2:
        r_vec = (r_vec[0], r_vec[1], 0.0)
    if len(v_vec) == 2:
        v_vec = (v_vec[0], v_vec[1], 0.0)

    rx, ry, rz = r_vec
    vx, vy, vz = v_vec
    r = math.sqrt(rx * rx + ry * ry + rz * rz)
    v2 = vx * vx + vy * vy + vz * vz
    if r < 1e-9:
        raise ValueError("|r| = 0")

    hx = ry * vz - rz * vy
    hy = rz * vx - rx * vz
    hz = rx * vy - ry * vx
    h = math.sqrt(hx * hx + hy * hy + hz * hz)

    rv = rx * vx + ry * vy + rz * vz
    ex = ((v2 - MU_EARTH / r) * rx - rv * vx) / MU_EARTH
    ey = ((v2 - MU_EARTH / r) * ry - rv * vy) / MU_EARTH
    ez = ((v2 - MU_EARTH / r) * rz - rv * vz) / MU_EARTH
    e = math.sqrt(ex * ex + ey * ey + ez * ez)

    eps = v2 / 2 - MU_EARTH / r
    a = -MU_EARTH / (2 * eps) if abs(eps) > 1e-15 else float("inf")
    i_deg = math.degrees(math.acos(max(-1.0, min(1.0, hz / h)))) if h > 1e-12 else 0.0

    nx, ny = -hy, hx
    n = math.sqrt(nx * nx + ny * ny)
    Omega = math.degrees(math.atan2(ny, nx)) % 360 if n > 1e-12 else 0.0

    if n > 1e-12 and e > 1e-12:
        cos_w = (nx * ex + ny * ey) / (n * e)
        w = math.acos(max(-1.0, min(1.0, cos_w)))
        if ez < 0:
            w = 2 * math.pi - w
        omega = math.degrees(w) % 360
        cos_nu = (ex * rx + ey * ry + ez * rz) / (e * r)
        nu = math.acos(max(-1.0, min(1.0, cos_nu)))
        if rv < 0:
            nu = 2 * math.pi - nu
        nu_deg = math.degrees(nu) % 360
    elif n > 1e-12:
        cos_u = (nx * rx + ny * ry) / (n * r)
        u = math.acos(max(-1.0, min(1.0, cos_u)))
        if rz < 0:
            u = 2 * math.pi - u
        omega = 0.0
        nu_deg = math.degrees(u) % 360
    elif e > 1e-12:
        omega = math.degrees(math.atan2(ey, ex)) % 360
        cos_nu = (ex * rx + ey * ry) / (e * r)
        nu = math.acos(max(-1.0, min(1.0, cos_nu)))
        if rv < 0:
            nu = 2 * math.pi - nu
        nu_deg = math.degrees(nu) % 360
    else:
        omega = 0.0
        nu_deg = math.degrees(math.atan2(ry, rx)) % 360

    return {
        "r": r, "v": math.sqrt(v2), "h": h, "a": a, "e": e,
        "eps": eps, "i": i_deg, "Omega": Omega,
        "omega": omega, "nu": nu_deg,
    }


# ═══════════════════════════════════════════════════════════════════════════
#  МАНЁВРЫ
# ═══════════════════════════════════════════════════════════════════════════


def vis_viva(r: float, a: float) -> float:
    """v = √(μ(2/r − 1/a))."""
    if r <= 0 or a <= 0:
        raise ValueError("r > 0, a > 0")
    return math.sqrt(MU_EARTH * (2 / r - 1 / a))


def hohmann(r1: float, r2: float) -> dict:
    """Перелёт Хомана между круговыми орбитами."""
    if r1 <= 0 or r2 <= 0 or abs(r1 - r2) < 1e-6:
        raise ValueError("r1, r2 > 0 и не равны")
    a_t = (r1 + r2) / 2
    v1c, v2c = math.sqrt(MU_EARTH / r1), math.sqrt(MU_EARTH / r2)
    v1t = math.sqrt(MU_EARTH * (2 / r1 - 1 / a_t))
    v2t = math.sqrt(MU_EARTH * (2 / r2 - 1 / a_t))
    dv1 = (v1t - v1c) * 1000
    dv2 = (v2c - v2t) * 1000
    t = math.pi * math.sqrt(a_t ** 3 / MU_EARTH)
    return {
        "r1": r1, "r2": r2, "a_t": a_t,
        "v1c": v1c, "v2c": v2c, "v1t": v1t, "v2t": v2t,
        "dv1_mps": dv1, "dv2_mps": dv2,
        "dv_total_mps": abs(dv1) + abs(dv2),
        "t_transfer_s": t,
    }


def bielliptic(r1: float, r2: float, r_b: float) -> dict:
    """Биэллиптический перелёт через промежуточный радиус r_b."""
    if r1 <= 0 or r2 <= 0 or r_b <= max(r1, r2):
        raise ValueError("r_b > max(r1, r2)")
    v1c = math.sqrt(MU_EARTH / r1)
    v2c = math.sqrt(MU_EARTH / r2)
    a1, a2 = (r1 + r_b) / 2, (r2 + r_b) / 2
    v1t = math.sqrt(MU_EARTH * (2 / r1 - 1 / a1))
    v_b1 = math.sqrt(MU_EARTH * (2 / r_b - 1 / a1))
    v_b2 = math.sqrt(MU_EARTH * (2 / r_b - 1 / a2))
    v2t = math.sqrt(MU_EARTH * (2 / r2 - 1 / a2))
    b1 = (v1t - v1c) * 1000
    b2 = (v_b2 - v_b1) * 1000
    b3 = (v2c - v2t) * 1000
    a_h = (r1 + r2) / 2
    v1h = math.sqrt(MU_EARTH * (2 / r1 - 1 / a_h))
    v2h = math.sqrt(MU_EARTH * (2 / r2 - 1 / a_h))
    dv_h = abs((v1h - v1c) * 1000) + abs((v2c - v2h) * 1000)
    return {
        "dv1_mps": b1, "dv2_mps": b2, "dv3_mps": b3,
        "dv_total_mps": abs(b1) + abs(b2) + abs(b3),
        "hohmann_total_mps": dv_h,
        "bielliptic_is_better": abs(b1) + abs(b2) + abs(b3) < dv_h,
    }


def tsiolkovsky(dv_mps: float, m0_kg: float, isp_s: float) -> dict:
    """m_fuel по Δv и массе. Проверяет физичность."""
    if dv_mps < 0 or m0_kg <= 0 or isp_s <= 0:
        raise ValueError("Δv ≥ 0, m0 > 0, Isp > 0")
    ve = isp_s * G0
    m1 = m0_kg * math.exp(-dv_mps / ve)
    fuel = m0_kg - m1
    if fuel >= m0_kg:
        raise ValueError("Требуемое топливо превышает массу")
    return {"ve_mps": ve, "m_final_kg": m1, "m_fuel_kg": fuel,
            "fuel_fraction": fuel / m0_kg}


def inverse_tsiolkovsky(fuel_kg: float, m0_kg: float, isp_s: float) -> dict:
    """Δv по топливу и массе."""
    if fuel_kg < 0 or m0_kg <= 0 or isp_s <= 0 or fuel_kg >= m0_kg:
        raise ValueError("0 ≤ m_fuel < m0, Isp > 0")
    ve = isp_s * G0
    m1 = m0_kg - fuel_kg
    dv = ve * math.log(m0_kg / m1)
    return {"ve_mps": ve, "m_final_kg": m1, "dv_mps": dv}


# ═══════════════════════════════════════════════════════════════════════════
#  J2-ПРЕЦЕССИЯ (новый пункт 47)
# ═══════════════════════════════════════════════════════════════════════════


def j2_precession(a: float, e: float, i_deg: float) -> dict:
    """Прецессия узла, перигея и среднего движения от J2.

    dΩ/dt  = −(3/2) J2 n (R/p)² cos i
    dω/dt  = (3/4) J2 n (R/p)² (5cos²i − 1)
    dM₀/dt = (3/4) J2 n (R/p)² √(1−e²) (3cos²i − 1)
    """
    if a <= 0 or not (0 <= e < 1) or not (0 <= i_deg <= 180):
        raise ValueError("a > 0, 0 ≤ e < 1, 0 ≤ i ≤ 180")
    i = math.radians(i_deg)
    n = math.sqrt(MU_EARTH / a ** 3)
    p = a * (1 - e * e)
    base = 0.75 * J2 * n * (R_EARTH / p) ** 2

    dOmega = -2 * base * math.cos(i)
    domega = base * (5 * math.cos(i) ** 2 - 1)
    dM = base * math.sqrt(1 - e * e) * (3 * math.cos(i) ** 2 - 1)

    return {
        "a": a, "e": e, "i_deg": i_deg, "p": p, "n": n,
        "T": 2 * math.pi / n,
        "dOmega_rad_s": dOmega,
        "dOmega_deg_day": math.degrees(dOmega) * 86400,
        "dOmega_deg_year": math.degrees(dOmega) * YEAR_S,
        "domega_rad_s": domega,
        "domega_deg_day": math.degrees(domega) * 86400,
        "domega_deg_year": math.degrees(domega) * YEAR_S,
        "dM_rad_s": dM,
        "dM_deg_day": math.degrees(dM) * 86400,
        "dM_deg_year": math.degrees(dM) * YEAR_S,
    }


# ═══════════════════════════════════════════════════════════════════════════
#  СТАНЦИЯ: РАДАР, ДАЛЬНОСТЬ, УГОЛ (48)
# ═══════════════════════════════════════════════════════════════════════════


def radar_track(rho_km: float, rho_dot_km_s: float, el_deg: float,
                station_alt_km: float = 0.0) -> dict:
    """Оценка орбитальных параметров по измерениям радиолокатора.

    Дано: наклонная дальность ρ, радиальная скорость ρ̇, угол места el.
    Находим: r = √(r_st² + ρ² + 2·r_st·ρ·cos(el)), затем vis-viva.
    """
    if rho_km <= 0:
        raise ValueError("ρ > 0")
    r_st = R_EARTH + station_alt_km
    el = math.radians(el_deg)

    # r² = r_st² + ρ² + 2·r_st·ρ·cos(el)  (косинус от вертикали)
    r2 = r_st ** 2 + rho_km ** 2 + 2 * r_st * rho_km * math.cos(el + math.pi / 2)
    # Внимание: el — от горизонта, поэтому проекция на радиус станции = ρ·sin(el)
    r2 = r_st ** 2 + rho_km ** 2 + 2 * r_st * rho_km * math.sin(el)
    if r2 <= 0:
        raise ValueError("Некорректная геометрия")
    r = math.sqrt(r2)

    # Радиальная скорость ṙ ≈ ρ̇ для малых углов (приближение)
    # Более точно: ṙ = ρ̇·sin(el) + (ρ·v_t/r)·cos(el)
    # Здесь упрощаем: считаем ρ̇ ≈ ṙ для оценки
    rdot = rho_dot_km_s

    # Оценка скорости через vis-viva невозможна без a — используем 2-ю космическую
    # Даём оценку ε = v²/2 − μ/r через радиальную и тангенциальную компоненты
    # v_t ≈ (ρ·cos(el)) / t_acq — неизвестно, поэтому даём верхнюю/нижнюю оценку
    v_esc_local = math.sqrt(2 * MU_EARTH / r)
    v_circ_local = math.sqrt(MU_EARTH / r)

    return {
        "range_km": rho_km, "range_rate_km_s": rho_dot_km_s,
        "elevation_deg": el_deg, "station_radius_km": r_st,
        "r_km": r, "H_km": r - R_EARTH, "rdot_km_s": rdot,
        "v_esc_local_km_s": v_esc_local,
        "v_circ_local_km_s": v_circ_local,
        "note": "v_full требует дополнительного измерения (угол азимута или доплер)",
    }


# ═══════════════════════════════════════════════════════════════════════════
#  БЮДЖЕТ МИССИИ (49–51)
# ═══════════════════════════════════════════════════════════════════════════


def ascent_budget(H_target_km: float, isp_s: float, m0_kg: float,
                  launch_lat_deg: float = 0.0,
                  gravity_loss_km_s: float = 1.7,
                  drag_loss_km_s: float = 0.15) -> dict:
    """Бюджет выведения на круговую орбиту.

    Δv_circ = √(μ/(R⊕+H)) − v_rot(lat)
    Δv_total = Δv_circ + gravity_loss + drag_loss
    """
    if H_target_km < 0 or isp_s <= 0 or m0_kg <= 0:
        raise ValueError("H ≥ 0, Isp > 0, m0 > 0")
    r_target = R_EARTH + H_target_km
    v_orbit = math.sqrt(MU_EARTH / r_target)
    v_rot = 0.4651 * math.cos(math.radians(launch_lat_deg))  # км/с
    dv_circ_km_s = v_orbit - v_rot
    dv_total_km_s = dv_circ_km_s + gravity_loss_km_s + drag_loss_km_s

    try:
        fuel = tsiolkovsky(dv_total_km_s * 1000, m0_kg, isp_s)
    except ValueError as exc:
        raise ValueError(f"Топлива недостаточно: {exc}")

    return {
        "r_target_km": r_target,
        "v_orbit_km_s": v_orbit,
        "v_rot_km_s": v_rot,
        "dv_circ_km_s": dv_circ_km_s,
        "gravity_loss_km_s": gravity_loss_km_s,
        "drag_loss_km_s": drag_loss_km_s,
        "dv_total_km_s": dv_total_km_s,
        "dv_total_mps": dv_total_km_s * 1000,
        "m_fuel_kg": fuel["m_fuel_kg"],
        "fuel_fraction": fuel["fuel_fraction"],
    }


def max_payload(dv_mps: float, isp_s: float, m0_kg: float, m_dry_kg: float) -> dict:
    """Максимальная полезная нагрузка (без ступеней)."""
    if dv_mps < 0 or isp_s <= 0 or m0_kg <= 0 or m_dry_kg < 0:
        raise ValueError("Δv ≥ 0, Isp > 0, m0 > 0, m_dry ≥ 0")
    tsi = tsiolkovsky(dv_mps, m0_kg, isp_s)
    m_payload = m0_kg - tsi["m_fuel_kg"] - m_dry_kg
    return {
        "ve_mps": tsi["ve_mps"], "m_fuel_kg": tsi["m_fuel_kg"],
        "m_final_kg": tsi["m_final_kg"], "m_dry_kg": m_dry_kg,
        "m_payload_kg": m_payload,
        "feasible": m_payload > 0,
    }


def staged_rocket(dv_total_mps: float, n_stages: int, isp_s: float,
                  epsilon: float) -> dict:
    """Ступенчатая ракета с одинаковыми Isp и ε.

    m_pl/m0 = [exp(−Δv/(N·Isp·g0)) − ε]^N
    """
    if dv_total_mps <= 0 or n_stages < 1 or isp_s <= 0:
        raise ValueError("Δv > 0, N ≥ 1, Isp > 0")
    if not (0 < epsilon < 1):
        raise ValueError("0 < ε < 1")

    ve = isp_s * G0
    dv_per_stage = dv_total_mps / n_stages
    ratio_per_stage = math.exp(-dv_per_stage / ve) - epsilon
    if ratio_per_stage <= 0:
        raise ValueError(f"При N={n_stages} ступеней масса не растёт — увеличьте Isp или уменьшите ε")
    payload_ratio = ratio_per_stage ** n_stages
    return {
        "n_stages": n_stages, "isp_s": isp_s, "epsilon": epsilon,
        "dv_total_mps": dv_total_mps,
        "dv_per_stage_mps": dv_per_stage,
        "ve_mps": ve,
        "payload_ratio": payload_ratio,
        "structural_ratio_total": epsilon ** n_stages,
    }


def best_staging(dv_total_mps: float, isp_s: float, epsilon: float,
                 max_stages: int = 5) -> list[dict]:
    """Все варианты N=1..max_stages для выбора оптимума."""
    out = []
    for n in range(1, max_stages + 1):
        try:
            out.append(staged_rocket(dv_total_mps, n, isp_s, epsilon))
        except ValueError:
            continue
    return out


# ═══════════════════════════════════════════════════════════════════════════
#  ТОЧКИ L1/L2 (52) — CR3BP через Ньютона
# ═══════════════════════════════════════════════════════════════════════════


def cr3bp_lagrange(mu: float, point: str = "L1",
                   tol: float = 1e-12, max_iter: int = 50) -> float:
    """Точное положение L1/L2 в CR3BP (доля расстояния от малого тела).

    Уравнение: x − (1−μ)(x+μ)/r1³ − μ(x−1+μ)/r2³ = 0
    Возвращает x_L (в единицах большой полуоси системы).
    """
    if not (0 < mu < 0.5):
        raise ValueError("0 < μ < 0.5")
    if point not in ("L1", "L2", "L3"):
        raise ValueError("point ∈ {L1, L2, L3}")

    guess_off = (mu / 3) ** (1 / 3)
    if point == "L1":
        x = 1 - mu - guess_off
    elif point == "L2":
        x = 1 - mu + guess_off
    else:  # L3
        x = -mu - 1 + (7 * mu / 12) ** (1 / 3)

    for _ in range(max_iter):
        if point == "L1":
            r1 = x + mu
            r2 = 1 - mu - x
            f = x - (1 - mu) / (r1 * r1) + mu / (r2 * r2)
            fp = 1 + 2 * (1 - mu) / (r1 ** 3) + 2 * mu / (r2 ** 3)
        elif point == "L2":
            r1 = x + mu
            r2 = x - 1 + mu
            f = x - (1 - mu) / (r1 * r1) - mu / (r2 * r2)
            fp = 1 + 2 * (1 - mu) / (r1 ** 3) + 2 * mu / (r2 ** 3)
        else:  # L3
            r1 = -(x + mu)
            r2 = 1 - mu - x
            f = x + (1 - mu) / (r1 * r1) + mu / (r2 * r2)
            fp = 1 - 2 * (1 - mu) / (r1 ** 3) + 2 * mu / (r2 ** 3)

        dx = f / fp
        x -= dx
        if abs(dx) < tol:
            break

    return x


def lagrange_distance_km(mu: float, big_a_km: float, point: str = "L1") -> dict:
    """Расстояние от малого тела до L1/L2/L3 в км."""
    x_L = cr3bp_lagrange(mu, point)
    x_small_body = 1 - mu
    dist_from_small = abs(x_L - x_small_body) * big_a_km
    dist_from_big = abs(x_L + mu) * big_a_km
    return {
        "point": point,
        "x_L_normalized": x_L,
        "x_small_body": x_small_body,
        "dist_from_small_km": dist_from_small,
        "dist_from_big_km": dist_from_big,
        "big_a_km": big_a_km,
    }


# ═══════════════════════════════════════════════════════════════════════════
#  ЗАМОРОЖЕННЫЕ ОРБИТЫ / КРИТИЧЕСКОЕ НАКЛОНЕНИЕ (53)
# ═══════════════════════════════════════════════════════════════════════════


CRITICAL_INC_DEG = math.degrees(math.acos(1 / math.sqrt(5)))  # ≈ 63.4349°


def frozen_orbit_info(a: float, e: float, i_deg: float) -> dict:
    """Информация о замороженной орбите и критическом наклонении."""
    if a <= 0 or not (0 <= e < 1) or not (0 <= i_deg <= 180):
        raise ValueError("a > 0, 0 ≤ e < 1, 0 ≤ i ≤ 180")
    j2 = j2_precession(a, e, i_deg)
    is_critical = abs(i_deg - CRITICAL_INC_DEG) < 0.5
    is_frozen = is_critical and e < 0.01  # малый эксцентриситет + критическое i
    return {
        **j2,
        "critical_inc_deg": CRITICAL_INC_DEG,
        "is_near_critical": is_critical,
        "is_frozen_like": is_frozen,
        "deviation_deg": i_deg - CRITICAL_INC_DEG,
    }


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
    "46": {"name": "Вектор → элементы", "inputs": ["x", "y", "z", "vx", "vy", "vz"]},
    "47": {"name": "J2-прецессия", "inputs": ["H", "e", "i"]},
    "48": {"name": "Радар", "inputs": ["rho", "rho_dot", "el"]},
    "49": {"name": "Бюджет", "inputs": ["H", "isp", "m0"]},
    "50": {"name": "Payload", "inputs": ["dv", "isp", "m0", "m_dry"]},
    "51": {"name": "Ступени", "inputs": ["dv", "isp", "epsilon"]},
    "52": {"name": "CR3BP", "inputs": ["system"]},
    "53": {"name": "Frozen", "inputs": ["H", "e", "i"]},
    "54": {"name": "Ламберт N витков", "inputs": ["H1", "H2", "dnu_deg", "dt", "n_max"]},
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
    }


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


def _s54(H1, H2, dnu_deg, dt, n_max=5):
    r1, r2 = H1 + R_EARTH, H2 + R_EARTH
    dnu = math.radians(dnu_deg)
    sols = lambert_universal_nrev(r1, r2, dnu, dt, n_max=int(n_max))
    if not sols:
        raise ValueError("Нет решений для данных параметров")
    for s in sols:
        s["v1_vec"] = list(s["v1_vec"])
        s["v2_vec"] = list(s["v2_vec"])
    return {"solutions": sols, "n_found": len(sols),
            "r1_km": r1, "r2_km": r2, "dnu_deg": dnu_deg, "dt_s": dt}


def _s27(H1, H2, dnu_deg, dt):
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
    }


_SOLVERS = {str(i): globals()[f"_s{i}"] for i in range(1, 55)}


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
