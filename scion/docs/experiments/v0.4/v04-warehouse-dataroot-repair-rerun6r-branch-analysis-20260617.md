# Warehouse Data-Root Repair Rerun Branch Analysis

Date: 2026-06-17
Role: Scion v0.4 warehouse postrun analysis subagent
Run root: `/home/clawd/research/scion-experiments/v04-warehouse-dataroot-repair-rerun6r-ad469f0-20260617T033450Z/rep01/on_compact/campaign`
Run commit: `ad469f0`
Model: `gpt-5.5`

## Required Reading

- `scion/design/scion-architecture-v3.md`
- `scion/TASK.md`
- `scion/docs/planning/v0.4/v0.4-evidence-repair-and-validation-plan-20260611.md`
- `scion/reports/v04-core-framework-code-review-20260611.md`
- `scion/reports/v04-core-framework-review-20260611.md`
- `scion/design/v0.5-evidence-uplift-roadmap.md`

V3 alignment: LLM outputs remain tainted proposal material. This report uses DB
rows, protocol metrics, prompt manifests, and agentic traces as audit evidence;
it does not propose adding LLM text, branch lessons, raw prompt ratios, or
problem diagnostics to `DecisionFeatures`.

## 1. Data-Root Repair Acceptance

The data-root repair is field-accepted by this run.

Evidence:

- Wrapper and campaign completed cleanly:
  - `exit.txt`: `WRAPPER_EXIT_STATUS:0`, `CAMPAIGN_EXIT_STATUS:complete`,
    `RUN_VALIDITY_STATUS:valid`, `COMPLETED_REQUESTED_ROUNDS:True`.
  - `status.json.run_validity.status=valid`, `effective_rounds_completed=6`,
    `protocol_metric_results=6`, `partial_campaign_evidence=false`.
- The run explicitly activated the declared runtime root:
  - `run.log`: `INFO: activated problem data root SCION_WAREHOUSE_DATA_ROOT=/home/clawd/research/scion-data`.
- Formal protocol rows reached canary and screening instead of failing canary
  path resolution:
  - `status.json.protocol_metric_stage_counts = {"screening": 6, "validation": 0, "frozen": 0}`.
  - `status.json.verification_consumed_candidates=6`, `verification_failure_consumed_candidates=0`.
  - `campaign_summary.json.runtime_budget_diagnostics=[]`.
- Every metrics file inspected has strict case resolution through the intended
  root:
  - `case_path_resolution.status_counts` is only
    `champion:resolved_safe_data_root` and `candidate:resolved_safe_data_root`.
  - `matched_root` in the metrics rows is `/home/clawd/research/scion-data`.
- No `absolute_outside_roots`, `CANARY_CONFIG_ERROR`, or ordinary canary veto is
  present in the run summary or DB rows.

This run therefore validates the copied-split safe-root repair as an
infrastructure fix. It does not validate warehouse research efficacy.

## 2. Campaign-Level Shape

The run consumed `10` proposal attempts:

- `6` completed formal screening rows.
- `4` proposal quality blocks:
  - `1` hypothesis block for missing validation-transfer risk.
  - `3` code/patch blocks for missing activation/effect diagnostic code.
- `0` validation rows.
- `0` frozen rows.
- `0` promotions.
- Champion stayed at version `1`.

Postrun aggregate screening evidence:

| aggregate | value |
|---|---:|
| case W/L/T | `10/4/50` |
| case win rate | `0.15625` |
| pair W/L/T | `52/29/47` |
| pair win rate | `0.40625` |
| decisions | `1 abandon`, `2 expand_screening`, `3 continue_explore` |

The aggregate is tie-heavy and pair-positive, but case-level win rate remains
far below the normal production screening threshold `0.55`.

## 3. Branch Trajectories

### Branch `6045ddb5`

Final state:

- `branches.state=abandoned`
- `branch_code_status=discarded`
- `last_screening_feedback_tier=quality_regression`
- `last_telemetry_outcome=pair_level_positive_signal`
- `failure_codes`:
  - `AGENT_QUALITY_BLOCKED:WAREHOUSE_VALIDATION_TRANSFER_QUALITY_MISSING`
  - `AGENT_QUALITY_BLOCKED:WAREHOUSE_VALIDATION_TRANSFER_PATCH_QUALITY_MISSING`
  - `SCREENING_FAIL_WIN_RATE`
  - `BRANCH_LIFECYCLE_ARCHIVE_LINEAGE`
  - `SCREENING_SOFT_ABANDON_LOSS_WITHOUT_WIN`

Path:

| step | evidence | hypothesis / target | result |
|---|---|---|---|
| 1 | `agentic_session c329d3bf`, `run.log` | create `operators/subcategory_group_repack.py`; mechanism `subcategory_group_repack` | blocked at hypothesis: missing `validation_transfer_risk` |
| 2 | hypothesis `fd00cce9`, session `3710c970` then code session `a603b734` | modify `operators/merge_vehicles.py`; `same_subcategory_merge_guard` | code blocked: missing `activation_effect_diagnostic_code` |
| 3 | hypothesis `80085fbe`, session `0741b3bf` then code session `0a218645` | modify `operators/move_order.py`; `split_bridge_relocation`, `validation_transfer_diagnostics`, `lexicographic_screening_guard` | passed verification/canary and screened |
| 4 | DB experiment row `2026-06-17T03:41:31` | same `move_order.py` candidate | abandoned |

Formal screening:

| metric | value |
|---|---:|
| stage | `screening` |
| case W/L/T | `0/2/4` |
| pair W/L/T | `2/5/5` |
| median delta | `0.0` |
| CI | `[-1925.0, 375.0]` |
| decision | `abandon` |
| reason | `SCREENING_FAIL_WIN_RATE`, `BRANCH_LIFECYCLE_ARCHIVE_LINEAGE`, `SCREENING_SOFT_ABANDON_LOSS_WITHOUT_WIN` |

Case-level losses were concentrated on `instance_prod_scr_ms02.json` and
`instance_prod_scr_m03.json`; the only case-level positive was
`instance_prod_scr_s03.json`. This is not a borderline validation candidate.

### Branch `ed329b23`

Final state:

- `branches.state=explore`
- `branch_code_status=active_no_effect`
- `last_screening_feedback_tier=no_effect`
- `last_telemetry_outcome=no_objective_effect`
- `best_quality_checkpoint_id=0dcd204b-2493-4e13-8efb-d37d5e7f1b41`
- `last_valid_checkpoint_id=780cfb37-255b-4dee-8c7d-0a94060a4cf8`

Path:

| step | evidence | hypothesis / target | result |
|---|---|---|---|
| 1 | hypothesis `1e7d751e`, session `46dc369f` then `649ef663` | modify `operators/merge_vehicles.py`; `bounded_compatible_merge_selector`, `lexicographic_merge_guard` | code blocked: missing `activation_effect_diagnostic_code` |
| 2 | hypothesis `577a8e6a`, sessions `997414eb` and `39ef6b7f` | create `operators/fill_and_downsize.py`; `fill_and_downsize`, `validation_transfer_diagnostics` | screened, then expanded |
| 3 | same hypothesis `577a8e6a` | expanded screening on the same candidate | continued same branch; validation not queued |
| 4 | hypothesis `295479ae`, sessions `53895bd0` and `517fc897` | modify `operators/fill_and_downsize.py`; stricter full-source-emptying and cost guard | all-tie screening; continued due runtime fresh-champion path |

Formal screening rows:

| row | hypothesis | case W/L/T | pair W/L/T | median | CI | decision | reason |
|---|---|---:|---:|---:|---|---|---|
| 1 | `577a8e6a` | `2/0/8` | `10/4/6` | `575.0` | `[-325.0, 1200.0]` | `expand_screening` | `SCREENING_EXPAND_LOW_SNR_TRAJECTORY_DIVERGENT` |
| 2 | `577a8e6a` | `3/1/12` | `15/8/9` | `575.0` | `[-50.0, 900.0]` | `continue_explore` | `SCREENING_LOW_SNR_EXPAND_EXHAUSTED_CONTINUE`, `SCREENING_MARGINAL_SIGNAL_CONTINUE` |
| 3 | `295479ae` | `0/0/6` | `0/0/12` | `0.0` | `[0.0, 0.0]` | `continue_explore` | `RUNTIME_TIE_FRESH_CHAMPION_REQUIRED` |

Interpretation:

- The first `fill_and_downsize` candidate had real pair/case signal and was
  correctly expanded.
- Expanded evidence stayed positive but did not satisfy the production
  diagnostic-validation policy.
- The follow-up refinement over-tightened the trigger and collapsed to all ties,
  leaving no objective effect. The runtime fresh-champion path then became the
  explicit reason code, but this was a secondary symptom after objective effect
  disappeared.

### Branch `792e6d6e`

Final state:

- `branches.state=explore`
- `branch_code_status=active_marginal`
- `screening_expand_count=1`
- `last_screening_feedback_tier=marginal`
- `last_telemetry_outcome=case_level_positive_signal`
- `best_quality_checkpoint_id=650d6b4b-0ac7-4b95-ac61-c637ca1775b5`
- `last_valid_checkpoint_id=650d6b4b-0ac7-4b95-ac61-c637ca1775b5`

Path:

| step | evidence | hypothesis / target | result |
|---|---|---|---|
| 1 | hypothesis `2e38e708`, sessions `5048ce1c` and `b44b1fc6` | create `operators/subcategory_upgrade_pack.py`; `subcategory_upgrade_pack`, `validation_transfer_diagnostics` | code blocked: missing `activation_effect_diagnostic_code` |
| 2 | hypothesis `474919b0`, sessions `d29d02bb` and `ec18d39e` | create `operators/locked_anchor_repack.py`; `locked_anchor_repack`, `validation_transfer_diagnostics` | screened, then expanded |
| 3 | same hypothesis `474919b0` | expanded screening on the same candidate | continued same branch; validation not queued |

Formal screening rows:

| row | hypothesis | case W/L/T | pair W/L/T | median | CI | decision | reason |
|---|---|---:|---:|---:|---|---|---|
| 1 | `474919b0` | `2/0/8` | `10/4/6` | `575.0` | `[-325.0, 1200.0]` | `expand_screening` | `SCREENING_EXPAND_LOW_SNR_TRAJECTORY_DIVERGENT` |
| 2 | `474919b0` | `3/1/12` | `15/8/9` | `575.0` | `[-50.0, 900.0]` | `continue_explore` | `SCREENING_LOW_SNR_EXPAND_EXHAUSTED_CONTINUE`, `SCREENING_MARGINAL_SIGNAL_CONTINUE` |

The expanded branch had clear positive cases:

- wins: `instance_prod_scr_micro03`, `scr_s02`, `scr_s03`, `scr_ms01`, `scr_m01`
- loss: `instance_prod_scr_ms02`

However the expanded pair signal was not strong enough under the conservative
diagnostic validation policy.

## 4. Why Marginal Signal Did Not Reach Validation

Direct cause: the two expanded positive candidates fail the
`pair_non_tie_win_rate_min` requirement.

Warehouse production protocol declares:

- `screening.win_rate_min=0.55`
- `expanded_borderline_advance.enabled=true`
- `allow_pair_level_signal=true`
- `pair_win_rate_min=0.46`
- `min_pair_total=12`
- `min_pair_wins=6`
- `min_pair_win_loss_margin=4`
- `pair_non_tie_win_rate_min=0.68`
- `max_pair_loss_rate=0.25`

For both expanded positive rows (`ed329b23/577a8e6a` and
`792e6d6e/474919b0`):

- case W/L/T = `3/1/12`
- pair W/L/T = `15/8/9`
- median delta = `575.0`
- CI low = `-50.0`
- pair win rate = `15/32 = 0.46875`, which passes `0.46`
- pair wins-losses margin = `7`, which passes `4`
- pair loss rate = `8/32 = 0.25`, exactly passes `0.25`
- non-tie pair win rate = `15/(15+8) = 0.65217`, which fails `0.68`

So the no-validation result is not caused by data-root, canary, verification,
proposal quality blocks, or missing formal rows. It is the intended consequence
of the current diagnostic validation gate.

Whether the gate is too conservative is a policy question. The current evidence
is borderline but not obviously strong: the expanded CI still crosses below
zero (`ci_low=-50.0`), the case win rate is only `3/16=0.1875`, and there is a
repeatable loss on `instance_prod_scr_ms02`. Loosening the gate from `0.68` to
about `0.65` would admit this run's expanded signal, but it would also admit a
weaker pair-positive/noisy shape than the previously replayed target
`13/6/9`, whose non-tie pair win rate was `0.684`.

Runtime replay was not the primary blocker:

- `fresh_runtime_replay_protocol_results=0`.
- `fresh_runtime_replay_drain` was skipped/blocked with
  `pressure_no_schedulable_replay_candidate`.
- One all-tie follow-up row did receive `RUNTIME_TIE_FRESH_CHAMPION_REQUIRED`,
  but that row had `0/0/6` cases and `0/0/12` pairs, so it had no objective
  signal to validate anyway.

Validation-transfer quality remains the more important blocker:

- The agents repeatedly had to be blocked for missing transfer/diagnostic
  content (`4` quality blocks).
- Passing patches wrote local `validation_transfer_diagnostics` dictionaries,
  but formal metrics report `candidate_phase_telemetry_summary={}` and
  `candidate_telemetry_guard_summary.mechanism_diagnostics[*].activation_status`
  / `effect_status = not_declared`.
