import pytest

from brewtrace.models import BrewMethod
from brewtrace.tools.brew_math import assess_drawdown, assess_ratio, compute_ratio


def test_compute_ratio():
    assert compute_ratio(16, 250) == 15.62


def test_assess_ratio_typical():
    assert assess_ratio(15.62) == "typical"


def test_assess_ratio_low_is_strong():
    assert assess_ratio(13.0) == "low"


def test_assess_ratio_high_is_dilute():
    assert assess_ratio(18.0) == "high"


@pytest.mark.parametrize(
    ("seconds", "expected"),
    [
        (120, "fast"),
        (150, "in_range"),
        (225, "in_range"),  # the canonical 3:45 case: slow-ish but normal
        (270, "slow"),
        (301, "stalled"),
        (330, "stalled"),
    ],
)
def test_assess_drawdown_v60(seconds, expected):
    assert assess_drawdown(seconds, BrewMethod.V60) == expected


def test_assess_drawdown_kalita_window_differs():
    assert assess_drawdown(170, BrewMethod.KALITA) == "fast"
    assert assess_drawdown(170, BrewMethod.V60) == "in_range"


def test_assess_drawdown_clever():
    assert assess_drawdown(90, BrewMethod.CLEVER) == "in_range"
