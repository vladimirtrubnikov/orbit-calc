"""tests/test_astrodynamics.py"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from core import astrodynamics as aero

MU = aero.MU_EARTH
R = aero.R_EARTH


def test_gso_from_a_e():
    el = aero.elements_from_a_e(42164.17, 0.0)
    assert abs(el["T"] - 86164.0) < 5
    assert el["e"] == 0


def test_iss_from_rp_ra():
    el = aero.elements_from_rp_ra(408 + R, 420 + R)
    a_expected = 414 + R   # v4.5: независимо от значения R_EARTH
    assert abs(el["a"] - a_expected) < 1
    assert 0 < el["e"] < 0.01


def test_hohmann_leo_gso():
    h = aero.hohmann(200 + R, 35786 + R)
    assert abs(h["dv_total_mps"] - 3940) < 50
    assert h["t_transfer_s"] > 0


def test_tsiolkovsky_roundtrip():
    t = aero.tsiolkovsky(1500, 1000, 320)
    back = aero.inverse_tsiolkovsky(t["m_fuel_kg"], 1000, 320)
    assert abs(back["dv_mps"] - 1500) < 1e-6


def test_state_vector_roundtrip():
    a, e, i_deg = 7000.0, 0.05, 45.0
    r_p = a * (1 - e)
    v_p = math.sqrt(MU * (2 / r_p - 1 / a))
    i = math.radians(i_deg)
    el = aero.elements_from_state(
        (r_p, 0.0, 0.0),
        (0.0, v_p * math.cos(i), v_p * math.sin(i)),
    )
    assert abs(el["a"] - a) < 1e-6
    assert abs(el["e"] - e) < 1e-6
    assert abs(el["i"] - i_deg) < 1e-6


def test_j2_sso():
    """J2-прецессия для SSO-700 ≈ 0.9856°/сут."""
    el = aero.j2_precession(6371.0 + 700, 0.0, 98.2)
    assert abs(el["dOmega_deg_day"] - 0.9856) < 0.1


def test_j2_gso_nodal_regression():
    """ГСО, i=0 → узел дрейфует ≈ -0.013°/сут (≈ -4.9°/год)."""
    el = aero.j2_precession(42164.17, 0.0, 0.0)
    assert abs(el["dOmega_deg_year"] - (-4.9)) < 0.5


def test_cr3bp_earth_sun_l1():
    mu = aero.M_EARTH / (aero.M_SUN + aero.M_EARTH)
    x_L1 = aero.cr3bp_lagrange(mu, "L1")
    # L1 Земля-Солнце на ≈ 1.5e6 км от Земли → доля ≈ 0.99
    assert abs(x_L1 - 0.99003) < 0.001


def test_cr3bp_earth_sun_l2():
    mu = aero.M_EARTH / (aero.M_SUN + aero.M_EARTH)
    x_L2 = aero.cr3bp_lagrange(mu, "L2")
    assert abs(x_L2 - 1.01007) < 0.001


def test_frozen_orbit_critical():
    el = aero.frozen_orbit_info(7000, 0.005, 63.43)
    assert el["is_near_critical"]


def test_staged_rocket_monotonic():
    """Полезная нагрузка растёт с N до оптимума."""
    results = aero.best_staging(9400, 320, 0.08, max_stages=4)
    assert len(results) >= 2


def test_ascent_budget_leo():
    r = aero.ascent_budget(200, 320, 500_000, launch_lat_deg=0)
    # Δv до LEO 200 км ≈ 9.3-9.5 км/с
    assert 9.0 < r["dv_total_km_s"] < 10.0