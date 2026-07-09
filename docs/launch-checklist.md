# Launch checklist

Repo-side items to do on GitHub after pushing, plus site-side recommendations.

## GitHub repo settings

- **Description:** `Fully local LLM coffee-brewing agent traced end-to-end with
  OpenTelemetry — Strands Agents + Ollama + Jaeger/Grafana, no cloud APIs, no SaaS.`
- **Topics:** `opentelemetry`, `strands-agents`, `ollama`, `llm-observability`,
  `ai-agents`, `genai`, `jaeger`, `grafana`, `local-llm`, `tracing`,
  `agent-evaluation`, `python`
- Pin the repo on the profile.
- Add a social-preview image (annotated Jaeger trace screenshot works well).
- Screenshots to capture for README/blog once running:
  - `screenshots/jaeger-trace.png` — full span tree of one diagnosis, attributes panel
    open on `brewtrace.request`
  - `screenshots/jaeger-eval-filter.png` — search filtered on `eval.passed=false`
  - `screenshots/grafana-tokens.png` — Prometheus `gen_ai_client_token_usage` histogram
  - `screenshots/tempo-trace.png` — same trace shape in Tempo

## Blog post (john-hodge.com)

- Source draft: `docs/tutorial.md`. Suggested title: *"Tracing a Local LLM Agent End
  to End: Strands Agents + Ollama + OpenTelemetry (No SaaS Required)"*, slug
  `strands-ollama-opentelemetry-local-agent-tracing`.
- Target the gap: vendor blogs own "LLM observability" head terms but nothing covers
  the fully-local Strands + Ollama + open-source-backend path. Name the exact stack in
  the title, intro, and headings.
- Link repo ↔ post both directions (README already links the blog; add the repo link
  in the post's first section and CTA).

## Site-side recommendations (separate effort, website repo)

- `feed.xml` currently serves the site's HTML fallback, not XML — there is no working
  RSS feed. Fixing it is the single highest-leverage distribution change.
- Cross-post to dev.to and/or Medium with `rel=canonical` back to john-hodge.com; the
  audience for this topic already lives there.
- Follow-up posts that build on this repo's authority:
  1. "Tracing MCP tool calls with OpenTelemetry" — connects to the existing
     agentic-phased-array-builder MCP work.
  2. LangGraph comparison: same agent as an explicit graph, same traces
     (`langgraph_version/` folder, catches both search audiences).
  3. "Which local models can actually call tools?" — extend the eval harness across
     qwen3 / llama3.1 / others; publish the table.
