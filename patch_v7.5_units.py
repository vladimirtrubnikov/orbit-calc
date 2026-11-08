#!/usr/bin/env python3
"""patch_v7.5_units.py — единицы T/Δt по конкретному case.

CLI читает T/Δt с разными единицами в разных case:
  case 8, 14:        T  [с]
  case 19, 20, 43:   T  [мин]
  case 27, 54:       Δt [ч]

GUI сейчас везде показывает [с] → пользователь введёт неверно.

Фикс:
  1. gui/input_form.py — использовать sid-aware единицы
  2. gui/case_meta_ext.py — UNITS_BY_CASE dict

Идемпотентен. Резервные копии: *.v7.5.bak
"""
from __future__ import annotations
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FORM = ROOT / "gui" / "input_form.py"
META = ROOT / "gui" / "case_meta_ext.py"


# ── 1. case_meta_ext.py — UNITS_BY_CASE ───────────────────────────────────
EXTRA_META = '''

# ─── v7.5: единицы T/Δt по конкретному case ────────────────────────────
# CLI читает T/Δt с разными единицами в разных case.
# (key, sid) → (unit, scale_to_seconds)
# scale: во сколько раз умножить введённое число, чтобы получить секунды.
#   с  → 1        мин → 60        ч → 3600
# runner.run_case получает уже введённое число, а input() в CLI вернёт "с",
# поэтому T читается как секунды. Чтобы пользователь не путался, пересчёт
# делаем в GUI ПЕРЕД вызовом run_case — тогда CLI всегда видит секунды.

UNITS_BY_CASE: dict[tuple[str, str], tuple[str, float]] = {
    # key, sid → (unit_label, multiplier_to_seconds)
    ("T", "8"):  ("с",   1.0),
    ("T", "14"): ("с",   1.0),
    ("T", "19"): ("мин", 60.0),
    ("T", "20"): ("мин", 60.0),
    ("T", "43"): ("мин", 60.0),
    ("T1", "43"): ("мин", 60.0),
    ("T2", "43"): ("мин", 60.0),
    ("dt", "27"): ("ч",  3600.0),
    ("dt", "54"): ("ч",  3600.0),
}


def unit_for(key: str, sid: str) -> tuple[str, float]:
    """Возвращает (unit_label, multiplier_to_seconds) для (key, sid)."""
    if (key, sid) in UNITS_BY_CASE:
        return UNITS_BY_CASE[(key, sid)]
    # Fallback — секунды, как в INPUT_META
    return ("с", 1.0)


def to_seconds(key: str, sid: str, value: float) -> float:
    """Переводит value в секунды согласно units_for(key, sid)."""
    _unit, mult = unit_for(key, sid)
    return float(value) * mult
'''


# ── 2. input_form.py — использовать unit_for + конвертация ────────────────
PATCH_IMPORT_OLD = "from .case_meta_ext import meta_for"
PATCH_IMPORT_NEW = "from .case_meta_ext import meta_for, unit_for, to_seconds"


PATCH_LOAD_OLD = '''        for key in meta["inputs"]:
            label, unit, typ, mn, mx, default = meta_for(key)
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
            if unit:
                u = QLabel(unit)
                u.setStyleSheet("color:#888; font-size:11px; min-width:40px;")
                row.addWidget(u)
            self._form_layout.addRow(label, row)
            self._fields[key] = edit'''

PATCH_LOAD_NEW = '''        for key in meta["inputs"]:
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
            self._fields[key] = edit'''

PATCH_VALUES_OLD = '''    def values(self) -> dict[str, float | str] | None:
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
                # Строковое значение (например, "system" = "1"/"2"/"3")
                out[key] = text
                edit.setStyleSheet(self._edit_style())
        return out if ok else None'''

PATCH_VALUES_NEW = '''    def values(self) -> dict[str, float | str] | None:
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
        return out if ok else None'''

PATCH_SAVE_OLD = '''    def _on_save(self) -> None:
        if not self._sid:
            return
        values = self.values()
        if values is None:
            return'''

PATCH_SAVE_NEW = '''    def _on_save(self) -> None:
        if not self._sid:
            return
        # Сохраняем то, что видит пользователь (без перевода в секунды)
        values = self.display_values()
        if values is None:
            return'''

# `_on_save` сейчас: `json.dumps(values)` и `self._saved_hint.setText("✓ Сохранено")`
# `values()` для сохранения → `display_values()` — достаточно.


