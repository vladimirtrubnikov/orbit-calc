"""gui/runner.py — вызов _solve_* из CLI с полным перехватом ввода."""
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
