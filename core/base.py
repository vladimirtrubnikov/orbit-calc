"""core/base.py — константы и базовые функции orbit-calc.

Единственный источник MU_EARTH, R_EARTH, G0 для всего проекта.
"""

from __future__ import annotations

import logging
import math
import sys

# ── Константы ──────────────────────────────────────────────────────────────
MU_EARTH = 398_600.4418      # км³/с²
R_EARTH = 6_378.0            # км (экваториальный радиус)
G0 = 9.80665                 # м/с²

LANG = "ru"

logger = logging.getLogger("orbit_calc")


# ── Локализация (минимальный словарь) ─────────────────────────────────────
_TRANSLATIONS = {
    "ru": {
        "menu_title": "Универсальный калькулятор орбитальных расчётов",
        "menu_1": "Параметры орбиты (Ap/Pe)",
        "menu_2": "Скорость в точке орбиты",
        "menu_3": "Круговая орбита",
        "menu_4": "Перелёт Хомана",
        "menu_5": "Биэллиптический перелёт",
        "menu_6": "Циолковский: dv → топливо",
        "menu_7": "Обратный Циолковский: топливо → dv",
        "menu_8": "Скорость убегания",
        "menu_9": "Анимация Хомана",
        "menu_10": "Анимация фазирования",
        "menu_11": "Сменить язык (ru/en)",
        "menu_0": "Выход",
        "menu_choice": "Выбор: ",
        "menu_no_plot": "(matplotlib не установлен — графики недоступны)",
        "hdr_orbit_params": "ПАРАМЕТРЫ ОРБИТЫ",
        "hdr_velocity": "СКОРОСТЬ В ТОЧКЕ",
        "hdr_circular": "КРУГОВАЯ ОРБИТА",
        "hdr_hohmann": "ПЕРЕЛЁТ ХОМАНА",
        "hdr_bielliptic": "БИЭЛЛИПТИЧЕСКИЙ ПЕРЕЛЁТ",
        "hdr_escape": "СКОРОСТЬ УБЕГАНИЯ",
        "hdr_anim_hohmann": "АНИМАЦИЯ ХОМАНА",
        "hdr_anim_phasing": "АНИМАЦИЯ ФАЗИРОВАНИЯ",
        "prompt_ap": "  Апогей (Ap), км: ",
        "prompt_pe": "  Перигей (Pe), км: ",
        "prompt_alt": "  Высота, км: ",
        "prompt_h1": "  Высота орбиты 1, км: ",
        "prompt_h2": "  Высота орбиты 2, км: ",
        "prompt_mass": "  Масса, кг: ",
        "prompt_isp": "  Isp, с: ",
        "prompt_fuel": "  Топливо, кг: ",
        "prompt_h": "  Высота, км: ",
        "prompt_phase": "  Фазовый угол, °: ",
        "prompt_nrev": "  Число витков: ",
        "prompt_plot": "Построить график? (y/n): ",
        "msg_neg_alt": "Высота не может быть отрицательной",
        "msg_same_orbits": "Орбиты совпадают",
        "msg_invalid_nrev": "Некорректное число витков",
        "msg_enter_0_11": "Введите 0..12",
        "msg_lang_changed": "Язык изменён",
        "log_calc_started": "Расчёт запущен",
        "log_neg_altitude": "Отрицательная высота",
        "log_invalid_params": "Некорректные параметры",
        "log_radius_below_earth": "Радиус ниже поверхности Земли",
        "log_point_outside_orbit": "Точка вне орбиты",
        "log_intermediate_too_low": "Промежуточная высота слишком мала",
        "log_mass_positive": "Масса должна быть > 0",
        "log_isp_positive": "Isp должен быть > 0",
        "log_fuel_negative": "Топливо не может быть отрицательным",
        "log_fuel_ge_mass": "Топливо ≥ массы",
        "log_fuel_exceeds_mass": "Топливо превышает массу",
        "log_phasing_impossible": "Фазирование невозможно",
    },
    "en": {},
}
# Заполняем английский как копию ключей (fallback на ключ)
for _k in _TRANSLATIONS["ru"]:
    if _k not in _TRANSLATIONS["en"]:
        _TRANSLATIONS["en"][_k] = _k


def _t(key: str) -> str:
    """Локализованная строка. Неизвестный ключ — возвращается как есть."""
    return _TRANSLATIONS.get(LANG, {}).get(key, key)


def set_lang(lang: str) -> None:
    """Переключение языка: 'ru' или 'en'."""
    global LANG
    if lang in ("ru", "en"):
        LANG = lang
    else:
        logger.warning(f"Неизвестный язык: {lang!r}, оставлен {LANG}")


def setup_logging(verbose: bool = False) -> None:
    """Настройка logging."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(levelname)-8s %(name)s: %(message)s",
        stream=sys.stderr,
    )


# ── Ввод ──────────────────────────────────────────────────────────────────
def rf(prompt: str = "") -> float:
    """Чтение float с повторами при ошибке."""
    while True:
        raw = input(prompt).strip().replace(",", ".")
        if not raw:
            continue
        try:
            return float(raw)
        except ValueError:
            print(f"  Не число: {raw!r}, повторите", file=sys.stderr)


def ri(prompt: str = "") -> int:
    """Чтение int с повторами."""
    while True:
        raw = input(prompt).strip()
        if not raw:
            continue
        try:
            return int(raw)
        except ValueError:
            print(f"  Не целое: {raw!r}, повторите", file=sys.stderr)


# ── Орбитальные хелперы ──────────────────────────────────────────────────
def check_orbit(ap: float, pe: float) -> tuple[bool, str]:
    """Проверка Ap/Pe. Возвращает (ok, message)."""
    if not isinstance(ap, (int, float)) or not isinstance(pe, (int, float)):
        return False, "Ap/Pe должны быть числами"
    if ap < 0 or pe < 0:
        return False, "Высоты должны быть ≥ 0"
    if ap < pe:
        return False, f"Ap ({ap:.1f}) < Pe ({pe:.1f}) — орбита невозможна"
    return True, ""


def sma(ap: float, pe: float) -> float:
    """Большая полуось по Ap/Pe."""
    return (ap + pe) / 2 + R_EARTH


def ecc(ap: float, pe: float) -> float:
    """Эксцентриситет по Ap/Pe."""
    r_p = pe + R_EARTH
    r_a = ap + R_EARTH
    return (r_a - r_p) / (r_a + r_p)


def period(ap: float, pe: float) -> float:
    """Период по Ap/Pe, секунды."""
    a = sma(ap, pe)
    return 2 * math.pi * math.sqrt(a ** 3 / MU_EARTH)


def vel_at(ap: float, pe: float, which: str = "perigee") -> float:
    """Скорость в перигее или апогее, км/с."""
    a = sma(ap, pe)
    if which == "perigee":
        r = pe + R_EARTH
    elif which == "apogee":
        r = ap + R_EARTH
    else:
        raise ValueError(f"which ∈ {{perigee, apogee}}, не {which!r}")
    return math.sqrt(MU_EARTH * (2 / r - 1 / a))
