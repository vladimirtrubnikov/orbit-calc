#!/usr/bin/env python3
"""patch_v10_github.py — GitHub Actions в GUI-сборщике.

Создаёт:
  build/github_actions.py       — логика (git, gh, workflow) + Qt dialog

Модифицирует:
  build/build_checks.py         — +_check_github, 3 проверки в pre-flight
  build/gui_builder.py          — кнопка 🐙 GitHub Actions + метод

Идемпотентен. Резервные копии: *.v10.bak
"""
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parent


# ═══════════════════════════════════════════════════════════════════
#  build/github_actions.py (полное содержимое)
# ═══════════════════════════════════════════════════════════════════

GH_ACTIONS_PY = '''"""build/github_actions.py — GitHub Actions integration for GUI builder.

Pure Python + optional PySide6 dialog (внутри run_dialog).
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path


WORKFLOW_TEMPLATE = """\\
name: Build Release

on:
  push:
    tags: ["v*"]
  workflow_dispatch:

permissions:
  contents: write

jobs:
  build:
    name: Build ${{ matrix.os }} ${{ matrix.variant }}
    runs-on: ${{ matrix.os }}
    strategy:
      fail-fast: false
      matrix:
        include:
          - {os: ubuntu-latest,  variant: cli, artifact: orbit-calc-linux-x86_64,           ext: ""}
          - {os: ubuntu-latest,  variant: gui, artifact: orbit-calc-gui-linux-x86_64,       ext: ""}
          - {os: windows-latest, variant: cli, artifact: orbit-calc-windows-x86_64.exe,     ext: ".exe"}
          - {os: windows-latest, variant: gui, artifact: orbit-calc-gui-windows-x86_64.exe, ext: ".exe"}
          - {os: macos-14,       variant: cli, artifact: orbit-calc-macos-arm64,             ext: ""}
          - {os: macos-14,       variant: gui, artifact: orbit-calc-gui-macos-arm64,         ext: ""}

    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: pip

      - name: Install dependencies
        shell: bash
        run: |
          python -m pip install --upgrade pip
          pip install pyinstaller pytest matplotlib numpy
          if [ "${{ matrix.variant }}" = "gui" ]; then
            pip install "PySide6>=6.5"
          fi

      - name: Run tests
        shell: bash
        run: python -m pytest tests/ -q

      - name: Build CLI
        if: matrix.variant == 'cli'
        shell: bash
        run: python -m PyInstaller --clean --noconfirm --distpath build/dist --workpath build/work build/orbit-calc.spec

      - name: Build GUI
        if: matrix.variant == 'gui'
        shell: bash
        run: python -m PyInstaller --clean --noconfirm --distpath build/dist --workpath build/work-gui build/orbit-calc-gui.spec

      - name: Rename artifact
        shell: bash
        run: |
          if [ "${{ matrix.variant }}" = "cli" ]; then
            SRC="build/dist/orbit-calc${{ matrix.ext }}"
          else
            SRC="build/dist/orbit-calc-gui${{ matrix.ext }}"
          fi
          DST="build/dist/${{ matrix.artifact }}"
          if [ -f "$SRC" ]; then
            mv "$SRC" "$DST"
          else
            echo "ERROR: $SRC not found"; ls -la build/dist/; exit 1
          fi
          ls -lh "$DST"

      - uses: actions/upload-artifact@v4
        with:
          name: ${{ matrix.artifact }}
          path: build/dist/${{ matrix.artifact }}
          retention-days: 30

  release:
    name: Create Release
    needs: build
    runs-on: ubuntu-latest
    if: startsWith(github.ref, 'refs/tags/v')
    steps:
      - uses: actions/download-artifact@v4
        with:
          path: artifacts

      - name: SHA256SUMS
        shell: bash
        run: |
          cd artifacts
          sha256sum */orbit-calc-* > SHA256SUMS.txt || true
          cat SHA256SUMS.txt

      - name: Create GitHub Release
        uses: softprops/action-gh-release@v2
        with:
          files: |
            artifacts/**/orbit-calc-*
            artifacts/SHA256SUMS.txt
          generate_release_notes: true
"""


@dataclass
class RepoInfo:
    ok: bool
    url: str = ""; owner: str = ""; name: str = ""
    branch: str = ""; commit: str = ""; tags: str = ""; error: str = ""


@dataclass
class GhInfo:
    installed: bool
    version: str = ""; authenticated: bool = False; error: str = ""


@dataclass
class WorkflowFile:
    exists: bool
    path: Path
    valid: bool = False
    jobs: list = field(default_factory=list)
    error: str = ""


@dataclass
class GitStatus:
    dirty: bool
    ahead: int; behind: int; untracked: int; modified: int
    error: str = ""


def detect_repo(root):
    try:
        r = subprocess.run(["git", "-C", str(root), "remote", "-v"],
                           capture_output=True, text=True, timeout=5)
        if r.returncode != 0 or "origin" not in r.stdout:
            return RepoInfo(ok=False, error="origin remote не найден")
        url = ""
        for line in r.stdout.strip().splitlines():
            if line.startswith("origin") and "(push)" in line:
                url = line.split()[1]; break
        m = re.search(r"github\\.com[:/]([^/]+)/([^/]+?)(?:\\.git)?$", url)
        if not m:
            return RepoInfo(ok=False, error=f"не GitHub URL: {url}")
        owner, name = m.group(1), m.group(2)
        b = subprocess.run(["git", "-C", str(root), "rev-parse", "--abbrev-ref", "HEAD"],
                           capture_output=True, text=True, timeout=5)
        branch = b.stdout.strip() if b.returncode == 0 else "main"
        c = subprocess.run(["git", "-C", str(root), "rev-parse", "--short", "HEAD"],
                           capture_output=True, text=True, timeout=5)
        commit = c.stdout.strip() if c.returncode == 0 else ""
        t = subprocess.run(["git", "-C", str(root), "describe", "--tags", "--abbrev=0"],
                           capture_output=True, text=True, timeout=5)
        tags = t.stdout.strip() if t.returncode == 0 else ""
        return RepoInfo(ok=True, url=url, owner=owner, name=name,
                        branch=branch, commit=commit, tags=tags)
    except Exception as exc:
        return RepoInfo(ok=False, error=str(exc))


def detect_gh():
    if not shutil.which("gh"):
        return GhInfo(installed=False, error="gh не установлен")
    try:
        v = subprocess.run(["gh", "--version"], capture_output=True, text=True, timeout=5)
        version = v.stdout.strip().splitlines()[0] if v.returncode == 0 else "?"
        s = subprocess.run(["gh", "auth", "status"], capture_output=True, text=True, timeout=5)
        auth_ok = s.returncode == 0
        err = "" if auth_ok else ((s.stderr or s.stdout) or "")[:200].strip()
        return GhInfo(installed=True, version=version, authenticated=auth_ok, error=err)
    except Exception as exc:
        return GhInfo(installed=True, error=str(exc))


def check_workflow(root):
    path = root / ".github" / "workflows" / "build-release.yml"
    if not path.is_file():
        return WorkflowFile(exists=False, path=path)
    try:
        text = path.read_text(encoding="utf-8")
        jobs = re.findall(r"^  (\\w+):\\s*$", text, re.MULTILINE)
        valid = all(k in text for k in ("name:", "on:", "jobs:"))
        return WorkflowFile(exists=True, path=path, valid=valid, jobs=jobs)
    except Exception as exc:
        return WorkflowFile(exists=True, path=path, error=str(exc))


def create_workflow(root, overwrite=False):
    path = root / ".github" / "workflows" / "build-release.yml"
    if path.exists() and not overwrite:
        return False, f"уже есть: {path}"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(WORKFLOW_TEMPLATE, encoding="utf-8")
    return True, str(path)


def check_git_status(root):
    try:
        r = subprocess.run(["git", "-C", str(root), "status", "--porcelain", "-b"],
                           capture_output=True, text=True, timeout=5)
        if r.returncode != 0:
            return GitStatus(dirty=False, ahead=0, behind=0, untracked=0, modified=0,
                             error=r.stderr.strip())
        ahead = behind = untracked = modified = 0
        for line in r.stdout.splitlines():
            if line.startswith("##"):
                m = re.search(r"ahead (\\d+)", line)
                if m: ahead = int(m.group(1))
                m = re.search(r"behind (\\d+)", line)
                if m: behind = int(m.group(1))
            elif line.startswith("??"):
                untracked += 1
            elif line[:2].strip():
                modified += 1
        return GitStatus(dirty=(modified > 0 or untracked > 0),
                         ahead=ahead, behind=behind,
                         untracked=untracked, modified=modified)
    except Exception as exc:
        return GitStatus(dirty=False, ahead=0, behind=0, untracked=0, modified=0, error=str(exc))


def validate_tag(tag):
    if not re.match(r"^v\\d+\\.\\d+\\.\\d+(-[A-Za-z0-9.-]+)?$", tag):
        return False, "формат: vX.Y.Z (например v0.9.0)"
    return True, ""


def push_and_tag(root, tag, message="", files=None):
    log = []
    def run(cmd, timeout=120):
        r = subprocess.run(cmd, capture_output=True, text=True, cwd=str(root), timeout=timeout)
        log.append(f"$ {' '.join(cmd)}")
        if r.stdout: log.append(r.stdout.rstrip())
        if r.stderr: log.append(r.stderr.rstrip())
        return r.returncode

    rc = run(["git", "add", *files]) if files else run(["git", "add", "-A"])
    if rc != 0:
        return rc, log

    s = subprocess.run(["git", "status", "--porcelain"],
                       capture_output=True, text=True, cwd=str(root))
    if s.stdout.strip():
        rc = run(["git", "commit", "-m", message or f"release: {tag}"])
        if rc != 0:
            return rc, log

    t = subprocess.run(["git", "tag", "-l", tag],
                       capture_output=True, text=True, cwd=str(root))
    if tag not in t.stdout.strip().splitlines():
        rc = run(["git", "tag", tag])
        if rc != 0:
            return rc, log

    return run(["git", "push", "origin", "HEAD", "--tags"]), log


def list_runs(owner, name, limit=5):
    try:
        r = subprocess.run(
            ["gh", "run", "list", "-R", f"{owner}/{name}", "-L", str(limit),
             "--json", "databaseId,status,conclusion,headBranch,event,createdAt,displayTitle,workflowName"],
            capture_output=True, text=True, timeout=15,
        )
        if r.returncode != 0:
            return []
        return json.loads(r.stdout)
    except Exception:
        return []


def download_latest(owner, name, dest):
    dest.mkdir(parents=True, exist_ok=True)
    try:
        r = subprocess.run(
            ["gh", "run", "download", "-R", f"{owner}/{name}", "--latest", "-D", str(dest)],
            capture_output=True, text=True, timeout=180,
        )
        if r.returncode != 0:
            return False, r.stderr.strip() or "download failed"
        return True, f"загружено в {dest}"
    except Exception as exc:
        return False, str(exc)


# ═══════════════════════════════════════════════════════════════════
#  Qt dialog
# ═══════════════════════════════════════════════════════════════════

def run_dialog(parent, root):
    """Показывает диалог GitHub Actions. Требует PySide6."""
    try:
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QColor, QDesktopServices, QFont, QTextCharFormat, QTextCursor
        from PySide6.QtWidgets import (
            QDialog, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel,
            QPushButton, QTextEdit, QInputDialog, QMessageBox,
        )
    except ImportError:
        print("PySide6 не установлен")
        return

    class GithubActionsDialog(QDialog):
        def __init__(self, parent, root):
            super().__init__(parent)
            self.setWindowTitle("🐙 GitHub Actions")
            self.resize(900, 700)
            self.root = root
            v = QVBoxLayout(self)

            sb = QGroupBox("Статус")
            sv = QVBoxLayout(sb)
            self.repo_lbl = QLabel("—"); self.gh_lbl = QLabel("—")
            self.wf_lbl = QLabel("—");   self.git_lbl = QLabel("—")
            for lbl in (self.repo_lbl, self.gh_lbl, self.wf_lbl, self.git_lbl):
                lbl.setStyleSheet("font-family: monospace; color: #c0c0c0;")
                sv.addWidget(lbl)
            v.addWidget(sb)

            ah = QHBoxLayout()
            for text, slot in [
                ("📝 Создать workflow", self.on_create),
                ("📤 Push & Tag", self.on_push),
                ("🔄 Check runs", self.on_check),
                ("⬇️ Download artifacts", self.on_download),
            ]:
                b = QPushButton(text); b.clicked.connect(slot); ah.addWidget(b)
            v.addLayout(ah)

            self.log = QTextEdit()
            self.log.setReadOnly(True)
            self.log.setFont(QFont("Monospace", 9))
            self.log.setStyleSheet("QTextEdit{background:#0f0f18;color:#d4d4d4;border:1px solid #2a2a3a;}")
            v.addWidget(self.log, 1)

            bh = QHBoxLayout()
            b = QPushButton("🌐 Открыть Actions"); b.clicked.connect(self.on_browser); bh.addWidget(b)
            bh.addStretch()
            c = QPushButton("Закрыть"); c.clicked.connect(self.accept); bh.addWidget(c)
            v.addLayout(bh)

            self.repo = self.gh = self.wf = None
            self.refresh()

        def refresh(self):
            self.repo = detect_repo(self.root)
            self.gh = detect_gh()
            self.wf = check_workflow(self.root)
            gs = check_git_status(self.root)

            self.repo_lbl.setText(
                f"✓ repo: {self.repo.owner}/{self.repo.name} ({self.repo.branch} @ {self.repo.commit})"
                if self.repo.ok else f"✗ repo: {self.repo.error}")

            if self.gh.installed and self.gh.authenticated:
                self.gh_lbl.setText(f"✓ gh: {self.gh.version}")
            elif self.gh.installed:
                self.gh_lbl.setText(f"⚠ gh: {self.gh.version} (gh auth login)")
            else:
                self.gh_lbl.setText("✗ gh не установлен (опционально)")

            self.wf_lbl.setText(
                f"✓ workflow: {self.wf.path.relative_to(self.root)}"
                if self.wf.exists else "✗ workflow: не найден")

            self.git_lbl.setText(
                f"⚠ git: modified={gs.modified}, untracked={gs.untracked}, ahead={gs.ahead}"
                if gs.dirty else f"✓ git: чисто (ahead={gs.ahead}, behind={gs.behind})")

        def logline(self, text, color="#d4d4d4"):
            cur = self.log.textCursor()
            cur.movePosition(QTextCursor.End)
            fmt = QTextCharFormat(); fmt.setForeground(QColor(color))
            cur.insertText(text + "\\n", fmt)
            self.log.setTextCursor(cur)
            self.log.ensureCursorVisible()

        def on_create(self):
            if self.wf.exists:
                if QMessageBox.question(self, "?", f"{self.wf.path} существует. Перезаписать?") != QMessageBox.Yes:
                    return
            ok, msg = create_workflow(self.root, overwrite=True)
            self.logline(("✓ " if ok else "✗ ") + msg, "#4ade80" if ok else "#ef4444")
            self.refresh()

        def on_push(self):
            if not self.repo.ok:
                self.logline("✗ нет GitHub repo", "#ef4444"); return
            tag, ok = QInputDialog.getText(self, "Tag", "Semver tag:", text="v0.9.0")
            if not ok: return
            valid, err = validate_tag(tag)
            if not valid:
                self.logline(f"✗ {err}", "#ef4444"); return
            msg, ok2 = QInputDialog.getText(self, "Commit message", "Сообщение:", text=f"release: {tag}")
            if not ok2: return
            if QMessageBox.question(self, "Push & Tag",
                    f"git add -A && commit && tag {tag} && push --tags\\nПродолжить?") != QMessageBox.Yes:
                return
            self.logline(f"\\n── Push & Tag {tag} ──", "#c084fc")
            rc, log = push_and_tag(self.root, tag, msg)
            for line in log:
                color = "#4ade80" if line.startswith("$") else "#d4d4d4"
                if "error" in line.lower() or "fatal" in line.lower():
                    color = "#ef4444"
                self.logline(line, color)
            if rc == 0:
                self.logline(f"✓ Actions запустятся на tag {tag}", "#4ade80")
                self.logline(f"  https://github.com/{self.repo.owner}/{self.repo.name}/releases", "#60a5fa")
            else:
                self.logline(f"✗ rc={rc}", "#ef4444")

        def on_check(self):
            if not (self.repo.ok and self.gh.installed and self.gh.authenticated):
                self.logline("✗ нужен gh + auth + git repo", "#ef4444"); return
            self.logline("\\n── Последние runs ──", "#c084fc")
            runs = list_runs(self.repo.owner, self.repo.name, limit=5)
            if not runs:
                self.logline("Нет runs или gh упал", "#fbbf24"); return
            for r in runs:
                concl = r.get("conclusion") or "—"
                color = "#4ade80" if concl == "success" else ("#ef4444" if concl == "failure" else "#fbbf24")
                self.logline(
                    f"  #{r['databaseId']} {r.get('workflowName','?')} [{r.get('event','?')}] "
                    f"status={r.get('status','?')} concl={concl}  {r.get('createdAt','')}", color)

        def on_download(self):
            if not (self.repo.ok and self.gh.installed and self.gh.authenticated):
                self.logline("✗ нужен gh + auth", "#ef4444"); return
            dest = self.root / "build" / "dist" / "gh"
            self.logline(f"\\n── Download → {dest} ──", "#c084fc")
            ok, msg = download_latest(self.repo.owner, self.repo.name, dest)
            self.logline(("✓ " if ok else "✗ ") + msg, "#4ade80" if ok else "#ef4444")

        def on_browser(self):
            if not self.repo.ok: return
            QDesktopServices.openUrl(QUrl(
                f"https://github.com/{self.repo.owner}/{self.repo.name}/actions"))

    GithubActionsDialog(parent, root).exec()
'''


