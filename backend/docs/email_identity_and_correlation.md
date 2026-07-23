# Email identity and correlation

This service deliberately keeps transport identity, email-thread identity, and business identity separate. An IMAP UID is not an RFC message identifier; an email conversation is not a business request; and one request may contain several operations. Collapsing any of these concepts would make replay, reused threads, clarification replies, and duplicate prevention unsafe.

This document describes the behavior implemented in `src/snoc_agent/mail`, `src/snoc_agent/db/models.py`, and `src/snoc_agent/workflow/inbound_processor.py`. The final section calls out the remaining MVP gaps explicitly.

## Identifier map

| Concept | Stored value | Scope and purpose |
|---|---|---|
| Mail account | `mail_accounts.id` UUID | Identifies one configured mailbox account. The CLI derives its logical name from `username@host:mailbox`. Credentials remain in environment configuration, never this table. |
| Physical mailbox location | `(mail_account_id, mailbox_name, uidvalidity, imap_uid)` | Unique location of one fetched item in one IMAP UID namespace. This is the only persisted IMAP locator. |
| Internal email identity | `email_messages.id` UUID | Stable primary key for every stored inbound or outbound logical email row. It is used by database relationships and logs. |
| RFC message identity | `rfc_message_id`, `normalized_message_id` | Sender-provided or locally generated `Message-ID`. The normalized form is the primary logical deduplication and reply-correlation signal when present. |
| RFC reply links | `in_reply_to`, `references_json` | Normalized identifiers of parent and ancestor messages. These may point to either inbound or stored outbound mail. |
| Raw-content identity | `raw_sha256` | SHA-256 of the complete raw MIME bytes. It is the logical deduplication fallback when `Message-ID` is absent. |
| Conversation | `conversations.id` UUID | Container for a reconstructed email chain. It can contain several business requests when a sender reuses a thread. |
| Business request | `requests.id` UUID | Authoritative internal identity of one request cycle. It is not derived from the subject or conversation ID. |
| Public request reference | `requests.public_reference` | Unique visible marker such as `SNOC-REQ-A84F91C274D2`; generated independently of the request UUID. |
| Operation | `operations.id` UUID | One action within a request. `sequence_number` is only an ordering label within that request, not a global identifier. |
| Clarification | `clarifications.id` UUID | Identifies one structured missing-information question, its target operations, and the reply that resolves or expires it. |
| Execution | `executions.id` UUID | Identifies the durable record created before a business API call. |
| Execution idempotency | `executions.idempotency_key` | Stable key `<operation UUID>:<operation revision>`. The database enforces global uniqueness. |
| Outbox item | `outbox_messages.id` UUID | Identifies one persisted logical outbound delivery. It references exactly one stored outbound email row. |

The internal UUID is always the database identity. RFC and visible identifiers are correlation signals, not substitutes for primary keys.

## IMAP identity: UID and UIDVALIDITY

An IMAP UID is unique only inside a particular mailbox UID namespace. `UIDVALIDITY` identifies that namespace. The same numeric UID can legitimately refer to a different message after the server changes UIDVALIDITY, so the worker stores and constrains the complete tuple:

```text
(mail_account_id, mailbox_name, uidvalidity, imap_uid)
```

`RealIMAPMailbox` selects the configured mailbox read-only, retrieves `UIDVALIDITY`, performs `UID SEARCH`, and fetches each candidate with:

```text
BODY.PEEK[] INTERNALDATE FLAGS UID
```

`BODY.PEEK[]` avoids intentionally setting `\Seen`. Sequence numbers returned by IMAP are never persisted. Each fetched message carries the mailbox, UIDVALIDITY, UID, internal date, flags, and raw MIME into the processor.

The current poller intentionally tolerates rediscovery. It searches the configured criterion (currently `ALL` in the CLI), and the database rejects or recognizes a previously stored physical locator. This makes the stored rows—not a fragile last-seen UID—the primary ingestion record.

### Current UIDVALIDITY behavior

When a physical message is stored, the processor updates `mail_accounts.last_uidvalidity` and advances `polling_checkpoint` to the greatest stored UID. The current CLI worker records those observations but does not use the checkpoint to narrow `UID SEARCH` and does not emit an explicit comparison/change event. Therefore:

- a new UIDVALIDITY is kept in a separate physical namespace because it is part of the unique tuple;
- the worker rescans the server-provided candidates in the new namespace;
- repeated messages are then suppressed logically by normalized `Message-ID`, or by raw SHA-256 when no valid `Message-ID` exists;
- old and new UID tuples are never rewritten or merged;
- there is currently no explicit UIDVALIDITY-change alert or checkpoint-reset event, and the checkpoint is not a complete rescan-progress mechanism.

This is safe for a single-worker, correctness-first rescan, but it is not a complete large-mailbox checkpoint implementation. Operators must not edit old `uidvalidity` values to make them match the new namespace. See `docs/runbook.md` for the change procedure and deployment limitation.

