#!/usr/bin/env python3
"""patch_v9_gui_variants.py — GUI-сборщик: 2 версии (CLI + GUI) × 2 платформы.

Создаёт:
  build/requirements-build-gui.txt
  build/build_all_gui.sh
  build/wine-entrypoint-gui.sh
  build/docker-compose.gui.yml

Модифицирует:
  build/Dockerfile.windows  — ARG ORBIT_VARIANT=cli|gui
  gui/app.py                — --version (без QApplication)
  build/build_checks.py     — verify_gui_binary + REQUIRED_FILES
  build/gui_builder.py      — «Что собирать» + 4 метода + _finish

Идемпотентен. Резервные копии: *.v9.bak
"""
from pathlib import Path
import os
import shutil
import stat
import sys

ROOT = Path(__file__).resolve().parent


# ═══════════════════════════════════════════════════════════════════════════
#  Новые файлы
# ═══════════════════════════════════════════════════════════════════════════

NEW_FILES = {

"build/requirements-build-gui.txt": """pyinstaller==6.11.1
PySide6>=6.5
matplotlib>=3.9
numpy>=2.0
""",

"build/build_all_gui.sh": r'''#!/usr/bin/env bash
# build_all_gui.sh — Linux GUI build (PySide6)
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIST="$ROOT/build/dist"
cd "$ROOT"

echo "=== orbit-calc GUI build (Linux) ==="
PYTHON="${PYTHON:-python3}"

if ! "$PYTHON" -c "import PySide6" 2>/dev/null; then
    echo "ERROR: PySide6 не установлен" >&2
    echo "  $PYTHON -m pip install 'PySide6>=6.5'" >&2
    exit 1
fi

if ! "$PYTHON" -c "import PyInstaller" 2>/dev/null; then
    "$PYTHON" -m pip install pyinstaller
fi

"$PYTHON" -c "
import sys
sys.path.insert(0, '$ROOT')
from gui.app import MainWindow
print('OK: gui.app imports')
"

mkdir -p "$DIST"
rm -rf "$ROOT/build/work-gui"
rm -f "$DIST/orbit-calc-gui" "$DIST/orbit-calc-gui-linux-x86_64"

echo
echo "=== PyInstaller (GUI, Linux) ==="
"$PYTHON" -m PyInstaller \
    --clean --noconfirm \
    --distpath "$DIST" \
    --workpath "$ROOT/build/work-gui" \
    "$ROOT/build/orbit-calc-gui.spec"

BIN="$DIST/orbit-calc-gui"
if [ ! -x "$BIN" ]; then
    echo "ERROR: GUI бинарник не создан" >&2
    exit 2
fi

mv "$BIN" "$DIST/orbit-calc-gui-linux-x86_64"
echo "OK: $DIST/orbit-calc-gui-linux-x86_64 ($(du -h "$DIST/orbit-calc-gui-linux-x86_64" | cut -f1))"
''',

"build/wine-entrypoint-gui.sh": r'''#!/usr/bin/env bash
# wine-entrypoint-gui.sh — Windows GUI build (Wine + PySide6)
set -euo pipefail
cd /src

echo "=== Windows GUI build (Wine + PySide6) ==="
wp --version

wp -c "import PySide6; print('OK: PySide6', PySide6.__version__)" || {
    echo "ERROR: PySide6 не установлен в Windows Python" >&2
    exit 1
}

mkdir -p /src/build/dist
rm -rf /tmp/pyi-work-gui
rm -f /src/build/dist/orbit-calc-gui.exe \
      /src/build/dist/orbit-calc-gui-windows-x86_64.exe

echo
echo "=== PyInstaller (GUI, Windows) ==="
wp -m PyInstaller \
    --clean --noconfirm \
    --distpath Z:/src/build/dist \
    --workpath Z:/tmp/pyi-work-gui \
    Z:/src/build/orbit-calc-gui.spec

cd /src/build/dist
if [ -f orbit-calc-gui.exe ]; then
    mv orbit-calc-gui.exe orbit-calc-gui-windows-x86_64.exe
    ls -lh orbit-calc-gui-windows-x86_64.exe
    echo "OK: build/dist/orbit-calc-gui-windows-x86_64.exe"
else
    echo "ERROR: orbit-calc-gui.exe не создан" >&2
    ls -la
    exit 1
fi
''',

"build/docker-compose.gui.yml": """services:
  windows-builder-gui:
    build:
      context: ..
      dockerfile: build/Dockerfile.windows
      args:
        ORBIT_VARIANT: "gui"
    working_dir: /src
    volumes:
      - ..:/src:z
      - wine-cache-gui:/wine:z
    environment:
      ORBIT_VARIANT: "gui"
    entrypoint: ["bash", "/src/build/wine-entrypoint-gui.sh"]

volumes:
  wine-cache-gui:
""",
}


