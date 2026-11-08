#!/usr/bin/env python3
"""patch_v7.1_runner_fix.py — фикс runner.py + CASE_META для GUI.

1. gui/runner.py — полный мок: rf, ri, input, _ask_plot
2. core/astrodynamics.py — CASE_META["46"] = ["x", "y", "z", "vx", "vy", "vz"]
3. core/astrodynamics.py — CASE_META["41"/"42"/"52"] = ["system"]
4. gui/case_meta_ext.py — INPUT_META += x,y,z,vx,vy,vz,system
5. tests/test_gui_smoke.py — тест-обход всех 54 case

Идемпотентен. Резервные копии: *.v7.1.bak
"""
from __future__ import annotations
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


# ─────────────────────────────────────────────────────────────────────────
#  1. gui/runner.py — полный мок
# ─────────────────────────────────────────────────────────────────────────
NEW_RUNNER = r'''"""gui/runner.py — вызов _solve_* из CLI с полным перехватом ввода."""
from __future__ import annotations

import builtins
import io
from contextlib import contextmanager, redirect_stdout
from dataclasses import dataclass, field
from typing import Any

from cli import calculator as calc
from core import astrodynamics as aero


@dataclass
class RunResult:
    sid: str
    inputs: dict[str, Any]
    stdout: str = ""
    output: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    latex: list[str] = field(default_factory=list)


# Подсказки из input() — что вернуть, не забирая из очереди
_UNIT_HINTS = ("единица", "unit")
_CHOICE_HINTS = ("выбор",)          # 41, 42, 52, 30 — "1"/"2"/"3"
_MODE_HINTS = ("режим",)            # 30 — "1"/"2"
_POINT_HINTS = ("точка",)           # 32 — "p"/"a"/"r"


@contextmanager
def _full_mock(values: list):
    """Мокает rf, ri, input(), _ask_plot на время вызова CLI.

    Очередь `values` расходуется по порядку: каждая rf/ri/input (кроме
    известных подсказок) забирает следующее значение.
    """
    orig_rf = calc.rf
    orig_ri = calc.ri
    orig_input = builtins.input
    orig_ask = getattr(calc, "_ask_plot", None)
    queue = list(values)
    idx = [0]

    def _next():
        if idx[0] < len(queue):
            v = queue[idx[0]]
            idx[0] += 1
            return v
        return 0.0

    def mock_rf(prompt: str = ""):
        v = _next()
        try:
            print(f"{prompt}{v}")
        except Exception:
            pass
        return float(v)

    def mock_ri(prompt: str = ""):
        v = _next()
        try:
            print(f"{prompt}{int(float(v))}")
        except Exception:
            pass
        return int(float(v))

    def mock_input(prompt: str = ""):
        low = prompt.lower()
        # 1. Единицы → секунды (в GUI INPUT_META уже задаёт секунды)
        if any(h in low for h in _UNIT_HINTS):
            return "с"
        # 2. Выбор системы тел → "1" (Earth-Sun по умолчанию)
        if any(h in low for h in _CHOICE_HINTS):
            return "1"
        # 3. Режим повторной траектории → "1" (H → k)
        if any(h in low for h in _MODE_HINTS):
            return "1"
        # 4. Точка для case 32 → "p" (перигей — самый типичный)
        if any(h in low for h in _POINT_HINTS):
            return "p"
        # 5. Всё остальное (γ для case 4, ν, ...) — из очереди
        v = _next()
        try:
            print(f"{prompt}{v}")
        except Exception:
            pass
        return str(v)

    calc.rf = mock_rf
    calc.ri = mock_ri
    if orig_ask is not None:
        calc._ask_plot = lambda: False
    builtins.input = mock_input
    try:
        yield
    finally:
        calc.rf = orig_rf
        calc.ri = orig_ri
        if orig_ask is not None:
            calc._ask_plot = orig_ask
        builtins.input = orig_input


def run_case(sid: str, inputs: dict[str, Any]) -> RunResult:
    """Запускает пункт sid с параметрами inputs, перехватывает stdout.

    Для числовых полей — float. Для строк (system="1") — str.
    """
    res = RunResult(sid=sid, inputs=dict(inputs))

    try:
        res.latex = calc._latex_get(sid)
    except Exception:
        res.latex = []

    meta = aero.CASE_META.get(sid)
    if meta is None:
        res.error = f"Неизвестный случай {sid}"
        return res

    # Преобразование в порядке CALL order в CLI
    order = meta["inputs"]
    try:
        vals = []
        for k in order:
            v = inputs[k]
            if isinstance(v, str):
                vals.append(v)
            else:
                vals.append(float(v))
    except KeyError as exc:
        res.error = f"Не задан параметр {exc}"
        return res
    except (TypeError, ValueError) as exc:
        res.error = f"Некорректное значение: {exc}"
        return res

    buf = io.StringIO()
    try:
        with redirect_stdout(buf):
            with _full_mock(vals):
                calc._dispatch_solve(sid)
    except SystemExit:
        pass
    except Exception as exc:
        res.error = f"{type(exc).__name__}: {exc}"

    res.stdout = buf.getvalue()
    r = getattr(calc, "_RESULT", {})
    res.output = dict(r.get("output") or {})
    if res.error is None and r.get("error"):
        res.error = r["error"]
    return res
'''


