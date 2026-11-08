"""cli/calculator.py — Интерактивный калькулятор орбитальных и астрономических расчётов."""


from __future__ import annotations

# ── bootstrap sys.path: работает при `python cli/calculator.py` из любого CWD ──
import sys as _sys
from pathlib import Path as _Path

_ROOT = _Path(__file__).resolve().parent.parent
if str(_ROOT) not in _sys.path:
    _sys.path.insert(0, str(_ROOT))
del _sys, _Path, _ROOT

# ── Минимальная замена _c (совместима с launcher._c) ──
import os as _os

if _os.name == "nt" and not _os.environ.get("WT_SESSION"):
    _CC = {"g": "", "y": "", "r": "", "b": "", "c": "", "d": "", "0": ""}
else:
    _CC = {
        "g": "\033[32m", "y": "\033[33m", "r": "\033[31m",
        "b": "\033[34m", "c": "\033[36m", "d": "\033[2m", "0": "\033[0m",
    }


def _c(text: str, color: str = "0") -> str:
    """Цветной текст. На старом Windows или без TTY — без escape-кодов."""
    code = _CC.get(color, "")
    reset = _CC["0"]
    return f"{code}{text}{reset}" if code else text
import argparse
import contextlib
import json
import math
import sys

try:
    import matplotlib  # noqa: F401

    HAS_PLOT = True
except ImportError:
    HAS_PLOT = False

_LAST_RESULT = None
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

from core.base import (
    G0,
    MU_EARTH,
    R_EARTH,
    _t,
    check_orbit,
    ecc,
    logger,
    period,
    rf,
    ri,
    set_lang,
    setup_logging,
    sma,
    vel_at,
)
from core.optimization import phasing_orbit
from core import astrodynamics as aero
from core.latex_formulas import get_formulas as _latex_get
from gui.animations import animate_hohmann, animate_phasing
from gui.plots import (
    _ask_plot,
    plot_bielliptic,
    plot_circular,
    plot_escape,
    plot_hohmann,
    plot_orbit_params,
    plot_velocity_point,
)

# ── Астрономические константы ──────────────────────────────────────────────
AU_KM = 149_597_870.7
M_SUN = 1.98892e30
M_EARTH = 5.9722e24
M_MOON = 7.342e22
M_MARS = 6.4171e23
A_MOON_KM = 384_400.0
A_MARS_AU = 1.523679

J2 = 1.08263e-3
T_SIDEREAL = 86_164.0905
YEAR_S = 365.2422 * 86_400
N_SUN = 2 * math.pi / YEAR_S


def __getattr__(name: str):
    if name == "LANG":
        from core import base
        return base.LANG
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


# ═══════════════════════════════════════════════════════════════════════════
#  ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ═══════════════════════════════════════════════════════════════════════════


def _elements_from_state(r_vec, v_vec):
    """Полные орбитальные элементы из вектора состояния (ECI)."""
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
    Omega_deg = math.degrees(math.atan2(ny, nx)) % 360 if n > 1e-12 else 0.0

    if n > 1e-12 and e > 1e-12:
        cos_w = (nx * ex + ny * ey) / (n * e)
        w = math.acos(max(-1.0, min(1.0, cos_w)))
        if ez < 0:
            w = 2 * math.pi - w
        omega_deg = math.degrees(w) % 360
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
        omega_deg = 0.0
        nu_deg = math.degrees(u) % 360
    else:
        if e > 1e-12:
            omega_deg = math.degrees(math.atan2(ey, ex)) % 360
            cos_nu = (ex * rx + ey * ry) / (e * r)
            nu = math.acos(max(-1.0, min(1.0, cos_nu)))
            if rv < 0:
                nu = 2 * math.pi - nu
            nu_deg = math.degrees(nu) % 360
        else:
            omega_deg = 0.0
            nu_deg = math.degrees(math.atan2(ry, rx)) % 360

    return {
        "r": r, "v": math.sqrt(v2), "h": h, "a": a, "e": e,
        "eps": eps, "i": i_deg, "Omega": Omega_deg,
        "omega": omega_deg, "nu": nu_deg,
    }


def _lambert_universal(r1, r2, dnu, dt):
    """Задача Ламберта (0 rev) в 2D-плоскости."""
    if not (0 < dnu < 2 * math.pi) or dt <= 0:
        return None

    r1_vec = (r1, 0.0)
    r2_vec = (r2 * math.cos(dnu), r2 * math.sin(dnu))

    cos_dnu = math.cos(dnu)
    A = 0.0 if abs(1 - cos_dnu) < 1e-15 else math.sin(dnu) * math.sqrt(r1 * r2 / (1 - cos_dnu))

    def _CS(z):
        if z > 1e-8:
            sz = math.sqrt(z)
            return (1 - math.cos(sz)) / z, (sz - math.sin(sz)) / (sz ** 3)
        if z < -1e-8:
            sz = math.sqrt(-z)
            return (math.cosh(sz) - 1) / (-z), (math.sinh(sz) - sz) / (sz ** 3)
        return 0.5, 1.0 / 6.0

    def F(z):
        C, S = _CS(z)
        if C < 1e-15:
            return None
        y = r1 + r2 + A * (z * S - 1) / math.sqrt(C)
        if y < 0:
            return None
        return math.sqrt(MU_EARTH) * dt - (y / C) ** 1.5 * S - A * math.sqrt(y)

    z_lo, z_hi = -4 * math.pi ** 2, 4 * math.pi ** 2
    f_lo, f_hi = F(z_lo), F(z_hi)
    if f_lo is None or f_hi is None or f_lo * f_hi > 0:
        return None

    z = 0.0
    for _ in range(200):
        z_mid = (z_lo + z_hi) / 2
        f_mid = F(z_mid)
        if f_mid is None:
            z_hi = z_mid
            continue
        if abs(f_mid) < 1e-8 or (z_hi - z_lo) < 1e-12:
            z = z_mid
            break
        if f_lo * f_mid < 0:
            z_hi = z_mid
        else:
            z_lo = z_mid
            f_lo = f_mid
    else:
        z = (z_lo + z_hi) / 2

    C, S = _CS(z)
    y = r1 + r2 + A * (z * S - 1) / math.sqrt(C)
    if y < 0:
        return None

    f = 1 - y / r1
    g = A * math.sqrt(y / MU_EARTH)
    g_dot = 1 - y / r2
    if abs(g) < 1e-15:
        return None

    v1_vec = ((r2_vec[0] - f * r1_vec[0]) / g, (r2_vec[1] - f * r1_vec[1]) / g)
    v2_vec = ((g_dot * r2_vec[0] - r1_vec[0]) / g, (g_dot * r2_vec[1] - r1_vec[1]) / g)
    return v1_vec, v2_vec


# ═══════════════════════════════════════════════════════════════════════════
#  ИСХОДНЫЕ ФУНКЦИИ (основное меню 1–11)
# ═══════════════════════════════════════════════════════════════════════════


# ── v4.3: делегирование в core.lambert ──
def _lambert_universal(r1, r2, dnu, dt):
    """Обёртка (v4.3): делегирует в core.lambert.lambert_universal."""
    return aero.lambert_universal(r1, r2, dnu, dt)


def calc_orbit_params() -> None:
    logger.info(_t("log_calc_started"))
    print("\n  " + _t("hdr_orbit_params") + "\n")
    ap = rf(_t("prompt_ap"))
    pe = rf(_t("prompt_pe"))
    ok, msg = check_orbit(ap, pe)
    if not ok:
        print(f"  {msg}")
        return
    a, e = sma(ap, pe), ecc(ap, pe)
    T = period(ap, pe)
    vp, va = vel_at(ap, pe, "perigee"), vel_at(ap, pe, "apogee")
    p = a * (1 - e**2)
    h = math.sqrt(MU_EARTH * p)
    energy = -MU_EARTH / (2 * a)
    print(f"\n  Полуось a:        {a:.3f} км")
    print(f"  Эксцентриситет e: {e:.6f}")
    print(f"  Фок. параметр p:  {p:.3f} км")
    print(f"  Период T:         {T / 60:.4f} мин ({T:.2f} с)")
    print(f"  v перигея:        {vp:.4f} км/с ({vp * 1000:.1f} м/с)")
    print(f"  v апогея:         {va:.4f} км/с ({va * 1000:.1f} м/с)")
    print(f"  v средняя:        {math.sqrt(MU_EARTH / a):.4f} км/с")
    print(f"  Угловая скорость: {2 * math.pi / T:.6f} рад/с")
    print(f"  Спец. энергия:    {energy:.4f} км²/с²")
    print(f"  Момент импульса:  {h:.4f} км²/с\n")
    if _ask_plot():
        plot_orbit_params(ap, pe)


def calc_velocity_point() -> None:
    print("\n  " + _t("hdr_velocity") + "\n")
    ap = rf("  Апогей (Ap), км: ")
    pe = rf("  Перигей (Pe), км: ")
    ok, msg = check_orbit(ap, pe)
    if not ok:
        print(f"  {msg}")
        return
    print("\n  Точка: p — перигей, a — апогей, r — произвольный радиус")
    pt = input("  Выбор: ").strip().lower()
    if pt == "p":
        v, r, name = vel_at(ap, pe, "perigee"), pe + R_EARTH, "перигее"
    elif pt == "a":
        v, r, name = vel_at(ap, pe, "apogee"), ap + R_EARTH, "апогее"
    elif pt == "r":
        r = rf("  Радиус от центра Земли, км: ")
        if r < R_EARTH:
            logger.warning(_t("log_radius_below_earth"))
            return
        a = sma(ap, pe)
        if 2 / r - 1 / a < 0:
            logger.warning(_t("log_point_outside_orbit"))
            return
        v = math.sqrt(MU_EARTH * (2 / r - 1 / a))
        name = f"r = {r:.1f} км"
    else:
        logger.warning(_t("log_invalid_params"))
        return
    print(f"\n  Орбита: {ap:.1f} × {pe:.1f} км")
    print(f"  Точка: {name}")
    print(f"  Высота: {r - R_EARTH:.1f} км")
    print(f"  Скорость: {v:.4f} км/с ({v * 1000:.1f} м/с)\n")
    _record(r_km=r, v_km_s=v, point=name)
    if _ask_plot():
        plot_velocity_point(ap, pe, r, v, name)


