"""tests/test_gui_units.py — единицы T/Δt по case (v7.5)."""
import pytest
from gui.case_meta_ext import unit_for, to_seconds


@pytest.mark.parametrize("key,sid,label,mult", [
    ("T",  "8",  "с",   1.0),
    ("T",  "14", "с",   1.0),
    ("T",  "19", "мин", 60.0),
    ("T",  "20", "мин", 60.0),
    ("T1", "43", "мин", 60.0),
    ("T2", "43", "мин", 60.0),
    ("dt", "27", "ч",   3600.0),
    ("dt", "54", "ч",   3600.0),
])
def test_unit_by_case(key, sid, label, mult):
    u, m = unit_for(key, sid)
    assert u == label, f"{key}/{sid}: ожидалось {label!r}, получено {u!r}"
    assert abs(m - mult) < 1e-9, f"{key}/{sid}: mult={m}, ожидалось {mult}"
    assert abs(to_seconds(key, sid, 1.0) - mult) < 1e-9


def test_default_seconds():
    u, m = unit_for("unknown_key", "1")
    assert u == "с" and m == 1.0
