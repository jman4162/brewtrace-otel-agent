"""BrewTrace CLI entry point."""

from __future__ import annotations

import argparse
import sys

from brewtrace.models import BrewAdvice, BrewLog, Recommendation, parse_brew_log
from brewtrace.tools.recommendation import diagnose, recommend


def _render_brew(brew: BrewLog) -> str:
    lines = ["Parsed brew log:"]
    fields = [
        ("method", brew.method.value if brew.method else None),
        ("dose", f"{brew.dose_g:g} g" if brew.dose_g else None),
        ("water", f"{brew.water_g:g} g" if brew.water_g else None),
        ("ratio", f"1:{brew.ratio}" if brew.ratio else None),
        ("temperature", f"{brew.temperature_c:g} °C" if brew.temperature_c else None),
        ("drawdown", f"{brew.drawdown_s}s" if brew.drawdown_s else None),
        ("grind setting", brew.grind_setting),
        ("defect", brew.defect.value if brew.defect else None),
    ]
    for name, value in fields:
        lines.append(f"  {name:13} {value if value is not None else '—'}")
    return "\n".join(lines)


def _render_recommendation(rec: Recommendation) -> str:
    adj = rec.adjustment
    lines = [
        f"Recommendation ({rec.confidence} confidence):",
        f"  change {adj.variable.value} → {adj.direction.value}: {adj.magnitude}",
        f"  why: {adj.rationale}",
    ]
    if rec.alternatives:
        lines.append("  alternatives considered:")
        for alt in rec.alternatives:
            lines.append(f"    - {alt.variable.value} {alt.direction.value}: {alt.rationale}")
    return "\n".join(lines)


def _render_advice(advice: BrewAdvice) -> str:
    return "\n".join(
        [
            f"Diagnosis: {advice.diagnosis_summary}",
            "",
            f"Change: {advice.variable.value} → {advice.direction.value} ({advice.magnitude})",
            f"Why: {advice.rationale}",
            f"Expected: {advice.expected_effect}",
        ]
    )


def _render_metrics(metrics) -> str:
    usage = metrics.accumulated_usage
    tool_calls = ", ".join(
        f"{name}×{m.call_count}" for name, m in sorted(metrics.tool_metrics.items())
    )
    return (
        f"[tokens in/out: {usage['inputTokens']}/{usage['outputTokens']} | "
        f"cycles: {len(metrics.cycle_durations)} | tools: {tool_calls or 'none'}]"
    )


def run_deterministic(brew_text: str) -> int:
    brew = parse_brew_log(brew_text)
    diagnosis = diagnose(brew)
    rec = recommend(brew, diagnosis)
    print(_render_brew(brew))
    print(f"\nDiagnosis: {diagnosis.summary}\n")
    print(_render_recommendation(rec))
    return 0


def run_agent(
    brew_text: str,
    model_id: str,
    host: str,
    telemetry: bool = True,
    console_traces: bool = False,
    metrics: bool = False,
    extra_attributes: dict | None = None,
) -> int:
    # Imported lazily so --no-llm never needs strands/ollama importable.
    from brewtrace.agent import build_agent, run_diagnosis
    from brewtrace.telemetry import brew_request_span, setup_telemetry

    if telemetry:
        setup_telemetry(otlp=True, console=console_traces, metrics=metrics)

    brew = parse_brew_log(brew_text)
    print(_render_brew(brew))
    print()

    agent = build_agent(model_id=model_id, host=host)
    if telemetry:
        with brew_request_span(brew, extra=extra_attributes):
            advice, result = run_diagnosis(agent, brew_text)
    else:
        advice, result = run_diagnosis(agent, brew_text)
    if advice is None:
        print("The model did not return structured advice; try again or use --no-llm.")
        return 1
    print(_render_advice(advice))
    print()
    print(_render_metrics(result.metrics))
    return 0


