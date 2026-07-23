# Hugging Face Inference Providers

The application uses the Hugging Face router's OpenAI-compatible API at
`https://router.huggingface.co/v1`. It reuses the generic HTTP transport while keeping provider
routing, discovery, structured-output compatibility, cost, and audit behavior explicit.

Hugging Face documentation:

- [Inference Providers](https://huggingface.co/docs/inference-providers/en/index)
- [Router model API](https://huggingface.co/docs/inference-providers/en/hub-api)
- [Structured output](https://huggingface.co/docs/inference-providers/en/guides/structured-output)
- [Pricing and billing](https://huggingface.co/docs/inference-providers/pricing)

## Token and configuration

Create a fine-grained Hugging Face user token with **Make calls to Inference Providers**
permission. Store it only in the environment or an uncommitted `.env`. Tokens are represented by
`SecretStr`, used only in the authorization header, and never included in cache keys, model-run
rows, reports, resume commands, or logs.

```dotenv
LLM_PROVIDER=huggingface
HF_TOKEN=hf_replace_me
HF_ROUTER_BASE_URL=https://router.huggingface.co/v1
HF_ANALYZER_MODEL=Qwen/Qwen2.5-7B-Instruct
HF_VERIFIER_MODEL=Qwen/Qwen3-8B
HF_PROVIDER_POLICY=cheapest
HF_ANALYZER_PROVIDER=
HF_VERIFIER_PROVIDER=
HF_ROUTING_SUFFIX_ENABLED=true
HF_REQUEST_TIMEOUT_SECONDS=120
HF_MAX_RETRIES=3
HF_RETRY_BASE_SECONDS=2
HF_USE_JSON_SCHEMA=true
HF_ALLOW_JSON_OBJECT_FALLBACK=true
HF_ALLOW_PROMPT_JSON_FALLBACK=true
HF_MAX_OUTPUT_TOKENS_ANALYZER=1200
HF_MAX_OUTPUT_TOKENS_VERIFIER=700
HF_EXTRA_BODY_JSON={}
HF_RUN_BUDGET_USD=20
HF_STOP_BEFORE_BUDGET_USD=19
HF_REQUIRE_BUDGET_CONFIRMATION=false
HF_ALLOW_UNKNOWN_COST=true
HF_MODEL_LIST_CACHE_TTL_SECONDS=300
HF_MODEL_LIST_CACHE_PATH=var/cache/hf_models.json
HF_LIVE_TEST_MAX_COST_USD=0.10
RUN_HF_LIVE_TESTS=false
EVALUATION_CHECKPOINT_EVERY=10
DRY_RUN=true
```

Provider-specific values take precedence:

| Effective value | First choice | Compatibility fallback | Final default |
|---|---|---|---|
| Router token | non-empty `HF_TOKEN` | `LLM_API_KEY` | none; authentication fails closed |
| Router URL | non-empty `HF_ROUTER_BASE_URL` | `LLM_BASE_URL` | `https://router.huggingface.co/v1` |
| Analyzer model | non-empty `HF_ANALYZER_MODEL` | `ANALYZER_MODEL` | canonical Qwen2.5 HF ID |
| Verifier model | non-empty `HF_VERIFIER_MODEL` | `VERIFIER_MODEL` | canonical Qwen3 HF ID |

When `LLM_PROVIDER` is omitted, a non-empty `LLM_BASE_URL` selects `openai_compatible`; otherwise
the deterministic demo backend is retained for backward compatibility. `HF_TOKEN` and other
`HF_*` settings do not implicitly select Hugging Face; set `LLM_PROVIDER=huggingface`. Explicit
`--analyzer-model` and `--verifier-model` flags override the stage models only for the evaluation
or smoke-test command on which they appear.

`HF_EXTRA_BODY_JSON` must be one object. It may contain advanced provider-specific fields but
cannot override `model`, `messages`, `response_format`, `temperature`, `max_tokens`, `stream`, or
authorization. Its values are not logged or persisted; only a hash affects inference caching.

## Routing and discovery

The route resolver stores both the base and routed IDs. Examples:

```text
Qwen/Qwen2.5-7B-Instruct:cheapest
Qwen/Qwen3-8B:fastest
Qwen/Qwen3-8B:cerebras
```

An explicit analyzer or verifier provider wins over `HF_PROVIDER_POLICY`. Analyzer and verifier
routes are resolved independently; the application never assumes both models share a provider.
Disable suffixes only with `HF_ROUTING_SUFFIX_ENABLED=false` for debugging.

```bash
python -m snoc_agent.cli.main models list
python -m snoc_agent.cli.main models list --all --refresh
python -m snoc_agent.cli.main models list --json
python -m snoc_agent.cli.main models check
```

The catalog cache is keyed by router URL and expires after
`HF_MODEL_LIST_CACHE_TTL_SECONDS`. Missing metadata remains missing. `models check` fails when a
base model or explicit route is unavailable, reports catalog alternatives, and never silently
changes the configured model.

Availability, provider status, pricing, context limits, throughput, latency, and structured-output
flags are displayed only when supplied by `/models`. They can change between discovery and an
inference request.

## Structured output and Qwen3 reasoning

Analyzer and verifier schemas come from Pydantic `model_json_schema()`.

1. With the default `HF_USE_JSON_SCHEMA=true`, send strict
   `response_format.type=json_schema`. Disabling that compatibility switch starts at JSON-object
   mode and therefore cannot claim a schema guarantee.
2. If and only if the provider explicitly rejects that format and the fallback is enabled, retry
   with `json_object`.
3. If and only if both structured formats are rejected, include the schema in a JSON-only prompt.
4. In prompt mode, permit at most one malformed-output repair.
5. Strictly validate every successful response with Pydantic.

Each model run stores schema name/hash/body, actual mode, fallback reason, parse attempts, and
validation errors. JSON-object and prompt modes are not reported as schema-guaranteed.

Hugging Face calls do not automatically send `QWEN3_ENABLE_THINKING` or chat-template-specific
parameters. The router may select providers with different extension support. Reasoning returned
in `reasoning`, `reasoning_content`, `analysis`, or a leading `<think>` block is stored separately;
only final content is parsed as the structured answer.

The local `openai_compatible` provider retains the existing configurable Qwen chat-template
behavior for servers that support it.

## Errors and retries

Final failures use these stable categories:

```text
authentication, permission, rate_limit, timeout,
provider_unavailable, model_unavailable, invalid_request,
structured_output_unsupported, malformed_output,
budget_exhausted, unknown
```

Only rate limits, timeouts, and temporary 502/503/504 provider failures are retried. Backoff is
exponential with jitter, and `Retry-After` takes precedence. Authentication, permission, unknown
model, invalid parameters, bounded schema-validation failure, and budget exhaustion are not
retried. Every transport retry, structured-mode fallback, and prompt repair passes through the
budget guard. Usage and cost are aggregated across every provider response, not just the final
validated response.

## Smoke test and privacy

```bash
python -m snoc_agent.cli.main models smoke-test \
  --analyzer-model Qwen/Qwen2.5-7B-Instruct \
  --verifier-model Qwen/Qwen3-8B
```

The command uses ten synthetic French cases, fake PDVs, and fake phone numbers. It does not build
IMAP, SMTP, or business-API adapters. It validates and persists analyzer/verifier output and writes
`outputs/evaluation/hf_smoke/smoke_report.json`.

Normal workers and evaluations may send real selected email text to an external provider even
when `DRY_RUN=true`; dry-run controls SMTP and business effects, not model data disclosure. Review
provider retention, location, access, and contract terms before using production messages.

## Evaluation cache, resume, and budget

Build the explicit subsets first:

```bash
python -m snoc_agent.cli.main evaluation datasets build \
  --source "labeled_data/labeled data/SMOLDATA_last_1000_reviewed.csv" \
  --output-dir outputs/evaluation
```

Run the small safety subset before the full matrix:

```bash
python -m snoc_agent.cli.main evaluate \
  --dataset outputs/evaluation/safety_regression.jsonl \
  --matrix \
  --use-cache \
  --resume \
  --budget-usd 2 \
  --output-dir outputs/evaluation/hf_safety_smoke

python -m snoc_agent.cli.main evaluate \
  --dataset "labeled_data/labeled data/SMOLDATA_last_1000_reviewed.csv" \
  --matrix \
  --use-cache \
  --resume \
  --budget-usd 20 \
  --output-dir outputs/evaluation/hf_qwen_matrix
```

An explicit pair uses the same persistence, cache, resume, and budget machinery:

```bash
python -m snoc_agent.cli.main evaluate \
  --dataset outputs/evaluation/safety_regression.jsonl \
  --analyzer-model Qwen/Qwen2.5-7B-Instruct \
  --verifier-model Qwen/Qwen3-8B \
  --use-cache \
  --resume \
  --budget-usd 2 \
  --output-dir outputs/evaluation/hf_selected_pair
```

The persistent runner handles both explicit single-pair and matrix commands. The matrix performs
each analyzer model once per input and each verifier model once per unique proposal/context.
Successful cache entries are keyed by stage, base model, resolved route, prompt version, actual
structured mode, generation settings, normalized context, and schema. Transport, provider, and
malformed-output failures are never cached. The original `model_runs` row remains the source of
truth; later `evaluation_inferences` rows reference it.

`--resume` searches for an incomplete run with the same dataset hash, configuration hash, and
output directory. It reuses completed inference rows even with `--no-cache`. Checkpoints are
written every `EVALUATION_CHECKPOINT_EVERY` rows and on clean budget stops or errors.

When `HF_REQUIRE_BUDGET_CONFIRMATION=true`, add `--confirm-budget` after reviewing the
command's `--budget-usd` value. Without it, evaluation fails before discovery or inference. A
known-cost stop returns a machine-readable `budget_stopped` result and secret-free resume command;
it does not persist a failed `model_runs` row for a request that was never sent.

Costs use decimal arithmetic and one of four audited bases:

| Cost basis | Meaning |
|---|---|
| `exact` | The response reports separate input and output costs; their sum is retained. |
| `provider_reported` | The response reports a usable aggregate cost but not both components. |
| `estimated` | Token usage is multiplied by explicit input/output pricing from `/models`. |
| `unknown` | Reported cost, usable pricing, or required usage metadata is missing. |

Missing pricing is never invented. Known cost stops before the threshold.
`HF_ALLOW_UNKNOWN_COST=true` permits unknown-cost calls while preserving warnings, request counts,
and token counts, but it means the local USD ceiling cannot be guaranteed. The provider billing
page is authoritative. For CLI evaluation, the effective stop is the lower of
`HF_STOP_BEFORE_BUDGET_USD` and 95% of `--budget-usd`; `--stop-before-budget-usd` can supply an
explicitly lower value.

## Demo migration and release policy

The historical “194 unsafe” rows were created by the deterministic demo backend over the reviewed
historical dataset. They are not Qwen failures. `evaluation datasets build` reproduces them from the
source hash and writes `demo_unsafe_candidates_manifest.json` plus
`safety_regression.jsonl` plus an unpopulated `demo_vs_real_regression_report.json`. A completed
matrix writes `failure_attribution.json`, distinguishing analyzer extraction mismatches, verifier
disagreement/structured failures, decision-policy failures, and data/ground-truth exclusions.
Real-model categories remain empty for demo runs; Hugging Face measurements are marked explicitly.

Raw model confidence is stored but is not a calibrated correctness probability. Optional `none`,
`logistic`, and `isotonic` calibration accepts only the calibration split and persists its dataset
hash. A run is release-eligible only when both `unsafe_auto_execute_count` and
`validation_pass_but_wrong_count` are zero.

## Opt-in live tests

Normal tests remain offline. Tiny live tests require a token and the explicit enable flag; the
cost cap has a safe default but should be reviewed:

```dotenv
# Repository-root .env, loaded by Settings when pytest imports the live-test module
HF_TOKEN=hf_replace_me
RUN_HF_LIVE_TESTS=true
HF_LIVE_TEST_MAX_COST_USD=0.10
```

```bash
pytest -m hf_live
```

They query `/models`, validate Qwen2.5 and Qwen3 Pydantic output, and construct no mail or business
integration. Before any inference, they require usable input/output pricing for both selected
routes; missing pricing fails the test without spending credits. Unknown-cost inference is disabled
for this live test. Process-environment values override `.env`.
The application CLI's `--env-file` option is not a pytest option. Unmarked tests force
`LLM_PROVIDER=demo`, so a configured `.env` cannot make the normal suite spend credits.
