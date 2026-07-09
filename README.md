# BrewTrace: an observable local coffee-brewing agent

A fully local LLM coffee assistant where every tool call, retrieval step, and model
response is traced with OpenTelemetry. Built with **Strands Agents + Ollama**; traces
viewed in **Jaeger** or **Grafana**. No cloud APIs, no SaaS, no API keys.

Describe a brew:

> I brewed 16g coffee / 250g water, V60, 94°C, 3:45 drawdown. It tasted sour and thin.

BrewTrace diagnoses it and recommends **one** controlled adjustment — and the trace
shows exactly which tools ran, what notes were retrieved, and why it chose grind over
temperature.

Most agent tutorials stop once the agent gives an answer. This project is about the
other half: instrumenting the full agent loop so you can inspect which tools were
called, what context was retrieved, how long each step took, and whether the
recommendation was reasonable.

## What this teaches

- Building a local agent with the Strands Agents SDK
- Running a tool-calling LLM with Ollama (and measuring which local models can
  actually route through tools)
- Wrapping deterministic, testable functions as agent tools
- Local retrieval over markdown notes — a transparent tf-idf scorer, no vector DB
- Exporting OpenTelemetry traces and metrics under the GenAI semantic conventions
- Inspecting agent traces in Jaeger; token/latency metrics in Grafana
- Evaluating agent recommendations with a deterministic scorer, plus an optional
  local LLM-as-judge

## Quickstart: zero to a traced agent

Prerequisites: [uv](https://docs.astral.sh/uv/), Docker, [Ollama](https://ollama.com).

```bash
git clone https://github.com/jman4162/brewtrace-otel-agent && cd brewtrace-otel-agent
uv sync
ollama pull qwen3

# start Jaeger (v2 ingests OTLP directly — no collector service needed)
docker compose --profile jaeger up -d

# diagnose a brew
uv run brewtrace "16g/250g V60, 94C, 3:45 drawdown, sour and thin"

# open http://localhost:16686 → service "brewtrace" → newest trace
```

No Docker or no Ollama handy? The deterministic mode needs neither:

```bash
uv run brewtrace --no-llm "16g/250g V60, 94C, 3:45 drawdown, sour and thin"
```

## What a trace looks like

```
brewtrace.request                              ← brew.method, brew.ratio, taste.primary_defect
└── invoke_agent Strands Agents                ← model id, tool list, total token usage
    └── execute_event_loop_cycle
        ├── chat                               ← per-call tokens, time-to-first-token
        ├── execute_tool calculate_brew_ratio
        ├── execute_tool assess_drawdown_time
        ├── execute_tool retrieve_recipe_notes ← the exact notes the model saw
        └── execute_tool recommend_adjustment
    └── execute_event_loop_cycle               ← final answer
```

The root span's `brew.*` attributes come from a deterministic parser, so traces are
queryable no matter what the model did: filter `taste.primary_defect=sour_thin` or
`eval.passed=false` in the Jaeger search box. See
[docs/architecture.md](docs/architecture.md) for the design and the GenAI
semantic-conventions notes (strands 1.46 emits both legacy and current token
attribute names — worth reading before you build dashboards).

## Evals

25 troubleshooting cases with acceptable-adjustment sets live in
`src/brewtrace/evals/cases.yaml`:

```bash
uv run python -m brewtrace.evals.run_evals            # deterministic pipeline: must be 25/25
uv run python -m brewtrace.evals.run_evals --agent    # live agent, threshold 80%
```

Agent-mode eval runs are traced with `eval.case_id` and `eval.passed` attributes, so
every failure links to the full trace of what the model actually did. Measured with
qwen3-8B (July 2026): **20/25** — and the traces sort the five failures into
extraction-schema mapping errors, priority drift, and guessing on missing data (see
[docs/tutorial.md](docs/tutorial.md)). An optional LLM-as-judge pass (local Ollama
judge, no Bedrock) scores rationale quality:
`uv sync --extra judge && uv run python -m brewtrace.evals.judge`.

## Metrics

```bash
docker compose --profile lgtm up -d     # Grafana LGTM stack (stop the jaeger profile first)
uv run brewtrace --metrics "16g/250g V60, 94C, 3:45, sour and thin"
# Grafana at http://localhost:3000 (admin/admin) → Explore → Prometheus
```

Strands emits its own instruments — `strands_event_loop_input_tokens` /
`output_tokens` histograms, `strands_tool_call_count` / `success` / `error` counters,
per-tool durations, time-to-first-token — not the GenAI semconv `gen_ai.client.*`
metric names the spec defines (verified against strands-agents 1.46.0; see
[docs/architecture.md](docs/architecture.md)). BrewTrace adds `brew.recommendations`
(counter, by recommended variable) and `brew.request.duration` (histogram). Jaeger
stores traces only — the `lgtm` profile exists so the metrics have somewhere to land.
If port 3000 is taken on your machine: `GRAFANA_PORT=3001 docker compose --profile lgtm up -d`.

## Use your real brew history (Beanbench)

If you log brews with [Beanbench](https://beanbench.coffee) (iOS), export your data as
JSON (Settings → Export) and diagnose real brews:

```bash
uv run brewtrace --from-beanbench export.json            # newest pour-over entry
uv run brewtrace --from-beanbench export.json --all      # every pour-over entry, traced
uv run brewtrace --from-beanbench export.json --defect bitter   # override taste inference
```

Beanbench has no structured defect field, so the taste defect is inferred from your
tasting notes; espresso and immersion entries are skipped.

## Development

```bash
uv run pytest              # fast: never touches an LLM
uv run pytest -m ollama    # live-agent smoke test (needs Ollama + qwen3)
uv run ruff check . && uv run ruff format .
```

Tools are thin `@tool` wrappers over pure functions (`src/brewtrace/tools/`), so the
whole diagnosis rule table is unit-tested without a model. The rule engine itself is
`src/brewtrace/tools/recommendation.py` — grind before temperature before ratio, one
variable per brew, with guards for the interactions (sour + stalled drawdown must
*not* get "grind finer").

## Tested with

| Component | Version |
|---|---|
| strands-agents | 1.46.0 |
| Jaeger | 2.19.0 |
| grafana/otel-lgtm | latest (July 2026) |
| Ollama model | qwen3 (8B); llama3.1 documented as a weaker-tool-calling comparison |
| Python | 3.10+ |

Exact dependency pins are in `pyproject.toml`/`uv.lock`. Tutorials rot at the
dependency layer first; if something breaks on newer versions, the dated table above
is the known-good baseline.

## FAQ

**Why coffee?** The domain is deterministic, local, and physically grounded — and the
question "why did it recommend a grind change instead of a temperature change?" is a
real observability problem, not a toy one.

**Why no vector database?** A tf-idf scorer over markdown sections is ~80 lines,
dependency-free, and every retrieval decision is legible in a trace. The tutorial is
about observability, not embeddings.

**Does it work with other Ollama models?** Any tool-capable model via `--model`. The
eval harness quantifies how well a given model routes through tools — qwen3 walks all
four tools reliably; llama3.1-8B usually skips them and answers from its priors.

**Why is there a second small trace after each diagnosis?** Structured output runs as
a separate tool-free extraction pass, because small local models routinely fail a
forced structured-output call at the end of a long tool loop.

## License

MIT