## RFC message identity

### `Message-ID`

Inbound `Message-ID` is stored in its original decoded form and in a comparison form. Normalization:

- extracts the first angle-bracketed identifier when present;
- trims surrounding whitespace;
- rejects an empty value or embedded whitespace;
- case-folds it;
- preserves one pair of angle brackets.

For example, `<Example-42@Mail.EXAMPLE>` becomes `<example-42@mail.example>`. A missing or invalid value is recorded in `parsing_warnings`; it does not prevent storage.

Outbound messages receive a generated RFC `Message-ID` before an outbox row is committed. This means a later reply can correlate even if SMTP delivery is delayed or retried.

### `In-Reply-To`

The parser normalizes the value as a single RFC message identifier. A known inbound or outbound match is a strong conversation signal. A match to an open clarification's outbound email also resolves the exact clarification and request.

### `References`

All parseable identifiers are normalized, order-preserved, and deduplicated in `references_json`. Outbound mail appends the source email's normalized `Message-ID` to the existing references list. A later inbound email can match any stored referenced identifier.

The correlator queries a known `In-Reply-To` first. Only when it does not match a stored message does it use `References` as the authoritative header set. It detects disagreement across the selected identifiers and compares the selected header request with any visible marker.

## Physical and logical deduplication

Deduplication happens before correlation or model inference.

1. If all physical locator fields are present, the processor first queries the complete IMAP tuple. An existing tuple returns the existing email ID immediately; no second row, model call, API call, or outbox item is created.
2. Otherwise, or for a new physical tuple, a valid normalized `Message-ID` is looked up as the logical signal.
3. If `Message-ID` is absent, raw MIME SHA-256 is used instead.
4. A logical duplicate at a different physical location is stored as a new `email_messages` row with `processing_status="duplicate"`, `duplicate_of_id` pointing to the original non-duplicate row, and the original conversation ID copied. It is not analyzed or executed.

The physical tuple is protected by a database unique constraint. `executions.idempotency_key` provides a separate final guard at the operation/API boundary.

Current limitation: `normalized_message_id` and `raw_sha256` are indexed but not unique. The application performs the lookup before inserting, which is sufficient for the supported single-worker mode but does not close every concurrent-ingestion race. Also, when a valid `Message-ID` is reused incorrectly by a sender, it wins over a differing raw hash and the later mail is classified as a logical duplicate. Investigate suspected identifier collisions rather than replaying them blindly.

## Conversation identity

A conversation is an email container, not a business request. `conversation_id` groups inbound and outbound messages that belong to the same apparent RFC chain. Its stored metadata includes a root internal email ID, normalized subject, primary sender, first/last timestamps, and status.

This separation is essential for reused chains:

```text
conversation C-1
├── request R-1 (completed VPN access)
└── request R-2 (later password reset in the same email chain)
```

The header link keeps the later email in `C-1`. Because no open request is selected from the closed request, analysis can create `R-2` with independent operations and fields.

`Conversation.status` currently remains `open`; the MVP does not close conversations automatically. Request and operation state remain authoritative for business completion.

## Implemented correlation order

The intended priority is RFC headers, visible request reference, internal conversation relationships, and finally a conservative subject fallback. The current implementation follows this flow:

```text
normalized In-Reply-To (when known), otherwise References
        │
        ├── known message(s) ──> strong conversation match
        │                         and exact clarification when applicable
        │
        ├── no known header match, valid SNOC-REQ marker ──> strong request match
        │
        ├── no strong signal, one subject+sender conversation ──> weak match
        │
        ├── conflicting independent signals ──> conflict/escalation
        │
        └── no match ──> new conversation
```

Detailed behavior:

1. The correlator queries normalized `In-Reply-To` first. If it matches no stored message, it queries the normalized `References` list instead. Stored inbound and outbound messages are both eligible.
2. Each matched message contributes its `conversation_id`.
3. A referenced outbound message tied to a `pending_send` or `open` clarification contributes the exact `clarification_id` and request.
4. Otherwise, a referenced message contributes a request only when its conversation currently has exactly one open request.
5. Visible `SNOC-REQ-*` markers are parsed from the subject and latest-user-message candidate. A known marker contributes its exact request and conversation.
6. Header and marker evidence is compared before either is accepted. Disagreement escalates rather than using the nominal priority to overwrite one signal.
7. If neither strong signal matches, normalized subject plus exact primary sender may group the mail into one conversation with `weak` strength. Subject fallback alone is not sufficient to complete an existing operation automatically.
8. With no candidate, the result is `new` and a new conversation is created.

The request repository treats `NEW`, `ANALYZING`, `ACTIVE`, `PARTIALLY_COMPLETED`, `NEEDS_INFORMATION`, and `READY_FOR_VALIDATION` as open. `ESCALATED`, `COMPLETED`, `FAILED`, `CANCELLED`, and `EXPIRED` are not candidates for implicit open-request selection.

