# Existing pipeline inventory

## Scope and provenance

This document records the repository artifacts that predate the production-style SNOC email service. It identifies the latest implementation of each experimental capability, what is safe to reuse, what requires adaptation, and what remains evaluation-only.

Dates are filesystem modification times in UTC+01:00. Commit dates are unavailable because the repository snapshot contains only an empty .git placeholder.

The most important reproducibility fact is that every main LLM notebook has execution_count set to null and contains no saved outputs. The repository also does not contain the Kaggle LLM prediction, validation, or safety CSVs that those notebooks say they write. Statements such as “zero unsafe auto-execution” therefore describe prior experiments but are not independently reproducible from this snapshot.

## Executive summary

- The newest and most complete LLM notebook is notebooks/kaggle_email_llm_number_extraction_coverage_tuning.ipynb, modified 2026-07-07.
- The newest text-cleaning implementation is scripts/semantic_clean_csv.py, modified 2026-07-14. It is newer than every notebook and has a verified, packaged output.
- The coverage-tuning notebook is the source for the latest candidate extraction, structured output parsing, deterministic validation, semantic SLM review, oracle analysis, and requested safety metrics.
- notebooks/kaggle_email_llm_number_extraction.ipynb and notebooks/kaggle_email_llm_number_extraction_safety_zero_unsafe_backup.ipynb are byte-identical.
- The four extraction-lineage notebooks duplicate most of their code. Across them, 119 functions or classes are AST-identical.
- Existing notebook schemas support one scalar action and one PDV/phone pair. They do not support multiple operations, corrections, persisted request state, field provenance, or reply correlation.
- Oracle selection and regression-row guards use gold evaluation data and hardcoded row IDs. They must remain isolated from the production workflow.
- No existing code implements IMAP polling, MIME parsing, RFC conversation reconstruction, stateful requests, clarification replies, idempotent execution, SQL persistence, or business API adapters.

## Notebook lineage

| Artifact | Modified | Cells | Role | Disposition |
|---|---:|---:|---|---|
| notebooks/kaggle_email_llm_number_extraction_coverage_tuning.ipynb | 2026-07-07 16:02 | 32 | Latest joint classification, candidate extraction, validation tuning, semantic SLM review, oracle and metrics | Primary notebook reference; adapt into typed modules |
| notebooks/failed_experiment.ipynb | 2026-07-06 14:37 | 30 | Intermediate attempt to recover validation coverage | Preserve as experiment; superseded by coverage-tuning notebook |
| notebooks/kaggle_email_llm_number_extraction_safety_zero_unsafe_backup.ipynb | 2026-07-06 12:57 | 29 | Earlier safety baseline | Preserve as historical baseline |
| notebooks/kaggle_email_llm_number_extraction.ipynb | 2026-07-06 12:01 | 29 | Same content as safety backup | Duplicate; do not maintain separately |
| notebooks/kaggle_email_llm_classification.ipynb | 2026-06-30 16:52 | 58 | Classification-only Qwen experiment and TF-IDF abstention pipeline | Reuse evaluation ideas only |
| reports/EDA Rapport v3.ipynb | 2026-06-30 10:36 | 10 | Markdown EDA and solution sketch | Documentation-only |
| reports/EDA Rapport v2..ipynb | 2026-06-30 10:26 | 10 | Earlier Markdown EDA | Documentation-only |

All main notebook cells are unexecuted. The EDA notebooks contain Markdown only despite declaring a Scala kernel.

### Coverage-tuning notebook cell map

The following cell numbers are the concrete source locations for the latest notebook logic:

| Cell | Capability | Important symbols |
|---:|---|---|
| 5 | Experiment configuration | pipeline mode, label mappings, thresholds, Qwen model names, semantic SLM and oracle switches |
| 8 | Dataset discovery and loading | find_csv, load_email_csv, normalize_digits_cell |
| 10 | Cleaning and thread selection | normalize_unicode, split_thread_segments, choose_cleaned_segments, clean_thread_body, clean_email_row |
| 12 | Sectioning and candidate extraction | split_latest_message_sections, canonical_phone, candidate_digit_groups, scoring, provenance, extract_number_candidates |
| 16 | Prompts and structured output | payload classes, prompt builders, JSON parsing, candidate field filling, two-stage prediction |
| 18 | Local Qwen inference | model_kwargs_for, load_llm, generate_from_user_prompt, generation score diagnostics |
| 20 | Batch model run | model iteration and prediction-frame construction |
| 23 | Evaluation and deterministic validation | reference normalization, business-rule diagnostics, validator, metrics and CSV reports |
| 25 | Semantic SLM and oracle | semantic prompts, blocker taxonomy, model review, guarded decision combination, oracle comparison |
| 28 | Generic validator prompt scaffold | SEMANTIC_VALIDATOR_PROMPT_TEMPLATE |

