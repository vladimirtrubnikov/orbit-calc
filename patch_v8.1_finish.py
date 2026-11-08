#!/usr/bin/env python3
"""patch_v8.1_finish.py — добавляет post-build verify в _finish.

Универсальный: ищет _finish или _finish_build.
Идемпотентен. Резервная копия: *.v8.1.bak
"""
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parent
BUILDER = ROOT / "build" / "gui_builder.py"


FINISH_ADD = '''
        # ── v8: verify each binary ───────────────────────────────
        try:
            import build_checks as _bc
            self._section("Проверка бинарников")
            for _f in sorted(DIST.iterdir()):
                if not _f.is_file() or not _f.name.startswith("orbit-calc"):
                    continue
                if _f.suffix == ".exe":
                    _r = _bc.verify_linux_binary(_f, sid="54", via_wine=True)
                else:
                    _r = _bc.verify_linux_binary(_f, sid="54")
                self._log(f"  {_f.name}: {_r.message}", _r.status)
        except Exception as _exc:
            self._log(f"  verify: {_exc}", "warn")
'''


def main() -> int:
    print("[patch v8.1] verify в _finish")
    print("=" * 50)

    if not BUILDER.is_file():
        print(f"[err] {BUILDER} не найден", file=sys.stderr)
        return 1

    text = BUILDER.read_text(encoding="utf-8")

    if "v8: verify each binary" in text:
        print("[skip] verify уже есть в _finish")
        return 0

    # Найти метод _finish (или _finish_build)
    found_name = None
    start = -1
    for name in ("_finish", "_finish_build"):
        marker = f"    def {name}(self"
        pos = text.find(marker)
        if pos >= 0:
            found_name = name
            start = pos
            break

    if found_name is None:
        print("[err] ни _finish, ни _finish_build не найдены", file=sys.stderr)
        print("      Проверьте: grep 'def _finish' build/gui_builder.py",
              file=sys.stderr)
        return 2

    print(f"[info] метод: {found_name} (pos {start})")

    # Конец метода — следующий '\n    def ' или конец файла
    end = text.find("\n    def ", start + 1)
    if end < 0:
        end = len(text)

    # Вставить ПЕРЕД концом метода (перед следующим def)
    new_text = text[:end] + FINISH_ADD + text[end:]

    # Синтаксис
    try:
        compile(new_text, str(BUILDER), "exec")
    except SyntaxError as exc:
        print(f"[err] SyntaxError после вставки: {exc}", file=sys.stderr)
        return 3

    bak = BUILDER.with_suffix(".py.v8.1.bak")
    if not bak.exists():
        shutil.copy2(BUILDER, bak)
        print(f"[backup] {bak.name}")

    BUILDER.write_text(new_text, encoding="utf-8")
    print(f"[ok] verify добавлен в конец {found_name}()")
    print("[ok] синтаксис корректен")

    # Verify — импорт build_checks
    print("\n[verify] build_checks.run_all")
    import subprocess
    code = (
        "import sys; sys.path.insert(0, '.'); "
        "sys.path.insert(0, 'build'); "
        "import build_checks; "
        "from pathlib import Path; "
        "checks = build_checks.run_all(Path('.')); "
        "errs, warns, total = build_checks.summary(checks); "
        "print(f'{total} checks ({errs} err, {warns} warn)')"
    )
    r = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True, text=True, cwd=str(ROOT),
    )
    if r.returncode == 0:
        print(f"  ✓ {r.stdout.strip()}")
    else:
        print(f"  ✗ {r.stderr.strip()}", file=sys.stderr)
        return 4

    print("\n" + "=" * 50)
    print("[patch v8.1] Готово")
    return 0


if __name__ == "__main__":
    sys.exit(main())