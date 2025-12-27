import math
import pathlib
import sys

sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))


def rescale_complexity(raw):
    """Raw 0–20 → rescaled 1–5 (divide by 4)."""
    return round(raw / 4, 2)


def test_low_complexity():
    assert math.isclose(rescale_complexity(5), 1.25, rel_tol=1e-6)


def test_mid_complexity():
    assert math.isclose(rescale_complexity(10), 2.5, rel_tol=1e-6)


def test_high_complexity():
    assert math.isclose(rescale_complexity(20), 5.0, rel_tol=1e-6)