The core loader, cleaner, candidate, prompt, Qwen and inference cells are byte-identical between the latest notebook and its immediate lineage. The meaningful changes are concentrated in configuration, validation, semantic review and reporting.

### Classification notebook

notebooks/kaggle_email_llm_classification.ipynb contains two distinct experiments:

1. A Qwen classification-only path with prompt examples, output parsing, optional rule guardrails and label log-probability diagnostics.
2. A production-style classical ML path using word and character TF-IDF, calibrated LinearSVC, confidence and margin abstention, repeated splits, source-aware evaluation and template-level grouping.

Useful cell clues are:

- Cell 31: preprocess_email_text.
- Cell 34: make_production_text_features and make_production_classifier_pipeline.
- Cells 38–46: probability summaries, abstention and repeated/source-aware evaluation.
- Cell 48: make_subject_template_key.
- Cell 52: classify_email and its human-review fallback.

Cell 21 is syntactically invalid because the fallback concatenation of the system and user prompts contains a broken multiline string. Later Qwen-loading code from the coverage-tuning notebook supersedes it.

## Python scripts and packaged logic

| Artifact | Modified | Purpose | Production treatment |
|---|---:|---|---|
| scripts/semantic_clean_csv.py | 2026-07-14 | Standalone deterministic cleaner; regenerates clean subject/body/text | Reuse high-confidence metadata cleanup; preserve raw content |
| scripts/explore_semantic_email_rules.py | 2026-07-14 | Offline rule and cleaning exploration on reviewed data | Evaluation-only |
| scripts/clean_emails.py | 2026-07-12 | Older cleaner plus deterministic code/phone extraction | Adapt selectively; phone assumptions are dataset-specific |
| scripts/label_clean_new_data.py | 2026-07-12 | Rule-labels and deduplicates the large CSVs | Dataset preparation only; not production semantics |
| scripts/build_manual_label_audit.py | 2026-07-12 | Builds the 80-row manual label audit | Evaluation-only |
| scripts/evaluate_ml_leakage_safe.py | 2026-06-30 | TF-IDF training, group split and held-out reporting | Reuse split/report concepts in evaluation |
| scripts/generate_augmented_emails.py | 2026-06-30 | Synthetic four-class examples | Fixture inspiration; output schema is stale |
| scripts/generate_challenging_augmented_emails.py | 2026-06-30 | Harder synthetic examples with formatting noise | Fixture inspiration; output schema is stale |
| scripts/generate_irrelevant_augmented_emails.py | 2026-06-30 | Adversarial irrelevant examples containing identifiers | Useful evaluation fixtures |
| scripts/analyze_text_lengths.py | 2026-06-24 | Length summaries and plots | Descriptive evaluation only |

The following copies are byte-identical:

- scripts/clean_emails.py
- labeled data/clean_emails.py
- labeled_data/labeled data/clean_emails.py

The following copies are also byte-identical:

- scripts/label_clean_new_data.py
- labeled data/label_clean_new_data.py
- labeled_data/labeled data/label_clean_new_data.py

The packaged cleaner at deliverables/semantic_email_cleaner_package/semantic_clean_csv.py is byte-identical to scripts/semantic_clean_csv.py.

## Label and action mappings

The extraction notebooks retain legacy labels for CSV compatibility:

| Legacy label | Canonical action |
|---|---|
| vpn | vpn_access |
| otp | otp_number_change |
| locked | account_unblock |
| reset | password_reset |
| irrelevant | irrelevant analysis outcome |

The existing application foundation reuses this mapping in src/snoc_agent/domain/enums.py as LEGACY_ACTION_MAPPING. It extends the internal domain with canonical unknown, ambiguous and irrelevant outcomes instead of carrying the legacy labels through the workflow.

Important semantic detail: otp means changing the phone or contact value that receives OTP/SMS/token messages. It does not mean that the sender provides a one-time password.