# ═══════════════════════════════════════════════════════════════════
#  build_checks: _check_github
# ═══════════════════════════════════════════════════════════════════

CHECK_GITHUB = '''

def _check_github(root: Path) -> list[Check]:
    """GitHub repo / gh CLI / workflow file."""
    checks = []

    try:
        r = subprocess.run(["git", "-C", str(root), "remote", "get-url", "origin"],
                           capture_output=True, text=True, timeout=5)
        if r.returncode == 0 and "github.com" in r.stdout:
            checks.append(Check("git remote", "ok", r.stdout.strip()[:60], category="GitHub Actions"))
        else:
            checks.append(Check("git remote", "info", "нет origin",
                                hint="git remote add origin ...", category="GitHub Actions"))
    except Exception as exc:
        checks.append(Check("git remote", "info", str(exc)[:60], category="GitHub Actions"))

    if shutil.which("gh"):
        try:
            r = subprocess.run(["gh", "auth", "status"], capture_output=True, text=True, timeout=5)
            if r.returncode == 0:
                checks.append(Check("gh CLI", "ok", "авторизован", category="GitHub Actions"))
            else:
                checks.append(Check("gh CLI", "warn", "не авторизован",
                                    hint="gh auth login", category="GitHub Actions"))
        except Exception:
            checks.append(Check("gh CLI", "info", "?", category="GitHub Actions"))
    else:
        checks.append(Check("gh CLI", "info", "не установлен",
                            hint="apt install gh  https://cli.github.com",
                            category="GitHub Actions"))

    wf = root / ".github" / "workflows" / "build-release.yml"
    if wf.is_file():
        checks.append(Check("workflow", "ok", str(wf.relative_to(root)),
                            category="GitHub Actions"))
    else:
        checks.append(Check("workflow", "info", "нет → создайте в 🐙 GitHub Actions",
                            category="GitHub Actions"))

    return checks
'''


def _apply(path, old, new, name, required=True):
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
        print(f"  [info] {name}: пропущено")
        return True
    bak = path.with_suffix(path.suffix + ".v10.bak")
    if not bak.exists():
        shutil.copy2(path, bak)
   