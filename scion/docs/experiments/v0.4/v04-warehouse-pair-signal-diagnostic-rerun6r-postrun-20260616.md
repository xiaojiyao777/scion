# Warehouse Pair-Signal Diagnostic Rerun 6R Postrun - 2026-06-16

Scope:

- Rerun root:
  `/home/clawd/research/scion-experiments/v04-warehouse-pairsignal-diagnostic-rerun6r-20260616T180447Z/rep01/on_compact/campaign`
- Repair report:
  `scion/docs/experiments/v0.4/v04-warehouse-pair-signal-diagnostic-protocol-repair-20260616.md`
- Architecture boundary:
  `scion/design/scion-architecture-v3.md` keeps Decision deterministic. LLM output, branch lessons, prompt text, and cross-branch maps are tainted proposal material; Decision consumes only `DecisionFeatures`. Warehouse semantics remain problem-owned.

## Executive Finding

The repair behaved as designed: the rerun completed six valid screening protocol rows with no infra, contract, verification, or canary blockers, but no candidate satisfied the repaired pair-level diagnostic validation policy. Therefore the final accounting is:

- validation protocol rows: 0
- frozen protocol rows: 0
- promoted experiments: 0
- stop reason: `max_rounds_exhausted`

The remaining failure is not "pair signal is invisible to Decision"; it is that the produced candidates did not meet the new pair-level policy. The only expanded-exhausted candidate became negative-median and pair-loss-heavy after expansion. The four same-branch `move_order.py` candidates on `3e328bae...` also never produced pair-positive evidence.

Main-session acceptance:

- Accept this rerun as valid evidence that the pair-signal diagnostic protocol repair did not over-promote or misroute loss-heavy evidence.
- Reject this rerun for warehouse research quality: it produced no validation, no frozen holdout, no promotion, and no measurable same-branch behavior progress.
- Treat the next fix as a lifecycle/research-quality repair, not another observability pass. The immediate code repair is a generic loss-dominated marginal follow-up brake in `BranchLifecyclePolicy`: active marginal/no-effect lineages with case losses greater than wins, pair losses at least pair wins, and non-positive median delta now park instead of consuming repeated formal screening rows.
- Preserve pair-positive branch depth: non-loss-dominated pair-positive marginal evidence remains eligible for continuation or diagnostic validation through the existing protocol path.

## Candidate-by-Candidate Decision Table

Policy thresholds from `protocol_prod.yaml` / repair report:

- expanded screening exhausted is required for diagnostic validation in this path;
- `median_delta >= 0` when pair-level signal is used;
- `pair_win_rate >= 0.50`;
- `min_pair_total >= 12`;
- `pair_wins >= 6`;
- `pair_wins - pair_losses >= 4`;
- `pair_wins / (pair_wins + pair_losses) >= 0.70`;
- `pair_losses / pair_total <= 0.25`.

Case W/L/T below is the `DecisionFeatures` case-level decision input, not the raw observability case list.

| Round | Branch | Candidate | Change | Case W/L/T | Pair W/L/T | Decision | Main Reason | Pair Policy Judgment |
|---:|---|---|---|---:|---:|---|---|---|
| 1 | `4d47d152...` | `5337de2a16e6852a` | create `operators/consolidate_subcategory.py` | 2/0/8 | 9/5/6 | `expand_screening` | `SCREENING_EXPAND_LOW_SNR_TRAJECTORY_DIVERGENT` | Not eligible yet: first screening, expand not exhausted. Also pair win rate is 9/20 = 0.45 and non-tie win rate is 9/14 = 0.64, below policy. |
| 2 | `4d47d152...` | `bdb377c15aff2629` | expanded screening of same hypothesis | 3/1/12 | 13/11/8 | `abandon` | `SCREENING_EXPAND_EXHAUSTED_BORDERLINE_NEGATIVE_DELTA`, `SCREENING_BORDERLINE_POLICY_FAIL_CLOSED`, lifecycle archive | Fails policy: median delta -50, pair win rate 13/32 = 0.41, margin 2, non-tie win rate 13/24 = 0.54, loss rate 11/32 = 0.34. |
| 3 | `3e328bae...` | `29382371359f2068` | modify `operators/move_order.py`, broad split-preserving cost move | 1/2/3 | 3/4/5 | `continue_explore` | `SCREENING_FAIL_WIN_RATE`, `SCREENING_MARGINAL_SIGNAL_CONTINUE` | Fails policy: not expanded-exhausted; pair wins < losses; pair win rate 0.25; loss rate 0.33. |
| 4 | `3e328bae...` | `a92b0560e22a72cf` | modify `move_order.py`, tighter same-subcategory/downgrade guard | 1/2/3 | 3/4/5 | `continue_explore` | `SCREENING_FAIL_WIN_RATE`, `SCREENING_MARGINAL_SIGNAL_CONTINUE` | Same failure as round 3. |
| 5 | `3e328bae...` | `19ae5ad5b4ea7951` | modify `move_order.py`, singleton-only absorption | 1/2/3 | 3/4/5 | `continue_explore` | `SCREENING_FAIL_WIN_RATE`, `SCREENING_MARGINAL_SIGNAL_CONTINUE` | Same failure as round 3. |
| 6 | `3e328bae...` | `d0fdfbe2eb1690d4` | modify `move_order.py`, independent opportunity-density guard | 1/2/3 | 3/4/5 | `continue_explore` | `SCREENING_FAIL_WIN_RATE`, `SCREENING_MARGINAL_SIGNAL_CONTINUE` | Same failure as round 3. |

