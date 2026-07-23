# Evaluation

The evaluation package measures model extraction and hybrid-policy behavior without constructing
mail, SMTP, or business-API services. The CLI uses SQLAlchemy for both an explicit analyzer/verifier
pair and the four-pair matrix, including persistent model-run audit, caching, checkpoints, resume,
usage/cost, and budget state. Demo, generic OpenAI-compatible, and Hugging Face providers are
supported, but none of these modes is an end-to-end production simulation.

## Running one evaluation

~~~bash
python -m snoc_agent.cli.main evaluate \
  --dataset "labeled_data/labeled data/SMOLDATA_last_1000_reviewed.csv" \
  --analyzer-model Qwen2.5-7B-Instruct \
  --verifier-model Qwen3-8B \
  --use-cache \
  --resume \
  --budget-usd 2 \
  --output-dir outputs/evaluation/qwen25_qwen3
~~~

`--limit N` evaluates the first `N` loaded examples; it is not a random or stratified sample.

Backend selection follows `LLM_PROVIDER=demo|openai_compatible|huggingface`. For compatibility, an omitted provider plus non-empty `LLM_BASE_URL` selects `openai_compatible`; otherwise it selects demo. Hugging Face routes must be checked with `models check` and are never silently substituted.

The deterministic mode does not load or run the model names passed on the command line. Those names remain experiment metadata, while the backend field identifies that predictions came from demo heuristics.

Run and compare all four Qwen2.5/Qwen3 pairings in one command:

~~~bash
python -m snoc_agent.cli.main evaluate \
  --dataset "labeled_data/labeled data/SMOLDATA_last_1000_reviewed.csv" \
  --matrix \
  --use-cache \
  --resume \
  --budget-usd 20 \
  --output-dir outputs/evaluation/qwen_matrix
~~~

Cache controls are mutually exclusive: `--use-cache`, `--no-cache`, and `--refresh-cache`. `--resume` reopens a matching incomplete run only when the dataset hash, configuration hash, and output directory match. `--checkpoint-every N` overrides `EVALUATION_CHECKPOINT_EVERY`; `--stop-before-budget-usd` can set a lower stop. If `HF_REQUIRE_BUDGET_CONFIRMATION=true`, add `--confirm-budget` after reviewing the limit.

The effective stop is the lower of `HF_STOP_BEFORE_BUDGET_USD` and 95% of the selected
`--budget-usd`; an explicit stop-threshold flag can lower it further.

Matrix mode evaluates each analyzer model once per input and each verifier model once per unique analyzer proposal/context. It then materializes the four policies without incorrectly sharing verification across different proposals. It writes one report directory per pairing plus comparison, `evaluation_run.json`, and `checkpoint.json` artifacts. A run is release-eligible only when both `unsafe_auto_execute_count == 0` and `validation_pass_but_wrong_count == 0`; if none qualify, no run is recommended. Deterministic-demo names and timings are never presented as Qwen measurements.

## Evaluation data flow

~~~mermaid
flowchart LR
    D["CSV / JSON / JSONL"] --> L["Dataset loader"]
    L --> X["EvaluationExample"]
    X --> P["Persistent selected-pair or<br/>four-pair runner"]
    P --> A["Production analyzer contract<br/>once per model/input"]
    A --> C[("Model-run audit +<br/>schema-aware cache")]
    A --> V["Production verifier contract<br/>per unique proposal/model"]
    V --> C
    V --> H["HybridDecisionEngine<br/>evaluation assumptions"]
    C --> B["Budget + checkpoint<br/>resume state"]
    H --> M["Metric engine"]
    X --> M
    M --> R["CSV + JSON + Markdown reports"]
    X -. "ground truth only" .-> O["oracle.py diagnostics"]
    H -. "production decision" .-> O
~~~

The prediction materializer used by the persistent CLI runner:

1. builds a new-request context from subject and body;
2. runs the production `EmailAnalyzer` contract;
3. runs the production `SemanticVerifier` contract for every proposal;
4. runs policy `hybrid-v1`;
5. emits predicted operations, decisions, agreement, contradiction, structured mode/validity, raw confidence, usage/cost, and cache-hit provenance.

Both CLI forms persist stage calls for audit/reuse and use the same budget and checkpoint engine.
The standalone `PipelineEvaluationPredictor` class remains available as a non-persistent
programmatic adapter. Neither path calls authorization, mail, outbox, SMTP, or business APIs. They
fix the following policy facts to isolate semantic and decision behavior:

- sender authorized;
- correlation `NEW` with no conflict;
- no prior execution;
- operation status `NEW`;
- API available and execution mode enabled;
- PDV pattern `^\d{8}$` and phone pattern `^\+?\d{9,15}$`.
- required numeric evidence constrained to candidates extracted from the current message;
- configured latest-message and serialized-context character limits, with any reduction passed to
  policy as incomplete context;
- no optional raw-confidence thresholds and no allowlisted VPN additional fields.

