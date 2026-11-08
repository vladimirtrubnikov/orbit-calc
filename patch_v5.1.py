#!/usr/bin/env python3
"""patch_v5.1.py — фиксит SPECPATH в spec + создаёт Docker-файлы.

1. build/orbit-calc.spec: .parent.parent → .parent
2. Создаёт: build/docker-compose.yml, build/Dockerfile.linux,
   build/Dockerfile.windows, build/wine-entrypoint.sh,
   build/requirements-build.txt

Идемпотентен. Резервные копии: *.v5.1.bak
"""

from __future__ import annotations

import shutil
import stat
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SPEC = ROOT / "build" / "orbit-calc.spec"

SPEC_OLD = "ROOT = Path(SPECPATH).parent.parent.resolve()"
SPEC_NEW = "ROOT = Path(SPECPATH).parent.resolve()"

FILES = {
    "build/docker-compose.yml": '''services:
  linux-builder:
    build:
      context: ..
      dockerfile: build/Dockerfile.linux
    working_dir: /src
    volumes:
      - ..:/src
    environment:
      ORBIT_LITE: "${ORBIT_LITE:-0}"
    entrypoint: ["bash", "/src/build/build_all.sh"]

  windows-builder:
    build:
      context: ..
      dockerfile: build/Dockerfile.windows
    working_dir: /src
    volumes:
      - ..:/src
      - wine-cache:/wine
    environment:
      ORBIT_LITE: "${ORBIT_LITE:-0}"
    entrypoint: ["bash", "/src/build/wine-entrypoint.sh"]

volumes:
  wine-cache:
''',

    "build/Dockerfile.linux": '''# Linux-сборка в изолированном контейнере
FROM python:3.11-slim-bookworm

ENV DEBIAN_FRONTEND=noninteractive \\
    PYTHONDONTWRITEBYTECODE=1 \\
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \\
        binutils file ca-certificates bash \\
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir --upgrade pip \\
    && pip install --no-cache-dir -r /tmp/req.txt 2>/dev/null || true

COPY build/requirements-build.txt /tmp/req.txt
RUN pip install --no-cache-dir -r /tmp/req.txt

WORKDIR /src

ENTRYPOINT ["bash", "/src/build/build_all.sh"]
''',

    "build/Dockerfile.windows": '''# Windows .exe через Wine на Linux-хосте
FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive \\
    WINEARCH=win64 \\
    WINEPREFIX=/wine \\
    WINEDEBUG=-all \\
    WINEDLLOVERRIDES="mscoree,mshtml=" \\
    PYTHON_VERSION=3.11.9

RUN dpkg --add-architecture i386 \\
    && apt-get update \\
    && apt-get install -y --no-install-recommends \\
        wine64 wine32 xvfb wget ca-certificates unzip xz-utils \\
        cabextract bash \\
    && rm -rf /var/lib/apt/lists/*

RUN wget -q "https://www.python.org/ftp/python/${PYTHON_VERSION}/python-${PYTHON_VERSION}-amd64.exe" -O /tmp/python.exe \\
    && xvfb-run wine /tmp/python.exe /quiet \\
        InstallAllUsers=0 PrependPath=1 Include_test=0 \\
    && rm /tmp/python.exe \\
    && wineboot --init 2>/dev/null || true

COPY build/requirements-build.txt /tmp/req.txt
RUN xvfb-run wine python -m pip install --upgrade pip \\
    && xvfb-run wine python -m pip install --no-cache-dir -r Z:/tmp/req.txt

WORKDIR /src

ENTRYPOINT ["bash", "/src/build/wine-entrypoint.sh"]
''',

    "build/wine-entrypoint.sh": '''#!/usr/bin/env bash
# wine-entrypoint.sh — PyInstaller внутри Wine
set -euo pipefail

cd /src

echo "=== Windows build (Wine) ==="

echo "=== Smoke test (Wine Python) ==="
xvfb-run wine python -c "
import sys
sys.path.insert(0, '.')
from core.astrodynamics import solve_case
r = solve_case('1', a=7000, e=0.1)
assert 'error' not in r, r
print('OK: solve_case работает под Windows Python')
"

if [ "${ORBIT_LITE:-0}" != "1" ]; then
    xvfb-run wine python -c "import matplotlib; print('OK: matplotlib', matplotlib.__version__)"
fi

rm -rf /src/build/dist /tmp/pyi-work
mkdir -p /src/build/dist

echo
echo "=== PyInstaller (Windows) ==="
xvfb-run wine python -m PyInstaller \\
    --clean --noconfirm \\
    --distpath Z:/src/build/dist \\
    --workpath Z:/tmp/pyi-work \\
    Z:/src/build/orbit-calc.spec

cd /src/build/dist
if [ -f orbit-calc.exe ]; then
    mv orbit-calc.exe orbit-calc-windows-x86_64.exe
    ls -lh orbit-calc-windows-x86_64.exe
    echo "OK: build/dist/orbit-calc-windows-x86_64.exe"
else
    echo "ERROR: orbit-calc.exe не создан" >&2
    ls -la
    exit 1
fi
''',

    "build/requirements-build.txt": '''pyinstaller==6.11.1
matplotlib==3.9.2
numpy==2.1.3
''',
}


