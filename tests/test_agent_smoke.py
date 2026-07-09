"""Live-agent smoke test. Requires a running Ollama server with qwen3.

Run with: uv run pytest -m ollama
"""

import pytest

from brewtrace.models import Direction, Variable

pytestmark = pytest.mark.ollama


def test_agent_canonical_diagnosis():
    from brewtrace.agent import build_agent, run_diagnosis

    agent = build_agent()
    advice, result = run_diagnosis(
        agent, "I brewed 16g coffee / 250g water, V60, 94C, 3:45 drawdown, sour and thin"
    )
    assert advice is not None
    # Underextraction: either finer grind or hotter water is defensible.
    assert (advice.variable, advice.direction) in {
        (Variable.GRIND, Direction.FINER),
        (Variable.TEMPERATURE, Direction.INCREASE),
    }
    # The agent must actually have used tools, not answered from priors.
    assert sum(m.call_count for m in result.metrics.tool_metrics.values()) >= 2
