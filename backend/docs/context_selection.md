# Context selection

The application does not flatten an email thread into one prompt. Raw MIME and parsed sections remain stored for audit and retry, while the analyzer receives a labelled subset chosen from correlation and unresolved state.

## Selection flow

~~~mermaid
flowchart TD
    M["Stored parsed inbound email"] --> Z["Record sender authorization"]
    Z --> A{"Automated / self / delivery message?"}
    A -->|yes| I["Store as ignored<br/>no model context"]
    A -->|no| U{"Authorized sender?"}
    U -->|no| E1["Escalation record<br/>no model context"]
    U -->|yes| C["Correlate headers, markers,<br/>sender, and subject"]
    C --> X{"Conflict or ambiguous<br/>weak match?"}
    X -->|yes| E2["Escalation record<br/>no analyzer choice"]
    X -->|no| R{"Known outbound<br/>clarification reply?"}
    R -->|yes| CR["clarification_reply context"]
    R -->|no| W{"Weak subject-only<br/>correlation?"}
    W -->|yes| WF["possible_follow_up context<br/>automatic_execution_allowed=false"]
    W -->|no| K{"Known request ID?"}
    K -->|yes| SR["correlated_request_reply context"]
    K -->|no| NR["new_request context"]
~~~

Correlation is evaluated before context construction. Direct RFC reply/reference matches and valid visible request markers are strong; a unique normalized-subject match for the same sender is weak; a message with no match is new. Conflicts between headers and markers, several candidate conversations/requests, or header/marker evidence belonging to a different primary sender are escalated before analysis.

## Parsing and segmentation

`parse_email` retains:

- decoded RFC identity, sender/reply-to/recipients, subject, and date;
- plain text and original HTML text;
- attachment filename, content type, byte size, and SHA-256 metadata;
- latest-message, quoted-thread, and signature candidates;
- automated classification and parsing/segmentation warnings.

Plain text is preferred. When only HTML exists, a standard-library `HTMLParser` extracts visible text, excludes `script` and `style` content, and normalizes whitespace. Binary attachment contents are hashed for metadata and are not sent to a model.

`segment_reply` is deterministic and non-authoritative. It recognizes common English and French reply separators, quoted-line prefixes, and a small signature/footer set. Its confidence is:

- 0.95 for a recognized quote separator;
- 0.75 for quote-prefix fallback;
- 0.80 when no quote boundary is found;
- at most 0.45 when only quoted content remains;
- 1.0 for an empty body, accompanied by an `empty_body` warning.

Before prompting, `clean_high_confidence_artifacts` performs only narrow cleanup: Unicode normalization, known anonymization tags, mail/tel metadata, an Outlook short link, one external-email banner pattern, and common mobile footers. It preserves line boundaries and records which cleanups occurred.

## New-request context

`ContextBuilder.new_request` currently emits:

~~~json
{
  "mode": "new_request",
  "subject": "decoded subject",
  "latest_user_message": "cleaned latest-message candidate",
  "text_since_last_closed_request": "same cleaned latest-message candidate",
  "numeric_candidates": [],
  "closed_history_summary": null,
  "preprocessing_notes": [],
  "segmentation_confidence": 0.8
}
~~~

Numeric candidates are extracted only from the cleaned latest-message candidate. Quoted text, signature text, HTML, attachments, and prior closed operation values are excluded.

The field `text_since_last_closed_request` is not currently reconstructed from database history: it is an alias of the selected latest message. Likewise, `closed_history_summary` is always `null`. These names express a safety boundary, not a complete historical summarization feature.

This context is used when correlation does not identify an existing request, including a genuinely new conversation. A strong correlation with a known request uses the separate correlated-request context below.

## Clarification-reply context

A reply is targeted when `In-Reply-To` or `References` resolves to the stored outbound email for a `Clarification`. The database then supplies the exact request and `target_operation_ids` recorded when the question was created.

`ContextBuilder.clarification_reply` emits:

~~~json
{
  "mode": "clarification_reply",
  "request_reference": "SNOC-REQ-...",
  "latest_user_message": "cleaned reply only",
  "previous_agent_question": "stored exact question",
  "target_operations": [
    {
      "operation_id": "...",
      "action": "otp_number_change",
      "known_fields": {
        "pdv_code": "12345678",
        "phone": null
      },
      "missing_fields": ["new_phone"]
    }
  ],
  "numeric_candidates_from_latest_reply": [],
  "preprocessing_notes": []
}
~~~

