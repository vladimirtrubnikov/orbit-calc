#!/usr/bin/env python3
"""patch_v8_final_fix.py — исправляет вложенные ''' в patch_v8_final.py.

Проблема: RUNNER_CODE = r'''...''' содержит f'''...''' внутри,
что закрывает внешний raw-string. Результат: NameError + SyntaxWarning.

Фикс: f'''...''' → f"""...""" в шаблоне projconf.

Идемпотентен. Бэкап: patch_v8_final.py.broken.bak
"""
from pathlib import Path
import shutil
import sys

PATCH = Path(__file__).resolve().parent / "patch_v8_final.py"


def main() -> int:
    if not PATCH.is_file():
        print(f"[err] {PATCH} не найден", file=sys.stderr)
        return 1

    text = PATCH.read_text(encoding="utf-8")

    if 'config_content = f"""[project]' in text:
        print("[skip] уже исправлено")
        return 0

    bak = PATCH.with_suffix(".py.broken.bak")
    if not bak.exists():
        shutil.copy2(PATCH, bak)
        print(f"[backup] {bak}")

    # 1. Открытие
    OLD_OPEN = "    config_content = f'''[project]"
    NEW_OPEN = '    config_content = f"""[project]'
    if OLD_OPEN not in text:
        print(f"[err] не найден якорь открытия: {OLD_OPEN!r}", file=sys.stderr)
        return 2
    text = text.replace(OLD_OPEN, NEW_OPEN, 1)
    print("[ok] открытие f''' → f\"\"\"")

    # 2. Закрытие
    OLD_CLOSE = "hide_console = true\n'''\n    config_path.write_text"
    NEW_CLOSE = 'hide_console = true\n"""\n    config_path.write_text'
    if OLD_CLOSE not in text:
        print(f"[err] не найден якорь закрытия", file=sys.stderr)
        idx = text.find("hide_console = true")
        if idx >= 0:
            print(f"  контекст: {text[idx:idx+120]!r}", file=sys.stderr)
        return 3
    text = text.replace(OLD_CLOSE, NEW_CLOSE, 1)
    print("[ok] закрытие ''' → \"\"\"")

    PATCH.write_text(text, encoding="utf-8")

    # 3. Проверка компиляции
    try:
        compile(text, str(PATCH), "exec")
        print("[ok] patch_v8_final.py компилируется")
    except SyntaxError as exc:
        print(f"[err] всё ещё SyntaxError: {exc}", file=sys.stderr)
        return 4

    print("\nГотово. Запускайте: python3 patch_v8_final.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())