def _beanbench_text(brew, defect_override: str | None) -> str:
    """Render an imported BrewLog as the agent's free-text input."""
    parts = []
    if brew.dose_g and brew.water_g:
        parts.append(f"{brew.dose_g:g}g coffee / {brew.water_g:g}g water")
    if brew.method:
        parts.append(brew.method.value)
    if brew.temperature_c:
        parts.append(f"{brew.temperature_c:g}C")
    if brew.drawdown_s:
        parts.append(f"{brew.drawdown_s // 60}:{brew.drawdown_s % 60:02d} drawdown")
    taste = defect_override or (brew.raw_text if brew.raw_text else None)
    if taste:
        parts.append(f"tasted: {taste}")
    return ", ".join(parts)


def run_beanbench(args) -> int:
    from brewtrace.ingest.beanbench import load_export

    result = load_export(args.from_beanbench)
    for reason in result.skipped:
        print(f"skipped: {reason}", file=sys.stderr)
    if not result.brews:
        print("No importable pour-over brews found in the export.", file=sys.stderr)
        return 1

    if args.all:
        entries = result.brews
    else:
        index = args.index if args.index is not None else 0
        if index >= len(result.brews):
            print(f"Only {len(result.brews)} brews in the export.", file=sys.stderr)
            return 1
        entries = [result.brews[index]]

    exit_code = 0
    for entry in entries:
        text = _beanbench_text(entry.brew, args.defect)
        print(f"— {entry.date or 'undated'} · {entry.coffee or 'unknown coffee'} —")
        if args.no_llm:
            exit_code = max(exit_code, run_deterministic(text))
        else:
            exit_code = max(
                exit_code,
                run_agent(
                    text,
                    model_id=args.model,
                    host=args.host,
                    telemetry=not args.no_telemetry,
                    console_traces=args.console_traces,
                    metrics=args.metrics,
                    extra_attributes={"brew.source": "beanbench"},
                ),
            )
        print()
    return exit_code


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="brewtrace",
        description="Diagnose a pour-over brew and recommend one controlled adjustment.",
    )
    parser.add_argument(
        "brew_text", nargs="?", help='e.g. "16g/250g V60, 94C, 3:45, sour and thin"'
    )
    parser.add_argument("--no-llm", action="store_true", help="deterministic rules only, no agent")
    parser.add_argument("--model", default="qwen3", help="Ollama model id (default: qwen3)")
    parser.add_argument(
        "--host", default="http://localhost:11434", help="Ollama host (default: localhost:11434)"
    )
    parser.add_argument("--no-telemetry", action="store_true", help="disable OTel export")
    parser.add_argument(
        "--console-traces",
        action="store_true",
        help="also print spans to stdout (no docker needed)",
    )
    parser.add_argument("--metrics", action="store_true", help="also export OTel metrics")
    beanbench = parser.add_argument_group("Beanbench import")
    beanbench.add_argument(
        "--from-beanbench", metavar="EXPORT.json", help="diagnose brews from a Beanbench export"
    )
    beanbench.add_argument(
        "--index", type=int, default=None, help="which entry to diagnose (0 = newest, default)"
    )
    beanbench.add_argument("--all", action="store_true", help="diagnose every pour-over entry")
    beanbench.add_argument(
        "--defect", help="override the defect inferred from tasting notes, e.g. sour_thin"
    )
    args = parser.parse_args(argv)

    if args.from_beanbench:
        return run_beanbench(args)

    if not args.brew_text:
        parser.error('describe your brew, e.g.: brewtrace "16g/250g V60, 94C, 3:45, sour and thin"')

    if args.no_llm:
        return run_deterministic(args.brew_text)
    return run_agent(
        args.brew_text,
        model_id=args.model,
        host=args.host,
        telemetry=not args.no_telemetry,
        console_traces=args.console_traces,
        metrics=args.metrics,
    )


if __name__ == "__main__":
    sys.exit(main())
