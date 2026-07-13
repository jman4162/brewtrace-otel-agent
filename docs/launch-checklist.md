# Launch checklist

Repo-side items to do on GitHub, plus site-side recommendations. Updated July 2026
after increment 2 (model matrix, provisioned dashboard, eval semconv events).

## Done

- [x] Repo description + topics set (via gh CLI)
- [x] Blog post published and linked both directions
  (john-hodge.com/blog/strands-ollama-opentelemetry-local-agent-tracing/)
- [x] `feed.xml` fixed — valid RSS 2.0
- [x] `screenshots/jaeger-trace.png` captured and embedded in README
- [x] CI badge green; MIT license
- [x] Provisioned Grafana dashboard ships with the `lgtm` profile

## Outstanding (manual, web UI)

- [ ] Pin the repo on the GitHub profile (no API for profile pins)
- [ ] Social-preview image (repo Settings → General; the annotated Jaeger screenshot
  or the Grafana dashboard works well)
- [ ] Remaining screenshots:
  - `screenshots/eval-dashboard.png` — the provisioned Grafana dashboard with matrix
    data loaded (`GRAFANA_PORT=3001 docker compose --profile lgtm up -d`, then run
    the matrix with `--metrics`)
  - `screenshots/jaeger-eval-filter.png` — Jaeger search filtered on `eval.passed=false`
  - `screenshots/tempo-trace.png` — same trace shape in Tempo

## Distribution (cheapest traction lever — currently zero syndication)

- [ ] Cross-post the launch post to dev.to with `rel=canonical` to john-hodge.com
  (the Strands/observability audience actively publishes there)
- [ ] Share to r/LocalLLaMA (fully-local + Ollama angle) and Hacker News
- [ ] When the model-comparison post ships, same circuit — the trace-backed table is
  the differentiator against the SEO listicles

## Blog post #2 (drafted)

- Source: `docs/model-comparison.md`. Suggested title: *"Which local models can
  actually call tools? A trace-backed comparison"*, slug
  `ollama-tool-calling-comparison-traced`.
- The gap: "Ollama tool calling benchmark" queries return listicles with no
  reproducible methodology; nobody ships the traces. This post does.

## Follow-up posts / features queued

1. **"Tracing MCP tool calls with OpenTelemetry"** — next increment: FastMCP server
   re-exporting the brew tools + trace-context propagation across the process
   boundary via MCP `_meta`. Gate on a half-day spike: does Strands' MCPClient link
   spans to the FastMCP server span? Connects to agentic-phased-array-builder.
2. **LangGraph comparison** — same workflow as an explicit graph, traced via
   openinference-instrumentation-langchain into the same backends
   (`langgraph_version/` folder; catches both search audiences).
3. Multi-turn conversation tracing (`gen_ai.conversation.id`, session-level linking) —
   needs a small design pass around the fresh-agent-per-request + two-pass extractor.
