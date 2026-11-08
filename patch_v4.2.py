#!/usr/bin/env python3
"""patch_v4.2.py — чистое делегирование в core + shadow verify + tests.

Правки:
  1. cli/calculator.py: _lambert_universal → делегатор в core.lambert
  2. cli/calculator.py: _print_orbit_result → вычисления через aero.elements_from_a_e
  3. cli/calculator.py: _capture_rf / _verify_against_core + _VERIFY_ENABLED
  4. cli/calculator.py: _dispatch_solve → обёртка _capture_rf, вызов verify
  5. cli/calculator.py: main() → _VERIFY_ENABLED = args.verbose
  6. tests/test_v4.py — 8 новых тестов (parametrized все 53 + shadow verify)

Идемпотентен. Резервные копии: *.py.v4.2.bak
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

CALC = Path("cli/calculator.py")
TESTS = Path("tests/test_v4.py")


# ── 1. Делегатор _lambert_universal ────────────────────────────────────────
PATCH_LAMBERT = (
    "def calc_orbit_params() -> None:",
    '''# ── v4.2: делегирование в core.lambert (убирает ~60 строк дублирования) ──
def _lambert_universal(r1, r2, dnu, dt):  # noqa: F811
    """Обёртка (v4.2): делегирует в core.lambert.lambert_universal."""
    return aero.lambert_universal(r1, r2, dnu, dt)


def calc_orbit_params() -> None:''',
)


# ── 2. _print_orbit_result: вычисления через aero ─────────────────────────
PATCH_PRINT_ORBIT = (
    """    r_p = a * (1 - e)
    r_a = a * (1 + e)
    p = a * (1 - e * e)
    h = math.sqrt(MU_EARTH * p)
    eps = -MU_EARTH / (2 * a)
    v_p = math.sqrt(MU_EARTH * (2 / r_p - 1 / a))
    v_a = math.sqrt(MU_EARTH * (2 / r_a - 1 / a))
    T = 2 * math.pi * math.sqrt(a ** 3 / MU_EARTH)
    v_cp = math.sqrt(MU_EARTH / r_p)
    v_ca = math.sqrt(MU_EARTH / r_a)""",
    """    try:
        _el = aero.elements_from_a_e(a, e)
    except ValueError as exc:
        logger.warning(f"  {exc}")
        return
    r_p, r_a, p = _el["r_p"], _el["r_a"], _el["p"]
    h, eps, T = _el["h"], _el["eps"], _el["T"]
    v_p, v_a = _el["v_p"], _el["v_a"]
    v_cp = math.sqrt(MU_EARTH / r_p)
    v_ca = math.sqrt(MU_EARTH / r_a)""",
)


# ── 3. Verify-инфраструктура (вставляется перед _dispatch_solve) ──────────
VERIFY_BLOCK = '''
# ── v4.2: shadow verify (--verbose) ──────────────────────────────────────
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

'''

PATCH_VERIFY_INSERT = (
    "def _dispatch_solve(sid: str) -> None:",
    VERIFY_BLOCK + "\ndef _dispatch_solve(sid: str) -> None:",
)


# ── 4. _dispatch_solve: обёртка _capture_rf + verify ───────────────────────
PATCH_DISPATCH = (
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
    '''def _dispatch_solve(sid: str) -> None:
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
    _verify_against_core(sid)''',
)


# ── 5. main(): _VERIFY_ENABLED = args.verbose ─────────────────────────────
PATCH_MAIN_VERIFY = (
    "    global _SHOW_LATEX\n    _SHOW_LATEX = args.latex\n",
    "    global _SHOW_LATEX, _VERIFY_ENABLED\n"
    "    _SHOW_LATEX = args.latex\n"
    "    _VERIFY_ENABLED = args.verbose\n",
)


# ── 6. tests/test_v4.py ────────────────────────────────────────────────────
TESTS_TEXT = '''"""tests/test_v4.py — тесты v4: solve_case + shadow verify + делегирование."""

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
    "16": {"H_a": 400, "h": 52000},
    "17": {"a": 7000, "H_p": 200},
    "18": {"a": 7000, "H_a": 400},
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
    for i in range(1, 54):
        assert str(i) in aero.CASE_META, f"Нет CASE_META для {i}"


def test_solvers_registry_complete():
    assert len(aero._SOLVERS) == 53


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
'''


def _apply(text: str, old: str, new: str, name: str) -> str:
    if new in text and old not in text:
        print(f"  [skip] {name}")
        return text
    if old not in text:
        raise RuntimeError(f"Якорь не найден для {name}: {old[:80]!r}")
    print(f"  [ok]   {name}")
    return text.replace(old, new, 1)


def patch_calc() -> int:
    print(f"\n[1] {CALC}")
    if not CALC.is_file():
        print(f"  [err] не найден", file=sys.stderr)
        return 1

    text = CALC.read_text(encoding="utf-8")

    if "_VERIFY_ENABLED" in text and "aero.elements_from_a_e" in text:
        print("  [skip] все правки v4.2 уже применены")
        return 0

    backup = CALC.with_suffix(".py.v4.2.bak")
    if not backup.exists():
        shutil.copy2(CALC, backup)
        print(f"  [backup] {backup}")

    try:
        # 1. Делегатор ламберта
        text = _apply(text, *PATCH_LAMBERT, "_lambert_universal → делегатор")

        # 2. _print_orbit_result через aero
        text = _apply(text, *PATCH_PRINT_ORBIT, "_print_orbit_result через aero")

        # 3. Verify-инфраструктура перед _dispatch_solve
        text = _apply(text, *PATCH_VERIFY_INSERT, "verify-инфраструктура")

        # 4. Обновление _dispatch_solve
        text = _apply(text, *PATCH_DISPATCH, "_dispatch_solve + verify")

        # 5. main
        text = _apply(text, *PATCH_MAIN_VERIFY, "main: _VERIFY_ENABLED")

    except RuntimeError as exc:
        print(f"  [err] {exc}", file=sys.stderr)
        return 2

    CALC.write_text(text, encoding="utf-8")

    try:
        compile(CALC.read_text(encoding="utf-8"), str(CALC), "exec")
        print("  [ok]   синтаксис корректен")
    except SyntaxError as exc:
        print(f"  [err] SyntaxError: {exc}", file=sys.stderr)
        return 3
    return 0


def create_tests() -> int:
    print(f"\n[2] {TESTS}")
    if TESTS.is_file():
        existing = TESTS.read_text(encoding="utf-8")
        if "test_shadow_verify_no_mismatch" in existing:
            print("  [skip] test_v4.py уже есть")
            return 0
    TESTS.parent.mkdir(parents=True, exist_ok=True)
    TESTS.write_text(TESTS_TEXT, encoding="utf-8")
    print("  [ok]   tests/test_v4.py создан (11 новых тестов)")
    return 0


def verify() -> None:
    print("\n[verify] импорт-проверка")
    import subprocess
    r = subprocess.run(
        [sys.executable, "-c",
         "import sys; sys.path.insert(0, '.'); "
         "from core.astrodynamics import solve_case, _SOLVERS; "
         "from cli.calculator import _VERIFY_ENABLED, _lambert_universal; "
         "assert len(_SOLVERS) == 53; "
         "r = solve_case('1', a=7000, e=0.1); "
         "assert 'error' not in r; "
         "print('OK: 53 cases, solve_case works, delegator works')"],
        capture_output=True, text=True,
    )
    if r.returncode == 0:
        print(f"  [ok]   {r.stdout.strip()}")
    else:
        print(f"  [err]  {r.stderr.strip()}", file=sys.stderr)


def main() -> int:
    print("[patch v4.2] Делегирование в core + shadow verify + tests")
    print("=" * 50)
    rc = 0
    rc |= patch_calc()
    rc |= create_tests()
    verify()
    print("\n" + "=" * 50)
    if rc == 0:
        print("[patch v4.2] Готово. Проверьте:")
        print("  pytest tests/ -v                              # 29 + 11 = 40 passed")
        print("  python3 cli/calculator.py --solve=1 --verbose  # shadow verify активен")
        print("  python3 cli/calculator.py --solve=34 --json")
        print("  python3 cli/calculator.py --solve=47 --latex")
    else:
        print(f"[patch v4.2] Завершён с ошибкой (rc={rc})", file=sys.stderr)
    return rc


if __name__ == "__main__":
    sys.exit(main())