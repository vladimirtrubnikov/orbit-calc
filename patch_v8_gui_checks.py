#!/usr/bin/env python3
"""patch_v8_gui_checks.py — 28 проверок в GUI-сборщике.

Создаёт build/build_checks.py (чистая логика).
Патчит build/gui_builder.py: pre_flight, _finish_build, +Copy Report.

Идемпотентен. Резервные копии: *.v8.bak
"""
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parent
CHECKS = ROOT / "build" / "build_checks.py"
BUILDER = ROOT / "build" / "gui_builder.py"


# ═══════════════════════════════════════════════════════════════════════════
#  build/build_checks.py
# ═══════════════════════════════════════════════════════════════════════════

CHECKS_SRC = r'''"""build/build_checks.py — 28 проверок перед сборкой пакета.

Pure Python, без Qt. Используется build/gui_builder.py.

Каждая проверка возвращает Check(status, name, message, hint, category).
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Check:
    name: str
    status: str          # "ok" | "warn" | "err" | "info"
    message: str = ""
    hint: str = ""
    category: str = "Прочее"


# ═══════════════════════════════════════════════════════════════════════════
#  Категория 1: файлы проекта
# ═══════════════════════════════════════════════════════════════════════════

REQUIRED_FILES = {
    # source
    "cli/calculator.py": True,
    "cli/__init__.py": True,
    "core/__init__.py": True,
    "core/base.py": True,
    "core/astrodynamics.py": True,
    "core/lambert.py": True,
    "core/latex_formulas.py": True,
    "core/optimization.py": True,
    "gui/__init__.py": True,
    "gui/plots.py": True,
    "gui/animations.py": True,
    # build
    "build/orbit-calc.spec": True,
    "build/build_all.sh": True,
    "build/Dockerfile.windows": True,
    "build/wine-entrypoint.sh": True,
    "build/docker-compose.lite.yml": True,
    "build/requirements-build-lite.txt": True,
    "pyproject.toml": True,
    # GUI (опционально)
    "build/orbit-calc-gui.spec": False,
    "gui/__main__.py": False,
    "gui/app.py": False,
    "gui/runner.py": False,
}


def _check_files(root: Path) -> list[Check]:
    checks = []
    for rel, required in REQUIRED_FILES.items():
        path = root / rel
        if path.is_file():
            checks.append(Check(rel, "ok", category="Файлы"))
        elif required:
            checks.append(Check(
                rel, "err", "отсутствует",
                hint=f"Создайте {rel} или запустите нужный patch_vN.py",
                category="Файлы",
            ))
        else:
            checks.append(Check(
                rel, "info", "не найден (опционально)",
                category="Файлы",
            ))
    return checks


# ═══════════════════════════════════════════════════════════════════════════
#  Категория 2: Python-окружение
# ═══════════════════════════════════════════════════════════════════════════


def _check_python() -> list[Check]:
    checks = []
    v = sys.version_info
    ver = f"{v.major}.{v.minor}.{v.micro}"
    if v >= (3, 10):
        checks.append(Check(f"Python {ver}", "ok", category="Python"))
    else:
        checks.append(Check(
            f"Python {ver}", "err", "< 3.10",
            hint="Обновите Python до 3.10+",
            category="Python",
        ))

    # PyInstaller
    try:
        import PyInstaller
        checks.append(Check(
            f"PyInstaller {PyInstaller.__version__}", "ok",
            category="Python",
        ))
    except ImportError:
        checks.append(Check(
            "PyInstaller", "err", "не установлен",
            hint="pip install pyinstaller",
            category="Python",
        ))

    # PySide6 (для GUI-бинарника, необязательно)
    try:
        import PySide6
        checks.append(Check(
            f"PySide6 {PySide6.__version__}", "ok",
            category="Python",
        ))
    except ImportError:
        checks.append(Check(
            "PySide6", "info", "не установлен (GUI опционально)",
            hint="pip install 'PySide6>=6.5'",
            category="Python",
        ))

    return checks


# ═══════════════════════════════════════════════════════════════════════════
#  Категория 3: Docker
# ═══════════════════════════════════════════════════════════════════════════


def _check_docker() -> list[Check]:
    checks = []
    docker = shutil.which("docker")

    if not docker:
        checks.append(Check(
            "docker", "warn", "не найден — Windows-сборка недоступна",
            hint="Установите Docker (Linux-сборка работает без него)",
            category="Docker",
        ))
        return checks

    # snap vs native
    if "/snap/" in docker:
        checks.append(Check(
            "Docker (snap)", "warn", "плохо с SELinux",
            hint="Перейдите на native: "
                 "sudo snap remove docker && sudo apt install docker.io",
            category="Docker",
        ))
    else:
        checks.append(Check(
            f"Docker: {docker}", "ok", category="Docker",
        ))

    # socket
    sock = Path("/var/run/docker.sock")
    if not sock.exists():
        checks.append(Check(
            "docker.sock", "err", "отсутствует — daemon не запущен",
            hint="sudo systemctl start docker",
            category="Docker",
        ))
        return checks

    try:
        import grp
        import pwd
        st = sock.stat()
        gname = grp.getgrgid(st.st_gid).gr_name
        uname = pwd.getpwuid(st.st_uid).pw_name
        perms = oct(st.st_mode)[-3:]
        if gname == "docker":
            checks.append(Check(
                f"docker.sock {perms} {uname}:{gname}", "ok",
                category="Docker",
            ))
        else:
            checks.append(Check(
                f"docker.sock {perms} {uname}:{gname}", "warn",
                f"группа {gname}, не docker",
                hint="sudo systemctl restart docker "
                     "(пересоздаст socket как root:docker)",
                category="Docker",
            ))
    except Exception:
        checks.append(Check(
            "docker.sock", "info", "stat failed", category="Docker",
        ))

    # docker info
    try:
        r = subprocess.run(
            ["docker", "info"], capture_output=True, timeout=10,
        )
        if r.returncode == 0:
            checks.append(Check(
                "docker info", "ok", category="Docker",
            ))
        else:
            err = (r.stderr or b"").decode(errors="replace").strip()[:80]
            checks.append(Check(
                "docker info", "err", err or "failed",
                hint="bash build/setup_docker.sh --fix && newgrp docker",
                category="Docker",
            ))
    except Exception as exc:
        checks.append(Check(
            "docker info", "err", str(exc)[:80],
            category="Docker",
        ))

    # newgrp setuid
    newgrp = Path("/usr/bin/newgrp")
    if newgrp.exists():
        mode = newgrp.stat().st_mode
        if mode & 0o4000:
            checks.append(Check(
                "newgrp (setuid)", "ok", category="Docker",
            ))
        else:
            checks.append(Check(
                "newgrp", "warn",
                f"нет setuid ({oct(mode)[-4:]})",
                hint="sudo chmod 4755 /usr/bin/newgrp",
                category="Docker",
            ))
    else:
        checks.append(Check(
            "newgrp", "info", "не найден", category="Docker",
        ))

    # wine (для локальной проверки .exe)
    if shutil.which("wine"):
        checks.append(Check(
            "wine (локально)", "ok", category="Docker",
        ))
    else:
        checks.append(Check(
            "wine (локально)", "info", "не установлен",
            category="Docker",
        ))

    return checks


# ═══════════════════════════════════════════════════════════════════════════
#  Категория 4: целостность исходников (v6-специфично)
# ═══════════════════════════════════════════════════════════════════════════


def _check_source_integrity(root: Path) -> list[Check]:
    checks = []

    # 1. astrodynamics регистрирует 54 case
    try:
        sys.path.insert(0, str(root))
        from core.astrodynamics import CASE_META, _SOLVERS
        n_meta = len(CASE_META)
        n_solv = len(_SOLVERS)
        if n_meta == 54 and n_solv == 54:
            checks.append(Check(
                "CASE_META / _SOLVERS: 54", "ok", category="Целостность",
            ))
        else:
            checks.append(Check(
                f"CASE_META={n_meta}, _SOLVERS={n_solv}", "err",
                "ожидалось 54",
                hint="Проверьте _s54 и CASE_META['54']",
                category="Целостность",
            ))
    except Exception as exc:
        checks.append(Check(
            "core.astrodynamics", "err", str(exc)[:80],
            category="Целостность",
        ))

    # 2. lambert_universal_nrev импортируется
    try:
        from core.lambert import lambert_universal_nrev
        assert callable(lambert_universal_nrev)
        checks.append(Check(
            "lambert_universal_nrev", "ok", category="Целостность",
        ))
    except Exception as exc:
        checks.append(Check(
            "lambert_universal_nrev", "err", str(exc)[:80],
            hint="Допишите v6-блок в core/lambert.py",
            category="Целостность",
        ))

    # 3. _solve_lambert_nrev существует И до _DISPATCH
    calc = root / "cli" / "calculator.py"
    if calc.is_file():
        text = calc.read_text(encoding="utf-8")
        has_func = "def _solve_lambert_nrev() -> None:" in text
        has_dispatch_entry = '"54": _solve_lambert_nrev' in text

        if not has_func:
            checks.append(Check(
                "_solve_lambert_nrev", "err", "функция не определена",
                hint="Примените patch_v6.2.py или patch_v6.3.py",
                category="Целостность",
            ))
        elif not has_dispatch_entry:
            checks.append(Check(
                "_solve_lambert_nrev → _DISPATCH['54']", "err",
                "не зарегистрирована",
                hint="Примените patch_v6_lambert.py",
                category="Целостность",
            ))
        else:
            # Порядок: функция должна быть ДО _DISPATCH
            f_pos = text.find("def _solve_lambert_nrev() -> None:")
            d_pos = text.find("_DISPATCH = {")
            if 0 <= f_pos < d_pos:
                checks.append(Check(
                    "_solve_lambert_nrev order", "ok",
                    category="Целостность",
                ))
            else:
                checks.append(Check(
                    "_solve_lambert_nrev order", "err",
                    f"функция (L{f_pos}) после _DISPATCH (L{d_pos})",
                    hint="Примените patch_v6.3.py",
                    category="Целостность",
                ))

    # 4. Тесты существуют
    for rel in ("tests/test_lambert_nrev.py", "tests/test_gui_smoke.py"):
        path = root / rel
        if path.is_file():
            checks.append(Check(rel, "ok", category="Целостность"))
        else:
            checks.append(Check(
                rel, "warn", "отсутствует",
                hint="Примените patch_v6_lambert.py / patch_v7_gui.py",
                category="Целостность",
            ))

    return checks


# ═══════════════════════════════════════════════════════════════════════════
#  Категория 5: бинарники в dist/ + staleness
# ═══════════════════════════════════════════════════════════════════════════


def _check_artifacts(root: Path) -> list[Check]:
    dist = root / "build" / "dist"
    checks = []

    if not dist.exists():
        checks.append(Check(
            "dist/", "info", "пуст — сборка не выполнялась",
            category="Артефакты",
        ))
        return checks

    bins = [f for f in dist.iterdir()
            if f.is_file() and f.name.startswith("orbit-calc")]
    if not bins:
        checks.append(Check(
            "dist/", "info", "нет файлов orbit-calc*",
            category="Артефакты",
        ))
        return checks

    # max mtime исходников
    source_files = []
    for sub in ("core", "cli", "gui"):
        d = root / sub
        if d.is_dir():
            source_files.extend(d.rglob("*.py"))
    max_src = max((p.stat().st_mtime for p in source_files if p.is_file()),
                  default=0)

    for b in bins:
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
            ))

    # SHA256SUMS.txt
    if (dist / "SHA256SUMS.txt").is_file():
        checks.append(Check(
            "SHA256SUMS.txt", "ok", category="Артефакты",
        ))
    else:
        checks.append(Check(
            "SHA256SUMS.txt", "info", "нет — создастся после сборки",
            category="Артефакты",
        ))

    return checks


# ═══════════════════════════════════════════════════════════════════════════
#  Категория 6: диск
# ═══════════════════════════════════════════════════════════════════════════


def _check_disk(root: Path) -> list[Check]:
    try:
        free_mb = shutil.disk_usage(root).free / (1024 * 1024)
        if free_mb > 500:
            return [Check(
                f"Свободно {free_mb:.0f} MB", "ok", category="Диск",
            )]
        if free_mb > 200:
            return [Check(
                f"Свободно {free_mb:.0f} MB", "warn",
                "мало для GUI-бинарника (~120 MB)",
                category="Диск",
            )]
        return [Check(
            f"Свободно {free_mb:.0f} MB", "err", "критически мало",
            hint="Освободите >500 MB",
            category="Диск",
        )]
    except Exception as exc:
        return [Check("disk", "info", str(exc)[:60], category="Диск")]


# ═══════════════════════════════════════════════════════════════════════════
#  Публичный API
# ═══════════════════════════════════════════════════════════════════════════


def run_all(root: Path) -> list[Check]:
    """Все проверки. Возвращает list[Check]."""
    sys.path.insert(0, str(root))
    checks: list[Check] = []
    checks.extend(_check_files(root))
    checks.extend(_check_python())
    checks.extend(_check_docker())
    checks.extend(_check_source_integrity(root))
    checks.extend(_check_artifacts(root))
    checks.extend(_check_disk(root))
    return checks


def categorize(checks: list[Check]) -> dict[str, list[Check]]:
    """Группирует по category, сохраняя порядок появления."""
    out: dict[str, list[Check]] = {}
    for c in checks:
        out.setdefault(c.category, []).append(c)
    return out


def summary(checks: list[Check]) -> tuple[int, int, int]:
    """(errors, warnings, total)."""
    errs = sum(1 for c in checks if c.status == "err")
    warns = sum(1 for c in checks if c.status == "warn")
    return errs, warns, len(checks)


def verify_linux_binary(binary: Path, sid: str = "54",
                       via_wine: bool = False,
                       timeout: int = 15) -> Check:
    """Запускает binary --solve=54 с тестовым вводом, проверяет v6.

    Возвращает Check с status='ok' если в выводе есть N=0 single.
    """
    cmd = [str(binary), f"--solve={sid}"]
    if via_wine:
        if not shutil.which("wine"):
            return Check(binary.name, "info", "wine не установлен")
        cmd = ["wine", *cmd]

    test_input = "622\n622\n90\nс\n1457\n2\n"

    try:
        r = subprocess.run(
            cmd, input=test_input,
            capture_output=True, text=True, timeout=timeout,
        )
        out = r.stdout
        if "N=0, single" in out or "Найдено решений" in out:
            return Check(
                binary.name, "ok",
                f"--solve={sid} работает (v6)",
            )
        if "Введите 0..53" in out or "Введите 0..53" in r.stderr:
            return Check(
                binary.name, "err",
                "старая версия (без case 54)",
                hint="Пересоберите пакет",
            )
        if r.returncode != 0:
            return Check(
                binary.name, "warn",
                f"exit {r.returncode}",
            )
        return Check(
            binary.name, "warn",
            "вывод без N=0 (проверьте вручную)",
        )
    except subprocess.TimeoutExpired:
        return Check(binary.name, "err", f"timeout {timeout}s")
    except Exception as exc:
        return Check(binary.name, "err", str(exc)[:80])
'''

