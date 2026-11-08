#!/usr/bin/env python3
"""patch_v6_dist_safe.py — build_all.sh и wine-entrypoint.sh больше не стирают друг друга.

Каждый скрипт удаляет только СВОЙ бинарник в build/dist/, а не всю директорию.
"""
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parent

BA_OLD = 'rm -rf "$DIST" "$BUILD/work"'
BA_NEW = '''mkdir -p "$DIST"
rm -rf "$BUILD/work"
rm -f "$DIST/orbit-calc" "$DIST/orbit-calc-linux-x86_64"'''

WE_OLD = '''rm -rf /src/build/dist /tmp/pyi-work
mkdir -p /src/build/dist'''
WE_NEW = '''mkdir -p /src/build/dist
rm -rf /tmp/pyi-work
rm -f /src/build/dist/orbit-calc.exe /src/build/dist/orbit-calc-windows-x86_64.exe'''

def patch(path: Path, old: str, new: str, name: str) -> bool:
    if not path.is_file():
        print(f"[err] {path} не найден")
        return False
    text = path.read_text(encoding="utf-8")
    if new in text:
        print(f"[skip] {name}")
        return True
    if old not in text:
        print(f"[err] якорь не найден в {path}: {old[:60]!r}")
        return False
    bak = path.with_suffix(path.suffix + ".v6.bak")
    if not bak.exists():
        shutil.copy2(path, bak)
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"[ok]   {name}")
    return True

def main() -> int:
    ok = True
    ok &= patch(ROOT / "build/build_all.sh", BA_OLD, BA_NEW,
                "build_all.sh: удаляет только Linux")
    ok &= patch(ROOT / "build/wine-entrypoint.sh", WE_OLD, WE_NEW,
                "wine-entrypoint.sh: удаляет только Windows")
    return 0 if ok else 1

if __name__ == "__main__":
    sys.exit(main())