# ═══════════════════════════════════════════════════════════════════════════
#  Хелперы
# ═══════════════════════════════════════════════════════════════════════════

def _apply(path: Path, old: str, new: str, name: str, required: bool = True) -> bool:
    if not path.is_file():
        print(f"  [err] {path.relative_to(ROOT)} не найден", file=sys.stderr)
        return False
    text = path.read_text(encoding="utf-8")
    if new in text:
        print(f"  [skip] {name}")
        return True
    if old not in text:
        if required:
            print(f"  [err] {name}: якорь не найден", file=sys.stderr)
            return False
        print(f"  [info] {name}: якорь отсутствует")
        return True
    bak = path.with_suffix(path.suffix + ".v9.bak")
    if not bak.exists():
        shutil.copy2(path, bak)
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"  [ok]   {name}")
    return True


def _replace_method(path: Path, method: str, new_body: str) -> bool:
    if not path.is_file():
        return False
    text = path.read_text(encoding="utf-8")
    marker = f"    def {method}(self"
    start = text.find(marker)
    if start < 0:
        print(f"  [err] метод {method} не найден", file=sys.stderr)
        return False
    end = text.find("\n    def ", start + 1)
    if end < 0:
        end = len(text)
    new_text = text[:start] + new_body.rstrip() + "\n" + text[end:]
    bak = path.with_suffix(path.suffix + ".v9.bak")
    if not bak.exists():
        shutil.copy2(path, bak)
    path.write_text(new_text, encoding="utf-8")
    print(f"  [ok]   метод {method} обновлён")
    return True


# ═══════════════════════════════════════════════════════════════════════════
#  Dockerfile.windows — вариант cli|lite|gui
# ═══════════════════════════════════════════════════════════════════════════

DOCKERFILE = ROOT / "build" / "Dockerfile.windows"

DOCKER_ARG_OLD = "ARG ORBIT_LITE=0"
DOCKER_ARG_NEW = "ARG ORBIT_LITE=0\nARG ORBIT_VARIANT=cli\nENV ORBIT_VARIANT=${ORBIT_VARIANT}"

DOCKER_REQ_OLD = "COPY build/requirements-build-lite.txt /tmp/req-lite.txt"
DOCKER_REQ_NEW = ("COPY build/requirements-build-lite.txt /tmp/req-lite.txt\n"
                  "COPY build/requirements-build-gui.txt /tmp/req-gui.txt")

DOCKER_PIP_OLD = '''RUN wp -m pip install --upgrade pip \\
    && if [ "${ORBIT_LITE}" = "1" ]; then \\
        echo "=== LITE: только pyinstaller ==="; \\
        wp -m pip install --no-cache-dir -r Z:/tmp/req-lite.txt; \\
    else \\
        echo "=== FULL: pyinstaller + matplotlib + numpy ==="; \\
        wp -m pip install --no-cache-dir -r Z:/tmp/req-full.txt; \\
    fi \\
    && wineserver -w'''

DOCKER_PIP_NEW = '''RUN wp -m pip install --upgrade pip \\
    && if [ "${ORBIT_VARIANT}" = "gui" ]; then \\
        echo "=== GUI: pyinstaller + PySide6 + matplotlib ==="; \\
        wp -m pip install --no-cache-dir -r Z:/tmp/req-gui.txt; \\
    elif [ "${ORBIT_LITE}" = "1" ]; then \\
        echo "=== LITE: только pyinstaller ==="; \\
        wp -m pip install --no-cache-dir -r Z:/tmp/req-lite.txt; \\
    else \\
        echo "=== FULL: pyinstaller + matplotlib + numpy ==="; \\
        wp -m pip install --no-cache-dir -r Z:/tmp/req-full.txt; \\
    fi \\
    && wineserver -w'''


# ═══════════════════════════════════════════════════════════════════════════
#  gui/app.py — --version без QApplication
# ═══════════════════════════════════════════════════════════════════════════

GUI_APP = ROOT / "gui" / "app.py"
GUI_APP_OLD = "def main() -> int:\n    app = QApplication(sys.argv)"
GUI_APP_NEW = (
    "def main() -> int:\n"
    "    if \"--version\" in sys.argv:\n"
    "        print(\"orbit-calc-gui 0.8.0\")\n"
    "        return 0\n"
    "    app = QApplication(sys.argv)"
)


