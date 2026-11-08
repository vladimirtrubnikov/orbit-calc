#!/usr/bin/env python3
"""patch_v8_final.py — полная интеграция xppb в GUI: поиск + распаковка + сборка.

Объединяет v8, v8.1, v8.2 и добавляет:
  - download_and_extract: скачивание + распаковка .tar.gz / .zip
  - repack_as_targz: нормализация .zip → .tar.gz
  - prepare_runtime: полный цикл → локальный .tar.gz
  - кнопка «⬇ Подготовить рантаймы» в GUI

Идемпотентен. Резервные копии: *.v8_final.bak
"""
from __future__ import annotations
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BUILD = ROOT / "build"
RUNNER = BUILD / "xppb_runner.py"
GUI = BUILD / "gui_builder.py"


# ═══════════════════════════════════════════════════════════════════════════
#  build/xppb_runner.py — финальная версия
# ═══════════════════════════════════════════════════════════════════════════

RUNNER_CODE = r'''"""build/xppb_runner.py — xppb: поиск, скачивание, распаковка, сборка.

Полный цикл для кроссплатформенной сборки .exe через xppb:
  1. find_runtime_url_with_source — найти URL (Astral / bjia56 / python.org / 14mhz)
  2. download_and_extract         — скачать и распаковать в build/runtimes/<platform>/
  3. repack_as_targz              — если .zip, пересобрать в .tar.gz (что ждёт xppb)
  4. prepare_runtime              — полный цикл → локальный .tar.gz
  5. update_runtimes_in_config    — записать локальный путь в projconf.toml
  6. run_xppb                     — запустить сборку
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tarfile
import urllib.request
import zipfile
from pathlib import Path
from urllib.error import URLError


# ─────────────────────────────────────────────────────────────────────────
#  Константы
# ─────────────────────────────────────────────────────────────────────────
RUNTIMES_DIR = Path("build") / "runtimes"


# ═══════════════════════════════════════════════════════════════════════════
#  ИСТОЧНИКИ РАНТАЙМОВ (по приоритету)
# ═══════════════════════════════════════════════════════════════════════════

RUNTIME_SOURCES = [
    {
        "name": "Astral python-build-standalone",
        "kind": "github",
        "repo": "astral-sh/python-build-standalone",
        "platforms": {"windows-x64", "linux-x64", "macos-arm64"},
        "url_suffix": ".tar.gz",
    },
    {
        "name": "bjia56/portable-python",
        "kind": "github",
        "repo": "bjia56/portable-python",
        "platforms": {"windows-x64", "linux-x64", "macos-arm64"},
        "url_suffix": ".zip",
    },
    {
        "name": "python.org embeddable",
        "kind": "python.org",
        "platforms": {"windows-x64"},
        "url_suffix": ".zip",
    },
    {
        "name": "14mhz/PortablePython",
        "kind": "github",
        "repo": "14mhz/PortablePython",
        "platforms": {"windows-x64", "linux-x64"},
        "url_suffix": ".zip",
    },
]


# ═══════════════════════════════════════════════════════════════════════════
#  ПОИСК URL
# ═══════════════════════════════════════════════════════════════════════════

def _http_json(url: str) -> dict | None:
    try:
        req = urllib.request.Request(
            url,
            headers={
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "orbit-calc-builder/1.0",
            },
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (URLError, json.JSONDecodeError, TimeoutError) as exc:
        print(f"[xppb] HTTP error {url}: {exc}", file=sys.stderr)
        return None


_ASTRAL_PATTERNS = {
    "windows-x64": "x86_64-pc-windows-msvc",
    "linux-x64":   "x86_64-unknown-linux-gnu",
    "macos-arm64": "aarch64-apple-darwin",
}
_ASTRAL_VARIANTS = ["install_only", "shared-install_only", "pgo-full"]


def _find_astral(platform: str, py_ver: str) -> str | None:
    data = _http_json(
        "https://api.github.com/repos/astral-sh/"
        "python-build-standalone/releases/latest"
    )
    if not data:
        return None
    pattern = _ASTRAL_PATTERNS.get(platform)
    if not pattern:
        return None

    candidates = [
        a for a in data.get("assets", [])
        if a.get("name", "").endswith(".tar.gz")
        and pattern in a.get("name", "")
        and f"cpython-{py_ver}" in a.get("name", "")
    ]
    if not candidates:
        candidates = [
            a for a in data.get("assets", [])
            if a.get("name", "").endswith(".tar.gz")
            and pattern in a.get("name", "")
            and "cpython-3." in a.get("name", "")
        ]
    if not candidates:
        return None

    def rank(asset):
        n = asset.get("name", "")
        for i, v in enumerate(_ASTRAL_VARIANTS):
            if v in n:
                return i
        return len(_ASTRAL_VARIANTS)

    candidates.sort(key=rank)
    return candidates[0].get("browser_download_url")


_BJIA56_PATTERNS = {
    "windows-x64": "windows-x86_64",
    "linux-x64":   "linux-x86_64",
    "macos-arm64": "macos-arm64",
}


def _find_bjia56(platform: str, py_ver: str) -> str | None:
    data = _http_json(
        "https://api.github.com/repos/bjia56/portable-python/releases/latest"
    )
    if not data:
        return None
    suffix = _BJIA56_PATTERNS.get(platform)
    if not suffix:
        return None

    candidates = [
        a for a in data.get("assets", [])
        if a.get("name", "").endswith(".zip")
        and suffix in a.get("name", "")
        and (f"-{py_ver}." in a.get("name", "")
             or f"-{py_ver}-" in a.get("name", ""))
    ]
    if not candidates:
        return None

    def rank(asset):
        n = asset.get("name", "")
        if "full" in n:
            return 0
        if "headless" in n:
            return 1
        return 2

    candidates.sort(key=rank)
    return candidates[0].get("browser_download_url")


def _find_pythonorg(platform: str, py_ver: str) -> str | None:
    if platform != "windows-x64":
        return None
    url = (f"https://www.python.org/ftp/python/{py_ver}/"
           f"python-{py_ver}-embed-amd64.zip")
    try:
        req = urllib.request.Request(url, method="HEAD")
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status == 200:
                return url
    except (URLError, TimeoutError):
        pass
    return None


def _find_14mhz(platform: str, py_ver: str) -> str | None:
    data = _http_json(
        "https://api.github.com/repos/14mhz/PortablePython/releases/latest"
    )
    if not data:
        return None
    suffix_map = {"windows-x64": "windows", "linux-x64": "linux"}
    suffix = suffix_map.get(platform)
    if not suffix:
        return None
    for a in data.get("assets", []):
        name = a.get("name", "").lower()
        if not (name.endswith(".zip") or name.endswith(".tar.gz")):
            continue
        if suffix not in name:
            continue
        if py_ver not in name:
            continue
        return a.get("browser_download_url")
    return None


_SOURCE_FINDERS = {
    "Astral python-build-standalone": _find_astral,
    "bjia56/portable-python":          _find_bjia56,
    "python.org embeddable":            _find_pythonorg,
    "14mhz/PortablePython":             _find_14mhz,
}


def find_runtime_url_with_source(
    platform: str = "windows-x64",
    python_version: str = "3.11",
) -> tuple[str | None, str | None]:
    """Возвращает (url, source_name) — перебирает источники по приоритету."""
    for source in RUNTIME_SOURCES:
        name = source["name"]
        if platform not in source["platforms"]:
            continue
        finder = _SOURCE_FINDERS.get(name)
        if finder is None:
            continue
        print(f"[xppb] Пробую {name} ({platform}, py{python_version})")
        url = finder(platform, python_version)
        if url:
            print(f"[xppb] ✓ {name}")
            return url, name
        print(f"[xppb] ✗ {name}")
    return None, None


def find_runtime_url(platform: str = "windows-x64",
                     python_version: str = "3.11") -> str | None:
    url, _ = find_runtime_url_with_source(platform, python_version)
    return url


# ═══════════════════════════════════════════════════════════════════════════
#  СКАЧИВАНИЕ + РАСПАКОВКА
# ═══════════════════════════════════════════════════════════════════════════

def _download(url: str, dest: Path, on_progress=None) -> None:
    """Скачивает url в dest с прогрессом (если есть callback)."""
    req = urllib.request.Request(url, headers={"User-Agent": "orbit-calc-builder/1.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        total = int(resp.headers.get("Content-Length", 0))
        downloaded = 0
        chunk = 64 * 1024
        with open(dest, "wb") as f:
            while True:
                block = resp.read(chunk)
                if not block:
                    break
                f.write(block)
                downloaded += len(block)
                if on_progress and total > 0:
                    on_progress(downloaded, total)


def download_and_extract(url: str, dest_dir: Path,
                         on_progress=None) -> Path:
    """Скачивает .tar.gz / .zip и распаковывает в dest_dir.

    Returns:
        Путь к директории с распакованным содержимым (dest_dir).
    """
    dest_dir.mkdir(parents=True, exist_ok=True)

    # 1. Скачать во временный файл
    suffix = ".tar.gz" if url.endswith(".tar.gz") else ".zip"
    archive = dest_dir.parent / f"_runtime_tmp{suffix}"
    print(f"[xppb] Скачиваю {url}")
    _download(url, archive, on_progress)
    print(f"[xppb] Скачано {archive.stat().st_size / 1024 / 1024:.1f} MB")

    # 2. Распаковать
    print(f"[xppb] Распаковываю в {dest_dir}")
    if suffix == ".tar.gz":
        with tarfile.open(archive, "r:gz") as tar:
            members = tar.getmembers()
            tar.extractall(path=dest_dir, members=members)
    else:
        with zipfile.ZipFile(archive, "r") as zf:
            zf.extractall(dest_dir)

    archive.unlink()

    # 3. Если внутри одна вложенная папка — поднять её содержимое наверх
    children = [p for p in dest_dir.iterdir() if p.is_dir()]
    files = [p for p in dest_dir.iterdir() if p.is_file()]
    if len(children) == 1 and not files:
        nested = children[0]
        print(f"[xppb] Разворачиваю вложенную {nested.name}")
        tmp = dest_dir.parent / f"_unpack_{dest_dir.name}"
        nested.rename(tmp)
        dest_dir.rmdir()
        tmp.rename(dest_dir)

    return dest_dir


def repack_as_targz(src_dir: Path, out_targz: Path) -> Path:
    """Пересобирает содержимое src_dir в .tar.gz (для xppb)."""
    out_targz.parent.mkdir(parents=True, exist_ok=True)
    print(f"[xppb] Пересобираю {src_dir} → {out_targz}")
    with tarfile.open(out_targz, "w:gz") as tar:
        for child in src_dir.iterdir():
            tar.add(child, arcname=child.name)
    return out_targz


def prepare_runtime(platform: str = "windows-x64",
                    python_version: str = "3.11",
                    on_progress=None) -> Path | None:
    """Полный цикл: найти → скачать → распаковать → нормализовать в .tar.gz.

    Returns:
        Путь к локальному .tar.gz или None.
    """
    url, source = find_runtime_url_with_source(platform, python_version)
    if not url:
        print(f"[xppb] Не найден URL для {platform}", file=sys.stderr)
        return None

    print(f"[xppb] Источник: {source}")
    print(f"[xppb] URL: {url}")

    extract_dir = Path("build") / "runtimes" / platform
    if extract_dir.exists():
        print(f"[xppb] Удаляю старую распаковку {extract_dir}")
        shutil.rmtree(extract_dir)
    extract_dir.mkdir(parents=True, exist_ok=True)

    try:
        download_and_extract(url, extract_dir, on_progress)
    except Exception as exc:
        print(f"[xppb] Ошибка скачивания/распаковки: {exc}", file=sys.stderr)
        return None

    # Всегда нормализуем в .tar.gz — xppb ждёт этот формат
    targz_path = Path("build") / "runtimes" / f"{platform}-runtime.tar.gz"
    try:
        repack_as_targz(extract_dir, targz_path)
    except Exception as exc:
        print(f"[xppb] Ошибка пересборки в tar.gz: {exc}", file=sys.stderr)
        return None

    size_mb = targz_path.stat().st_size / 1024 / 1024
    print(f"[xppb] Готово: {targz_path} ({size_mb:.1f} MB)")
    return targz_path


# ═══════════════════════════════════════════════════════════════════════════
#  КОНФИГ + СБОРКА
# ═══════════════════════════════════════════════════════════════════════════

def generate_config(project_root: Path,
                    entry_point: str = "gui/__main__.py",
                    project_name: str = "orbit-calc-gui",
                    dependencies: list[str] | None = None) -> Path:
    """Генерирует projconf.toml для xppb."""
    if dependencies is None:
        dependencies = ["PySide6", "matplotlib"]

    config_path = project_root / "projconf.toml"
    src_list = '", "'.join(["core", "gui", "cli"])
    deps_list = ", ".join(f'"{d}"' for d in dependencies)

    config_content = f"""[project]
name = "{project_name}"
version = "0.1.0"
python_version = "3.11"
entry_point = "{entry_point}"
source_files = ["{src_list}"]
dependencies = [{deps_list}]
hidden_imports = ["core.astrodynamics", "core.lambert", "cli.calculator"]
launch_command = "{{ENTRY_POINT}}"

[runtimes]
# Заполняется кнопкой «⬇ Подготовить рантаймы» или вручную

[windows]
hide_console = true
"""
    config_path.write_text(config_content, encoding="utf-8")
    return config_path


def update_runtimes_in_config(config_path: Path,
                              local_paths: dict[str, Path] | None = None,
                              platforms: list[str] | None = None,
                              python_version: str = "3.11",
                              use_local: bool = False) -> int:
    """Обновляет [runtimes] в projconf.toml.

    Args:
        config_path: путь к projconf.toml
        local_paths: {platform: Path} — если use_local=True, использовать их
        platforms: список платформ (если local_paths не задан)
        python_version: версия Python
        use_local: True — использовать local_paths, False — найти URL

    Returns:
        Количество обновлённых платформ.
    """
    if not config_path.is_file():
        print(f"[xppb] Конфиг не найден: {config_path}", file=sys.stderr)
        return 0

    text = config_path.read_text(encoding="utf-8")
    updated = 0

    if use_local and local_paths:
        items = local_paths.items()
    else:
        if platforms is None:
            platforms = ["windows-x64", "linux-x64"]
        items = []
        for plat in platforms:
            url, src = find_runtime_url_with_source(plat, python_version)
            if url:
                items.append((plat, url))

    for platform, value in items:
        value_str = str(value)
        pattern = re.compile(rf'^({re.escape(platform)}\s*=\s*)".*?"',
                             re.MULTILINE)
        new_line = rf'\g<1>"{value_str}"'
        new_text, n = pattern.subn(new_line, text, count=1)
        if n > 0:
            text = new_text
        elif "[runtimes]" in text:
            text = text.replace("[runtimes]",
                                f'[runtimes]\n{platform} = "{value_str}"', 1)
        else:
            text += f'\n[runtimes]\n{platform} = "{value_str}"\n'
        updated += 1
        print(f"[xppb] {platform} → {value_str}")

    if updated:
        config_path.write_text(text, encoding="utf-8")
        print(f"[xppb] Обновлено {updated} платформ")

    return updated


def check_xppb() -> bool:
    return shutil.which("xppb") is not None


def run_xppb(project_root: Path, on_line=None) -> int:
    if not check_xppb():
        print("[xppb] xppb не установлен: pip install xppb", file=sys.stderr)
        return 127

    cmd = ["xppb"]
    print(f"[xppb] Запуск: {' '.join(cmd)} в {project_root}")

    try:
        proc = subprocess.Popen(
            cmd, cwd=str(project_root),
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1,
        )
        for line in proc.stdout:
            line = line.rstrip()
            if on_line:
                on_line(line)
            else:
                print(line)
        return proc.wait()
    except FileNotFoundError:
        print("[xppb] Команда 'xppb' не найдена", file=sys.stderr)
        return 127
    except Exception as exc:
        print(f"[xppb] Ошибка: {exc}", file=sys.stderr)
        return 1
'''


