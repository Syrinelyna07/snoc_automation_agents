# SNOC LangGraph email agent

This repository is the self-contained next-generation project. It retains the tested
`snoc_agent` Python namespace while isolating its package, migrations, Docker image, PostgreSQL
volume, dashboard, journey reports, and graph audit from the legacy application.

The container stack always forces `WORKFLOW_ENGINE=langgraph` and `DRY_RUN=true`. Run the complete
guarded real-mail acceptance suite from the project root:

```bash
scripts/run_real_acceptance.sh
```

The command validates code and configuration, runs all six real IMAP/SMTP journeys with configured
vLLM inference, saves timestamped reports/logs, and stops the new worker through an exit trap. If
the original DSIP checkout is detected (or explicitly configured), it also safely stops and
restarts that legacy worker. The PostgreSQL volume and dashboard on <http://localhost:8502> remain
available for audit.

See [TEAM_HANDOFF.md](TEAM_HANDOFF.md) before the first push or teammate setup. In particular,
never commit `.env`, raw mail under `var/`, or acceptance reports under `outputs/`.

---

## Preserved implementation notes

This repository now contains a first production-style, safety-first service for telecom support
emails. It stores raw MIME before model work, reconstructs conversations from RFC headers,
separates conversations from business requests and operations, asks structured clarification
questions, independently verifies model proposals, enforces hard invariants, and executes only
through an idempotent business-API adapter.

The historical notebooks, datasets, reports, and standalone scripts remain intact as experimental
and evaluation artifacts. Their production-safe pieces were extracted into `src/snoc_agent`.

## Architecture

```mermaid
flowchart LR
    IMAP[IMAP UID fetch] --> Raw[(email_messages)]
    Raw --> Parse[MIME parser and reply candidates]
    Parse --> Corr[conversation/request correlation]
    Corr --> Context[bounded labelled context]
    Context --> Analyzer[configured analyzer]
    Analyzer --> Verifier[independent verifier]
    Verifier --> Policy[hybrid safety policy]
    Policy -->|missing fields| Clarify[(clarification + outbox)]
    Policy -->|unsafe/ambiguous| Escalate[(structured escalation)]
    Policy -->|safe| Execute[idempotent API adapter]
    Execute --> State[(operation/request state)]
    State --> Summary[(completion outbox)]
```

Models propose and semantically verify operations. They never authorize senders, mutate state,
select endpoints, or call business APIs. The application owns those decisions.

### Feature-flagged LangGraph workflow

The original imperative processor remains the default:

```dotenv
WORKFLOW_ENGINE=legacy
```

Set `WORKFLOW_ENGINE=langgraph` to use the five-node
`Ingress → Security → NLU → Policy → Fulfilment` graph. The graph uses LangChain Runnable
boundaries for the existing audited analyzer and verifier, while authorization, policy and
side-effect code remain deterministic. `Runtime.legacy_processor` remains available for immediate
rollback.

The preserved pre-migration source remains in the original DSIP checkout and is intentionally not
part of this standalone repository. See
[migration status](docs/langgraph_migration_status.md) for the implemented boundary and known next
steps.

## Quick start

Python 3.12 is required.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
alembic upgrade head
```

For the exact LangChain/LangGraph versions used by the parity suite:

```bash
pip install -c constraints-langchain.txt -e ".[dev]"
```

SQLite is the default. The command above creates `snoc_agent.db`; set `DATABASE_URL` to a
PostgreSQL SQLAlchemy URL for deployment.

Run the complete offline workflow without credentials, a GPU, or network access:

```bash
python -m snoc_agent.cli.main replay-email \
  tests/fixtures/emails/scenario_a_complete_unblock/01_complete_unblock.eml

python -m snoc_agent.cli.main replay-directory \
  tests/fixtures/emails/scenario_c_multi_operation/