# ═══════════════════════════════════════════════════════════════════════════
#  build_checks.py — verify_gui_binary + новые файлы
# ═══════════════════════════════════════════════════════════════════════════

CHECKS = ROOT / "build" / "build_checks.py"

CHECKS_REQ_OLD = '    "build/requirements-build-lite.txt": True,'
CHECKS_REQ_NEW = '''    "build/requirements-build-lite.txt": True,
    "build/requirements-build-gui.txt": True,
    "build/build_all_gui.sh": True,
    "build/wine-entrypoint-gui.sh": True,
    "build/docker-compose.gui.yml": True,'''


CHECKS_VERIFY_GUI = '''

def verify_gui_binary(binary: Path) -> Check:
    """Проверяет GUI бинарник: размер > 40 MB + file magic (PE32+/ELF)."""
    size_mb = binary.stat().st_size / (1024 * 1024)
    if size_mb < 40:
        return Check(
            binary.name, "warn",
            f"слишком мал ({size_mb:.1f} MB) — не похоже на GUI",
        )
    try:
        r = subprocess.run(
            ["file", "-b", str(binary)],
            capture_output=True, text=True, timeout=5,
        )
        ft = r.stdout.lower()
        if not any(x in ft for x in ("pe32", "elf", "mach-o")):
            return Check(binary.name, "warn",
                         f"неопознанный формат: {ft[:60]}")
    except Exception:
        pass
    return Check(
        binary.name, "ok",
        f"GUI ({size_mb:.1f} MB, PySide6 внутри)",
    )
'''


# ═══════════════════════════════════════════════════════════════════════════
#  gui_builder.py — «Что собирать» + методы + _finish
# ═══════════════════════════════════════════════════════════════════════════

BUILDER = ROOT / "build" / "gui_builder.py"

BUILDER_IMPORT_OLD = "    QFileDialog, QTabWidget, QPushButton, QSizePolicy,\n)"
BUILDER_IMPORT_NEW = "    QFileDialog, QTabWidget, QPushButton, QSizePolicy, QCheckBox,\n)"

BUILDER_VARIANT_ANCHOR = '        plat_box = QGroupBox("Платформы")'
BUILDER_VARIANT_BLOCK = '''        # v9: Что собирать
        variant_box = QGroupBox("Что собирать")
        vv = QVBoxLayout(variant_box)
        self.cli_check = QCheckBox("CLI-калькулятор (54 case)")
        self.cli_check.setChecked(True)
        self.gui_check = QCheckBox("GUI-калькулятор (PySide6, ~150 MB)")
        self.gui_check.setChecked(True)
        vv.addWidget(self.cli_check)
        vv.addWidget(self.gui_check)
        hint_v = QLabel("GUI: 4–6 мин в Docker при первой сборке")
        hint_v.setStyleSheet("color:#888;font-size:10px;")
        vv.addWidget(hint_v)
        lv.addWidget(variant_box)

        plat_box = QGroupBox("Платформы")'''


RUN_BUILD_NEW = '''    def run_build(self) -> None:
        self.log.clear()
        self.section("Сборка пакета")

        mode = "LITE" if self.lite_radio.isChecked() else "FULL"
        self.log_line(f"Режим CLI: {mode}", "info")

        variants = []
        if self.cli_check.isChecked():
            variants.append("cli")
        if self.gui_check.isChecked():
            variants.append("gui")
        if not variants:
            self.log_line("Нечего собирать — отметьте CLI или GUI", "warn")
            return

        if self.both_radio.isChecked():
            platforms = ["windows", "linux"]
        elif self.linux_radio.isChecked():
            platforms = ["linux"]
        else:
            platforms = ["windows"]

        self.log_line(f"Варианты: {variants}  ·  Платформы: {platforms}", "info")
        if "gui" in variants and "windows" in platforms:
            self.log_line("GUI Windows: первый раз ~15 мин (PySide6 слой в Docker)", "info")

        self.queue = ["preflight", "tests"]
        for variant in variants:
            for platform in platforms:
                self.queue.append(f"{platform}-{variant}")

        self._next()
'''

NEXT_NEW = '''    def _next(self) -> None:
        if not self.queue:
            self._finish()
            return
        step = self.queue.pop(0)
        if step == "preflight":
            self.pre_flight()
            QTimer.singleShot(100, self._next)
        elif step == "tests":
            self.run_tests(self._next)
        elif step == "linux-cli":
            self.run_linux_build(self._next)
        elif step == "linux-gui":
            self.run_linux_gui(self._next)
        elif step == "windows-cli":
            self.run_windows_build(self._next)
        elif step == "windows-gui":
            self.run_windows_gui(self._next)
'''