# ═══════════════════════════════════════════════════════════════════════════
#  Патч gui_builder.py
# ═══════════════════════════════════════════════════════════════════════════


IMPORT_OLD = '''import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
'''

IMPORT_NEW = '''import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# build_checks: same dir as this file
_BUILD_DIR = Path(__file__).resolve().parent
if str(_BUILD_DIR) not in sys.path:
    sys.path.insert(0, str(_BUILD_DIR))
try:
    import build_checks
except ImportError:
    build_checks = None
'''


PREFLIGHT_NEW = '''    def pre_flight(self) -> None:
        self.log.clear()
        self._section("Pre-flight")
        self._log(f"pwd: {ROOT}", "cmd")

        if build_checks is None:
            self._log("✗ build/build_checks.py не найден", "err")
            return

        all_checks = build_checks.run_all(ROOT)
        by_cat = build_checks.categorize(all_checks)

        for cat_name, items in by_cat.items():
            self._section(cat_name)
            for c in items:
                if c.status == "ok":
                    self._log(f"✓ {c.name}", "ok")
                elif c.status == "warn":
                    self._log(f"! {c.name}: {c.message}", "warn")
                    if c.hint:
                        self._log(f"  → {c.hint}", "info")
                elif c.status == "err":
                    self._log(f"✗ {c.name}: {c.message}", "err")
                    if c.hint:
                        self._log(f"  → {c.hint}", "info")
                else:
                    self._log(f"— {c.name}: {c.message}", "info")

        errs, warns, total = build_checks.summary(all_checks)
        self._log("", "info")
        if errs:
            self._log(f"✗ FAIL: {errs} err, {warns} warn, {total} total", "err")
            self.stage_label.setText(f"Pre-flight: FAIL ({errs} err)")
        elif warns:
            self._log(f"⚠ OK с {warns} предупреждениями ({total} проверок)", "warn")
            self.stage_label.setText(f"Pre-flight: OK ({warns} warn)")
        else:
            self._log(f"✓ OK: {total} проверок", "ok")
            self.stage_label.setText(f"Pre-flight: OK ({total} checks)")

    def _copy_report(self) -> None:
        """Копирует лог в буфер обмена."""
        try:
            from PySide6.QtWidgets import QApplication
            QApplication.clipboard().setText(self.log.toPlainText())
            self._log("✓ Отчёт скопирован в буфер", "ok")
        except Exception as exc:
            self._log(f"clipboard: {exc}", "warn")
'''