- In other words, the patches include counters, but the problem-owned telemetry
  declaration path does not consume them as structured activation/effect
  diagnostics. The agent therefore gets weak feedback about why a candidate
  helped some screening cases and lost on `scr_ms02`.

## 5. Agent Context And Output Quality

This run does not support the simple explanation that source code or branch
history was hidden by hard truncation:

- Prompt manifests were present for all `30` LLM calls.
- The trajectory manifest loaded `30/30` prompt manifests and `15/15` sessions
  had branch-lesson usage projection.
- `branch_lesson_usage_accounting.usage_present_count=15`,
  `semantic_projection_present_count=15`, `usage_missing_count=0`.
- Prompt manifests show no truncated prompt blocks in inspected sessions.
- `current_champion_research_code` was visible in hypothesis/code prompts
  around `17k` chars.
- Follow-up hypothesis prompts included `current_branch_code` for branch
  `ed329b23`, and code prompts included target/current file content.

But the context is still not producing sufficiently discriminative research:

- The prompt family aggregate is still dominated by generic/tool material:
  - `general`: about `49.6%` token share.
  - `tool_selection`: about `21.0%`.
  - `research_signal`: about `13.7%`.
  - `tool_observation`: about `8.6%`.
  - `governance`: about `3.8%`.
  - `feedback`: about `3.3%`.
- Cross-branch and branch-lesson material was visible, but it did not prevent
  repeated similar vehicle-elimination proposals. Two distinct created
  operators, `fill_and_downsize` and `locked_anchor_repack`, produced identical
  formal screening shapes (`2/0/8` then `3/1/12` cases, `10/4/6` then
  `15/8/9` pairs).
- The agent's successful patches focus on local move guards and lightweight
  dictionaries. They do not create a problem-owned, protocol-visible
  explanation of activation/effect transfer.
- The follow-up refinement on `ed329b23` over-corrected a marginal positive
  candidate into an all-tie no-effect candidate. This is a branch-depth quality
  failure: depth happened, but it did not preserve or sharpen the positive
  mechanism.

Quality gate assessment:

- The quality gates are not over-strong in this run. They blocked real defects
  and still allowed `6` formal protocol rows.
- They are also not strong enough to ensure actionable validation-transfer
  instrumentation. The passing patches satisfy textual/local-code checks, but
  their counters remain `not_declared` to telemetry guard summaries.

## 6. TASK.md Implications And Next Step

TASK.md's warehouse effective-research gate is still open:

- Existing promotion behavior is not disproven by this run, but this specific
  rerun had no validation/frozen/promotion.
- Branch transfer and context were inspected; context visibility is mostly
  fixed.
- The failure is now narrower: branch-level mechanism quality and
  validation-transfer attribution, not generic observability or data-root
  infrastructure.

Recommended next smallest repair or experiment:

1. Add a warehouse problem-owned activation/effect declaration bridge for the
   existing proposal-level diagnostic counters, or tighten the warehouse
   patch-quality hook so accepted patches must expose counters through a
   declared telemetry path. Keep this problem-owned in
   `WarehouseDeliveryAdapter` / warehouse problem configuration, not in generic
   Decision.
2. Add a report-only postrun check that flags `validation_transfer_diagnostics`
   dictionaries whose corresponding metrics still show
   `activation_status=not_declared` and `effect_status=not_declared`. This is an
   acceptance diagnostic, not promotion evidence.
3. Rerun a short warehouse production `6R` field check from the repair commit.

Acceptance criteria:

- Data-root remains valid: run validity `valid`, `6/6` requested rounds,
  `0` canary config/path-root failures.
- At least one screening-positive warehouse candidate has declared
  activation/effect diagnostics consumed in metrics, not merely local dicts in
  code.
- Quality blocks decrease because the agent follows the repair template, not
  because the gate is weakened.
- If a candidate has the same `3/1/12`, `15/8/9`, median `575` shape, the report
  must explicitly say whether it failed only because `pair_non_tie_win_rate`
  remains below `0.68` or because effect diagnostics show poor transfer risk.
- Do not loosen validation/frozen/promotion gates until the problem-owned
  diagnostics can explain which cases/mechanism conditions transfer.

Optional follow-up experiment after the repair:

- Run a no-LLM deterministic replay of the `fill_and_downsize` and
  `locked_anchor_repack` patches on the validation cases in record-only mode,
  with protocol decisions disabled, to see whether the repeated screening
  signal collapses on validation-style instances. This should be analysis
  evidence only and must not mutate champion or Decision state.
