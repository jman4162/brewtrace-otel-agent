"""Rule-based brew diagnosis and adjustment recommendation.

The rule table encodes standard pour-over troubleshooting: adjust the
highest-leverage extraction variable first (grind > temperature > ratio >
agitation/technique > bloom), one variable per brew, unless a guard
contraindicates it. Guards are what make this interesting to trace: sour +
stalled drawdown must NOT get "grind finer" even though sour alone would.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from strands import tool

from brewtrace.models import (
    Adjustment,
    BrewLog,
    Diagnosis,
    Direction,
    Recommendation,
    TasteDefect,
    Variable,
)
from brewtrace.tools.brew_math import assess_drawdown, assess_ratio

TEMP_CEILING_C = 96.0
TEMP_FLOOR_C = 88.0

Guard = Callable[[BrewLog, Diagnosis], str | None]
"""Returns a human-readable reason if the rule is contraindicated, else None."""


def _slow_drawdown(brew: BrewLog, diagnosis: Diagnosis) -> str | None:
    if diagnosis.drawdown in ("slow", "stalled"):
        return f"drawdown is already {diagnosis.drawdown}; grinding finer would make it worse"
    return None


def _temp_at_ceiling(brew: BrewLog, diagnosis: Diagnosis) -> str | None:
    if brew.temperature_c is not None and brew.temperature_c >= TEMP_CEILING_C:
        return f"water is already at {brew.temperature_c:g}°C (ceiling {TEMP_CEILING_C:g}°C)"
    return None


def _temp_at_floor(brew: BrewLog, diagnosis: Diagnosis) -> str | None:
    if brew.temperature_c is not None and brew.temperature_c <= TEMP_FLOOR_C:
        return f"water is already at {brew.temperature_c:g}°C (floor {TEMP_FLOOR_C:g}°C)"
    return None


@dataclass
class Rule:
    adjustment: Adjustment
    contraindicated: Guard | None = None


def _adj(variable: Variable, direction: Direction, magnitude: str, rationale: str) -> Adjustment:
    return Adjustment(
        variable=variable, direction=direction, magnitude=magnitude, rationale=rationale
    )


DEFECT_RULES: dict[TasteDefect, list[Rule]] = {
    TasteDefect.SOUR_THIN: [
        Rule(
            _adj(
                Variable.GRIND,
                Direction.FINER,
                "one grind step finer",
                "Sour and thin means underextraction; a finer grind increases contact "
                "surface and slows flow, extracting more.",
            ),
            contraindicated=_slow_drawdown,
        ),
        Rule(
            _adj(
                Variable.TEMPERATURE,
                Direction.INCREASE,
                "+2-3°C",
                "Hotter water extracts faster without adding fines, so it fixes "
                "underextraction even when the drawdown is already slow.",
            ),
            contraindicated=_temp_at_ceiling,
        ),
        Rule(
            _adj(
                Variable.BLOOM,
                Direction.INCREASE,
                "bloom 45s with a gentle swirl",
                "A longer, evenly wetted bloom improves extraction uniformity.",
            ),
        ),
    ],
    TasteDefect.SOUR: [
        Rule(
            _adj(
                Variable.GRIND,
                Direction.FINER,
                "a small grind step finer",
                "Sourness without thinness is mild underextraction; nudge extraction "
                "up with a slightly finer grind.",
            ),
            contraindicated=_slow_drawdown,
        ),
        Rule(
            _adj(
                Variable.TEMPERATURE,
                Direction.INCREASE,
                "+2°C",
                "Hotter water raises extraction without changing flow.",
            ),
            contraindicated=_temp_at_ceiling,
        ),
    ],
    TasteDefect.BITTER_ASTRINGENT: [
        Rule(
            _adj(
                Variable.GRIND,
                Direction.COARSER,
                "one grind step coarser",
                "Bitterness with a drying finish means overextraction plus fines; "
                "coarser reduces both.",
            ),
        ),
        Rule(
            _adj(
                Variable.TEMPERATURE,
                Direction.DECREASE,
                "-2-3°C",
                "Cooler water slows extraction of late, harsh compounds.",
            ),
            contraindicated=_temp_at_floor,
        ),
        Rule(
            _adj(
                Variable.AGITATION,
                Direction.GENTLER,
                "gentler pours, no late stirring",
                "Astringency tracks fines migration; less agitation keeps fines out of the cup.",
            ),
        ),
    ],
    TasteDefect.BITTER: [
        Rule(
            _adj(
                Variable.GRIND,
                Direction.COARSER,
                "one grind step coarser",
                "Harsh bitterness means overextraction; coarser reduces contact "
                "surface and speeds flow.",
            ),
        ),
        Rule(
            _adj(
                Variable.TEMPERATURE,
                Direction.DECREASE,
                "-3°C",
                "Cooler water extracts less of the bitter late fractions.",
            ),
            contraindicated=_temp_at_floor,
        ),
    ],
    TasteDefect.WEAK: [
        # Balanced-but-weak is a strength problem, not extraction: fix ratio,
        # don't touch grind first.
        Rule(
            _adj(
                Variable.RATIO,
                Direction.DECREASE,
                "about 1g more coffee (e.g. 1:16.5 toward 1:15)",
                "Weak but balanced means extraction is fine and the cup is just "
                "dilute; use more coffee rather than changing extraction.",
            ),
        ),
        Rule(
            _adj(
                Variable.GRIND,
                Direction.FINER,
                "a small grind step finer",
                "If a stronger ratio alone is not enough, raise extraction slightly.",
            ),
            contraindicated=_slow_drawdown,
        ),
    ],
    TasteDefect.STRONG_MUDDY: [
        Rule(
            _adj(
                Variable.RATIO,
                Direction.INCREASE,
                "more water (toward 1:16.5-1:17)",
                "Heavy, muddled cups are usually too concentrated; dilute the recipe.",
            ),
        ),
        Rule(
            _adj(
                Variable.GRIND,
                Direction.COARSER,
                "one grind step coarser",
                "Coarser lowers extraction and cleans up the cup.",
            ),
        ),
    ],
    TasteDefect.HOLLOW: [
        Rule(
            _adj(
                Variable.POUR_TECHNIQUE,
                Direction.MORE_EVEN,
                "even spiral pours plus a gentle swirl after the final pour",
                "A hollow, muted cup with okay acidity points to uneven extraction "
                "or channeling; fix bed uniformity before anything else.",
            ),
        ),
        Rule(
            _adj(
                Variable.GRIND,
                Direction.FINER,
                "a small grind step finer",
                "Slightly finer raises overall extraction once the bed is even.",
            ),
            contraindicated=_slow_drawdown,
        ),
    ],
    TasteDefect.BALANCED: [
        Rule(
            _adj(
                Variable.NONE,
                Direction.KEEP,
                "change nothing",
                "The brew is balanced; repeat it and change nothing so you have a stable baseline.",
            ),
        ),
    ],
}

# Drawdown-driven rules apply when the timing itself is the problem.
STALLED_RULES: list[Rule] = [
    Rule(
        _adj(
            Variable.GRIND,
            Direction.COARSER,
            "one grind step coarser",
            "A stalled drawdown means excess fines are clogging the bed; coarser "
            "produces fewer fines.",
        ),
    ),
    Rule(
        _adj(
            Variable.POUR_TECHNIQUE,
            Direction.GENTLER,
            "fewer, gentler pour pulses",
            "Aggressive pouring drives fines into the filter; gentler pours keep the bed open.",
        ),
    ),
]

FAST_RULES: list[Rule] = [
    Rule(
        _adj(
            Variable.GRIND,
            Direction.FINER,
            "one grind step finer",
            "A fast drawdown with a sour or weak cup means the grind is too coarse "
            "and water is channeling through.",
        ),
    ),
    Rule(
        _adj(
            Variable.POUR_TECHNIQUE,
            Direction.MORE_EVEN,
            "more, smaller pulse pours",
            "Smaller pulses keep the water level low and slow the pass-through.",
        ),
    ),
]


def diagnose(brew: BrewLog) -> Diagnosis:
    """Combine the reported defect with ratio/drawdown assessments."""
    extraction = "unknown"
    strength = "unknown"
    if brew.defect in (TasteDefect.SOUR_THIN, TasteDefect.SOUR):
        extraction = "under"
    elif brew.defect in (TasteDefect.BITTER_ASTRINGENT, TasteDefect.BITTER):
        extraction = "over"
    elif brew.defect == TasteDefect.HOLLOW:
        extraction = "uneven"
    elif brew.defect in (TasteDefect.WEAK, TasteDefect.STRONG_MUDDY, TasteDefect.BALANCED):
        extraction = "ok"

    if brew.defect in (TasteDefect.SOUR_THIN, TasteDefect.WEAK):
        strength = "weak"
    elif brew.defect == TasteDefect.STRONG_MUDDY:
        strength = "strong"
    elif brew.defect in (TasteDefect.BALANCED, TasteDefect.BITTER, TasteDefect.SOUR):
        strength = "ok"

    drawdown = "unknown"
    if brew.drawdown_s is not None and brew.method is not None:
        drawdown = assess_drawdown(brew.drawdown_s, brew.method)

    parts = []
    if brew.defect:
        parts.append(f"defect={brew.defect.value}")
    parts.append(f"extraction={extraction}")
    if brew.ratio:
        parts.append(f"ratio=1:{brew.ratio} ({assess_ratio(brew.ratio)})")
    parts.append(f"drawdown={drawdown}")
    return Diagnosis(
        extraction=extraction,
        strength=strength,
        drawdown=drawdown,
        summary="; ".join(parts),
    )


def recommend(brew: BrewLog, diagnosis: Diagnosis) -> Recommendation:
    """Pick the first non-contraindicated rule; skipped rules become alternatives."""
    if brew.defect is None:
        if diagnosis.drawdown == "stalled":
            rules = STALLED_RULES
        elif diagnosis.drawdown == "fast":
            rules = FAST_RULES
        else:
            return Recommendation(
                adjustment=_adj(
                    Variable.NONE,
                    Direction.KEEP,
                    "log more detail",
                    "No taste defect could be identified; next brew, note how it "
                    "tasted (sour/bitter/weak/etc.) and the drawdown time.",
                ),
                confidence="low",
            )
    elif diagnosis.drawdown == "stalled" and brew.defect in (
        TasteDefect.BITTER,
        TasteDefect.BITTER_ASTRINGENT,
        TasteDefect.BALANCED,
    ):
        # Stall + overextraction symptoms: the stall IS the story.
        rules = STALLED_RULES
    elif diagnosis.drawdown == "fast" and brew.defect in (TasteDefect.SOUR, TasteDefect.WEAK):
        rules = FAST_RULES
    else:
        rules = DEFECT_RULES[brew.defect]

    chosen: Adjustment | None = None
    alternatives: list[Adjustment] = []
    for rule in rules:
        reason = rule.contraindicated(brew, diagnosis) if rule.contraindicated else None
        if chosen is None and reason is None:
            chosen = rule.adjustment
        else:
            alt = rule.adjustment.model_copy()
            if reason:
                alt.rationale = f"(skipped: {reason}) {alt.rationale}"
            alternatives.append(alt)

    if chosen is None:
        # Every rule was contraindicated — surface the best alternative honestly.
        chosen = _adj(
            Variable.NONE,
            Direction.KEEP,
            "re-measure and repeat",
            "Every standard adjustment is contraindicated by the log; repeat the "
            "brew and double-check the measurements.",
        )

    missing = [
        name
        for name, value in (
            ("drawdown time", brew.drawdown_s),
            ("water temperature", brew.temperature_c),
            ("dose/water", brew.ratio),
        )
        if value is None
    ]
    if missing:
        confidence = "medium"
        chosen = chosen.model_copy()
        chosen.rationale += f" (Confidence reduced: next time also log {', '.join(missing)}.)"
    else:
        confidence = "high"

    return Recommendation(adjustment=chosen, alternatives=alternatives, confidence=confidence)


@tool
def recommend_adjustment(brew_log_json: str) -> dict:
    """Diagnose a brew log and return exactly ONE controlled adjustment to try next.

    Args:
        brew_log_json: A BrewLog as JSON, e.g. {"method": "v60", "dose_g": 16,
            "water_g": 250, "temperature_c": 94, "drawdown_s": 225,
            "defect": "sour_thin"}
    """
    brew = BrewLog.model_validate_json(brew_log_json)
    diagnosis = diagnose(brew)
    rec = recommend(brew, diagnosis)
    return {
        "diagnosis": diagnosis.summary,
        "adjustment": rec.adjustment.model_dump(),
        "confidence": rec.confidence,
        "alternatives": [a.model_dump() for a in rec.alternatives],
    }