def calc_circular() -> None:
    print("\n  " + _t("hdr_circular") + "\n")
    alt = rf(_t("prompt_alt"))
    if alt < 0:
        logger.warning(_t("msg_neg_alt"))
        return
    r = alt + R_EARTH
    v = math.sqrt(MU_EARTH / r)
    T = 2 * math.pi * math.sqrt(r**3 / MU_EARTH)
    print(f"\n  Высота:       {alt:.1f} км")
    print(f"  Радиус:       {r:.1f} км")
    print(f"  Скорость:     {v:.4f} км/с ({v * 1000:.1f} м/с)")
    print(f"  Период:       {T / 60:.4f} мин")
    print(f"  n:            {2 * math.pi / T:.6f} рад/с\n")
    _record(r_km=r, v_km_s=v, T_s=T, n_rad_s=2 * math.pi / T)
    if _ask_plot():
        plot_circular(alt)


def calc_hohmann() -> None:
    print("\n  " + _t("hdr_hohmann") + "\n")
    h1 = rf(_t("prompt_h1"))
    h2 = rf(_t("prompt_h2"))
    if abs(h1 - h2) < 0.001:
        print("  " + _t("msg_same_orbits"))
        return
    if h1 < 0 or h2 < 0:
        logger.warning(_t("log_neg_altitude"))
        return
    r1, r2 = h1 + R_EARTH, h2 + R_EARTH
    a_trans = (r1 + r2) / 2
    v1_c, v2_c = math.sqrt(MU_EARTH / r1), math.sqrt(MU_EARTH / r2)
    v1_t = math.sqrt(MU_EARTH * (2 / r1 - 1 / a_trans))
    v2_t = math.sqrt(MU_EARTH * (2 / r2 - 1 / a_trans))
    dv1 = (v1_t - v1_c) * 1000
    dv2 = (v2_c - v2_t) * 1000
    t_trans = math.pi * math.sqrt(a_trans**3 / MU_EARTH)
    print(f"\n  Орбита 1: {h1:.1f} км → Орбита 2: {h2:.1f} км")
    print(f"  Импульс 1 (старт):  {dv1:+.2f} м/с")
    print(f"  Импульс 2 (финиш): {dv2:+.2f} м/с")
    print(f"  Суммарный |dv|:     {abs(dv1) + abs(dv2):.2f} м/с")
    print(f"  Время перелёта:     {t_trans / 60:.2f} мин ({t_trans / 3600:.2f} ч)")
    print(f"  Промежуточная:      {max(h1, h2):.1f} × {min(h1, h2):.1f} км\n")
    _record(r1_km=r1, r2_km=r2, a_t_km=a_trans, dv1_mps=dv1, dv2_mps=dv2,
            dv_total_mps=abs(dv1) + abs(dv2), t_transfer_s=t_trans)
    if _ask_plot():
        plot_hohmann(h1, h2, dv1, dv2)


def calc_bielliptic() -> None:
    print("\n  " + _t("hdr_bielliptic") + "\n")
    h1 = rf("  Высота орбиты 1, км: ")
    h2 = rf("  Высота орбиты 2, км: ")
    h_bi = rf("  Промежуточная высота, км: ")
    if h_bi <= max(h1, h2):
        logger.warning(_t("log_intermediate_too_low"))
        return
    if h1 < 0 or h2 < 0:
        logger.warning(_t("log_neg_altitude"))
        return
    r1, r2, rb = h1 + R_EARTH, h2 + R_EARTH, h_bi + R_EARTH
    v1c, v2c = math.sqrt(MU_EARTH / r1), math.sqrt(MU_EARTH / r2)
    a1, a2 = (r1 + rb) / 2, (r2 + rb) / 2
    b1 = (math.sqrt(MU_EARTH * (2 / r1 - 1 / a1)) - v1c) * 1000
    v_a1 = math.sqrt(MU_EARTH * (2 / rb - 1 / a1))
    v_a2 = math.sqrt(MU_EARTH * (2 / rb - 1 / a2))
    b2 = (v_a2 - v_a1) * 1000
    b3 = (v2c - math.sqrt(MU_EARTH * (2 / r2 - 1 / a2))) * 1000
    total = abs(b1) + abs(b2) + abs(b3)
    a_h = (r1 + r2) / 2
    dv_h = abs((math.sqrt(MU_EARTH * (2 / r1 - 1 / a_h)) - v1c) * 1000) + abs(
        (v2c - math.sqrt(MU_EARTH * (2 / r2 - 1 / a_h))) * 1000
    )
    print(f"\n  Орбита 1: {h1:.1f} → Орбита 2: {h2:.1f} через {h_bi:.1f} км")
    print(f"  Импульс 1: {b1:+.2f} м/с")
    print(f"  Импульс 2: {b2:+.2f} м/с")
    print(f"  Импульс 3: {b3:+.2f} м/с")
    print(f"  Суммарный |dv|:  {total:.2f} м/с")
    print(f"  Хоман (для сравнения): {dv_h:.2f} м/с")
    if total < dv_h:
        print(f"  => Биэллиптический выгоднее на {dv_h - total:.2f} м/с")
    else:
        print(f"  => Хоман выгоднее на {total - dv_h:.2f} м/с")
    print()
    if _ask_plot():
        plot_bielliptic(h1, h2, h_bi, b1, b2, b3)


def calc_tsiolkovsky() -> None:
    print("\n  --- ЦИОЛКОВСКИЙ: dv → ТОПЛИВО ---\n")
    dv = rf("  dv, м/с: ")
    mass = rf(_t("prompt_mass"))
    isp = rf(_t("prompt_isp"))
    thrust = rf("  Тяга двигателя, Н (0 = не считать время): ")
    if dv < 0:
        dv = abs(dv)
    if mass <= 0:
        logger.warning(_t("log_mass_positive"))
        return
    if isp <= 0:
        logger.warning(_t("log_isp_positive"))
        return
    ve = isp * G0
    fuel = mass * (1 - math.exp(-dv / ve))
    if fuel >= mass:
        logger.warning(_t("log_fuel_exceeds_mass"))
        return
    print(f"\n  dv:                {dv:.1f} м/с")
    print(f"  Масса нач.:        {mass:.1f} кг")
    print(f"  Isp:               {isp:.0f} с")
    print(f"  Скорость истеч.:   {ve:.1f} м/с")
    print(f"  Топливо:           {fuel:.3f} кг")
    print(f"  Масса кон.:        {mass - fuel:.1f} кг")
    if thrust > 0:
        burn_time = dv * (mass - fuel / 2) / thrust
        print(f"  Тяга:              {thrust:.0f} Н")
        print(f"  Время работы:      {burn_time:.2f} с")
    _record(ve_mps=ve, m_fuel_kg=fuel, m_final_kg=mass - fuel, fuel_fraction=fuel / mass)
    print()


def calc_inverse_ts() -> None:
    print("\n  --- ОБРАТНЫЙ ЦИОЛКОВСКИЙ: ТОПЛИВО → dv ---\n")
    fuel = rf(_t("prompt_fuel"))
    mass = rf("  Масса корабля, кг: ")
    isp = rf("  Удельный импульс (Isp), с: ")
    if fuel < 0:
        logger.warning(_t("log_fuel_negative"))
        return
    if mass <= 0:
        logger.warning(_t("log_mass_positive"))
        return
    if isp <= 0:
        logger.warning(_t("log_isp_positive"))
        return
    if fuel >= mass:
        logger.warning(_t("log_fuel_ge_mass"))
        return
    ve = isp * G0
    dv = ve * math.log(mass / (mass - fuel))
    print(f"\n  Топливо:           {fuel:.1f} кг")
    print(f"  Масса нач.:        {mass:.1f} кг")
    print(f"  Isp:               {isp:.0f} с")
    print(f"  Скорость истеч.:   {ve:.1f} м/с")
    print(f"  dv:                {dv:.2f} м/с\n")
    _record(ve_mps=ve, m_final_kg=mass - fuel, dv_mps=dv)


def calc_escape() -> None:
    print("\n  " + _t("hdr_escape") + "\n")
    alt = rf("  Высота, км: ")
    if alt < 0:
        logger.warning(_t("log_neg_altitude"))
        return
    r = alt + R_EARTH
    v_esc = math.sqrt(2 * MU_EARTH / r)
    v_circ = math.sqrt(MU_EARTH / r)
    print(f"\n  Высота:          {alt:.1f} км")
    print(f"  Параболическая:  {v_esc:.4f} км/с ({v_esc * 1000:.1f} м/с)")
    print(f"  Круговая:        {v_circ:.4f} км/с ({v_circ * 1000:.1f} м/с)")
    print(f"  Отношение:       {v_esc / v_circ:.6f} (√2 = {math.sqrt(2):.6f})\n")
    if _ask_plot():
        plot_escape(alt)


def calc_hohmann_animation() -> None:
    print("\n  " + _t("hdr_anim_hohmann") + "\n")
    h1 = rf("  Высота орбиты 1, км: ")
    h2 = rf("  Высота орбиты 2, км: ")
    if abs(h1 - h2) < 0.001:
        logger.warning(_t("msg_same_orbits"))
        return
    if h1 < 0 or h2 < 0:
        logger.warning(_t("log_neg_altitude"))
        return
    r1, r2 = h1 + R_EARTH, h2 + R_EARTH
    a_trans = (r1 + r2) / 2
    v1_c, v2_c = math.sqrt(MU_EARTH / r1), math.sqrt(MU_EARTH / r2)
    v1_t = math.sqrt(MU_EARTH * (2 / r1 - 1 / a_trans))
    v2_t = math.sqrt(MU_EARTH * (2 / r2 - 1 / a_trans))
    dv1 = (v1_t - v1_c) * 1000
    dv2 = (v2_c - v2_t) * 1000
    print(f"\n  dv1 = {dv1:+.1f} м/с, dv2 = {dv2:+.1f} м/с")
    if not _ask_plot():
        return
    fname = animate_hohmann(h1, h2, dv1, dv2)
    if fname:
        print(f"  Анимация сохранена: {fname}")


def calc_phasing_animation() -> None:
    print("\n  " + _t("hdr_anim_phasing") + "\n")
    h = rf(_t("prompt_h"))
    phase = rf(_t("prompt_phase"))
    n_rev = ri(_t("prompt_nrev"))
    if n_rev < 1 or n_rev > 20:
        logger.warning(_t("msg_invalid_nrev"))
        return
    res = phasing_orbit(h, phase, n_rev)
    if res is None:
        logger.warning(_t("log_phasing_impossible"))
        return
    print(f"\n  dv = {res['dv_total_mps']:.1f} м/с")
    print(f"  Время сближения = {res['time_to_rendezvous_s'] / 60:.1f} мин")
    if not _ask_plot():
        return
    fname = animate_phasing(h, phase, n_rev)
    if fname:
        print(f"  Анимация сохранена: {fname}")


