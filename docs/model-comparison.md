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

Run: July 13, 2026 · strands-agents 1.46.0 · Apple Silicon, Ollama local.

| Model | Pass rate | Tool-use rate | Median latency | Median tokens/case |
|---|---|---|---|---|
| qwen3 | 88% (22/25) | 96% | 168s | 4561 |
| qwen3.5:9b (think=off) | 68% (17/25) | 96% | 17s | 4268 |
| qwen3.5:9b | 32% (8/25) | 100% | 103s | 5507 |
| llama3.1 | 8% (2/25) | 0% | 30s | 954 |
| llama3.2 | 0% (0/25) | 92% | 9s | 3042 |

Headline readings:

- **Pass rate and tool-use rate are different axes.** llama3.2 calls tools on 92% of
  cases and still passes zero; llama3.1 barely calls them at all. "Supports tool
  calling" (the Ollama capability flag — all five have it) tells you almost nothing
  about whether a model can execute a four-step tool workflow.
- **qwen3's thinking buys accuracy at 10× the latency.** 88% at 168s median vs
  qwen3.5-no-think's 68% at 17s. Which one you want depends entirely on whether a
  human is waiting for the answer.
- **Default qwen3.5 loses 36 points to an interop bug, not to reasoning.** See the
  taxonomy below.

## Failure taxonomy

Every failure below is one Jaeger/Tempo query away (`eval.passed=false`,
`eval.model=<model>`), and each mode was diagnosed by reading traces, not by
guessing:

**llama3.1 — answers from its priors (20 of 23 failures).** Zero tool calls on 25/25
cases; it writes plausible coffee advice from training data and ignores the
prescribed workflow entirely. The two "passes" are cases where its priors happen to
match the rule engine. This is the failure mode that makes agent observability
non-optional: the answers *look* fine.

**llama3.2 — routes but can't follow (23 of 25 failures).** The 3B model dutifully
calls the tools (fast: 9s median), then recommends something other than what
`recommend_adjustment` returned — usually a superficially related variable. Tool
*calling* is not tool *following*.

**qwen3.5 default — the silent thinking bug (16 of 17 failures).** The model calls
the tools correctly, then ends its turn with an **empty final message**: the response
reports ~200+ output tokens but zero content blocks — the tokens went to thinking
that never surfaced as text. The extraction pass receives an empty answer and maps it
to "no change". Disabling thinking (`think: false` via Ollama's API) eliminates the
mode and doubles the pass rate. The trace made this legible: token counts on the
`chat` span with no `gen_ai.choice` content is exactly what "the model thought but
never spoke" looks like.

**qwen3 / qwen3.5-no-think — genuine judgment errors (the remaining handful).** The
same three buckets measured in the launch post: direction-semantics extraction misses
("use more coffee" → ratio/*increase*), priority drift (a defensible second-choice
adjustment over the rule table's first choice), and guessing when data is missing
instead of asking for more.

## Caveats

- Single run per model; local-model tool calling has run-to-run variance. The traces
  make individual failures inspectable, but the pass rates carry ±1-2 case noise.
- The extraction pass can misattribute a *correct* prose recommendation (observed:
  "use more coffee" extracted as ratio/increase — wrong direction for a right answer).
  Failures are therefore an upper bound on end-to-end error, not pure tool-routing
  error; the per-case traces distinguish the two.
- Latency includes qwen-family thinking tokens, which inflate wall-clock relative to
  non-reasoning models.