Consequently, auto-execution metrics do not measure live sender authentication, thread correlation, stored clarification merging, idempotency, adapter reliability, or SMTP behavior.

The predictor is passed an `EvaluationExample` object that contains expected fields, but its implementation reads only `subject` and `body`. The report metadata value `ground_truth_visible_to_predictor=false` records that intended discipline; it is not a process-level or type-level information barrier.

## Dataset loader and scoring eligibility

`load_dataset` accepts:

- CSV with French or English legacy columns;
- JSON containing a list, or an `examples`, `rows`, or `data` list;
- JSONL/NDJSON with one object per non-empty line.

Structured datasets can supply a JSON list of attributed operations. Legacy labels are canonicalized through the domain action mapping. Legacy `irrelevant`, `ambiguous`, `unknown`, and `automated` labels become non-action outcomes.

The loader refuses to invent attribution:

- a legacy `multiple` row has no separable operation truth and is excluded from all scoring;
- a legacy row with semicolon-separated PDV or phone values remains eligible for label scoring but is excluded from operation scoring;
- a row whose `evaluation_status` starts with `excluded` is excluded from both.

For the repository’s current `SMOLDATA_last_1000_reviewed.csv`:

| Rows | Use |
|---:|---|
| 1,000 | Loaded |
| 995 | Classification/label scoring |
| 954 | Operation and safety scoring |
| 5 | Excluded: legacy `multiple` without attribution |
| 41 | Label-only: semicolon multi-value fields without operation attribution |

These counts describe this checked-in file; a different dataset or later revision can produce different eligibility counts.

Build deterministic evaluation subsets and a source-hash manifest with:

~~~bash
python -m snoc_agent.cli.main evaluation datasets build \
  --source "labeled_data/labeled data/SMOLDATA_last_1000_reviewed.csv" \
  --output-dir outputs/evaluation
~~~

This creates the fake-data integration smoke set, demo-derived safety regression candidates plus explicit safety cases, the oracle false-escalation diagnostic set, group-aware development/calibration/held-out files, a split manifest, and stateful `.eml` scenario references. Threshold selection belongs on the calibration split, never the held-out test. `evaluation calibrate --method none|logistic|isotonic` persists its parameters with the calibration dataset hash.

## Metric definitions

Metrics use exact canonical string matching rather than fuzzy equivalence.

| Metric | Current definition |
|---|---|
| Classification accuracy / macro F1 | Exact expected versus predicted row label over label-scorable examples; per-class precision, recall, F1, and confusion matrix are also emitted |
| Operation count accuracy | Expected and predicted operation list lengths match |
| Action exact match | Multisets of canonical operation actions match |
| PDV / phone exact match | Multisets of values for that field match across the row |
| Numbers exact match | Both PDV and phone multiset checks pass |
| Joint action-and-fields exact match | Multisets of `(action, pdv_code, phone, additional_fields)` match; this detects values attributed to the wrong operation |
| Structured-output validity | Prediction was coercible without schema/operation parse failure |
| Analyzer/verifier agreement | Mean over predictions that report an agreement value |
| Contradiction metrics | Accuracy, precision, recall, F1, and prediction coverage only where expected contradiction truth is provided |
| Auto-execution coverage | Operation-scorable actionable rows with at least one auto-execution, divided by actionable rows |
| Operation auto coverage | Expected operations covered by counted auto executions |
| Unsafe auto execute | Auto-execution on a wrong/empty/non-action prediction, expected contradiction, failed reported invariant, or invalid structured output |
| Validation pass but wrong | Explicit/inferred validation pass with a non-exact operation prediction |
| Validation fail but correct | Explicit validation failure with an exact operation prediction |
| False escalation | Exact operation prediction escalated/reviewed despite no expected contradiction |
| Latency | Mean and interpolated p95 of reported or measured end-to-end predictor latency |
| Usage and cost | Request/token counts plus decimal input/output/total cost with basis `exact` for separately reported input/output costs, `provider_reported` for aggregate response cost, `estimated` from explicit catalog rates and usage, or `unknown` when required data is absent |

Operation comparisons are order-insensitive. Joint comparison still preserves action-to-field attribution because each operation is compared as a complete tuple.

`coerce_prediction` infers a validation pass when a top-level decision contains `AUTO_EXECUTE`. It does not infer an explicit validation failure from `ESCALATE`. The current pipeline predictor also does not emit `hard_invariants_passed`. Therefore validator failure metrics are most informative for predictors that explicitly provide those fields; they are incomplete diagnostics for the built-in pipeline adapter.

`unsafe_auto_execute` is a count of attempted operations on unsafe rows, while `unsafe_auto_execute_rows` counts affected examples. `false_escalation_rate` uses all actionable examples as its denominator; `false_escalation_share` uses escalated rows.

## Reports

`write_offline_run_report` writes atomically within the selected output directory:

- `predictions.csv` — per-example truth, prediction, exact-match flags, decisions, safety flags, structured modes/schema guarantee, raw confidence, latency, usage/cost, cache hits, and errors;
- `summary.json` — aggregate, per-class, and per-operation-action metrics;
- `confusion_matrix.json` — classification confusion counts;
- `per_error_category_examples.json` — bounded examples for label, count, action, PDV, phone, joint, structure, unsafe execution, validator, and escalation errors;
- `model_configuration.json` — analyzer/verifier names, backends, quantization labels, prompt versions, and metadata;
- `summary.md` — a compact metric table.

Every CLI evaluation also writes `evaluation_run.json`, a resumable `checkpoint.json`,
`failure_attribution.json`, and comparison files (a one-row comparison for an explicit pair).
Database rows link evaluation inferences and cache entries back to the original `model_runs`;
cached reuse never overwrites the source run.

Email subject/body content is excluded from error examples by default, and the CLI does not enable it. Prediction rows contain expected and predicted structured values, which can still be sensitive.

The legacy programmatic offline runner is sequential and can record per-example exceptions or fail
fast. The persistent CLI runner is also row-sequential, checkpoints completed calls, safely
materializes bounded structured-output failures, and pauses cleanly on transport, budget, or
manual interruption errors.

## Comparing model pairs

`compare_runs` reports core metrics and deltas from a selected baseline. It first applies the non-negotiable release gate:

~~~text
unsafe_auto_execute_count == 0
AND
validation_pass_but_wrong_count == 0
~~~

If no run passes, `recommended_run` is null. Among eligible rows, ordering is:

1. fewest unsafe automatic executions;
2. highest joint action-and-fields correctness;
3. highest auto-execution coverage;
4. lowest mean latency;
5. run name as a deterministic tie-break.

This is a mechanical ordering after the safety gate, not a deployment approval. It has no statistical significance testing, confidence intervals, class-specific gate, or minimum sample-size rule.

## Oracle isolation

Oracle logic exists only in `src/snoc_agent/evaluation/oracle.py`. It is not re-exported from `snoc_agent.evaluation`, and production modules do not import it.

`analyze_oracle_rescues` uses ground truth to select operation-scorable rows where:

~~~text
joint action-and-fields prediction is exactly correct
AND
the production decision contains ESCALATE
~~~

It reports:

- `oracle_rescue_rate`: selected exact predictions divided by production escalations;
- `potential_rescue_share_of_correct_predictions`: selected exact predictions divided by all exact operation predictions.

This measures an upper bound on false escalations that perfect ground-truth knowledge could identify. It is useful for diagnosing policy/model disagreement and estimating headroom. It is not deployable because production does not know which predictions are correct. Oracle rescue rate must not be described as a safe production rescue rate, and oracle candidates must never override the production decision.

## Reproducibility and limitations

- Persistent selected-pair and matrix runs capture dataset/configuration hashes, stage model runs, base/resolved routes, prompt/schema/settings hashes, fallback audit, usage/cost basis, cache provenance, budget state, and completion checkpoints. They still do not capture a code commit or model weights/tokenizer/serving-engine digest.
- `OfflineRun` holds start/finish timestamps and duration in memory, but the standard report writer does not persist those run timestamps.
- Any configured remote provider makes evaluation network-dependent. HF live tests are opt-in with `pytest -m hf_live`, load the repository-root `.env` through `Settings`, skip unless both `HF_TOKEN` and `RUN_HF_LIVE_TESTS=true` are present, and use `HF_LIVE_TEST_MAX_COST_USD` as the known-cost cap. Environment values override `.env`; CLI `--env-file` does not apply to pytest.
- Demo-backend scores measure heuristics, not either configured Qwen model.
- The built-in predictor tests only new-request contexts with fixed policy assumptions; it does not evaluate thread reconstruction, direct clarification state, weak correlation, corrections, authorization, deduplication, or external execution.
- Agreement is reported as true when the analyzer proposes no operations because there are no verifier disagreements; this can inflate agreement on non-action examples.
- Exact matching intentionally exposes attribution errors, but it does not normalize equivalent international phone formats or evaluate free-text evidence quality.
- Comparison recommendations are deterministic rankings without uncertainty estimates.

## Migration note: the 194 demo candidates

The historical “194 unsafe cases” came from 995 scorable rows processed by deterministic demo heuristics: 545 automatic-execution attempts and 194 `validation_pass_but_wrong` outcomes. The nominal four model names all received the same demo behavior because no real model endpoint was configured. These are candidate regression cases—not Qwen2.5 or Qwen3 failures.

`evaluation datasets build` reproduces and labels those candidates, writes `demo_vs_real_regression_report.json`, and includes them in `safety_regression.jsonl`. A completed matrix writes `failure_attribution.json` separating the immutable demo candidate list from real-model extraction mismatches, verifier disagreement/structure failures, decision-policy failures, and data/ground-truth exclusions. Real-model categories stay empty unless a non-demo provider actually ran; Hugging Face measurements are identified separately.

Production context and side-effect behavior are described in [Architecture](architecture.md) and [Context selection](context_selection.md).
