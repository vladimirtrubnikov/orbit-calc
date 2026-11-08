#!/usr/bin/env python3
"""patch_v7.1_gui_fix.py — 3 фикса GUI v7.

1. gui/input_form.py: textChanged/returnPressed → лямбды (Qt передаёт 1 арг)
2. gui/runner.py: полный мок rf/ri/input/_ask_plot (не только rf)
3. tests/test_gui_smoke.py: sys.path.insert для прямого pytest

Идемпотентен. Резервные копии: *.v7.1.bak
"""
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parent


# ─── 1. InputForm ─────────────────────────────────────────────────────────
INPUT_FORM_OLD = '''            edit.setStyleSheet(self._edit_style())
            edit.textChanged.connect(self.changed.emit)
            edit.returnPressed.connect(self.submit.emit)'''

INPUT_FORM_NEW = '''            edit.setStyleSheet(self._edit_style())
            # Qt textChanged передаёт 1 аргумент — оборачиваем в лямбду
            edit.textChanged.connect(lambda _=None: self.changed.emit())
            edit.returnPressed.connect(lambda: self.submit.emit())'''


# ─── 2. runner.run_case — полный мок ──────────────────────────────────────
RUNNER_OLD = '''    order = meta["inputs"]
    try:
        vals = [float(inputs[k]) for k in order]
    except KeyError as exc:
        res.error = f"Не задан параметр {exc}"
        return res
    except (TypeError, ValueError) as exc:
        res.error = f"Некорректное значение: {exc}"
        return res

    old_ask = getattr(calc, "_ask_plot", None)
    calc._ask_plot = lambda: False

    buf = io.StringIO()
    try:
        with redirect_stdout(buf):
            with calc._input_queue(vals):
                calc._dispatch_solve(sid)
    except SystemExit:
        pass
    except Exception as exc:
        res.error = f"{type(exc).__name__}: {exc}"
    finally:
        if old_ask is not None:
            calc._ask_plot = old_ask'''

RUNNER_NEW = '''    order = meta["inputs"]
    try:
        vals = [float(inputs[k]) for k in order]
    except KeyError as exc:
        res.error = f"Не задан параметр {exc}"
        return res
    except (TypeError, ValueError) as exc:
        res.error = f"Некорректное значение: {exc}"
        return res

    # Полный мок: rf, ri, input, _ask_plot
    import builtins
    orig_rf = calc.rf
    orig_ri = calc.ri
    orig_ask = getattr(calc, "_ask_plot", None)
    queue = list(vals)
    idx = [0]

    def mock_rf(prompt=""):
        if idx[0] < len(queue):
            v = queue[idx[0]]
            idx[0] += 1
            return float(v)
        return 0.0

    def mock_ri(prompt=""):
        if idx[0] < len(queue):
            v = int(queue[idx[0]])
            idx[0] += 1
            return v
        return 0

    def mock_input(prompt=""):
        # Единица измерения → секунды (как в GUI по умолчанию)
        low = prompt.lower()
        if "единица" in low or "unit" in low:
            return "с"
        # γ / выбор режима → дефолт (пустая строка → or "1" / or 0.0)
        return ""

    calc.rf = mock_rf
    calc.ri = mock_ri
    if orig_ask is not None:
        calc._ask_plot = lambda: False

    buf = io.StringIO()
    try:
        with redirect_stdout(buf):
            # Патчим builtins.input на время вызова
            orig_input = builtins.input
            builtins.input = mock_input
            try:
                calc._dispatch_solve(sid)
            finally:
                builtins.input = orig_input
    except SystemExit:
        pass
    except Exception as exc:
        res.error = f"{type(exc).__name__}: {exc}"
    finally:
        calc.rf = orig_rf
        calc.ri = orig_ri
        if orig_ask is not None:
            calc._ask_plot = orig_ask'''


# ─── 3. tests/test_gui_smoke.py — sys.path ────────────────────────────────
TESTS_OLD = '''import json
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")
from PySide6.QtWidgets import QApplication

from gui.app import MainWindow'''

TESTS_NEW = '''import json
import os
import sys
from pathlib import Path

import pytest

# sys.path.insert: работает при pytest tests/test_gui_smoke.py напрямую
sys.path.insert(0, str(Path(__file__).parent.parent))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")
from PySide6.QtWidgets import QApplication

from gui.app import MainWindow'''


def _patch(path: Path, old: str, new: str, name: str) -> bool:
    if not path.is_file():
        print(f"  [err] {path} не найден", file=sys.stderr)
        return False
    text = path.read_text(encoding="utf-8")
    if new in text:
        print(f"  [skip] {name}")
        return True
    if old not in text:
        print(f"  [err] {name}: якорь не найден", file=sys.stderr)
        # диагностика
        for i, line in enumerate(text.splitlines()[:15], 1):
            if "textChanged" in line or "import builtins" in line or "QT_QPA" in line:
                print(f"    L{i}: {line!r}", file=sys.stderr)
        return False
    bak = path.with_suffix(path.suffix + ".v7.1.bak")
    if not bak.exists():
        shutil.copy2(path, bak)
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"  [ok]   {name}")
    return True


def main() -> int:
    print("[patch v7.1] GUI fixes")
    print("=" * 50)

    ok = True
    print("\n[1] gui/input_form.py")
    ok &= _patch(
        ROOT / "gui" / "input_form.py",
        INPUT_FORM_OLD, INPUT_FORM_NEW,
        "textChanged/returnPressed → лямбды",
    )

    print("\n[2] gui/runner.py")
    ok &= _patch(
        ROOT / "gui" / "runner.py",
        RUNNER_OLD, RUNNER_NEW,
        "полный мок rf/ri/input",
    )

    print("\n[3] tests/test_gui_smoke.py")
    ok &= _patch(
        ROOT / "tests" / "test_gui_smoke.py",
        TESTS_OLD, TESTS_NEW,
        "sys.path.insert",
    )

    # Синтаксис
    print("\n[4] Синтаксис")
    for rel in ("gui/input_form.py", "gui/runner.py", "tests/test_gui_smoke.py"):
        try:
            compile((ROOT / rel).read_text(encoding="utf-8"), rel, "exec")
            print(f"  [ok]   {rel}")
        except SyntaxError as exc:
            print(f"  [err]  {rel}: {exc}", file=sys.stderr)
            ok = False

    print("\n" + "=" * 50)
    if ok:
        print("[patch v7.1] Готово. Проверьте:")
        print("  pytest tests/test_gui_smoke.py -v")
        print("  pytest tests/ -q                    # 112 passed")
        print("  python3 -m gui")
    else:
        print("[patch v7.1] Есть ошибки — см. выше", file=sys.stderr)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())