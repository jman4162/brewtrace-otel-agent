"""Domain model for brew logs, diagnoses, and recommendations.

Pure Pydantic + regex parsing. No strands or opentelemetry imports: everything
here is testable without an LLM or a collector.
"""

from __future__ import annotations

import re
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class BrewMethod(str, Enum):
    V60 = "v60"
    KALITA = "kalita"
    CLEVER = "clever"


class TasteDefect(str, Enum):
    SOUR_THIN = "sour_thin"
    SOUR = "sour"
    BITTER_ASTRINGENT = "bitter_astringent"
    BITTER = "bitter"
    WEAK = "weak"
    STRONG_MUDDY = "strong_muddy"
    HOLLOW = "hollow"
    BALANCED = "balanced"


class Variable(str, Enum):
    GRIND = "grind"
    TEMPERATURE = "temperature"
    RATIO = "ratio"
    AGITATION = "agitation"
    POUR_TECHNIQUE = "pour_technique"
    BLOOM = "bloom"
    NONE = "none"


class Direction(str, Enum):
    FINER = "finer"
    COARSER = "coarser"
    INCREASE = "increase"
    DECREASE = "decrease"
    GENTLER = "gentler"
    MORE_EVEN = "more_even"
    KEEP = "keep"


class BrewLog(BaseModel):
    method: BrewMethod | None = None
    dose_g: float | None = None
    water_g: float | None = None
    temperature_c: float | None = None
    grind_setting: str | None = None
    bloom_time_s: int | None = None
    drawdown_s: int | None = None
    defect: TasteDefect | None = None
    raw_text: str = ""

    @property
    def ratio(self) -> float | None:
        if self.dose_g and self.water_g:
            return round(self.water_g / self.dose_g, 2)
        return None


class Diagnosis(BaseModel):
    extraction: Literal["under", "over", "uneven", "ok", "unknown"]
    strength: Literal["weak", "ok", "strong", "unknown"]
    drawdown: Literal["fast", "in_range", "slow", "stalled", "unknown"]
    summary: str


class Adjustment(BaseModel):
    variable: Variable
    direction: Direction
    magnitude: str
    rationale: str


class Recommendation(BaseModel):
    adjustment: Adjustment
    alternatives: list[Adjustment] = Field(default_factory=list)
    confidence: Literal["high", "medium", "low"]


class BrewAdvice(BaseModel):
    """Structured output the agent must produce.

    Mirrors Adjustment's variable/direction fields so the eval scorer handles
    the deterministic pipeline and the agent with one code path.
    """

    diagnosis_summary: str = Field(description="One-sentence diagnosis of the brew")
    variable: Variable = Field(description="The single variable to change")
    direction: Direction = Field(description="Which way to change it")
    magnitude: str = Field(description="How much to change it, e.g. 'one grind step finer'")
    rationale: str = Field(description="Why this change, grounded in the brew data")
    expected_effect: str = Field(description="What the next cup should taste like if it works")


# --- Parsing -----------------------------------------------------------------

_DOSE_WATER = re.compile(r"(\d+(?:\.\d+)?)\s*g\b", re.IGNORECASE)
_EXPLICIT_DOSE = re.compile(r"(\d+(?:\.\d+)?)\s*g\s*(?:coffee|dose)", re.IGNORECASE)
_EXPLICIT_WATER = re.compile(r"(\d+(?:\.\d+)?)\s*g\s*(?:water)", re.IGNORECASE)
_TEMP = re.compile(r"(\d{2,3})(?:\.\d+)?\s*°?\s*c\b", re.IGNORECASE)
_TIME = re.compile(r"(\d{1,2}):(\d{2})")

_METHOD_KEYWORDS: dict[str, BrewMethod] = {
    "v60": BrewMethod.V60,
    "kalita": BrewMethod.KALITA,
    "clever": BrewMethod.CLEVER,
}

# Ordered: more specific compound defects must match before their parts.
_DEFECT_KEYWORDS: list[tuple[re.Pattern[str], TasteDefect]] = [
    (re.compile(r"sour.{0,20}\bthin\b|\bthin\b.{0,20}sour", re.IGNORECASE), TasteDefect.SOUR_THIN),
    (
        re.compile(r"bitter.{0,25}(astringen|dry(ing)?\s+finish)", re.IGNORECASE),
        TasteDefect.BITTER_ASTRINGENT,
    ),
    (re.compile(r"astringen|dry(ing)?\s+finish", re.IGNORECASE), TasteDefect.BITTER_ASTRINGENT),
    (re.compile(r"\bsour\b|\btart\b|\bsharp acidity\b", re.IGNORECASE), TasteDefect.SOUR),
    (re.compile(r"\bbitter\b|\bharsh\b|\bburnt\b", re.IGNORECASE), TasteDefect.BITTER),
    (re.compile(r"\bweak\b|\bwatery\b|\bdilute", re.IGNORECASE), TasteDefect.WEAK),
    (
        re.compile(r"\bmuddy\b|\bmuddled\b|too strong|\bheavy\b", re.IGNORECASE),
        TasteDefect.STRONG_MUDDY,
    ),
    (
        re.compile(r"\bhollow\b|\bflat\b|\bmuted\b|no sweetness|lacks? sweetness", re.IGNORECASE),
        TasteDefect.HOLLOW,
    ),
    (
        re.compile(r"\bbalanced\b|\bgreat\b|\bdelicious\b|tastes? good", re.IGNORECASE),
        TasteDefect.BALANCED,
    ),
]

_GRIND_SETTING = re.compile(
    r"(?:grind|ode|encore|c40|zp6|k6)[^\d]{0,15}(\d+(?:\.\d+)?)", re.IGNORECASE
)


def parse_brew_log(text: str) -> BrewLog:
    """Parse a free-text brew description into a BrewLog.

    Unparseable fields stay None; downstream rules must tolerate that.
    """
    method = None
    lowered = text.lower()
    for keyword, m in _METHOD_KEYWORDS.items():
        if keyword in lowered:
            method = m
            break

    dose_g: float | None = None
    water_g: float | None = None
    explicit_dose = _EXPLICIT_DOSE.search(text)
    explicit_water = _EXPLICIT_WATER.search(text)
    if explicit_dose:
        dose_g = float(explicit_dose.group(1))
    if explicit_water:
        water_g = float(explicit_water.group(1))
    if dose_g is None or water_g is None:
        # Fall back to positional: smaller gram figure = dose, larger = water.
        grams = [float(m.group(1)) for m in _DOSE_WATER.finditer(text)]
        grams = [g for g in grams if g not in (dose_g, water_g)]
        if dose_g is None and water_g is None and len(grams) >= 2:
            dose_g, water_g = min(grams[:2]), max(grams[:2])
        elif dose_g is None and water_g is not None and grams:
            dose_g = grams[0]
        elif water_g is None and dose_g is not None and grams:
            water_g = grams[0]

    temp_match = _TEMP.search(text)
    temperature_c = float(temp_match.group(1)) if temp_match else None

    drawdown_s = None
    time_match = _TIME.search(text)
    if time_match:
        drawdown_s = int(time_match.group(1)) * 60 + int(time_match.group(2))

    defect = None
    for pattern, d in _DEFECT_KEYWORDS:
        if pattern.search(text):
            defect = d
            break

    grind_match = _GRIND_SETTING.search(text)
    grind_setting = grind_match.group(1) if grind_match else None

    return BrewLog(
        method=method,
        dose_g=dose_g,
        water_g=water_g,
        temperature_c=temperature_c,
        grind_setting=grind_setting,
        drawdown_s=drawdown_s,
        defect=defect,
        raw_text=text,
    )