FINISH_ADD = '''        # ── v8: verify each binary ───────────────────────────────
        self._section("Проверка бинарников")
        try:
            for f in sorted(DIST.iterdir()):
                if not f.is_file() or not f.name.startswith("orbit-calc"):
                    continue
                if f.suffix == ".exe":
                    r = build_checks.verify_linux_binary(
                        f, sid="54", via_wine=True,
                    )
                    self._log(f"  {f.name}: {r.message}", r.status)
                else:
                    r = build_checks.verify_linux_binary(f, sid="54")
                    self._log(f"  {f.name}: {r.message}", r.status)
        except Exception as exc:
            self._log(f"  verify: {exc}", "warn")

        # ── v8: SHA256SUMS.txt ───────────────────────────────────
        self._section("SHA256SUMS")
        try:
            files = [str(f) for f in sorted(DIST.iterdir())
                     if f.is_file() and f.name.startswith("orbit-calc")]
            if files:
                r = subprocess.run(
                    ["sha256sum", *files],
                    capture_output=True, text=True, timeout=10,
                )
                sums = r.stdout.strip()
                (DIST / "SHA256SUMS.txt").write_text(sums + "\\n")
                for line in sums.splitlines():
                    self._log(f"  {line}", "info")
                self._log(f"  → SHA256SUMS.txt записан", "ok")
        except Exception as exc:
            self._log(f"  sha256sum: {exc}", "warn")
'''


