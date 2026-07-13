"""Eval runner: deterministic pipeline by default, live agent with --agent.

Deterministic mode must score 100% — the cases and the rule table are two
views of the same logic, and a mismatch means one of them is wrong. Agent
mode measures how reliably a local model routes through the tools; each case
runs inside its own `brewtrace.request` span tagged with eval.case_id and
eval.passed, so failures are filterable in Jaeger, and carries a
`gen_ai.evaluation.result` span event with the spec attribute names.
"""

from __future__ import annotations

import argparse
import sys
import time

from pydantic import BaseModel

from brewtrace.evals.scoring import EvalCase, EvalResult, load_cases, score
from brewtrace.models import parse_brew_log
from brewtrace.tools.recommendation import diagnose, recommend


class CaseRun(BaseModel):
    """One agent-mode case with the telemetry the matrix report needs."""

    result: EvalResult
    duration_s: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    tool_calls: int = 0

    @property
    def used_tools(self) -> bool:
        # The prescribed workflow is 4 tool calls; ≥2 counts as "actually
        # routed through tools" rather than answering from priors.
        return self.tool_calls >= 2


def run_deterministic(cases: list[EvalCase]) -> list[EvalResult]:
    results = []
    for case in cases:
        brew = parse_brew_log(case.input)
        if brew.defect != case.expected_defect:
            results.append(
                EvalResult(
                    case_id=case.id,
                    passed=False,
                    got_variable="none",
                    got_direction="keep",
                    detail=f"parser found defect={brew.defect}, expected {case.expected_defect}",
                )
            )
            continue
        rec = recommend(brew, diagnose(brew))
        results.append(score(rec.adjustment.variable, rec.adjustment.direction, case))
    return results


EVALUATION_NAME = "brew_adjustment_accuracy"


def _add_evaluation_event(span, result: EvalResult) -> None:
    """Attach a gen_ai.evaluation.result event (OTel GenAI semconv, Development).

    The spec says the event SHOULD be parented to the GenAI operation span
    being evaluated — a span event on the per-case request span does exactly
    that, and stays visible in Jaeger without the experimental Events API.
    """
    span.add_event(
        "gen_ai.evaluation.result",
        {
            "gen_ai.evaluation.name": EVALUATION_NAME,
            "gen_ai.evaluation.score.value": 1.0 if result.passed else 0.0,
            "gen_ai.evaluation.score.label": "pass" if result.passed else "fail",
            "gen_ai.evaluation.explanation": result.detail,
        },
    )


def run_agent(
    cases: list[EvalCase],
    model_id: str,
    host: str,
    metrics: bool = False,
    quiet: bool = False,
) -> list[CaseRun]:
    from brewtrace.agent import build_agent, run_diagnosis
    from brewtrace.telemetry import brew_request_span, record_eval_result, setup_telemetry

    setup_telemetry(otlp=True, metrics=metrics)
    runs: list[CaseRun] = []
    for case in cases:
        agent = build_agent(model_id=model_id, host=host)  # fresh history per case
        brew = parse_brew_log(case.input)
        started = time.perf_counter()
        extra = {"eval.case_id": case.id, "eval.model": model_id}
        with brew_request_span(brew, extra=extra) as span:
            agent_result = None
            try:
                advice, agent_result = run_diagnosis(agent, case.input)
            except Exception as exc:  # noqa: BLE001 — a crashed case is a failed case
                advice = None
                span.set_attribute("eval.error", str(exc)[:200])
            if advice is None:
                result = EvalResult(
                    case_id=case.id,
                    passed=False,
                    got_variable="none",
                    got_direction="keep",
                    detail="no structured advice returned",
                )
            else:
                result = score(advice.variable, advice.direction, case)
            span.set_attribute("eval.passed", result.passed)
            _add_evaluation_event(span, result)

        run = CaseRun(result=result, duration_s=time.perf_counter() - started)
        if agent_result is not None:
            usage = agent_result.metrics.accumulated_usage
            run.input_tokens = usage.get("inputTokens", 0)
            run.output_tokens = usage.get("outputTokens", 0)
            run.tool_calls = sum(m.call_count for m in agent_result.metrics.tool_metrics.values())
        if metrics:
            record_eval_result(model_id, result.passed)
        runs.append(run)
        if not quiet:
            marker = "PASS" if result.passed else "FAIL"
            print(
                f"  {marker} {case.id}: {result.detail} "
                f"[{run.duration_s:.0f}s, {run.tool_calls} tool calls]"
            )
    return runs


def summarize(results: list[EvalResult], threshold: float) -> int:
    passed = sum(1 for r in results if r.passed)
    rate = passed / len(results) if results else 0.0
    print(f"\n{passed}/{len(results)} passed ({rate:.0%}, threshold {threshold:.0%})")
    for r in results:
        if not r.passed:
            print(f"  FAIL {r.case_id}: {r.detail}")
    return 0 if rate >= threshold else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run BrewTrace evals")
    parser.add_argument("--agent", action="store_true", help="run the live agent per case")
    parser.add_argument("--model", default="qwen3")
    parser.add_argument("--host", default="http://localhost:11434")
    parser.add_argument("--metrics", action="store_true", help="emit brew.eval.results metric")
    parser.add_argument(
        "--threshold",
        type=float,
        default=None,
        help="pass-rate threshold (default: 1.0 deterministic, 0.8 agent)",
    )
    args = parser.parse_args(argv)

    cases = load_cases()
    if args.agent:
        threshold = args.threshold if args.threshold is not None else 0.8
        print(f"Running {len(cases)} cases against the live agent ({args.model})…")
        runs = run_agent(cases, model_id=args.model, host=args.host, metrics=args.metrics)
        results = [r.result for r in runs]
    else:
        threshold = args.threshold if args.threshold is not None else 1.0
        results = run_deterministic(cases)
    return summarize(results, threshold)


if __name__ == "__main__":
    sys.exit(main())
