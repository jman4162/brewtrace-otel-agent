# BrewTrace: an observable local coffee-brewing agent

A fully local LLM coffee assistant where every tool call, retrieval step, and model
response is traced with OpenTelemetry. Built with Strands Agents + Ollama; traces viewed
in Jaeger or Grafana. No cloud APIs, no SaaS, no API keys.

Describe a brew:

> I brewed 16g coffee / 250g water, V60, 94°C, 3:45 drawdown. It tasted sour and thin.

BrewTrace diagnoses it and recommends **one** controlled adjustment — and the trace shows
exactly which tools ran, what notes were retrieved, and why it chose grind over temperature.

## What this teaches

- Building a local agent with the Strands Agents SDK
- Running a tool-calling LLM with Ollama
- Wrapping deterministic, testable functions as agent tools
- Local retrieval over markdown notes (no vector DB)
- Exporting OpenTelemetry traces and metrics (GenAI semantic conventions)
- Inspecting agent traces in Jaeger
- Evaluating agent recommendations with a deterministic scorer

## Status

Under construction — milestones:

- [ ] M0: project scaffold, Jaeger via docker compose
- [ ] M1: deterministic brew diagnosis (no LLM)
- [ ] M2: Strands + Ollama agent with tools
- [ ] M3: OpenTelemetry traces in Jaeger
- [ ] M4: eval harness
- [ ] M4.5: Beanbench brew-log import
- [ ] M5: metrics + Grafana LGTM stack
- [ ] M6: tutorial + launch

## Quickstart (so far)

```bash
uv sync
docker compose up -d   # Jaeger UI at http://localhost:16686
uv run pytest
```