The reviewed 1,000-row dataset also has five rows labeled multiple. Notebook evaluation excludes them. The production analyzer must instead return an operation list and represent multiple operations directly.

## Existing prompts

No standalone prompt file existed before the production application. All prompts are embedded in notebooks.

### Analyzer prompts

Coverage-tuning cell 16 contains the newest prompt material:

- SYSTEM_PROMPT
- CLASSIFICATION_INSTRUCTION
- DIRECT_EXTRACTION_INSTRUCTION
- STAGE2_FIELD_EXTRACTOR_INSTRUCTION
- CLASSIFICATION_EXAMPLES
- DIRECT_EXTRACTION_EXAMPLES
- SYNONYM_TO_LABEL

The strongest reusable material is the business distinction expressed in the definitions and contrastive examples:

- An access creation or provisioning request containing a contact/OTP phone is vpn_access, not otp_number_change.
- otp_number_change requires an actual change, update, replacement or correction of the OTP/SMS/token destination phone.
- password_reset requires password, PIN or credential-reset semantics.
- account_unblock requires locked, blocked, inactive or unblock semantics.
- Keyword frequency alone is not the requested action.

The scalar notebook prompt and schema are intentionally not reused verbatim. They must be adapted to:

- zero or more proposed operations;
- correction, reply and new-request classification;
- per-field provenance;
- missing fields and contradictions;
- ambiguity and unknown outcomes;
- an explicit statement that models propose operations and never invoke APIs.

### Verifier prompts

Coverage-tuning cell 25 contains:

- build_semantic_support_prompt;
- build_vpn_semantic_prompt;
- build_otp_semantic_prompt;
- build_locked_semantic_prompt;
- build_reset_semantic_prompt;
- build_irrelevant_semantic_prompt;
- semantic_json_instruction;
- semantic_row_context.

The verifier asks whether the proposed action, PDV and required phone are supported and whether a contradiction exists. This independent-support pattern is reused conceptually. The new verifier must operate per proposed operation, include field provenance, and avoid access to expected labels.

Cell 28 contains the older generic semantic-validator scaffold. It is less specific than the action-specific cell 25 prompts and remains notebook-only.

## Cleaning and reply segmentation

### Reused

The safe reusable layer from scripts/semantic_clean_csv.py includes:

- Unicode NFKC and HTML-entity normalization;
- whitespace normalization;
- common subject reply-prefix handling;
- removal of high-confidence anonymization placeholders;
- removal of mailto/tel metadata, Outlook shortlinks and external-email banners;
- removal of common mobile-client footer residue;
- conservative repair of known legacy text corruption.

The packaged report states that this cleaner is idempotent on the reviewed 1,000-row dataset and preserves every non-clean column.

### Adapted

Coverage-tuning cell 12 function split_latest_message_sections provides useful French and English separator candidates and returns:

- latest_message_text;
- quoted_thread_text;
- signature_text.

This is adapted as a presentation and candidate-provenance aid only. RFC Message-ID, In-Reply-To and References headers are the primary conversation signals in the production service.

### Intentionally not authoritative

The notebook functions segment_score, request_categories, choose_cleaned_segments and clean_thread_body may:

- discard low-signal current text;
- replace a generic current reply with a quoted request;
- keep a quoted segment because it appears to introduce another deterministic intent category;
- merge up to two selected segments and lose original offsets.

That behavior is useful for historical classification experiments but unsafe for stateful reply, correction and reused-thread handling. The production system must store the original message and expose explicitly labeled sections to the model rather than silently deleting history.

## Numeric candidates and field attribution

Coverage-tuning cell 12 is the best existing candidate implementation. It includes:

- extraction of grouped 8, 9, 10 and 12-digit spans;
- subject, latest-message, quoted-thread and signature provenance;
- local context windows and candidate offsets;
- separate PDV and phone candidate types;
- old-phone and new-phone context;
- penalties for quote and signature provenance;
- detection of a pseudo-phone produced by prefixing an eight-digit PDV with 7.

### Reused

- Candidate discovery independent of the final action.
- Candidate provenance and context.
- PDV-derived pseudo-phone detection.
- The invariant that a PDV code has exactly eight digits.

### Adapted

- Candidate records become typed data passed to the analyzer and verifier.
- The analyzer attributes candidates to operations.
- Phone validation uses the configurable pattern in Settings instead of notebook-specific canonicalization.
- Section and score values remain evidence, not permission to execute.