# ═══════════════════════════════════════════════════════════════════════════
#  --solve: ОБЩИЙ ПРИНТЕР
# ═══════════════════════════════════════════════════════════════════════════


def _print_orbit_result(a: float, e: float) -> None:
    global _LAST_RESULT
    if a > 0 and 0 <= e < 1:
        _LAST_RESULT = {"a": round(a, 6), "e": round(e, 10)}
    if a <= 0:
        logger.warning("  a должна быть > 0")
        return
    if e < 0 or e >= 1:
        logger.warning("  Для эллиптической орбиты нужно 0 ≤ e < 1")
        return

    try:
        _el = aero.elements_from_a_e(a, e)
    except ValueError as exc:
        logger.warning(f"  {exc}")
        return
    r_p, r_a, p = _el["r_p"], _el["r_a"], _el["p"]
    h, eps, T = _el["h"], _el["eps"], _el["T"]
    v_p, v_a = _el["v_p"], _el["v_a"]
    v_cp = math.sqrt(MU_EARTH / r_p)
    v_ca = math.sqrt(MU_EARTH / r_a)

    if r_p < R_EARTH:
        logger.warning(f"  !!! Перигей ниже поверхности: r_p = {r_p:.1f} км < R⊕ = {R_EARTH:.1f} км")

    print("\n  ─── ИТОГОВЫЕ ПАРАМЕТРЫ ───")
    print(f"  r_p (перигей):     {r_p:12.3f} км   (H_p = {r_p - R_EARTH:+12.3f} км)")
    print(f"  r_a (апогей):      {r_a:12.3f} км   (H_a = {r_a - R_EARTH:+12.3f} км)")
    print(f"  a  (полуось):      {a:12.3f} км")
    print(f"  e  (эксцентр.):    {e:12.6f}")
    print(f"  p  (фок. парам.):  {p:12.3f} км")
    print(f"  h  (мом. импульс): {h:12.4f} км²/с")
    print(f"  ε  (уд. энергия):  {eps:12.4f} км²/с²")
    print(f"  T  (период):       {T:12.2f} с = {T / 60:.4f} мин")
    print(f"  v_p (перигей):     {v_p:12.4f} км/с  ({v_p * 1000:.1f} м/с)")
    print(f"  v_a (апогей):      {v_a:12.4f} км/с  ({v_a * 1000:.1f} м/с)")
    print(f"  v_circ(r_p):       {v_cp:12.4f} км/с  (Δv: {(v_p - v_cp) * 1000:+.1f} м/с)")
    print(f"  v_circ(r_a):       {v_ca:12.4f} км/с  (Δv: {(v_a - v_ca) * 1000:+.1f} м/с)")
    print(f"  n  (ср. движение): {2 * math.pi / T:12.6f} рад/с")
    print()
    _record(a=a, e=e, r_p=r_p, r_a=r_a, p=p, h=h, eps=eps,
            T=T, v_p=v_p, v_a=v_a, n=2 * math.pi / T)
    if _ask_plot():
        plot_orbit_params(r_a - R_EARTH, r_p - R_EARTH)


# ═══════════════════════════════════════════════════════════════════════════
#  --solve: ОБРАТНАЯ ЗАДАЧА (1–16)
# ═══════════════════════════════════════════════════════════════════════════


def _solve_a_e() -> None:
    """1: известны a и e."""
    print("\n  СЛУЧАЙ 1: a и e\n")
    print("  r_p = a·(1 − e),  r_a = a·(1 + e),  p = a·(1 − e²)")
    print("  h = √(μ·p),  ε = −μ/(2a),  T = 2π·√(a³/μ)\n")

    a = rf("  a, км: ")
    e = rf("  e (0 ≤ e < 1): ")

    r = aero.solve_case("1", a=a, e=e)
    if "error" in r:
        logger.warning(f"  {r['error']}")
        return

    print(f"\n  Шаг 1: r_p = {a:.3f}·(1 − {e:.6f}) = {r['r_p']:.3f} км")
    print(f"  Шаг 1: r_a = {a:.3f}·(1 + {e:.6f}) = {r['r_a']:.3f} км")
    print(f"  Шаг 2: p = {a:.3f}·(1 − {e * e:.6f}) = {r['p']:.3f} км")
    print(f"  Шаг 3: h = √({MU_EARTH:.4f}·{r['p']:.3f}) = {r['h']:.4f} км²/с")
    print(f"  Шаг 4: ε = −{MU_EARTH:.4f}/(2·{a:.3f}) = {r['eps']:.4f} км²/с²")
    _print_orbit_result(r["a"], r["e"])


def _solve_rp_ra() -> None:
    """2: известны H_p и H_a."""
    print("\n  СЛУЧАЙ 2: H_p и H_a\n")
    print("  a = (r_p + r_a)/2,  e = (r_a − r_p)/(r_a + r_p)\n")

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

    print(f"\n  Шаг 0: r_p = {H_p:.3f} + {R_EARTH:.3f} = {r['r_p']:.3f} км")
    print(f"  Шаг 0: r_a = {H_a:.3f} + {R_EARTH:.3f} = {r['r_a']:.3f} км")
    print(f"  Шаг 1: a = {r['a']:.3f} км")
    print(f"  Шаг 2: e = {r['e']:.6f}")
    _print_orbit_result(r["a"], r["e"])


def _solve_rp_e() -> None:
    """3: известны H_p и e."""
    print("\n  СЛУЧАЙ 3: H_p и e\n")
    print("  a = r_p/(1 − e),  r_a = a·(1 + e)\n")

    H_p = rf("  H_p, км: ")
    e = rf("  e: ")

    r = aero.solve_case("3", H_p=H_p, e=e)
    if "error" in r:
        logger.warning(f"  {r['error']}")
        return

    r_p = H_p + R_EARTH
    print(f"\n  Шаг 0: r_p = {r_p:.3f} км")
    print(f"  Шаг 1: a = {r_p:.3f}/(1 − {e:.6f}) = {r['a']:.3f} км")
    print(f"  Шаг 2: r_a = {r['a']:.3f}·(1 + {e:.6f}) = {r['r_a']:.3f} км")
    _print_orbit_result(r["a"], r["e"])


def _solve_r_v_gamma() -> None:
    """4: известны H, v, γ."""
    print("\n  СЛУЧАЙ 4: H, v, γ\n")
    print("  ε = v²/2 − μ/r,  h = r·v·cos γ,  a = −μ/(2ε)")
    print("  p = h²/μ,  e = √(1 − p/a)\n")

    H = rf("  H, км: ")
    v = rf("  v, км/с: ")
    g_in = input("  γ, ° [0]: ").strip()
    g = float(g_in.replace(",", ".")) if g_in else 0.0

    r = aero.solve_case("4", H=H, v=v, gamma=g)
    if "error" in r:
        logger.warning(f"  {r['error']}")
        return

    print(f"\n  Шаг 1: ε = {r['eps']:.6f} км²/с²")
    print(f"  Шаг 2: h = {r['h']:.4f} км²/с")
    print(f"  Шаг 3: a = {r['a']:.3f} км")
    print(f"  Шаг 4: p = {r['p']:.3f} км")
    print(f"  Шаг 5: e = {r['e']:.6f}")
    _print_orbit_result(r["a"], r["e"])


def _solve_h_eps() -> None:
    """5: известны h и ε."""
    print("\n  СЛУЧАЙ 5: h и ε\n")
    print("  a = −μ/(2ε),  p = h²/μ,  e = √(1 − p/a)\n")

    h = rf("  h, км²/с: ")
    eps = rf("  ε, км²/с²: ")

    r = aero.solve_case("5", h=h, eps=eps)
    if "error" in r:
        logger.warning(f"  {r['error']}")
        return

    print(f"\n  Шаг 1: a = {r['a']:.3f} км")
    print(f"  Шаг 2: p = {r['p']:.3f} км")
    print(f"  Шаг 3: e = {r['e']:.6f}")
    _print_orbit_result(r["a"], r["e"])


def _solve_rp_vp() -> None:
    """6: известны H_p и v_p (эллипс/парабола/гипербола)."""
    print("\n  СЛУЧАЙ 6: H_p и v_p\n")
    print("  ε = v_p²/2 − μ/r_p,  p = (r_p·v_p)²/μ,  a = −μ/(2ε)")
    print("  (ε < 0 — эллипс,  ε = 0 — парабола,  ε > 0 — гипербола)\n")

    H_p = rf("  H_p, км: ")
    v_p = rf("  v_p, км/с: ")

    r = aero.solve_case("6", H_p=H_p, v_p=v_p)
    if "error" in r:
        logger.warning(f"  {r['error']}")
        return

    kind = r.get("kind")
    if kind == "ellipse":
        print(f"\n  ε = {r['eps']:.6f} км²/с²")
        print(f"  h = {r['h']:.4f} км²/с,  p = {r['p']:.3f} км")
        print(f"  a = {r['a']:.3f} км,  e = {r['e']:.6f}  (эллипс)")
        _print_orbit_result(r["a"], r["e"])
    elif kind == "parabola":
        print("\n  ε = 0 → параболическая орбита (e = 1)")
        print(f"  e = 1,  r_p = {r['r_p']:.3f} км,  p = {r['p']:.3f} км")
        print(f"  C3 = 0,  v_p = v_esc = {r['v_p']:.4f} км/с\n")
    else:
        print(f"\n  ε > 0 → гипербола (e = {r['e']:.6f})")
        print(f"  a = {r['a']:.3f} км,  e = {r['e']:.6f},  p = {r['p']:.3f} км")
        print(f"  C3 = v_∞² = {r['C3']:.4f} км²/с²,  v_∞ = {r['v_inf']:.4f} км/с")
        print(f"  v_p = {r['v_p']:.4f} км/с,  δ = {r['delta_deg']:.4f}°\n")


def _solve_h_a() -> None:
    """7: известны h и a."""
    print("\n  СЛУЧАЙ 7: h и a\n")
    print("  p = h²/μ,  e = √(1 − p/a)\n")

    h = rf("  h, км²/с: ")
    a = rf("  a, км: ")

    r = aero.solve_case("7", h=h, a=a)
    if "error" in r:
        logger.warning(f"  {r['error']}")
        return

    print(f"\n  Шаг 1: p = {r['p']:.3f} км")
    print(f"  Шаг 2: e = {r['e']:.6f}")
    _print_orbit_result(r["a"], r["e"])


