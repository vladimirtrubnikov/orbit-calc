#!/usr/bin/env python3
"""patch_v4.1.py — фикс KeyError: '_s27' в core/astrodynamics.py.

Причина: patch_v4 определил _s1.._s53, но пропустил _s27 (Ламберт).
Реестр _SOLVERS = {str(i): globals()[f"_s{i}"] for i in range(1, 54)}
требует все имена — отсюда KeyError при импорте.

Правки:
  1. Создать core/lambert.py (lambert_universal)
  2. Добавить импорт lambert_universal в core/astrodynamics.py
  3. Вставить _s27 перед _SOLVERS

Идемпотентен. Резервные копии: core/astrodynamics.py.v4.1.bak
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

ASTRO = Path("core/astrodynamics.py")
LAMBERT = Path("core/lambert.py")

LAMBERT_TEXT = '''"""core/lambert.py — задача Ламберта (0 rev), чистая функция.

Самодостаточен: MU_EARTH определён локально, чтобы не создавать
циклический импорт с core/astrodynamics.py.
"""

from __future__ import annotations

import math

MU_EARTH = 398_600.4418


def lambert_universal(r1: float, r2: float, dnu: float, dt: float):
    """Универсальные переменные, 0 rev, короткий путь (prograde).

    Возвращает (v1_vec, v2_vec) в 2D-плоскости или None при неудаче.
    """
    if not (0 < dnu < 2 * math.pi) or dt <= 0:
        return None
    if r1 <= 0 or r2 <= 0:
        return None

    r1_vec = (r1, 0.0)
    r2_vec = (r2 * math.cos(dnu), r2 * math.sin(dnu))

    cos_dnu = math.cos(dnu)
    if abs(1 - cos_dnu) < 1e-15:
        A = 0.0
    else:
        A = math.sin(dnu) * math.sqrt(r1 * r2 / (1 - cos_dnu))

    def _CS(z):
        if z > 1e-8:
            sz = math.sqrt(z)
            return (1 - math.cos(sz)) / z, (sz - math.sin(sz)) / (sz ** 3)
        if z < -1e-8:
            sz = math.sqrt(-z)
            return (math.cosh(sz) - 1) / (-z), (math.sinh(sz) - sz) / (sz ** 3)
        return 0.5, 1.0 / 6.0

    def F(z):
        C, S = _CS(z)
        if C < 1e-15:
            return None
        y = r1 + r2 + A * (z * S - 1) / math.sqrt(C)
        if y < 0:
            return None
        return math.sqrt(MU_EARTH) * dt - (y / C) ** 1.5 * S - A * math.sqrt(y)

    z_lo, z_hi = -4 * math.pi ** 2, 4 * math.pi ** 2
    f_lo, f_hi = F(z_lo), F(z_hi)
    if f_lo is None or f_hi is None or f_lo * f_hi > 0:
        return None

    z = 0.0
    for _ in range(200):
        z_mid = (z_lo + z_hi) / 2
        f_mid = F(z_mid)
        if f_mid is None:
            z_hi = z_mid
            continue
        if abs(f_mid) < 1e-8 or (z_hi - z_lo) < 1e-12:
            z = z_mid
            break
        if f_lo * f_mid < 0:
            z_hi = z_mid
        else:
            z_lo = z_mid
            f_lo = f_mid
    else:
        z = (z_lo + z_hi) / 2

    C, S = _CS(z)
    y = r1 + r2 + A * (z * S - 1) / math.sqrt(C)
    if y < 0:
        return None

    f = 1 - y / r1
    g = A * math.sqrt(y / MU_EARTH)
    g_dot = 1 - y / r2
    if abs(g) < 1e-15:
        return None

    v1_vec = ((r2_vec[0] - f * r1_vec[0]) / g, (r2_vec[1] - f * r1_vec[1]) / g)
    v2_vec = ((g_dot * r2_vec[0] - r1_vec[0]) / g, (g_dot * r2_vec[1] - r1_vec[1]) / g)
    return v1_vec, v2_vec
'''


# ── Правка 1: импорт lambert_universal в astrodynamics.py ─────────────────
PATCH_IMPORT = (
    "from __future__ import annotations\n\nimport math\n",
    "from __future__ import annotations\n\nimport math\n\n"
    "from core.lambert import lambert_universal  # noqa: E402\n",
)

# ── Правка 2: вставить _s27 перед _SOLVERS ────────────────────────────────
S27_BLOCK = '''def _s27(H1, H2, dnu_deg, dt):
    """Ламберт: r1, r2, Δν, Δt → Δv1, Δv2."""
    r1, r2 = H1 + R_EARTH, H2 + R_EARTH
    dnu = math.radians(dnu_deg)
    if not (0 < dnu < 2 * math.pi) or dt <= 0:
        raise ValueError("0 < Δν < 360°, Δt > 0")
    res = lambert_universal(r1, r2, dnu, dt)
    if res is None:
        raise ValueError("Ламберт не сошёлся — проверьте Δν, Δt")
    v1_vec, v2_vec = res
    v1 = math.hypot(*v1_vec)
    v2 = math.hypot(*v2_vec)
    vc1 = math.sqrt(MU_EARTH / r1)
    tang2 = (-math.sin(dnu), math.cos(dnu))
    vc2 = math.sqrt(MU_EARTH / r2)
    dv1 = math.hypot(v1_vec[0], v1_vec[1] - vc1)
    dv2 = math.hypot(vc2 * tang2[0] - v2_vec[0], vc2 * tang2[1] - v2_vec[1])
    return {"dv1_mps": dv1 * 1000, "dv2_mps": dv2 * 1000,
            "dv_total_mps": (dv1 + dv2) * 1000,
            "v1_transfer_km_s": v1, "v2_transfer_km_s": v2}


_SOLVERS = {str(i): globals()[f"_s{i}"] for i in range(1, 54)}'''

PATCH_S27 = (
    '_SOLVERS = {str(i): globals()[f"_s{i}"] for i in range(1, 54)}',
    S27_BLOCK,
)


def _apply(text, old, new, name):
    if new in text and old not in text:
        print(f"  [skip] {name}")
        return text
    if old not in text:
        raise RuntimeError(f"Якорь не найден для {name}: {old[:80]!r}")
    print(f"  [ok]   {name}")
    return text.replace(old, new, 1)


def create_lambert():
    print(f"\n[1] {LAMBERT}")
    if LAMBERT.is_file():
        print("  [skip] уже существует")
        return 0
    LAMBERT.parent.mkdir(parents=True, exist_ok=True)
    LAMBERT.write_text(LAMBERT_TEXT, encoding="utf-8")
    print("  [ok]   создан")
    return 0


def fix_astrodynamics():
    print(f"\n[2] {ASTRO}")
    if not ASTRO.is_file():
        print(f"  [err] не найден", file=sys.stderr)
        return 1

    text = ASTRO.read_text(encoding="utf-8")

    if "_s27(H1, H2, dnu_deg, dt)" in text and "from core.lambert import" in text:
        print("  [skip] _s27 и импорт уже есть")
        return 0

    backup = ASTRO.with_suffix(".py.v4.1.bak")
    if not backup.exists():
        shutil.copy2(ASTRO, backup)
        print(f"  [backup] {backup}")

    try:
        text = _apply(text, *PATCH_IMPORT, "импорт lambert_universal")
        text = _apply(text, *PATCH_S27, "_s27 перед _SOLVERS")
    except RuntimeError as exc:
        print(f"  [err] {exc}", file=sys.stderr)
        return 2

    ASTRO.write_text(text, encoding="utf-8")

    # Синтаксис
    try:
        compile(ASTRO.read_text(encoding="utf-8"), str(ASTRO), "exec")
        print("  [ok]   синтаксис корректен")
    except SyntaxError as exc:
        print(f"  [err] SyntaxError: {exc}", file=sys.stderr)
        return 3

    # Импорт-тест
    try:
        sys.path.insert(0, ".")
        if "core.astrodynamics" in sys.modules:
            del sys.modules["core.astrodynamics"]
        if "core.lambert" in sys.modules:
            del sys.modules["core.lambert"]
        import importlib
        mod = importlib.import_module("core.astrodynamics")
        assert hasattr(mod, "_s27"), "_s27 не найден в модуле"
        assert "27" in mod._SOLVERS, "_SOLVERS['27'] отсутствует"
        assert len(mod._SOLVERS) == 53, f"_SOLVERS: {len(mod._SOLVERS)} != 53"
        print("  [ok]   импорт успешен, _SOLVERS содержит 53 элемента")
    except Exception as exc:
        print(f"  [err] импорт-тест упал: {exc}", file=sys.stderr)
        return 4

    return 0


def main() -> int:
    print("[patch v4.1] Фикс KeyError: '_s27'")
    print("=" * 50)
    rc = 0
    rc |= create_lambert()
    rc |= fix_astrodynamics()
    print("\n" + "=" * 50)
    if rc == 0:
        print("[patch v4.1] Готово. Проверьте:")
        print("  pytest tests/ -v                                # 29 passed")
        print("  python3 -c \"from core.astrodynamics import solve_case; "
              "print(solve_case('27', H1=200, H2=35786, dnu_deg=180, dt=18929))\"")
        print("  python3 cli/calculator.py --solve=27 --json")
    else:
        print(f"[patch v4.1] Завершён с ошибкой (rc={rc})", file=sys.stderr)
    return rc


if __name__ == "__main__":
    sys.exit(main())