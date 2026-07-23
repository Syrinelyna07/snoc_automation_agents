# Model pipeline

The model boundary follows one rule: models propose and inspect semantics; application code authorizes, validates, changes state, and performs side effects. Neither analyzer nor verifier receives a business-API adapter.

## Pipeline

~~~mermaid
flowchart TD
    C["Labelled selected context"] --> A["Analyzer / verifier request"]
    A --> COMPAT{"Provider accepts<br/>strict JSON Schema?"}
    COMPAT -->|yes| S1
    COMPAT -->|explicit rejection| OBJ["JSON object fallback"]
    OBJ -->|explicit rejection| PROMPT["Prompt JSON fallback<br/>at most one repair"]
    OBJ --> S1
    PROMPT --> S1
    S1{"Strict Pydantic<br/>schema valid?"}
    S1 -->|no after bounded policy| F1["Fail message / no execution"]
    S1 -->|yes| P["Persist analysis<br/>materialize operations"]
    P --> V["Verifier call<br/>for each operation"]
    V --> S2{"SemanticVerification<br/>schema valid?"}
    S2 -->|no| F2["Escalate operation"]
    S2 -->|yes| H["HybridDecisionEngine<br/>semantic agreement + hard invariants"]
    H -->|AUTO_EXECUTE| E["ExecutionService"]
    H -->|ASK_FOR_INFORMATION| Q["Structured clarification"]
    H -->|ESCALATE / REVIEW_CORRECTION| R["Human escalation record"]
    H -->|IGNORE| I["No business operation"]
~~~

Candidate extraction is deliberately non-authoritative. Regex discovers numeric spans and preserves their source section and offsets; the analyzer attributes values to operations; the verifier independently checks support; deterministic code validates the final field formats.

## Models, prompts, and backend selection

| Stage | Prompt version | Default configured model | Default temperature | Runtime behavior |
|---|---|---|---:|---|
| Analysis | `analyzer_v1` | Alias: `Qwen2.5-7B-Instruct`; HF: `Qwen/Qwen2.5-7B-Instruct` | 0.0 | One call per email context |
| Verification | `verifier_v1` | Alias: `Qwen3-8B`; HF: `Qwen/Qwen3-8B` | 0.0 | One call per proposed operation |
| Reply segmentation | `reply_segmenter_v1` | None | n/a | Prompt is packaged but is not called; runtime segmentation is deterministic |

Prompt files live under `src/snoc_agent/prompts` and the versions are constants in `ai/prompts.py`. Successful and failed production-path analysis/verification audit rows store the prompt version in `model_runs`.

`build_model_services` selects a first-class provider:

- `LLM_PROVIDER=huggingface` uses the HF router, resolves analyzer/verifier base IDs independently to `:cheapest`, `:fastest`, `:preferred`, or an explicit provider, and retains both base and routed IDs. `models list` and `models check` discover current availability rather than hardcoding it.
- `LLM_PROVIDER=openai_compatible` posts to `{LLM_BASE_URL}/chat/completions`; analyzer and verifier can use different configured names but share the HTTP backend.
- `LLM_PROVIDER=demo` uses deterministic keyword/regex heuristics for workflow demonstration and offline tests. It is not Qwen inference or production validation.
- If `LLM_PROVIDER` is omitted, a non-empty `LLM_BASE_URL` preserves the legacy OpenAI-compatible selection; otherwise demo is selected.
- `MockLLMBackend` consumes queued deterministic fixtures and is used by integration tests; normal CLI construction does not select it.

For Hugging Face, the default `HF_USE_JSON_SCHEMA=true` attempts strict `json_schema` first. Only
an explicit capability rejection permits `json_object`; only rejection of both structured modes
permits prompt-enforced JSON, with at most one repair. Disabling strict mode starts at JSON object
and cannot claim a schema guarantee. Pydantic validation remains mandatory in every mode, and the
recorded mode determines whether schema guarantee can be claimed. Reasoning fields and leading
`<think>` blocks are stored separately and never parsed as the final JSON answer.