def _solve_T_circular() -> None:
    """8: известен T (круговая)."""
    print("\n  СЛУЧАЙ 8: T (круговая)\n")
    print("  a = (μ·T²/(4π²))^(1/3),  r = a,  v = √(μ/r)\n")

    unit = input("  Единица T — с/мин [с]: ").strip().lower() or "с"
    mult = 60.0 if unit in ("м", "мин", "m", "min") else 1.0
    T_in = rf("  T: ")
    T = T_in * mult

    r = aero.solve_case("8", T=T)
    if "error" in r:
        logger.warning(f"  {r['error']}")
        return

    print(f"\n  Шаг 1: T = {T:.4f} с")
    print(f"  Шаг 2: a = {r['a']:.3f} км (H = {r['a'] - R_EARTH:+.3f} км)")
    print(f"  Шаг 3: v = {r['v']:.4f} км/с ({r['v'] * 1000:.1f} м/с)")
    print(f"\n  e = 0,  T = {T / 60:.4f} мин\n")


def _solve_ra_e() -> None:
    """9: известны H_a и e."""
    print("\n  СЛУЧАЙ 9: H_a и e\n")
    print("  a = r_a/(1 + e),  r_p = a·(1 − e),  p = a·(1 − e²)")
    print("  h = √(μp),  ε = −μ/(2a),  T = 2π√(a³/μ)\n")

    H_a = rf("  H_a, км: ")
    e = rf("  e (0 ≤ e < 1): ")

    r = aero.solve_case("9", H_a=H_a, e=e)
    if "error" in r:
        logger.warning(f"  {r['error']}")
        return

    r_a = H_a + R_EARTH
    print(f"\n  Шаг 0: r_a = {H_a:.3f} + {R_EARTH:.3f} = {r_a:.3f} км")
    print(f"  Шаг 1: a = r_a/(1 + e) = {r_a:.3f}/(1 + {e:.6f}) = {r['a']:.3f} км")
    print(f"  Шаг 2: r_p = a·(1 − e) = {r['a']:.3f}·(1 − {e:.6f}) = {r['r_p']:.3f} км")
    print(f"  Шаг 3: p = {r['p']:.3f} км")
    print(f"  Шаг 4: h = {r['h']:.4f} км²/с")
    print(f"  Шаг 5: ε = {r['eps']:.4f} км²/с²")
    _print_orbit_result(r["a"], r["e"])


def _solve_ra_va() -> None:
    """10: известны H_a и v_a."""
    print("\n  СЛУЧАЙ 10: H_a и v_a\n")
    print("  ε = v_a²/2 − μ/r_a,  h = r_a·v_a,  a = −μ/(2ε)\n")

    H_a = rf("  H_a, км: ")
    v_a = rf("  v_a, км/с: ")

    r = aero.solve_case("10", H_a=H_a, v_a=v_a)
    if "error" in r:
        logger.warning(f"  {r['error']}")
        return

    print(f"\n  ε = {r['eps']:.6f} км²/с²,  h = {r['h']:.4f} км²/с")
    print(f"  a = {r['a']:.3f} км,  e = {r['e']:.6f}")
    _print_orbit_result(r["a"], r["e"])


def _solve_vp_va() -> None:
    """11: известны v_p и v_a."""
    print("\n  СЛУЧАЙ 11: v_p и v_a\n")
    print("  v_p/v_a = (1+e)/(1−e)  ⟹  e = (v_p − v_a)/(v_p + v_a)")
    print("  a = μ/(v_p·v_a),  p = a·(1 − e²)\n")

    v_p = rf("  v_p, км/с: ")
    v_a = rf("  v_a, км/с: ")

    r = aero.solve_case("11", v_p=v_p, v_a=v_a)
    if "error" in r:
        logger.warning(f"  {r['error']}")
        return

    print(f"\n  Шаг 1: e = ({v_p:.4f} − {v_a:.4f})/({v_p:.4f} + {v_a:.4f}) = {r['e']:.6f}")
    print(f"  Шаг 2: a = {MU_EARTH:.4f}/({v_p:.4f}·{v_a:.4f}) = {r['a']:.3f} км")
    print(f"  Шаг 3: p = {r['a']:.3f}·(1 − {r['e'] * r['e']:.6f}) = {r['p']:.3f} км")
    print(f"  Проверка: r_p = {r['r_p']:.3f} км,  r_a = {r['r_a']:.3f} км")
    print(f"           h = r_p·v_p = {r['r_p'] * v_p:.4f} = r_a·v_a = {r['r_a'] * v_a:.4f}")
    _print_orbit_result(r["a"], r["e"])


def _solve_h_e() -> None:
    """12: известны h и e."""
    print("\n  СЛУЧАЙ 12: h и e\n")
    print("  p = h²/μ,  a = p/(1 − e²)")
    print("  r_p = p/(1 + e),  r_a = p/(1 − e)\n")

    h = rf("  h, км²/с: ")
    e = rf("  e (0 ≤ e < 1): ")

    r = aero.solve_case("12", h=h, e=e)
    if "error" in r:
        logger.warning(f"  {r['error']}")
        return

    print(f"\n  Шаг 1: p = {h:.4f}²/{MU_EARTH:.4f} = {r['p']:.3f} км")
    print(f"  Шаг 2: a = {r['p']:.3f}/(1 − {e * e:.6f}) = {r['a']:.3f} км")
    print(f"  Шаг 3: r_p = {r['r_p']:.3f} км,  r_a = {r['r_a']:.3f} км")
    _print_orbit_result(r["a"], r["e"])


def _solve_p_e() -> None:
    """13: известны p и e."""
    print("\n  СЛУЧАЙ 13: p и e\n")
    print("  a = p/(1 − e²),  h = √(μp)")
    print("  r_p = p/(1 + e),  r_a = p/(1 − e)\n")

    p_in = rf("  p, км: ")
    e = rf("  e (0 ≤ e < 1): ")

    r = aero.solve_case("13", p=p_in, e=e)
    if "error" in r:
        logger.warning(f"  {r['error']}")
        return

    print(f"\n  Шаг 1: a = {p_in:.3f}/(1 − {e * e:.6f}) = {r['a']:.3f} км")
    print(f"  Шаг 2: h = √({MU_EARTH:.4f}·{p_in:.3f}) = {r['h']:.4f} км²/с")
    print(f"  Шаг 3: r_p = {r['r_p']:.3f} км,  r_a = {r['r_a']:.3f} км")
    _print_orbit_result(r["a"], r["e"])


def _solve_T_e() -> None:
    """14: известны T и e."""
    print("\n  СЛУЧАЙ 14: T и e\n")
    print("  a = (μT²/(4π²))^(1/3),  далее по (a, e)\n")

    unit = input("  Единица T — с/мин [мин]: ").strip().lower() or "мин"
    mult = 60.0 if unit in ("м", "мин", "m", "min") else 1.0
    T_in = rf("  T: ")
    e = rf("  e (0 ≤ e < 1): ")
    T = T_in * mult

    r = aero.solve_case("14", T=T, e=e)
    if "error" in r:
        logger.warning(f"  {r['error']}")
        return

    print(f"\n  Шаг 1: T = {T:.4f} с")
    print(f"  Шаг 2: a = {r['a']:.3f} км (H_ср = {r['a'] - R_EARTH:+.3f} км)")
    _print_orbit_result(r["a"], r["e"])


def _solve_rp_h() -> None:
    """15: известны H_p и h."""
    print("\n  СЛУЧАЙ 15: H_p и h\n")
    print("  p = h²/μ,  r_p = p/(1+e)  ⟹  e = p/r_p − 1")
    print("  a = p/(1 − e²)\n")

    H_p = rf("  H_p, км: ")
    h = rf("  h, км²/с: ")

    r = aero.solve_case("15", H_p=H_p, h=h)
    if "error" in r:
        logger.warning(f"  {r['error']}")
        return

    r_p = H_p + R_EARTH
    print(f"\n  Шаг 0: r_p = {H_p:.3f} + {R_EARTH:.3f} = {r_p:.3f} км")
    print(f"  Шаг 1: p = {h:.4f}²/{MU_EARTH:.4f} = {r['p']:.3f} км")
    print(f"  Шаг 2: e = p/r_p − 1 = {r['p']:.3f}/{r_p:.3f} − 1 = {r['e']:.6f}")
    print(f"  Шаг 3: a = p/(1 − e²) = {r['a']:.3f} км")
    _print_orbit_result(r["a"], r["e"])


def _solve_ra_h() -> None:
    """16: известны H_a и h."""
    print("\n  СЛУЧАЙ 16: H_a и h\n")
    print("  p = h²/μ,  r_a = p/(1−e)  ⟹  e = 1 − p/r_a")
    print("  a = p/(1 − e²)\n")

    H_a = rf("  H_a, км: ")
    h = rf("  h, км²/с: ")

    r = aero.solve_case("16", H_a=H_a, h=h)
    if "error" in r:
        logger.warning(f"  {r['error']}")
        return

    r_a = H_a + R_EARTH
    print(f"\n  Шаг 0: r_a = {H_a:.3f} + {R_EARTH:.3f} = {r_a:.3f} км")
    print(f"  Шаг 1: p = {h:.4f}²/{MU_EARTH:.4f} = {r['p']:.3f} км")
    print(f"  Шаг 2: e = 1 − p/r_a = 1 − {r['p']:.3f}/{r_a:.3f} = {r['e']:.6f}")
    print(f"  Шаг 3: a = p/(1 − e²) = {r['a']:.3f} км")
    _print_orbit_result(r["a"], r["e"])


def _solve_a_rp() -> None:
    """17: известны a и H_p."""
    print("\n  СЛУЧАЙ 17: a и H_p\n")
    print("  e = 1 − r_p/a,  r_a = a·(1 + e) = 2a − r_p\n")

    a = rf("  a, км: ")
    H_p = rf("  H_p, км: ")

    r = aero.solve_case("17", a=a, H_p=H_p)
    if "error" in r:
        logger.warning(f"  {r['error']}")
        return

    r_p = H_p + R_EARTH
    print(f"\n  Шаг 0: r_p = {r_p:.3f} км")
    print(f"  Шаг 1: e = 1 − {r_p:.3f}/{a:.3f} = {r['e']:.6f}")
    print(f"  Шаг 2: r_a = 2a − r_p = {2 * a - r_p:.3f} км")
    _print_orbit_result(r["a"], r["e"])


def _solve_a_ra() -> None:
    """18: известны a и H_a."""
    print("\n  СЛУЧАЙ 18: a и H_a\n")
    print("  e = r_a/a − 1,  r_p = a·(1 − e) = 2a − r_a\n")

    a = rf("  a, км: ")
    H_a = rf("  H_a, км: ")

    r = aero.solve_case("18", a=a, H_a=H_a)
    if "error" in r:
        logger.warning(f"  {r['error']}")
        return

    r_a = H_a + R_EARTH
    print(f"\n  Шаг 0: r_a = {r_a:.3f} км")
    print(f"  Шаг 1: e = {r_a:.3f}/{a:.3f} − 1 = {r['e']:.6f}")
    print(f"  Шаг 2: r_p = 2a − r_a = {2 * a - r_a:.3f} км")
    _print_orbit_result(r["a"], r["e"])