# ─────────────────────────────────────────────────────────────────────────
#  2. core/astrodynamics.py — CASE_META fixes
# ─────────────────────────────────────────────────────────────────────────
CASE_META_FIXES = [
    # case 46: 6 координат вместо tuple
    (
        '    "46": {"name": "Вектор → элементы", "inputs": ["r", "v"]},',
        '    "46": {"name": "Вектор → элементы", '
        '"inputs": ["x", "y", "z", "vx", "vy", "vz"]},',
    ),
    # case 41, 42, 52 — system вместо параметров
    (
        '    "41": {"name": "Хилл/SOI", "inputs": ["system"]},',
        '    "41": {"name": "Хилл/SOI", "inputs": ["system"]},',
    ),
    (
        '    "42": {"name": "L1/L2 (прибл.)", "inputs": ["system"]},',
        '    "42": {"name": "L1/L2 (прибл.)", "inputs": ["system"]},',
    ),
    (
        '    "52": {"name": "CR3BP", "inputs": ["mu", "point"]},',
        '    "52": {"name": "CR3BP", "inputs": ["system"]},',
    ),
]


# ─────────────────────────────────────────────────────────────────────────
#  3. gui/case_meta_ext.py — доп. INPUT_META
# ─────────────────────────────────────────────────────────────────────────
EXTRA_INPUT_META = '''
# --- v7.1: добавочные ключи для case 46 (вектор состояния) и 41/42/52 ---
INPUT_META.update({
    "x":      ("x",       "км",    "float", -1e6, 1e6, 7000.0),
    "y":      ("y",       "км",    "float", -1e6, 1e6, 0.0),
    "z":      ("z",       "км",    "float", -1e6, 1e6, 0.0),
    "vx":     ("vx",      "км/с",  "float", -20, 20, 0.0),
    "vy":     ("vy",      "км/с",  "float", -20, 20, 7.5),
    "vz":     ("vz",      "км/с",  "float", -20, 20, 0.5),
    "system": ("Система тел", "",  "choice", 1, 3, 1),
})

CHOICES = {
    "system": [
        ("1", "Земля — Солнце"),
        ("2", "Луна — Земля"),
        ("3", "Марс — Солнце"),
    ],
}
'''


def _apply(path: Path, old: str, new: str, name: str,
           required: bool = True) -> bool:
    if not path.is_file():
        print(f"  [err] {path} не найден")
        return False
    text = path.read_text(encoding="utf-8")
    if new in text and old not in text:
        print(f"  [skip] {name}")
        return True
    if old not in text:
        if required:
            print(f"  [err] якорь не найден: {name}")
            print(f"        ожидалось: {old[:80]!r}")
            return False
        print(f"  [skip] {name} (не критично)")
        return True
    bak = path.with_suffix(path.suffix + ".v7.1.bak")
    if not bak.exists():
        shutil.copy2(path, bak)
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"  [ok]   {name}")
    return True


def _patch_runner() -> bool:
    print("\n[1] gui/runner.py")
    path = ROOT / "gui" / "runner.py"
    if not path.is_file():
        print(f"  [err] не найден")
        return False
    old_text = path.read_text(encoding="utf-8")
    if "_full_mock" in old_text:
        print("  [skip] уже с _full_mock")
        return True
    bak = path.with_suffix(".py.v7.1.bak")
    if not bak.exists():
        shutil.copy2(path, bak)
    path.write_text(NEW_RUNNER, encoding="utf-8")
    print("  [ok] runner.py перезаписан (полный мок)")
    return True


def _patch_case_meta() -> bool:
    print("\n[2] core/astrodynamics.py — CASE_META")
    path = ROOT / "core" / "astrodynamics.py"
    if not path.is_file():
        print(f"  [err] не найден")
        return False
    ok = True
    for old, new in CASE_META_FIXES:
        if old == new:
            continue  # 41/42 не меняем
        ok &= _apply(path, old, new,
                     f"CASE_META: {old.strip()[:50]}",
                     required=False)
    return ok


def _patch_input_meta() -> bool:
    print("\n[3] gui/case_meta_ext.py — INPUT_META")
    path = ROOT / "gui" / "case_meta_ext.py"
    if not path.is_file():
        print(f"  [err] не найден")
        return False
    text = path.read_text(encoding="utf-8")
    if "v7.1: добавочные ключи" in text:
        print("  [skip] уже есть")
        return True
    bak = path.with_suffix(".py.v7.1.bak")
    if not bak.exists():
        shutil.copy2(path, bak)
    path.write_text(text.rstrip() + "\n" + EXTRA_INPUT_META, encoding="utf-8")
    print("  [ok] добавлены x,y,z,vx,vy,vz,system + CHOICES")
    return True