# ═══════════════════════════════════════════════════════════════════════════
#  Патчи для gui_builder.py
# ═══════════════════════════════════════════════════════════════════════════

IMPORT_OLD = "from pathlib import Path\n"
IMPORT_NEW = (
    "from pathlib import Path\n\n"
    "from build.xppb_runner import (\n"
    "    check_xppb, generate_config, run_xppb,\n"
    "    find_runtime_url_with_source, update_runtimes_in_config,\n"
    "    prepare_runtime,\n"
    ")\n"
    "from PySide6.QtCore import QThreadPool, QRunnable, QObject, Signal\n"
)

MODE_OLD = '''        self.full_radio = QRadioButton("Full — с matplotlib (~200 MB)")
        self.lite_radio = QRadioButton("LITE — без matplotlib (~20 MB)")
        self.full_radio.setChecked(True)'''

MODE_NEW = '''        self.full_radio = QRadioButton("Full — с matplotlib (~200 MB)")
        self.lite_radio = QRadioButton("LITE — без matplotlib (~20 MB)")
        self.xppb_radio = QRadioButton("Кроссплатформенная (xppb)")
        self.xppb_radio.setToolTip(
            "Собрать .exe для Windows из Linux через xppb. "
            "Требует pip install xppb"
        )
        self.full_radio.setChecked(True)'''

