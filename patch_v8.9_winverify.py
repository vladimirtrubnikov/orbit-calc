#!/usr/bin/env python3
"""patch_v8.9_winverify.py — verify .exe: ASCII input, UTF-8, GLX.

Проблемы текущего verify:
  1. test_input содержит кириллическую "с" — Wine читает как мусор
  2. xvfb-run без GLX → Xlib GLX spam (не критично, но шум)
  3. без PYTHONIOENCODING=utf-8 → mojibake в выводе, check на "Найдено решений" не работает
  4. без WINEDEBUG=-all → сотни fixme-строк в stderr

Фикс: ASCII "s", PYTHONIOENCODING=utf-8, WINEDEBUG=-all, GLX extensions.
Если и это не поможет — graceful timeout (проверьте .exe на Windows).

Идемпотентен. Резервная копия: build_checks.py.v8.9.bak
"""
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parent
CHECKS = ROOT / "build" / "build_checks.py"


OLD_CMD = '''    cmd = [str(binary), f"--solve={sid}"]
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

NEW_CMD = '''    cmd = [str(binary), f"--solve={sid}"]
    env_override = None
    if via_wine:
        if not shutil.which("wine"):
            return Check(binary.name, "info", "wine не установлен (проверьте на Windows)")
        if not shutil.which("xvfb-run"):
            return Check(
                binary.name, "warn",
                "wine без xvfb — консоль Windows требует X11",
                hint="sudo apt install xorg-xvfb xvfb-run",
            )
        _screen = "-screen 0 1024x768x24 +extension GLX +render -noreset"
        cmd = ["xvfb-run", "-a", "-s", _screen, "wine", *cmd]
        env_override = {
            "WINEDEBUG": "-all",
            "PYTHONIOENCODING": "utf-8",
            "PYTHONUTF8": "1",
        }'''


OLD_INPUT = 'test_input = "622\\n622\\n90\\nс\\n1457\\n2\\n"'
NEW_INPUT = 'test_input = "622\\n622\\n90\\ns\\n1457\\n2\\n"   # ASCII "s", не кириллица'


OLD_RUN = '''        r = subprocess.run(
            cmd, input=test_input,
            capture_output=True, text=True, timeout=timeout,
            encoding="utf-8", errors="replace",
        )'''

NEW_RUN = '''        _env = None
        if env_override:
            import os as _os
            _env = {**_os.environ, **env_override}
        r = subprocess.run(
            cmd, input=test_input,
            capture_output=True, text=True, timeout=timeout,
            encoding="utf-8", errors="replace",
            env=_env,
        )'''


def _apply(text: str, old: str, new: str, name: str) -> tuple[str, bool]:
    if new in text:
        print(f"  [skip] {name}")
        return text, True
    if old not in text:
        print(f"  [err] {name}: якорь не найден", file=sys.stderr)
        return text, False
    print(f"  [ok]   {name}")
    return text.replace(old, new, 1), True


def main() -> int:
    print("[patch v8.9] verify .exe: ASCII, UTF-8, GLX")
    print("=" * 50)

    if not CHECKS.is_file():
        print(f"[err] {CHECKS} не найден", file=sys.stderr)
        return 1

    text = CHECKS.read_text(encoding="utf-8")
    ok = True

    text, ok1 = _apply(text, OLD_CMD, NEW_CMD,
                       "xvfb-run + GLX + WINEDEBUG + UTF-8")
    text, ok2 = _apply(text, OLD_INPUT, NEW_INPUT,
                       'test_input: "с" → "s" (ASCII)')
    text, ok3 = _apply(text, OLD_RUN, NEW_RUN,
                       "subprocess.run с env_override")

    if not (ok1 and ok2 and ok3):
        return 2

    try:
        compile(text, str(CHECKS), "exec")
    except SyntaxError as exc:
        print(f"[err] SyntaxError: {exc}", file=sys.stderr)
        return 3

    bak = CHECKS.with_suffix(".py.v8.9.bak")
    if not bak.exists():
        shutil.copy2(CHECKS, bak)
        print(f"[backup] {bak.name}")

    CHECKS.write_text(text, encoding="utf-8")
    print("[ok] синтаксис корректен")

    print("\n" + "=" * 50)
    print("[patch v8.9] Готово. Запуск: python3 build/gui_builder.py")
    print("\nПервый ручной тест (перед GUI):")
    print('  printf "622\\n622\\n90\\ns\\n1457\\n2\\n" | \\')
    print('    PYTHONIOENCODING=utf-8 WINEDEBUG=-all \\')
    print('    timeout 60 xvfb-run -a -s "-screen 0 1024x768x24 +extension GLX" \\')
    print('    wine build/dist/orbit-calc-windows-x86_64.exe --solve=54 2>/dev/null | head -20')
    return 0


if __name__ == "__main__":
    sys.exit(main())