def _add_54_case_test() -> bool:
    print("\n[4] tests/test_gui_smoke.py — тест-обход 54 case")
    path = ROOT / "tests" / "test_gui_smoke.py"
    if not path.is_file():
        print(f"  [err] не найден")
        return False
    text = path.read_text(encoding="utf-8")
    if "test_all_54_cases_no_hang" in text:
        print("  [skip] уже есть")
        return True
    bak = path.with_suffix(".py.v7.1.bak")
    if not bak.exists():
        shutil.copy2(path, bak)

    test_add = '''

# ─────────────────────────────────────────────────────────────────────────
#  v7.1: полный обход 54 case — проверка, что ничего не висит
# ─────────────────────────────────────────────────────────────────────────
import signal


# Примеры валидных входов для каждого case
_ALL_CASES = {
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
    "15": {"H_p": 200, "h": 51500},
    "16": {"H_a": 400, "h": 51500},
    "17": {"a": 7000, "H_p": 200},
    "18": {"a": 6600, "H_a": 400},
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
    "41": {"system": "1"},
    "42": {"system": "1"},
    "43": {"T1": 5400, "T2": 86164},
    "44": {"H": 400, "di": 28.5},
    "45": {"H": 400, "gamma_deg": 10},
    "46": {"x": 7000, "y": 0, "z": 0, "vx": 0, "vy": 7.5, "vz": 0.5},
    "47": {"H": 700, "e": 0.001, "i": 98.2},
    "48": {"rho": 1000, "rho_dot": 0.5, "el": 30},
    "49": {"H": 200, "isp": 320, "m0": 500_000},
    "50": {"dv": 1500, "isp": 320, "m0": 1000, "m_dry": 100},
    "51": {"dv": 9400, "isp": 320, "epsilon": 0.08},
    "52": {"system": "1"},
    "53": {"H": 700, "e": 0.001, "i": 63.43},
    "54": {"H1": 622, "H2": 622, "dnu_deg": 90, "dt": 1457, "n_max": 2},
}


def _run_with_timeout(sid, inputs, seconds=5):
    """Запускает runner в дочернем процессе с таймаутом."""
    import multiprocessing as mp
    from gui.runner import run_case

    def _target(q):
        try:
            r = run_case(sid, inputs)
            q.put(("ok", r.error, len(r.output)))
        except Exception as exc:
            q.put(("exc", f"{type(exc).__name__}: {exc}", 0))

    q = mp.Queue()
    p = mp.Process(target=_target, args=(q,))
    p.start()
    p.join(seconds)
    if p.is_alive():
        p.terminate()
        p.join(1)
        return ("hang", None, 0)
    if not q.empty():
        return q.get()
    return ("crash", "no result", 0)


import pytest

@pytest.mark.parametrize("sid", sorted(_ALL_CASES))
def test_all_54_cases_no_hang(sid):
    """Каждый case из 54 — либо успех, либо валидная ошибка, но не зависание."""
    status, err, _n = _run_with_timeout(sid, _ALL_CASES[sid], seconds=5)
    assert status != "hang", f"case {sid}: ЗАВИС (нужен полный мок ri/input)"
    assert status != "crash", f"case {sid}: CRASH — {err}"
    # error допустим — некоторые примеры могут быть несовместны
    # главное, что процесс завершился
'''
    path.write_text(text.rstrip() + test_add, encoding="utf-8")
    print("  [ok] добавлен test_all_54_cases_no_hang")
    return True


def main() -> int:
    print("[patch v7.1] Фикс runner.py + CASE_META + тест-обход 54 case")
    print("=" * 60)

    ok = True
    ok &= _patch_runner()
    ok &= _patch_case_meta()
    ok &= _patch_input_meta()
    ok &= _add_54_case_test()

    # Синтаксис
    print("\n[verify] синтаксис")
    for rel in ("gui/runner.py", "core/astrodynamics.py",
                "gui/case_meta_ext.py", "tests/test_gui_smoke.py"):
        p = ROOT / rel
        if not p.is_file():
            continue
        try:
            compile(p.read_text(encoding="utf-8"), str(p), "exec")
            print(f"  [ok] {rel}")
        except SyntaxError as exc:
            print(f"  [err] {rel}: {exc}")
            ok = False

    print("\n" + "=" * 60)
    print("[patch v7.1] Готово" if ok else "[patch v7.1] Ошибки")
    if ok:
        print("\nПроверка:")
        print("  pytest tests/test_gui_smoke.py -v")
        print("  # ожидание: 7 passed (включая test_lambert_54 и обход 54 case)")
        print("\nЗапуск GUI:")
        print("  python3 -m gui")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())