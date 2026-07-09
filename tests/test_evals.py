"""Every eval case must pass against the deterministic pipeline.

If one fails, either the rule table or the case is wrong — the test output
says which pair disagreed so you can decide.
"""

import pytest

from brewtrace.evals.run_evals import run_deterministic
from brewtrace.evals.scoring import load_cases

CASES = load_cases()


def test_case_count():
    assert len(CASES) >= 20


@pytest.mark.parametrize("case", CASES, ids=[c.id for c in CASES])
def test_deterministic_pipeline_passes(case):
    results = run_deterministic([case])
    assert results[0].passed, results[0].detail