def _solve_T_rp() -> None:
    """19: известны T и H_p."""
    print("\n  СЛУЧАЙ 19: T и H_p\n")
    print("  a = (μT²/4π²)^(1/3),  e = 1 − r_p/a\n")

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
    print(f"\n  Шаг 1: T = {T:.4f} с")
    print(f"  Шаг 2: a = {r['a']:.3f} км")
    print(f"  Шаг 3: r_p = {r_p:.3f} км")
    print(f"  Шаг 4: e = {r['e']:.6f}")
    _print_orbit_result(r["a"], r["e"])


def _solve_T_vp() -> None:
    """20: известны T и v_p."""
    print("\n  СЛУЧАЙ 20: T и v_p\n")
    print("  a = (μT²/4π²)^(1/3),  e = (a·v_p² − μ)/(a·v_p² + μ)\n")

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

    print(f"\n  Шаг 1: T = {T:.4f} с,  a = {r['a']:.3f} км")
    print(f"  Шаг 2: e = {r['e']:.6f},  r_p = {r['r_p']:.3f} км")
    _print_orbit_result(r["a"], r["e"])


def _solve_e_vp() -> None:
    """21: известны e и v_p."""
    print("\n  СЛУЧАЙ 21: e и v_p\n")
    print("  v_p² = μ(1+e)/r_p  ⟹  r_p = μ(1+e)/v_p²")
    print("  a = r_p/(1 − e)\n")

    e = rf("  e (0 ≤ e < 1): ")
    v_p = rf("  v_p, км/с: ")

    r = aero.solve_case("21", e=e, v_p=v_p)
    if "error" in r:
        logger.warning(f"  {r['error']}")
        return

    print(f"\n  Шаг 1: r_p = {MU_EARTH:.4f}·(1+{e:.6f})/{v_p:.4f}² = {r['r_p']:.3f} км")
    print(f"  Шаг 2: a = {r['r_p']:.3f}/(1 − {e:.6f}) = {r['a']:.3f} км")
    _print_orbit_result(r["a"], r["e"])


def _solve_e_va() -> None:
    """22: известны e и v_a."""
    print("\n  СЛУЧАЙ 22: e и v_a\n")
    print("  v_a² = μ(1−e)/r_a  ⟹  r_a = μ(1−e)/v_a²")
    print("  a = r_a/(1 + e)\n")

    e = rf("  e (0 ≤ e < 1): ")
    v_a = rf("  v_a, км/с: ")

    r = aero.solve_case("22", e=e, v_a=v_a)
    if "error" in r:
        logger.warning(f"  {r['error']}")
        return

    print(f"\n  Шаг 1: r_a = {MU_EARTH:.4f}·(1−{e:.6f})/{v_a:.4f}² = {r['r_a']:.3f} км")
    print(f"  Шаг 2: a = {r['r_a']:.3f}/(1 + {e:.6f}) = {r['a']:.3f} км")
    _print_orbit_result(r["a"], r["e"])


def _solve_rp_va() -> None:
    """23: известны H_p и v_a."""
    print("\n  СЛУЧАЙ 23: H_p и v_a\n")
    print("  Из v_a² = μ·r_p/(a(2a − r_p)):")
    print("    2a²·v_a² − r_p·v_a²·a − μ·r_p = 0")
    print("  a = (r_p·v_a² + √(r_p²v_a⁴ + 8μr_pv_a²))/(4v_a²)")
    print("  e = 1 − r_p/a\n")

    H_p = rf("  H_p, км: ")
    v_a = rf("  v_a, км/с: ")

    r = aero.solve_case("23", H_p=H_p, v_a=v_a)
    if "error" in r:
        logger.warning(f"  {r['error']}")
        return

    r_p = H_p + R_EARTH
    print(f"\n  Шаг 0: r_p = {r_p:.3f} км")
    print(f"  Шаг 1: v_a² = {v_a * v_a:.6f}")
    print(f"  Шаг 3: a = {r['a']:.3f} км")
    print(f"  Шаг 4: e = 1 − {r_p:.3f}/{r['a']:.3f} = {r['e']:.6f}")
    _print_orbit_result(r["a"], r["e"])


def _solve_ra_vp() -> None:
    """24: известны H_a и v_p."""
    print("\n  СЛУЧАЙ 24: H_a и v_p\n")
    print("  Из v_p² = μ·r_a/(a(2a − r_a)):")
    print("    2a²·v_p² − r_a·v_p²·a − μ·r_a = 0")
    print("  a = (r_a·v_p² + √(r_a²v_p⁴ + 8μr_av_p²))/(4v_p²)")
    print("  e = r_a/a − 1\n")

    H_a = rf("  H_a, км: ")
    v_p = rf("  v_p, км/с: ")

    r = aero.solve_case("24", H_a=H_a, v_p=v_p)
    if "error" in r:
        logger.warning(f"  {r['error']}")
        return

    r_a = H_a + R_EARTH
    print(f"\n  Шаг 0: r_a = {r_a:.3f} км")
    print(f"  Шаг 1: v_p² = {v_p * v_p:.6f}")
    print(f"  Шаг 3: a = {r['a']:.3f} км")
    print(f"  Шаг 4: e = {r_a:.3f}/{r['a']:.3f} − 1 = {r['e']:.6f}")
    _print_orbit_result(r["a"], r["e"])


def _solve_hohmann_incl() -> None:
    """25: Хоман + смена наклонения Δi."""
    print("\n  ПЕРЕЛЁТ ХОМАНА СО СМЕНОЙ НАКЛОНЕНИЯ\n")
    print("  Вариант A: Δi в 1-м импульсе;  Вариант B: Δi во 2-м\n")

    h1 = rf("  H1, км: ")
    h2 = rf("  H2, км: ")
    di = rf("  Δi, °: ")

    r = aero.solve_case("25", H1=h1, H2=h2, di=di)
    if "error" in r:
        logger.warning(f"  {r['error']}")
        return

    print(f"\n  Вариант A: Δv1' = {r['dv1_A_mps']:.2f},  Δv2 = {r['dv2_A_mps']:.2f},  ΣA = {r['total_A_mps']:.2f} м/с")
    print(f"  Вариант B: Δv1 = {r['dv1_B_mps']:.2f},  Δv2' = {r['dv2_B_mps']:.2f},  ΣB = {r['total_B_mps']:.2f} м/с")
    if r["best"] == "A":
        print(f"\n  => Оптимально: A, экономия {r['total_B_mps'] - r['total_A_mps']:.2f} м/с\n")
    else:
        print(f"\n  => Оптимально: B, экономия {r['total_A_mps'] - r['total_B_mps']:.2f} м/с\n")


def _solve_phasing_full() -> None:
    """26: фазирующий манёвр."""
    print("\n  ФАЗИРУЮЩИЙ МАНЁВР\n")
    print("  T_phase = T_circ·(1 − Δφ/(360·N)),  a_phase = (μ(T_ph/2π)²)^(1/3)\n")

    H = rf("  H, км: ")
    dphi = rf("  Δφ, ° (положительный — цель впереди): ")
    N = rf("  N (число витков фазовой орбиты): ")

    r = aero.solve_case("26", H=H, dphi=dphi, N=N)
    if "error" in r:
        logger.warning(f"  {r['error']}")
        return

    print(f"\n  Шаг 0: r_c = {r['r_c_km']:.3f} км")
    print(f"  Шаг 1: T_circ = {r['T_circ_s']:.4f} с")
    print(f"  Шаг 2: T_phase = {r['T_phase_s']:.4f} с")
    print(f"  Шаг 3: a_phase = {r['a_phase_km']:.3f} км")
    print(f"  Шаг 4: v_circ = {r['v_circ_km_s']:.4f},  v_phase = {r['v_ph_km_s']:.4f} км/с")
    print(f"  Шаг 5: |Δv1| = {r['dv1_mps']:.2f} м/с")
    type_str = "поднятие апогея" if r["type"] == "raise" else "опускание перигея"
    print(f"\n  Тип: {type_str}")
    print(f"  r_p_phase = {r['r_p_phase_km']:.1f} км,  r_a_phase = {r['r_a_phase_km']:.1f} км")
    print(f"  Суммарный Δv = {r['dv_total_mps']:.2f} м/с")
    print(f"  Время: {N:.0f} витков × {r['T_phase_s'] / 60:.4f} мин = {N * r['T_phase_s'] / 60:.2f} мин\n")


def _solve_lambert() -> None:
    """27: Ламберт (r1, r2, Δν, Δt → Δv)."""
    print("\n  ЛАМБЕРТ (r1, r2, Δν, Δt → Δv)\n")
    print("  Универсальные переменные, 0 rev, короткий путь (prograde)\n")

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

    print(f"\n  Шаг 0: r1 = {r['r1_km']:.3f},  r2 = {r['r2_km']:.3f} км,  Δt = {dt:.1f} с")
    print(f"  Шаг 1: v1_transfer = {r['v1_km_s']:.4f},  v2_transfer = {r['v2_km_s']:.4f} км/с")
    print(f"  Шаг 3: Δv1 = {r['dv1_mps']:.2f} м/с")
    print(f"  Шаг 4: Δv2 = {r['dv2_mps']:.2f} м/с")
    print(f"\n  Суммарный Δv: {r['dv_total_mps']:.2f} м/с")
    print(f"  Передаточная: a = {r['a_km']:.3f} км,  e = {r['e']:.6f}\n")


def _solve_r_v_nu() -> None:
    """28: известны r, v, ν."""
    print("\n  СЛУЧАЙ 28: r, v, ν\n")
    print("  a = μr/(2μ − rv²),  два корня для e по r = a(1−e²)/(1+e·cos ν)\n")

    H = rf("  H, км: ")
    v = rf("  v, км/с: ")
    nu_deg = rf("  ν, °: ")

    r = aero.solve_case("28", H=H, v=v, nu_deg=nu_deg)
    if "error" in r:
        logger.warning(f"  {r['error']}")
        return

    print(f"\n  Шаг 2: a = {r['a']:.3f} км")
    print(f"  Принято: e = {r['e']:.6f} ({r['branch']})")
    _print_orbit_result(r["a"], r["e"])


