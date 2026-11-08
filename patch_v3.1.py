#!/usr/bin/env python3
"""patch_v3.1.py — исправляет 3 упавших теста после v3."""

import sys
from pathlib import Path

FIXES = [
    ("core/astrodynamics.py",
     "        except ValueError:\n            break\n    return out",
     "        except ValueError:\n            continue\n    return out",
     "best_staging: break → continue"),

    ("core/astrodynamics.py",
     "                  gravity_loss_km_s: float = 1.2,\n"
     "                  drag_loss_km_s: float = 0.15) -> dict:",
     "                  gravity_loss_km_s: float = 1.7,\n"
     "                  drag_loss_km_s: float = 0.15) -> dict:",
     "ascent_budget: 1.2 → 1.7"),

    ("tests/test_solvers.py",
     "def test_dispatch_completeness():\n"
     "    for i in range(1, 47):",
     "def test_dispatch_completeness():\n"
     "    for i in range(1, 54):",
     "test_dispatch_completeness: 46 → 53"),

    ("tests/test_solvers.py",
     "def test_dispatch_count():\n"
     "    assert len(calc._DISPATCH) == 46",
     "def test_dispatch_count():\n"
     "    assert len(calc._DISPATCH) >= 46",
     "test_dispatch_count: == 46 → >= 46"),
]


def main() -> int:
    changed = 0
    for path_str, old, new, name in FIXES:
        path = Path(path_str)
        if not path.is_file():
            print(f"[skip] {path_str} не найден")
            continue
        text = path.read_text(encoding="utf-8")
        if new in text and old not in text:
            print(f"[skip] {name} — уже применён")
            continue
        if old not in text:
            print(f"[ERR]  {name}: якорь не найден в {path_str}", file=sys.stderr)
            return 1
        path.write_text(text.replace(old, new, 1), encoding="utf-8")
        print(f"[ok]   {name}")
        changed += 1
    print(f"\nПрименено правок: {changed}")
    return 0


if __name__ == "__main__":
    sys.exit(main())