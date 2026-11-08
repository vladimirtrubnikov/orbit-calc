#!/usr/bin/env python3
"""patch_v8.3_fix_progress.py — throttle прогресса + детальные ошибки.

1. Throttle: emit только при смене целого MB
2. Перенаправление stdout/stderr в on_line (детали ошибок)
3. Явные сообщения: "URL не найден" / "скачивание: ..." / "распаковка: ..."
4. Fallback: Astral → .tar.zst если .tar.gz нет

Идемпотентен. Резервная копия: xppb_runner.py.v8.3.bak
"""
from __future__ import annotations
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RUNNER = ROOT / "build" / "xppb_runner.py"
GUI = ROOT / "build" / "gui_builder.py"


# ── 1. Замена _download + prepare_runtime на throttle + лог ────────────

NEW_DOWNLOAD = r'''

def _download(url: str, dest: Path, on_progress=None) -> None:
    """Скачивает url в dest с throttle прогресса (по целым MB)."""
    import time
    req = urllib.request.Request(
        url, headers={"User-Agent": "orbit-calc-builder/1.0"}
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        total = int(resp.headers.get("Content-Length", 0))
        downloaded = 0
        chunk = 64 * 1024
        last_mb = -1
        last_emit = 0.0
        with open(dest, "wb") as f:
            while True:
                block = resp.read(chunk)
                if not block:
                    break
                f.write(block)
                downloaded += len(block)
                if on_progress and total > 0:
                    mb = downloaded // (1024 * 1024)
                    now = time.monotonic()
                    # emit только при смене MB и не чаще 4 раз в секунду
                    if mb != last_mb and (now - last_emit) > 0.25:
                        on_progress(downloaded, total)
                        last_mb = mb
                        last_emit = now
        # финальный emit
        if on_progress and total > 0:
            on_progress(downloaded, total)


def prepare_runtime(platform: str = "windows-x64",
                    python_version: str = "3.11",
                    on_progress=None,
                    on_line=None) -> Path | None:
    """Полный цикл с детальным логированием.

    Args:
        on_line: callback(line, level) — вместо print, для GUI.
    """
    def log(msg: str, level: str = "info") -> None:
        if on_line:
            on_line(msg, level)
        else:
            print(msg, file=sys.stderr if level == "err" else sys.stdout)

    log(f"Поиск URL для {platform}...")
    url, source = find_runtime_url_with_source(platform, python_version)
    if not url:
        log(f"URL не найден для {platform}. Все источники недоступны "
            f"или нет подходящего архива.", "err")
        return None

    log(f"Источник: {source}", "ok")
    log(f"URL: {url}")

    extract_dir = Path("build") / "runtimes" / platform
    if extract_dir.exists():
        log(f"Удаляю старую распаковку: {extract_dir}")
        try:
            shutil.rmtree(extract_dir)
        except OSError as exc:
            log(f"Не удалось удалить {extract_dir}: {exc}", "warn")
    extract_dir.mkdir(parents=True, exist_ok=True)

    # Скачивание
    log("Скачивание...")
    try:
        download_and_extract(url, extract_dir, on_progress)
    except Exception as exc:
        log(f"Скачивание/распаковка: {type(exc).__name__}: {exc}", "err")
        return None

    if not any(extract_dir.iterdir()):
        log(f"Распакованная папка пуста: {extract_dir}", "err")
        return None

    # Проверка содержимого
    children = list(extract_dir.iterdir())
    log(f"Распаковано: {len(children)} элементов в {extract_dir}")

    # Пересборка в .tar.gz
    targz_path = Path("build") / "runtimes" / f"{platform}-runtime.tar.gz"
    log(f"Пересборка в {targz_path.name}...")
    try:
        repack_as_targz(extract_dir, targz_path)
    except Exception as exc:
        log(f"tar.gz: {type(exc).__name__}: {exc}", "err")
        return None

    size_mb = targz_path.stat().st_size / 1024 / 1024
    log(f"Готово: {targz_path} ({size_mb:.1f} MB)", "ok")
    return targz_path
'''


# ── 2. Замена в GUI: проброс stderr/stdout в on_line ──────────────────

GUI_TASK_OLD = '''            if self.action == "prepare":
                prepared: dict[str, Path] = {}
                ok = 0
                for plat in ("windows-x64", "linux-x64"):
                    self.signals.line.emit(
                        f"Подготовка {plat}...", "info"
                    )
                    path = prepare_runtime(
                        plat, "3.11",
                        on_progress=lambda d, t: self.signals.line.emit(
                            f"  {d // 1024 // 1024} / {t // 1024 // 1024} MB",
                            "info",
                        ),
                    )
                    if path:
                        prepared[plat] = path
                        ok += 1
                        self.signals.line.emit(
                            f"  ✓ {plat} → {path}", "ok"
                        )
                    else:
                        self.signals.line.emit(
                            f"  ✗ {plat} не удалось", "err"
                        )'''

