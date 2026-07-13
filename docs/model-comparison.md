# Which local models can actually call tools?

A trace-backed comparison of Ollama models on the BrewTrace eval suite. Every number
in the table links back to OpenTelemetry traces you can reproduce locally — not a
vibes-based listicle.

## Methodology

- **Task**: 25 pour-over troubleshooting cases (`src/brewtrace/evals/cases.yaml`),
  each with a set of acceptable (variable, direction) adjustments. The agent must
  route through four tools (ratio → drawdown → retrieval → rule engine) and recommend
  exactly one change.
- **Scoring is deterministic**: pass iff the structured recommendation's
  (variable, direction) is in the case's acceptable set. No LLM judge in the loop.
- **Tool-use rate**: fraction of cases where the model made ≥2 real tool calls —
  i.e., actually consulted the tools rather than answering from its priors. The
  prescribed workflow is 4 calls.
- **Two-pass structured output**: the tool-using agent answers in prose; a second
  tool-free call extracts the structured recommendation. Small local models routinely
  fail a forced structured-output call at the end of a tool loop, so this isolates
  tool-routing ability from schema-emission ability (imperfectly — see failure
  taxonomy below).
- **Every case is traced**: `brewtrace.request` span with `eval.case_id`,
  `eval.model`, `eval.passed` attributes and a `gen_ai.evaluation.result` span event
  (OTel GenAI semconv). Filter `eval.passed=false` in Jaeger/Tempo to replay any
  failure.
- **Reproduce**:
  `uv run python -m brewtrace.evals.matrix --models qwen3,llama3.1,llama3.2 --metrics`
  — raw per-case results land in `data/matrix/<model>.json`; regenerate the table with
  `--report`. Models without the `tools` capability (per `ollama show`) are refused,
  not shown as 0% rows.
- **Hardware**: Apple Silicon Mac, Ollama defaults, temperature 0.2, single run per
  model (July 2026). Latency numbers include model inference and the extraction pass;
  treat them as relative, not absolute.

## Results

<!-- MATRIX_TABLE -->

## Failure taxonomy

<!-- FAILURE_NOTES -->

## Caveats

- Single run per model; local-model tool calling has run-to-run variance. The traces
  make individual failures inspectable, but the pass rates carry ±1-2 case noise.
- The extraction pass can misattribute a *correct* prose recommendation (observed:
  "use more coffee" extracted as ratio/increase — wrong direction for a right answer).
  Failures are therefore an upper bound on end-to-end error, not pure tool-routing
  error; the per-case traces distinguish the two.
- Latency includes qwen-family thinking tokens, which inflate wall-clock relative to
  non-reasoning models.
