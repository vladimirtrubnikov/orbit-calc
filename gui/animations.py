"""gui/animations.py — анимации манёвров.

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
