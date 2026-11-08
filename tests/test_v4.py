"""tests/test_v4.py — тесты v4: solve_case + shadow verify + делегирование."""

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from core import astrodynamics as aero


EXAMPLES = {
    "1":  {"a": 7000, "e": 0.1},
    "2":  {"H_p": 200, "H_a": 400},
    "3":  {"H_p": 200, "e": 0.01},
    "4":  {"H": 200, "v": 7.8, "gamma": 0},
    "5":  {"h": 52000, "eps": -28.5},
    "6":  {"H_p": 200, "v_p": 7.9},
    "7":  {"h": 52000, "a": 7000},
    "8":  {"T": 5400},
    "9":  {"H_a": 400, "e": 0.01},
    "10": {"H_a": 400, "v_a": 7.6},
    "11": {"v_p": 7.9, "v_a": 7.6},
    "12": {"h": 52000, "e": 0.01},
    "13": {"p": 6800, "e": 0.01},
    "14": {"T": 5400, "e": 0.01},
    "15": {"H_p": 200, "h": 52000},
    "16": {"H_a": 400, "h": 51500},   # v4.4: 52000 → e<0; 51500 → e≈0.018
    "17": {"a": 7000, "H_p": 200},
    "18": {"a": 6600, "H_a": 400},    # v4.4: 7000 → e<0; 6600 → e≈0.027
    "19": {"T": 5400, "H_p": 200},
    "20": {"T": 5400, "v_p": 7.9},
    "21": {"e": 0.01, "v_p": 7.9},
    "22": {"e": 0.01, "v_a": 7.6},
    "23": {"H_p": 200, "v_a": 7.5},
    "24": {"H_a": 400, "v_p": 8.0},
    "25": {"H1": 200, "H2": 35786, "di": 28.5},
    "26": {"H": 400, "dphi": 30, "N": 3},
    "27": {"H1": 200, "H2": 35786, "dnu_deg": 180, "dt": 18929},
    "28": {"H": 200, "v": 7.8, "nu_deg": 0},
    "29": {"H": 700},
    "30": {"H": 550},
    "31": {"Ap": 420, "Pe": 408},
    "32": {"Ap": 420, "Pe": 408, "r": 6785},
    "33": {"H": 400},
    "34": {"H1": 200, "H2": 35786},
    "35": {"H1": 200, "H2": 35786, "H_bi": 200000},
    "36": {"dv": 1500, "m0": 1000, "isp": 320},
    "37": {"m_fuel": 400, "m0": 1000, "isp": 320},
    "38": {"a": 7000, "e": 0.1, "nu1": 0, "nu2": 180},
    "39": {"a": 7000, "e": 0.1, "t": 1000},
    "40": {"H_p": 200, "v_inf": 3.0},
    "41": {"system": "earth-sun"},
    "42": {"system": "earth-sun"},
    "43": {"T1": 5400, "T2": 86164},
    "44": {"H": 400, "di": 28.5},
    "45": {"H": 400, "gamma_deg": 10},
    "46": {"r": (7000, 0, 0), "v": (0, 7.5, 0.5)},
    "47": {"H": 700, "e": 0.001, "i": 98.2},
    "48": {"rho": 1000, "rho_dot": 0.5, "el": 30},
    "49": {"H": 200, "isp": 320, "m0": 500_000},
    "50": {"dv": 1500, "isp": 320, "m0": 1000, "m_dry": 100},
    "51": {"dv": 9400, "isp": 320, "epsilon": 0.08},
    "52": {"mu": 3.003e-6, "point": "L1"},
    "53": {"H": 700, "e": 0.001, "i": 63.43},
}


def test_case_meta_complete():
    for i in range(1, 55):
        assert str(i) in aero.CASE_META, f"Нет CASE_META для {i}"


def test_solvers_registry_complete():
    assert len(aero._SOLVERS) >= 53


@pytest.mark.parametrize("sid", sorted(EXAMPLES))
def test_solve_case_ok(sid):
    r = aero.solve_case(sid, **EXAMPLES[sid])
    assert "error" not in r, f"{sid}: {r.get('error')}"
    assert isinstance(r, dict) and r


def test_solve_case_wrong_args():
    assert "error" in aero.solve_case("1", wrong_arg=5)


def test_solve_case_unknown():
    assert "error" in aero.solve_case("999")


def test_lambert_module():
    """core.lambert даёт тот же результат, что aero через делегатор."""
    from core.lambert import lambert_universal
    r1, r2 = 6571.0, 42157.0
    a_t = (r1 + r2) / 2
    dt = math.pi * math.sqrt(a_t ** 3 / aero.MU_EARTH)
    res = lambert_universal(r1, r2, math.pi, dt)
    assert res is not None
    v1, v2 = res
    v1_expected = math.sqrt(aero.MU_EARTH * (2 / r1 - 1 / a_t))
    assert abs(math.hypot(*v1) - v1_expected) < 0.01


def test_lambert_delegator_matches_aero():
    """cli._lambert_universal == aero.lambert_universal."""
    from cli import calculator as calc
    r1, r2 = 6571.0, 42157.0
    dt = 18929.0
    cli_res = calc._lambert_universal(r1, r2, math.pi, dt)
    aero_res = aero.lambert_universal(r1, r2, math.pi, dt)
    assert cli_res is not None and aero_res is not None
    for c, a in zip(cli_res, aero_res):
        assert abs(c[0] - a[0]) < 1e-10
        assert abs(c[1] - a[1]) < 1e-10


def test_print_orbit_uses_aero():
    """_print_orbit_result не дублирует формулы — использует aero."""
    import inspect
    from cli import calculator as calc
    src = inspect.getsource(calc._print_orbit_result)
    assert 'aero.elements_from_a_e' in src
    # Inline-формул не должно остаться:
    assert "r_p = a * (1 - e)" not in src


@pytest.mark.parametrize("sid", ["1", "3", "5", "11", "17"])
def test_shadow_verify_no_mismatch(sid, caplog):
    """Shadow verify не выдаёт предупреждений о расхождении."""
    from cli import calculator as calc
    vals = [float(v) for v in EXAMPLES[sid].values()]
    calc._VERIFY_ENABLED = True
    try:
        with calc._input_queue(vals):
            calc._dispatch_solve(sid)
    finally:
        calc._VERIFY_ENABLED = False
    mismatches = [r for r in caplog.records
                  if "verify" in r.getMessage().lower()
                  and r.levelname in ("WARNING", "ERROR")]
    assert not mismatches, f"verify mismatch: {[r.getMessage() for r in mismatches]}"


def test_json_structure():
    import json
    from cli import calculator as calc
    calc._RESULT = {"case": "1", "output": {"a": 7000.0, "e": 0.1},
                    "error": None, "kind": "orbit"}
    s = json.dumps(calc._RESULT, indent=2)
    assert '"case": "1"' in s
    assert "7000" in s


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
