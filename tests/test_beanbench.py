import json
from pathlib import Path

from brewtrace.ingest.beanbench import load_export
from brewtrace.models import BrewMethod, TasteDefect

FIXTURE = Path(__file__).parent / "fixtures" / "beanbench_export.json"


def test_loads_pour_over_entries_and_skips_espresso():
    result = load_export(FIXTURE)
    assert len(result.brews) == 3
    assert len(result.skipped) == 1
    assert "Espresso" in result.skipped[0]
    assert "pour-over only" in result.skipped[0]


def test_newest_entry_first():
    result = load_export(FIXTURE)
    assert result.brews[0].date == "2026-07-01T07:42:00Z"
    assert result.brews[0].brew.method == BrewMethod.V60


def test_field_mapping():
    brew = load_export(FIXTURE).brews[0].brew
    assert brew.dose_g == 16.0
    assert brew.water_g == 250.0
    assert brew.temperature_c == 94.0
    assert brew.grind_setting == "5.2"
    assert brew.drawdown_s == 225
    assert brew.ratio == 15.62


def test_defect_inferred_from_tasting_notes():
    brews = load_export(FIXTURE).brews
    assert brews[0].brew.defect == TasteDefect.SOUR_THIN
    assert brews[1].brew.defect == TasteDefect.BITTER_ASTRINGENT
    assert brews[2].brew.defect == TasteDefect.BALANCED


def test_kalita_185_maps_to_kalita():
    brews = load_export(FIXTURE).brews
    assert brews[1].brew.method == BrewMethod.KALITA


def test_missing_fields_tolerated(tmp_path):
    export = tmp_path / "minimal.json"
    export.write_text(json.dumps([{"method": "V60", "doseGrams": 15.0}]))
    result = load_export(export)
    assert len(result.brews) == 1
    brew = result.brews[0].brew
    assert brew.dose_g == 15.0
    assert brew.water_g is None
    assert brew.defect is None


def test_wrapped_export_object(tmp_path):
    export = tmp_path / "wrapped.json"
    export.write_text(json.dumps({"brewLogs": [{"method": "V60", "doseGrams": 16.0}]}))
    assert len(load_export(export).brews) == 1
