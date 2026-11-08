#!/usr/bin/env python3
"""patch_v5_selfcontained.py — делает проект самодостаточным для PyInstaller.

Создаёт (если отсутствуют):
  core/__init__.py
  core/base.py                — константы, rf, ri, _t, sma, ecc, ...
  core/optimization.py        — phasing_orbit (через aero)
  gui/__init__.py
  gui/animations.py           — animate_hohmann, animate_phasing (заглушки)
  gui/plots.py                — _ask_plot, plot_* (matplotlib или no-op)
  build/orbit-calc.spec
  build/build_all.sh
"""

from __future__ import annotations

import shutil
import stat
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

FILES = {
    "core/__init__.py": '''"""core — орбитальные и астрономические расчёты orbit-calc."""

__version__ = "0.5.0"
''',

    "core/base.py": '''"""core/base.py — константы и базовые функции orbit-calc.

Единственный источник MU_EARTH, R_EARTH, G0 для всего проекта.
"""

from __future__ import annotations

import logging
import math
import sys

# ── Константы ──────────────────────────────────────────────────────────────
MU_EARTH = 398_600.4418      # км³/с²
R_EARTH = 6_378.0            # км (экваториальный радиус)
G0 = 9.80665                 # м/с²

LANG = "ru"

logger = logging.getLogger("orbit_calc")


# ── Локализация (минимальный словарь) ─────────────────────────────────────
_TRANSLATIONS = {
    "ru": {
        "menu_title": "Универсальный калькулятор орбитальных расчётов",
        "menu_1": "Параметры орбиты (Ap/Pe)",
        "menu_2": "Скорость в точке орбиты",
        "menu_3": "Круговая орбита",
        "menu_4": "Перелёт Хомана",
        "menu_5": "Биэллиптический перелёт",
        "menu_6": "Циолковский: dv → топливо",
        "menu_7": "Обратный Циолковский: топливо → dv",
        "menu_8": "Скорость убегания",
        "menu_9": "Анимация Хомана",
        "menu_10": "Анимация фазирования",
        "menu_11": "Сменить язык (ru/en)",
        "menu_0": "Выход",
        "menu_choice": "Выбор: ",
        "menu_no_plot": "(matplotlib не установлен — графики недоступны)",
        "hdr_orbit_params": "ПАРАМЕТРЫ ОРБИТЫ",
        "hdr_velocity": "СКОРОСТЬ В ТОЧКЕ",
        "hdr_circular": "КРУГОВАЯ ОРБИТА",
        "hdr_hohmann": "ПЕРЕЛЁТ ХОМАНА",
        "hdr_bielliptic": "БИЭЛЛИПТИЧЕСКИЙ ПЕРЕЛЁТ",
        "hdr_escape": "СКОРОСТЬ УБЕГАНИЯ",
        "hdr_anim_hohmann": "АНИМАЦИЯ ХОМАНА",
        "hdr_anim_phasing": "АНИМАЦИЯ ФАЗИРОВАНИЯ",
        "prompt_ap": "  Апогей (Ap), км: ",
        "prompt_pe": "  Перигей (Pe), км: ",
        "prompt_alt": "  Высота, км: ",
        "prompt_h1": "  Высота орбиты 1, км: ",
        "prompt_h2": "  Высота орбиты 2, км: ",
        "prompt_mass": "  Масса, кг: ",
        "prompt_isp": "  Isp, с: ",
        "prompt_fuel": "  Топливо, кг: ",
        "prompt_h": "  Высота, км: ",
        "prompt_phase": "  Фазовый угол, °: ",
        "prompt_nrev": "  Число витков: ",
        "prompt_plot": "Построить график? (y/n): ",
        "msg_neg_alt": "Высота не может быть отрицательной",
        "msg_same_orbits": "Орбиты совпадают",
        "msg_invalid_nrev": "Некорректное число витков",
        "msg_enter_0_11": "Введите 0..12",
        "msg_lang_changed": "Язык изменён",
        "log_calc_started": "Расчёт запущен",
        "log_neg_altitude": "Отрицательная высота",
        "log_invalid_params": "Некорректные параметры",
        "log_radius_below_earth": "Радиус ниже поверхности Земли",
        "log_point_outside_orbit": "Точка вне орбиты",
        "log_intermediate_too_low": "Промежуточная высота слишком мала",
        "log_mass_positive": "Масса должна быть > 0",
        "log_isp_positive": "Isp должен быть > 0",
        "log_fuel_negative": "Топливо не может быть отрицательным",
        "log_fuel_ge_mass": "Топливо ≥ массы",
        "log_fuel_exceeds_mass": "Топливо превышает массу",
        "log_phasing_impossible": "Фазирование невозможно",
    },
    "en": {},
}
# Заполняем английский как копию ключей (fallback на ключ)
for _k in _TRANSLATIONS["ru"]:
    if _k not in _TRANSLATIONS["en"]:
        _TRANSLATIONS["en"][_k] = _k


def _t(key: str) -> str:
    """Локализованная строка. Неизвестный ключ — возвращается как есть."""
    return _TRANSLATIONS.get(LANG, {}).get(key, key)


def set_lang(lang: str) -> None:
    """Переключение языка: 'ru' или 'en'."""
    global LANG
    if lang in ("ru", "en"):
        LANG = lang
    else:
        logger.warning(f"Неизвестный язык: {lang!r}, оставлен {LANG}")


def setup_logging(verbose: bool = False) -> None:
    """Настройка logging."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(levelname)-8s %(name)s: %(message)s",
        stream=sys.stderr,
    )


# ── Ввод ──────────────────────────────────────────────────────────────────
def rf(prompt: str = "") -> float:
    """Чтение float с повторами при ошибке."""
    while True:
        raw = input(prompt).strip().replace(",", ".")
        if not raw:
            continue
        try:
            return float(raw)
        except ValueError:
            print(f"  Не число: {raw!r}, повторите", file=sys.stderr)


def ri(prompt: str = "") -> int:
    """Чтение int с повторами."""
    while True:
        raw = input(prompt).strip()
        if not raw:
            continue
        try:
            return int(raw)
        except ValueError:
            print(f"  Не целое: {raw!r}, повторите", file=sys.stderr)


# ── Орбитальные хелперы ──────────────────────────────────────────────────
def check_orbit(ap: float, pe: float) -> tuple[bool, str]:
    """Проверка Ap/Pe. Возвращает (ok, message)."""
    if not isinstance(ap, (int, float)) or not isinstance(pe, (int, float)):
        return False, "Ap/Pe должны быть числами"
    if ap < 0 or pe < 0:
        return False, "Высоты должны быть ≥ 0"
    if ap < pe:
        return False, f"Ap ({ap:.1f}) < Pe ({pe:.1f}) — орбита невозможна"
    return True, ""


def sma(ap: float, pe: float) -> float:
    """Большая полуось по Ap/Pe."""
    return (ap + pe) / 2 + R_EARTH


def ecc(ap: float, pe: float) -> float:
    """Эксцентриситет по Ap/Pe."""
    r_p = pe + R_EARTH
    r_a = ap + R_EARTH
    return (r_a - r_p) / (r_a + r_p)


def period(ap: float, pe: float) -> float:
    """Период по Ap/Pe, секунды."""
    a = sma(ap, pe)
    return 2 * math.pi * math.sqrt(a ** 3 / MU_EARTH)


def vel_at(ap: float, pe: float, which: str = "perigee") -> float:
    """Скорость в перигее или апогее, км/с."""
    a = sma(ap, pe)
    if which == "perigee":
        r = pe + R_EARTH
    elif which == "apogee":
        r = ap + R_EARTH
    else:
        raise ValueError(f"which ∈ {{perigee, apogee}}, не {which!r}")
    return math.sqrt(MU_EARTH * (2 / r - 1 / a))
''',

    "core/optimization.py": '''"""core/optimization.py — фазирование и оптимизация манёвров."""

from __future__ import annotations

from core import astrodynamics as aero


def phasing_orbit(H: float, phase_deg: float, n_rev: int) -> dict | None:
    """Фазирующий манёвр: H, Δφ, N → dv, время.

    Возвращает dict с dv_total_mps и time_to_rendezvous_s, или None.
    """
    try:
        r = aero.solve_case("26", H=H, dphi=phase_deg, N=n_rev)
    except Exception:
        return None
    if "error" in r:
        return None
    return {
        "dv_total_mps": r["dv_total_mps"],
        "time_to_rendezvous_s": n_rev * r["T_phase_s"],
        "a_phase_km": r["a_phase_km"],
        "T_phase_s": r["T_phase_s"],
    }
''',

    "gui/__init__.py": '''"""gui — опциональная визуализация orbit-calc."""

try:
    import matplotlib  # noqa: F401
    HAS_PLOT = True
except ImportError:
    HAS_PLOT = False
''',

    "gui/animations.py": '''"""gui/animations.py — анимации манёвров.

Заглушки: возвращают None (анимация не создаётся).
Полная реализация требует matplotlib.animation + ffmpeg.
"""

from __future__ import annotations


def animate_hohmann(h1: float, h2: float, dv1: float, dv2: float) -> str | None:
    """Анимация Хомана. Заглушка."""
    return None


def animate_phasing(H: float, phase_deg: float, n_rev: int) -> str | None:
    """Анимация фазирования. Заглушка."""
    return None
''',

    "gui/plots.py": '''"""gui/plots.py — статические графики орбит.

Если matplotlib доступен — строит графики.
Если нет — no-op (функции просто ничего не делают).
"""

from __future__ import annotations

try:
    import matplotlib
    matplotlib.use("Agg")  # backend без GUI
    import matplotlib.pyplot as plt
    import numpy as np
    HAS_MPL = True
except ImportError:
    HAS_MPL = False


def _ask_plot() -> bool:
    """Спрашивает пользователя, строить ли график."""
    if not HAS_MPL:
        return False
    try:
        ans = input("  Построить график? (y/n): ").strip().lower()
        return ans == "y"
    except EOFError:
        return False


def _orbit_xy(a: float, e: float, n: int = 360):
    """Возвращает x, y точек орбиты (эллипс с фокусом в 0)."""
    if not HAS_MPL:
        return None, None
    theta = np.linspace(0, 2 * np.pi, n)
    p = a * (1 - e * e)
    r = p / (1 + e * np.cos(theta))
    x = r * np.cos(theta)
    y = r * np.sin(theta)
    return x, y


def _save(fig, name: str) -> str:
    """Сохраняет фигуру в build/dist/plots/."""
    from pathlib import Path
    out = Path("build/dist/plots")
    out.mkdir(parents=True, exist_ok=True)
    path = out / name
    fig.savefig(path, dpi=100, bbox_inches="tight")
    plt.close(fig)
    return str(path)


def plot_orbit_params(ap: float, pe: float) -> None:
    if not HAS_MPL:
        return
    from core.base import R_EARTH
    r_p = pe + R_EARTH
    r_a = ap + R_EARTH
    a = (r_p + r_a) / 2
    e = (r_a - r_p) / (r_a + r_p)
    x, y = _orbit_xy(a, e)
    if x is None:
        return
    fig, ax = plt.subplots(figsize=(6, 6))
    ax.plot(x, y, "b-", lw=1.5)
    ax.plot([0], [0], "ko", ms=8)
    ax.set_aspect("equal")
    ax.grid(True, alpha=0.3)
    ax.set_title(f"a={a:.0f} км, e={e:.4f}")
    print(f"  График: {_save(fig, 'orbit.png')}")


def plot_hohmann(h1: float, h2: float, dv1: float, dv2: float) -> None:
    if not HAS_MPL:
        return
    from core.base import R_EARTH
    r1, r2 = h1 + R_EARTH, h2 + R_EARTH
    x1, y1 = _orbit_xy(r1, 0.0)
    x2, y2 = _orbit_xy(r2, 0.0)
    a_t = (r1 + r2) / 2
    e_t = (max(r1, r2) - min(r1, r2)) / (r1 + r2)
    xt, yt = _orbit_xy(a_t, e_t)
    if x1 is None:
        return
    fig, ax = plt.subplots(figsize=(8, 8))
    ax.plot(x1, y1, "b-", label=f"H1={h1:.0f}")
    ax.plot(x2, y2, "g-", label=f"H2={h2:.0f}")
    ax.plot(xt, yt, "r--", label="transfer", alpha=0.6)
    ax.plot([0], [0], "ko", ms=6)
    ax.set_aspect("equal")
    ax.legend()
    ax.grid(True, alpha=0.3)
    ax.set_title(f"Хоман: Δv1={dv1:+.0f}, Δv2={dv2:+.0f} м/с")
    print(f"  График: {_save(fig, 'hohmann.png')}")


def plot_bielliptic(h1: float, h2: float, h_bi: float,
                    b1: float, b2: float, b3: float) -> None:
    if not HAS_MPL:
        return
    from core.base import R_EARTH
    r1, r2, rb = h1 + R_EARTH, h2 + R_EARTH, h_bi + R_EARTH
    x1, y1 = _orbit_xy(r1, 0.0)
    x2, y2 = _orbit_xy(r2, 0.0)
    a1 = (r1 + rb) / 2
    e1 = (rb - r1) / (rb + r1)
    xt1, yt1 = _orbit_xy(a1, e1)
    if x1 is None:
        return
    fig, ax = plt.subplots(figsize=(8, 8))
    ax.plot(x1, y1, "b-", label=f"H1={h1:.0f}")
    ax.plot(x2, y2, "g-", label=f"H2={h2:.0f}")
    ax.plot(xt1, yt1, "r--", alpha=0.6, label="transfer")
    ax.plot([0], [0], "ko", ms=6)
    ax.set_aspect("equal")
    ax.legend()
    ax.grid(True, alpha=0.3)
    ax.set_title(f"Биэллиптика: ΣΔv={abs(b1)+abs(b2)+abs(b3):.0f} м/с")
    print(f"  График: {_save(fig, 'bielliptic.png')}")


def plot_circular(alt: float) -> None:
    if not HAS_MPL:
        return
    from core.base import R_EARTH
    x, y = _orbit_xy(alt + R_EARTH, 0.0)
    if x is None:
        return
    fig, ax = plt.subplots(figsize=(6, 6))
    ax.plot(x, y, "b-")
    ax.plot([0], [0], "ko", ms=6)
    ax.set_aspect("equal")
    ax.grid(True, alpha=0.3)
    ax.set_title(f"Круговая H={alt:.0f} км")
    print(f"  График: {_save(fig, 'circular.png')}")


def plot_escape(alt: float) -> None:
    if not HAS_MPL:
        return
    from core.base import R_EARTH
    r = alt + R_EARTH
    x, y = _orbit_xy(r, 0.0)
    if x is None:
        return
    fig, ax = plt.subplots(figsize=(6, 6))
    ax.plot(x, y, "b-", label="круговая")
    # Парабола (приближение — большой эллипс)
    xp, yp = _orbit_xy(r * 5, 0.8)
    if xp is not None:
        ax.plot(xp, yp, "r--", alpha=0.5, label="парабола")
    ax.plot([0], [0], "ko", ms=6)
    ax.set_aspect("equal")
    ax.legend()
    ax.grid(True, alpha=0.3)
    ax.set_title(f"v_esc при H={alt:.0f} км")
    print(f"  График: {_save(fig, 'escape.png')}")


def plot_velocity_point(ap: float, pe: float, r: float,
                        v: float, name: str) -> None:
    if not HAS_MPL:
        return
    from core.base import R_EARTH
    r_p, r_a = pe + R_EARTH, ap + R_EARTH
    a = (r_p + r_a) / 2
    e = (r_a - r_p) / (r_a + r_p)
    x, y = _orbit_xy(a, e)
    if x is None:
        return
    fig, ax = plt.subplots(figsize=(6, 6))
    ax.plot(x, y, "b-", lw=1)
    ax.plot([0], [0], "ko", ms=6)
    # Точка на орбите (по радиусу)
    th = 0.0 if abs(r - r_p) < 1e-3 else (np.pi if abs(r - r_a) < 1e-3 else 0.0)
    ax.plot([r * np.cos(th)], [r * np.sin(th)], "r*", ms=15)
    ax.set_aspect("equal")
    ax.grid(True, alpha=0.3)
    ax.set_title(f"{name}: v={v:.3f} км/с")
    print(f"  График: {_save(fig, 'velocity_point.png')}")
''',

    "build/orbit-calc.spec": '''# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec для orbit-calc."""

import os
from pathlib import Path

ROOT = Path(SPECPATH).parent.parent.resolve()
LITE = os.environ.get("ORBIT_LITE", "").lower() in ("1", "true", "yes")

hiddenimports = [
    "core", "core.base", "core.optimization", "core.astrodynamics",
    "core.lambert", "core.latex_formulas",
    "gui", "gui.animations", "gui.plots",
]

excludes = [
    "tkinter", "PyQt5", "PyQt6", "PySide2", "PySide6",
    "test", "tests", "unittest", "pytest",
    "IPython", "jupyter", "notebook",
    "numpy.f2py", "numpy.distutils",
    "scipy.tests", "scipy.benchmarks",
]
if LITE:
    excludes.append("matplotlib")

datas = []
for pkg in ("core", "gui"):
    d = ROOT / pkg
    if d.is_dir():
        datas.append((str(d), pkg))

a = Analysis(
    [str(ROOT / "cli" / "calculator.py")],
    pathex=[str(ROOT)],
    binaries=[], datas=datas,
    hiddenimports=hiddenimports, hookspath=[], hooksconfig={},
    runtime_hooks=[], excludes=excludes, noarchive=False, optimize=0,
)
pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz, a.scripts, a.binaries, a.zipfiles, a.datas, [],
    name="orbit-calc", debug=False, bootloader_ignore_signals=False,
    strip=False, upx=False, upx_exclude=[], runtime_tmpdir=None,
    console=True, disable_windowed_traceback=False, argv_emulation=False,
    target_arch=None, codesign_identity=None, entitlements_file=None, icon=None,
)
''',

    "build/build_all.sh": '''#!/usr/bin/env bash
# build_all.sh — PyInstaller-сборка для текущей ОС.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD="$ROOT/build"
DIST="$BUILD/dist"
cd "$ROOT"

echo "=== orbit-calc build ==="
echo "OS:   $(uname -s)"
echo "Root: $ROOT"

PYTHON="${PYTHON:-python3}"

if ! "$PYTHON" -c "import PyInstaller" 2>/dev/null; then
    echo "Установка PyInstaller..."
    "$PYTHON" -m pip install --upgrade pip pyinstaller
fi

if [ "${ORBIT_LITE:-0}" = "1" ]; then
    echo "Режим: LITE (без matplotlib)"
else
    if ! "$PYTHON" -c "import matplotlib" 2>/dev/null; then
        echo "WARN: matplotlib отсутствует → LITE"
        export ORBIT_LITE=1
    else
        echo "Режим: FULL (с matplotlib)"
    fi
fi

echo
echo "=== Smoke test ==="
"$PYTHON" -c "
import sys
sys.path.insert(0, '$ROOT')
from core.astrodynamics import solve_case
r = solve_case('1', a=7000, e=0.1)
assert 'error' not in r, r
print('OK: solve_case')
"

rm -rf "$DIST" "$BUILD/work"
echo
echo "=== PyInstaller ==="
"$PYTHON" -m PyInstaller \\
    --clean --noconfirm \\
    --distpath "$DIST" --workpath "$BUILD/work" \\
    "$BUILD/orbit-calc.spec"

BIN="$DIST/orbit-calc"
[ -f "${BIN}.exe" ] && BIN="${BIN}.exe"

if [ ! -x "$BIN" ]; then
    echo "ERROR: бинарник не создан" >&2
    ls -la "$DIST" >&2
    exit 2
fi
echo
echo "OK: $BIN ($(du -h "$BIN" | cut -f1))"
''',
}


