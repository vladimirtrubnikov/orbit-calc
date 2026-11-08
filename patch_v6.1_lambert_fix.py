#!/usr/bin/env python3
"""patch_v6.1_lambert_fix.py — заменяет v6-секцию core/lambert.py.

Причина: _bisect_with_none возвращает None при g(z_a)=None,
что ломает 0-rev для Δν ≠ π.

Фикс: скан от z_a в сторону z_b для поиска валидной нижней границы.

Идемпотентен. Резервная копия: core/lambert.py.v6.1.bak
"""
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parent
LAMBERT = ROOT / "core" / "lambert.py"
MARKER = "#  v6: мультивитковый Ламберт (N rev)"


NEW_BLOCK = '''

# ═══════════════════════════════════════════════════════════════════════════
#  v6.1: мультивитковый Ламберт (N rev) — исправленная _bisect_with_none
# ═══════════════════════════════════════════════════════════════════════════


def _stumpff_C(z: float) -> float:
    if z > 1e-8:
        return (1 - math.cos(math.sqrt(z))) / z
    if z < -1e-8:
        return (math.cosh(math.sqrt(-z)) - 1) / (-z)
    return 0.5


def _stumpff_S(z: float) -> float:
    if z > 1e-8:
        sz = math.sqrt(z)
        return (sz - math.sin(sz)) / (sz ** 3)
    if z < -1e-8:
        sz = math.sqrt(-z)
        return (math.sinh(sz) - sz) / (sz ** 3)
    return 1.0 / 6.0


def _y_from_z(z: float, r1: float, r2: float, A: float):
    C = _stumpff_C(z)
    if C < 1e-15:
        return None
    S = _stumpff_S(z)
    y = r1 + r2 + A * (z * S - 1) / math.sqrt(C)
    return y if y >= 0 else None


def _tof_norm(z: float, r1: float, r2: float, A: float):
    y = _y_from_z(z, r1, r2, A)
    if y is None:
        return None
    C = _stumpff_C(z)
    S = _stumpff_S(z)
    x = math.sqrt(y / C)
    return x ** 3 * S + A * math.sqrt(y)


def _bisect_with_none(g, z_a, z_b, target, tol=1e-10, max_iter=100):
    """Бисекция между z_a (g<target) и z_b (g>target или None).

    Если g(z_a)=None или g(z_a)>=target — сканирует в сторону z_b,
    чтобы найти валидную нижнюю границу (y<0 на границах полос — норма).
    """
    # 1. Валидный z_a: g(z_a) < target
    g_a = g(z_a)
    if g_a is None or g_a >= target:
        found = False
        for i in range(1, 201):
            z_try = z_a + (z_b - z_a) * i / 200
            gv = g(z_try)
            if gv is not None and gv < target:
                z_a = z_try
                g_a = gv
                found = True
                break
        if not found:
            return None

    # 2. Валидный z_b: g(z_b) > target или None
    g_b = g(z_b)
    if g_b is not None and g_b <= target:
        found = False
        for i in range(1, 201):
            z_try = z_b - (z_b - z_a) * i / 200
            gv = g(z_try)
            if gv is None or gv > target:
                z_b = z_try
                g_b = gv
                found = True
                break
        if not found:
            return None

    # 3. Бисекция
    for _ in range(max_iter):
        mid = (z_a + z_b) / 2
        g_mid = g(mid)
        if g_mid is None:
            z_b = mid
            continue
        if abs(g_mid - target) < tol or abs(z_b - z_a) < tol:
            return mid
        if g_mid < target:
            z_a = mid
        else:
            z_b = mid
    return (z_a + z_b) / 2


def _find_min_tof(z_lo, z_hi, r1, r2, A, n_samples=40):
    """Ищет z_min в (z_lo, z_hi), где TOF минимален. None если на границе."""
    samples = []
    for i in range(n_samples + 1):
        z = z_lo + (z_hi - z_lo) * i / n_samples
        tof = _tof_norm(z, r1, r2, A)
        if tof is not None:
            samples.append((z, tof))
    if len(samples) < 3:
        return None
    min_i = min(range(len(samples)), key=lambda i: samples[i][1])
    if min_i == 0 or min_i == len(samples) - 1:
        return None
    lo, hi = samples[min_i - 1][0], samples[min_i + 1][0]
    for _ in range(60):
        m1 = lo + (hi - lo) / 3
        m2 = hi - (hi - lo) / 3
        t1 = _tof_norm(m1, r1, r2, A)
        t2 = _tof_norm(m2, r1, r2, A)
        if t1 is None or t2 is None:
            break
        if t1 < t2:
            hi = m2
        else:
            lo = m1
    return (lo + hi) / 2


def _make_solution(z, r1, r2, r1_vec, r2_vec, A, revs, branch):
    y = _y_from_z(z, r1, r2, A)
    if y is None:
        return None
    f = 1 - y / r1
    g = A * math.sqrt(y / MU_EARTH)
    gdot = 1 - y / r2
    if abs(g) < 1e-15:
        return None
    v1_vec = ((r2_vec[0] - f * r1_vec[0]) / g,
              (r2_vec[1] - f * r1_vec[1]) / g)
    v2_vec = ((gdot * r2_vec[0] - r1_vec[0]) / g,
              (gdot * r2_vec[1] - r1_vec[1]) / g)
    return {"z": z, "revs": revs, "branch": branch,
            "v1_vec": v1_vec, "v2_vec": v2_vec}


def lambert_universal_nrev(r1, r2, dnu, dt, n_max=5):
    """Мультивитковый Ламберт: все решения N=0..N_max.

    Возвращает список dict: {z, revs, branch, v1_vec, v2_vec}.
    branch: "single" (N=0), "left"/"right" (N>=1).
    """
    if not (0 < dnu < 2 * math.pi) or dt <= 0 or r1 <= 0 or r2 <= 0:
        return []
    if n_max < 0:
        return []
    n_max = min(n_max, 10)

    r1_vec = (r1, 0.0)
    r2_vec = (r2 * math.cos(dnu), r2 * math.sin(dnu))
    cos_dnu = math.cos(dnu)
    A = (0.0 if abs(1 - cos_dnu) < 1e-15
         else math.sin(dnu) * math.sqrt(r1 * r2 / (1 - cos_dnu)))
    target = math.sqrt(MU_EARTH) * dt
    sols = []

    g = lambda z: _tof_norm(z, r1, r2, A)

    # N=0
    z_lo0 = -4 * math.pi ** 2
    z_hi0 = 4 * math.pi ** 2 * 0.99
    z0 = _bisect_with_none(g, z_lo0, z_hi0, target)
    if z0 is not None:
        s = _make_solution(z0, r1, r2, r1_vec, r2_vec, A, 0, "single")
        if s:
            sols.append(s)

    # N>=1
    eps = 1e-3
    for N in range(1, n_max + 1):
        z_lo = (2 * math.pi * N) ** 2 + eps
        z_hi = (2 * math.pi * (N + 1)) ** 2 - eps
        if z_lo >= z_hi:
            continue
        z_min = _find_min_tof(z_lo, z_hi, r1, r2, A)
        if z_min is None:
            continue
        tof_min = g(z_min)
        if tof_min is None or tof_min > target:
            continue

        z_left = _bisect_with_none(g, z_min, z_lo, target)
        if z_left is not None:
            s = _make_solution(z_left, r1, r2, r1_vec, r2_vec, A, N, "left")
            if s:
                sols.append(s)

        z_right = _bisect_with_none(g, z_min, z_hi, target)
        if z_right is not None:
            s = _make_solution(z_right, r1, r2, r1_vec, r2_vec, A, N, "right")
            if s:
                sols.append(s)

    return sols
'''


