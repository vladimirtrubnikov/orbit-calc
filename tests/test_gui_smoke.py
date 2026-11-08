"""tests/test_gui_smoke.py — smoke-тесты GUI (offscreen)."""
import json
import os
import sys
from pathlib import Path

import pytest

# sys.path.insert: работает при pytest tests/test_gui_smoke.py напрямую
sys.path.insert(0, str(Path(__file__).parent.parent))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")
from PySide6.QtWidgets import QApplication

from gui.app import MainWindow


@pytest.fixture(scope="module")
def app():
    a = QApplication.instance() or QApplication([])
    yield a


def test_window_creates(app):
    w = MainWindow()
    assert w._current_sid == "1"
    w.close()


def test_all_cases_in_sidebar(app):
    w = MainWindow()
    assert len(w.sidebar._items) == 54
    w.close()


def test_case_switch(app):
    w = MainWindow()
    w.on_case_selected("11")
    assert w._current_sid == "11"
    assert "v_p" in w.form._fields
    w.close()


def test_run_case(app):
    w = MainWindow()
    w.on_case_selected("1")
    w.form.set_values({"a": 7000, "e": 0.1})
    w._run_live()
    assert w._current_result is not None
    assert w._current_result.error is None
    assert "a" in w._current_result.output
    w.close()


def test_lambert_54(app):
    w = MainWindow()
    w.on_case_selected("54")
    w.form.set_values(
        {"H1": 622, "H2": 622, "dnu_deg": 90, "dt": 1457, "n_max": 2}
    )
    w._run_live()
    assert w._current_result is not None
    assert w._current_result.error is None
    assert "n_found" in w._current_result.output
    w.close()


def test_export_json(app, tmp_path):
    w = MainWindow()
    w.on_case_selected("2")
    w.form.set_values({"H_p": 408, "H_a": 420})
    w._run_live()
    out = tmp_path / "result.json"
    w._export_json(str(out), w._current_result)
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["case"] == "2"
    assert "a" in data["output"]
    w.close()

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

# ═══════════════════════════════════════════════════════════════════════════
#  v7.2: тест-обход 54 case с signal.alarm (без multiprocessing)
# ═══════════════════════════════════════════════════════════════════════════
import signal as _signal


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


class _Timeout(Exception):
    pass


def _alarm_handler(signum, frame):
    raise _Timeout("5 s timeout")


@pytest.mark.parametrize("sid", sorted(_ALL_CASES, key=int))
def test_all_54_cases_no_hang(sid):
    """Каждый case: либо результат, либо валидная ошибка, но не зависание."""
    if not hasattr(_signal, "SIGALRM"):
        pytest.skip("SIGALRM недоступен (не Unix)")

    from gui.runner import run_case

    old = _signal.signal(_signal.SIGALRM, _alarm_handler)
    _signal.alarm(5)
    try:
        try:
            r = run_case(sid, _ALL_CASES[sid])
        finally:
            _signal.alarm(0)
        # r.error допустим — например, данные несовместны.
        # Главное — процесс завершился без зависания.
        assert hasattr(r, "stdout")
        assert hasattr(r, "output")
    except _Timeout:
        pytest.fail(f"case {sid}: ЗАВИС > 5 с (нужен полный мок ri/input)")
    finally:
        _signal.signal(_signal.SIGALRM, old)

# ═══════════════════════════════════════════════════════════════════════════
#  v7.3: кнопки Save / Reset в InputForm
# ═══════════════════════════════════════════════════════════════════════════


def _qsettings():
    from PySide6.QtCore import QSettings
    return QSettings("orbit-calc", "gui")


def test_save_button(app):
    """Кнопка Сохранить пишет значения в QSettings."""
    s = _qsettings()
    s.clear()
    s.sync()
    try:
        w = MainWindow()
        w.on_case_selected("1")
        w.form._fields["a"].setText("8000")
        w.form._fields["e"].setText("0.2")
        w.form._on_save()
        raw = s.value("case_1/inputs", "", type=str)
        assert raw, "QSettings не сохранил значения"
        import json
        data = json.loads(raw)
        assert data["a"] == 8000.0
        assert data["e"] == 0.2
        w.close()
    finally:
        s.clear()
        s.sync()


def test_reset_button(app):
    """Кнопка Сбросить возвращает defaults и удаляет сохранение."""
    s = _qsettings()
    s.clear()
    s.sync()
    try:
        w = MainWindow()
        w.on_case_selected("1")
        w.form._fields["a"].setText("8000")
        w.form._on_save()
        assert s.value("case_1/inputs", "", type=str)
        w.form._on_reset()
        assert s.value("case_1/inputs", "", type=str) == ""
        assert float(w.form._fields["a"].text()) == 7000.0
        assert float(w.form._fields["e"].text()) == 0.0
        w.close()
    finally:
        s.clear()
        s.sync()


def test_saved_values_restored_on_load(app):
    """Сохранённые значения подгружаются при переключении case."""
    s = _qsettings()
    s.clear()
    s.sync()
    try:
        w = MainWindow()
        w.on_case_selected("1")
        w.form._fields["a"].setText("8000")
        w.form._fields["e"].setText("0.25")
        w.form._on_save()

        # Переключение на другой case и обратно
        w.on_case_selected("2")
        w.on_case_selected("1")

        assert float(w.form._fields["a"].text()) == 8000.0
        assert float(w.form._fields["e"].text()) == 0.25
        w.close()
    finally:
        s.clear()
        s.sync()

def test_zero_button(app):
    """Кнопка Обнулить ставит все поля в 0, не трогая QSettings."""
    s = _qsettings()
    s.clear()
    s.sync()
    try:
        w = MainWindow()
        w.on_case_selected("1")
        w.form._fields["a"].setText("8000")
        w.form._fields["e"].setText("0.25")
        w.form._on_save()
        assert s.value("case_1/inputs", "", type=str)  # сохранено

        w.form._on_zero()
        assert w.form._fields["a"].text() == "0"
        assert w.form._fields["e"].text() == "0"
        # QSettings не тронут
        assert s.value("case_1/inputs", "", type=str)
        w.close()
    finally:
        s.clear()
        s.sync()
