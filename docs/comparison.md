# Langfuse vs Logfire: draft comparison

Status: draft v4. Langfuse run 1 (stub LLM, 16 traces, 65 observations, 6 errors) is in. Logfire runs 1 and 2 (stub LLM, 32 traces) are in, see `docs/screenshots/logfire-live-view.webp`. Real Claude Haiku 5.5 runs are in both tools: 16 traces each, 4 LLM calls, 1 injected timeout. The rows marked **(UI)** need a check against the screenshots in `docs/screenshots/`.

## Setup

| | Langfuse 5.2 (self-hosted) | Logfire 5.6 (free cloud) |
|---|---|---|
| Hosting | Docker Compose: web, worker, Postgres, ClickHouse, Redis, MinIO | SaaS only on the free tier. Self-hosting is an enterprise offer. |
| Account | Local account and project in your own server | Cloud account, project, and write token |
| Data model | Trace with typed observations: span, generation, tool, agent, and more | OpenTelemetry spans with attributes |
| SDK base | OpenTelemetry under the hood, with its own TracerProvider | OpenTelemetry, sets the global TracerProvider |

## Instrumentation (same pipeline, same span names)

| | Langfuse | Logfire |
|---|---|---|
| Span | `start_as_current_observation(as_type="span", input=...)` | `logfire.span(name, input=...)` |
| LLM call | `as_type="generation"`, `model=...` | plain span plus `gen_ai.*` attributes |
| Tokens | `usage_details={"input", "output"}` | `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens` |
| Cost | `cost_details` per part. The server adds the total (checked). Its price table already knows `claude-haiku-5-5` at $0.10 and $0.50 per 1M tokens, so `cost_details` is optional for known models (checked). | `operation.cost` attribute. This demo sets it by hand. The Logfire integrations, such as `logfire.instrument_anthropic()`, calculate it in the SDK with the `genai-prices` package (read in the SDK source). Price data lives in the client, not the server. **(UI)**: is it shown? |
| Errors | Exception on exit gives OTel status ERROR. The server maps it to level ERROR with the message. No extra code (checked on the server). | Exception and level `error` on exit, no extra code. The live view tags the trace `exception`, and adds a `pydantic` tag for a `ValidationError` (checked). |
| Non-LLM spans (`featurize`, `sklearn.predict`) | Supported, but the UI centers on generations **(UI)** | First-class, same as any span |
| Test hooks | `span_exporter=` and `tracer_provider=` on the client | `capfire` pytest fixture |
| Read API | Server v4 runs in `events_only` mode. `/api/public/traces` returns 404. Use `/api/public/v2/observations` with `fields=` to get usage, cost, and I/O. Score lists also return 404. Read scores with `/api/public/v2/metrics` (view `scores-categorical`), which needs `orderBy` and `config.row_limit` (checked). | Read token and `LogfireQueryClient.query_json_rows(sql)`. Any SQL on the `records` table, for example cost per span name (checked). |
| Trap found | One client for each public key. A second `Langfuse(...)` with the same key reuses the first exporter. | Pending spans in test exports. Filter on `logfire.span_type == "span"`. |

## What each UI shows (fill in after the runs)

| Question | Langfuse | Logfire |
|---|---|---|
| Trace tree with latency per step | **(UI)** | Live view: one row per trace, with a child count badge and a latency bar. 3 children for the scikit-learn path, 4 for the LLM path (checked). Per-step view **(UI)**. |
| Input and output of each step | **(UI)** | **(UI)** |
| Tokens and cost per trace, and in total | Per generation, with the total cost added by the server (checked in the API) **(UI)** | Token badge on the root row, summed from the child `gen_ai.usage.*` (`196 in, 45 out`, checked). No cost in the live view. Trace detail **(UI)**. |
| Find the failed traces | **(UI)** | Red child badge and red latency bar on each failed trace, visible without a filter (checked) |
| Query the data | Metrics API with views and dimensions, no SQL **(UI)** | SQL on all spans, in the UI and through the read API (checked) |
| LLM extras: prompts, scores, datasets, evals | **(UI)** | **(UI)** |
| Agents page | n/a | Lists spans that follow the OpenTelemetry GenAI agent conventions or OpenInference. This router is a pipeline, not an agent, so the page is empty (`docs/screenshots/logfire-agents-empty.webp`). |
| Human labels | Score configs (categorical `true_category`) and an annotation queue in the UI. Items can be added from the API (`scripts/queue_langfuse.py`). | No queue in the SDK. `logfire.experimental.annotations.record_feedback` attaches a label to a span from code. The script `scripts/sync_labels.py` copies the Langfuse labels. |

## Real run numbers (Claude Haiku 5.5)

| | Value |
|---|---|
| Tickets | 16: 8 scikit-learn, 5 sent to the LLM, 2 invalid, 1 LLM timeout |
| LLM latency | 1.4 s to 1.8 s per call (scikit-learn path: under 2 ms) |
| Tokens per call | 476 to 485 in, 42 to 53 out, for tickets of 10 to 20 words. Most input tokens are the system prompt and the output schema. |
| Cost | $0.00029 for 4 calls, about $0.00007 per call |

## Native mode (`--native`): one line of setup instead of a hand-written generation

| | Langfuse | Logfire |
|---|---|---|
| Setup | Give the Anthropic client the Langfuse `TracerProvider` and set `content_mode="content"`. Langfuse exports spans with `gen_ai.*` attributes by default. | `logfire.instrument_anthropic(client)`, plus `uv add genai-prices` for cost |
| LLM span | `anthropic.messages.create`, type GENERATION, under `llm.classify` (checked) | `Message with 'claude-haiku-5-5'` under `llm.classify` (checked in memory) |
| Cost | Calculated on the server from its price table. Splits input, output, cached, cache creation, and reasoning tokens (checked). | Calculated in the SDK by `genai-prices` and sent as `operation.cost`. Same value as the manual adapter (checked). |
| Content | The Anthropic SDK records metadata only by default. You must turn on `content_mode="content"`. | Prompt, system instructions, and answer by default |
| Trap | `messages.parse` shows as `messages.create`. | The span name is a template, not a fixed name. Filter on `gen_ai.request.model`, not on the name. |

## Human labels and accuracy

Labels: 13 tickets labeled by hand in the Langfuse annotation queue, then copied to Logfire with `scripts/sync_labels.py`.

| Path | Langfuse | Logfire |
|---|---|---|
| scikit-learn | 7/9 | 7/9 |
| LLM (Claude Haiku 5.5) | 4/4 | 4/4 |
| Whole router | 11/13 | 11/13 |

Both wrong answers come from scikit-learn above the 0.5 threshold:

| Ticket | Predicted | True | Confidence |
|---|---|---|---|
| T-005, reset email never arrives | account | bug | 0.58 |
| T-008, app still says processing | shipping | bug | 0.68 |

A threshold of 0.7 sends both to the LLM. This is a hypothesis: it is not run, and 13 tickets are too few to tune on.

In Logfire, each label is a record of kind `annotation`, attached to its `route_ticket` span (checked with SQL).

## Draft outline for the post

1. The predictor: a cheap model first, an LLM only when the model is unsure.
2. One `Telemetry` seam, two adapters of about 50 lines each.
3. Setup cost: six containers vs one token.
4. The same trace in both UIs.
5. Cost and tokens: where each tool shows them.
6. Errors: what each tool catches without extra code.
7. Verdict (a hypothesis, confirm after the runs): Langfuse for LLM product work, Logfire for the whole service.
