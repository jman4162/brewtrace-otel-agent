"""Optional LLM-as-judge evaluation via strands-agents-evals with a local judge.

The deterministic scorer in scoring.py checks *what* the agent recommended;
this judge scores *how well the answer is argued* — whether the rationale is
grounded in the brew data rather than generic coffee advice. It is optional
because judge scores are non-deterministic and need a second model call per
case.

strands-agents-evals defaults to an Amazon Bedrock judge; the whole point of
this module is overriding that with a local Ollama model so the project stays
cloud-free.

Install and run:
    uv sync --extra judge
    uv run python -m brewtrace.evals.judge [--model qwen3] [--limit 5]
"""

from __future__ import annotations

import argparse
import sys

RUBRIC = """Score the coffee-brewing recommendation 0-1:
- Does it recommend exactly ONE variable change? (hard fail if more than one)
- Is the rationale grounded in the specific numbers given (ratio, temperature,
  drawdown time), not generic advice?
- Is the direction physically sensible for the described taste defect?
Pass at score >= 0.7."""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="LLM-as-judge eval (optional)")
    parser.add_argument("--model", default="qwen3", help="Ollama model used as the judge")
    parser.add_argument("--host", default="http://localhost:11434")
    parser.add_argument("--agent-model", default="qwen3", help="Ollama model under evaluation")
    parser.add_argument("--limit", type=int, default=5, help="number of cases to judge")
    args = parser.parse_args(argv)

    try:
        from strands_evals import Case, Experiment
        from strands_evals.evaluators import OutputEvaluator
    except ImportError:
        print("strands-agents-evals is not installed. Run: uv sync --extra judge")
        return 2

    from strands.models.ollama import OllamaModel

    from brewtrace.agent import build_agent, run_diagnosis
    from brewtrace.evals.scoring import load_cases

    judge_model = OllamaModel(host=args.host, model_id=args.model, temperature=0.0)
    evaluator = OutputEvaluator(rubric=RUBRIC, model=judge_model, include_inputs=True)

    cases = [
        Case(name=c.id, input=c.input)
        for c in load_cases()[: args.limit]
    ]

    def task(case):
        agent = build_agent(model_id=args.agent_model, host=args.host)
        advice, _ = run_diagnosis(agent, case.input)
        if advice is None:
            return "no structured advice returned"
        return (
            f"Change {advice.variable.value} → {advice.direction.value} "
            f"({advice.magnitude}). {advice.rationale}"
        )

    experiment = Experiment(cases=cases, evaluators=[evaluator])
    report = experiment.run_evaluations(task)
    print(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
