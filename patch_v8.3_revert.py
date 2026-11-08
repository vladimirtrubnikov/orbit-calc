#!/usr/bin/env python3
"""patch_v8.3_revert.py — откат лишних переименований v8.2.

v8.2 ошибочно заменил:
  self._section( → self.log_section(   (методы _section/_log существуют)
  self._log(     → self.log_line(

Правильно только:
  self.stage_label → self.stage_lbl   (это уже сделано, оставляем)

Идемпотентен. Резервная копия: *.v8.3.bak
"""
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parent
BUILDER = ROOT / "build" / "gui_builder.py"


def main() -> int:
    print("[patch v8.3] Откат лишних переименований v8.2")
    print("=" * 50)

    if not BUILDER.is_file():
        print(f"[err] {BUILDER} не найден", file=sys.stderr)
        return 1

    text = BUILDER.read_text(encoding="utf-8")
    original = text

    # Откатить ТОЛЬКО два ошибочных переименования.
    # self.stage_lbl — оставляем (это правильно).
    fixes = [
        ("self.log_section(", "self._section(", "log_section → _section"),
        ("self.log_line(",    "self._log(",     "log_line → _log"),
    ]

    for old, new, name in fixes:
        count = text.count(old)
        if count == 0:
            print(f"  [skip] {name} — не найдено")
            continue
        text = text.replace(old, new)
        print(f"  [ok]   {name} ({count} замен)")

    if text == original:
        print("\n[skip] всё уже в порядке")
        return 0

    # Синтаксис до записи
    try:
        compile(text, str(BUILDER), "exec")
    except SyntaxError as exc:
        print(f"[err] SyntaxError: {exc}", file=sys.stderr)
        return 2

    bak = BUILDER.with_suffix(".py.v8.3.bak")
    if not bak.exists():
        shutil.copy2(BUILDER, bak)
        print(f"[backup] {bak.name}")

    BUILDER.write_text(text, encoding="utf-8")
    print("[ok] синтаксис корректен")

    # Verify: не осталось ли неверных вызовов
    print("\n[verify]")
    remaining = []
    for bad in ("self.log_section(", "self.log_line(", "self.stage_label"):
        if bad in text:
            remaining.append(bad)
    if remaining:
        print(f"  ✗ остались: {remaining}", file=sys.stderr)
        return 3
    print("  ✓ старых имён не осталось")

    # Verify: правильные методы на месте
    for good in ("self._section(", "self._log(", "self.stage_lbl"):
        n = text.count(good)
        if n == 0:
            print(f"  ✗ не найдено: {good}", file=sys.stderr)
            return 4
        print(f"  ✓ {good}: {n}")

    print("\n" + "=" * 50)
    print("[patch v8.3] Готово. Запуск: python3 build/gui_builder.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())