Stored values and current reply candidates are deliberately separate. Only target operations are included. The analyzer can fill a missing value or report contradiction/correction; it cannot silently select another open request from the conversation.

When mapping returned proposals to targets, an exact `local_operation_id` match is preferred. Positional fallback is permitted only for exactly one target and one proposal; multi-target replies require explicit operation IDs and otherwise fail closed. Unmatched proposals remain available to create a new request, which supports a mixed reply containing clarification data plus a new action.

A visible request marker alone can strongly identify a request, but it does not identify a particular clarification. It therefore does not produce this targeted context.

## Strong correlated-request context

When headers or a visible marker strongly identify a stored request but not one particular clarification, `ContextBuilder.correlated_request_reply` emits:

~~~json
{
  "mode": "correlated_request_reply",
  "subject": "decoded subject",
  "request_reference": "SNOC-REQ-...",
  "request_status": "COMPLETED",
  "latest_user_message": "cleaned latest-message candidate",
  "closed_history_summary": null,
  "stored_operations": [
    {
      "operation_id": "...",
      "action": "vpn_access",
      "known_fields": {
        "pdv_code": "42000001",
        "phone": "0770000010"
      },
      "missing_fields": []
    }
  ],
  "numeric_candidates": [],
  "automatic_execution_allowed": false,
  "preprocessing_notes": []
}
~~~

The context separates current numeric candidates from stored operation fields and identifies the
request status. `automatic_execution_allowed` is false when the correlated request is completed
or when any configured context limit forces a reduction; otherwise this strong-correlation
context sets it true. Weak contexts always set it false.

An analyzer-labelled correction can be matched to an existing operation by operation ID or canonical action. Field changes create revisions. A proposal that is not consumed as a correction/clarification creates a new request, supporting a genuinely new request sent in a reused completed chain. The deterministic policy sends changes to completed operations to review and prevents execution of the completed revision.

Unlike the new-request context, this context intentionally shows labelled stored operation values. That improves correction/follow-up interpretation but means values from a completed request are present in the model input. The prompts instruct the analyzer not to reuse them for a new operation; current numeric candidates still come only from the latest user text.

## Weak possible-follow-up context

Subject fallback is accepted only when normalized subject plus sender identifies exactly one conversation and correlation does not report several open requests. The context is:

~~~json
{
  "mode": "possible_follow_up",
  "latest_user_message": "cleaned latest-message candidate",
  "possible_open_requests": [
    {
      "request_id": "...",
      "request_reference": "SNOC-REQ-...",
      "status": "NEEDS_INFORMATION",
      "operations": [
        {
          "operation_id": "...",
          "action": "otp_number_change",
          "missing_fields": ["new_phone"]
        }
      ]
    }
  ],
  "correlation_strength": "weak",
  "automatic_execution_allowed": false,
  "numeric_candidates": [],
  "preprocessing_notes": []
}
~~~

Known PDV and phone values are not included in this weak context. The analyzer may identify a follow-up, new request, or ambiguity, but the decision engine will not auto-execute an operation with weak correlation. Missing fields under weak correlation escalate rather than triggering another automatic question.

If subject fallback finds several conversations, or the candidate conversation has several open requests, the processor escalates before the analyzer rather than choosing the newest request.

## Numeric candidates and provenance

`extract_numeric_candidates` finds separated numeric groups containing 8–15 digits, optionally with a leading plus. Each candidate includes:

- normalized and raw value;
- exact character offsets;
- a short surrounding text window;
- source section;
- a hint: eight digits as PDV-or-unknown, 9–15 digits as phone-or-unknown, otherwise numeric-unknown.

The hint is not an attribution. Required-field evidence must be marked supported by the analyzer, independently supported by the verifier, pass deterministic formatting, and match either a current numeric candidate or the explicitly targeted strong stored state. New operations cannot authorize values from labelled stored/closed state. Candidate extraction remains limited to `latest_user_message` even when a bounded uncertain-thread snippet is shown.

## Enforced size and context limits