```

With `LLM_PROVIDER=demo`, replay uses the explicitly labelled deterministic demo backend. If
`LLM_PROVIDER` is omitted, an empty `LLM_BASE_URL` preserves that legacy default. Demo inference
is only a workflow simulator. `DRY_RUN=true` uses the mock business API and fake SMTP transport.

The clarification sequence can also be replayed across two commands while preserving the SQLite
state:

```bash
python -m snoc_agent.cli.main replay-email \
  tests/fixtures/emails/scenario_b_otp_clarification/01_incomplete_otp.eml
python -m snoc_agent.cli.main replay-email \
  tests/fixtures/emails/scenario_b_otp_clarification/03_reply_phone_only.eml
```

Replay mode is forcibly dry-run and authorizes only the fixture senders it is currently injecting.
Normal IMAP workers still require `AUTHORIZED_SENDERS`.

Scenarios G–I have self-seeding `scenario.json` manifests. They use a fresh in-memory database,
bind generated request/outbound identifiers into later messages, and require no manual SQL:

```bash
python -m snoc_agent.cli.main replay-directory \
  tests/fixtures/emails/scenario_g_mixed_reply
python -m snoc_agent.cli.main replay-directory \
  tests/fixtures/emails/scenario_h_corrections --scenario before-execution
python -m snoc_agent.cli.main replay-directory \
  tests/fixtures/emails/scenario_h_corrections --scenario after-execution
python -m snoc_agent.cli.main replay-directory \
  tests/fixtures/emails/scenario_i_correlation_markers
```

## Local model configuration

The real backend targets a local OpenAI-compatible `/chat/completions` API and is independent of
the serving implementation. For example:

```dotenv
LLM_PROVIDER=openai_compatible
LLM_BASE_URL=http://127.0.0.1:8000/v1
LLM_API_KEY=
ANALYZER_MODEL=Qwen2.5-7B-Instruct
VERIFIER_MODEL=Qwen3-8B
ANALYZER_TEMPERATURE=0
VERIFIER_TEMPERATURE=0
QWEN3_ENABLE_THINKING=false
QWEN3_SEND_THINKING_PARAMETER=true
LLM_JSON_SCHEMA_MODE=true
# Configure only after offline calibration; unset means no raw-confidence gate.
# ANALYZER_MIN_RAW_CONFIDENCE=0.85
# VERIFIER_MIN_RAW_CONFIDENCE=0.85
```

For Qwen3, `QWEN3_ENABLE_THINKING` is sent as a chat-template option when supported by the server.
Disable `QWEN3_SEND_THINKING_PARAMETER` for servers that reject that extension. Set
`LLM_JSON_SCHEMA_MODE=false` for servers that support JSON-object mode but not OpenAI JSON Schema.
Every run stores backend/model names, quantization label, prompt version, bounded context hash,
raw and parsed output, latency, token counts, and optional log probabilities.

No model weights are bundled or downloaded automatically. Real local-model checks are marked
`local_model` and remain optional.

## Primary vLLM deployments

`LLM_PROVIDER=vllm` is the primary hosted-model workflow. It reuses the audited
OpenAI-compatible client, but routes the two roles to independently discovered deployments. The
application requires the exact IDs returned by each `/v1/models` endpoint and never substitutes a
different model:

```dotenv
LLM_PROVIDER=vllm
VLLM_API_KEY=replace_me
VLLM_QWEN_BASE_URL=https://qwen.example.com/v1
VLLM_QWEN_MODEL=Qwen/Qwen2.5-7B-Instruct-AWQ
VLLM_GEMMA_BASE_URL=https://gemma.example.com/v1
VLLM_GEMMA_MODEL=google/gemma-4-12B-it
VLLM_ANALYZER_DEPLOYMENT=gemma
VLLM_VERIFIER_DEPLOYMENT=gemma
DRY_RUN=true
```

The deployment selectors accept `qwen`, `gemma`, or the exact configured model ID. Qwen and
Gemma have different base URLs and separate backend instances. No Hugging Face routing suffix,
pricing policy, or Qwen chat-template thinking parameter is applied. Tokens, latency, schema mode,
reasoning, retries, endpoint alias, and exact served model are audited; USD cost is recorded as
unknown because these endpoints publish no pricing metadata.

```bash
python -m snoc_agent.cli.main models list
python -m snoc_agent.cli.main models check
python -m snoc_agent.cli.main models smoke-test \
  --analyzer-model gemma \
  --verifier-model gemma \
  --output-dir outputs/evaluation/vllm_smoke
