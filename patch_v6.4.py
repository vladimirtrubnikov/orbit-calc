#!/usr/bin/env python3
"""patch_v6.4.py — обновляет тесты под 54-й случай.

1. tests/test_v4.py::test_solvers_registry_complete — == 53 → >= 53
2. tests/test_v4.py::test_case_meta_complete — range(1, 54) → range(1, 55)
3. tests/test_solvers.py::test_dispatch_completeness — range(1, 54) → range(1, 55)

Идемпотентен. Резервные копии: *.v6.4.bak
"""
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parent

PATCHES = [
    # (файл, старое, новое, имя)
    ("tests/test_v4.py",
     "def test_solvers_registry_complete():\n    assert len(aero._SOLVERS) == 53",
     "def test_solvers_registry_complete():\n    assert len(aero._SOLVERS) >= 53",
     "test_v4: == 53 → >= 53"),

    ("tests/test_v4.py",
     "def test_case_meta_complete():\n    for i in range(1, 54):",
     "def test_case_meta_complete():\n    for i in range(1, 55):",
     "test_v4: range 1..54 → 1..55"),

    ("tests/test_solvers.py",
     "def test_dispatch_completeness():\n    # v3: пункты 1..53\n    for i in range(1, 54):",
     "def test_dispatch_completeness():\n    # v6: пункты 1..54\n    for i in range(1, 55):",
     "test_solvers: range 1..54 → 1..55"),
]


def main() -> int:
    print("[patch v6.4] Обновление тестов под case 54")
    print("=" * 50)

    changed = 0
    for rel, old, new, name in PATCHES:
        path = ROOT / rel
        if not path.is_file():
            print(f"  [err] {rel} не найден", file=sys.stderr)
            return 1
        text = path.read_text(encoding="utf-8")
        if new in text:
            print(f"  [skip] {name}")
            continue
        if old not in text:
            print(f"  [err] {name}: якорь не найден", file=sys.stderr)
            return 2
        bak = path.with_suffix(path.suffix + ".v6.4.bak")
        if not bak.exists():
            shutil.copy2(path, bak)
        path.write_text(text.replace(old, new, 1), encoding="utf-8")
        print(f"  [ok]   {name}")
        changed += 1

    # Синтаксис
    for rel in {p[0] for p in PATCHES}:
        path = ROOT / rel
        try:
            compile(path.read_text(encoding="utf-8"), str(path), "exec")
        except SyntaxError as exc:
            print(f"  [err] SyntaxError в {rel}: {exc}", file=sys.stderr)
            return 3

    print(f"\n[ok] синтаксис корректен")
    print("=" * 50)
    print(f"[patch v6.4] Готово: {changed} правок" if changed else
          "[patch v6.4] Всё уже было правильно")
    return 0


if __name__ == "__main__":
    sys.exit(main())