The production foundation implements canonical mappings and configurable hard formats in:

- src/snoc_agent/domain/enums.py;
- src/snoc_agent/domain/value_objects.py;
- src/snoc_agent/config.py.

### Incompatible behavior not reused

scripts/clean_emails.py treats any security-distorted 9, 10 or 12-digit value as a canonical 7XXXXXXXX phone. The notebook implementation is stricter but can still convert an eight-digit value into 7 plus that value in a strong phone context. Neither assumption is a safe universal production invariant.

The notebook best_pdv_candidate, best_phone_candidate and fill_fields_from_candidates functions choose one scalar value using hand-tuned scores. They are retained as evaluation baselines only. Models perform semantic attribution, while deterministic code checks format, provenance and required fields.

## Existing structured output and parsing

Coverage-tuning cell 16 defines three Pydantic classes:

- ExtractionPayload;
- ClassificationPayload;
- FieldPayload.

They contain plain strings with defaults, allow only one action and one PDV/phone pair, and do not encode provenance, missing fields, multi-operation decomposition, corrections or state transitions.

The notebook parser:

- scans generated text for decodable dictionaries;
- returns the last dictionary found;
- normalizes many free-text label synonyms;
- coerces fields into a permissive schema;
- may accept non-schema text before or after the object.

The production application adapts only the idea of typed structured output. It uses strict Pydantic v2 schemas and explicit invalid-output handling. Parsing failure, unknown actions and contradictions route to escalation rather than permissive coercion.

## Qwen model loading

Coverage-tuning cell 18 provides the latest working local Transformers path:

- AutoTokenizer and AutoModelForCausalLM;
- tokenizer chat templates;
- deterministic generation;
- optional bitsandbytes NF4 quantization;
- GPU memory budgeting;
- a PyTorch compatibility shim;
- model cleanup;
- generated-token transition-score diagnostics.

The configured analyzer is Qwen/Qwen2.5-1.5B-Instruct. The validation reviewer attempts Qwen/Qwen2.5-3B-Instruct and falls back to Qwen2.5 1.5B.

No existing implementation supports Qwen3 or a configurable thinking switch. The production configuration adds analyzer and verifier model names plus qwen3_enable_thinking. Model-specific request parameters belong behind the model backend.

generation_confidence_from_scores computes an exponentiated mean log probability across the generated sequence. This is not a calibrated probability that an operation is correct and is retained only as an audit diagnostic.

## Deterministic validation taxonomy

Coverage-tuning cell 23 contains the latest deterministic_payload_validator. Its issue strings fall into these groups:

### Schema and required-field issues

- unknown_label;
- missing_required_pdv;
- missing_required_phone_for_otp;
- missing_required_phone_for_vpn;
- missing_required_field;
- irrelevant_with_extracted_numbers;
- unexpected_phone_for_action.

### Candidate and provenance issues

- selected_pdv_not_in_candidates;
- selected_phone_not_in_candidates;
- selected_pdv_only_in_quoted_thread;
- selected_phone_only_in_quoted_thread;
- candidate_only_in_quoted_thread;
- selected_phone_appears_pdv_derived.

### Ambiguity and confidence issues

- ambiguous_action_request;
- ambiguous_operational_request;
- ambiguous_field_candidates;
- ambiguous_pdv_candidates;
- ambiguous_phone_candidates;
- low_confidence_selected_pdv;
- low_confidence_selected_phone;
- low_confidence_field_candidate.

### Semantic rule issues

- model_rule_semantic_disagreement;
- strong_reset_evidence_misclassified;
- strong_vpn_provisioning_misclassified;
- possible_reset_misclassified_as_otp;
- possible_vpn_access_misclassified;
- otp_without_phone;
- operational_label_without_pdv.

### Dataset-quality issues

audit_ground_truth_row emits:

- missing_reference_pdv_for_phone_required_action;
- missing_reference_phone_for_phone_required_action;
- missing_reference_pdv_for_operational_action;
- irrelevant_with_reference_payload.

The production application reuses the first two categories only where they represent deterministic invariants: schema validity, configured field formats, required fields and unsafe provenance. Keyword-based semantic interpretation moves to the analyzer and verifier.