GROUP_OLD = '''        self.mode_group.addButton(self.full_radio)
        self.mode_group.addButton(self.lite_radio)'''
GROUP_NEW = '''        self.mode_group.addButton(self.full_radio)
        self.mode_group.addButton(self.lite_radio)
        self.mode_group.addButton(self.xppb_radio)'''

BTN_OLD = '''        self.preflight_btn = QPushButton("🔍  Pre-flight check")
        self.preflight_btn.clicked.connect(self.pre_flight)
        actions_lv.addWidget(self.preflight_btn)'''

BTN_NEW = '''        self.preflight_btn = QPushButton("🔍  Pre-flight check")
        self.preflight_btn.clicked.connect(self.pre_flight)
        actions_lv.addWidget(self.preflight_btn)

        self.find_runtimes_btn = QPushButton("🔍  Найти рантаймы (xppb)")
        self.find_runtimes_btn.setToolTip(
            "Найти URL рантаймов Python через GitHub API"
        )
        self.find_runtimes_btn.clicked.connect(self._on_find_runtimes)
        actions_lv.addWidget(self.find_runtimes_btn)

        self.prepare_runtimes_btn = QPushButton("⬇  Подготовить рантаймы")
        self.prepare_runtimes_btn.setToolTip(
            "Скачать и распаковать рантаймы в build/runtimes/"
        )
        self.prepare_runtimes_btn.clicked.connect(self._on_prepare_runtimes)
        actions_lv.addWidget(self.prepare_runtimes_btn)'''