def _solve_sso() -> None:
    """29: солнечно-синхронная орбита."""
    print("\n  СОЛНЕЧНО-СИНХРОННАЯ ОРБИТА (SSO)\n")
    print("  cos i = −2·n_☉/(3·J2·n·(R⊕/a)²)\n")

    H = rf("  H, км: ")

    r = aero.solve_case("29", H=H)
    if "error" in r:
        logger.warning(f"  {r['error']}")
        return

    print(f"\n  n = {r['n_rad_s']:.8f} рад/с,  T = {r['T_s']:.2f} с = {r['T_s'] / 60:.4f} мин")
    print(f"  i_SSO = {r['i_SSO_deg']:.4f}°  (ретроградная)\n")


def _solve_repeat_track() -> None:
    """30: повторяющаяся траектория."""
    print("\n  ПОВТОРЯЮЩАЯСЯ ТРАЕКТОРИЯ\n")
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
        print(f"\n  T_orb = {T_orb:.4f} с,  a = {a:.3f} км,  H = {H:+.3f} км\n")
        return

    H = rf("  H, км: ")

    r = aero.solve_case("30", H=H)
    if "error" in r:
        logger.warning(f"  {r['error']}")
        return

    print(f"\n  T_orb = {r['T_orb_s']:.4f} с,  k_rep = {r['k_rep']}")
    print(f"  H_rep = {r['H_rep_km']:+.3f} км\n")


def _solve_ap_pe() -> None:
    """31: Ap/Pe."""
    print("\n  ПАРАМЕТРЫ ОРБИТЫ ПО Ap/Pe\n")
    print("  r_p = H_p + R⊕,  r_a = H_a + R⊕,  a = (r_p+r_a)/2\n")

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

    print(f"\n  a = {r['a']:.3f} км,  e = {r['e']:.6f}")
    _print_orbit_result(r["a"], r["e"])


def _solve_velocity_at_point() -> None:
    """32: скорость в точке орбиты."""
    print("\n  СКОРОСТЬ В ТОЧКЕ ОРБИТЫ (vis-viva)\n")
    print("  v² = μ·(2/r − 1/a)\n")

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

    print(f"\n  Точка: {name}")
    print(f"  v = {r['v_km_s']:.4f} км/с ({r['v_km_s'] * 1000:.1f} м/с)\n")


def _solve_circular_full() -> None:
    """33: круговая скорость и период."""
    print("\n  КРУГОВАЯ СКОРОСТЬ И ПЕРИОД\n")
    print("  v = √(μ/r),  T = 2π√(r³/μ)\n")

    alt = rf("  Высота, км: ")

    r = aero.solve_case("33", H=alt)
    if "error" in r:
        logger.warning(f"  {r['error']}")
        return

    print(f"\n  r = {r['r_km']:.3f} км,  v = {r['v_km_s']:.4f} км/с")
    print(f"  T = {r['T_s']:.2f} с = {r['T_s'] / 60:.4f} мин")
    print(f"  n = {r['n_rad_s']:.6f} рад/с\n")


def _solve_hohmann_full() -> None:
    """34: перелёт Хомана."""
    print("\n  ПЕРЕЛЁТ ХОМАНА (2 ИМПУЛЬСА)\n")
    print("  a_t = (r1+r2)/2,  Δv1 = v1_t − v1_c,  Δv2 = v2_c − v2_t\n")

    h1 = rf("  Высота орбиты 1, км: ")
    h2 = rf("  Высота орбиты 2, км: ")

    r = aero.solve_case("34", H1=h1, H2=h2)
    if "error" in r:
        logger.warning(f"  {r['error']}")
        return

    print(f"\n  Δv1 = {r['dv1_mps']:+.2f} м/с,  Δv2 = {r['dv2_mps']:+.2f} м/с")
    print(f"  Σ|Δv| = {r['dv_total_mps']:.2f} м/с")
    print(f"  t = {r['t_transfer_s']:.2f} с = {r['t_transfer_s'] / 60:.2f} мин ({r['t_transfer_s'] / 3600:.2f} ч)\n")


def _solve_bielliptic_full() -> None:
    """35: биэллиптический перелёт."""
    print("\n  БИЭЛЛИПТИЧЕСКИЙ ПЕРЕЛЁТ (3 ИМПУЛЬСА)\n")

    h1 = rf("  H1, км: ")
    h2 = rf("  H2, км: ")
    h_bi = rf("  H_rb (промежуточная), км: ")

    r = aero.solve_case("35", H1=h1, H2=h2, H_bi=h_bi)
    if "error" in r:
        logger.warning(f"  {r['error']}")
        return

    print(f"\n  Δv1 = {r['dv1_mps']:+.2f} м/с,  Δv2 = {r['dv2_mps']:+.2f} м/с,  Δv3 = {r['dv3_mps']:+.2f} м/с")
    print(f"  Σ|Δv| = {r['dv_total_mps']:.2f} м/с  (Хоман: {r['hohmann_total_mps']:.2f} м/с)")
    verdict = "биэллиптика выгоднее" if r["bielliptic_is_better"] else "Хоман выгоднее"
    print(f"  Вывод: {verdict}\n")


def _solve_tsiolkovsky_full() -> None:
    """36: Циолковский."""
    print("\n  ЦИОЛКОВСКИЙ: Δv → ТОПЛИВО\n")

    dv = rf("  Δv, м/с: ")
    m0 = rf("  Масса начальная m0, кг: ")
    isp = rf("  Isp, с: ")

    r = aero.solve_case("36", dv=dv, m0=m0, isp=isp)
    if "error" in r:
        logger.warning(f"  {r['error']}")
        return

    print(f"\n  v_e = {r['ve_mps']:.2f} м/с")
    print(f"  m_fuel = {r['m_fuel_kg']:.3f} кг ({r['fuel_fraction'] * 100:.2f}%)")
    print(f"  m_final = {r['m_final_kg']:.3f} кг\n")


def _solve_inverse_ts_full() -> None:
    """37: обратный Циолковский."""
    print("\n  ОБРАТНЫЙ ЦИОЛКОВСКИЙ: ТОПЛИВО → Δv\n")

    m_fuel = rf("  Топливо m_fuel, кг: ")
    m0 = rf("  Масса начальная m0, кг: ")
    isp = rf("  Isp, с: ")

    r = aero.solve_case("37", m_fuel=m_fuel, m0=m0, isp=isp)
    if "error" in r:
        logger.warning(f"  {r['error']}")
        return

    print(f"\n  v_e = {r['ve_mps']:.2f} м/с")
    print(f"  m_final = {r['m_final_kg']:.3f} кг")
    print(f"  Δv = {r['dv_mps']:.2f} м/с\n")


def _solve_time_of_flight() -> None:
    """38: время пролёта по истинной аномалии."""
    print("\n  ВРЕМЯ ПРОЛЁТА ПО ИСТИННОЙ АНОМАЛИИ\n")

    a = rf("  a, км: ")
    e = rf("  e (0 ≤ e < 1): ")
    nu1 = rf("  ν1, °: ")
    nu2 = rf("  ν2, °: ")

    r = aero.solve_case("38", a=a, e=e, nu1=nu1, nu2=nu2)
    if "error" in r:
        logger.warning(f"  {r['error']}")
        return

    print(f"\n  ΔM = {r['dM_rad']:.6f} рад,  T = {r['T_s']:.2f} с")
    print(f"  Δt = {r['dt_s']:.4f} с = {r['dt_s'] / 60:.4f} мин = {r['dt_s'] / 3600:.4f} ч\n")


def _solve_true_anomaly_by_time() -> None:
    """39: истинная аномалия по времени."""
    print("\n  ИСТИННАЯ АНОМАЛИЯ ПО ВРЕМЕНИ\n")

    a = rf("  a, км: ")
    e = rf("  e (0 ≤ e < 1): ")
    t = rf("  t (от перигея), с: ")

    r = aero.solve_case("39", a=a, e=e, t=t)
    if "error" in r:
        logger.warning(f"  {r['error']}")
        return

    print(f"\n  E = {r['E_rad']:.8f} рад")
    print(f"  ν = {r['nu_deg']:.4f}°,  r = {r['r_km']:.3f} км")
    print(f"  v = {r['v_km_s']:.4f} км/с ({r['v_km_s'] * 1000:.1f} м/с)\n")


def _solve_hyperbolic() -> None:
    """40: гиперболическая орбита."""
    print("\n  ГИПЕРБОЛИЧЕСКАЯ ОРБИТА (C3, v_∞)\n")

    H_p = rf("  H_p, км: ")
    v_inf = rf("  v_∞, км/с: ")

    r = aero.solve_case("40", H_p=H_p, v_inf=v_inf)
    if "error" in r:
        logger.warning(f"  {r['error']}")
        return

    print(f"\n  C3 = {r['C3_km2_s2']:.4f} км²/с²,  a = {r['a_km']:.3f} км,  e = {r['e']:.6f}")
    print(f"  p = {r['p_km']:.3f} км,  v_p = {r['v_p_km_s']:.4f} км/с")
    print(f"  δ = {r['delta_deg']:.4f}°\n")


def _solve_hill_soi() -> None:
    """41: сфера Хилла и SOI."""
    print("\n  СФЕРА ХИЛЛА И SOI\n")
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

    print(f"\n  r_H = {r['r_H_km']:.3e} км ({r['r_H_km'] / 1e3:.1f} тыс. км)")
    print(f"  r_SOI = {r['r_SOI_km']:.3e} км ({r['r_SOI_km'] / 1e3:.1f} тыс. км)\n")


def _solve_lagrange_l1_l2() -> None:
    """42: L1/L2 (приближение)."""
    print("\n  ТОЧКИ ЛАГРАНЖА L1/L2 (приближение)\n")
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

    print(f"\n  μ = {r['mu']:.6e},  r_L = {r['r_L_km']:.3e} км ({r['r_L_km'] / 1e3:.1f} тыс. км)\n")


def _solve_synodic_period() -> None:
    """43: синодический период."""
    print("\n  СИНОДИЧЕСКИЙ ПЕРИОД\n")

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

    print(f"\n  T_syn = {r['T_syn_s']:.4f} с = {r['T_syn_s'] / 60:.4f} мин")
    print(f"        = {r['T_syn_s'] / 3600:.4f} ч = {r['T_syn_s'] / 86400:.4f} сут\n")


def _solve_inclination_change() -> None:
    """44: Δv смены наклонения."""
    print("\n  Δv ДЛЯ СМЕНЫ НАКЛОНЕНИЯ\n")

    alt = rf("  Высота, км: ")
    di = rf("  Δi, °: ")

    r = aero.solve_case("44", H=alt, di=di)
    if "error" in r:
        logger.warning(f"  {r['error']}")
        return

    print(f"\n  v = {r['v_km_s']:.4f} км/с")
    print(f"  Δv = {r['dv_mps']:.1f} м/с\n")


