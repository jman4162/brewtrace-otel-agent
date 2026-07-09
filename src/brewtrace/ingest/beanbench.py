"""Import brew logs from a Beanbench JSON export.

Beanbench (https://beanbench.coffee) exports every logged brew as JSON via its
share sheet. The field mapping is nearly 1:1 with BrewLog; the one gap is that
Beanbench has no structured defect taxonomy, so the taste defect is inferred
from the free-text tasting notes with the same keyword matching the CLI parser
uses (override with --defect if it guesses wrong).

Only pour-over methods BrewTrace understands are imported; espresso, immersion,
and custom methods are skipped with a warning.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from brewtrace.models import BrewLog, BrewMethod, infer_defect

# Beanbench method strings → BrewTrace methods. Everything else is skipped.
METHOD_MAP: dict[str, BrewMethod] = {
    "v60": BrewMethod.V60,
    "kalita 155": BrewMethod.KALITA,
    "kalita 185": BrewMethod.KALITA,
    "kalita": BrewMethod.KALITA,
    "clever dripper": BrewMethod.CLEVER,
    "clever": BrewMethod.CLEVER,
}


@dataclass
class ImportedBrew:
    brew: BrewLog
    date: str | None
    coffee: str | None
    rating: float | None


@dataclass
class ImportResult:
    brews: list[ImportedBrew]
    skipped: list[str]  # human-readable "why" per skipped entry


def _entry_to_brew(entry: dict) -> BrewLog | None:
    method_raw = (entry.get("method") or "").strip().lower()
    method = METHOD_MAP.get(method_raw)
    if method is None:
        return None

    notes_text = " ".join(
        str(entry.get(key) or "") for key in ("tastingNotes", "notes")
    ).strip()

    grind = entry.get("grindSetting")
    return BrewLog(
        method=method,
        dose_g=entry.get("doseGrams"),
        water_g=entry.get("waterGrams"),
        temperature_c=entry.get("temperatureCelsius"),
        grind_setting=str(grind) if grind is not None else None,
        drawdown_s=entry.get("drawdownTimeSeconds"),
        defect=infer_defect(notes_text) if notes_text else None,
        raw_text=notes_text,
    )


def load_export(path: Path | str) -> ImportResult:
    """Parse a Beanbench JSON export into BrewLogs, newest entry first."""
    data = json.loads(Path(path).read_text())
    if isinstance(data, dict):
        # Tolerate a wrapped export: find the first list value.
        entries = next((v for v in data.values() if isinstance(v, list)), [data])
    else:
        entries = data

    brews: list[ImportedBrew] = []
    skipped: list[str] = []
    for entry in entries:
        if not isinstance(entry, dict):
            skipped.append(f"unrecognized entry: {str(entry)[:60]}")
            continue
        brew = _entry_to_brew(entry)
        label = f"{entry.get('date', 'undated')} {entry.get('method', 'no method')}"
        if brew is None:
            skipped.append(f"{label}: method not supported (pour-over only)")
            continue
        brews.append(
            ImportedBrew(
                brew=brew,
                date=entry.get("date"),
                coffee=entry.get("coffee"),
                rating=entry.get("rating"),
            )
        )

    brews.sort(key=lambda b: b.date or "", reverse=True)
    return ImportResult(brews=brews, skipped=skipped)