def _apply(path: Path, old: str, new: str, name: str,
           required: bool = True) -> bool:
    if not path.is_file():
        print(f"  [err] {path} не найден", file=sys.stderr)
        return False
    text = path.read_text(encoding="utf-8")
    if new in text:
        print(f"  [skip] {name}")
        return True
    if old not in text:
        if required:
            print(f"  [err] {name}: якорь не найден", file=sys.stderr)
            return False
        print(f"  [info] {name}: якорь отсутствует, пропускаю")
        return True
    bak = path.with_suffix(path.suffix + ".v8.bak")
    if not bak.exists():
        shutil.copy2(path, bak)
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"  [ok]   {name}")
    return True


def _find_method_bounds(text: str, name: str) -> tuple[int, int]:
    start = text.find(f"    def {name}(self")
    if start < 0:
        return -1, -1
    end = text.find("\n    def ", start + 1)
    if end < 0:
        end = len(text)
    return start, end


def _replace_preflight() -> bool:
    """Заменяет весь метод pre_flight в gui_builder.py."""
    if not BUILDER.is_file():
        print(f"  [err] {BUILDER} не найден", file=sys.stderr)
        return False
    text = BUILDER.read_text(encoding="utf-8")

    if "build_checks.run_all" in text:
        print("  [skip] pre_flight уже v8")
        return True

    start, end = _find_method_bounds(text, "pre_flight")
    if start < 0:
        print("  [err] метод pre_flight не найден", file=sys.stderr)
        return False

    bak = BUILDER.with_suffix(".py.v8.bak")
    if not bak.exists():
        shutil.copy2(BUILDER, bak)

    new_text = text[:start] + PREFLIGHT_NEW + "\n" + text[end:]
    BUILDER.write_text(new_text, encoding="utf-8")
    print("  [ok]   pre_flight → v8 (28 проверок)")
    return True


