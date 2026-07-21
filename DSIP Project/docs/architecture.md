# Architecture

This document describes the code that is currently implemented. It is not a target-state diagram and it does not imply that the live integrations have been production-certified.

## System shape

The application is a synchronous, constructor-wired worker. SQLAlchemy is the durable coordination layer; models never receive mail or business-API clients.

~~~mermaid
flowchart LR
    IMAP["IMAP mailbox"] --> ORCH["MailOrchestrator"]
    EML["Local .eml replay"] --> PROC["InboundProcessor"]
    ORCH --> PROC
    PROC --> RAW["Pre-parse raw persistence<br/>physical deduplication"]
    RAW --> DB[("SQL database")]
    RAW --> PARSE["MIME parser<br/>reply segmenter"]
    RAW -->|unsafe raw size| QUAR[("QUARANTINED")]
    PARSE --> DB
    PARSE -->|fatal parse| QUAR
    DB --> AUTH["Sender authorization<br/>and correlation"]
    AUTH --> CTX["ContextBuilder"]
    CTX --> ANALYZER["EmailAnalyzer"]
    ANALYZER --> DB
    ANALYZER --> VERIFIER["SemanticVerifier<br/>per operation"]
    VERIFIER --> POLICY["HybridDecisionEngine"]
    POLICY --> DB
    POLICY -->|AUTO_EXECUTE| EXEC["ExecutionService"]
    EXEC --> MOCKAPI["MockBusinessAPI"]
    EXEC --> HTTPAPI["HttpBusinessAPI"]
    POLICY -->|ASK_FOR_INFORMATION| OUTBOX["Transactional outbox"]
    POLICY -->|ESCALATE| ESC[("Escalation record")]
    ESC -->|live mode| OUTBOX
    EXEC --> OUTBOX
    OUTBOX --> FAKESMTP["FakeSMTPTransport"]
    OUTBOX --> SMTP["SMTP server"]
~~~

The main dependency graph is assembled in `src/snoc_agent/cli/runtime.py`. The important separations are:

| Layer | Current responsibility |
|---|---|
| `mail` | RFC/MIME parsing, deterministic reply segmentation, IMAP/SMTP transports, threading headers, public markers, and correlation |
| `ai` | Bounded context construction, numeric candidate discovery, strict model schemas, analyzer/verifier calls, prompt loading, and backend adapters |
| `workflow` | Authorization, request and operation materialization, deterministic policy, clarification/escalation creation, execution, and finalization |
| `business_api` | Validated mock and synchronous HTTP adapters for the four supported operations |
| `db` | SQLAlchemy entities, repositories, sessions, and Alembic-managed schema |
| `evaluation` | Dataset/subset loading, persistent selected-pair and matrix inference, schema-aware caching/reuse, budget/checkpoint/resume state, calibration, metrics, comparisons, reports, and isolated oracle diagnostics |
| `cli` | Database, IMAP worker, failed/quarantine retry, outbox, replay, provider discovery/probes, evaluation, calibration, and inspection commands |

PostgreSQL is the intended deployment database. SQLite is the default and is used for local replay and tests.

## Inbound data flow

1. `RealIMAPMailbox` selects a mailbox read-only, obtains `UIDVALIDITY`, performs UID search, and fetches complete messages with `BODY.PEEK[]`. Each fetched UID is processed independently.
2. `InboundProcessor.process_raw` hashes and persists the raw bytes plus a minimal email row before MIME parsing. Physical identity is `(mail_account_id, mailbox_name, uidvalidity, imap_uid)`; an existing physical row returns without reparsing. The parser then enriches that row. A fatal parse or unsafe raw size marks it `QUARANTINED`, while successful parsing enables logical deduplication by normalized RFC `Message-ID` or raw SHA-256.
3. Automated messages are stored and ignored. Sender authorization is evaluated before business analysis. Unauthorized mail creates an escalation record without reaching either model or the business API.
4. Header, visible-marker, sender, and subject signals are correlated. Conflicting signals and ambiguous subject matches are escalated before the normal analyzer is called.
5. `ContextBuilder` constructs one of four labelled contexts: new request, direct clarification reply, strongly correlated request reply, or weak possible follow-up. See [Context selection](context_selection.md).
6. `EmailAnalyzer` proposes zero or more strict `ProposedOperation` objects. Successful calls persist input and output; failed calls persist a failed model-run audit row.
7. Proposals are materialized as request/operation state. A direct clarification can update only its recorded target operations; corrections can revise an existing matching operation; remaining proposals create a new request.
8. `SemanticVerifier` independently checks each proposal. A verifier exception escalates that operation. Successful verification is persisted and passed to `HybridDecisionEngine` with deterministic state, correlation, format, authorization, and execution facts.
9. Each operation is decided independently. Complete safe operations can execute while another operation in the same request waits for information or escalates.
10. `ExecutionService` commits a unique `operation UUID:revision` idempotency record before performing external I/O. The mock adapter records a successful dry run; the HTTP adapter validates an explicit successful response.
11. Clarifications and terminal summaries are created as outbound `EmailMessage` plus `OutboxMessage` rows in the same transaction. A separate outbox pass sends them through fake or real SMTP.

