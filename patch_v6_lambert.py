#!/usr/bin/env python3
"""patch_v6_lambert.py — добавляет мультивитковый Ламберт (case 54).

Идемпотентен. Резервные копии: *.v6.bak
"""
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parent

LAMBERT = ROOT / "core" / "lambert.py"
ASTRO = ROOT / "core" / "astrodynamics.py"
CALC = ROOT / "cli" / "calculator.py"
LATEX = ROOT / "core" / "latex_formulas.py"
TESTS = ROOT / "tests" / "test_lambert_nrev.py"

LAMBERT_BLOCK = open(ROOT / "_lambert_v6_block.py", encoding="utf-8").read() if (ROOT / "_lambert_v6_block.py").is_file() else ""


def patch(path, old, new, name, required=True):
    if not path.is_file():
        print(f"[err] {path} не найден")
        return False
    text = path.read_text(encoding="utf-8")
    if new in text:
        print(f"[skip] {name}")
        return True
    if old not in text:
        if required:
            print(f"[err] {name}: якорь не найден")
            return False
        print(f"[skip] {name}: якорь не найден (не критично)")
        return True
    bak = path.with_suffix(path.suffix + ".v6.bak")
    if not bak.exists():
        shutil.copy2(path, bak)
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"[ok]   {name}")
    return True


def main():
    print("[patch v6] Мультивитковый Ламберт")
    print("=" * 50)
    ok = True

    # 1. core/lambert.py: append N-rev block
    if LAMBERT_BLOCK:
        text = LAMBERT.read_text(encoding="utf-8")
        if "_solve_band_v6" not in text and "lambert_universal_nrev" not in text:
            bak = LAMBERT.with_suffix(".py.v6.bak")
            if not bak.exists():
                shutil.copy2(LAMBERT, bak)
            LAMBERT.write_text(text.rstrip() + "\n\n" + LAMBERT_BLOCK, encoding="utf-8")
            print("[ok]   core/lambert.py: +N-rev block")
        else:
            print("[skip] core/lambert.py: N-rev уже есть")
    else:
        print("[err] _lambert_v6_block.py не найден — сохраните блок из ответа")
        ok = False

    # 2. core/astrodynamics.py
    ok &= patch(ASTRO,
        "from core.lambert import lambert_universal",
        "from core.lambert import lambert_universal, lambert_universal_nrev",
        "astrodynamics: import")

    ok &= patch(ASTRO,
        '    "53": {"name": "Frozen", "inputs": ["H", "e", "i"]},\n}',
        '    "53": {"name": "Frozen", "inputs": ["H", "e", "i"]},\n'
        '    "54": {"name": "Ламберт N витков", "inputs": ["H1", "H2", "dnu_deg", "dt", "n_max"]},\n}',
        "astrodynamics: CASE_META")

    ok &= patch(ASTRO,
        'def _s53(H, e, i): return frozen_orbit_info(H + R_EARTH, e, i)',
        'def _s53(H, e, i): return frozen_orbit_info(H + R_EARTH, e, i)\n\n\n'
        'def _s54(H1, H2, dnu_deg, dt, n_max=5):\n'
        '    r1, r2 = H1 + R_EARTH, H2 + R_EARTH\n'
        '    dnu = math.radians(dnu_deg)\n'
        '    sols = lambert_universal_nrev(r1, r2, dnu, dt, n_max=int(n_max))\n'
        '    if not sols:\n'
        '        raise ValueError("Нет решений для данных параметров")\n'
        '    for s in sols:\n'
        '        s["v1_vec"] = list(s["v1_vec"])\n'
        '        s["v2_vec"] = list(s["v2_vec"])\n'
        '    return {"solutions": sols, "n_found": len(sols),\n'
        '            "r1_km": r1, "r2_km": r2, "dnu_deg": dnu_deg, "dt_s": dt}',
        "astrodynamics: _s54")

    ok &= patch(ASTRO,
        '_SOLVERS = {str(i): globals()[f"_s{i}"] for i in range(1, 54)}',
        '_SOLVERS = {str(i): globals()[f"_s{i}"] for i in range(1, 55)}',
        "astrodynamics: _SOLVERS range")

    # 3. cli/calculator.py
    ok &= patch(CALC,
        '    "53": _solve_frozen_orbit,\n}',
        '    "53": _solve_frozen_orbit,\n    "54": _solve_lambert_nrev,\n}',
        "cli: _DISPATCH")

    ok &= patch(CALC,
        '        print(" 53. Замороженная орбита / критическое наклонение")',
        '        print(" 53. Замороженная орбита / критическое наклонение")\n'
        '        print(" 54. Ламберт N витков (multi-rev)")',
        "cli: menu")

    ok &= patch(CALC,
        'def _dispatch_solve(sid: str) -> None:',
        '_SOLVE_LAMBERT_NREV_SRC = """__PLACEHOLDER__"""\n\n'
        'def _dispatch_solve(sid: str) -> None:',
        "cli: _solve_lambert_nrev placeholder", required=False)

    # 4. latex_formulas.py
    ok &= patch(LATEX,
        '    ],\n}\n\ndef get_formulas',
        '    ],\n'
        '    "54": [\n'
        '        r"\\sqrt{\\mu}\\,\\Delta t = \\chi^3 S(z) + A\\sqrt{y(z)}",\n'
        '        r"y(z) = r_1 + r_2 + A\\,\\dfrac{z\\,S(z) - 1}{\\sqrt{C(z)}}",\n'
        '        r"z \\in \\left((2\\pi N)^2,\\; (2\\pi(N+1))^2\\right)\\ \\text{для}\\ N \\geq 1",\n'
        '    ],\n'
        '}\n\ndef get_formulas',
        "latex: 54", required=False)

    # 5. tests
    if not TESTS.is_file():
        print("[err] tests/test_lambert_nrev.py отсутствует — сохраните из ответа")
        ok = False
    else:
        print(f"[ok]   {TESTS.relative_to(ROOT)}")

    print("=" * 50)
    print("[patch v6] Готово" if ok else "[patch v6] Ошибки — см. выше")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())