The notebook taxonomy is not a stable production enum. Several issue and blocker sets overlap, one blocker literal is duplicated, and combine_deterministic_and_semantic_slm repeats two local assignments. These are harmless in the notebook but should not be copied.

## Semantic SLM validation and oracle

Coverage-tuning cell 25 is the only implementation of semantic SLM review. Its sound reusable pattern is:

1. Keep deterministic hard failures non-overridable.
2. Ask an independent model whether action, PDV and phone are supported.
3. Require explicit YES for all applicable support checks.
4. Require contradiction_present to be NO.
5. Permit a decision change only when every remaining blocker is explicitly tunable.

The cell separates non-overridable, safety-critical and tunable blockers and reports guarded, strict and diagnostic-aggressive modes.

### Oracle definition

is_oracle_false_escalation_candidate selects a row only when:

- deterministic validation did not pass;
- gold label_match is true;
- gold numbers_exact_match is true;
- no ground-truth issue is recorded.

This is useful for measuring the upper bound of rescuing false escalations. It is not a production routing policy.

### Evaluation leakage that must stay isolated

- VALIDATION_SLM_EVAL_ORACLE_MODE is enabled in the notebook.
- Oracle rows are selected with expected labels and numbers.
- UNSAFE_REGRESSION_ROW_IDS is a hardcoded list of dataset row IDs.
- BLOCK_SEMANTIC_SLM_RELAXATION_FOR_REGRESSION_ROWS uses those IDs.
- The same notebook cell runs both production-candidate and oracle-candidate reviews.

The production workflow must never import oracle row selection or hardcoded evaluation IDs. Oracle logic belongs only in the evaluation package.

## Metrics

Coverage-tuning cell 23 defines the requested metrics after normalizing reference and prediction values:

    label_match = predicted_label == reference_label
    pdv_exact_match = predicted_pdv == reference_pdv
    phone_exact_match = predicted_phone == reference_phone
    numbers_exact_match = pdv_exact_match and phone_exact_match
    joint_label_and_numbers_exact_match = label_match and numbers_exact_match

    would_auto_execute = validation_status == "pass"
    unsafe_auto_execute = would_auto_execute and not (
        label_match and numbers_exact_match
    )
    validation_pass_but_wrong = unsafe_auto_execute
    validation_fail_but_correct = (
        validation_status != "pass"
        and label_match
        and numbers_exact_match
    )
    auto_execute_coverage = mean(would_auto_execute)

It additionally reports:

- unsafe auto-execution count and rate among executed rows;
- safe correct auto-execution rate;
- false escalation count and rate;
- candidate reference coverage;
- candidate selection error;
- per-label precision, recall and F1;
- confusion matrices;
- per-business-action summaries;
- strict metrics with known ground-truth issues excluded.

These scalar formulas are reusable for legacy dataset comparisons. Multi-operation evaluation must additionally compare normalized operation sets and field attribution per operation.

scripts/evaluate_ml_leakage_safe.py provides reusable evaluation helpers:

- synthetic_group_key;
- choose_group_fold using StratifiedGroupKFold;
- metric_dict;
- per-label and confusion reports;
- source-aware held-out evaluation.

Its label list and input paths are stale and require adaptation.

## Dataset inventory

### Current large labeled data

All four files are duplicated byte-for-byte across data/new data, labeled data, and labeled_data/labeled data.

| File | Rows | Label distribution |
|---|---:|---|
| BIGDATA_merged.csv | 2,000 | irrelevant 1,272; reset 365; vpn 150; locked 126; otp 87 |
| SMOLDATA_merged.csv | 12,496 | locked 6,273; irrelevant 2,136; otp 2,250; vpn 1,310; reset 527 |
| merged_new_data.csv | 14,496 | locked 6,399; irrelevant 3,408; otp 2,337; vpn 1,460; reset 892 |
| manual_label_audit.csv | 80 | all 80 rows marked agreement |

The common schema is:

- objet;
- corps;
- label;
- clean_objet;
- clean_corps;
- clean_email_text;
- code_pos_pdv_number;
- code_otp_number.

The large merged data contains many missing required reference fields, semicolon-separated multi-values, and irrelevant rows that legitimately contain identifiers. Dataset loading must preserve these facts and report quality issues rather than silently treating every row as an executable complete request.

### Reviewed evaluation data

