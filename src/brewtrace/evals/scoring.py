"""Deterministic eval scoring: no LLM, no judgment calls."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel

from brewtrace.models import Direction, TasteDefect, Variable

CASES_PATH = Path(__file__).with_name("cases.yaml")


class AcceptableAdjustment(BaseModel):
    variable: Variable
    direction: Direction


class EvalCase(BaseModel):
    id: str
    input: str
    expected_defect: TasteDefect | None = None
    acceptable: list[AcceptableAdjustment]
    notes: str | None = None


class EvalResult(BaseModel):
    case_id: str
    passed: bool
    got_variable: Variable
    got_direction: Direction
    detail: str


def load_cases(path: Path = CASES_PATH) -> list[EvalCase]:
    raw = yaml.safe_load(path.read_text())
    return [EvalCase.model_validate(item) for item in raw]


def score(variable: Variable, direction: Direction, case: EvalCase) -> EvalResult:
    """Pass iff the (variable, direction) pair is in the case's acceptable set.

    The one-variable invariant is structural: both the deterministic pipeline
    and the agent's structured output can only express a single adjustment.
    """
    accepted = any(
        variable == a.variable and direction == a.direction for a in case.acceptable
    )
    wanted = " or ".join(f"{a.variable.value}/{a.direction.value}" for a in case.acceptable)
    return EvalResult(
        case_id=case.id,
        passed=accepted,
        got_variable=variable,
        got_direction=direction,
        detail=f"got {variable.value}/{direction.value}, wanted {wanted}",
    )