# ── 3. app.py — summary показывает то же, что в истории ────────────────
# Не трогаем: _run_live использует form.values() для run_case,
# а summary выводит из res.output (уже в секундах/каноне).


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
    bak = path.with_suffix(path.suffix + ".v7.5.bak")
    if not bak.exists():
        shutil.copy2(path, bak)
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"  [ok]   {name}")
    return True


def main() -> int:
    print("[patch v7.5] Единицы T/Δt по case")
    print("=" * 60)

    # 1. Добавить UNITS_BY_CASE в case_meta_ext.py
    print(f"\n[1] {META}")
    if not META.is_file():
        print(f"  [err] не найден", file=sys.stderr)
        return 1
    text = META.read_text(encoding="utf-8")
    if "UNITS_BY_CASE" in text:
        print("  [skip] UNITS_BY_CASE уже есть")
    else:
        bak = META.with_suffix(".py.v7.5.bak")
        if not bak.exists():
            shutil.copy2(META, bak)
            print(f"  [backup] {bak}")
        META.write_text(text.rstrip() + "\n" + EXTRA_META, encoding="utf-8")
        print("  [ok] UNITS_BY_CASE, unit_for, to_seconds добавлены")

    # 2. input_form.py — import
    print(f"\n[2] {FORM}")
    if not FORM.is_file():
        print(f"  [err] не найден", file=sys.stderr)
        return 2

    ok = True
    ok &= _apply(FORM, PATCH_IMPORT_OLD, PATCH_IMPORT_NEW,
                 "import unit_for, to_seconds")
    ok &= _apply(FORM, PATCH_LOAD_OLD, PATCH_LOAD_NEW,
                 "load_case: unit по (key, sid)")
    ok &= _apply(FORM, PATCH_VALUES_OLD, PATCH_VALUES_NEW,
                 "values/display_values с переводом")
    ok &= _apply(FORM, PATCH_SAVE_OLD, PATCH_SAVE_NEW,
                 "_on_save через display_values")

    if not ok:
        print("\n[err] некоторые правки не применились", file=sys.stderr)
        return 3

    # 3. Синтаксис
    print("\n[3] Синтаксис")
    for p in (FORM, META):
        try:
            compile(p.read_text(encoding="utf-8"), str(p), "exec")
            print(f"  [ok] {p.name}")
        except SyntaxError as exc:
            print(f"  [err] {p.name}: {exc}", file=sys.stderr)
            return 4

    # 4. Проверка
    print("\n[4] Проверка")
    import subprocess
    code = (
        "import sys; sys.path.insert(0, '.'); "
        "from gui.case_meta_ext import unit_for, to_seconds; "
        # case 54, dt=1457 ч → 5245200 с
        "u, m = unit_for('dt', '54'); "
        "assert u == 'ч', u; "
        "assert abs(to_seconds('dt', '54', 1457) - 1457*3600) < 1; "
        # case 8, T=5400 с → 5400 с
        "u, m = unit_for('T', '8'); "
        "assert u == 'с', u; "
        "assert abs(to_seconds('T', '8', 5400) - 5400) < 1; "
        # case 19, T=90 мин → 5400 с
        "u, m = unit_for('T', '19'); "
        "assert u == 'мин', u; "
        "assert abs(to_seconds('T', '19', 90) - 5400) < 1; "
        "print('OK: единицы корректны')"
    )
    r = subprocess.run(
        [sys.executable, "-c", code], cwd=str(ROOT),
        capture_output=True, text=True,
        env={"QT_QPA_PLATFORM": "offscreen", "PATH": "/usr/bin:/bin"},
    )
    if r.returncode == 0:
        print(f"  [ok] {r.stdout.strip()}")
    else:
        print(f"  [err] {r.stderr.strip()}", file=sys.stderr)
        return 5

    print("\n" + "=" * 60)
    print("[patch v7.5] Готово. Проверьте:")
    print("  pytest tests/ -q                    # 170 passed")
    print("  python3 -m gui")
    print()
    print("В GUI проверьте единицы:")
    print("  case 8  (T круговая):       T [с]")
    print("  case 19 (T и H_p):          T [мин]")
    print("  case 20 (T и v_p):          T [мин]")
    print("  case 43 (синодический):     T1 [мин], T2 [мин]")
    print("  case 27 (Ламберт):          Δt [ч]")
    print("  case 54 (Ламберт N-rev):    Δt [ч]")
    return 0


if __name__ == "__main__":
    sys.exit(main())