The processor intentionally uses several short transactions:

~~~mermaid
sequenceDiagram
    participant W as Worker
    participant DB as Database
    participant M as Models
    participant API as Business API
    W->>DB: Store raw email and physical identity
    W->>DB: Parse/enrich, logical dedup, or quarantine
    W->>DB: Authorize, correlate, select bounded context
    W->>M: Analyze
    W->>DB: Persist analysis and operation revisions
    loop each operation
        W->>M: Verify proposal
        W->>DB: Persist verification and policy decision
    end
    W->>DB: Persist execution idempotency key
    W->>API: Execute eligible operation
    W->>DB: Persist result, aggregate state, and outbox
~~~

This makes failed model calls retryable from stored raw MIME and prevents an API call from occurring before an idempotency key is durable. It is not a distributed transaction: a process or network failure can still require reconciliation.

## Runtime modes

Model selection and side-effect selection are independent:

| Configuration or command | Model behavior | Business API | Outbound mail |
|---|---|---|---|
| `LLM_PROVIDER=demo` | `DemoLLMBackend` deterministic heuristics; no model server; valid only with `DRY_RUN=true` | Determined by `DRY_RUN` | Determined by `DRY_RUN` |
| `LLM_PROVIDER=openai_compatible` | HTTP calls to `LLM_BASE_URL`; local Qwen thinking settings remain available | Determined by `DRY_RUN` | Determined by `DRY_RUN` |
| `LLM_PROVIDER=huggingface` | HF router calls with independently resolved analyzer/verifier routes and no automatic Qwen-specific thinking field | Determined by `DRY_RUN` | Determined by `DRY_RUN` |
| `DRY_RUN=true` | Any configured provider above | `MockBusinessAPI`; records only | `FakeSMTPTransport`, even if SMTP is configured |
| `DRY_RUN=false` | Requires a non-demo provider and its credentials/endpoint | `HttpBusinessAPI` | `RealSMTPTransport` |
| `mail poll` / `worker run` | Either backend above | As above | Poll uses real IMAP; only `worker run` also drains the outbox |
| `replay-email` / `replay-directory` | Demo or configured HTTP model | Forced `MockBusinessAPI` | Forced `FakeSMTPTransport` |
| `evaluate` | Demo or configured HTTP model; explicit-pair and matrix forms both persist stage calls, cache, checkpoints, usage, cost, and budget state | Never constructed or called | Never constructed or called |

Important consequences:

- An explicit `LLM_PROVIDER` selects the backend. When it is omitted, non-empty
  `LLM_BASE_URL` selects `openai_compatible` and an empty value selects demo; `HF_*` settings alone
  do not implicitly select Hugging Face. Within HF mode, each non-empty provider-specific token,
  URL, or model setting wins over its compatibility alias, followed by the safe default.
- `DRY_RUN=false` requires a business API base URL, SMTP host, and non-demo model provider. OpenAI-compatible mode requires `LLM_BASE_URL`; Hugging Face mode requires an effective token. This does not certify model quality or provider health.
- Replay copies the loaded settings with `dry_run=true`, initializes the schema, and adds fixture senders to the static authorization set. It cannot call the live business API or real SMTP. Its JSON result includes stored escalation summaries.
- A dry-run worker can poll a real mailbox and call a configured model server while still using the mock business API and fake SMTP.
- Explicit-pair and matrix CLI evaluation both use SQLAlchemy for audit/cache/checkpoints but construct no mail, SMTP, or business API service. Either form can call a configured model provider. The lower-level `PipelineEvaluationPredictor` remains available as a non-persistent programmatic adapter.

