#!/usr/bin/env python3
"""patch_v8.2_attr_fix.py — фикс имён атрибутов v8/v8.1.

Проблема: v8/v8.1 использовали имена, которых нет в оригинале gui_builder.py:
  self.stage_label  → self.stage_lbl
  self._section(...) → self.log_section(...)
  self._log(...)     → self.log_line(...)

Идемпотентен. Резервная копия: *.v8.2.bak
"""
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parent
BUILDER = ROOT / "build" / "gui_builder.py"


def main() -> int:
    print("[patch v8.2] Имена атрибутов v8/v8.1")
    print("=" * 50)

    if not BUILDER.is_file():
        print(f"[err] {BUILDER} не найден", file=sys.stderr)
        return 1

    text = BUILDER.read_text(encoding="utf-8")
    original = text

    fixes = [
        ("self.stage_label",  "self.stage_lbl",   "stage_label → stage_lbl"),
        ("self._section(",    "self.log_section(", "_section → log_section"),
        ("self._log(",        "self.log_line(",    "_log → log_line"),
    ]

    for old, new, name in fixes:
        count = text.count(old)
        if count == 0:
            print(f"  [skip] {name} — не найдено")
            continue
        text = text.replace(old, new)
        print(f"  [ok]   {name} ({count} замен)")

    if text == original:
        print("\n[skip] всё уже исправлено")
        return 0

    try:
        compile(text, str(BUILDER), "exec")
    except SyntaxError as exc:
        print(f"[err] SyntaxError: {exc}", file=sys.stderr)
        return 2

    bak = BUILDER.with_suffix(".py.v8.2.bak")
    if not bak.exists():
        shutil.copy2(BUILDER, bak)
        print(f"[backup] {bak.name}")

    BUILDER.write_text(text, encoding="utf-8")
    print("[ok] синтаксис корректен")

    # Verify — не осталось ли старых имён
    print("\n[verify]")
    remaining = []
    for old_name in ("self.stage_label", "self._section(", "self._log("):
        if old_name in text:
            remaining.append(old_name)
    if remaining:
        print(f"  ✗ остались: {remaining}", file=sys.stderr)
        return 3
    print("  ✓ все три имени заменены")

    print("\n" + "=" * 50)
    print("[patch v8.2] Готово. Запуск: python3 build/gui_builder.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())