Important reconciliation note:

- Raw pair metrics and branch observability list some positive cases, for example `3e328bae...` repeatedly has positive raw cases `s03` and `ml02`.
- That did not make the candidate policy-positive. DecisionFeatures still had low case win rate and pair losses equal to or exceeding wins.
- Under v3, the raw observability lists may guide the next proposal, but they cannot override the deterministic DecisionFeatures gate.

## Why There Was 0 Validation / 0 Frozen / 0 Promotion

1. All six protocol rows stopped at screening. `status.json` reports `protocol_metric_stage_counts.screening=6`, `validation=0`, `frozen=0`.
2. Contract, verification, and canary all passed for the formal candidates. There was no pre-protocol failure sink.
3. The pair-level diagnostic repair only creates a validation route for expanded-exhausted, non-regressive, pair-positive evidence. The rerun did not produce that shape:
   - `4d47d152...` initially looked low-SNR enough to expand, but after expansion it had negative median and heavy pair losses.
   - `3e328bae...` was never pair-positive: `3/4/5` pair W/L/T repeated four times.
4. Frozen and promotion are downstream of validation. With no `QUEUE_VALIDATE`, no frozen holdout or promotion dossier could occur.

## Branch Depth: `3e328bae...`

The branch did achieve scheduler depth: four counted screening steps on the same branch, all targeting `operators/move_order.py` and mechanism `split_preserving_cost_move`.

However, this was not effective research depth.

Evidence:

- Metrics were identical across all four formal candidates:
  - DecisionFeatures case W/L/T: `1/2/3`
  - pair W/L/T: `3/4/5`
  - median delta: `0.0`
  - CI: `[-1925.0, 1500.0]`
  - decision: `continue_explore`
- Raw pair aggregation was also identical across all four metric refs:
  - pair W/L/T: `3/4/5`
  - raw positive cases: `s03`, `ml02`
  - raw negative cases: `ms02`, `m03`
- Code diffs were not byte-identical. The branch moved from:
  - broad ranked cost move,
  - to same-subcategory/downgrade guard,
  - to singleton-only absorption,
  - to independent opportunity-density guard.
- But those changes did not alter the measured outcome on the screening set. The branch was changing trigger text and local filters without changing the evaluated behavior distribution.

Judgment:

- Same-branch depth is mechanically present but scientifically weak.
- The issue is not that scheduler failed to permit depth; it permitted too much low-yield same-mechanism refinement after a repeated unchanged signal.
- The branch should have been forced into either a materially different mechanism or an explicit activation/effect diagnostic that proves the new guard changes activation counts on the losing cases before spending another formal screening row.

## Agent Context / Branch Lessons

Branch lesson visibility was present.

Prompt manifest evidence:

- Hypothesis manifests included `branch_lesson_usage_context`.
- Repair-profile hypothesis manifests for same-branch refinement also included `same_mechanism_follow_up_constraints`.
- The context was not truncated in the sampled manifests.

Usage evidence:

- Campaign observability reports:
  - `branch_lesson_record_count=6`
  - `branch_lesson_usage_requirement_count=3`
  - `branch_lesson_usage_present_count=6`
  - `branch_lesson_usage_satisfied_count=4`
  - `branch_lesson_usage_present_not_semantic_count=2`
  - `branch_lesson_usage_missing_block_count=0`
- The `3e328bae...` hypothesis outputs explicitly referenced lessons, avoided the closed `subcategory_consolidation` branch, preserved `same_subcat_singleton_absorption`, and contrasted new triggers such as `density_guard_not_single_trigger`.

Judgment:

- Context/lesson visibility is not the primary failure.
- The agent used lessons semantically enough to change proposal text and code shape.
- The lesson mechanism is still too weak as a quality gate: it accepts plausible semantic usage even when the next formal candidate repeats the same objective evidence exactly. It catches missing usage, not "lesson usage failed to produce a measurable behavior delta."

## Specific Next Fixes

### 1. Add a same-branch repeated-signal brake

Module targets:

- `scion/scion/core/scheduling/signals.py`
- `scion/scion/core/scheduler.py`
- likely tests under `scion/scion/tests/unit/` near scheduler and screening feedback tests.

