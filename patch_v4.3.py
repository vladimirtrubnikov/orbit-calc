#!/usr/bin/env python3
"""patch_v4.3.py — полное восстановление v4 поверх v3.5.

Причина: patch_v4 упал (rc=2) и не записал cli/calculator.py.
patch_v4.2 упал (rc=2) на _dispatch_solve — файл не был записан.
Итог: cli/calculator.py в состоянии v3.5, tests/test_v4.py создан.

Правки (устойчивы к частично применённым):
  1. _RESULT + _record + _set_kind
  2. _print_orbit_result: _set_kind + aero + _record
  3. _lambert_universal → делегатор в core.lambert
  4. verify-инфраструктура перед _dispatch_solve
  5. _dispatch_solve — v3 → v4.3 (учитывает v4-форму тоже)
  6. main(): _VERIFY_ENABLED + --json через _RESULT
  7. RECORD_PATCHES (11 прямых расчётов)

Идемпотентен. Резервная копия: cli/calculator.py.v4.3.bak
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

CALC = Path("cli/calculator.py")


# ═══════════════════════════════════════════════════════════════════════════
#  P1: _RESULT + _record + _set_kind
# ═══════════════════════════════════════════════════════════════════════════

P1_OLD = "_LAST_RESULT = None\n"
P1_NEW = '''_LAST_RESULT = None
_RESULT = {"case": None, "output": {}, "error": None, "kind": None}


def _record(**kwargs):
    """Записывает результаты в _RESULT для --json."""
    if _RESULT["output"] is None:
        _RESULT["output"] = {}
    for k, v in kwargs.items():
        if isinstance(v, (int, float)):
            _RESULT["output"][k] = round(float(v), 10)
        else:
            _RESULT["output"][k] = v


def _set_kind(kind):
    _RESULT["kind"] = kind
'''


# ═══════════════════════════════════════════════════════════════════════════
#  P2a: _print_orbit_result — _set_kind("orbit")
# ═══════════════════════════════════════════════════════════════════════════

P2A_OLD = '''def _print_orbit_result(a: float, e: float) -> None:
    """Печатает полный набор параметров эллиптической орбиты по (a, e)."""
    global _LAST_RESULT
    if a > 0 and 0 <= e < 1:'''

P2A_NEW = '''def _print_orbit_result(a: float, e: float) -> None:
    """Печатает полный набор параметров эллиптической орбиты по (a, e)."""
    global _LAST_RESULT
    _set_kind("orbit")
    if a > 0 and 0 <= e < 1:'''


# ═══════════════════════════════════════════════════════════════════════════
#  P2b: _print_orbit_result — формулы через aero
# ═══════════════════════════════════════════════════════════════════════════

P2B_OLD = """    r_p = a * (1 - e)
    r_a = a * (1 + e)
    p = a * (1 - e * e)
    h = math.sqrt(MU_EARTH * p)
    eps = -MU_EARTH / (2 * a)
    v_p = math.sqrt(MU_EARTH * (2 / r_p - 1 / a))
    v_a = math.sqrt(MU_EARTH * (2 / r_a - 1 / a))
    T = 2 * math.pi * math.sqrt(a ** 3 / MU_EARTH)
    v_cp = math.sqrt(MU_EARTH / r_p)
    v_ca = math.sqrt(MU_EARTH / r_a)"""

P2B_NEW = """    try:
        _el = aero.elements_from_a_e(a, e)
    except ValueError as exc:
        logger.warning(f"  {exc}")
        return
    r_p, r_a, p = _el["r_p"], _el["r_a"], _el["p"]
    h, eps, T = _el["h"], _el["eps"], _el["T"]
    v_p, v_a = _el["v_p"], _el["v_a"]
    v_cp = math.sqrt(MU_EARTH / r_p)
    v_ca = math.sqrt(MU_EARTH / r_a)"""


# ═══════════════════════════════════════════════════════════════════════════
#  P2c: _print_orbit_result — _record(...) в конце
# ═══════════════════════════════════════════════════════════════════════════

P2C_OLD = '''    print(f"  n  (ср. движение): {2 * math.pi / T:12.6f} рад/с")
    print()
    if _ask_plot():
        plot_orbit_params(r_a - R_EARTH, r_p - R_EARTH)'''

P2C_NEW = '''    print(f"  n  (ср. движение): {2 * math.pi / T:12.6f} рад/с")
    print()
    _record(a=a, e=e, r_p=r_p, r_a=r_a, p=p, h=h, eps=eps,
            T=T, v_p=v_p, v_a=v_a, n=2 * math.pi / T)
    if _ask_plot():
        plot_orbit_params(r_a - R_EARTH, r_p - R_EARTH)'''


# ═══════════════════════════════════════════════════════════════════════════
#  P3: _lambert_universal → делегатор
# ═══════════════════════════════════════════════════════════════════════════

P3_OLD = "def calc_orbit_params() -> None:"
P3_NEW = '''# ── v4.3: делегирование в core.lambert ──
def _lambert_universal(r1, r2, dnu, dt):
    """Обёртка (v4.3): делегирует в core.lambert.lambert_universal."""
    return aero.lambert_universal(r1, r2, dnu, dt)


def calc_orbit_params() -> None:'''


# ═══════════════════════════════════════════════════════════════════════════
#  P4: verify-инфраструктура
# ═══════════════════════════════════════════════════════════════════════════

P4_OLD = "def _dispatch_solve(sid: str) -> None:"
P4_NEW = '''# ── v4.3: shadow verify (--verbose) ──────────────────────────────────────
_VERIFY_CAPTURE = {"sid": None, "inputs": []}
_VERIFY_ENABLED = False
_SKIP_VERIFY = {"4", "8", "14", "19", "20", "27", "30", "41", "42", "48", "49"}


@contextlib.contextmanager
def _capture_rf():
    """Записывает rf() вызовы в _VERIFY_CAPTURE для сверки с aero."""
    mod = sys.modules[__name__]
    original = mod.rf
    _VERIFY_CAPTURE["inputs"] = []

    def recording_rf(prompt=""):
        v = original(prompt)
        _VERIFY_CAPTURE["inputs"].append(v)
        return v

    mod.rf = recording_rf
    try:
        yield
    finally:
        mod.rf = original


def _verify_against_core(sid: str) -> None:
    """Сверяет _RESULT с aero.solve_case в --verbose режиме."""
    if not _VERIFY_ENABLED:
        return
    if sid in _SKIP_VERIFY:
        return
    meta = aero.CASE_META.get(sid)
    if not meta:
        return
    inputs = _VERIFY_CAPTURE["inputs"]
    params = meta["inputs"]
    if len(inputs) != len(params):
        return
    kwargs = dict(zip(params, inputs))
    expected = aero.solve_case(sid, **kwargs)
    if "error" in expected:
        return
    for key in list(_RESULT["output"]):
        if key not in expected:
            continue
        exp = expected[key]
        got = _RESULT["output"][key]
        if isinstance(exp, (int, float)) and isinstance(got, (int, float)):
            tol = 1e-6 * max(abs(exp), 1.0)
            if abs(got - exp) > tol:
                logger.warning(
                    f"  verify {sid}: {key} got={got:.6g} exp={exp:.6g} "
                    f"Δ={abs(got - exp):.3e}"
                )


def _dispatch_solve(sid: str) -> None:'''


# ═══════════════════════════════════════════════════════════════════════════
#  P5: _dispatch_solve — v3 или v4 → v4.3
# ═══════════════════════════════════════════════════════════════════════════

P5_V3_OLD = '''def _dispatch_solve(sid: str) -> None:
    """Единая точка входа: LaTeX (если включён) + расчёт."""
    _print_latex(sid)
    _DISPATCH[sid]()'''

P5_V4_OLD = '''def _dispatch_solve(sid: str) -> None:
    """Единая точка: сброс _RESULT + LaTeX + расчёт + перехват ошибок."""
    global _RESULT
    _RESULT = {"case": sid, "output": {}, "error": None, "kind": None}
    _print_latex(sid)
    try:
        _DISPATCH[sid]()
    except SystemExit:
        raise
    except Exception as exc:
        _RESULT["error"] = f"{type(exc).__name__}: {exc}"
        raise'''

P5_NEW = '''def _dispatch_solve(sid: str) -> None:
    """Единая точка: сброс _RESULT + LaTeX + расчёт + verify."""
    global _RESULT
    _RESULT = {"case": sid, "output": {}, "error": None, "kind": None}
    _print_latex(sid)
    _VERIFY_CAPTURE["sid"] = sid
    try:
        if _VERIFY_ENABLED:
            with _capture_rf():
                _DISPATCH[sid]()
        else:
            _DISPATCH[sid]()
    except SystemExit:
        raise
    except Exception as exc:
        _RESULT["error"] = f"{type(exc).__name__}: {exc}"
        raise
    _verify_against_core(sid)'''


# ═══════════════════════════════════════════════════════════════════════════
#  P6: main — _VERIFY_ENABLED + --json через _RESULT
# ═══════════════════════════════════════════════════════════════════════════

P6A_OLD = "    global _SHOW_LATEX\n    _SHOW_LATEX = args.latex\n"
P6A_NEW = ("    global _SHOW_LATEX, _VERIFY_ENABLED\n"
           "    _SHOW_LATEX = args.latex\n"
           "    _VERIFY_ENABLED = args.verbose\n")

P6B_OLD = '''        if args.json and _LAST_RESULT is not None:
            print(json.dumps(_LAST_RESULT, indent=2, ensure_ascii=False))'''
P6B_NEW = '''        if args.json:
            payload = {k: v for k, v in _RESULT.items() if v not in (None, {}, [])}
            if not payload.get("output") and _LAST_RESULT:
                payload["output"] = _LAST_RESULT
            print(json.dumps(payload, indent=2, ensure_ascii=False))'''


# ═══════════════════════════════════════════════════════════════════════════
#  P7: RECORD_PATCHES — 11 прямых расчётов
# ═══════════════════════════════════════════════════════════════════════════

RECORD_PATCHES = [
    ("32",
     '    print(f"  Скорость: {v:.4f} км/с ({v * 1000:.1f} м/с)\\n")\n    if _ask_plot():\n        plot_velocity_point(ap, pe, r, v, name)',
     '    print(f"  Скорость: {v:.4f} км/с ({v * 1000:.1f} м/с)\\n")\n    _record(r_km=r, v_km_s=v, point=name)\n    if _ask_plot():\n        plot_velocity_point(ap, pe, r, v, name)'),
    ("33",
     '    print(f"  n:            {2 * math.pi / T:.6f} рад/с\\n")\n    if _ask_plot():\n        plot_circular(alt)',
     '    print(f"  n:            {2 * math.pi / T:.6f} рад/с\\n")\n    _record(r_km=r, v_km_s=v, T_s=T, n_rad_s=2 * math.pi / T)\n    if _ask_plot():\n        plot_circular(alt)'),
    ("34",
     '    print(f"  Промежуточная:      {max(h1, h2):.1f} × {min(h1, h2):.1f} км\\n")\n    if _ask_plot():\n        plot_hohmann(h1, h2, dv1, dv2)',
     '    print(f"  Промежуточная:      {max(h1, h2):.1f} × {min(h1, h2):.1f} км\\n")\n    _record(r1_km=r1, r2_km=r2, a_t_km=a_trans, dv1_mps=dv1, dv2_mps=dv2,\n            dv_total_mps=abs(dv1) + abs(dv2), t_transfer_s=t_trans)\n    if _ask_plot():\n        plot_hohmann(h1, h2, dv1, dv2)'),
    ("36",
     '        print(f"  Время работы:      {burn_time:.2f} с")\n    print()',
     '        print(f"  Время работы:      {burn_time:.2f} с")\n    _record(ve_mps=ve, m_fuel_kg=fuel, m_final_kg=mass - fuel, fuel_fraction=fuel / mass)\n    print()'),
    ("37",
     '    print(f"  dv:                {dv:.2f} м/с\\n")',
     '    print(f"  dv:                {dv:.2f} м/с\\n")\n    _record(ve_mps=ve, m_final_kg=mass - fuel, dv_mps=dv)'),
    ("43",
     '    print(f"  T_syn = {T_syn:.4f} с = {T_syn / 60:.4f} мин = {T_syn / 86400:.4f} сут\\n")',
     '    print(f"  T_syn = {T_syn:.4f} с = {T_syn / 60:.4f} мин = {T_syn / 86400:.4f} сут\\n")\n    _record(T_syn_s=T_syn, T1_s=T1, T2_s=T2)'),
    ("44",
     '    print(f"  Δv = {dv:.4f} км/с = {dv * 1000:.1f} м/с\\n")',
     '    print(f"  Δv = {dv:.4f} км/с = {dv * 1000:.1f} м/с\\n")\n    _record(v_km_s=v, dv_mps=dv * 1000, di_deg=di)'),
    ("45",
     '    print(f"\\n  ε = {elev:.4f}°,  d = {d:.3f} км\\n")',
     '    print(f"\\n  ε = {elev:.4f}°,  d = {d:.3f} км\\n")\n    _record(elev_deg=elev, range_km=d)'),
    ("47",
     "    print(f\"  Перигей за год: {r['domega_deg_year']:+.2f}°\\n\")",
     "    print(f\"  Перигей за год: {r['domega_deg_year']:+.2f}°\\n\")\n    _record(r)"),
    ("49",
     "    print(f\"  Шаг 7: m_fuel = {r['m_fuel_kg']:.1f} кг ({r['fuel_fraction']*100:.2f}%)\\n\")",
     "    print(f\"  Шаг 7: m_fuel = {r['m_fuel_kg']:.1f} кг ({r['fuel_fraction']*100:.2f}%)\\n\")\n    _record(r)"),
    ("50",
     '    print(f"\\n  Полезная нагрузка: {status}\\n")',
     '    print(f"\\n  Полезная нагрузка: {status}\\n")\n    _record(r)'),
    ("53",
     "    print(f\"  Замороженная (e<0.01 и i≈i_crit): {'да' if r['is_frozen_like'] else 'нет'}\\n\")",
     "    print(f\"  Замороженная (e<0.01 и i≈i_crit): {'да' if r['is_frozen_like'] else 'нет'}\\n\")\n    _record(r)"),
]


# ═══════════════════════════════════════════════════════════════════════════
#  Применение
# ═══════════════════════════════════════════════════════════════════════════


def _has(text: str, marker: str) -> bool:
    return marker in text


def _try_apply(text, old, new, name, *, required=False) -> tuple[str, bool]:
    """Возвращает (text, changed). Если old нет, но new уже есть — skip."""
    if new in text and old not in text:
        print(f"  [skip] {name}")
        return text, False
    if old not in text:
        if required:
            raise RuntimeError(f"Якорь не найден (обязателен) для {name}: {old[:80]!r}")
        print(f"  [skip] {name} — якорь отсутствует (уже применён или другая форма)")
        return text, False
    print(f"  [ok]   {name}")
    return text.replace(old, new, 1), True


def patch_calc() -> int:
    print(f"\n[1] {CALC}")
    if not CALC.is_file():
        print(f"  [err] не найден", file=sys.stderr)
        return 1

    text = CALC.read_text(encoding="utf-8")
    original = text

    # Быстрый выход: всё уже есть
    if (all(m in text for m in [
        "_VERIFY_CAPTURE", "_RESULT = ", "_record", "_set_kind",
        "aero.elements_from_a_e",
    ]) and "_VERIFY_CAPTURE[\"sid\"] = sid" in text):
        print("  [skip] v4.3 уже полностью применён")
        return 0

    backup = CALC.with_suffix(".py.v4.3.bak")
    if not backup.exists():
        shutil.copy2(CALC, backup)
        print(f"  [backup] {backup}")

    try:
        # P1
        text, _ = _try_apply(text, P1_OLD, P1_NEW, "P1 _RESULT/_record/_set_kind")

        # P2a, P2b, P2c
        text, _ = _try_apply(text, P2A_OLD, P2A_NEW, "P2a _print_orbit_result _set_kind")
        text, _ = _try_apply(text, P2B_OLD, P2B_NEW, "P2b _print_orbit_result → aero")
        text, _ = _try_apply(text, P2C_OLD, P2C_NEW, "P2c _print_orbit_result _record")

        # P3
        text, _ = _try_apply(text, P3_OLD, P3_NEW, "P3 _lambert_universal → делегатор")

        # P4 — только если ещё нет verify-инфраструктуры
        if "_VERIFY_CAPTURE" not in text:
            text, _ = _try_apply(text, P4_OLD, P4_NEW, "P4 verify-инфраструктура")
        else:
            print("  [skip] P4 verify-инфраструктура — уже есть")

        # P5 — _dispatch_solve: пробуем обе формы
        if "_VERIFY_CAPTURE[\"sid\"] = sid" in text:
            print("  [skip] P5 _dispatch_solve — уже v4.3")
        elif P5_V4_OLD in text:
            text = text.replace(P5_V4_OLD, P5_NEW, 1)
            print("  [ok]   P5 _dispatch_solve (v4 → v4.3)")
        elif P5_V3_OLD in text:
            text = text.replace(P5_V3_OLD, P5_NEW, 1)
            print("  [ok]   P5 _dispatch_solve (v3 → v4.3)")
        else:
            raise RuntimeError(
                "P5 _dispatch_solve не найден ни в v3, ни в v4 форме. "
                "Показываю первые 3 строки _dispatch_solve из файла:\n" +
                "\n".join(text.split("def _dispatch_solve")[1].splitlines()[:3])
            )

        # P6a, P6b
        text, _ = _try_apply(text, P6A_OLD, P6A_NEW, "P6a main _VERIFY_ENABLED")
        text, _ = _try_apply(text, P6B_OLD, P6B_NEW, "P6b main --json через _RESULT")

        # P7 — 11 прямых расчётов
        for sid, old, new in RECORD_PATCHES:
            try:
                text, _ = _try_apply(text, old, new, f"P7.{sid} _record")
            except RuntimeError as exc:
                print(f"  [warn] {exc}")

    except RuntimeError as exc:
        print(f"  [err] {exc}", file=sys.stderr)
        return 2

    # Синтаксис
    try:
        compile(text, str(CALC), "exec")
    except SyntaxError as exc:
        print(f"  [err] SyntaxError после правок: {exc}", file=sys.stderr)
        return 3

    CALC.write_text(text, encoding="utf-8")
    print(f"  [written] {len(text)} байт")
    return 0


def verify() -> int:
    print("\n[verify] импорт-проверка")
    import subprocess
    code = (
        "import sys; sys.path.insert(0, '.'); "
        "from core.astrodynamics import solve_case, _SOLVERS; "
        "assert len(_SOLVERS) == 53; "
        "from cli.calculator import (_RESULT, _record, _set_kind, "
        "_VERIFY_ENABLED, _VERIFY_CAPTURE, _lambert_universal, _dispatch_solve); "
        "import inspect; "
        "src = inspect.getsource(_dispatch_solve); "
        "assert '_VERIFY_CAPTURE' in src; "
        "src = inspect.getsource(_dispatch_solve); "
        "assert 'with _capture_rf' in src; "
        "r = solve_case('1', a=7000, e=0.1); "
        "assert 'error' not in r; "
        "print('OK: _RESULT, _record, _set_kind, _VERIFY_*, _dispatch_solve v4.3')"
    )
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    if r.returncode == 0:
        print(f"  [ok]   {r.stdout.strip()}")
        return 0
    print(f"  [err]  {r.stderr.strip()}", file=sys.stderr)
    return 4


def main() -> int:
    print("[patch v4.3] Полное восстановление v4 поверх v3.5")
    print("=" * 50)
    rc = patch_calc()
    if rc != 0:
        print("\n[patch v4.3] Правки не применены — файл не изменён", file=sys.stderr)
        return rc
    rc = verify()
    print("\n" + "=" * 50)
    if rc == 0:
        print("[patch v4.3] Готово. Проверьте:")
        print("  pytest tests/ -v                              # 40 passed")
        print("  python3 cli/calculator.py --solve=34 --json")
        print("  python3 cli/calculator.py --solve=1 --verbose  # shadow verify")
        print("  python3 cli/calculator.py --solve=47 --latex --json")
    return rc


if __name__ == "__main__":
    sys.exit(main())