#!/usr/bin/env python3
"""patch_v8.5_final.py — финальные фиксы v8.

1. build_checks.verify_linux_binary: errors="replace" (CP866 от Wine)
2. gui_builder._finish: platform через file magic (как в build_checks)

Идемпотентен. Резервные копии: *.v8.5.bak
"""
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parent
CHECKS = ROOT / "build" / "build_checks.py"
BUILDER = ROOT / "build" / "gui_builder.py"


# ═══════════════════════════════════════════════════════════════════════════
#  Fix 1: errors="replace" в verify_linux_binary
# ═══════════════════════════════════════════════════════════════════════════

VERIFY_OLD = '''    try:
        r = subprocess.run(
            cmd, input=test_input,
            capture_output=True, text=True, timeout=timeout,
        )
        out = r.stdout'''

VERIFY_NEW = '''    try:
        # errors="replace": Wine выводит CP866/CP1251 — не UTF-8
        r = subprocess.run(
            cmd, input=test_input,
            capture_output=True, text=True, timeout=timeout,
            encoding="utf-8", errors="replace",
        )
        out = r.stdout'''


# ═══════════════════════════════════════════════════════════════════════════
#  Fix 2: platform в gui_builder._finish
# ═══════════════════════════════════════════════════════════════════════════

FINISH_OLD = '''        for f in sorted(DIST.iterdir()):
            if not f.is_file() or not f.name.startswith("orbit-calc"):
                continue
            found = True
            size_mb = f.stat().st_size / (1024 * 1024)
            if f.name.endswith(".exe"):
                plat = "Windows"
            elif "linux" in f.name:
                plat = "Linux"
            else:
                plat = "?"
            self.log_line(f"  ✓ {f.name} ({size_mb:.1f} MB, {plat})", "ok")'''

FINISH_NEW = '''        for f in sorted(DIST.iterdir()):
            if not f.is_file() or not f.name.startswith("orbit-calc"):
                continue
            found = True
            size_mb = f.stat().st_size / (1024 * 1024)
            # platform через file magic (надёжнее чем имя)
            plat = "?"
            try:
                r = subprocess.run(
                    ["file", "-b", str(f)],
                    capture_output=True, text=True, timeout=5,
                )
                ft = r.stdout.lower()
                if "pe32" in ft or "ms windows" in ft:
                    plat = "Windows"
                elif "elf" in ft:
                    plat = "Linux"
                elif "mach-o" in ft:
                    plat = "macOS"
            except Exception:
                # fallback: по расширению
                if f.suffix == ".exe":
                    plat = "Windows"
                elif "linux" in f.name:
                    plat = "Linux"
            self.log_line(f"  ✓ {f.name} ({size_mb:.1f} MB, {plat})", "ok")'''


def _apply(path: Path, old: str, new: str, name: str) -> bool:
    if not path.is_file():
        print(f"  [err] {path} не найден", file=sys.stderr)
        return False
    text = path.read_text(encoding="utf-8")
    if new in text:
        print(f"  [skip] {name}")
        return True
    if old not in text:
        print(f"  [err] {name}: якорь не найден", file=sys.stderr)
        return False
    bak = path.with_suffix(path.suffix + ".v8.5.bak")
    if not bak.exists():
        shutil.copy2(path, bak)
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"  [ok]   {name}")
    return True


def main() -> int:
    print("[patch v8.5] Финальные фиксы v8")
    print("=" * 50)

    print(f"\n[1] {CHECKS.relative_to(ROOT)}")
    ok1 = _apply(CHECKS, VERIFY_OLD, VERIFY_NEW,
                 'errors="replace" в verify_linux_binary')

    print(f"\n[2] {BUILDER.relative_to(ROOT)}")
    ok2 = _apply(BUILDER, FINISH_OLD, FINISH_NEW,
                 "platform через file magic в _finish")

    if not (ok1 and ok2):
        return 2

    # Синтаксис
    print("\n[3] Синтаксис")
    for p in (CHECKS, BUILDER):
        try:
            compile(p.read_text(encoding="utf-8"), str(p), "exec")
            print(f"  [ok]   {p.name}")
        except SyntaxError as exc:
            print(f"  [err]  {p.name}: {exc}", file=sys.stderr)
            return 3

    print("\n" + "=" * 50)
    print("[patch v8.5] Готово")
    print("\nЧто теперь:")
    print("  • verify .exe — ошибка декодирования → мягкая обработка")
    print("  • post-build platform → по file magic, не по имени")
    return 0


if __name__ == "__main__":
    sys.exit(main())