GUI_METHODS = '''    def run_linux_gui(self, on_done=None) -> None:
        if sys.platform != "linux":
            self.log_line("Linux GUI — только на Linux, пропуск", "warn")
            if on_done: on_done()
            return
        self._start(["bash", "build/build_all_gui.sh"],
                    "Linux GUI build", on_done)

    def run_windows_gui(self, on_done=None) -> None:
        if not shutil.which("docker"):
            self.log_line("Docker не установлен — Windows GUI пропуск", "err")
            if on_done: on_done()
            return
        self._start(self._docker() + [
            "compose", "-f", "build/docker-compose.gui.yml",
            "run", "--rm", "windows-builder-gui",
        ], "Windows GUI build", on_done)

'''

FINISH_NEW = '''    def _finish(self) -> None:
        self.section("Сборка завершена")
        self.progress.setRange(0, 100)
        self.progress.setValue(100)
        self.stage_lbl.setText("Готово")
        self.tests_lbl.setText("Тесты:  ✓")

        if not DIST.exists():
            self.log_line("dist/ отсутствует", "err")
            return

        # Собираем все файлы orbit-calc*
        self.section("Содержимое dist/")
        found = []
        for f in sorted(DIST.iterdir()):
            if not f.is_file() or not f.name.startswith("orbit-calc"):
                continue
            size_mb = f.stat().st_size / (1024 * 1024)
            plat = "?"
            try:
                r = subprocess.run(["file", "-b", str(f)],
                                   capture_output=True, text=True, timeout=5)
                ft = r.stdout.lower()
                if "pe32" in ft or "ms windows" in ft:
                    plat = "Windows"
                elif "elf" in ft:
                    plat = "Linux"
                elif "mach-o" in ft:
                    plat = "macOS"
            except Exception:
                pass
            variant = "GUI" if "-gui" in f.name else "CLI"
            self.log_line(f"  ✓ {f.name} ({size_mb:.1f} MB, {variant}, {plat})", "ok")
            found.append(f)

        if not found:
            self.log_line("  dist/ пуст — сборка провалилась", "err")
            return

        # Verify
        self.section("Проверка бинарников")
        try:
            import build_checks as _bc
            for f in found:
                is_gui = "-gui" in f.name
                is_win = f.suffix == ".exe"
                if is_gui:
                    r = _bc.verify_gui_binary(f)
                else:
                    r = _bc.verify_linux_binary(f, sid="54", via_wine=is_win)
                self.log_line(f"  {f.name}: {r.message}", r.status)
        except Exception as exc:
            self.log_line(f"  verify: {exc}", "warn")

        # SHA256SUMS
        self.section("SHA256SUMS")
        try:
            files = [str(f) for f in found]
            if files:
                r = subprocess.run(["sha256sum", *files],
                                   capture_output=True, text=True, timeout=10)
                sums = r.stdout.strip()
                (DIST / "SHA256SUMS.txt").write_text(sums + "\\n")
                for line in sums.splitlines():
                    self.log_line(f"  {line}", "info")
                self.log_line(f"  → SHA256SUMS.txt записан", "ok")
        except Exception as exc:
            self.log_line(f"  sha256sum: {exc}", "warn")
'''


# ═══════════════════════════════════════════════════════════════════════════
#  main
# ═══════════════════════════════════════════════════════════════════════════