RUNBUILD_OLD = '''    def run_build(self) -> None:
        self.log.clear()
        self._section("Сборка пакета")
        self.log_line(
            "Режим: " + ("LITE" if self.lite_radio.isChecked() else "Full"),
            "info",
        )'''

RUNBUILD_NEW = '''    def run_build(self) -> None:
        self.log.clear()
        self._section("Сборка пакета")

        if self.xppb_radio.isChecked():
            self._run_xppb_build()
            return

        self.log_line(
            "Режим: " + ("LITE" if self.lite_radio.isChecked() else "Full"),
            "info",
        )'''

METHODS_OLD = "    def _finish_build(self) -> None:"

METHODS_NEW = '''    def _on_find_runtimes(self) -> None:
        """Поиск URL (без скачивания)."""
        self.log.clear()
        self._section("Автопоиск рантаймов (xppb)")

        config_path = ROOT / "projconf.toml"
        if not config_path.is_file():
            try:
                config_path = generate_config(
                    ROOT, "gui/__main__.py", "orbit-calc-gui",
                    ["PySide6", "matplotlib"],
                )
                self.log_line(f"Создан {config_path}", "ok")
            except Exception as exc:
                self.log_line(f"Ошибка: {exc}", "err")
                return

        self.log_line("Запрос к GitHub API...", "info")
        self.stage_label.setText("Поиск рантаймов...")
        self.find_runtimes_btn.setEnabled(False)

        signals = _RuntimesSignals()
        signals.line.connect(self.log_line)
        signals.done.connect(lambda n: self._on_task_done(
            self.find_runtimes_btn, "Рантаймы найдены", n > 0
        ))

        task = _RuntimesTask(
            config_path=config_path,
            action="find",
            signals=signals,
        )
        QThreadPool.globalInstance().start(task)

    def _on_prepare_runtimes(self) -> None:
        """Скачивание + распаковка рантаймов."""
        self.log.clear()
        self._section("Подготовка рантаймов (xppb)")

        config_path = ROOT / "projconf.toml"
        if not config_path.is_file():
            try:
                config_path = generate_config(
                    ROOT, "gui/__main__.py", "orbit-calc-gui",
                    ["PySide6", "matplotlib"],
                )
                self.log_line(f"Создан {config_path}", "ok")
            except Exception as exc:
                self.log_line(f"Ошибка: {exc}", "err")
                return

        self.log_line("Скачивание и распаковка (~1-3 мин)...", "info")
        self.stage_label.setText("Подготовка рантаймов...")
        self.prepare_runtimes_btn.setEnabled(False)

        signals = _RuntimesSignals()
        signals.line.connect(self.log_line)
        signals.done.connect(lambda n: self._on_task_done(
            self.prepare_runtimes_btn, "Рантаймы готовы", n > 0
        ))

        task = _RuntimesTask(
            config_path=config_path,
            action="prepare",
            signals=signals,
        )
        QThreadPool.globalInstance().start(task)

    def _on_task_done(self, btn, message_ok: str, success: bool) -> None:
        btn.setEnabled(True)
        self.stage_label.setText(message_ok if success else "Ошибка")

    def _run_xppb_build(self) -> None:
        """Сборка через xppb."""
        self.log_line("Режим: Кроссплатформенная сборка (xppb)", "info")

        if not check_xppb():
            self.log_line(
                "xppb не установлен. Установите: pip install xppb", "err"
            )
            self.stage_label.setText("xppb: не установлен")
            return

        try:
            config_path = generate_config(
                ROOT, "gui/__main__.py", "orbit-calc-gui",
                ["PySide6", "matplotlib"],
            )
            self.log_line(f"Создан конфиг: {config_path}", "ok")
        except Exception as exc:
            self.log_line(f"Ошибка генерации конфига: {exc}", "err")
            return

        # Если локальные рантаймы есть — использовать их
        local_paths = {}
        for plat in ("windows-x64", "linux-x64"):
            p = ROOT / "build" / "runtimes" / f"{plat}-runtime.tar.gz"
            if p.is_file():
                local_paths[plat] = p

        if local_paths:
            self.log_line(
                f"Локальные рантаймы: {list(local_paths.keys())}", "ok"
            )
            update_runtimes_in_config(config_path, local_paths=local_paths,
                                      use_local=True)
        else:
            self.log_line(
                "Локальные рантаймы не найдены — пробую найти URL", "warn"
            )
            update_runtimes_in_config(config_path)

        self.log_line("Запуск xppb...", "info")
        self.progress.setRange(0, 0)
        self.stop_btn.setEnabled(True)
        self._set_buttons_enabled(False)
        self.stage_label.setText("Выполняется: xppb...")

        def on_line(line: str) -> None:
            level = "info"
            low = line.lower()
            if any(w in low for w in ("error", "failed", "exception")):
                level = "err"
            elif any(w in low for w in ("success", "built", "done", "ok")):
                level = "ok"
            self.log_line(line, level)

        try:
            rc = run_xppb(ROOT, on_line=on_line)
        except Exception as exc:
            self.log_line(f"Критическая ошибка xppb: {exc}", "err")
            rc = 1

        self.progress.setRange(0, 100)
        self.progress.setValue(100 if rc == 0 else 0)
        self.stop_btn.setEnabled(False)
        self._set_buttons_enabled(True)

        if rc == 0:
            self.log_line("xppb завершён успешно.", "ok")
            self.stage_label.setText("Готово (xppb)")
        else:
            self.log_line(f"xppb завершён с кодом {rc}.", "err")
            self.stage_label.setText("Ошибка xppb")

        self._finish_build()

    def _finish_build(self) -> None:'''


