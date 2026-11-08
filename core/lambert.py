"""core/lambert.py — задача Ламберта (0 rev), чистая функция.

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

    # v4.4: z_hi = 4π² даёт C = 0 (деление на ноль). Сдвигаем вниз.
    z_lo, z_hi = -4 * math.pi ** 2, 4 * math.pi ** 2 * 0.99
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


# ═══════════════════════════════════════════════════════════════════════════


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
