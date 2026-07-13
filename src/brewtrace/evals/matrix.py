"""Model-comparison matrix: run the eval suite across Ollama models.

Each model's raw results are persisted to data/matrix/<model>.json so long
runs are resumable and the report regenerates without re-running anything:

    uv run python -m brewtrace.evals.matrix --models qwen3,llama3.1,llama3.2
    uv run python -m brewtrace.evals.matrix --report   # table from saved JSON only

Models must support native tool calling (checked via the Ollama API); models
without it are refused rather than shown as misleading 0% rows.
"""

from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from brewtrace.evals.run_evals import run_agent
from brewtrace.evals.scoring import load_cases

MATRIX_DIR = Path(__file__).resolve().parents[3] / "data" / "matrix"


def model_supports_tools(model_id: str) -> bool:
    """Check the model's capabilities via `ollama show`."""
    try:
        out = subprocess.run(
            ["ollama", "show", model_id], capture_output=True, text=True, timeout=30
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return out.returncode == 0 and "tools" in out.stdout


def run_model(model_id: str, host: str, metrics: bool) -> dict:
    cases = load_cases()
    print(f"=== {model_id}: {len(cases)} cases ===")
    runs = run_agent(cases, model_id=model_id, host=host, metrics=metrics)
    record = {
        "model": model_id,
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "cases": [
            {
                "case_id": r.result.case_id,
                "passed": r.result.passed,
                "detail": r.result.detail,
                "duration_s": round(r.duration_s, 1),
                "input_tokens": r.input_tokens,
                "output_tokens": r.output_tokens,
                "tool_calls": r.tool_calls,
                "used_tools": r.used_tools,
            }
            for r in runs
        ],
    }
    MATRIX_DIR.mkdir(parents=True, exist_ok=True)
    path = MATRIX_DIR / f"{model_id.replace(':', '_').replace('/', '_')}.json"
    path.write_text(json.dumps(record, indent=2))
    print(f"saved {path}")
    return record


def _summary_row(record: dict) -> dict:
    cases = record["cases"]
    n = len(cases)
    passed = sum(1 for c in cases if c["passed"])
    return {
        "model": record["model"],
        "cases": n,
        "pass_rate": passed / n if n else 0.0,
        "tool_use_rate": sum(1 for c in cases if c["used_tools"]) / n if n else 0.0,
        "median_latency_s": statistics.median(c["duration_s"] for c in cases) if n else 0,
        "median_tokens": statistics.median(c["input_tokens"] + c["output_tokens"] for c in cases)
        if n
        else 0,
        "failures": [c["case_id"] for c in cases if not c["passed"]],
    }


def render_table(records: list[dict]) -> str:
    rows = sorted((_summary_row(r) for r in records), key=lambda x: -x["pass_rate"])
    lines = [
        "| Model | Pass rate | Tool-use rate | Median latency | Median tokens/case |",
        "|---|---|---|---|---|",
    ]
    for row in rows:
        lines.append(
            f"| {row['model']} | {row['pass_rate']:.0%} ({round(row['pass_rate'] * row['cases'])}/"
            f"{row['cases']}) | {row['tool_use_rate']:.0%} | {row['median_latency_s']:.0f}s "
            f"| {row['median_tokens']:.0f} |"
        )
    return "\n".join(lines)


def load_records() -> list[dict]:
    if not MATRIX_DIR.exists():
        return []
    return [json.loads(p.read_text()) for p in sorted(MATRIX_DIR.glob("*.json"))]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Model-comparison eval matrix")
    parser.add_argument("--models", help="comma-separated Ollama model ids to run")
    parser.add_argument("--host", default="http://localhost:11434")
    parser.add_argument("--metrics", action="store_true", help="emit brew.eval.results metrics")
    parser.add_argument("--force", action="store_true", help="re-run models with saved results")
    parser.add_argument(
        "--report", action="store_true", help="print the table from saved JSON, run nothing"
    )
    args = parser.parse_args(argv)

    if args.report:
        records = load_records()
        if not records:
            print("No saved results in data/matrix/.")
            return 1
        print(render_table(records))
        return 0

    if not args.models:
        parser.error("--models is required unless --report")

    exit_code = 0
    for model_id in [m.strip() for m in args.models.split(",") if m.strip()]:
        saved = MATRIX_DIR / f"{model_id.replace(':', '_').replace('/', '_')}.json"
        if saved.exists() and not args.force:
            print(f"skip {model_id}: saved results exist ({saved}); use --force to re-run")
            continue
        if not model_supports_tools(model_id):
            print(
                f"refuse {model_id}: no 'tools' capability per `ollama show` "
                f"(pull it first, or it does not support native tool calling)"
            )
            exit_code = 1
            continue
        record = run_model(model_id, host=args.host, metrics=args.metrics)
        row = _summary_row(record)
        print(
            f"{model_id}: {row['pass_rate']:.0%} pass, {row['tool_use_rate']:.0%} tool use, "
            f"median {row['median_latency_s']:.0f}s"
        )

    print()
    records = load_records()
    if records:
        print(render_table(records))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