```

`models check` probes `/health`, checks both exact served IDs, sends a minimal chat completion, and
validates a strict JSON-Schema response. The compact smoke command uses ten synthetic French
cases and creates no mail or business adapter. Live compatibility testing in this repository found
that the bounded Qwen analyzer response could exhaust its output limit on one password-reset case.
In the 10-case four-pair matrix, both Gemma-analyzer pairs had zero unsafe decisions and the
deterministic selection rule chose Gemma/Gemma; it is therefore the active default. This is compact
suite evidence, not a production-quality or release claim. See [the vLLM guide](docs/vllm_inference.md).

## Hugging Face Inference Providers

Hugging Face is a first-class provider using `https://router.huggingface.co/v1`. Create a
fine-grained user token with **Make calls to Inference Providers** permission. Never commit the
token; place a newly created token only in `.env` or the process environment.

```dotenv
LLM_PROVIDER=huggingface
HF_TOKEN=hf_replace_me
HF_ROUTER_BASE_URL=https://router.huggingface.co/v1
HF_ANALYZER_MODEL=Qwen/Qwen2.5-7B-Instruct
HF_VERIFIER_MODEL=Qwen/Qwen3-8B
HF_PROVIDER_POLICY=cheapest
HF_RUN_BUDGET_USD=20
HF_STOP_BEFORE_BUDGET_USD=19
HF_ALLOW_UNKNOWN_COST=true
DRY_RUN=true
```

`HF_TOKEN`, `HF_ROUTER_BASE_URL`, and the `HF_*_MODEL` settings take precedence over
`LLM_API_KEY`, `LLM_BASE_URL`, `ANALYZER_MODEL`, and `VERIFIER_MODEL`. If `LLM_PROVIDER` is
unset, the compatibility rule remains: a non-empty `LLM_BASE_URL` selects
`openai_compatible`; otherwise the deterministic demo backend is selected.
`HF_TOKEN` or another `HF_*` value alone never selects Hugging Face: set
`LLM_PROVIDER=huggingface`. For Hugging Face runtime calls, each non-empty provider-specific
setting wins over its compatibility alias, then the safe default applies. Explicit model flags on
the evaluation and smoke-test commands override only those command's stage models.

Discover current availability before spending credits:

```bash
python -m snoc_agent.cli.main models list
python -m snoc_agent.cli.main models check
python -m snoc_agent.cli.main models smoke-test \
  --analyzer-model Qwen/Qwen2.5-7B-Instruct \
  --verifier-model Qwen/Qwen3-8B
```

`models check` validates authentication, configured model/provider compatibility, a minimal chat
completion, and structured output. `models smoke-test` processes ten synthetic French cases with
fake PDVs and phone numbers. It constructs neither mail nor business-API adapters, forces dry-run
semantics, validates Pydantic responses, persists model-run audits, and writes
`outputs/evaluation/hf_smoke/smoke_report.json`.

Routing appends `:cheapest`, `:fastest`, or `:preferred`. Set `HF_ANALYZER_PROVIDER` and
`HF_VERIFIER_PROVIDER` independently to pin an explicit provider, such as `cerebras`; an explicit
provider wins over the policy. Set `HF_ROUTING_SUFFIX_ENABLED=false` only for debugging. The
application never substitutes another model when a configured route is unavailable.

