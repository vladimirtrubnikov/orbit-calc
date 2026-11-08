"""gui — GUI и визуализация orbit-calc."""

try:
    import matplotlib  # noqa: F401
    HAS_PLOT = True
except ImportError:
    HAS_PLOT = False

__all__ = ["HAS_PLOT"]
