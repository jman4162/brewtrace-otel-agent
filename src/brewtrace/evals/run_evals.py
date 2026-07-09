"""Eval runner: deterministic pipeline by default, live agent with --agent.

Deterministic mode must score 100% — the cases and the rule table are two
views of the same logic, and a mismatch means one of them is wrong. Agent
mode measures how reliably a local model routes through the tools; each case
runs inside its own `brewtrace.request` span tagged with eval.case_id and
eval.passed, so failures are filterable in Jaeger.
"""

from __future__ import annotations

import argparse
import sys

from brewtrace.evals.scoring import EvalCase, EvalResult, load_cases, score
from brewtrace.models import parse_brew_log
from brewtrace.tools.recommendation import diagnose, recommend


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


def run_agent(cases: list[EvalCase], model_id: str, host: str) -> list[EvalResult]:
    from brewtrace.agent import build_agent, run_diagnosis
    from brewtrace.telemetry import brew_request_span, setup_telemetry

    setup_telemetry(otlp=True)
    agent_results = []
    for case in cases:
        agent = build_agent(model_id=model_id, host=host)  # fresh history per case
        brew = parse_brew_log(case.input)
        with brew_request_span(brew, extra={"eval.case_id": case.id}) as span:
            try:
                advice, _ = run_diagnosis(agent, case.input)
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
        agent_results.append(result)
        marker = "PASS" if result.passed else "FAIL"
        print(f"  {marker} {case.id}: {result.detail}")
    return agent_results


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
        results = run_agent(cases, model_id=args.model, host=args.host)
    else:
        threshold = args.threshold if args.threshold is not None else 1.0
        results = run_deterministic(cases)
    return summarize(results, threshold)


if __name__ == "__main__":
    sys.exit(main())
