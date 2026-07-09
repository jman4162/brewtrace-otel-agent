# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project status: greenfield

No code exists yet. The design source of truth is `background-info.local.md` (a local-only
planning note — keep it out of git and don't cite it in published docs). This file records
the intended design and conventions; update it as the real implementation lands and diverges.

## What this project is

**BrewTrace** — a fully local LLM coffee-brewing agent where every tool call, retrieval
step, and model response is traced with OpenTelemetry. A user describes a brew
("16g/250g V60, 94°C, 3:45 drawdown, sour and thin") and the agent diagnoses it and
recommends one controlled adjustment. The tutorial point is agent observability: tracing
the full reasoning-and-tool-use path, not just logging the final answer.

Published as a personal tutorial project (github.com/jman4162). Fully local: no cloud
APIs, no credentials, nothing work-related.

## Stack and tooling conventions

- Python, managed with **uv** (`pyproject.toml`, `uv sync`, `uv run …`)
- **ruff** for linting and formatting; **pytest** for tests
- **Strands Agents SDK** for the agent loop (native Ollama support and built-in OTel tracing);
  optional LangGraph comparison in a separate folder as the final milestone
- **Ollama** for the LLM (`ollama/qwen3` or `ollama/llama3.1`)
- **OpenTelemetry** → OTLP → **Jaeger**, run via `docker-compose.yml` (OTel Collector + Jaeger)
- **SQLite** for the experiment logger; plain local markdown files under `recipes/` for RAG

Commands (once scaffolded):

- `uv sync` — install/update the environment
- `uv run pytest` — run tests; single test: `uv run pytest tests/test_x.py::test_name`
- `uv run ruff check .` and `uv run ruff format .`
- `docker compose up -d` — start the OTel Collector + Jaeger stack
- `uv run python -m brewtrace.app` — run the agent CLI (entry point: `src/brewtrace/app.py`)

## Planned architecture

Layout: `src/brewtrace/` with `app.py` (entry), `agent.py` (agent loop), `telemetry.py`
(OTel setup/export), `models.py`, `tools/` (`brew_math.py`, `recipe_retriever.py`,
`experiment_log.py`, `recommendation.py`), and `evals/` (`cases.yaml`, `run_evals.py`).
Supporting dirs: `recipes/` (markdown RAG corpus), `docs/`, `notebooks/`.

Trace shape per request:

```
brewtrace.request
├── llm.plan
├── tool.calculate_brew_ratio
├── tool.retrieve_recipe_notes
├── tool.recommend_adjustment
├── llm.final_response
└── eval.score_recommendation
```

Span attribute namespaces: `brew.*` (method, dose_g, water_g, ratio, grinder,
drawdown_seconds), `taste.primary_defect`, `agent.*` (tool_count, model).
Metrics: `agent.request.latency_ms`, `agent.llm.latency_ms`, `agent.tool.latency_ms`,
`agent.tool.error_count`, `agent.retrieval.documents_used`, `agent.eval.pass_rate`.

## Build order (milestones)

1. Deterministic CLI — parse a brew log, compute ratio/drawdown/likely issue, no LLM
2. Strands + Ollama agent with tool calling
3. OpenTelemetry traces exported to Jaeger
4. Local RAG over `recipes/*.md`
5. Eval harness: 20–30 troubleshooting cases scored for directional sanity
6. LangGraph comparison version (separate folder)

Keep tools deterministic and testable independent of the LLM — the eval harness scores
whether recommendations are directionally sane (one controlled variable changed).