def main() -> int:
    print("[patch v5] Самодостаточный проект")
    print("=" * 50)
    created = 0
    skipped = 0
    for rel, content in FILES.items():
        path = ROOT / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            print(f"  [skip] {rel} — уже есть")
            skipped += 1
            continue
        path.write_text(content, encoding="utf-8")
        print(f"  [ok]   {rel}")
        created += 1

    # chmod +x на build_all.sh
    sh = ROOT / "build" / "build_all.sh"
    if sh.exists():
        st = sh.stat().st_mode
        sh.chmod(st | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    # Синтаксис
    print("\n[verify] синтаксис")
    for rel in FILES:
        if rel.endswith(".py"):
            p = ROOT / rel
            try:
                compile(p.read_text(encoding="utf-8"), str(p), "exec")
                print(f"  [ok]   {rel}")
            except SyntaxError as exc:
                print(f"  [err] {rel}: {exc}")
                return 2

    print("\n[verify] импорт core.base")
    import subprocess
    r = subprocess.run(
        [sys.executable, "-c",
         "import sys; sys.path.insert(0, '.'); "
         "from core.base import R_EARTH, MU_EARTH, rf, ri, sma, ecc; "
         "from core.optimization import phasing_orbit; "
         "from gui.plots import _ask_plot; "
         "print(f'OK: R_EARTH={R_EARTH}, MU_EARTH={MU_EARTH}')"],
        cwd=str(ROOT), capture_output=True, text=True,
    )
    if r.returncode == 0:
        print(f"  [ok]   {r.stdout.strip()}")
    else:
        print(f"  [err]  {r.stderr.strip()}", file=sys.stderr)
        return 3

    print("\n" + "=" * 50)
    print(f"[patch v5] Готово: {created} создано, {skipped} пропущено")
    print("\nПроверьте:")
    print("  python3 build/gui_builder.py             # откройте GUI заново")
    print("  python3 -c \"from core.base import R_EARTH; print(R_EARTH)\"")
    print("  pytest tests/ -v                         # 97 passed")
    print("  ./build/build_all.sh                     # Linux native")
    if not shutil.which("docker"):
        print("\nDocker не установлен — Windows-сборка будет недоступна.")
        print("Linux-сборка работает без Docker.")
    return 0


if __name__ == "__main__":
    sys.exit(main())