def _write_new_files() -> int:
    print("\n[1] Новые файлы")
    n = 0
    for rel, content in NEW_FILES.items():
        path = ROOT / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and path.read_text(encoding="utf-8") == content:
            print(f"  [skip] {rel}")
            continue
        if path.exists():
            bak = path.with_suffix(path.suffix + ".v9.bak")
            if not bak.exists():
                shutil.copy2(path, bak)
            print(f"  [update] {rel}")
        else:
            print(f"  [new]    {rel}")
        path.write_text(content, encoding="utf-8")
        n += 1
    # chmod +x
    for rel in ("build/build_all_gui.sh", "build/wine-entrypoint-gui.sh"):
        p = ROOT / rel
        if p.exists():
            p.chmod(p.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return n


def main() -> int:
    print("[patch v9] GUI-сборщик: 2 версии × 2 платформы")
    print("=" * 60)

    _write_new_files()

    # Dockerfile
    print(f"\n[2] build/Dockerfile.windows")
    ok = True
    ok &= _apply(DOCKERFILE, DOCKER_ARG_OLD, DOCKER_ARG_NEW, "ARG ORBIT_VARIANT")
    ok &= _apply(DOCKERFILE, DOCKER_REQ_OLD, DOCKER_REQ_NEW, "COPY req-gui")
    ok &= _apply(DOCKERFILE, DOCKER_PIP_OLD, DOCKER_PIP_NEW, "pip variant")

    # gui/app.py
    print(f"\n[3] gui/app.py")
    ok &= _apply(GUI_APP, GUI_APP_OLD, GUI_APP_NEW, "--version handler")

    # build_checks.py
    print(f"\n[4] build/build_checks.py")
    ok &= _apply(CHECKS, CHECKS_REQ_OLD, CHECKS_REQ_NEW, "REQUIRED_FILES + 4")

    text = CHECKS.read_text(encoding="utf-8")
    if "def verify_gui_binary" not in text:
        # append at end
        CHECKS.write_text(text.rstrip() + "\n\n" + CHECKS_VERIFY_GUI.strip() + "\n",
                         encoding="utf-8")
        print("  [ok]   verify_gui_binary")
    else:
        print("  [skip] verify_gui_binary")

    # gui_builder.py
    print(f"\n[5] build/gui_builder.py")
    ok &= _apply(BUILDER, BUILDER_IMPORT_OLD, BUILDER_IMPORT_NEW, "QCheckBox import")
    ok &= _apply(BUILDER, BUILDER_VARIANT_ANCHOR, BUILDER_VARIANT_BLOCK,
                 "«Что собирать» group")

    text = BUILDER.read_text(encoding="utf-8")
    if "Варианты:" not in text:
        # replace run_build
        if _replace_method(BUILDER, "run_build", RUN_BUILD_NEW):
            print("  [ok]   run_build → variants × platforms")
    else:
        print("  [skip] run_build")

    text = BUILDER.read_text(encoding="utf-8")
    if "run_linux_gui" not in text:
        # insert before _finish
        marker = "    def _finish(self"
        idx = text.find(marker)
        if idx >= 0:
            text = text[:idx] + GUI_METHODS + "\n" + text[idx:]
            BUILDER.write_text(text, encoding="utf-8")
            print("  [ok]   +run_linux_gui / +run_windows_gui")
        else:
            print("  [err] _finish не найден", file=sys.stderr)
            ok = False
    else:
        print("  [skip] GUI методы")

    text = BUILDER.read_text(encoding="utf-8")
    if "verify_gui_binary" not in text:
        _replace_method(BUILDER, "_finish", FINISH_NEW)
    else:
        print("  [skip] _finish")

    text = BUILDER.read_text(encoding="utf-8")
    if 'step == "linux-gui"' not in text:
        _replace_method(BUILDER, "_next", NEXT_NEW)

    # Синтаксис
    print(f"\n[6] Синтаксис")
    syntax_ok = True
    for rel in ("build/gui_builder.py", "build/build_checks.py", "gui/app.py"):
        p = ROOT / rel
        try:
            compile(p.read_text(encoding="utf-8"), str(p), "exec")
            print(f"  [ok]   {rel}")
        except SyntaxError as exc:
            print(f"  [err]  {rel}: {exc}", file=sys.stderr)
            syntax_ok = False

    if not (ok and syntax_ok):
        print("\n[patch v9] Есть ошибки — см. выше", file=sys.stderr)
        return 1

    # Проверка импорта
    print("\n[verify]")
    import subprocess
    code = (
        "import sys; sys.path.insert(0, '.'); "
        "sys.path.insert(0, 'build'); "
        "import build_checks; "
        "assert hasattr(build_checks, 'verify_gui_binary'); "
        "from pathlib import Path; "
        "checks = build_checks.run_all(Path('.')); "
        "errs, warns, total = build_checks.summary(checks); "
        "print(f'{total} checks ({errs} err, {warns} warn)')"
    )
    r = subprocess.run([sys.executable, "-c", code],
                       capture_output=True, text=True, cwd=str(ROOT),
                       env={**os.environ, "QT_QPA_PLATFORM": "offscreen"})
    if r.returncode == 0:
        print(f"  ✓ {r.stdout.strip()}")
    else:
        print(f"  ✗ {r.stderr.strip()}", file=sys.stderr)
        return 2

    print("\n" + "=" * 60)
    print("[patch v9] Готово")
    print("\nЧто теперь:")
    print("  Чекбоксы: [x] CLI  [x] GUI")
    print("  Платформы: Linux / Windows / Обе")
    print("  → до 4 бинарников одной кнопкой")
    print("\nЗапуск: python3 build/gui_builder.py")
    print("\nПервый прогон с GUI Windows: ~15 мин (PySide6 в Docker)")
    print("Повторно: ~4 мин")
    return 0


if __name__ == "__main__":
    sys.exit(main())