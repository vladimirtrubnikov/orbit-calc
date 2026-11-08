"""tests/test_solvers.py — smoke tests для cli/calculator.py"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from cli import calculator as calc

MU = calc.MU_EARTH
R = calc.R_EARTH


def test_sma_gso():
    a = calc.sma(35786, 35786)
    assert abs(a - 42164.17) < 0.5


def test_ecc_circular():
    assert calc.ecc(35786, 35786) < 1e-6


def test_iss_orbit():
    ap, pe = 420, 408
    a, e = calc.sma(ap, pe), calc.ecc(ap, pe)
    r_p, r_a = pe + R, ap + R
    assert abs(a - (r_p + r_a) / 2) < 1e-6
    assert abs(e - (r_a - r_p) / (r_a + r_p)) < 1e-12


def test_vis_viva_gso():
    assert abs(math.sqrt(MU / (35786 + R)) - 3.0747) < 0.001


def test_hohmann_leo_gso():
    h1, h2 = 200, 35786
    r1, r2 = h1 + R, h2 + R
    a_t = (r1 + r2) / 2
    v1c, v2c = math.sqrt(MU / r1), math.sqrt(MU / r2)
    v1t = math.sqrt(MU * (2 / r1 - 1 / a_t))
    v2t = math.sqrt(MU * (2 / r2 - 1 / a_t))
    total = abs(v1t - v1c) * 1000 + abs(v2c - v2t) * 1000
    assert abs(total - 3940) < 50


def test_tsiolkovsky_roundtrip():
    dv, m0, isp = 1500, 1000, 320
    ve = isp * calc.G0
    fuel = m0 * (1 - math.exp(-dv / ve))
    assert abs(ve * math.log(m0 / (m0 - fuel)) - dv) < 1e-6


def test_state_vector_roundtrip():
    a, e, i_deg = 7000.0, 0.05, 45.0
    r_p = a * (1 - e)
    v_p = math.sqrt(MU * (2 / r_p - 1 / a))
    el = calc._elements_from_state(
        (r_p, 0.0, 0.0),
        (0.0, v_p * math.cos(math.radians(i_deg)),
         v_p * math.sin(math.radians(i_deg))),
    )
    assert abs(el["a"] - a) < 1e-6
    assert abs(el["e"] - e) < 1e-6
    assert abs(el["i"] - i_deg) < 1e-6


def test_dispatch_completeness():
    for i in range(1, 55):
        assert str(i) in calc._DISPATCH, f"Отсутствует пункт {i}"


def test_dispatch_count():
    assert len(calc._DISPATCH) >= 46


def test_keys_to_solver_valid():
    for keys, sid in calc._KEYS_TO_SOLVER.items():
        assert str(sid) in calc._DISPATCH
        assert len(keys) == 2


def test_from_parse_gso():
    result = calc._parse_from("Ap=35786,Pe=35786")
    assert result is not None
    sid, vals = result
    assert sid == 2
    assert vals == [35786.0, 35786.0]


# ═══════════════════════════════════════════════════════════════════════════
#  v3.5: regression-тесты для _c / _print_latex / LaTeX-формул
# ═══════════════════════════════════════════════════════════════════════════


def test_color_helper():
    """_c возвращает str и не падает для любого разумного входа."""
    from cli import calculator as calc
    for color in ("g", "y", "r", "b", "c", "d", "0", "unknown"):
        result = calc._c("x", color)
        assert isinstance(result, str), f"color={color!r}"
        assert "x" in result, f"color={color!r}"


def test_latex_helper(capsys):
    """_print_latex не падает при _SHOW_LATEX=True (ловит NameError: _c)."""
    from cli import calculator as calc
    old = calc._SHOW_LATEX
    calc._SHOW_LATEX = True
    try:
        calc._print_latex("47")
        calc._print_latex("1")
        calc._print_latex("999")   # неизвестный — не должен падать
    finally:
        calc._SHOW_LATEX = old
    out = capsys.readouterr().out
    assert "LaTeX" in out or out == ""  # для "999" — пусто, допустимо


def test_latex_formulas_known():
    """LaTeX определён для новых пунктов 47, 49, 51, 52, 53."""
    from core import latex_formulas as lf
    for sid in ("47", "49", "51", "52", "53"):
        formulas = lf.get_formulas(sid)
        assert isinstance(formulas, list), f"sid={sid}"
        assert len(formulas) > 0, f"Нет LaTeX для случая {sid}"
        for f in formulas:
            assert isinstance(f, str) and f, f"пустая формула в {sid}"


def test_latex_formulas_unknown_empty():
    """Для неизвестного sid get_formulas возвращает []."""
    from core import latex_formulas as lf
    assert lf.get_formulas("nonexistent") == []
    assert lf.get_formulas("54") == []   # 54 пока не реализован


def test_dispatch_47_53_present():
    """Все новые пункты 47-53 зарегистрированы в _DISPATCH."""
    from cli import calculator as calc
    for i in range(47, 54):
        sid = str(i)
        assert sid in calc._DISPATCH, f"Отсутствует пункт {sid}"
        assert callable(calc._DISPATCH[sid]), f"Пункт {sid} не callable"


def test_dispatch_solve_dispatcher():
    """_dispatch_solve зовёт _DISPATCH[sid] без падения."""
    from cli import calculator as calc

    called = []
    original = calc._DISPATCH["47"]
    calc._DISPATCH["47"] = lambda: called.append("ok")
    old = calc._SHOW_LATEX
    calc._SHOW_LATEX = False
    try:
        calc._dispatch_solve("47")
    finally:
        calc._DISPATCH["47"] = original
        calc._SHOW_LATEX = old
    assert called == ["ok"]
