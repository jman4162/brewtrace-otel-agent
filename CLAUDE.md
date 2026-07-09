# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project is

**BrewTrace** — a fully local LLM coffee-brewing agent (Strands Agents SDK + Ollama)
where every tool call, retrieval step, and model response is traced with OpenTelemetry.
A user describes a brew; the agent diagnoses it and recommends exactly one controlled
adjustment. Published as a tutorial project (github.com/jman4162); the tutorial point is
agent observability, not coffee.

`background-info.local.md` is a local-only planning note — gitignored, never cite it in
published docs.

## Commands

- `uv sync` — install (dev group included); `uv sync --extra judge` adds strands-agents-evals
- `uv run pytest` — fast suite, never touches an LLM (`addopts = -m 'not ollama'`)
- `uv run pytest -m ollama` — live-agent smoke test (needs Ollama + qwen3)
- `uv run pytest tests/test_x.py::test_name` — single test
- `uv run ruff check .` / `uv run ruff format .`
- `docker compose --profile jaeger up -d` — Jaeger v2, UI :16686, OTLP 4317/4318
- `docker compose --profile lgtm up -d` — Grafana LGTM stack, UI :3000 (one profile at a
  time; both bind 4317/4318)
- `uv run brewtrace "16g/250g V60, 94C, 3:45, sour and thin"` — agent mode (traced)
- `uv run brewtrace --no-llm "…"` — deterministic mode, no Ollama/Docker needed
- `uv run brewtrace --from-beanbench export.json [--all|--index N] [--defect X]`
- `uv run python -m brewtrace.evals.run_evals [--agent] [--model qwen3]`

## Architecture invariant

**All domain logic is pure, typed, LLM-free functions; `@tool` wrappers are thin; the
agent is a routing layer.** Tests and deterministic evals must never require a model.
Keep it that way: new tool = pure function first, `@tool` wrapper at the bottom of the
same file.

- `models.py` — Pydantic domain model + regex parser (`parse_brew_log`, `infer_defect`).
  No strands/otel imports allowed here.
- `tools/recommendation.py` — the rule engine (DEFECT_RULES with contraindication
  guards; priority grind > temperature > ratio > technique > bloom, ONE variable per
  brew). The showcase interaction: sour + stalled drawdown must NOT get "grind finer".
- `tools/brew_math.py`, `tools/recipe_retriever.py` (stdlib tf-idf over `recipes/*.md`),
  `tools/experiment_log.py` (sqlite3, `data/brewtrace.db`).
- `agent.py` — OllamaModel + system prompt. **Two-pass structured output**: prose answer
  first, then a tool-free extraction agent produces `BrewAdvice`. Small models fail
  forced structured output after tool loops; don't "simplify" this back to one pass.
- `telemetry.py` — the only module importing the OTel SDK. `brew_request_span` is the
  manual parent span carrying `brew.*`/`taste.*`/`eval.*` attributes from the
  deterministic parse (the parser runs even in agent mode for exactly this reason).
- `evals/` — cases.yaml (25 cases) + deterministic scorer. Deterministic mode must be
  25/25 by construction; a failure means the rule table and the case table disagree.
- `ingest/beanbench.py` — JSON export adapter for the Beanbench iOS app (same owner).
  Optional feature: core tutorial must work without it.

## Hard-won facts (don't re-derive)

- Default model is **qwen3**: it reliably walks the 4-tool workflow. llama3.1-8B skips
  tools on open-ended prompts (kept as the documented comparison, not the default).
- strands-agents 1.46.0 emits BOTH legacy and current GenAI token attributes
  (`gen_ai.usage.prompt_tokens` and `gen_ai.usage.input_tokens`), and legacy
  `gen_ai.system`. Span names are current (`invoke_agent`, `chat`, `execute_tool <name>`).
  GenAI semconv is Development-status; docs/architecture.md documents observed behavior.
- Strands METRICS are framework-named (`strands_event_loop_input_tokens`,
  `strands_tool_call_count`, …), NOT the spec's `gen_ai.client.*` — verified in
  Prometheus. Don't "fix" docs to claim gen_ai.client metrics exist.
- Live eval baseline (qwen3-8B, July 2026): 20/25. Failure buckets: extraction maps
  "more coffee" → ratio/increase (wrong direction), priority drift, guessing on
  missing data.
- Custom attributes go in `brew.*` / `taste.*` / `eval.*`, never `gen_ai.*`.
- `Agent.structured_output()` is deprecated; use `agent(prompt, structured_output_model=M)`
  → `result.structured_output`.
- Strands streams model text to stdout unless `Agent(callback_handler=None)`.
- Exact version pins matter (tutorial repo): strands-agents==1.46.0, Jaeger 2.19.0.
  The README "Tested with" table is the dated baseline — update it when bumping pins.
- If `import brewtrace` suddenly fails (`ModuleNotFoundError`) while the editable
  install looks fine: check `ls -lO .venv/lib/python3.12/site-packages/*.pth` for the
  macOS `hidden` flag. Python 3.12's site module silently skips UF_HIDDEN .pth files.
  Fix: `chflags nohidden .venv/lib/python3.12/site-packages/*.pth`. uv occasionally
  creates them hidden on this machine.
