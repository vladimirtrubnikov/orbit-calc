#!/usr/bin/env python3
"""patch_v8.6_platform.py — платформа в _finish через file magic.

Проблема: patch_v8.5 искал self.log_line, а после v8.3 — self._log.
Устойчив: ищет по мелкому блоку "plat = ..." без привязки к имени лог-метода.
"""
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parent
BUILDER = ROOT / "build" / "gui_builder.py"


# Маленький якорь — только блок определения plat, без log-вызова
SMALL_OLD = '''            if f.name.endswith(".exe"):
                plat = "Windows"
            elif "linux" in f.name:
                plat = "Linux"
            else:
                plat = "?"'''

SMALL_NEW = '''            # platform через file magic (надёжнее чем имя)
            plat = "?"
            try:
                _rr = subprocess.run(
                    ["file", "-b", str(f)],
                    capture_output=True, text=True, timeout=5,
                )
                _ft = _rr.stdout.lower()
                if "pe32" in _ft or "ms windows" in _ft:
                    plat = "Windows"
                elif "elf" in _ft:
                    plat = "Linux"
                elif "mach-o" in _ft:
                    plat = "macOS"
            except Exception:
                if f.suffix == ".exe":
                    plat = "Windows"
                elif "linux" in f.name:
                    plat = "Linux"'''


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
    print("[patch v8.6] Platform через file magic в _finish")
    print("=" * 50)

    if not BUILDER.is_file():
        print(f"[err] {BUILDER} не найден", file=sys.stderr)
        return 1

    text = BUILDER.read_text(encoding="utf-8")

    # Проверка: subprocess доступен в области видимости?
    if "import subprocess" not in text:
        print("[warn] 'import subprocess' не найден — добавляю", file=sys.stderr)
        # Вставить после импортов
        for anchor in ("import shutil\n", "import sys\n"):
            if anchor in text:
                text = text.replace(
                    anchor, anchor + "import subprocess\n", 1,
                )
                print(f"  [ok]   import subprocess после {anchor.strip()}")
                break

    text, ok = _apply(text, SMALL_OLD, SMALL_NEW,
                      "plat через file magic")

    if not ok:
        # Диагностика: показать что реально в файле
        print("\n[диагностика] первые 15 строк вокруг 'endswith(\".exe\")':",
              file=sys.stderr)
        idx = text.find('f.name.endswith(".exe")')
        if idx >= 0:
            start = max(0, idx - 200)
            end = min(len(text), idx + 300)
            print(text[start:end], file=sys.stderr)
        else:
            print("  строка 'endswith(\".exe\")' вообще не найдена",
                  file=sys.stderr)
        return 2

    try:
        compile(text, str(BUILDER), "exec")
    except SyntaxError as exc:
        print(f"[err] SyntaxError: {exc}", file=sys.stderr)
        return 3

    bak = BUILDER.with_suffix(".py.v8.6.bak")
    if not bak.exists():
        shutil.copy2(BUILDER, bak)
        print(f"  [backup] {bak.name}")

    BUILDER.write_text(text, encoding="utf-8")
    print("  [ok]   синтаксис корректен")

    # Verify
    print("\n[verify]")
    if "file -b" in BUILDER.read_text(encoding="utf-8"):
        print("  ✓ file magic в _finish")
    else:
        print("  ✗ file magic не появился", file=sys.stderr)
        return 4

    print("\n" + "=" * 50)
    print("[patch v8.6] Готово. Запуск: python3 build/gui_builder.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())