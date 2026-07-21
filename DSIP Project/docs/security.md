# Security

This is a safety-oriented MVP, not a completed production security posture. The controls below are present in code; the remaining-risk section is part of the operating contract.

## Trust boundaries

~~~mermaid
flowchart LR
    MAIL["Untrusted email<br/>headers, body, HTML, attachments"] --> APP["Application process<br/>parser + workflow policy"]
    OP["Trusted operator<br/>environment configuration"] --> APP
    APP --> DB[("Sensitive database<br/>and raw .eml storage")]
    APP --> LLM["External/local model server<br/>untrusted output"]
    LLM --> APP
    APP --> API["Telecom business API<br/>validated response"]
    API --> APP
    APP --> SMTP["SMTP delivery boundary"]
~~~

The intended trust model is:

- Email content, display names, reply headers, visible request markers, HTML, and model output are untrusted.
- Operator configuration and database state are trusted inputs only to the extent that deployment access controls protect them.
- A model server is allowed to interpret text but not authorize, select credentials/endpoints, change policy, or execute an operation.
- A business API response is not authoritative until its HTTP status, size, JSON schema, and explicit boolean `success` are validated.
- SMTP acceptance confirms handoff only; it does not authenticate the eventual reader or prove delivery.

## Controls implemented

### Inbound identity and authorization

- Physical IMAP deduplication uses account, mailbox, `UIDVALIDITY`, and UID. Logical deduplication uses normalized RFC `Message-ID` or raw-message SHA-256.
- The real IMAP client selects the mailbox read-only and fetches with `BODY.PEEK[]`.
- `StaticSenderAuthorizer` parses exactly one mailbox, rejects malformed/control-character input, case-normalizes it, and requires an explicit configured address.
- Authorization is stored with a reason and evaluated outside the model. Unauthorized non-automated mail creates an escalation record before model analysis or API execution.
- An LDAP/AD adapter protocol and fail-closed wrapper exist. Without an adapter, every LDAP lookup is denied.

These controls authenticate only the parsed `From` address against a local list; they do not authenticate who transmitted the message.

### Correlation and replay resistance

- Header, marker, subject, request, and clarification identity are separate concepts.
- A visible marker is accepted only if it maps to a stored request; marker/header disagreement, several visible markers, several header requests/conversations, and marker/primary-sender mismatch escalate.
- Subject fallback is weak and cannot auto-execute. Several candidate conversations or open requests escalate rather than selecting the newest.
- Completed/cancelled operations cannot execute. Corrections and completed-operation replies are routed to review.
- A unique database idempotency key is derived from operation UUID plus revision and is persisted before the API call. Reusing a mock key with different data fails closed.

### Model boundary

- Analyzer and verifier prompts state that email is untrusted data and cannot alter policy, call tools, authorize, or invent identifiers.
- Context is serialized as JSON and labelled inside application/verification delimiters rather than concatenated with the system instruction.
- Strict Pydantic v2 schemas forbid extra fields and lax type coercion. Confidence ranges and enumerated actions/evidence sources are validated.
- Every mode ends in strict local Pydantic validation. Hugging Face fallbacks occur only after explicit capability rejection; only prompt-enforced JSON permits one repair request. Final analyzer failure prevents processing, and verifier failure escalates the affected operation.
- Required evidence must be supported, and quoted closed history cannot be the sole source of a required value.
- The verifier is a separate call per operation. Its result still remains untrusted until deterministic policy checks pass.

### Deterministic side-effect gates

`HybridDecisionEngine` requires authorization, valid structure, canonical action, complete and correctly formatted fields, complete bounded model context, safe correlation, no prior execution, an open operation, no closed-history-only evidence, configured execution mode, semantic agreement, no contradiction/ambiguity, and API availability. Any context-limit warning disables automatic execution.

The execution layer rechecks operation state and required fields before selecting one of four fixed adapter methods. Models do not receive endpoint configuration or credentials and cannot call adapters directly.

Business adapter protections include:

- relative configured endpoint paths and percent-encoded path parameters;
- validated eight-digit PDV and bounded safe idempotency key;
- reserved core payload fields that optional VPN data cannot override;
- Bearer token added only by the adapter;
- configured timeout and a maximum of five retries;
- retries disabled unless remote idempotency is explicitly declared guaranteed;
- a 1 MB maximum business-response body;
- strict explicit-success response validation.

Transport uncertainty is fail-closed for further automatic execution: a business timeout/transport error is recorded as `UNKNOWN`, the operation escalates, and a structured escalation records the execution evidence and warns the operator to reconcile the idempotency key before retrying. A validated API rejection is recorded as `FAILED` with a separate structured failure reason.

### Outbound mail

- Outbound messages are persisted before SMTP, with generated RFC `Message-ID`, `In-Reply-To`, references, public request reference, and internal request/operation/clarification headers.
- Sender, recipient, subject, and generated header values reject CR/LF header injection.
- Outbound content is `text/plain`; the current templates do not render user-controlled HTML.
- A transactional outbox prevents an SMTP retry from creating a second logical clarification. Transient failures are bounded.

### Secrets and logs

- IMAP, SMTP, model API, and business API secret fields use Pydantic `SecretStr`, reducing accidental exposure through settings representation.
- `HF_TOKEN` is never logged or persisted. `HF_EXTRA_BODY_JSON` must be an object, cannot override core request fields, and its values are neither logged nor persisted verbatim.
- Clients are constructor-injected; credentials are not stored in application database entities.
- JSON logging emits a fixed message and optional correlation IDs. The current workflow does not log full email bodies or authorization/API tokens.
- `LOG_EMAIL_CONTENT` defaults to false.

## Sensitive-data footprint

The absence of body logging does not mean the application avoids content storage. By default it stores:

- raw MIME as a filesystem `.eml`; when file storage is disabled, the raw bytes are stored in the database;
- decoded plain text, HTML, latest/quoted/signature sections, addresses, headers, and attachment metadata;
- model input contexts, raw model output, parsed output, evidence, and validation decisions;
- API request and response bodies;
- outbound recipient, subject, body, and headers;
- escalation evidence.

Attachment binary content is not stored as a separate attachment object and is not prompted, but it remains inside the retained raw MIME and is decoded in memory to calculate size and SHA-256.

`LOG_EMAIL_CONTENT` is currently a configuration field only; no conditional body-logging path is implemented. Conversely, model-run audit persistence stores selected email content regardless of that logging flag.

## Enabling live effects

`DRY_RUN=true` is the default. It selects `MockBusinessAPI` and `FakeSMTPTransport`. Escalations are persisted but do not create an outbound escalation email in this mode.

Setting `DRY_RUN=false` requires business API and SMTP configuration plus a non-demo model provider. OpenAI-compatible mode requires `LLM_BASE_URL`; Hugging Face mode requires an effective token and can use the default router URL. Escalations also create a structured outbound email addressed to `ESCALATION_RECIPIENT` through the transactional outbox. Live configuration still does **not**:

- require TLS schemes/modes;
- require an operator confirmation at execution time;
- verify that a model pair passed an evaluation gate.

Provider-specific validation prevents the built-in demonstration backend from driving live effects. `models check` can verify current HF authentication, catalog routing, chat completion, and structured output, but it does not certify model quality or future availability.

Replay copies settings with `dry_run=true` and automatically adds senders found in replay files to the authorization set. It therefore cannot call the live business API or real SMTP. It can still call a configured model server and persist sensitive replay content, and its JSON output includes database escalation summaries.

A dry-run worker can still read a real IMAP mailbox and send sensitive context to a configured model server. With the Hugging Face router, that context may leave the organization and reach the dynamically routed inference provider. “Dry run” controls business API and SMTP effects, not ingestion or model disclosure.

## Remaining risks

### Message authenticity and request ownership

