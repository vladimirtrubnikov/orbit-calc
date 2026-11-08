#!/usr/bin/env python3
"""patch_v8.7_xvfb.py — Wine verify через xvfb-run.

Причина "exit 1": wine консольного .exe требует X11 (wineconsole).
В headless среде xvfb-run создаёт виртуальный display.

Идемпотентен. Резервная копия: build_checks.py.v8.7.bak
"""
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parent
CHECKS = ROOT / "build" / "build_checks.py"


VERIFY_OLD = '''    cmd = [str(binary), f"--solve={sid}"]
    if via_wine:
        if not shutil.which("wine"):
            return Check(binary.name, "info", "wine не установлен")
        cmd = ["wine", *cmd]'''

VERIFY_NEW = '''    cmd = [str(binary), f"--solve={sid}"]
    if via_wine:
        if not shutil.which("wine"):
            return Check(binary.name, "info", "wine не установлен (проверьте на Windows)")
        # Консольный .exe под Wine требует X11 → xvfb-run создаёт виртуальный display.
        if shutil.which("xvfb-run"):
            cmd = ["xvfb-run", "-a", "wine", *cmd]
        else:
            return Check(
                binary.name, "warn",
                "wine без xvfb — консоль Windows требует X11",
                hint="sudo apt install xvfb   или   проверьте .exe на Windows",
            )'''


def main() -> int:
    print("[patch v8.7] Wine verify через xvfb-run")
    print("=" * 50)

    if not CHECKS.is_file():
        print(f"[err] {CHECKS} не найден", file=sys.stderr)
        return 1

    text = CHECKS.read_text(encoding="utf-8")

    if "xvfb-run" in text and "via_wine" in text and "-a" in text:
        # Проверить, что именно в контексте verify, а не в другом месте
        idx = text.find("def verify_linux_binary")
        end = text.find("\ndef ", idx + 1)
        func = text[idx:end] if end > 0 else text[idx:]
        if "xvfb-run" in func:
            print("[skip] verify_linux_binary уже с xvfb-run")
            return 0

    if VERIFY_OLD not in text:
        print("[err] якорь не найден — показываю блок:",
              file=sys.stderr)
        idx = text.find("def verify_linux_binary")
        end = text.find("\ndef ", idx + 1)
        print(text[idx:end] if end > 0 else text[idx:],
              file=sys.stderr)
        return 2

    new_text = text.replace(VERIFY_OLD, VERIFY_NEW, 1)

    try:
        compile(new_text, str(CHECKS), "exec")
    except SyntaxError as exc:
        print(f"[err] SyntaxError: {exc}", file=sys.stderr)
        return 3

    bak = CHECKS.with_suffix(".py.v8.7.bak")
    if not bak.exists():
        shutil.copy2(CHECKS, bak)
        print(f"[backup] {bak.name}")

    CHECKS.write_text(new_text, encoding="utf-8")
    print("[ok] verify_linux_binary → xvfb-run -a wine")
    print("[ok] синтаксис корректен")

    # Проверка наличия xvfb-run
    print("\n[info] доступность xvfb-run:")
    if shutil.which("xvfb-run"):
        print(f"  ✓ {shutil.which('xvfb-run')}")
    else:
        print("  ✗ не установлен — verify .exe будет пропущен с warn")
        print("  → sudo apt install xvfb    (или ALT: sudo apt-get install xvfb)")

    print("\n[info] проверка xvfb-run вживую (wine + xvfb):")
    import subprocess
    if shutil.which("xvfb-run") and shutil.which("wine"):
        binary = ROOT / "build" / "dist" / "orbit-calc-windows-x86_64.exe"
        if binary.is_file():
            try:
                r = subprocess.run(
                    ["xvfb-run", "-a", "wine", str(binary), "--solve=54"],
                    input="622\n622\n90\nс\n1457\n2\n",
                    capture_output=True, text=True, timeout=90,
                    encoding="utf-8", errors="replace",
                )
                if "N=0, single" in r.stdout:
                    print("  ✓ .exe работает под xvfb-run wine")
                elif "Найдено решений" in r.stdout:
                    print("  ✓ .exe работает (N найдено)")
                else:
                    print(f"  ! exit={r.returncode}, стderr={r.stderr[:100]!r}")
                    print(f"  stdout[:200]={r.stdout[:200]!r}")
            except Exception as exc:
                print(f"  ✗ {exc}")
        else:
            print("  [skip] .exe ещё не собран")

    print("\n" + "=" * 50)
    print("[patch v8.7] Готово")
    return 0


if __name__ == "__main__":
    sys.exit(main())