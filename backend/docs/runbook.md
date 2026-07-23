# SNOC email agent runbook

This runbook covers the synchronous MVP in this repository. It favors preserving evidence and preventing duplicate business actions over automatic recovery. When an API outcome or request association is uncertain, stop automatic handling and reconcile it; do not “fix” uncertainty by deleting rows or changing identifiers.

## Operating modes

### Local SQLite demonstration

SQLite is the default:

```text
DATABASE_URL=sqlite:///./snoc_agent.db
DRY_RUN=true
```

In this mode:

- `LLM_PROVIDER=demo` selects the deterministic demo backend; when
  `LLM_PROVIDER` is omitted, an empty `LLM_BASE_URL` preserves that legacy default;
- the business API is `MockBusinessAPI`;
- SMTP is the in-memory fake transport, even if `SMTP_HOST` is present;
- replay automatically authorizes senders found in the supplied `.eml` files;
- raw MIME is stored under `RAW_EML_DIRECTORY` unless `STORE_RAW_EML=false`.

Use SQLite for tests, fixture replay, and a single local worker. Do not run multiple pollers or outbox senders against the same SQLite file. The implementation has application-level logical deduplication and no concurrent outbox row claiming.

### PostgreSQL deployment

PostgreSQL is the intended persistent deployment database. The included `docker-compose.yml` starts a local development PostgreSQL 16 instance:

```bash
docker compose up -d postgres
```

Set a SQLAlchemy URL such as:

```text
DATABASE_URL=postgresql+psycopg://snoc_agent:REPLACE_ME@127.0.0.1:5432/snoc_agent
```

The package declares `psycopg[binary]` as its PostgreSQL DBAPI driver. Production images may replace the binary distribution with an organization-approved psycopg build while preserving the same SQLAlchemy URL. The Compose password is for local development only and must be replaced outside a developer machine.

PostgreSQL provides stronger durability and constraint handling, but it does not by itself make this worker horizontally scalable. Until row claiming and database-level logical-message uniqueness are implemented, run:

- one IMAP ingestion/processing worker per configured mail account;
- one outbox sender for the database;
- one reviewed migration job.

Back up the database before migrations, use a least-privilege application role, and keep raw-email storage on encrypted persistent storage with appropriate retention controls.

## Installation and initialization