## Persistence and audit trail

The schema stores separate identities and histories:

- `mail_accounts` and `email_messages` retain mailbox/RFC identity, parsed sections, raw storage reference or blob, deduplication, authorization, correlation, and processing status.
- `conversations` group mail threads; `requests` represent business cycles inside a conversation.
- `operations` hold independently evolving actions and fields. `field_revisions` record initial extraction and clarification/correction changes with source email/model-run links.
- `clarifications` bind an outbound question to exact operation IDs and requested fields.
- `model_runs` store inputs/hashes, raw and parsed final output, separated reasoning, base/resolved routes, reported provider/request ID, structured-output mode/schema/fallback/validation audit, timing, usage/logprobs, pricing/cost basis, cache linkage, and classified final errors.
- `inference_cache_entries`, `evaluation_runs`, and `evaluation_inferences` preserve cross-command reuse, original model-run provenance, dataset/configuration hashes, checkpoints, resume state, and budget/token/cost accounting. `calibration_artifacts` bind offline calibration parameters to a calibration dataset hash.
- `validation_decisions` store analyzer/verifier payloads, invariant results, reasons, and policy version `hybrid-v1`.
- `executions` store the operation revision, unique idempotency key, request/response data, dry-run flag, attempts, and status.
- `outbox_messages` separate logical outbound creation from SMTP delivery.
- `escalations` store a reason, summary, and evidence. Live mode also creates a structured outbound escalation and outbox row; dry-run mode keeps the escalation database-only.

## Failure behavior

- An analyzer or unexpected processor failure marks the stored email `FAILED`, records failed model/processing audit where applicable, and creates one processing-failure escalation. `processing retry-failed` reparses its stored raw MIME and retries the same logical row.
- A parse-fatal or raw-size failure marks the minimal row `QUARANTINED`, retains raw MIME, avoids normal-poll reparse, and requires an explicit `quarantine retry EMAIL_ID` after inspection.
- A verifier failure is fail-closed per operation: a failed model run and escalation are persisted and no API call is made.
- A business transport failure has an unknown outcome, records execution status `UNKNOWN`, and escalates the operation. Non-transport API errors are recorded as `FAILED` and also escalate.
- HTTP business retries are disabled unless `BUSINESS_API_IDEMPOTENCY_GUARANTEED=true`. Even then they are bounded and limited to transport errors and selected transient statuses.
- SMTP failures remain in the outbox for bounded retry. The logical outbound message is not recreated.
- One IMAP message failure is logged and does not stop processing later fetched UIDs.

## Current limitations

- The worker is single-process synchronous code. There is no queue, lease, row locking, or outbox claim protocol. Multiple outbox workers can select the same pending row and risk duplicate SMTP delivery.
- IMAP search defaults to `ALL` and refetches every UID on each poll; database deduplication makes this safe but inefficient. The persisted polling checkpoint fields are not used.
- A crash after a remote API accepted a request but before the result transaction commits leaves a durable pending execution. Automatic duplicate prevention is conservative, but there is no reconciliation command for that state.
- Writing a raw `.eml` file occurs before the email row commits. A database rollback can leave an orphan file.
- Live escalation is queued through the same outbox/SMTP path and requires an outbox drain, while dry-run escalation remains database-only. There is still no human queue UI, assignment/acknowledgement workflow, or resolution command.
- Live IMAP, SMTP, model-server, PostgreSQL, and telecom API interoperability require deployment testing. Normal tests use SQLite/mocked HTTP or deterministic models, the mock business API, and fake SMTP; separately marked HF live probes run only when explicitly enabled with credentials and a small cost cap.
- No throughput, horizontal-scaling, disaster-recovery, or retention guarantees are implemented.

For the model boundary, see [Model pipeline](model_pipeline.md). For operational risks and trust assumptions, see [Security](security.md).