| Setting | Default |
|---|---:|
| `MAX_RAW_EMAIL_BYTES` | 10,485,760 bytes |
| `MAX_TEXT_PART_BYTES` | 1,048,576 bytes |
| `MAX_HTML_PART_BYTES` | 2,097,152 bytes |
| `MAX_ATTACHMENT_COUNT` | 20 |
| `MAX_ATTACHMENT_BYTES` | 5,242,880 bytes |
| `MAX_MODEL_CONTEXT_CHARACTERS` | 24,000 characters |
| `MAX_LATEST_MESSAGE_CHARACTERS` | 12,000 characters |
| `MAX_RELEVANT_THREAD_CHARACTERS` | 4,000 characters |

Raw input larger than `MAX_RAW_EMAIL_BYTES` is retained and quarantined before MIME parsing.
During parsing, `MAX_TEXT_PART_BYTES` and `MAX_HTML_PART_BYTES` bound decoded text, while
`MAX_ATTACHMENT_COUNT` and `MAX_ATTACHMENT_BYTES` create explicit attachment warnings. The raw
MIME remains the recovery/audit source even when decoded sections or attachment metadata are
bounded.

For model input, `MAX_LATEST_MESSAGE_CHARACTERS` bounds current prose,
`MAX_RELEVANT_THREAD_CHARACTERS` bounds the low-trust uncertain-thread excerpt, and
`MAX_MODEL_CONTEXT_CHARACTERS` caps the serialized context. Free text is shortened at protected
token boundaries so phone numbers, PDV codes, addresses, and other identifiers are not silently
cut. The builder removes low-trust prose first, then candidate snippets, and finally whole
structured entries from the least critical end if necessary; it never substring-truncates a
structured identifier.

Every reduction adds `context_limit_warnings`, sets `automatic_execution_allowed=false`, and is
passed to deterministic policy as incomplete context. Automatic execution therefore fails closed
even if the model otherwise returns a complete proposal.

## Verifier context

The verifier receives less conversational data than the analyzer and checks one operation at a time:

~~~json
{
  "context_mode": "clarification_reply",
  "latest_user_message": "...",
  "stored_operation_state": {
    "operation_id": "...",
    "action": "otp_number_change",
    "pdv_code": "12345678",
    "phone": "0555123456",
    "missing_fields": [],
    "status": "NEW",
    "current_revision": 2
  },
  "proposed_operation": {},
  "candidate_evidence": [],
  "correlation_strength": "strong"
}
~~~

It does not receive ground truth, credentials, authorization configuration, API endpoints, or an API client. Authorization and correlation decisions are passed independently to the deterministic policy rather than inferred from email text.

## What is stored but not prompted

The database retains the full raw MIME path/blob, bounded decoded plain text and HTML,
segmentation candidates, retained attachment metadata, parsing/limit warnings, and correlation
evidence. This supports audit and retry but expands the sensitive-data footprint. Retention in
storage does not imply inclusion in model context.

## Current limitations

- When deterministic segmentation confidence is below `0.8`, the analyzer may receive a
  protected-identifier-safe head/tail excerpt, bounded by
  `MAX_RELEVANT_THREAD_CHARACTERS`, under a labelled `untrusted_segmentation_candidate` section.
  No numeric candidates are promoted from it, and no model-based segmentation fallback is wired
  despite the packaged `reply_segmenter_v1` prompt.
- Character and MIME limits are enforced, but there is no tokenizer-aware prompt budget or model
  response-byte cap. Attachments inside the bounded raw MIME are still decoded in memory to
  calculate metadata hashes.
- “Text since last closed request” and trusted completion-boundary reconstruction are not implemented beyond using the current latest-message candidate.
- `automatic_execution_allowed` is a model instruction rather than a field read directly by
  `HybridDecisionEngine`. The same MIME/context-limit metadata is separately converted into the
  deterministic `input_context_complete` invariant; request status, weak correlation, operation
  mapping, and evidence are also passed independently to policy.
- Completed-request values are included as labelled `stored_operations`, but deterministic provenance prevents a newly materialized operation from authorizing those values. `closed_history_summary` remains `null`; there is no generated historical summary.
- Weak context exposes action and missing-field metadata but not known field values; this is conservative but can reduce semantic resolution.
- Deterministic separators cover a limited set of mail-client languages and formats. Raw content is preserved, but a bad split can omit relevant text from the prompt.
- No attachment text extraction, OCR, inline-image analysis, or malware scanning exists.

The downstream semantic and deterministic checks are described in [Model pipeline](model_pipeline.md); privacy implications are described in [Security](security.md).