From the repository root:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
cp .env.example .env
python -m snoc_agent.cli.main db init
```

`db init` runs Alembic to `head`. Replay also calls SQLAlchemy `create_all` for convenience, but deployment must use Alembic so schema revisions are recorded.

Global CLI options precede the subcommand:

```bash
python -m snoc_agent.cli.main --env-file /path/to/snoc.env db init
```

Relative SQLite and raw-MIME paths are resolved from the process working directory. Use explicit absolute paths in service configuration.

## Configuration gate before live use

Start with `DRY_RUN=true`. Configure and validate at least:

```text
DATABASE_URL
IMAP_HOST, IMAP_PORT, IMAP_USERNAME, IMAP_PASSWORD, IMAP_MAILBOX, IMAP_SSL
SMTP_FROM_ADDRESS
AUTHORIZED_SENDERS
ESCALATION_RECIPIENT
PDV_PATTERN, PHONE_PATTERN
MAX_CLARIFICATION_ROUNDS
```

To use a real model while retaining mock API/SMTP behavior, keep `DRY_RUN=true` and
configure either `LLM_PROVIDER=huggingface` plus the corresponding `HF_*` settings,
or `LLM_PROVIDER=openai_compatible` plus `LLM_BASE_URL`, model names, and an API key.
An explicit `LLM_PROVIDER` selects the backend; `HF_*` values alone do not select Hugging Face.
Within HF mode, non-empty `HF_TOKEN`, router URL, and stage model settings override their legacy
`LLM_*`/model aliases, followed by safe defaults.

`DRY_RUN=false` is a coupled live-mode switch in the current runtime. Startup then requires all of:

```text
a non-demo model provider (`HF_TOKEN` for Hugging Face, or `LLM_BASE_URL` for an OpenAI-compatible server)
BUSINESS_API_BASE_URL
SMTP_HOST
```

It selects the HTTP business adapter and real SMTP transport. Before enabling it:

1. Pin and evaluate analyzer/verifier models and prompt versions.
2. Test every endpoint mapping against a non-production API environment.
3. Confirm `AUTHORIZED_SENDERS`; an empty list authorizes nobody.
4. Confirm the configured PDV and phone patterns.
5. Confirm SMTP SSL versus STARTTLS; they are mutually exclusive.
6. Keep `BUSINESS_API_IDEMPOTENCY_GUARANTEED=false` unless the remote service owner has explicitly guaranteed semantics for the `Idempotency-Key` header.
7. Review raw-email storage permissions and logging. Full email-body logging is off by default.

The escalation service always persists a structured database record. In live mode it also queues a structured email to `ESCALATION_RECIPIENT`; the normal outbox worker must drain it. In replay/dry-run mode no real escalation email is queued, and replay JSON prints the stored escalation summary. A production deployment still needs an operator queue or report around the `escalations` table for acknowledgement, assignment, and resolution.

## Normal commands

Initialize or migrate:

```bash
python -m snoc_agent.cli.main db init
```

Poll one IMAP batch without sending outbox mail:

```bash
python -m snoc_agent.cli.main mail poll --once
```

Run the combined polling, processing, and outbox loop:

```bash
python -m snoc_agent.cli.main worker run
```

Run only the outbox:

```bash
python -m snoc_agent.cli.main outbox send --once
python -m snoc_agent.cli.main outbox send --loop
```

Retry all stored emails currently marked `failed`:

```bash
python -m snoc_agent.cli.main processing retry-failed
```

Inspect state:

```bash
python -m snoc_agent.cli.main failures list
python -m snoc_agent.cli.main quarantine list
python -m snoc_agent.cli.main quarantine retry 00000000-0000-0000-0000-000000000000
python -m snoc_agent.cli.main request show SNOC-REQ-A84F91C274D2
python -m snoc_agent.cli.main conversation show 00000000-0000-0000-0000-000000000000
python -m snoc_agent.cli.main operation show 00000000-0000-0000-0000-000000000000
```

Discover and probe Hugging Face routes without involving mail or business adapters:

```bash
python -m snoc_agent.cli.main models list
python -m snoc_agent.cli.main models check
python -m snoc_agent.cli.main models smoke-test \
  --analyzer-model Qwen/Qwen2.5-7B-Instruct \
  --verifier-model Qwen/Qwen3-8B
```

The `evaluate` command accepts either `--matrix` or both explicit model flags. Both forms support
the mutually exclusive `--use-cache`, `--no-cache`, and `--refresh-cache` controls, plus
`--resume`, budget and stop-threshold values, `--checkpoint-every`, and conditional
`--confirm-budget`. Dataset building and calibration are under `evaluation datasets build` and
`evaluation calibrate`; see [Evaluation](evaluation.md) for their required paths.

The CLI prints JSON. Runtime logs are JSON with UTC timestamp, severity, logger, message, exception, and available correlation IDs.

## What to monitor

At minimum, alert on:

- worker process exit or repeated IMAP connection errors;
- growth in `email_messages.processing_status='failed'`;
- growth in `email_messages.processing_status='quarantined'`, quarantine categories, or repeated manual retries;
- messages stuck in `processing` longer than the expected model/API timeout window;
- executions stuck in `pending` or operations stuck in `EXECUTING`;
- any `executions.status='unknown'`;
- outbox rows in `failed`, or old rows in `pending`;
- correlation-conflict escalation rate;
- clarification backlog in `pending_send` or `open`;
- unexpected UIDVALIDITY values or a large duplicate rescan;
- repeated logical `Message-ID` collisions with different raw hashes;
- unsafe or elevated live-execution volume.

Useful read-only queries are:

```sql
SELECT processing_status, count(*)
FROM email_messages
GROUP BY processing_status;

SELECT status, count(*)
FROM executions
GROUP BY status;

SELECT status, count(*), min(created_at) AS oldest
FROM outbox_messages
GROUP BY status;

