#!/usr/bin/env python3
"""patch_v8.4_polish.py — 3 полировки после успешного v8.

1. build/build_checks.py: verify_linux_binary timeout 15 → 90 (Wine)
2. build/build_checks.py: _check_artifacts → platform через file magic
3. cli/calculator.py: не нужно; build_all.sh переименование — post-build

Идемпотентен. Резервные копии: *.v8.4.bak
"""
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parent
CHECKS = ROOT / "build" / "build_checks.py"


# ── 1. Timeout в verify_linux_binary ──────────────────────────────────────
TIMEOUT_OLD = '''def verify_linux_binary(binary: Path, sid: str = "54",
                       via_wine: bool = False,
                       timeout: int = 15) -> Check:'''

TIMEOUT_NEW = '''def verify_linux_binary(binary: Path, sid: str = "54",
                       via_wine: bool = False,
                       timeout: int | None = None) -> Check:
    """Запускает binary --solve=54. timeout: 90 для Wine, 15 для native."""
    if timeout is None:
        timeout = 90 if via_wine else 15
'''


# ── 2. Платформа через file magic ─────────────────────────────────────────
PLAT_OLD = '''    for b in bins:
        mtime = b.stat().st_mtime
        size_mb = b.stat().st_size / (1024 * 1024)
        age_h = (max_src - mtime) / 3600 if max_src > mtime else 0

        if mtime < max_src:
            checks.append(Check(
                f"{b.name} ({size_mb:.1f} MB)", "warn",
                f"устарел на {age_h:.1f} ч относительно исходников",
                hint="Пересоберите пакет (🚀)",
                category="Артефакты",
            ))
        else:
            checks.append(Check(
                f"{b.name} ({size_mb:.1f} MB)", "ok",
                "актуален",
                category="Артефакты",
            ))'''

PLAT_NEW = '''    for b in bins:
        mtime = b.stat().st_mtime
        size_mb = b.stat().st_size / (1024 * 1024)
        age_h = (max_src - mtime) / 3600 if max_src > mtime else 0

        # Платформа через file magic
        plat = "?"
        try:
            r = subprocess.run(
                ["file", "-b", str(b)],
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
            pass

        label = f"{b.name} ({size_mb:.1f} MB, {plat})"
        if mtime < max_src:
            checks.append(Check(
                label, "warn",
                f"устарел на {age_h:.1f} ч относительно исходников",
                hint="Пересоберите пакет (🚀)",
                category="Артефакты",
            ))
        else:
            checks.append(Check(
                label, "ok", "актуален", category="Артефакты",
            ))'''


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
    print("[patch v8.4] Полировка v8")
    print("=" * 50)

    if not CHECKS.is_file():
        print(f"[err] {CHECKS} не найден", file=sys.stderr)
        return 1

    text = CHECKS.read_text(encoding="utf-8")
    ok = True
    text, ok1 = _apply(text, TIMEOUT_OLD, TIMEOUT_NEW,
                       "timeout 15 → 90 для Wine")
    text, ok2 = _apply(text, PLAT_OLD, PLAT_NEW,
                       "platform через file magic")
    ok = ok1 and ok2

    if not ok:
        return 2

    try:
        compile(text, str(CHECKS), "exec")
    except SyntaxError as exc:
        print(f"[err] SyntaxError: {exc}", file=sys.stderr)
        return 3

    bak = CHECKS.with_suffix(".py.v8.4.bak")
    if not bak.exists():
        shutil.copy2(CHECKS, bak)
        print(f"[backup] {bak.name}")

    CHECKS.write_text(text, encoding="utf-8")
    print("[ok] синтаксис корректен")

    print("\n[verify]")
    import subprocess
    code = (
        "import sys; sys.path.insert(0, '.'); sys.path.insert(0, 'build'); "
        "import build_checks; "
        "from pathlib import Path; "
        "checks = build_checks.run_all(Path('.')); "
        "errs, warns, total = build_checks.summary(checks); "
        "print(f'{total} checks ({errs} err, {warns} warn)'); "
        "[print(f'  {c.name}: {c.message}') for c in checks "
        " if c.category == 'Артефакты']"
    )
    r = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True, text=True, cwd=str(ROOT),
    )
    if r.returncode == 0:
        for line in r.stdout.strip().splitlines():
            print(f"  ✓ {line}")
    else:
        print(f"  ✗ {r.stderr.strip()}", file=sys.stderr)
        return 4

    print("\n" + "=" * 50)
    print("[patch v8.4] Готово")
    return 0


if __name__ == "__main__":
    sys.exit(main())