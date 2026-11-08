"""gui/input_form.py — динамическая форма по CASE_META с save/reset."""
from __future__ import annotations

import json

from PySide6.QtCore import QSettings, QTimer, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel,
    QLineEdit, QFrame, QPushButton,
)
from core import astrodynamics as aero
from .case_meta_ext import meta_for, unit_for, to_seconds


def _settings() -> QSettings:
    return QSettings("orbit-calc", "gui")


def _saved_key(sid: str) -> str:
    return f"case_{sid}/inputs"


class InputForm(QWidget):
    changed = Signal()
    submit = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMaximumHeight(360)
        self._fields: dict[str, QLineEdit] = {}
        self._sid: str | None = None

        self._outer = QHBoxLayout(self)
        self._outer.setContentsMargins(0, 0, 0, 0)

        self._panel = QFrame()
        self._panel.setStyleSheet(
            "QFrame { background:#15151f; border-radius:8px; }"
        )
        panel_v = QVBoxLayout(self._panel)
        panel_v.setContentsMargins(12, 12, 12, 12)
        panel_v.setSpacing(6)

        self._title = QLabel("Выберите пункт слева")
        self._title.setStyleSheet(
            "color:#8b5cf6; font-size:13px; font-weight:bold;"
        )
        panel_v.addWidget(self._title)

        self._saved_hint = QLabel("")
        self._saved_hint.setStyleSheet(
            "color:#4ade80; font-size:10px; padding:0; margin-bottom:2px;"
        )
        panel_v.addWidget(self._saved_hint)

        self._form_wrap = QWidget()
        self._form_layout = QFormLayout(self._form_wrap)
        self._form_layout.setContentsMargins(0, 0, 0, 0)
        self._form_layout.setSpacing(8)
        panel_v.addWidget(self._form_wrap)

        # ── Кнопки Save/Reset ──
        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)

        self._save_btn = QPushButton("💾 Сохранить")
        self._save_btn.setToolTip(
            "Запомнить текущие значения полей для этого случая. "
            "Сохраняется между запусками."
        )
        self._save_btn.clicked.connect(self._on_save)
        self._save_btn.setStyleSheet(self._btn_style("#4ade80"))
        btn_row.addWidget(self._save_btn)

        self._reset_btn = QPushButton("🔄 Сбросить")
        self._reset_btn.setToolTip(
            "Вернуть значения по умолчанию и удалить сохранённые."
        )
        self._reset_btn.clicked.connect(self._on_reset)
        self._reset_btn.setStyleSheet(self._btn_style("#fbbf24"))
        btn_row.addWidget(self._reset_btn)

        self._zero_btn = QPushButton("⭕ Обнулить")
        self._zero_btn.setToolTip(
            "Установить все поля в 0. Сохранённые значения не трогаются."
        )
        self._zero_btn.clicked.connect(self._on_zero)
        self._zero_btn.setStyleSheet(self._btn_style("#94a3b8"))
        btn_row.addWidget(self._zero_btn)

        btn_row.addStretch(1)
        panel_v.addLayout(btn_row)

        self._outer.addWidget(self._panel, 1)

    def load_case(self, sid: str) -> None:
        # Очистить старые поля
        while self._form_layout.count():
            item = self._form_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
            else:
                lay = item.layout()
                if lay is not None:
                    while lay.count():
                        sub = lay.takeAt(0)
                        sw = sub.widget()
                        if sw is not None:
                            sw.deleteLater()
        self._fields.clear()
        self._sid = sid

        meta = aero.CASE_META.get(sid)
        if not meta:
            self._title.setText(f"Случай {sid}: неизвестен")
            self._saved_hint.setText("")
            return

        self._title.setText(f"{sid}. {meta['name']}")

        # Загружаем сохранённые значения, если есть
        saved = _settings().value(_saved_key(sid), "", type=str)
        saved_dict: dict = {}
        if saved:
            try:
                saved_dict = json.loads(saved)
            except (ValueError, TypeError):
                saved_dict = {}

        for key in meta["inputs"]:
            label, unit, typ, mn, mx, default = meta_for(key)
            # v7.5: единицы по конкретному (key, sid)
            unit_label, _mult = unit_for(key, sid)
            value = saved_dict.get(key, default)
            row = QHBoxLayout()
            edit = QLineEdit(str(value))
            edit.setPlaceholderText(
                f"{mn} … {mx}" if (mn is not None or mx is not None) else ""
            )
            edit.setStyleSheet(self._edit_style())
            edit.textChanged.connect(self._on_field_changed)
            edit.returnPressed.connect(self.submit.emit)
            row.addWidget(edit, 1)
            # Показываем sid-aware единицу, не INPUT_META
            if unit_label:
                u = QLabel(unit_label)
                u.setStyleSheet("color:#888; font-size:11px; min-width:40px;")
                row.addWidget(u)
            self._form_layout.addRow(label, row)
            self._fields[key] = edit

        self._saved_hint.setText(
            "✓ Используются сохранённые значения" if saved_dict else ""
        )

    # ─── Кнопки ─────────────────────────────────────────────
    def _on_save(self) -> None:
        if not self._sid:
            return
        # Сохраняем то, что видит пользователь (без перевода в секунды)
        values = self.display_values()
        if values is None:
            return
        s = _settings()
        s.setValue(_saved_key(self._sid),
                   json.dumps(values, ensure_ascii=False))
        s.sync()
        self._saved_hint.setText("✓ Сохранено")
        orig = self._save_btn.text()
        self._save_btn.setText("✓ Сохранено")
        QTimer.singleShot(1500, lambda: self._save_btn.setText(orig))

    def _on_reset(self) -> None:
        if not self._sid:
            return
        s = _settings()
        s.remove(_saved_key(self._sid))
        s.sync()

        meta = aero.CASE_META.get(self._sid)
        if not meta:
            return
        for key, edit in self._fields.items():
            _, _, _, _, _, default = meta_for(key)
            edit.setText(str(default))
        self._saved_hint.setText("")

    def _on_zero(self) -> None:
        """Устанавливает все поля в 0. Сохранённые значения не трогает."""
        if not self._sid:
            return
        for edit in self._fields.values():
            edit.setText("0")
        self._saved_hint.setText("")

    def _on_field_changed(self) -> None:
        if self._saved_hint.text():
            self._saved_hint.setText("")
        self.changed.emit()

    # ─── Значения ────────────────────────────────────────────
    def values(self) -> dict[str, float | str] | None:
        """Возвращает значения полей в СИ-совместимых единицах.

        Для T/Δt с единицей мин/ч — переводит в секунды (как CLI ожидает).
        Пользователь видит в поле «мин» или «ч», ввод — в этих единицах,
        но CLI получает секунды через to_seconds().
        """
        out: dict[str, float | str] = {}
        ok = True
        for key, edit in self._fields.items():
            text = edit.text().strip().replace(",", ".")
            if not text:
                edit.setStyleSheet(self._edit_style(error=True))
                ok = False
                continue
            try:
                raw = float(text)
                edit.setStyleSheet(self._edit_style())
                # v7.5: перевести в секунды (для T/Δt/…)
                if self._sid is not None:
                    out[key] = to_seconds(key, self._sid, raw)
                else:
                    out[key] = raw
            except ValueError:
                # Строковое значение (system = "1"/"2"/"3")
                out[key] = text
                edit.setStyleSheet(self._edit_style())
        return out if ok else None

    def display_values(self) -> dict[str, float | str] | None:
        """Значения как введены (без перевода в секунды).

        Для _on_zero/_on_reset/истории и prefill — чтобы QSettings и defaults
        хранились в тех же единицах, что видит пользователь.
        """
        out: dict[str, float | str] = {}
        ok = True
        for key, edit in self._fields.items():
            text = edit.text().strip().replace(",", ".")
            if not text:
                edit.setStyleSheet(self._edit_style(error=True))
                ok = False
                continue
            try:
                out[key] = float(text)
                edit.setStyleSheet(self._edit_style())
            except ValueError:
                out[key] = text
                edit.setStyleSheet(self._edit_style())
        return out if ok else None

    def set_values(self, values: dict[str, float | str]) -> None:
        for k, v in values.items():
            if k in self._fields:
                self._fields[k].setText(str(v))

    # ── Стили ──
    def _edit_style(self, error: bool = False) -> str:
        border = "#ef4444" if error else "#333"
        return (
            f"QLineEdit {{ background:#0f0f18; color:#e0e0e0; "
            f"border:1px solid {border}; border-radius:4px; "
            f"padding:5px 8px; font-family:monospace; font-size:12px; }}"
            f"QLineEdit:focus {{ border:1px solid #8b5cf6; }}"
        )

    def _btn_style(self, accent: str) -> str:
        return (
            f"QPushButton {{ background:#1a1a2e; color:{accent}; "
            f"border:1px solid {accent}; border-radius:4px; "
            f"padding:5px 12px; font-size:11px; font-weight:bold; }}"
            f"QPushButton:hover {{ background:{accent}22; }}"
            f"QPushButton:pressed {{ background:{accent}44; }}"
        )