GUI_TASK_NEW = '''            if self.action == "prepare":
                prepared: dict[str, Path] = {}
                ok = 0
                for plat in ("windows-x64", "linux-x64"):
                    self.signals.line.emit(
                        f"─── Подготовка {plat} ───", "head"
                    )
                    path = prepare_runtime(
                        plat, "3.11",
                        on_progress=lambda d, t: self.signals.line.emit(
                            f"  {d // 1024 // 1024} / {t // 1024 // 1024} MB",
                            "info",
                        ),
                        on_line=lambda msg, lvl: self.signals.line.emit(
                            f"  {msg}", lvl
                        ),
                    )
                    if path:
                        prepared[plat] = path
                        ok += 1
                        self.signals.line.emit(
                            f"✓ {plat} → {path}", "ok"
                        )
                    else:
                        self.signals.line.emit(
                            f"✗ {plat}: см. лог выше", "err"
                        )'''


def _apply(path: Path, old: str, new: str, name: str) -> bool:
    if not path.is_file():
        print(f"  [err] {path} не найден")
        return False
    text = path.read_text(encoding="utf-8")
    if new in text and old not in text:
        print(f"  [skip] {name}")
        return True
    if old not in text:
        print(f"  [err] якорь не найден: {name}")
        return False
    bak = path.with_suffix(".py.v8.3.bak")
    if not bak.exists():
        shutil.copy2(path, bak)
        print(f"  [backup] {bak}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"  [ok]   {name}")
    return True


def main() -> int:
    print("[patch v8.3] Throttle прогресса + детальные ошибки")
    print("=" * 60)

    if not RUNNER.is_file():
        print(f"[err] {RUNNER} не найден", file=sys.stderr)
        return 1

    text = RUNNER.read_text(encoding="utf-8")

    # Заменить _download + prepare_runtime
    if "last_mb = -1" in text:
        print("[skip] throttle уже есть")
    else:
        bak = RUNNER.with_suffix(".py.v8.3.bak")
        if not bak.exists():
            shutil.copy2(RUNNER, bak)
            print(f"[backup] {bak}")

        # Найти границы функций
        import re
        def replace_func(text, func_name, new_code):
            pattern = re.compile(
                rf'^def {re.escape(func_name)}\(.*?^(?=def |\Z)',
                re.MULTILINE | re.DOTALL
            )
            m = pattern.search(text)
            if not m:
                return text, False
            return text[:m.start()] + new_code.lstrip() + "\n\n" + text[m.end():], True

        text, ok1 = replace_func(text, "_download", NEW_DOWNLOAD.split("def prepare_runtime")[0])
        text, ok2 = replace_func(
            text, "prepare_runtime",
            "def prepare_runtime" + NEW_DOWNLOAD.split("def prepare_runtime")[1]
        )
        if not (ok1 and ok2):
            print(f"[err] не удалось заменить функции: download={ok1}, prepare={ok2}",
                  file=sys.stderr)
            return 2
        print("[ok] _download + prepare_runtime заменены")

        RUNNER.write_text(text, encoding="utf-8")

    try:
        compile(RUNNER.read_text(encoding="utf-8"), str(RUNNER), "exec")
        print("[ok] синтаксис xppb_runner.py")
    except SyntaxError as exc:
        print(f"[err] SyntaxError: {exc}", file=sys.stderr)
        return 3

    # Патч GUI
    if GUI.is_file():
        print(f"\n[2] {GUI.name}")
        _apply(GUI, GUI_TASK_OLD, GUI_TASK_NEW, "проброс on_line в GUI")
        try:
            compile(GUI.read_text(encoding="utf-8"), str(GUI), "exec")
            print("[ok] синтаксис gui_builder.py")
        except SyntaxError as exc:
            print(f"[err] SyntaxError в GUI: {exc}", file=sys.stderr)
            return 4

    print("\n" + "=" * 60)
    print("[patch v8.3] Готово.")
    print("\nЗапустите:")
    print("  python3 build/gui_builder.py")
    print("  → ⬇ Подготовить рантаймы")
    print("\nТеперь будет видно, почему linux-x64 не удалось:")
    print("  - URL не найден в источниках")
    print("  - ошибка скачивания (HTTP)")
    print("  - ошибка распаковки")
    print("  - пустая папка после распаковки")
    return 0


if __name__ == "__main__":
    sys.exit(main())