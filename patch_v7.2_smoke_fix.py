#!/usr/bin/env python3
"""patch_v7.2_smoke_fix.py — заменяет multiprocessing timeout на signal.SIGALRM.

Причина: multiprocessing.Process с forkserver-контекстом (Python 3.14 Linux)
не может pickle локальную функцию _target → PicklingError.

Фикс: signal.alarm(5) — проще, надёжнее, работает на Unix.
Для Windows — pytest.skip.

Идемпотентен. Резервная копия: tests/test_gui_smoke.py.v7.2.bak
"""
from __future__ import annotations
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TESTS = ROOT / "tests" / "test_gui_smoke.py"


NEW_BLOCK = r'''

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
'''


def main() -> int:
    print("[patch v7.2] signal.SIGALRM вместо multiprocessing")
    print("=" * 60)

    if not TESTS.is_file():
        print(f"[err] {TESTS} не найден", file=sys.stderr)
        return 1

    text = TESTS.read_text(encoding="utf-8")

    if "def test_all_54_cases_no_hang" in text and "_signal.SIGALRM" in text:
        print("[skip] уже с signal.SIGALRM")
        return 0

    # Обрезать старый блок _ALL_CASES..test_all_54 (от маркера)
    marker = "# ─────"
    idx = text.find(marker)
    if idx < 0:
        print("[warn] маркер не найден — оставляю всё как есть, дописываю в конец")

    # Удалить старый блок про 54 case (включая _run_with_timeout и _ALL_CASES),
    # если он есть. Ищем "# v7.1: полный обход" и режем до конца файла.
    cut_marker = "# v7.1: полный обход"
    cut_idx = text.find(cut_marker)
    if cut_idx > 0:
        # Найти заголовок раздела, который мы добавили
        section_start = text.rfind("# ═══════", 0, cut_idx)
        if section_start > 0:
            text = text[:section_start].rstrip()
        else:
            text = text[:cut_idx].rstrip()
        print("[ok] старый блок v7.1 удалён")

    bak = TESTS.with_suffix(".py.v7.2.bak")
    if not bak.exists():
        shutil.copy2(TESTS, bak)
        print(f"[backup] {bak}")

    text = text.rstrip() + NEW_BLOCK
    TESTS.write_text(text, encoding="utf-8")
    print("[ok] добавлен signal-based тест-обход")

    # Синтаксис
    try:
        compile(text, str(TESTS), "exec")
        print("[ok] синтаксис корректен")
    except SyntaxError as exc:
        print(f"[err] SyntaxError: {exc}", file=sys.stderr)
        return 2

    print("\n" + "=" * 60)
    print("[patch v7.2] Готово. Проверьте:")
    print("  pytest tests/test_gui_smoke.py -v")
    print("  pytest tests/ -q                    # 166 passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())