SELECT reason_code, count(*)
FROM escalations
WHERE status = 'open'
GROUP BY reason_code;
```

Never include secrets or full raw email bodies in incident tickets. Prefer internal UUIDs, public request reference, status, warning codes, and redacted evidence.

## Incident: failed analyzer/model call

### Expected behavior

The HTTP inference backends use their configured timeout and bounded retry count.
They retry only rate limits, timeouts, and temporary provider failures, honoring
`Retry-After` and otherwise using exponential backoff with jitter. Authentication,
permission, invalid model/request, and ordinary schema-validation failures are not
transport-retried. Hugging Face prompt-enforced JSON mode permits at most one repair
request after both structured-output modes have been explicitly rejected.

If analyzer generation still fails:

- the already-created email row becomes `failed`;
- raw MIME remains at `raw_eml_path` or in `raw_eml_blob`;
- `parsing_warnings` receives a truncated `processing_error:<detail>` entry;
- no business API call is authorized from that failed analysis.

Failed analyzer and verifier attempts are persisted in `model_runs` with `structured_output_valid=false`, the input-context hash, base/resolved model route, provider metadata, structured mode/schema/fallback audit, separated reasoning when present, usage/pricing/cost fields, cache linkage, a classified final error, and a bounded error string. A backend exception may occur before a final response body is available, so preserve provider logs when the failed row has no `raw_output`.

The cost basis is `exact` for separately reported input/output costs, `provider_reported` for an
aggregate response cost, `estimated` only from explicit catalog rates plus usage, and `unknown`
when the required information is absent.

### Response

1. Run `failures list` and record the email UUID.
2. Check JSON worker logs for `inbound processing failed` with that UUID.
3. Verify model server reachability, model name, API authorization, timeout, and response-format support.
4. Confirm the returned content can satisfy the strict Pydantic schema; do not loosen schemas to accept unsafe prose.
5. Fix the external/model configuration.
6. Run `processing retry-failed` during a controlled window.
7. Inspect the request/operation and execution tables afterward, because an earlier short transaction may already have persisted a request, operation revision, or execution guard before a later failure.

`retry-failed` retries every generic failed email, not one selected UUID. There is no per-email CLI for those rows; use a staging copy or reviewed administrative tooling when only one should be retried. Parse-fatal quarantines are separate and do support `quarantine retry EMAIL_ID`.

### Verifier failure differs

A verifier exception is handled per operation. The operation is set to `ESCALATED`, an escalation with reason `semantic_verifier_failure` is created, and the email normally finishes as `processed`. It therefore does not appear in `processing retry-failed`. Resolve it through human review or a future dedicated verifier-retry/reconciliation command; do not reset it to `NEW` with ad hoc SQL.

## Incident: malformed or unusual email

The parser is deliberately tolerant. Missing/invalid `Message-ID`, invalid dates, missing sender, uncertain segmentation, unsupported body, or HTML-only conversion are recorded as warnings. Attachment content is never sent to the model; only filename, media type, size, and SHA-256 metadata are stored.

If parsing succeeds:

- the email is stored normally;
- missing `Message-ID` causes raw SHA-256 deduplication;
- authorization, automated-message filtering, and safety policy still apply;
- warnings are visible in `failures list` only if processing later fails, or by direct database inspection otherwise.

If parsing itself raises, the application keeps the raw source, marks its minimal
email row `quarantined`, records a safe failure category/message, and skips that
physical message on ordinary polling so the same fatal input is not reparsed forever.

Response:

1. Run `python -m snoc_agent.cli.main quarantine list` and review the email UUID,
   category, safe message, size, raw path, and retry count.
2. Preserve the original raw MIME outside the application log when incident policy
   requires a separate evidence copy.
3. Reproduce with `replay-email` against a temporary dry-run database and determine
   whether the problem is RFC/MIME decoding, a configured resource limit, or a parser bug.
4. Deploy the tested parser/configuration fix.
5. Retry exactly the reviewed item with
   `python -m snoc_agent.cli.main quarantine retry EMAIL_ID`.
6. Do not manufacture a `Message-ID` merely to bypass deduplication.

## Incident: SMTP failure

### Expected behavior

Clarification/completion state and one logical outbound email are committed before SMTP. The outbox sender loads `pending` rows in creation order.

- Accepted: outbox becomes `sent`, `sent_at` is set, outbound email becomes `processed`, and a linked clarification becomes `open`.
- Transient failure below the default three-attempt limit: `retry_count` increments, `last_error` is stored, and status remains `pending` for the next sender pass.
- Permanent failure or third failed attempt: status becomes `failed`.

The same outbox row and RFC `Message-ID` are reused. SMTP retry does not create a second clarification.

### Response

1. Inspect `outbox_messages.status`, `retry_count`, `last_error`, recipient, and related request/clarification IDs.
2. Correct DNS/connectivity, credentials, TLS mode, sender policy, or recipient data.
3. For rows still `pending`, run `outbox send --once`.
4. For `failed` rows, verify that SMTP did not actually accept the message before requeueing.
5. Requeue only the reviewed outbox UUID in one database transaction; do not create a new outbound email or clarification.

The current CLI has no failed-outbox requeue command. A controlled administrative update has the following shape:

```sql
BEGIN;
SELECT id, status, retry_count, last_error, outbound_email_id
FROM outbox_messages
WHERE id = :reviewed_outbox_id
FOR UPDATE;