# ── QThreadPool helpers (вставляются перед классом BuilderWindow) ──
HELPERS = '''

# ═══════════════════════════════════════════════════════════════════════════
#  Вспомогательные классы для фоновых задач (QThreadPool)
# ═══════════════════════════════════════════════════════════════════════════

class _RuntimesSignals(QObject):
    """Сигналы для безопасной доставки из worker-потока."""
    line = Signal(str, str)     # текст, уровень
    done = Signal(int)           # 0/1 — успех


class _RuntimesTask(QRunnable):
    """Задача: найти URL (action='find') или скачать+распаковать (action='prepare')."""

    def __init__(self, config_path: Path, action: str,
                 signals: _RuntimesSignals):
        super().__init__()
        self.config_path = config_path
        self.action = action
        self.signals = signals

    def run(self) -> None:
        try:
            if self.action == "find":
                n = update_runtimes_in_config(self.config_path)
                self.signals.done.emit(n if n > 0 else 0)
                return

            if self.action == "prepare":
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
                        )

                if prepared:
                    update_runtimes_in_config(
                        self.config_path, local_paths=prepared, use_local=True
                    )
                    self.signals.line.emit(
                        f"projconf.toml обновлён: {list(prepared.keys())}",
                        "ok",
                    )

                self.signals.done.emit(1 if ok > 0 else 0)
                return

            self.signals.line.emit(f"Неизвестное действие: {self.action}", "err")
            self.signals.done.emit(0)
        except Exception as exc:
            self.signals.line.emit(f"Ошибка: {exc}", "err")
            self.signals.done.emit(0)

'''