Local OpenAI-compatible Qwen3 settings may send `chat_template_kwargs.enable_thinking` when explicitly configured. Hugging Face sends no Qwen-specific thinking parameter automatically; advanced provider parameters can be supplied through validated `HF_EXTRA_BODY_JSON`, whose values are not logged or persisted verbatim.

Transport retries are limited to rate limits, timeouts, and temporary 502/503/504 failures. They
use exponential backoff with jitter and honor `Retry-After`; authentication, permission, invalid
model/request, exhausted budget, and exhausted malformed-output policy are not retried. Transport
retries, compatibility fallbacks, and the single prompt repair are separate paid requests, each
passes the budget guard, and their reported usage/cost is aggregated.

The model registry names four experiment pairs:

- `qwen25_qwen25`
- `qwen3_qwen3`
- `qwen25_qwen3`
- `qwen3_qwen25`

The CLI evaluation command accepts explicit analyzer and verifier model strings; it does not
expand registry pair names automatically. Explicit-pair and `--matrix` commands both use the
persistent cache/checkpoint/budget runner; matrix mode selects all four registry pairs.

## Analyzer contract

`EmailAnalyzer` serializes the selected context as JSON inside an explicit `<APPLICATION_CONTEXT>` delimiter. `EmailAnalysis` is strict and forbids extra fields. It contains:

- a message kind: new request, clarification reply, correction, mixed, irrelevant, ambiguous, or automated;
- zero or more operations with canonical action, PDV, phone, optional fields, missing fields, evidence, ambiguity reasons, and raw self-reported confidence;
- referenced operation IDs, new-request indication, contradiction indication/details, and unresolved ambiguities.

Each evidence item states its field, value, source, text, and whether support is supported, unsupported, or unclear. The allowed source taxonomy separates latest mail, stored request state, prior question, relevant context, quoted closed history, and unknown origin.

The analyzer prompt treats email content as untrusted data, disallows policy changes and tool calls, instructs the model not to invent identifiers or copy values from closed history, and requires separable multi-operation output. These instructions reduce prompt-injection risk but do not make model output trusted.

## Verifier contract

For each proposal, `SemanticVerifier` receives a fresh labelled payload:

- context mode and latest user message;
- stored state for that one operation;
- the full proposed operation;
- current numeric candidates;
- correlation strength.

The payload is enclosed by `<VERIFICATION_CONTEXT>`. The strict response independently reports support for action, PDV, phone, and every proposed optional field; compatibility with stored state; contradiction, correction, and new-request signals; missing fields; evidence summary; and raw confidence.

“Independent” here means a separate prompt, schema, and call that does not accept the analyzer’s confidence as authority. It can still be the same model and backend when configured that way; the current runtime does not enforce model-family diversity.

If analysis fails, the message is marked failed and remains retryable. If verification fails, only the affected operation is escalated and execution is refused.

## Deterministic decision policy

`HybridDecisionEngine` policy version `hybrid-v1` combines semantic results with state that models cannot change.

The hard-invariant map contains:

- authorized sender;
- valid structured output;
- complete bounded model context with no limit warning;
- known canonical action;
- complete required fields with configured PDV and phone formats;
- no request-correlation conflict;
- no execution already recorded for the same operation revision;
- operation not completed or cancelled;
- no required value sourced only from quoted closed history;
- required evidence resolves to current-message candidates or strongly correlated stored state;
- configured analyzer/verifier raw-confidence thresholds pass when enabled;
- optional fields are allowlisted and independently supported by evidence and the verifier;
- a correlated proposal retains the stored operation action;
- execution mode configured, meaning dry-run or a non-empty business API base URL.

Automatic execution additionally requires:

- correlation strength `NEW` or `STRONG`;
- verifier support for the action and required semantic fields;
- supported evidence for every required field;
- analyzer/verifier agreement;
- no analyzer or verifier contradiction;
- no scoped or unscoped ambiguity;
- no unexpected new request in a non-new context;
- an available API adapter.

