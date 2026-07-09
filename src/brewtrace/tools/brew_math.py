"""Brew arithmetic: ratio and drawdown assessment.

Pure functions on top; thin @tool wrappers for the agent at the bottom.
"""

from __future__ import annotations

from typing import Literal

from strands import tool

from brewtrace.models import BrewMethod

# Acceptable drawdown windows in seconds. Clever is post-release drainage
# (steep time excluded) — drawdown is less diagnostic for immersion hybrids.
DRAWDOWN_TARGETS_S: dict[BrewMethod, tuple[int, int]] = {
    BrewMethod.V60: (150, 240),
    BrewMethod.KALITA: (180, 270),
    BrewMethod.CLEVER: (60, 120),
}

RATIO_RANGE = (15.0, 17.0)
STALL_MARGIN_S = 60


def compute_ratio(dose_g: float, water_g: float) -> float:
    return round(water_g / dose_g, 2)


def assess_ratio(ratio: float) -> Literal["low", "typical", "high"]:
    """low = strong end (< 1:15), high = dilute end (> 1:17)."""
    if ratio < RATIO_RANGE[0]:
        return "low"
    if ratio > RATIO_RANGE[1]:
        return "high"
    return "typical"


def assess_drawdown(
    drawdown_s: int, method: BrewMethod
) -> Literal["fast", "in_range", "slow", "stalled"]:
    low, high = DRAWDOWN_TARGETS_S[method]
    if drawdown_s < low:
        return "fast"
    if drawdown_s <= high:
        return "in_range"
    if drawdown_s <= high + STALL_MARGIN_S:
        return "slow"
    return "stalled"


@tool
def calculate_brew_ratio(dose_g: float, water_g: float) -> dict:
    """Calculate the coffee-to-water brew ratio and assess it against pour-over norms.

    Args:
        dose_g: Coffee dose in grams
        water_g: Brew water in grams
    """
    ratio = compute_ratio(dose_g, water_g)
    return {
        "ratio": ratio,
        "ratio_label": f"1:{ratio}",
        "assessment": assess_ratio(ratio),
        "typical_range": "1:15 to 1:17 for pour-over",
    }


@tool
def assess_drawdown_time(drawdown_s: int, method: str) -> dict:
    """Assess whether a pour-over drawdown time is fast, in range, slow, or stalled.

    Args:
        drawdown_s: Drawdown time in seconds
        method: Brew method, one of: v60, kalita, clever
    """
    brew_method = BrewMethod(method.lower())
    low, high = DRAWDOWN_TARGETS_S[brew_method]
    return {
        "assessment": assess_drawdown(drawdown_s, brew_method),
        "target_range_s": [low, high],
        "note": f"{brew_method.value} target is {low}-{high}s; "
        f"more than {high + STALL_MARGIN_S}s counts as stalled",
    }