UPDATE outbox_messages
SET status = 'pending', retry_count = 0, last_error = NULL
WHERE id = :reviewed_outbox_id AND status = 'failed';
COMMIT;
```

Adapt locking syntax for SQLite, which does not support `FOR UPDATE`. Always retain the original outbox and outbound email IDs.

SMTP acceptance and the database commit are not atomic. If the process crashed after the server accepted mail but before `sent` committed, the row remains `pending` and a retry can send a duplicate message. Ask the recipient/mail administrator to search for the stored RFC `Message-ID` before retrying an ambiguous delivery.

## Incident: business API timeout or unsafe response

### Safety behavior

Before calling the API, the execution service commits:

- `execution.status='pending'`;
- the stable `<operation UUID>:<revision>` idempotency key;
- request payload and intended action;
- operation state `EXECUTING`.

The HTTP client always sends `Idempotency-Key`. It retries transport errors and HTTP `408`, `429`, `502`, `503`, and `504` only when `BUSINESS_API_IDEMPOTENCY_GUARANTEED=true`. Otherwise it makes one attempt, regardless of `BUSINESS_API_MAX_RETRIES`.

An authoritative success requires all of:

- HTTP 2xx;
- response no larger than the configured adapter limit;
- valid JSON matching the response schema;
- an explicit boolean `success: true`.

A transport exhaustion/timeout produces `execution.status='unknown'`; a non-success HTTP response, invalid/oversized response, or explicit unsuccessful payload produces `failed`. Both escalate the operation and disable automatic eligibility. The workflow does not issue a later automatic retry.

### Response to `unknown`

1. Stop automatic/manual attempts for that operation.
2. Inspect the execution UUID, idempotency key, endpoint, attempt count, and redacted payload.
3. Query the remote system or its idempotency ledger using the exact key.
4. Determine whether the business side effect happened.
5. Record reconciliation evidence in a reviewed operator system.
6. If it succeeded remotely, update local state only through a dedicated/reviewed reconciliation procedure.
7. If it definitively did not execute, obtain approval for an explicit retry mechanism that reuses the same idempotency key. The current `ExecutionService` returns the existing row and intentionally will not call again.

Never delete the execution row, alter its key, or increment an operation revision merely to obtain another call. A new revision means changed business data, not a retry token.

### Response to `failed`

Treat a known validation/rejection failure as a human escalation. Correcting legitimate operation data should create field revision evidence and follow correction policy. Corrections after completion are human-review-only in this MVP.

### Stuck `pending` / `EXECUTING`

A process crash between the pre-call commit and result commit can leave this pair. Treat it exactly like an unknown outcome until the remote system is reconciled. Restarting the worker does not erase or replay the execution guard.

## Incident: duplicate message

Two paths exist:

- Physical rediscovery: the complete `(account, mailbox, UIDVALIDITY, UID)` already exists. Processing returns the original email ID and inserts no row.
- Logical duplicate at another locator: a new row is stored with status `duplicate` and `duplicate_of_id`; no analyzer, verifier, API, or outbox work runs.

Response:

1. Confirm `duplicate_of_id`, normalized `Message-ID`, raw SHA-256, and physical locator.
2. Confirm there is at most one execution for each operation-revision idempotency key.
3. Take no retry action for a genuine duplicate.
4. If two different messages reused the same valid `Message-ID`, quarantine the later message for human review. The current deduplicator prefers valid `Message-ID` over raw-hash disagreement.
5. If concurrent workers caused a physical unique-constraint error, return to the supported single-ingestion-worker topology and retry only the failed stored source after reviewing partial state.

The CLI result uses `status: "duplicate"` and includes `duplicate_of_id`.

## Incident: UIDVALIDITY change

### Current behavior

Every fetched `MailboxMessage` carries the UIDVALIDITY returned by the selected mailbox. It is part of the physical unique constraint, so UID `123` under namespace `A` never aliases UID `123` under namespace `B`.

The processor records the latest observed `mail_accounts.last_uidvalidity` and greatest stored UID. Polling does not use that checkpoint to narrow the search and does not create a UIDVALIDITY-change event. After a server change, the worker sees the server's current candidates in a new namespace and relies on logical `Message-ID`/raw-hash deduplication during the rescan.

### Response

1. Run only one poller for the account.
2. Record the old/new values from stored email rows and the IMAP server; do not rewrite old rows.
3. Ensure sufficient database/raw-storage capacity for duplicate-event rows from the rescan.
4. Run one controlled poll and monitor duplicate, failed, request, and execution counts.
5. Verify that old messages become logical duplicates and that only genuinely new logical messages reach analysis.
6. Investigate missing-`Message-ID` mail whose raw bytes changed across server migration; raw-hash deduplication cannot recognize semantically equal but byte-different MIME.
7. Verify that the account row now records the new UIDVALIDITY and advancing UIDs; do not treat these observational fields as proof that a full rescan finished.

Do not set the new UIDVALIDITY on old `email_messages`, reuse old UIDs under the new namespace, or delete duplicate rows to make counts look normal.

For large mailboxes, explicit change detection, persisted rescan progress, and alerting must be added before production scale-out. The current behavior is a correctness-first full candidate rescan.

## Incident: request-correlation conflict

Conflicts include headers pointing to several conversations/requests, multiple visible markers, header/marker disagreement, header or marker sender mismatch, multiple open requests under a weak subject match, or several subject-matched conversations.

Expected behavior:

- authorization is already checked;
- `email_messages.correlation_details` stores strength, matched signal, candidate IDs, and conflict codes;
- normal analyzer processing is skipped;
- email becomes `processed`;
- a `request_correlation_conflict` escalation is created;
- no operation is selected and no business API call occurs.

Response:

1. Inspect the internal email UUID and redacted `In-Reply-To`, `References`, visible reference(s), sender, conversation candidates, and open requests.
2. Verify whether the sender legitimately owns the referenced request.
3. Do not choose “the most recent” request merely because it is convenient.
4. Ask the sender to reply directly to the correct agent email or include exactly one correct public request reference in a new message.
5. Resolve the escalation through human tooling; the original email is `processed` and is not eligible for `retry-failed`.

Replaying the exact raw message will normally be deduplicated and will not repair the conflict. Recovery should produce a new legitimate email identity or use a reviewed administrative correlation workflow.

## Manual replay

Replay requires no mailbox, GPU, credentials, API, or SMTP server in default dry-run mode.

One email:

```bash
python -m snoc_agent.cli.main replay-email \
  tests/fixtures/emails/scenario_a_complete_unblock/01_complete_unblock.eml