| File | Rows | Notes |
|---|---:|---|
| labeled_data/labeled data/SMOLDATA_last_1000_reviewed.csv | 1,000 | Current reviewed reference set |
| labeled_data/labeled data/SMOLDATA_last_1000_reviewed_backup_before_rule_exploration.csv | 1,000 | Exact duplicate backup |
| reports/SMOLDATA_last_1000_semantically_cleaned.csv | 1,000 | Derived clean-text output |
| deliverables/semantic_email_cleaner_package/SMOLDATA_last_1000_semantically_cleaned.csv | 1,000 | Exact duplicate of report output |

The reviewed label distribution is:

| Label | Rows |
|---|---:|
| locked | 411 |
| otp | 224 |
| irrelevant | 204 |
| vpn | 110 |
| reset | 46 |
| multiple | 5 |

scripts/explore_semantic_email_rules.py scores 995 rows and deliberately excludes the five multiple rows.

### Older and augmented data

| File | Rows | Role |
|---|---:|---|
| data/old data/merged_data.csv | 265 | Original raw four-class set |
| data/old data/cleaned_merged_data.csv | 265 | Original set with clean and extraction columns |
| data/augmented_data/augmented_emails_cleaned_aligned.csv | 230 | Regular synthetic examples |
| data/augmented_data/challenging_augmented_emails_cleaned_aligned.csv | 240 | Harder formatting and thread examples |
| data/augmented_data/irrelevant_emails_cleaned.csv | 80 | Adversarial irrelevant examples containing numbers |
| data/special_cases.csv | 5 | Four vpn and one locked special cases |

The older 265-row set has no irrelevant examples. The augmented irrelevant set is useful because irrelevant messages may still contain PDV, phone or transaction-like numbers.

### Manual review traces

| Artifact | Records | Schema or role |
|---|---:|---|
| .review/otp_align_lines_2_334.jsonl | 106 | old/new numeric span, normalized OTP, role and note |
| .review/otp_align_lines_335_667.jsonl | 120 | same |
| .review/otp_align_lines_668_1001.jsonl | 105 | same |
| .review/batch_*.tsv | 256 | final label, POS, OTP and reason |
| .review/crosscheck_*.tsv | 15 | recommendation and corrected outputs |

These are valuable audit provenance but are not runtime fixtures without conversion to explicit test cases.

### Archives and duplicate payloads

- labeled data.zip is an older archive whose contained file sizes differ from the extracted current copies.
- labeled_data.zip contains the later labeled-data bundle.
- deliverables/semantic_email_cleaner_package.zip contains the verified cleaner, cleaned CSV and report.

The application should use explicit configured dataset paths and should not rely on archive discovery.

## Reports and evaluation artifacts

| Artifact | Purpose and findings |
|---|---|
| reports/semantic_rule_exploration_summary.json | Machine-readable cleaning, rule-label and extraction metrics on 995 scored rows |
| reports/semantic_rule_exploration_predictions.csv | 1,000-row audit with baseline/rule predictions and match flags |
| reports/semantic_rule_exploration.md | Human-readable summary; five multiple rows excluded |
| reports/ml_leakage_safe_evaluation.md | Group-stratified and challenging-heldout classical ML report |
| reports/email_classifier_pipeline.joblib | sklearn 1.7.2 word/char TF-IDF plus calibrated LinearSVC artifact |
| reports/number_extraction_audit_after_160.csv | 223 rows: 217 ok and 6 needs_review |
| reports/merged_table_clean2_after160_pos_cleanup.csv | 23 cleanup actions |
| reports/text_length_analysis.md and related CSV/PNG files | Descriptive length analysis |
| reports/EDA Rapport v2..ipynb and v3.ipynb | Business and EDA narrative |

The semantic exploration report records:

- 995 scored rows and five excluded multiple rows;
- 100 percent exact clean-subject agreement;
- 98.19 percent exact clean-body agreement;
- 15.26 percent token reduction with reported intent retention;
- deterministic rule-label accuracy of 93.07 percent;
- raw POS exact-set accuracy of 92.86 percent after explored rules;
- raw OTP exact-set accuracy of 97.19 percent after explored rules.

These are deterministic rule results, not LLM results.

The joblib artifact contains a FeatureUnion with word and character TF-IDF plus CalibratedClassifierCV over LinearSVC. Its preprocessing is external to the serialized pipeline, and it is tied to sklearn 1.7.2. It is suitable only as an optional historical comparator unless it is retrained and versioned with its preprocessing.