# ═══════════════════════════════════════════════════════════════════════════
#  Применение
# ═══════════════════════════════════════════════════════════════════════════

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
    bak = path.with_suffix(path.suffix + ".v8_final.bak")
    if not bak.exists():
        shutil.copy2(path, bak)
        print(f"  [backup] {bak}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"  [ok]   {name}")
    return True


def main() -> int:
    print("[patch v8_final] xppb: поиск + распаковка + сборка")
    print("=" * 60)

    BUILD.mkdir(parents=True, exist_ok=True)

    # 1. Перезаписать xppb_runner.py
    print(f"\n[1] {RUNNER.name}")
    if RUNNER.is_file():
        existing = RUNNER.read_text(encoding="utf-8")
        if ("prepare_runtime" in existing
                and "download_and_extract" in existing
                and "repack_as_targz" in existing):
            print("  [skip] все функции уже есть")
        else:
            bak = RUNNER.with_suffix(".py.v8_final.bak")
            if not bak.exists():
                shutil.copy2(RUNNER, bak)
                print(f"  [backup] {bak}")
            RUNNER.write_text(RUNNER_CODE, encoding="utf-8")
            print("  [update] перезаписан (полная версия)")
    else:
        RUNNER.write_text(RUNNER_CODE, encoding="utf-8")
        print("  [new] создан")

    try:
        compile(RUNNER.read_text(encoding="utf-8"), str(RUNNER), "exec")
        print("  [ok] синтаксис")
    except SyntaxError as exc:
        print(f"  [err] SyntaxError: {exc}", file=sys.stderr)
        return 1

    # 2. Патчить gui_builder.py
    print(f"\n[2] {GUI.name}")
    if not GUI.is_file():
        print(f"  [err] {GUI} не найден", file=sys.stderr)
        return 2

    ok = True
    ok &= _apply(GUI, IMPORT_OLD, IMPORT_NEW, "imports")
    ok &= _apply(GUI, MODE_OLD, MODE_NEW, "radio xppb")
    ok &= _apply(GUI, GROUP_OLD, GROUP_NEW, "addButton xppb")
    ok &= _apply(GUI, BTN_OLD, BTN_NEW, "кнопки find+prepare")
    ok &= _apply(GUI, RUNBUILD_OLD, RUNBUILD_NEW, "run_build dispatcher")
    ok &= _apply(GUI, METHODS_OLD, METHODS_NEW, "3 метода xppb")

    gui_text = GUI.read_text(encoding="utf-8")
    if "_RuntimesSignals" not in gui_text:
        anchor = "class BuilderWindow(QMainWindow):"
        if anchor in gui_text:
            gui_text = gui_text.replace(
                anchor, HELPERS.strip() + "\n\n\n" + anchor, 1
            )
            GUI.write_text(gui_text, encoding="utf-8")
            print("  [ok]   _RuntimesSignals / _RuntimesTask")
        else:
            print("  [err] class BuilderWindow не найден", file=sys.stderr)
            ok = False
    else:
        print("  [skip] _RuntimesSignals уже есть")

    if not ok:
        print("\n[err] часть патчей не применилась", file=sys.stderr)
        return 3

    try:
        compile(GUI.read_text(encoding="utf-8"), str(GUI), "exec")
        print("\n[ok] синтаксис gui_builder.py")
    except SyntaxError as exc:
        print(f"\n[err] SyntaxError: {exc}", file=sys.stderr)
        return 4

    print("\n" + "=" * 60)
    print("[patch v8_final] Готово.")
    print("\nКак использовать:")
    print("  1. pip install xppb")
    print("  2. python3 build/gui_builder.py")
    print("  3. «🔍 Найти рантаймы»     — URL в projconf.toml (~5 с)")
    print("  4. «⬇ Подготовить рантаймы» — скачать и распаковать (~2 мин)")
    print("  5. Режим → «Кроссплатформенная (xppb)»")
    print("  6. «🚀 Собрать пакет»")
    print("\nАртефакты: build/runtimes/<platform>-runtime.tar.gz")
    return 0


if __name__ == "__main__":
    sys.exit(main())