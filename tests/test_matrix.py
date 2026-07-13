from brewtrace.evals.matrix import _summary_row, render_table


def _record(model="test-model", passes=(True, True, False)):
    return {
        "model": model,
        "completed_at": "2026-07-13T00:00:00Z",
        "cases": [
            {
                "case_id": f"case-{i}",
                "passed": p,
                "detail": "d",
                "duration_s": 10.0 + i,
                "input_tokens": 100,
                "output_tokens": 50,
                "tool_calls": 4 if p else 0,
                "used_tools": p,
            }
            for i, p in enumerate(passes)
        ],
    }


def test_summary_row():
    row = _summary_row(_record())
    assert row["pass_rate"] == 2 / 3
    assert row["tool_use_rate"] == 2 / 3
    assert row["median_latency_s"] == 11.0
    assert row["median_tokens"] == 150
    assert row["failures"] == ["case-2"]


def test_render_table_sorted_by_pass_rate():
    good = _record("good", (True, True, True))
    bad = _record("bad", (False, False, True))
    table = render_table([bad, good])
    lines = table.splitlines()
    assert "| Model |" in lines[0]
    assert lines[2].startswith("| good | 100% (3/3) |")
    assert lines[3].startswith("| bad | 33% (1/3) |")