def _patch_finish() -> bool:
    """Добавляет verification + SHA в _finish_build (если ещё нет)."""
    if not BUILDER.is_file():
        return False
    text = BUILDER.read_text(encoding="utf-8")

    if "v8: verify each binary" in text:
        print("  [skip] _finish_build уже v8")
        return True

    # Найти конец метода _finish_build
    start = text.find("    def _finish_build(self)")
    if start < 0:
        print("  [err] _finish_build не найден", file=sys.stderr)
        return False

    end = text.find("\n    def ", start + 1)
    if end < 0:
        print("  [err] конец _finish_build не найден", file=sys.stderr)
        return False

    # Вставить ПЕРЕД концом (перед следующим def)
    new_text = text[:end] + "\n" + FINISH_ADD + "\n" + text[end:]

    bak = BUILDER.with_suffix(".py.v8b.bak")
    if not bak.exists():
        shutil.copy2(BUILDER, bak)

    BUILDER.write_text(new_text, encoding="utf-8")
    print("  [ok]   _finish_build → +verify +SHA256")
    return True


def _add_copy_button() -> bool:
    """Добавляет кнопку Copy Report в Preflight group."""
    if not BUILDER.is_file():
        return False
    text = BUILDER.read_text(encoding="utf-8")

    if '"📋  Copy report"' in text or "📋  Copy report" in text:
        print("  [skip] Copy report уже есть")
        return True

    old = '''        self.preflight_btn = QPushButton("🔍  Pre-flight check")
        self.preflight_btn.clicked.connect(self.pre_flight)
        al.addWidget(self.preflight_btn)
'''
    new = '''        self.preflight_btn = QPushButton("🔍  Pre-flight check (28 проверок)")
        self.preflight_btn.clicked.connect(self.pre_flight)
        al.addWidget(self.preflight_btn)

        self.copy_btn = QPushButton("📋  Copy report")
        self.copy_btn.clicked.connect(self._copy_report)
        al.addWidget(self.copy_btn)
'''
    if old not in text:
        print("  [info] preflight_btn не найден — пропускаю Copy report")
        return True

    bak = BUILDER.with_suffix(".py.v8c.bak")
    if not bak.exists():
        shutil.copy2(BUILDER, bak)
    BUILDER.write_text(text.replace(old, new, 1), encoding="utf-8")
    print("  [ok]   Copy report button")
    return True