def _solve_look_angle() -> None:
    """45: угол места и дальность."""
    print("\n  УГОЛ МЕСТА И ДАЛЬНОСТЬ ДО СПУТНИКА\n")

    H = rf("  H спутника, км: ")
    gamma_deg = rf("  γ, °: ")

    r = aero.solve_case("45", H=H, gamma_deg=gamma_deg)
    if "error" in r:
        logger.warning(f"  {r['error']}")
        return

    print(f"\n  ε = {r['elev_deg']:.4f}°,  d = {r['range_km']:.3f} км\n")


def _solve_state_vector() -> None:
    """46: вектор состояния → элементы."""
    print("\n  ВЕКТОР СОСТОЯНИЯ → ЭЛЕМЕНТЫ\n")
    print("  h = r × v,  e = (v × h)/μ − r̂,  i = arccos(h_z/|h|)\n")

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

    print(f"\n  |r| = {r['r']:.3f} км,  |v| = {r['v']:.4f} км/с")
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
    _record(r)


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
    _record(r)


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
    _record(r)


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
    _record(r)


def _solve_lambert_nrev() -> None:
    """54: Ламберт N витков (multi-rev)."""
    print("\n  ЛАМБЕРТ N ВИТКОВ\n")
    print("  Универсальные переменные, все решения от N=0 до N_max")
    print("  Для N≥1 — до 2 решений (left/right branches)\n")

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
    print(f"\n  Найдено решений: {r['n_found']}")
    print(f"  r1 = {r['r1_km']:.1f} км, r2 = {r['r2_km']:.1f} км, Δν = {dnu_deg:.1f}°, Δt = {dt:.1f} с\n")

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

    _record(n_found=r["n_found"], n_solutions=r["n_found"], n_max=n_max, dt_s=dt, dnu_deg=dnu_deg)


_DISPATCH = {
    "1": _solve_a_e, "2": _solve_rp_ra, "3": _solve_rp_e,
    "4": _solve_r_v_gamma, "5": _solve_h_eps, "6": _solve_rp_vp,
    "7": _solve_h_a, "8": _solve_T_circular, "9": _solve_ra_e,
    "10": _solve_ra_va, "11": _solve_vp_va, "12": _solve_h_e,
    "13": _solve_p_e, "14": _solve_T_e, "15": _solve_rp_h,
    "16": _solve_ra_h, "17": _solve_a_rp, "18": _solve_a_ra,
    "19": _solve_T_rp, "20": _solve_T_vp, "21": _solve_e_vp,
    "22": _solve_e_va, "23": _solve_rp_va, "24": _solve_ra_vp,
    "25": _solve_hohmann_incl, "26": _solve_phasing_full,
    "27": _solve_lambert, "28": _solve_r_v_nu, "29": _solve_sso,
    "30": _solve_repeat_track, "31": _solve_ap_pe,
    "32": _solve_velocity_at_point, "33": _solve_circular_full,
    "34": _solve_hohmann_full, "35": _solve_bielliptic_full,
    "36": _solve_tsiolkovsky_full, "37": _solve_inverse_ts_full,
    "38": _solve_time_of_flight, "39": _solve_true_anomaly_by_time,
    "40": _solve_hyperbolic, "41": _solve_hill_soi,
    "42": _solve_lagrange_l1_l2, "43": _solve_synodic_period,
    "44": _solve_inclination_change, "45": _solve_look_angle,
    "46": _solve_state_vector,
    "47": _solve_j2_precession,
    "48": _solve_radar,
    "49": _solve_budget_ascent,
    "50": _solve_payload_max,
    "51": _solve_staged_rocket,
    "52": _solve_cr3bp_lagrange,
    "53": _solve_frozen_orbit,
    "54": _solve_lambert_nrev,
}

_ALIASES = {
    "Ap": "H_a", "Pe": "H_p", "vp": "v_p", "va": "v_a",
    "ra": "H_a", "rp": "H_p", "Hi": "H",
}

_KEYS_TO_SOLVER = {
    frozenset(["a", "e"]): 1,
    frozenset(["H_p", "H_a"]): 2,
    frozenset(["H_p", "e"]): 3,
    frozenset(["h", "eps"]): 5,
    frozenset(["H_p", "v_p"]): 6,
    frozenset(["h", "a"]): 7,
    frozenset(["H_a", "e"]): 9,
    frozenset(["H_a", "v_a"]): 10,
    frozenset(["v_p", "v_a"]): 11,
    frozenset(["h", "e"]): 12,
    frozenset(["p", "e"]): 13,
    frozenset(["H_p", "h"]): 15,
    frozenset(["H_a", "h"]): 16,
    frozenset(["a", "H_p"]): 17,
    frozenset(["a", "H_a"]): 18,
    frozenset(["e", "v_p"]): 21,
    frozenset(["e", "v_a"]): 22,
    frozenset(["H_p", "v_a"]): 23,
    frozenset(["H_a", "v_p"]): 24,
}

_ORDERED_KEYS = {
    1: ["a", "e"], 2: ["H_p", "H_a"], 3: ["H_p", "e"],
    5: ["h", "eps"], 6: ["H_p", "v_p"], 7: ["h", "a"],
    9: ["H_a", "e"], 10: ["H_a", "v_a"], 11: ["v_p", "v_a"],
    12: ["h", "e"], 13: ["p", "e"],
    15: ["H_p", "h"], 16: ["H_a", "h"], 17: ["a", "H_p"],
    18: ["a", "H_a"],
    21: ["e", "v_p"], 22: ["e", "v_a"], 23: ["H_p", "v_a"],
    24: ["H_a", "v_p"],
}

_PRESETS = {
    "gso":       (2, [35786.0, 35786.0], "Геостационарная: H_p = H_a = 35786 км"),
    "iss":       (2, [408.0, 420.0], "МКС: H_p = 408, H_a = 420 км"),
    "leo-550":   (2, [550.0, 550.0], "LEO 550 км (Starlink shell 1)"),
    "meo-20200": (2, [20200.0, 20200.0], "MEO 20200 км (GPS)"),
    "sso-700":   (29, [700.0], "SSO при H = 700 км → i_SSO"),
    "molniya":   (2, [500.0, 40000.0], "HEO 500×40000 км (Молния-подобная)"),
}


@contextlib.contextmanager
def _input_queue(values):
    mod = sys.modules[__name__]
    original = mod.rf
    original_ask = getattr(mod, "_ask_plot", None)
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
    if original_ask is not None:
        mod._ask_plot = lambda: False
    try:
        yield
    finally:
        mod.rf = original
        if original_ask is not None:
            mod._ask_plot = original_ask


def _parse_from(spec):
    kv = {}
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "=" not in part:
            raise ValueError(f"Ожидался key=value: {part!r}")
        k, v = part.split("=", 1)
        k = _ALIASES.get(k.strip(), k.strip())
        kv[k] = float(v.strip())
    keys = frozenset(kv.keys())
    solver_id = _KEYS_TO_SOLVER.get(keys)
    if solver_id is None:
        print(f"  Неизвестная комбинация: {sorted(keys)}")
        print(f"  Поддерживается {len(_KEYS_TO_SOLVER)} комбинаций из 2 параметров:")
        for keys_ in sorted(_KEYS_TO_SOLVER, key=lambda k: _KEYS_TO_SOLVER[k]):
            sid = _KEYS_TO_SOLVER[keys_]
            print(f"    {sid:2d}: {sorted(keys_)}")
        return None
    return solver_id, [kv[k] for k in _ORDERED_KEYS[solver_id]]


class _StdoutFilter:
    def __init__(self, target, level):
        self.target = target
        self.level = level

    def write(self, text):
        if self.level == "full":
            return self.target.write(text)
        if self.level == "brief":
            if "  Шаг" in text or "Формул" in text or "СЛУЧАЙ" in text:
                return 0
            return self.target.write(text)
        keep = ("ИТОГОВЫЕ", "полуось", "эксцентр", "перигей", "апогей",
                "мом. импульс", "Суммарный", "dv:", "Δv:", "Точка:",
                "Скорость:", "e =", "a =")
        if any(k in text for k in keep):
            return self.target.write(text)
        return 0

    def flush(self):
        self.target.flush()

    def isatty(self):
        return False


class _Tee:
    def __init__(self, *targets):
        self.targets = targets

    def write(self, text):
        for t in self.targets:
            t.write(text)
        return len(text)

    def flush(self):
        for t in self.targets:
            t.flush()

    def isatty(self):
        return False


def _run_demo():
    print("\n  ДЕМО: 4 типовых сценария\n" + "=" * 50)
    scenarios = [
        ("ГСО (H_p = H_a = 35786 км)", 2, [35786.0, 35786.0]),
        ("МКС (H_p = 408, H_a = 420 км)", 2, [408.0, 420.0]),
        ("Перелёт LEO 200 → ГСО", 34, [200.0, 35786.0]),
        ("SSO при H = 700 км", 29, [700.0]),
    ]
    for title, sid, vals in scenarios:
        print(f"\n── {title} " + "─" * max(10, 40 - len(title)))
        with _input_queue(vals):
            _dispatch_solve(str(sid))
    print("\n  " + "=" * 50 + "\n  ДЕМО завершено.\n")


# ═══════════════════════════════════════════════════════════════════════════
#  --solve: МЕНЮ
# ═══════════════════════════════════════════════════════════════════════════


_SHOW_LATEX = False


def _print_latex(sid: str) -> None:
    """Печатает LaTeX-формулы перед расчётом."""
    if not _SHOW_LATEX:
        return
    formulas = _latex_get(sid)
    if not formulas:
        return
    print(f"\n  {_c('LaTeX:', 'b')}")
    for f in formulas:
        print(f"    ${f}$")


# ── v4.3: shadow verify (--verbose) ──────────────────────────────────────
_VERIFY_CAPTURE = {"sid": None, "inputs": []}
_VERIFY_ENABLED = False
_SKIP_VERIFY = {"4", "8", "14", "19", "20", "27", "30", "41", "42", "48", "49"}


@contextlib.contextmanager
def _capture_rf():
    """Записывает rf() вызовы в _VERIFY_CAPTURE для сверки с aero."""
    mod = sys.modules[__name__]
    original = mod.rf
    _VERIFY_CAPTURE["inputs"] = []

    def recording_rf(prompt=""):
        v = original(prompt)
        _VERIFY_CAPTURE["inputs"].append(v)
        return v

    mod.rf = recording_rf
    try:
        yield
    finally:
        mod.rf = original


