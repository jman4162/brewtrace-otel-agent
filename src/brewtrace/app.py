"""BrewTrace CLI entry point."""

from __future__ import annotations

import argparse
import sys

from brewtrace.models import BrewLog, Recommendation, parse_brew_log
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


def run_deterministic(brew_text: str) -> int:
    brew = parse_brew_log(brew_text)
    diagnosis = diagnose(brew)
    rec = recommend(brew, diagnosis)
    print(_render_brew(brew))
    print(f"\nDiagnosis: {diagnosis.summary}\n")
    print(_render_recommendation(rec))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="brewtrace",
        description="Diagnose a pour-over brew and recommend one controlled adjustment.",
    )
    parser.add_argument(
        "brew_text", nargs="?", help='e.g. "16g/250g V60, 94C, 3:45, sour and thin"'
    )
    parser.add_argument("--no-llm", action="store_true", help="deterministic rules only, no agent")
    args = parser.parse_args(argv)

    if not args.brew_text:
        parser.error('describe your brew, e.g.: brewtrace "16g/250g V60, 94C, 3:45, sour and thin"')

    if args.no_llm:
        return run_deterministic(args.brew_text)

    print("Agent mode arrives in milestone 2 — use --no-llm for now.", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