def _update_enable_actions() -> bool:
    """Добавляет copy_btn в список disable/enable."""
    if not BUILDER.is_file():
        return False
    text = BUILDER.read_text(encoding="utf-8")
    old = '''    def _enable_actions(self, enabled: bool) -> None:
        for b in (self.preflight_btn, self.tests_btn, self.build_btn,
                  self.open_btn, self.chown_btn, self.sha_btn):
            b.setEnabled(enabled)'''
    new = '''    def _enable_actions(self, enabled: bool) -> None:
        buttons = [self.preflight_btn, self.tests_btn, self.build_btn,
                   self.open_btn, self.chown_btn, self.sha_btn]
        if hasattr(self, "copy_btn"):
            buttons.append(self.copy_btn)
        for b in buttons:
            b.setEnabled(enabled)'''
    if old not in text:
        print("  [info] _enable_actions не найден (старая версия?)")
        return True
    if new in text:
        print("  [skip] _enable_actions уже v8")
        return True
    bak = BUILDER.with_suffix(".py.v8d.bak")
    if not bak.exists():
        shutil.copy2(BUILDER, bak)
    BUILDER.write_text(text.replace(old, new, 1), encoding="utf-8")
    print("  [ok]   _enable_actions → +copy_btn")
    return True


def _verify_import() -> bool:
    """Проверяет, что build_checks импортируется и run_all работает."""
    print("\n[verify]")
    import subprocess
    code = (
        "import sys; sys.path.insert(0, '.'); "
        "sys.path.insert(0, 'build'); "
        "import build_checks; "
        "from pathlib import Path; "
        "checks = build_checks.run_all(Path('.')); "
        "errs, warns, total = build_checks.summary(checks); "
        "print(f'OK: {total} checks ({errs} err, {warns} warn)')"
    )
    r = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True, text=True,
        env={**os.environ, "QT_QPA_PLATFORM": "offscreen"},
    )
    if r.returncode == 0:
        for line in r.stdout.strip().splitlines():
            print(f"  ✓ {line}")
        return True
    print(f"  ✗ {r.stderr.strip()}", file=sys.stderr)
    return False


