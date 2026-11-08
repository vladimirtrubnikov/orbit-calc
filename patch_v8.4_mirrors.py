#!/usr/bin/env python3
"""patch_v8.4_mirrors.py — retry + зеркала для скачивания рантаймов.

Причина: HTTP 504 Gateway Time-out от GitHub CDN.

Добавляет:
  1. _download_with_retries — 3 попытки, экспоненциальная задержка
  2. Список зеркал для github.com/astral-sh/...:
       - ghproxy.net, ghfast.top, gh-proxy.com (URL-префиксы)
       - USTC: mirrors.ustc.edu.cn/github-release/...
       - npmmirror: registry.npmmirror.com/-/binary/python-build-standalone
       - python-standalone.org
  3. Переменная ORBIT_XPPB_MIRROR для ручного указания
  4. Fallback на другие источники (bjia56, python.org)

Идемпотентен. Резервная копия: xppb_runner.py.v8.4.bak
"""
from __future__ import annotations
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RUNNER = ROOT / "build" / "xppb_runner.py"


NEW_BLOCK = r'''

# ═══════════════════════════════════════════════════════════════════════════
#  v8.4: retry + зеркала для скачивания
# ═══════════════════════════════════════════════════════════════════════════

import os
import time


# Зеркала-префиксы: mirror + original_url
GITHUB_MIRROR_PREFIXES = [
    "https://ghproxy.net/",
    "https://ghfast.top/",
    "https://gh-proxy.com/",
]

# Прямые зеркала Astral (замена базового URL)
ASTRAL_BASE = (
    "https://github.com/astral-sh/python-build-standalone/releases/download/"
)
ASTRAL_MIRROR_REPLACEMENTS = [
    # (old_base, new_base)
    (ASTRAL_BASE,
     "https://mirrors.ustc.edu.cn/github-release/astral-sh/"
     "python-build-standalone/LatestRelease/"),
    (ASTRAL_BASE,
     "https://registry.npmmirror.com/-/binary/python-build-standalone/"),
    (ASTRAL_BASE,
     "https://python-standalone.org/mirror/astral-sh/"
     "python-build-standalone/releases/download/"),
]


def _candidate_urls(url: str) -> list[str]:
    """Возвращает список URL для попытки: оригинал + зеркала.

    Порядок:
      1. ORBIT_XPPB_MIRROR (если задан) — полная замена
      2. Оригинал (GitHub)
      3. Прямые зеркала Astral (USTC, npmmirror, python-standalone.org)
      4. Префиксные зеркала (ghproxy.net, ghfast.top, gh-proxy.com)
    """
    out: list[str] = []

    # 1. Пользовательское зеркало (полная замена)
    custom = os.environ.get("ORBIT_XPPB_MIRROR", "").strip()
    if custom:
        # Если задан префикс — просто добавляем
        if custom.endswith("/") and url.startswith("https://github.com/"):
            out.append(custom + url)
        else:
            out.append(custom)
        return out  # если задан вручную — только его

    # 2. Оригинал
    out.append(url)

    # 3. Прямые зеркала Astral
    if url.startswith(ASTRAL_BASE):
        suffix = url[len(ASTRAL_BASE):]
        for _old, new_base in ASTRAL_MIRROR_REPLACEMENTS:
            out.append(new_base + suffix)

    # 4. Префиксные зеркала (для github.com и release-assets)
    if "github.com/" in url:
        for prefix in GITHUB_MIRROR_PREFIXES:
            out.append(prefix + url)

    # 5. Убрать дубли, сохранить порядок
    seen: set[str] = set()
    unique: list[str] = []
    for u in out:
        if u not in seen:
            seen.add(u)
            unique.append(u)
    return unique


def _download_with_retries(url: str, dest: Path, on_progress=None,
                           on_line=None) -> Path:
    """Скачивает url с retry и зеркалами.

    Returns:
        Path к скачанному файлу.

    Raises:
        RuntimeError: если все попытки провалились.
    """
    def log(msg: str, level: str = "info") -> None:
        if on_line:
            on_line(msg, level)
        else:
            print(msg, file=sys.stderr if level == "err" else sys.stdout)

    candidates = _candidate_urls(url)
    log(f"Кандидатов URL: {len(candidates)}")
    for i, c in enumerate(candidates, 1):
        log(f"  [{i}] {c}")

    last_error: Exception | None = None
    for i, candidate in enumerate(candidates, 1):
        log(f"Попытка {i}/{len(candidates)}: {candidate}")
        # Внутренний retry на временные 5xx / timeout (3 попытки)
        for attempt in range(1, 4):
            try:
                _download(candidate, dest, on_progress)
                log(f"Успех: {candidate}", "ok")
                return dest
            except urllib.error.HTTPError as exc:
                last_error = exc
                if exc.code in (502, 503, 504, 408, 429):
                    wait = 2 ** attempt  # 2, 4, 8
                    log(f"  HTTP {exc.code}, повтор через {wait} с "
                        f"(попытка {attempt}/3)", "warn")
                    time.sleep(wait)
                    continue
                # 404, 403 — нет смысла retry
                log(f"  HTTP {exc.code}, пропускаю зеркало", "warn")
                break
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                last_error = exc
                wait = 2 ** attempt
                log(f"  {type(exc).__name__}: {exc}, "
                    f"повтор через {wait} с", "warn")
                time.sleep(wait)
                continue
        log(f"  Зеркало {candidate} не сработало", "warn")

    raise RuntimeError(
        f"Все {len(candidates)} URL и 3 retry не сработали. "
        f"Последняя ошибка: {type(last_error).__name__}: {last_error}"
    )
'''