def _verify_against_core(sid: str) -> None:
    """Сверяет _RESULT с aero.solve_case в --verbose режиме."""
    if not _VERIFY_ENABLED:
        return
    if sid in _SKIP_VERIFY:
        return
    meta = aero.CASE_META.get(sid)
    if not meta:
        return
    inputs = _VERIFY_CAPTURE["inputs"]
    params = meta["inputs"]
    if len(inputs) != len(params):
        return
    kwargs = dict(zip(params, inputs))
    expected = aero.solve_case(sid, **kwargs)
    if "error" in expected:
        return
    for key in list(_RESULT["output"]):
        if key not in expected:
            continue
        exp = expected[key]
        got = _RESULT["output"][key]
        if isinstance(exp, (int, float)) and isinstance(got, (int, float)):
            tol = 1e-6 * max(abs(exp), 1.0)
            if abs(got - exp) > tol:
                logger.warning(
                    f"  verify {sid}: {key} got={got:.6g} exp={exp:.6g} "
                    f"Δ={abs(got - exp):.3e}"
                )


def _dispatch_solve(sid: str) -> None:
    """Единая точка: сброс _RESULT + LaTeX + расчёт + verify."""
    global _RESULT
    _RESULT = {"case": sid, "output": {}, "error": None, "kind": None}
    _print_latex(sid)
    _VERIFY_CAPTURE["sid"] = sid
    try:
        if _VERIFY_ENABLED:
            with _capture_rf():
                _DISPATCH[sid]()
        else:
            _DISPATCH[sid]()
    except SystemExit:
        raise
    except Exception as exc:
        _RESULT["error"] = f"{type(exc).__name__}: {exc}"
        raise
    _verify_against_core(sid)


def calc_solve() -> None:
    while True:
        print(f"\n{'=' * 50}")
        print("  РЕШЕНИЕ (--solve)")
        print(f"{'=' * 50}")
        print("  ── Обратная задача (1–2 параметра) ──")
        print("  1. a и e")
        print("  2. H_p и H_a")
        print("  3. H_p и e")
        print("  4. H, v, γ")
        print("  5. h и ε")
        print("  6. H_p и v_p (эллипс/парабола/гипербола)")
        print("  7. h и a")
        print("  8. T → круговая орбита")
        print("  9. H_a и e")
        print(" 10. H_a и v_a")
        print(" 11. v_p и v_a")
        print(" 12. h и e")
        print(" 13. p и e")
        print(" 14. T и e")
        print(" 15. H_p и h")
        print(" 16. H_a и h")
        print("  ── Обратная задача: расширение ──")
        print(" 17. a и H_p")
        print(" 18. a и H_a")
        print(" 19. T и H_p")
        print(" 20. T и v_p")
        print(" 21. e и v_p")
        print(" 22. e и v_a")
        print(" 23. H_p и v_a")
        print(" 24. H_a и v_p")
        print(" 25. Хоман + смена наклонения Δi")
        print(" 26. Фазирующий манёвр (Δφ, N → Δv)")
        print(" 27. Ламберт: r1, r2, Δν, Δt → Δv")
        print(" 28. r, v, ν")
        print(" 29. Солнечно-синхронная орбита (H → i_SSO)")
        print(" 30. Повторяющаяся траектория (H ↔ k)")
        print("  ── Прямые расчёты с пояснениями ──")
        print(" 31. Параметры орбиты по Ap/Pe")
        print(" 32. Скорость в точке орбиты")
        print(" 33. Круговая скорость и период")
        print(" 34. Перелёт Хомана (2 импульса)")
        print(" 35. Биэллиптический перелёт (3 импульса)")
        print(" 36. Циолковский: Δv → топливо")
        print(" 37. Обратный Циолковский: топливо → Δv")
        print("  ── Астрономические расчёты ──")
        print(" 38. Время пролёта по истинной аномалии (Кеплер)")
        print(" 39. Истинная аномалия по времени (обратный Кеплер)")
        print(" 40. Гиперболическая орбита (C3, v_∞, a, e)")
        print(" 41. Сфера Хилла и SOI")
        print(" 42. Точки Лагранжа L1/L2")
        print(" 43. Синодический период")
        print(" 44. Δv смены наклонения")
        print(" 45. Угол места и дальность до спутника")
        print("  ── Вектор состояния ──")
        print(" 46. Вектор состояния → орбитальные элементы")
        print("  ── Итерация v3 ──")
        print(" 47. J2-прецессия (a, e, i → dΩ/dt, dω/dt, dM₀/dt)")
        print(" 48. Радиолокатор (ρ, ρ̇, el → r, H, v_esc)")
        print(" 49. Бюджет выведения на орбиту")
        print(" 50. Максимальная полезная нагрузка")
        print(" 51. Ступенчатая ракета (N ступеней)")
        print(" 52. Точные L1/L2/L3 (CR3BP, Ньютон)")
        print(" 53. Замороженная орбита / критическое наклонение")
        print(" 54. Ламберт N витков (multi-rev)")
        print("  0. Назад")
        ch = input("\n  Выбор: ").strip()
        try:
            if ch == "0":
                break
            elif ch in _DISPATCH:
                _dispatch_solve(ch)
            else:
                print("  Введите 0..46")
        except (ValueError, ZeroDivisionError) as exc:
            logger.warning(f"  Ошибка ввода: {exc}")


# ═══════════════════════════════════════════════════════════════════════════
#  ОСНОВНОЕ МЕНЮ
# ═══════════════════════════════════════════════════════════════════════════


def interactive_calculator() -> None:
    while True:
        print(f"\n{'=' * 50}")
        print("  " + _t("menu_title"))
        print(f"{'=' * 50}")
        print("  1. " + _t("menu_1"))
        print("  2. " + _t("menu_2"))
        print("  3. " + _t("menu_3"))
        print("  4. " + _t("menu_4"))
        print("  5. " + _t("menu_5"))
        print("  6. " + _t("menu_6"))
        print("  7. " + _t("menu_7"))
        print("  8. " + _t("menu_8"))
        print("  9. " + _t("menu_9"))
        print(" 10. " + _t("menu_10"))
        print(" 11. " + _t("menu_11"))
        print(" 12. Орбитальные задачи по неполным данным (46 расчётов, --solve)")
        print("  0. " + _t("menu_0"))
        if not HAS_PLOT:
            print("\n  " + _t("menu_no_plot"))
        ch = input("\n" + _t("menu_choice")).strip()
        if ch == "1":
            calc_orbit_params()
        elif ch == "2":
            calc_velocity_point()
        elif ch == "3":
            calc_circular()
        elif ch == "4":
            calc_hohmann()
        elif ch == "5":
            calc_bielliptic()
        elif ch == "6":
            calc_tsiolkovsky()
        elif ch == "7":
            calc_inverse_ts()
        elif ch == "8":
            calc_escape()
        elif ch == "9":
            calc_hohmann_animation()
        elif ch == "10":
            calc_phasing_animation()
        elif ch == "11":
            new_lang = input("  ru/en: ").strip().lower()
            set_lang(new_lang)
            from core import base
            print("  " + _t("msg_lang_changed") + ": " + base.LANG)
        elif ch == "12":
            calc_solve()
        elif ch == "0":
            break
        else:
            logger.warning(_t("msg_enter_0_11"))


def main() -> None:
    """Точка входа: GUI, интерактивный калькулятор или прямой вызов."""
    p = argparse.ArgumentParser(
        prog="orbit_calc.py",
        description="Универсальный калькулятор орбитальных и астрономических расчётов",
    )
    p.add_argument("--lang", default="ru", choices=["ru", "en"], help="Interface language")
    p.add_argument("--verbose", action="store_true", help="Enable debug logging")
    p.add_argument("--solve", nargs="?", const="menu", default=None,
                   help="Номер пункта 1..46, 'menu', 'demo' или пусто (меню)")
    p.add_argument("--explain", default="full", choices=["full", "brief", "none"],
                   help="Уровень детализации (по умолчанию full)")
    p.add_argument("--from", dest="from_spec", default=None,
                   help='Параметры "Ap=35786,Pe=35786" — автоопределение случая')
    p.add_argument("--preset", default=None,
                   help="Preset: gso, iss, leo-550, meo-20200, sso-700, molniya")
    p.add_argument("--save", default=None,
                   help="Сохранить сессию в файл (.md)")
    p.add_argument("--json", action="store_true",
                   help="JSON-вывод (только орбитальные случаи 1-24)")
    p.add_argument("--latex", action="store_true",
                   help="Показывать LaTeX-формулы перед расчётом")
    args = p.parse_args()
    setup_logging(args.verbose)
    set_lang(args.lang)
    global _SHOW_LATEX, _VERIFY_ENABLED
    _SHOW_LATEX = args.latex
    _VERIFY_ENABLED = args.verbose

    if args.explain != "full":
        sys.stdout = _StdoutFilter(sys.stdout, args.explain)

    _teed = None
    if args.save:
        _teed = open(args.save, "w", encoding="utf-8")
        sys.stdout = _Tee(sys.stdout, _teed)

    try:
        if args.preset:
            if args.preset not in _PRESETS:
                print(f"  Неизвестный preset: {args.preset}")
                print(f"  Доступны: {', '.join(_PRESETS)}")
                return
            sid, vals, desc = _PRESETS[args.preset]
            print(f"\n  PRESET: {args.preset} — {desc}\n")
            with _input_queue(vals):
                _dispatch_solve(str(sid))

        elif args.from_spec:
            try:
                parsed = _parse_from(args.from_spec)
            except ValueError as exc:
                print(f"  Ошибка --from: {exc}")
                return
            if parsed is None:
                return
            sid, vals = parsed
            print(f"\n  --from → пункт {sid}, значения {vals}\n")
            with _input_queue(vals):
                _dispatch_solve(str(sid))

        elif args.solve == "demo":
            _run_demo()

        elif args.solve is None:
            interactive_calculator()

        elif args.solve == "menu":
            calc_solve()

        elif args.solve.isdigit() and args.solve in _DISPATCH:
            _dispatch_solve(args.solve)

        else:
            print(f"  Неизвестное значение --solve: {args.solve!r}")

        if args.json:
            payload = {k: v for k, v in _RESULT.items() if v not in (None, {}, [])}
            if not payload.get("output") and _LAST_RESULT:
                payload["output"] = _LAST_RESULT
            print(json.dumps(payload, indent=2, ensure_ascii=False))

    finally:
        if _teed is not None:
            _teed.close()
            sys.stdout = sys.__stdout__


if __name__ == "__main__":
    main()