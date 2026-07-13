"""CLI tests — everything here runs offline (no agent, no collector)."""

import json

import pytest

from brewtrace.app import _beanbench_text, main, run_deterministic
from brewtrace.ingest.beanbench import load_export
from brewtrace.models import parse_brew_log

FIXTURE = "tests/fixtures/beanbench_export.json"


def test_no_args_errors():
    with pytest.raises(SystemExit) as exc:
        main([])
    assert exc.value.code == 2


def test_deterministic_canonical(capsys):
    code = run_deterministic("16g/250g V60, 94C, 3:45 drawdown, sour and thin")
    out = capsys.readouterr().out
    assert code == 0
    assert "sour_thin" in out
    assert "change grind → finer" in out


def test_deterministic_stall_flips_to_temperature(capsys):
    run_deterministic("16g/250g V60, 92C, 5:00 drawdown, sour and thin")
    out = capsys.readouterr().out
    assert "change temperature → increase" in out
    assert "skipped" in out  # the contraindicated grind rule shows up as alternative


def test_main_no_llm_exit_code(capsys):
    assert main(["--no-llm", "16g/250g v60, 94C, 3:00, bitter"]) == 0
    assert "change grind → coarser" in capsys.readouterr().out


def test_beanbench_text_rendering():
    brew = load_export(FIXTURE).brews[0].brew
    text = _beanbench_text(brew, None)
    assert "16g coffee / 250g water" in text
    assert "v60" in text
    assert "3:45 drawdown" in text
    assert "Sour and thin" in text
    # The rendered text must round-trip through the parser.
    reparsed = parse_brew_log(text)
    assert reparsed.dose_g == 16
    assert reparsed.defect is not None


def test_beanbench_text_defect_override():
    brew = load_export(FIXTURE).brews[0].brew
    assert "tasted: bitter" in _beanbench_text(brew, "bitter")


def test_beanbench_no_llm_runs_and_warns(capsys):
    code = main(["--from-beanbench", FIXTURE, "--no-llm", "--all"])
    captured = capsys.readouterr()
    assert code == 0
    assert "Espresso" in captured.err and "pour-over only" in captured.err
    assert captured.out.count("Recommendation (") == 3  # three pour-over entries


def test_beanbench_index_out_of_range(capsys):
    assert main(["--from-beanbench", FIXTURE, "--no-llm", "--index", "99"]) == 1


def test_beanbench_empty_export(tmp_path, capsys):
    empty = tmp_path / "empty.json"
    empty.write_text(json.dumps([{"method": "Espresso"}]))
    assert main(["--from-beanbench", str(empty), "--no-llm"]) == 1


def test_beanbench_missing_file():
    with pytest.raises(FileNotFoundError):
        main(["--from-beanbench", "does-not-exist.json", "--no-llm"])
