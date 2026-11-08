#!/usr/bin/env python3
"""patch_v3.3.py — исправляет SyntaxError: from __future__ imports must occur at the beginning.

Причина: patch_v3.2 вставил bootstrap sys.path ПЕРЕД `from __future__ import annotations`.
Правка: переносит `from __future__` обратно на первое место (после docstring).

Идемпотентен. Резервная копия: cli/calculator.py.v3.3.bak
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

CALC = Path("cli/calculator.py")
FUTURE = "from __future__ import annotations"
BOOT_MARKER = "# ── bootstrap sys.path"


def fix() -> int:
    if not CALC.is_file():
        print(f"[err] {CALC} не найден", file=sys.stderr)
        return 1

    text = CALC.read_text(encoding="utf-8")

    future_pos = text.find(FUTURE)
    boot_pos = text.find(BOOT_MARKER)

    if boot_pos < 0:
        print("[skip] bootstrap не найден — нечего чинить")
        return 0
    if future_pos < 0:
        print("[err] `from __future__ import annotations` потерян", file=sys.stderr)
        return 2

    if future_pos < boot_pos:
        print("[skip] порядок уже правильный (future до bootstrap)")
        return 0

    # future идёт ПОСЛЕ bootstrap — переносим.
    # 1. Извлекаем bootstrap-блок.
    boot_end_marker = "del _sys, _Path, _ROOT\n"
    boot_end = text.find(boot_end_marker, boot_pos)
    if boot_end < 0:
        print(f"[err] не найден конец bootstrap (`{boot_end_marker.strip()}`)",
              file=sys.stderr)
        return 3
    boot_end += len(boot_end_marker)
    bootstrap_block = text[boot_pos:boot_end]

    # 2. Убираем bootstrap и future из исходного места.
    without = text[:boot_pos] + text[boot_end:]
    future_pos = without.find(FUTURE)
    if future_pos < 0:
        print("[err] future потерян после удаления bootstrap", file=sys.stderr)
        return 4

    # 3. Оставляем future на месте, вставляем bootstrap после него.
    insert_at = future_pos + len(FUTURE)
    # Гарантируем ровно одну пустую строку между future и bootstrap.
    tail = without[insert_at:]
    tail_clean = tail.lstrip("\n")
    new_text = without[:insert_at] + "\n\n" + bootstrap_block + tail_clean

    backup = CALC.with_suffix(CALC.suffix + ".v3.3.bak")
    if not backup.exists():
        shutil.copy2(CALC, backup)
        print(f"[backup] {backup}")

    CALC.write_text(new_text, encoding="utf-8")
    print("[ok] bootstrap перенесён после `from __future__ import annotations`")

    # Пост-проверка
    try:
        compile(CALC.read_text(encoding="utf-8"), str(CALC), "exec")
        print("[ok] синтаксис корректен")
    except SyntaxError as exc:
        print(f"[err] всё ещё SyntaxError: {exc}", file=sys.stderr)
        return 5

    return 0


def main() -> int:
    print("[patch v3.3] Порядок future/bootstap")
    print("=" * 50)
    rc = fix()
    print("=" * 50)
    if rc == 0:
        print("[patch v3.3] Готово. Проверьте:")
        print("  python3 cli/calculator.py --solve=47 --latex")
        print("  python3 cli/calculator.py --preset gso")
        print("  pytest tests/ -v")
    return rc


if __name__ == "__main__":
    sys.exit(main())