- There is no SPF, DKIM, DMARC, S/MIME, or PGP verification. A spoofed `From` address that passes upstream mail controls can satisfy the static whitelist.
- Runtime construction always uses the static whitelist; the LDAP adapter is not wired into CLI settings.
- Marker and header correlation both compare the inbound sender with the conversation's primary sender; a cross-sender reference becomes a correlation conflict. This is mailbox-string ownership, not cryptographic identity proof.
- Authorization checks `From`. A mismatched `Reply-To` is retained for audit but ignored for automatic requester replies, which are addressed to the authorized sender.
- Public request markers are identifiers, not secrets or authenticators.

### Prompt and model risks

- Textual XML-like delimiters are instructions to the model, not a parser-enforced sandbox. Email can contain delimiter-looking text, adversarial instructions, or model-specific attacks.
- VPN `additional_fields` keys require an explicit deployment allowlist; non-null values also require matching supported evidence and verifier support. The application still lacks a deployment-specific type/schema registry for those optional fields, so the safest default is the empty allowlist.
- Optional analyzer and verifier raw-confidence thresholds fail closed when configured. They are disabled by default because no calibrated release values are bundled. Offline logistic/isotonic calibration can persist a calibration-split artifact, but it is not automatically installed as a production release policy; there is still no output-content policy or independent model-server attestation.
- Configurable caps cover raw MIME, text/HTML parts, attachment count/size, latest message, relevant thread, and total selected context. Reductions create warnings and block automatic execution when interpretation is incomplete. Tokenizer-aware prompt budgeting and an inference response-byte cap remain absent.
- A configured model server receives sensitive selected context. There is no data-loss-prevention filter or guarantee about that server’s retention.

### Storage, logging, and audit

- Database and raw-email encryption at rest, field-level encryption, retention/deletion schedules, backups, key management, and access control are not implemented by the application.
- Raw-file directory ownership and permissions are not set explicitly. The configured path must be secured by deployment.
- Model/API payloads and outbound mail can contain PDV/phone data. Inspection CLI commands have no role-based access control.
- Audit rows and hashes are not signed or append-only; a database administrator can alter them.
- `db init` renders the configured database URL with its password redacted. Operators must still avoid exposing credentials through shell history, environment inspection, or external SQLAlchemy logs.
- Exception strings are persisted in warnings/escalation evidence. External error details should be reviewed before production exposure.

### Transport and availability

- The business client accepts both `http://` and `https://`. IMAP SSL is configurable, and live SMTP can be configured with neither implicit SSL nor STARTTLS. The application does not enforce encryption in transit, certificate pinning, mTLS, or private-network restrictions.
- The model base URL is not scheme-validated and has no response-size cap, circuit breaker, or egress allowlist.
- Raw/MIME part and attachment limits are enforced, but attachment payloads inside the bounded raw message are still decoded to calculate metadata and are not malware-scanned.
- Outbox rows are selected without a lease or row lock. Concurrent outbox workers can send the same pending message.
- A crash after remote API acceptance but before local result commit requires manual reconciliation. The durable idempotency record prevents a blind second call but no reconciliation workflow exists.
- Live escalation sends a structured plain-text notification through ordinary SMTP; dry-run escalation is database-only. There is no authenticated case-management UI, acknowledgement, assignment, or resolution workflow.

## Deployment requirements not yet encoded

Before live use, add or enforce externally:

1. an approved-model/server release gate, including disclosure rules for replay data;
2. authenticated sender controls and request-ownership checks, including `Reply-To`;
3. HTTPS/IMAPS/SMTP TLS requirements, restricted egress, and managed secrets;
4. encrypted storage, least-privilege database/filesystem access, retention, and redaction rules;
5. deployment review/tuning of the enforced size limits, plus attachment security scanning and tokenizer-aware model limits;
6. a deployment-specific typed schema registry for the already allowlisted API optional fields;
7. outbox claiming and execution reconciliation for multi-worker/crash safety;
8. authenticated escalation case handling, acknowledgement, assignment, access control, and resolution audit;
9. evaluated model/prompt release gates and live integration tests.

The exact runtime mode matrix is in [Architecture](architecture.md), and model-specific behavior is in [Model pipeline](model_pipeline.md).