def main() -> int:
    print("[patch v8] GUI-сборщик: 28 проверок")
    print("=" * 60)

    # 1. build_checks.py
    print(f"\n[1] {CHECKS.relative_to(ROOT)}")
    CHECKS.parent.mkdir(parents=True, exist_ok=True)
    if CHECKS.is_file() and CHECKS.read_text(encoding="utf-8") == CHECKS_SRC:
        print("  [skip] build_checks.py уже совпадает")
    else:
        if CHECKS.is_file():
            bak = CHECKS.with_suffix(".py.v8.bak")
            if not bak.exists():
                shutil.copy2(CHECKS, bak)
            print(f"  [update] build_checks.py (бэкап: {bak.name})")
        else:
            print("  [new] build_checks.py")
        CHECKS.write_text(CHECKS_SRC, encoding="utf-8")

    # Синтаксис
    try:
        compile(CHECKS_SRC, str(CHECKS), "exec")
        print("  [ok]   синтаксис корректен")
    except SyntaxError as exc:
        print(f"  [err] SyntaxError: {exc}", file=sys.stderr)
        return 2

    # 2. gui_builder.py
    print(f"\n[2] {BUILDER.relative_to(ROOT)}")
    if not BUILDER.is_file():
        print(f"  [err] {BUILDER} не найден", file=sys.stderr)
        return 1

    ok = True
    ok &= _apply(BUILDER, IMPORT_OLD, IMPORT_NEW, "imports")
    ok &= _replace_preflight()
    ok &= _patch_finish()
    ok &= _add_copy_button()
    ok &= _update_enable_actions()

    if not ok:
        return 3

    # Синтаксис gui_builder
    try:
        compile(BUILDER.read_text(encoding="utf-8"), str(BUILDER), "exec")
        print("  [ok]   синтаксис корректен")
    except SyntaxError as exc:
        print(f"  [err] SyntaxError: {exc}", file=sys.stderr)
        return 4

    # 3. verify
    ok = _verify_import()

    print("\n" + "=" * 60)
    if ok:
        print("[patch v8] Готово")
        print("\nПроверки в GUI:")
        print("  • Файлы (20) — все обязательные + опциональные")
        print("  • Python (3) — версия, PyInstaller, PySide6")
        print("  • Docker (5) — snap, socket, info, newgrp, wine")
        print("  • Целостность (4) — 54 case, lambert_nrev, порядок, tests")
        print("  • Артефакты (3) — staleness, размер, SHA256SUMS")
        print("  • Диск (1) — свободное место")
        print("\nPost-build:")
        print("  • file magic (ELF/PE)")
        print("  • --solve=54 на каждом бинарнике")
        print("  • SHA256SUMS.txt автогенерация")
        print("\nЗапуск: python3 build/gui_builder.py")
    return 0 if ok else 5


if __name__ == "__main__":
    sys.exit(main())