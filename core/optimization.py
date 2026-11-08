"""core/optimization.py — фазирование и оптимизация манёвров."""

from __future__ import annotations

from core import astrodynamics as aero


def phasing_orbit(H: float, phase_deg: float, n_rev: int) -> dict | None:
    """Фазирующий манёвр: H, Δφ, N → dv, время.

    Возвращает dict с dv_total_mps и time_to_rendezvous_s, или None.
    """
    try:
        r = aero.solve_case("26", H=H, dphi=phase_deg, N=n_rev)
    except Exception:
        return None
    if "error" in r:
        return None
    return {
        "dv_total_mps": r["dv_total_mps"],
        "time_to_rendezvous_s": n_rev * r["T_phase_s"],
        "a_phase_km": r["a_phase_km"],
        "T_phase_s": r["T_phase_s"],
    }