```

A sequential scenario, recursively sorted by filename:

```bash
python -m snoc_agent.cli.main replay-directory \
  tests/fixtures/emails/scenario_b_otp_clarification
```

Replay behavior:

- initializes missing tables with SQLAlchemy metadata;
- processes each file in sorted order in one persistent runtime/database;
- uses mailbox `REPLAY`, UIDVALIDITY `1`, and per-run index as the synthetic UID;
- binds the fixture's symbolic clarification target to the latest stored outbound clarification when present;
- authorizes fixture sender addresses for that replay runtime;
- sends the outbox after each input through the fake SMTP transport in dry-run mode;
- prints JSON processing decisions and outbox counts.

For an isolated run, point configuration at a new temporary database rather than deleting the normal database:

```bash
demo_dir="$(mktemp -d)"
DATABASE_URL="sqlite+pysqlite:///$demo_dir/snoc.sqlite3" \
RAW_EML_DIRECTORY="$demo_dir/raw_eml" \
DRY_RUN=true \
python -m snoc_agent.cli.main replay-directory \
  tests/fixtures/emails/scenario_b_otp_clarification
```

The shell expands the absolute path into the four-slash SQLite form. Keep the printed request/operation UUIDs if the temporary database will be inspected afterward.

To use a configured model during replay, set `LLM_PROVIDER` plus the selected provider's endpoint/token and model settings while keeping `DRY_RUN=true`. This uses the real model endpoint but still uses the mock business API and fake SMTP. Do not describe that as a full live integration test.

Rerunning a fixture against the same database normally produces a logical duplicate because its RFC `Message-ID` is stable. Use a fresh temporary database for a fresh scenario; do not edit fixture identifiers to defeat deduplication unless the test is specifically about a new message.

## Stored-email retry and partial-state review

Inbound processing uses short transactions:

1. email storage;
2. conversation/context preparation;
3. model proposal/operation persistence;
4. per-operation verification decision;
5. pre-call execution guard;
6. API result;
7. aggregate status/outbox finalization.

This limits lost work, but a failed email can have partial durable state. Before or after `processing retry-failed`, inspect:

- existing request IDs for the email/conversation;
- operation revisions and status;
- model runs and validation decisions;
- execution rows and keys;
- clarifications/outbox rows;
- escalation records.

The execution idempotency guard prevents the same operation revision from being called twice, but retry is not a substitute for reconciling a `pending`/`unknown` API outcome.

## Database recovery rules

- Restore database and raw-email storage from the same recovery point when possible.
- Never restore an old database and then enable live polling/API execution without reconciling remote idempotency history.
- Run Alembic only once per deployment and verify the revision before starting workers.
- Preserve `email_messages`, `field_revisions`, `model_runs`, `validation_decisions`, `executions`, and `escalations` as the production audit chain. Preserve `inference_cache_entries`, `evaluation_runs`, `evaluation_inferences`, and `calibration_artifacts` with evaluation outputs when reproducibility matters.
- Treat manual `UPDATE` statements as reviewed incidents. Record operator, reason, before/after state, and external evidence.
- Do not use SQLite file copying while a writer is active as a production backup method.

## Known operational limitations

The following gaps should be closed before a multi-worker or high-volume production rollout:

- no explicit UIDVALIDITY comparison event, checkpoint reset, or complete rescan-progress mechanism;
- no database row claiming/lease for outbox or inbound work;
- no database uniqueness constraint on normalized logical `Message-ID` or raw SHA-256;
- no failed-outbox requeue CLI;
- no execution reconciliation/retry command;
- no escalation assignment/resolution UI or dedicated escalation inspection CLI (SMTP delivery uses the ordinary outbox worker);
- quarantined mail requires explicit operator inspection/retry and has no assignment UI;
- SMTP delivery is at least once across the SMTP-accept/database-commit boundary;
- conversation status is not automatically closed;
- live SMTP and live business API are coupled under `DRY_RUN=false`;
- production PostgreSQL deployments must still choose and test their approved psycopg build and TLS policy.

These limitations do not weaken the default dry-run safety posture, but they define the supported operating envelope: one synchronous worker, one sender, bounded external calls, explicit escalation, and human reconciliation for uncertainty.