Missing data results in `ASK_FOR_INFORMATION` only when the action is supported, all deterministic field errors are missing-required-field errors, correlation is new or strong, no contradiction or major ambiguity exists, evidence provenance and configured confidence gates pass, optional fields are allowlisted and supported, the stored action still matches, and the sender is authorized. Otherwise the operation escalates.

Irrelevant or automated analysis is ignored. A verifier-detected correction, or an operation already completed, is sent to `REVIEW_CORRECTION`. Unknown actions, disagreement, weak correlation, conflict, closed-history evidence, invalid formats, or API unavailability fail closed.

## State and audit outputs

On successful calls, `persist_model_run` stores:

- backend, reported model name, base/resolved route, requested/reported provider, provider request ID, derived family, quantization label, and prompt version;
- SHA-256 of canonical input context and the full input context;
- raw final output, parsed output, and separated reasoning;
- structured-output mode/schema/name, fallback reason, parse attempts, and validation errors;
- latency, prompt/completion/total tokens, raw logprobs, pricing metadata, decimal input/output/total cost, cost basis, generation-settings hash, and cache-source linkage when supplied.

Cost basis is `exact` when a response reports both input and output components,
`provider_reported` when it reports only a usable aggregate, `estimated` when explicit catalog
rates can be applied to usage, and `unknown` otherwise. No missing price is synthesized.

Every successful verifier decision also creates a `validation_decisions` row containing analyzer and verifier results, every invariant boolean, final decision/reasons, and policy version. Operations retain evidence/provenance, analyzer and verifier confidence metadata, model agreement, decision, revision, and execution eligibility.

`persist_failed_model_run` records failed analyzer and verifier calls with configured
model/backend/prompt metadata, full hashed input context, `structured_output_valid=false`, a
classified final error, and a bounded safe error string. Actual raw/reasoning output, timing,
attempt count, usage, pricing, cost, schema/fallback audit, and logprobs are retained when the
failure occurred after a provider response; unavailable fields remain null and are never
invented. Analyzer failure also marks the email failed and creates a processing-failure
escalation; verifier failure escalates the affected operation.

## Confidence semantics

Self-reported confidence is audit metadata, not an execution probability. Optional `ANALYZER_MIN_RAW_CONFIDENCE` and `VERIFIER_MIN_RAW_CONFIDENCE` gates can be configured; when enabled, a missing or lower value fails closed. No threshold is enabled by default because the repository does not bundle a calibration decision.

`ai/confidence.py` calculates an uncalibrated margin from either a custom `label_logprobs` map or standard token `content[].top_logprobs`. Raw logprobs and minimum/mean token or label margins are persisted and exposed in evaluation reports when present. Missing or provider-specific incompatible shapes remain absent; a margin is a diagnostic separation score, not a calibrated correctness probability.

## Known limitations

- Live settings require a non-demo provider and provider-specific credentials/endpoint. HF `models check` verifies current catalog/routes and minimal chat/structured probes, but no endpoint/model is automatically production-certified.
- No calibrated threshold artifact, adjudicator, ensemble voting, or production-safe “rescue” policy is bundled. Offline `none`, logistic, and isotonic calibration can persist an artifact only from the calibration split; installing any release threshold remains a deployment decision.
- Contexts have enforced character budgets and fail closed when reduced, but there is no tokenizer-aware prompt budget.
- The HTTP model adapter has no response-byte cap, circuit breaker, streaming, model digest verification, or continuous health check.
- Base/resolved routes and reported provider/request ID are persisted, but serving engine version, tokenizer revision, weights checksum, and generation seed are not.
- The packaged segmentation prompt is unused, and no segmentation model run is audited.
- Successful model contexts and raw outputs can contain sensitive mail content. Their persistence and protection are deployment responsibilities; see [Security](security.md).

Evaluation-specific assumptions and oracle isolation are documented in [Evaluation](evaluation.md).
