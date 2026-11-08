"""tests/test_lambert_nrev.py — мультивитковый Ламберт (case 54)."""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from core import astrodynamics as aero
from core.lambert import lambert_universal, lambert_universal_nrev, MU_EARTH


def _T(r):
    return 2 * math.pi * math.sqrt(r ** 3 / MU_EARTH)


def test_0rev_compat():
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
    assert abs(math.hypot(*v1) - v1_expected) < 0.01


def test_returns_list():
    r = 7000.0
    T = _T(r)
    sols = lambert_universal_nrev(r, r, math.pi / 2, 1.25 * T, n_max=2)
    assert isinstance(sols, list)
    assert len(sols) >= 1


def test_contains_0rev():
    r = 7000.0
    T = _T(r)
    sols = lambert_universal_nrev(r, r, math.pi / 2, T / 4, n_max=2)
    n0 = [s for s in sols if s["revs"] == 0]
    assert len(n0) == 1
    assert n0[0]["branch"] == "single"


def test_multiple_revs():
    r = 7000.0
    T = _T(r)
    sols = lambert_universal_nrev(r, r, math.pi / 2, 3.25 * T, n_max=3)
    revs = {s["revs"] for s in sols}
    assert 0 in revs
    assert 1 in revs


def test_short_time_only_0rev():
    r = 7000.0
    T = _T(r)
    sols = lambert_universal_nrev(r, r, math.pi / 2, T / 4, n_max=3)
    revs = {s["revs"] for s in sols}
    assert revs == {0}


def test_v_magnitudes_sane():
    r = 7000.0
    T = _T(r)
    sols = lambert_universal_nrev(r, r, math.pi / 2, 2.25 * T, n_max=3)
    for s in sols:
        v1 = math.hypot(*s["v1_vec"])
        v2 = math.hypot(*s["v2_vec"])
        assert 0.1 < v1 < 50, f"v1={v1} revs={s['revs']} {s['branch']}"
        assert 0.1 < v2 < 50, f"v2={v2} revs={s['revs']} {s['branch']}"


def test_invalid_args():
    assert lambert_universal_nrev(-1, 7000, math.pi / 2, 1000) == []
    assert lambert_universal_nrev(7000, 7000, 0, 1000) == []
    assert lambert_universal_nrev(7000, 7000, math.pi / 2, -1) == []


def test_via_solve_case():
    r = aero.solve_case("54", H1=622, H2=622, dnu_deg=90, dt=1457, n_max=2)
    assert "error" not in r
    assert "solutions" in r
    assert r["n_found"] == len(r["solutions"])


def test_branches_have_vectors():
    r = 7000.0
    T = _T(r)
    sols = lambert_universal_nrev(r, r, math.pi / 2, 1.25 * T, n_max=2)
    for s in sols:
        assert len(s["v1_vec"]) == 2
        assert len(s["v2_vec"]) == 2
        assert s["branch"] in ("single", "left", "right")
