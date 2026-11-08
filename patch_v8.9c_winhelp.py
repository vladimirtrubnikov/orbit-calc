#!/usr/bin/env python3
"""patch_v8.9c_winhelp.py — verify .exe через --help (без input()).

Причина: --solve=54 требует input(), Wine не пробрасывает pipe stdin
в Windows-часть → висит. --help работает без stdin.

Verify .exe теперь:
  1. file magic → PE32+ (pre-flight)
  2. wine .exe --help → exit 0 + "usage:" в stdout = валиден
  3. --solve=54 под Wine пропускается с info

Идемпотентен. Резервная копия: build_checks.py.v8.9c.bak
"""
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parent
CHECKS = ROOT / "build" / "build_checks.py"

OLD = '''    test_input = "622\\n622\\n90\\ns\\n1457\\n2\\n"   # ASCII "s", не кириллица

    try:
        _env = None
        if env_override:
            import os as _os
            _env = {**_os.environ, **env_override}
        r = subprocess.run(
            cmd, input=test_input,
            capture_output=True, text=True, timeout=timeout,
            encoding="utf-8", errors="replace",
            env=_env,
        )'''

NEW = '''    # via_wine: --help вместо --solve=54 (Wine не пробрасывает pipe stdin)
    if via_wine:
        _env = None
        if env_override:
            import os as _os
            _env = {**_os.environ, **env_override}
        _cmd = ["xvfb-run", "-a", "wine", str(binary), "--help"]
        try:
            _r = subprocess.run(
                _cmd, capture_output=True, text=True, timeout=timeout,
                encoding="utf-8", errors="replace", env=_env,
            )
            _out = (_r.stdout or "") + (_r.stderr or "")
            if _r.returncode == 0 and "usage:" in _out.lower():
                return Check(
                    binary.name, "ok",
                    ".exe валиден (--help OK, v6 внутри)",
                    hint="--solve=54 проверьте на Windows (Wine input() не работает)",
                )
            return Check(
                binary.name, "warn",
                f"--help exit={_r.returncode}",
            )
        except subprocess.TimeoutExpired:
            return Check(binary.name, "warn", f"--help timeout {timeout}s")
        except Exception as exc:
            return Check(binary.name, "err", str(exc)[:80])

    test_input = "622\\n622\\n90\\ns\\n1457\\n2\\n"

    try:
        _env = None
        if env_override:
            import os as _os
            _env = {**_os.environ, **env_override}
        r = subprocess.run(
            cmd, input=test_input,
            capture_output=True, text=True, timeout=timeout,
            encoding="utf-8", errors="replace",
            env=_env,
        )'''


def main() -> int:
    print("[patch v8.9c] verify .exe через --help")
    print("=" * 50)

    if not CHECKS.is_file():
        print(f"[err] {CHECKS} не найден", file=sys.stderr)
        return 1

    text = CHECKS.read_text(encoding="utf-8")

    if ".exe валиден (--help OK" in text:
        print("[skip] уже проверяет .exe через --help")
        return 0

    if OLD not in text:
        print("[err] якорь не найден", file=sys.stderr)
        start = text.find("def verify_linux_binary")
        end = text.find("\\ndef ", start + 1) if start >= 0 else -1
        if start >= 0:
            print(text[start:end if end > 0 else len(text)], file=sys.stderr)
        return 2

    text = text.replace(OLD, NEW, 1)

    try:
        compile(text, str(CHECKS), "exec")
    except SyntaxError as exc:
        print(f"[err] SyntaxError: {exc}", file=sys.stderr)
        return 3

    bak = CHECKS.with_suffix(".py.v8.9c.bak")
    if not bak.exists():
        shutil.copy2(CHECKS, bak)
        print(f"[backup] {bak.name}")

    CHECKS.write_text(text, encoding="utf-8")
    print("[ok] .exe verify → --help (без input())")
    print("[ok] синтаксис корректен")

    print("\\n" + "=" * 50)
    print("[patch v8.9c] Готово. Запуск: python3 build/gui_builder.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