With the default `HF_USE_JSON_SCHEMA=true`, Hugging Face calls first request strict JSON Schema,
then use `json_object` only after an explicit schema rejection, then prompt-enforced JSON only
after both structured modes are rejected. Prompt fallback permits one repair. Disabling the strict
mode starts at JSON object and cannot claim a schema guarantee. Every run records its actual mode
and fallback reason, and only `json_schema` is reported as schema-guaranteed. Local Qwen servers
may still use `QWEN3_ENABLE_THINKING`; those provider-specific chat-template parameters are not
automatically sent through the HF router. Advanced users may set a safe JSON object in
`HF_EXTRA_BODY_JSON`.

Usage is recorded when returned. The persisted cost basis is `exact` when the response supplies
separate input and output costs, `provider_reported` when it supplies only an aggregate cost,
`estimated` only when token usage can be multiplied by explicit router pricing metadata, and
`unknown` otherwise. Known cost stops at the configured threshold. With the default
`HF_ALLOW_UNKNOWN_COST=true`, unknown-cost calls continue with an explicit audit warning, so the
local USD limit cannot be guaranteed for those calls. Hugging Face billing is authoritative.

Evaluation uses the lower of `HF_STOP_BEFORE_BUDGET_USD` and 95% of `--budget-usd`; an explicit
`--stop-before-budget-usd` may lower that threshold.

Email text sent to an external provider may contain operational identifiers and personal data.
Review provider retention, regional, contractual, and access requirements before processing real
mail. Model/provider availability, pricing, and structured-output support can change.

## PostgreSQL and workers

Start the development database if Docker is available:

```bash
docker compose up -d postgres
export DATABASE_URL=postgresql+psycopg://snoc_agent:local-development-only@localhost:5432/snoc_agent
alembic upgrade head
```

The base package includes Psycopg 3 with its binary distribution so the documented PostgreSQL URL
works after installation. Deployment images may replace that extra with a locally compiled
Psycopg build if required by their packaging policy.

Worker commands are synchronous and independently callable:

```bash
python -m snoc_agent.cli.main db init
python -m snoc_agent.cli.main mail poll --once
python -m snoc_agent.cli.main outbox send --once
python -m snoc_agent.cli.main processing retry-failed
python -m snoc_agent.cli.main worker run
```

### Docker black-box mailbox journey and audit dashboard

The Docker stack can exercise the application as an external user while keeping telecom actions
simulated. Configure two distinct mailboxes in `.env`: `IMAP_USERNAME`/`SMTP_USERNAME` are the
agent mailbox, while `SENDER_USERNAME`/`SENDER_PASSWORD` are the personal test mailbox. When
`AUTHORIZED_SENDERS` contains exactly that one personal address, `SENDER_USERNAME` may be omitted.
Keep `DRY_RUN=true` so the business adapter remains `MockBusinessAPI`, and opt into real test mail
with `DRY_RUN_SEND_EMAILS=true`.

For an isolated run, set this exact criterion so the worker ignores unrelated inbox traffic:

```dotenv
IMAP_SEARCH_CRITERION=HEADER X-SNOC-Test-Run "docker-e2e"
```

Start PostgreSQL, the continuous IMAP worker, and the read-only Streamlit dashboard:

```bash
docker compose up --build -d postgres worker dashboard
```

Open <http://localhost:8502>. The dashboard lists treated inbound emails and exposes IMAP
metadata, the RFC message chain, Gmail thread IDs, analyzer/verifier inputs and outputs, schema
modes, policy decisions, request/operation state, dry-run executions, and outbound delivery. It
also renders the latest journey report from the read-only `outputs/` mount. It reads PostgreSQL and
artifacts without mutating workflow state.

Run the compact external-user journey:

```bash
docker compose --profile test run --rm journey
```

The driver sends real, naturally titled emails from the personal mailbox to the agent, waits for
the SMTP reply, answers incomplete requests in the same RFC thread, and waits for a terminal
state. Run/case identifiers exist only in `X-SNOC-Test-*` headers. Its six journeys cover OTP
clarification, account unblock, VPN, quoted-history password reset, ambiguous multi-operation
attribution, and automated out-of-office metadata. On Gmail it fetches `X-GM-THRID` from the
sender's All Mail mailbox and requires every message in a journey to share one thread. The report
is written to `outputs/docker_mail_journey/report.json`.