def _patch_spec() -> int:
    print(f"\n[1] {SPEC}")
    if not SPEC.is_file():
        print("  [err] spec не найден", file=sys.stderr)
        return 1
    text = SPEC.read_text(encoding="utf-8")
    if SPEC_NEW in text and SPEC_OLD not in text:
        print("  [skip] SPECPATH уже исправлен")
        return 0
    if SPEC_OLD not in text:
        print("  [err] якорь не найден", file=sys.stderr)
        # Попробуем более широкий поиск
        for line in text.splitlines():
            if "SPECPATH" in line and "ROOT" in line:
                print(f"  Найдено: {line.strip()!r}", file=sys.stderr)
        return 2
    backup = SPEC.with_suffix(".spec.v5.1.bak")
    if not backup.exists():
        shutil.copy2(SPEC, backup)
    SPEC.write_text(text.replace(SPEC_OLD, SPEC_NEW, 1), encoding="utf-8")
    print("  [ok]   .parent.parent → .parent")
    return 0


def _create_files() -> int:
    print("\n[2] Создание build-файлов")
    created = 0
    for rel, content in FILES.items():
        p = ROOT / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        if p.exists():
            print(f"  [skip] {rel}")
            continue
        p.write_text(content, encoding="utf-8")
        print(f"  [ok]   {rel}")
        created += 1

    sh = ROOT / "build" / "wine-entrypoint.sh"
    if sh.exists():
        sh.chmod(sh.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        print("  [ok]   chmod +x build/wine-entrypoint.sh")

    ba = ROOT / "build" / "build_all.sh"
    if ba.exists():
        ba.chmod(ba.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    return created


def _verify_spec_logic() -> int:
    """Проверяет, что ROOT/cli/calculator.py существует."""
    print("\n[verify] Логика spec")
    import subprocess
    code = (
        "from pathlib import Path; "
        f"SPECPATH = '{ROOT / 'build'}'; "
        "ROOT = Path(SPECPATH).parent.resolve(); "
        "calc = ROOT / 'cli' / 'calculator.py'; "
        "print('ROOT =', ROOT); "
        "print('calc =', calc); "
        "assert calc.exists(), f'NOT FOUND: {calc}'"
    )
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    if r.returncode == 0:
        for line in r.stdout.strip().splitlines():
            print(f"  [ok]   {line}")
        return 0
    print(f"  [err]  {r.stderr.strip()}", file=sys.stderr)
    return 1


def _verify_files() -> int:
    """Синтаксический минимум: все файлы существуют и не пусты."""
    print("\n[verify] Файлы на диске")
    required = [
        "build/orbit-calc.spec",
        "build/build_all.sh",
        "build/docker-compose.yml",
        "build/Dockerfile.linux",
        "build/Dockerfile.windows",
        "build/wine-entrypoint.sh",
        "build/requirements-build.txt",
        "cli/calculator.py",
        "core/__init__.py",
        "core/base.py",
        "core/astrodynamics.py",
        "core/lambert.py",
        "core/latex_formulas.py",
        "gui/__init__.py",
        "gui/animations.py",
        "gui/plots.py",
    ]
    missing = []
    for rel in required:
        p = ROOT / rel
        if not p.is_file():
            print(f"  [err] {rel} — ОТСУТСТВУЕТ")
            missing.append(rel)
        elif p.stat().st_size == 0:
            print(f"  [err] {rel} — пустой")
            missing.append(rel)
        else:
            print(f"  [ok]  {rel} ({p.stat().st_size} б)")
    return 0 if not missing else 2


def main() -> int:
    print("[patch v5.1] SPECPATH fix + Docker-файлы")
    print("=" * 50)

    rc = _patch_spec()
    if rc != 0:
        return rc

    _create_files()

    rc = _verify_spec_logic()
    if rc != 0:
        return rc

    rc = _verify_files()
    if rc != 0:
        return rc

    print("\n" + "=" * 50)
    print("[patch v5.1] Готово. Проверьте:")
    print("  python3 build/gui_builder.py                       # pre-flight теперь OK")
    print("  bash build/build_all.sh                            # локальная Linux-сборка")
    print("  ls -la build/dist/orbit-calc")
    print()
    print("Docker не установлен — Windows-сборка недоступна.")
    print("Для неё: sudo apt install docker.io docker-compose-plugin")
    print("        sudo usermod -aG docker $USER  # перелогиниться")
    return 0


if __name__ == "__main__":
    sys.exit(main())