def main() -> int:
    print("[patch v8.4] Retry + зеркала для скачивания")
    print("=" * 60)

    if not RUNNER.is_file():
        print(f"[err] {RUNNER} не найден", file=sys.stderr)
        return 1

    text = RUNNER.read_text(encoding="utf-8")

    if "_download_with_retries" in text:
        print("[skip] v8.4 уже применён")
        return 0

    bak = RUNNER.with_suffix(".py.v8.4.bak")
    if not bak.exists():
        shutil.copy2(RUNNER, bak)
        print(f"[backup] {bak}")

    # 1. Вставить блок после импортов (перед RUNTIMES_DIR)
    marker = "RUNTIMES_DIR = Path(\"build\") / \"runtimes\""
    if marker not in text:
        print("[err] не найден RUNTIMES_DIR", file=sys.stderr)
        return 2
    text = text.replace(
        marker,
        NEW_BLOCK.strip() + "\n\n" + marker,
        1,
    )
    print("[ok] _download_with_retries + _candidate_urls вставлены")

    # 2. В prepare_runtime заменить _download на _download_with_retries
    old_call = "        download_and_extract(url, extract_dir, on_progress)"
    new_call = "        download_and_extract(url, extract_dir, on_progress, on_line=log)"
    if old_call in text:
        text = text.replace(old_call, new_call, 1)
        print("[ok] prepare_runtime → download_and_extract с on_line")
    else:
        print("[warn] старый вызов download_and_extract не найден")

    # 3. download_and_extract — принять on_line и использовать _download_with_retries
    old_sig = "def download_and_extract(url: str, dest_dir: Path,\n                         on_progress=None) -> Path:"
    new_sig = "def download_and_extract(url: str, dest_dir: Path,\n                         on_progress=None, on_line=None) -> Path:"
    if old_sig in text:
        text = text.replace(old_sig, new_sig, 1)
        print("[ok] download_and_extract signature + on_line")
    else:
        print("[warn] сигнатура download_and_extract не найдена")

    old_dl = '    print(f"[xppb] Скачиваю {url}")\n    _download(url, archive, on_progress)'
    new_dl = '    print(f"[xppb] Скачиваю {url}")\n    _download_with_retries(url, archive, on_progress, on_line)'
    if old_dl in text:
        text = text.replace(old_dl, new_dl, 1)
        print("[ok] _download → _download_with_retries")
    else:
        print("[warn] вызов _download в download_and_extract не найден")

    RUNNER.write_text(text, encoding="utf-8")

    try:
        compile(RUNNER.read_text(encoding="utf-8"), str(RUNNER), "exec")
        print("[ok] синтаксис xppb_runner.py")
    except SyntaxError as exc:
        print(f"[err] SyntaxError: {exc}", file=sys.stderr)
        return 3

    print("\n" + "=" * 60)
    print("[patch v8.4] Готово.")
    print("\nКак использовать:")
    print("  python3 build/gui_builder.py")
    print("  → ⬇ Подготовить рантаймы")
    print()
    print("Теперь при 504 будут попытки:")
    print("  1. GitHub (оригинал) × 3 (2/4/8 с)")
    print("  2. USTC зеркало × 3")
    print("  3. npmmirror × 3")
    print("  4. python-standalone.org × 3")
    print("  5. ghproxy.net × 3")
    print("  6. ghfast.top × 3")
    print("  7. gh-proxy.com × 3")
    print("  = до 21 попытки")
    print()
    print("Ручное зеркало (если всё падает):")
    print("  ORBIT_XPPB_MIRROR='https://ghproxy.net/' python3 build/gui_builder.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())