"""gui/plots.py — статические графики орбит.

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