def _verify() -> bool:
    """In-process проверка: solve_case('54') возвращает решения."""
    print("\n[verify] solve_case('54')")
    import math as _m

    # Сбросить core.* в sys.modules, чтобы подхватить новый core/lambert.py
    for mod_name in list(sys.modules.keys()):
        if mod_name == "core" or mod_name.startswith("core."):
            del sys.modules[mod_name]
    sys.path.insert(0, str(ROOT))

    try:
        from core.astrodynamics import solve_case, _SOLVERS
        n = len(_SOLVERS)
        if n != 54:
            print(f"  [err] _SOLVERS = {n}, ожидалось 54", file=sys.stderr)
            return False
        print(f"  ✓ _SOLVERS: {n}")

        r = solve_case("54", H1=622, H2=622, dnu_deg=90, dt=1457, n_max=2)
        if "error" in r:
            print(f"  [err] {r['error']}", file=sys.stderr)
            return False

        print(f"  ✓ solve_case(54): {r['n_found']} решений")
        for s in r["solutions"]:
            v1 = _m.hypot(*s["v1_vec"])
            v2 = _m.hypot(*s["v2_vec"])
            print(f"    N={s['revs']} {s['branch']}: |v1|={v1:.4f}, |v2|={v2:.4f} км/с")
        return True
    except Exception as exc:
        import traceback
        print(f"  [err] {type(exc).__name__}: {exc}", file=sys.stderr)
        traceback.print_exc()
        return False


def main():
    print("[patch v6.1] Фикс _bisect_with_none")
    print("=" * 50)

    if not LAMBERT.is_file():
        print(f"[err] {LAMBERT} не найден", file=sys.stderr)
        return 1

    text = LAMBERT.read_text(encoding="utf-8")

    if "v6.1: мультивитковый" in text:
        print("[skip] v6.1 уже применён")
        return 0 if _verify() else 4

    idx = text.find(MARKER)
    if idx < 0:
        print(f"[err] маркер '{MARKER}' не найден", file=sys.stderr)
        return 2

    bak = LAMBERT.with_suffix(".py.v6.1.bak")
    if not bak.exists():
        shutil.copy2(LAMBERT, bak)
        print(f"[backup] {bak}")

    base = text[:idx].rstrip() + "\n"
    LAMBERT.write_text(base + NEW_BLOCK, encoding="utf-8")
    print("[ok] v6-секция заменена на v6.1")

    try:
        compile(LAMBERT.read_text(encoding="utf-8"), str(LAMBERT), "exec")
        print("[ok] синтаксис корректен")
    except SyntaxError as exc:
        print(f"[err] SyntaxError: {exc}", file=sys.stderr)
        return 3

    ok = _verify()
    print("\n" + "=" * 50)
    print("[patch v6.1] Готово" if ok else "[patch v6.1] Ошибка verify")
    return 0 if ok else 4


if __name__ == "__main__":
    sys.exit(main())