### Conversation match versus request match

Header evidence may identify a conversation without selecting a request. This is deliberate:

- a reference to a completed chain keeps the new email in the old conversation but does not reopen the completed request;
- a reference to an ordinary message in a conversation with zero or several open requests does not invent one authoritative target;
- a direct reply to a stored clarification identifies both request and target operations.

For an exact clarification reply, the context builder loads only the clarification's target operations, known fields, missing fields, and previous question. A weak subject match supplies possible open requests as non-authoritative context. A correlation conflict bypasses normal analysis and creates an escalation.

## Conflict detection

The correlator records machine-readable conflict codes in `email_messages.correlation_details`:

| Code | Meaning |
|---|---|
| `headers_reference_multiple_conversations` | Header IDs match messages assigned to different conversations. |
| `headers_reference_multiple_requests` | Header-linked messages imply different open requests. |
| `multiple_visible_request_markers` | Subject/latest text contains markers for more than one known request. |
| `header_marker_request_conflict` | Header-derived and marker-derived request sets differ. |
| `header_marker_conversation_conflict` | Header-derived and marker-derived conversations differ. |
| `header_sender_mismatch` | Header-linked conversation ownership differs from the current primary sender. |
| `marker_sender_mismatch` | A visible marker belongs to a conversation whose primary sender differs from the current sender. |
| `multiple_open_requests` | One weak subject-matched conversation contains several open requests. |
| `subject_matches_multiple_conversations` | Subject plus sender still matches more than one conversation. |

Any `conflict` result, and a weak result carrying a conflict, is persisted and escalated before the analyzer runs. Marker/sender validation makes a copied public reference insufficient to hijack another sender's request. Authorization is checked independently before correlation.

## Visible and machine-readable outbound markers

Every clarification and completion reply contains the public request reference in the subject and body. Outbound rows also store:

```text
X-SNOC-Request-ID
X-SNOC-Operation-IDs
X-SNOC-Clarification-ID   # clarifications only
```

Custom headers are useful audit metadata, but the service does not rely on them surviving a user's mail client. Normal RFC reply headers and the visible reference are the supported return path.

Completion mail adds:

```text
[[SNOC_REQUEST_CLOSED:SNOC-REQ-XXXXXXXXXXXX]]
```

The marker is a visible context boundary and fallback reference. Database request/operation state remains authoritative, and the marker never authorizes execution by itself.

## Clarification linkage

The outbound clarification is committed transactionally with:

- its own internal email UUID and generated RFC `Message-ID`;
- the request and conversation IDs;
- `In-Reply-To` pointing to the inbound source email;
- accumulated `References`;
- one clarification UUID containing target operation UUIDs and requested fields;
- one unique outbox row.

When a reply references that outbound `Message-ID`, the lookup path is:

```text
inbound reply
  -> stored outbound email
  -> clarification
  -> request
  -> target operations
```

Only clarifications in `pending_send` or `open` participate in this exact lookup. Resolved or expired clarifications are not silently reopened.

## Operation and execution identity

Operations are independently stateful even when one email requests several actions. Their UUIDs, rather than action names or list position, identify clarification targets and revision history.

Initial extraction creates `field_revisions` rows with reason `initial_extraction` for each populated core field while the new operation remains at revision `1`. Each later material field change applied from a clarification or correction creates another field-revision row and increments `operation.current_revision` once per changed field. Execution uses:

```text
idempotency_key = <operation.id>:<operation.current_revision>
```

The execution row and unique key are committed before the API call. Re-entering execution for the same revision returns the existing execution record and does not call the adapter again. A genuine corrected field creates a new revision and therefore a different key, but corrections after completion are routed to human review rather than executed automatically.

## Known MVP boundaries

The following are documented limitations of the current code, not supported guarantees:

- `mail_accounts.last_uidvalidity` and the greatest stored UID are recorded, but polling still intentionally searches all configured candidates and has no explicit UIDVALIDITY-change event.
- A known `In-Reply-To` outranks `References`; if it is unknown, conflicting matches within the selected `References` set still escalate.
- The conversation graph is implicit in stored message header links. There is no separate parent/child edge table or reverse-child traversal pass.
- Existing operations are updated automatically only for an exact clarification reply or an analyzer-classified correction. A generic reply to the sole open request is not merged as a general follow-up path in this MVP.
- Subject fallback is exact normalized subject plus exact primary sender; aliases, forwarding, and mailbox ownership changes require human handling.
- Logical `Message-ID`/hash deduplication is application-level, so production deployment should run one ingestion worker until database-level claiming/uniqueness is added.
- Physical duplicate rediscovery returns the original row rather than inserting a separate duplicate-event row.
- The correlation engine does not repair a conflict automatically. The safe recovery path is a new, correctly threaded sender reply or explicit human administration.
