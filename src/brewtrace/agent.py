"""Strands agent assembly: model, tools, system prompt."""

from __future__ import annotations

from strands import Agent
from strands.models.ollama import OllamaModel

from brewtrace.models import BrewAdvice
from brewtrace.tools.brew_math import assess_drawdown_time, calculate_brew_ratio
from brewtrace.tools.experiment_log import get_recent_experiments, log_brew_experiment
from brewtrace.tools.recipe_retriever import retrieve_recipe_notes
from brewtrace.tools.recommendation import recommend_adjustment

DEFAULT_MODEL = "qwen3"
DEFAULT_HOST = "http://localhost:11434"

SYSTEM_PROMPT = """You are BrewTrace, a pour-over coffee troubleshooting assistant.

You MUST NOT answer from your own coffee knowledge. Before answering, always
call these tools, in this order:
1. calculate_brew_ratio with the dose and water weights
2. assess_drawdown_time if a drawdown or brew time was given
3. retrieve_recipe_notes for the method and the described taste problem
4. recommend_adjustment with the brew details as JSON

Then answer using only what the tools returned:
- Recommend exactly the ONE variable change that recommend_adjustment chose.
  Never change two variables.
- Be concise: a one-line diagnosis, the single change, and why.
"""


def build_agent(
    model_id: str = DEFAULT_MODEL,
    host: str = DEFAULT_HOST,
    temperature: float = 0.2,
) -> Agent:
    model = OllamaModel(
        host=host,
        model_id=model_id,
        temperature=temperature,
        keep_alive="10m",
    )
    return Agent(
        model=model,
        system_prompt=SYSTEM_PROMPT,
        callback_handler=None,  # don't stream model text to stdout
        tools=[
            calculate_brew_ratio,
            assess_drawdown_time,
            retrieve_recipe_notes,
            recommend_adjustment,
            log_brew_experiment,
            get_recent_experiments,
        ],
    )


EXTRACTOR_PROMPT = """You convert a coffee-brewing recommendation into structured data.
Report exactly what the recommendation says — do not add your own judgment."""


def _result_text(result) -> str:
    content = getattr(result.message, "get", lambda *_: None)("content") or []
    parts = [block.get("text", "") for block in content if isinstance(block, dict)]
    return "\n".join(p for p in parts if p) or str(result)


def run_diagnosis(agent: Agent, brew_text: str):
    """Run one diagnosis; returns (BrewAdvice, AgentResult).

    Two passes: the tool-using agent answers in prose, then a tool-free call
    extracts the structured BrewAdvice. Small local models (llama3.1-8B)
    routinely fail a forced structured-output tool call at the end of a long
    tool loop, so asking for structure separately is far more reliable.
    """
    # Small local models follow tool instructions in the user turn far more
    # reliably than in the system prompt, so the workflow is restated here.
    result = agent(
        f"Diagnose this brew and recommend the one change to make next.\n"
        f"Brew: {brew_text}\n\n"
        f"Work through the tools in order before answering: calculate_brew_ratio, "
        f"assess_drawdown_time, retrieve_recipe_notes, then recommend_adjustment. "
        f"Report the single adjustment that recommend_adjustment returns."
    )
    answer = _result_text(result)

    extractor = Agent(
        model=agent.model, system_prompt=EXTRACTOR_PROMPT, tools=[], callback_handler=None
    )
    extraction = extractor(
        f"Structure this brew recommendation:\n\n{answer}",
        structured_output_model=BrewAdvice,
    )
    return extraction.structured_output, result
