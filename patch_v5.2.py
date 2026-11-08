#!/usr/bin/env python3
"""patch_v5.2.py — фикс Windows-сборки через Docker.

1. build/docker-compose.yml: добавить :z к volumes (SELinux)
2. Создать build/setup_docker.sh — диагностика и авто-фикс
3. Создать build/README_docker.md — справка

Идемпотентен. Резервные копии: *.v5.2.bak
"""

from __future__ import annotations

import shutil
import stat
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
COMPOSE = ROOT / "build" / "docker-compose.yml"


# ── 1. compose с :z ────────────────────────────────────────────────────────
COMPOSE_TEXT = '''services:
  linux-builder:
    build:
      context: ..
      dockerfile: build/Dockerfile.linux
    working_dir: /src
    volumes:
      - ..:/src:z
    environment:
      ORBIT_LITE: "${ORBIT_LITE:-0}"
    entrypoint: ["bash", "/src/build/build_all.sh"]

  windows-builder:
    build:
      context: ..
      dockerfile: build/Dockerfile.windows
    working_dir: /src
    volumes:
      - ..:/src:z
      - wine-cache:/wine:z
    environment:
      ORBIT_LITE: "${ORBIT_LITE:-0}"
    entrypoint: ["bash", "/src/build/wine-entrypoint.sh"]

volumes:
  wine-cache:
'''


# ── 2. setup_docker.sh ─────────────────────────────────────────────────────
SETUP_DOCKER = '''#!/usr/bin/env bash
# setup_docker.sh — диагностика и авто-фикс доступа к Docker.
#
# Проверяет:
#   1. Установлен ли docker
#   2. Snap или native
#   3. Запущен ли daemon
#   4. В группе ли docker текущий пользователь
#   5. Доступен ли /var/run/docker.sock
#
# Ничего не меняет без подтверждения (кроме --fix).
set -uo pipefail

RED='\\033[31m'; YEL='\\033[33m'; GRN='\\033[32m'; CYA='\\033[36m'; RST='\\033[0m'

ok()   { echo -e "  ${GRN}✓${RST} $*"; }
warn() { echo -e "  ${YEL}!${RST} $*"; }
err()  { echo -e "  ${RED}✗${RST} $*"; }
info() { echo -e "  ${CYA}→${RST} $*"; }

FIX=0
[ "${1:-}" = "--fix" ] && FIX=1

echo "=== Docker diagnostic ==="
echo

# 1. Установлен?
if ! command -v docker >/dev/null 2>&1; then
    err "docker не установлен"
    echo
    echo "Установите:"
    echo "  sudo apt update && sudo apt install docker.io docker-compose-plugin"
    exit 1
fi
DOCKER_BIN=$(command -v docker)
ok "docker: $DOCKER_BIN"

# 2. Snap или native?
if [[ "$DOCKER_BIN" == /snap/* ]] || snap list 2>/dev/null | grep -q "^docker"; then
    warn "Docker установлен через SNAP"
    info "Snap Docker хуже работает с SELinux и volume-монтированием"
    info "Рекомендую перейти на native: sudo snap remove docker && sudo apt install docker.io"
    IS_SNAP=1
else
    ok "Docker установлен нативно (не snap)"
    IS_SNAP=0
fi

# 3. Daemon запущен?
if ! systemctl is-active --quiet docker 2>/dev/null; then
    if ! pgrep -x dockerd >/dev/null 2>&1; then
        err "docker daemon не запущен"
        if [ "$FIX" = "1" ]; then
            info "Запускаю: sudo systemctl start docker"
            sudo systemctl start docker
            sleep 2
            systemctl is-active --quiet docker && ok "daemon запущен" || err "не удалось"
        else
            info "Запустите: sudo systemctl start docker"
        fi
    fi
else
    ok "daemon запущен"
fi

# 4. Группа docker
if id -nG "$USER" | grep -qw docker; then
    ok "пользователь $USER в группе docker"
else
    err "пользователь $USER НЕ в группе docker"
    if [ "$FIX" = "1" ]; then
        info "Добавляю: sudo usermod -aG docker $USER"
        sudo usermod -aG docker "$USER"
        warn "Требуется перелогиниться или выполнить: newgrp docker"
    else
        info "Исправьте: sudo usermod -aG docker $USER && newgrp docker"
    fi
fi

# 5. Доступ к socket
if [ -S /var/run/docker.sock ]; then
    if [ -r /var/run/docker.sock ] && [ -w /var/run/docker.sock ]; then
        ok "/var/run/docker.sock доступен"
    else
        err "/var/run/docker.sock — нет прав"
        PERMS=$(stat -c "%a %U:%G" /var/run/docker.sock 2>/dev/null)
        info "Права: $PERMS"
        info "Лечится добавлением в группу docker (см. пункт 4)"
    fi
else
    warn "/var/run/docker.sock отсутствует (daemon не запущен?)"
fi

# 6. SELinux
if command -v getenforce >/dev/null 2>&1; then
    ENFORCE=$(getenforce 2>/dev/null || echo "?")
    info "SELinux: $ENFORCE"
    if [ "$ENFORCE" = "Enforcing" ]; then
        warn "SELinux enforcing — volume mounts требуют флаг :z"
        info "В docker-compose.yml уже добавлено :z (patch v5.2)"
        if ! command -v matchpathcon >/dev/null 2>&1; then
            info "Для silence warning установите: sudo apt install policycoreutils"
        fi
    fi
fi

# 7. Финальная проверка
echo
echo "=== Проверка ==="
if docker info >/dev/null 2>&1; then
    ok "docker info работает — всё готово"
    info "Запустите Windows-сборку:"
    info "  docker compose -f build/docker-compose.yml run --rm windows-builder"
    exit 0
else
    err "docker info НЕ работает"
    if [ "$FIX" = "0" ]; then
        info "Попробуйте: bash build/setup_docker.sh --fix"
    fi
    exit 2
fi
'''


# ── 3. README_docker.md ────────────────────────────────────────────────────
README = '''# Docker для Windows-сборки

Linux-сборка работает без Docker (`./build/build_all.sh`).
Docker нужен только для `.exe`-бинарника (через Wine).

## Быстрый фикс

```bash
# 1. Диагностика
bash build/setup_docker.sh

# 2. Авто-фикс (запуск daemon + добавление в группу)
bash build/setup_docker.sh --fix

# 3. Перелогиниться (или newgrp в текущей сессии)
newgrp docker

# 4. Проверка
docker info