## Missing and stale paths

Several notebook and script defaults do not exist under the referenced names:

- merged_table_cleaned_emails.csv;
- irrelevant_emails.csv;
- merged_table_clean2.csv;
- challenging_augmented_emails_cleaned.csv;
- augmented_emails_cleaned.csv;
- merged_table_clean_badrou.csv.

Likely current counterparts have been moved or renamed under data/old data and data/augmented_data, often with an _aligned suffix.

The generation scripts also write obsolete schemas and paths such as:

- data/augmented_emails_ground_truth.csv;
- data/challenging_augmented_emails_ground_truth.csv;
- code_pos_number instead of code_pos_pdv_number.

No existing notebook runs as-is against the repository without path overrides and, in some cases, schema adaptation.

## Reuse decision matrix

| Existing capability | Reused | Adapted | Notebook/evaluation only |
|---|---|---|---|
| Legacy-to-canonical action mapping | Yes, in domain enums | Extended with ambiguous and unknown outcomes | No |
| Unicode and high-confidence mail-artifact cleanup | Yes | Applied without deleting raw content | Aggressive segment selection remains offline |
| Reply/quote/signature regexes | As candidate separators | Combined with MIME and RFC-header correlation | Not authoritative |
| Numeric span discovery | Yes | Typed candidates with configurable phone format and provenance | Score-based final field filling |
| PDV-derived pseudo-phone detection | Yes | Used as a hard safety signal | No |
| Business definitions and contrastive prompt examples | Conceptually | Multi-operation analyzer and per-operation verifier prompts | Scalar notebook schema |
| Pydantic structured output idea | Yes | Strict Pydantic v2 multi-operation schemas | Permissive scalar notebook payloads |
| Qwen local loading pattern | Conceptually | Interchangeable backend and Qwen3 thinking configuration | Notebook globals and Kaggle install cells |
| Required-field and format validation | Yes | Canonical names and configured regexes | Keyword-based semantic “hard rules” |
| Candidate provenance checks | Yes | Current/history policy in decision engine | Hand-tuned candidate thresholds as authorization |
| Semantic SLM independent support check | Yes, as a design pattern | Independent per-operation verifier and agreement policy | Oracle-selected reviewer routing |
| Exact-match and safety metrics | Yes | Extended for operation sets and attribution | Notebook display/export plumbing |
| Oracle false-escalation analysis | No production import | Isolated evaluation module only | Gold-selected row routing |
| Classical TF-IDF pipeline | Optional baseline | Must be retrained/versioned to use | Existing joblib is historical |

## Reproducibility and safety caveats

1. Main notebooks have no saved execution state or outputs.
2. The repository contains no LLM-generated joint extraction, semantic SLM, validation profile or unsafe-row CSVs named by the notebooks.
3. Notebook claims about zero unsafe auto-execution cannot be verified from this snapshot.
4. Default dataset filenames are stale.
5. The classification notebook contains a syntax error in its Qwen inference cell.
6. Scalar exact-match code does not support semicolon-separated values or multiple operations.
7. Phone normalization contains dataset-specific Algerian and security-distortion assumptions.
8. Candidate scores and validation thresholds were tuned on particular notebook rows and are not calibrated probabilities.
9. generation_confidence is a sequence-generation statistic, not action confidence.
10. Hardcoded unsafe regression row IDs and oracle selection use evaluation truth.
11. Deterministic notebook validation mixes hard invariants with semantic keyword interpretation.
12. The reviewed dataset contains ground-truth quality issues; strict metrics deliberately exclude some rows.
13. The classical ML report uses generated/template-heavy data and stale filenames.
14. Duplicate scripts, datasets and notebooks make path selection ambiguous unless configuration is explicit.

## Final production boundary

The notebooks remain valuable experimental and evaluation artifacts. The production service should extract only small, typed, testable units:

- canonical action mappings;
- conservative cleanup;
- reply-section candidates;
- numeric candidate discovery and provenance;
- strict structured-output validation;
- configurable required-field and format checks;
- independent analyzer/verifier agreement;
- exact-match, safety and coverage metrics;
- isolated oracle analysis.

State, authorization, RFC correlation, clarification handling, idempotency and API execution are new application responsibilities. No notebook function is allowed to call a business API, and no model output is executable until the deterministic decision engine approves it.