With `DRY_RUN=true`, analyzer/verifier calls, decisions, state changes, validation records, and
dry-run execution records still happen. `DRY_RUN_SEND_EMAILS=true` additionally uses real SMTP for
clarification and terminal replies. Only the telecom business mutation is replaced by
`MockBusinessAPI`; every recorded execution must have `dry_run=true`.

Inspection commands:

```bash
python -m snoc_agent.cli.main request show SNOC-REQ-A84F91C274D2
python -m snoc_agent.cli.main conversation show UUID
python -m snoc_agent.cli.main operation show UUID
python -m snoc_agent.cli.main failures list
python -m snoc_agent.cli.main quarantine list
python -m snoc_agent.cli.main quarantine retry EMAIL_UUID
```

## Offline evaluation

The evaluation path supports legacy CSVs and attributed multi-operation JSON/JSONL datasets:

```bash
python -m snoc_agent.cli.main evaluate \
  --dataset "labeled_data/labeled data/SMOLDATA_last_1000_reviewed.csv" \
  --analyzer-model Qwen2.5-7B-Instruct \
  --verifier-model Qwen3-8B \
  --output-dir outputs/evaluation/qwen25_qwen3
```

Or run the complete four-pair matrix and safety-first comparison:

```bash
python -m snoc_agent.cli.main evaluate \
  --dataset "labeled_data/labeled data/SMOLDATA_last_1000_reviewed.csv" \
  --matrix \
  --use-cache \
  --resume \
  --budget-usd 20 \
  --output-dir outputs/evaluation/hf_qwen_matrix
```

Both the explicit single-pair command and `--matrix` use the same persistent evaluation runner and
write predictions, summary JSON, confusion data, categorized errors, model configuration,
checkpoints, cost/token counts, and Markdown metrics. Matrix mode runs each analyzer once per input
and each verifier once per unique proposal/context, then materializes all four policies.
`--use-cache` reads/writes successful persistent results, `--no-cache` bypasses the global cache,
`--refresh-cache` replaces cache pointers while retaining old model-run audits, and `--resume`
reuses completed calls from an interrupted matching run. Cache, resume, budget, stop-threshold,
checkpoint, and confirmation flags apply to both forms.

If `HF_REQUIRE_BUDGET_CONFIRMATION=true`, the evaluation command refuses to start until
`--confirm-budget` is supplied after the operator reviews the configured limit. A clean budget
stop writes a resumable command instead of creating a fake failed model run.

Build explicit smoke, safety, oracle-diagnostic, stateful, development, calibration, and held-out
subsets before the safety run:

```bash
python -m snoc_agent.cli.main evaluation datasets build \
  --source "labeled_data/labeled data/SMOLDATA_last_1000_reviewed.csv" \
  --output-dir outputs/evaluation

python -m snoc_agent.cli.main evaluate \
  --dataset outputs/evaluation/safety_regression.jsonl \
  --matrix --use-cache --resume --budget-usd 2 \
  --output-dir outputs/evaluation/hf_safety_smoke
```

The historical full deterministic-demo run produced 194 unsafe candidate rows. Those rows came
from heuristic `DemoLLMBackend` output, not Qwen. The dataset builder reproduces their IDs and
source hash in `demo_unsafe_candidates_manifest.json`, labels them explicitly, and adds them to the
safety regression subset. It also writes an initially empty
`demo_vs_real_regression_report.json`; a completed matrix writes `failure_attribution.json` with
separate analyzer, verifier, policy, and ground-truth-review categories. Real categories remain
unpopulated until genuine provider calls are run.

Optional confidence calibration supports `none`, `logistic`, and `isotonic` and accepts only rows
mapped to the calibration split:

```bash
python -m snoc_agent.cli.main evaluation calibrate \
  --predictions outputs/evaluation/hf_qwen_matrix/qwen25_qwen3/predictions.csv \
  --method isotonic \
  --split-manifest outputs/evaluation/split_manifest.json \
  --output outputs/evaluation/calibration_isotonic.json
```

Raw confidence is never presented as a correctness probability without such an artifact. A release
recommendation is emitted only when both `unsafe_auto_execute_count == 0` and
`validation_pass_but_wrong_count == 0`. Oracle rescue analysis remains evaluation-only.

## Tests and quality

```bash
pytest
ruff check .
ruff format --check .
mypy src/snoc_agent
```

The default test suite uses SQLite, fake IMAP/SMTP, deterministic model responses, and the mock
business API. It requires no internet, credentials, local models, or GPU.

Opt-in live tests use only synthetic content and are skipped unless explicitly enabled:

```dotenv
# .env in the project root
HF_TOKEN=hf_replace_me
RUN_HF_LIVE_TESTS=true
HF_LIVE_TEST_MAX_COST_USD=0.10
```

```bash
pytest -m hf_live
```

For the independently hosted vLLM deployments:

```dotenv
RUN_VLLM_LIVE_TESTS=true
```

```bash
pytest -m vllm_live
```

The live-test module loads the project-root `.env` through `Settings`; real environment
variables override it. The CLI-only `--env-file` option does not apply to pytest. All unmarked
tests force the demo provider, so a developer `.env` cannot turn the normal suite into paid
inference. The live test requires usable route pricing before inference and disables unknown-cost
calls; missing pricing fails before credits are spent.

## Safety defaults

- `DRY_RUN=true` is the default.
- Live execution additionally requires a non-demo LLM provider with its required credentials or
  endpoint, plus configured business API and SMTP endpoints.
- An empty sender whitelist denies normal inbound senders.
- Raw MIME is stored before MIME parsing or model processing and remains retryable.
- Parse-fatal and raw-size failures are quarantined and are not reparsed by normal polling.
- MIME, attachment, latest-message, thread, and total model-context limits create explicit warnings
  and prevent automatic execution.
- IMAP identity uses account/mailbox/UIDVALIDITY/UID; sequence numbers are never persisted.
- Message-ID and raw-hash signals prevent duplicate logical processing.
- Each operation revision has a stable, unique API idempotency key.
- Closed/cancelled operations, weak/conflicting correlation, unsupported evidence, quoted-history
  fields, contradictions, and analyzer/verifier disagreement cannot auto-execute.
- Email content is untrusted, and structured model outputs are strictly validated with Pydantic.
- Full email-body logging is off by default.

Do not set `DRY_RUN=false` until endpoint behavior, authorization sources, TLS, backups, retention,
alerting, and a production safety threshold have been validated in the target environment.

## Current limitations

- LDAP/Active Directory is an adapter seam; only the static whitelist is implemented locally.
- Attachments are hashed and described but their binary content is not analyzed.
- HTML-to-text conversion is intentionally small and dependency-free.
- The automated default suite mocks IMAP/SMTP; the opt-in Docker mailbox journey above exercises
  real IMAP/SMTP with operator-supplied test credentials. The business API remains mocked in that
  journey.
- Qwen confidence values are stored but are not treated as calibrated probabilities.
- PostgreSQL is the deployment target, while automated tests currently exercise SQLite.
- Automatic clarification defaults to one round; subsequent incompleteness escalates.
- Corrections to completed operations require human review.
- The historical flat dataset has no RFC/stateful ground truth and only five unattributed
  `multiple` rows; the new `.eml` fixtures cover the stateful workflow separately.
- A USD cap cannot be enforced locally for calls whose selected provider exposes neither response
  cost nor usable pricing metadata when `HF_ALLOW_UNKNOWN_COST=true`.

Further detail is in [the migration plan](docs/langchain_five_agent_migration_plan.md),
[migration status](docs/langgraph_migration_status.md), and
[the vLLM guide](docs/vllm_inference.md).