Change:

- When the same branch and same mechanism produce the same deterministic screening signature twice in a row, do not schedule another same-branch refinement unless the next proposal is a diagnostic/telemetry run with an explicit activation/effect measurement plan.
- Signature should be deterministic and compact:
  - stage,
  - case W/L/T,
  - pair W/L/T,
  - median bucket,
  - loss-heavy flag,
  - mechanism id.

Acceptance:

- A unit test constructs a branch with two consecutive `split_preserving_cost_move` results of `case=1/2/3`, `pair=3/4/5`, `median=0.0`; scheduler must return `create_new` or a diagnostic-only same-branch action, not `same_branch_low_signal_observation_sample`.
- Existing pair-positive expanded-exhausted `6/2/4` diagnostic validation behavior remains unchanged.

### 2. Strengthen material-difference requirements for same-branch refinement

Module targets:

- `scion/scion/core/explore_step/material_difference.py`
- `scion/scion/core/explore_step/branch_lesson_usage.py`
- `scion/scion/core/explore_step_pipeline.py` or whichever pre-code quality block currently calls these checks.

Change:

- For same-branch same-mechanism refinements after a repeated signature, require `material_difference` to name a measurable behavior delta, not just changed trigger words.
- Required fields should be machine-checkable:
  - `expected_activation_delta`
  - `protected_loss_cases`
  - `new_noop_condition`
  - `measurable_counter_name`
- Block code generation if this is missing or metadata-only.

Acceptance:

- A hypothesis like "tighten singleton trigger" without expected activation/effect counters is blocked before code.
- A hypothesis that names `move_order.singleton_absorption_attempts`, `accepted_saving`, and the losing cases `ms02/m03` passes proposal quality but remains tainted and proposal-only.

### 3. Add problem-owned activation counters for warehouse operators

Module targets:

- warehouse problem adapter/provider layer, not generic Decision:
  - likely `scion/problems/warehouse_delivery/*`
  - warehouse prompt/provider files that render problem-owned telemetry guidance
  - runtime bridge that collects candidate telemetry into audit/proposal context.

Change:

- Add optional operator-level counters for warehouse production diagnostics:
  - `move_order.candidate_count`
  - `move_order.accepted_count`
  - `move_order.noop_reason.{capacity,subcategory,destination,loss_guard}`
  - `move_order.accepted_saving`
  - `consolidate_subcategory.repack_attempts`
  - `consolidate_subcategory.repack_successes`
- Keep them excluded from `DecisionFeatures`; use only in proposal context and postrun audit.

Acceptance:

- The next 6R-like run can explain whether `3e328bae...` refinements changed activation on `s03/ml02/ms02/m03`.
- `DecisionFeatures` schema and no-free-text validation remain unchanged.

### 4. Fix or quarantine misleading family coverage / stagnation labels

Evidence:

- `campaign_summary.family_coverage` reports `subcategory_consolidation: 6`, while research shape diagnostics separately show `split_preserving_cost_move: 5` and `subcategory_consolidation: 3`.
- Stagnation signal says all recent steps use `subcategory_consolidation`, which contradicts the four `move_order.py` same-branch candidates.

Module targets:

- summary/stagnation recording:
  - `scion/scion/core/evidence_recording/summary.py`
  - `scion/scion/core/stagnation.py` or the warehouse/problem mechanism-family mapper used by summaries.

Change:

- Ensure family coverage and stagnation use canonical `mechanism_ids`, not stale broad family labels or hypothesis text family.

Acceptance:

- For this rerun replay/postrun summary, four `3e328bae...` steps are counted as `split_preserving_cost_move`, not `subcategory_consolidation`.
- Stagnation message should say flat repeated `split_preserving_cost_move` signal, not all `subcategory_consolidation`.

### 5. Do not loosen pair-level validation thresholds yet

No threshold change is justified by this run.

Reason:

- The repaired policy was designed for pair-positive, non-regressive evidence like `case 2/0/4`, `pair 6/2/4`, `median 0`.
- This rerun produced:
  - expanded branch: `pair 13/11/8`, median `-50`;
  - deep branch: `pair 3/4/5`.
- Lowering thresholds would validate loss-heavy candidates, not recover a hidden positive signal.

## Recommended Next Experiment

Run one short controlled rerun after the scheduler/material-difference fixes:

- same 6R budget;
- keep protocol thresholds unchanged;
- require same-branch repeated-signal brake;
- require activation/effect counters for warehouse same-branch refinements;
- postrun acceptance:
  - no three consecutive formal candidates on same branch may have identical case and pair W/L/T unless the intervening candidate is an explicit diagnostic;
  - any `QUEUE_VALIDATE` must show either ordinary screening pass or repaired pair-level diagnostic pass;
  - summary family coverage must match formal candidate target mechanisms.
