# v0.4 post-40R repair verification: warehouse 12R branch analysis

Date: 2026-06-09

Experiment root:
`/home/clawd/research/scion-experiments/v04-post40r-repair-verify-warehouse-12r-gpt55-20260609T042719Z-claw`

Primary evidence:

- Architecture baseline: `scion/design/scion-architecture-v3.md`
- Campaign summary: `/home/clawd/research/scion-experiments/v04-post40r-repair-verify-warehouse-12r-gpt55-20260609T042719Z-claw/campaign/campaign_summary.json`
- Status: `/home/clawd/research/scion-experiments/v04-post40r-repair-verify-warehouse-12r-gpt55-20260609T042719Z-claw/campaign/status.json`
- Wrapper audit: `/home/clawd/research/scion-experiments/v04-post40r-repair-verify-warehouse-12r-gpt55-20260609T042719Z-claw/campaign/run_status.json`
- DB: `/home/clawd/research/scion-experiments/v04-post40r-repair-verify-warehouse-12r-gpt55-20260609T042719Z-claw/campaign/scion.db`
- LLM trace index: `/home/clawd/research/scion-experiments/v04-post40r-repair-verify-warehouse-12r-gpt55-20260609T042719Z-claw/campaign/agentic_sessions/agentic_session_trace_index.json`
- Formal candidates: `/home/clawd/research/scion-experiments/v04-post40r-repair-verify-warehouse-12r-gpt55-20260609T042719Z-claw/campaign/artifacts/formal_candidates/index.jsonl`
- Metrics: `/home/clawd/research/scion-experiments/v04-post40r-repair-verify-warehouse-12r-gpt55-20260609T042719Z-claw/campaign/metrics/*.json`

## Executive conclusion

This run is valid and complete for a 12 effective-round warehouse campaign. The wrapper exited normally (`wrapper_exit_status=0`), `run_validity.status=valid`, and the campaign stopped only because `max_rounds_exhausted`.

Scientifically, this is a positive Scion agent result. The agent found and promoted a real warehouse solver improvement: hypothesis `966c766d-18e2-434e-bcb5-8bb57ff643d8` on branch `3e7eef00-4aaf-49d5-a74c-e664b3828c39`, replacing random `MoveOrder` with same-subcategory compaction. The candidate passed screening, validation, and frozen holdout, then became `champion_version=2`.

The promotion is quality-reliable under the declared lexicographic warehouse objective. It improved the primary split/cost objective on validation and frozen holdout with fresh champion runtime evidence. The main caveat is runtime: validation and frozen both show high-confidence runtime regression (`runtime_ratio_median` about `1.47` and `1.57`). The campaign correctly treated runtime as tie-break/supporting evidence, not as a standalone promotion veto. That is consistent with the current warehouse objective policy, but it remains a mechanism issue before broader production-style runs.

The run can proceed to 20R. It can proceed to 40R as a search validation run if the next campaign keeps the terminal cleanup audit and monitors runtime pressure. Before treating 40R as a stronger framework acceptance run, fix the audit gaps listed at the end, especially explicit `DecisionFeatures` persistence and clearer proposal/effective-round accounting labels.

## Architecture boundary check

The experiment stayed inside the Scion v3 boundary in the important ways:

- LLM activity is proposal/code/tool-context only. Deterministic gates and protocol produced the actual branch decisions.
- Decisions match structured protocol results: Contract passed, Verification passed, Canary passed, protocol stage/result, and reason codes.
- Cross-branch lessons are marked as proposal visibility only: `cross_branch_research_observability.policy=proposal_observability_only` and `decision_input_policy=excluded_from_decision_features`.
- Warehouse-specific mechanisms stayed inside problem-owned operator files such as `operators/move_order.py`, `operators/split_vehicle.py`, `operators/merge_vehicles.py`, and newly proposed warehouse operators. There is no evidence of warehouse/operator-pool semantics being converted into generic Scion core rules.

One audit gap remains: `experiment_events.decision_features_json` is null in the DB protocol rows I checked. The decision behavior is reconstructable from structured columns and reason-code events, but v3 wants Decision input to be an explicit Safe Feature Extractor output. Future runs should persist the exact `DecisionFeatures` record for every decision.

## Run validity and accounting

The run is complete:

- `requested_rounds=12`
- `effective_rounds_completed=12`
- `counted_experiment_steps=12`
- `run_complete=true`
- `run_completeness_status=complete`
- `run_validity_status=valid`
- `stopped_reason=max_rounds_exhausted`

LLM accounting is clean:

- `trace_file_count=53`
- `usage_trace_count=53`
- `model_counts={"gpt-5.5": 53}`
- request kinds: `hypothesis=18`, `tool_selection=25`, `code=10`
- providers: `openai_compatible=53`
- unknown model/provider/kind counts are all zero

Protocol accounting:

- `protocol_metric_results=12`
- `protocol_stage_counts={"screening": 10, "validation": 1, "frozen": 1}`
- `verification_consumed_candidates=12`
- `verification_failure_consumed_candidates=0`
- `proposal_quality_blocks=0`
- `quality_blocks=0`
- `formal_screened_candidates=10`
- `validation_protocol_results=1`
- `frozen_protocol_results=1`

The main accounting subtlety is that 12 effective rounds are not 12 unique LLM-generated hypotheses. There are 9 unique hypotheses in the DB, because one candidate was expanded in screening and the promoted candidate consumed validation and frozen rounds without new hypothesis/code generation. The 12 effective rounds are the 12 completed protocol metric rows.

`formal_candidates/index.jsonl` has 9 entries, not 10, because it indexes replayable patch artifacts per unique screening patch candidate. The DB has 10 screening protocol rows because `4ec7133b-...` was screened twice: initial screening and expanded screening. The status file explicitly reconciles this as a formal artifact subset of screening rows.

## Protocol rounds

This table treats "round" as a completed protocol metric row, which is the counter behind `effective_rounds_completed=12`.

| R | Stage | Branch / hypothesis | LLM calls | Candidate idea and code | Protocol result | Decision / Scion v3 check |
|---:|---|---|---|---|---|---|
| 1 | screening | `7f6a27eb` / `f16cf136` | hypothesis `2`, tool_selection `4`, code `1` | Create `operators/subcategory_full_merge.py`; whole-subcategory vehicle-level repack of split subcategories. | 10 cases: wins `2`, losses `3`, ties `5`, win rate `0.20`, median delta `-0.5`, CI `[-1.5, 1.0]`; Contract/Verification/Canary passed. | `abandon`; correct screening fail and soft archive. Positive cases existed, but aggregate failed threshold. |
| 2 | screening | `e9ffe275` / `d3868e8e` | hypothesis `2`, tool_selection `1`, code `1` | Modify `operators/move_order.py` into `split_drain_move`, moving an order from split subcategory into same-subcategory vehicle. | 6 cases: wins `5`, losses `0`, ties `1`, win rate `0.833`, median delta `4.5`, CI `[1.25, 7.5]`; runtime ratio median `3.42`, regression rate `0.917`. | `abandon` by `RUNTIME_REGRESSION`. This is conservative: quality passed, but runtime was severe enough to hard-abandon this branch. |
| 3 | screening | `c7bd21e4` / `d3e92d96` | hypothesis `2`, tool_selection `2`, code `1` | Modify `operators/merge_vehicles.py` into bounded same-subcategory bin-completion merge. | 6 cases: wins `0`, losses `2`, ties `4`, win rate `0.0`, median delta `0.0`, CI `[-1.0, 1.25]`; low cached runtime confidence. | `abandon`; correct screening fail. Runtime was only advisory/audit due cached champion evidence. |
| 4 | screening | `3e7eef00` / `4ec7133b` | hypothesis `2`, tool_selection `2`, code `2` | Create `operators/subcategory_knapsack_pack.py`, bounded vehicle-level local bin/knapsack repack. | 10 cases: wins `5`, losses `1`, ties `4`, win rate `0.5`, median delta `1.5`, CI `[-0.5, 2.75]`. | `expand_screening`; correct unclear/marginal handling, not promoted from screening. |
| 5 | screening expand | `3e7eef00` / `4ec7133b` | no new LLM; same patch | Expanded same `subcategory_knapsack_pack` candidate. | 16 cases: wins `8`, losses `2`, ties `6`, win rate `0.5`, median delta `1.25`, CI `[-0.5, 2.75]`. | `continue_explore`; correct after expand exhausted. Candidate remained useful but below validation threshold. |
| 6 | screening | `3e7eef00` / `966c766d` | hypothesis `2`, tool_selection `2`, code `1` | Modify `operators/move_order.py` into split-preserving same-subcategory compaction; only move unlocked orders into existing same-subcategory vehicles, accept lexicographic improvement. | 6 cases: wins `5`, losses `0`, ties `1`, win rate `0.833`, median delta `3.5`, CI `[1.25, 8.0]`. | `queue_validate`; correct screening pass. |
| 7 | validation | `3e7eef00` / `966c766d` | no new LLM; same patch | Formal validation of the screening pass. | 6 validation cases x 3 seeds = 18 pairs; median delta `14.5`, CI `[7.0, 21.0]`; runtime ratio median `1.47`; champion runtime fresh. | `queue_frozen` by `VALIDATION_PASS_HIERARCHICAL`; correct promotion pipeline. |
| 8 | frozen | `3e7eef00` / `966c766d` | no new LLM; same patch | Final frozen holdout for same MoveOrder compaction. | 4 frozen cases x 3 seeds = 12 pairs; median delta `16.5`, CI `[8.0, 28.0]`; runtime ratio median `1.57`; all pairs valid. | `promote` by `FROZEN_PASS_HIERARCHICAL`; becomes champion v2. A separate DB holdout-use event `f49353e8-...` allowed/consumed frozen before this metric row. |
| 9 | screening | `2578557a` / `e6e60df1` | hypothesis `2`, tool_selection `2`, code `1` | Modify `operators/move_order.py` with singleton-fragment evacuation after champion v2. | 6 cases: wins `0`, losses `2`, ties `4`, win rate `0.0`, median delta `-0.5`, CI `[-2.25, 0.0]`. | `abandon`; correct post-promotion regression handling against base champion v2. |
| 10 | screening | `27af28e3` / `c41307ce` | hypothesis `2`, tool_selection `1`, code `1` | Replace `operators/split_vehicle.py` random split with guarded demix of mixed-subcategory vehicles. | 6 cases: wins `1`, losses `0`, ties `5`, win rate `0.167`, median delta `0.25`, CI `[-0.25, 1.5]`. | `continue_explore`; correct marginal positive follow-up, not validation. |
| 11 | screening | `27af28e3` / `e7e07e84` | hypothesis `2`, tool_selection `6`, code `1` | Tighten guarded demix activation: only existing compatible destination with repack capacity; suppress new-vehicle demix. | 6 cases: wins `1`, losses `0`, ties `5`, win rate `0.167`, median delta `0.25`, CI `[0.0, 2.0]`. | `continue_explore`; weak-positive retained as best checkpoint. |
| 12 | screening | `27af28e3` / `64da715c` | hypothesis `2`, tool_selection `5`, code `1` | Cost-aware destination saturation trigger for guarded demix. | 6 cases: wins `1`, losses `0`, ties `5`, win rate `0.167`, median delta `0.0`, CI `[-0.5, 1.75]`. | `continue_explore`; final metric row, leaves one active marginal branch. |

Note on numbering: the DB also has a frozen allowance event. The effective-round accounting counts the 12 metric rows: 10 screening rows, 1 validation row, and 1 frozen metric row. The frozen allowance event is visible in DB lineage but is not a `protocol_metric_results` row.

## Promotion and champion v2

Promoted hypothesis:

- Branch: `3e7eef00-4aaf-49d5-a74c-e664b3828c39`
- Hypothesis: `966c766d-18e2-434e-bcb5-8bb57ff643d8`
- Mechanism: `split_preserving_same_subcat_compact`
- File: `operators/move_order.py`
- Base champion version: `1`
- Promotion experiment id: `93226461-26bd-4fed-b6e1-843d4604ad6f`
- Champion v2 promoted at: `2026-06-09T05:24:03.800912`
- Champion v2 snapshot: `/home/clawd/research/scion-experiments/v04-post40r-repair-verify-warehouse-12r-gpt55-20260609T042719Z-claw/campaign/champions/champion_v2`

The promoted code changes only the problem-owned operator behavior. `diff -qr` between champion v1 and champion v2 shows substantive differences in `operators/move_order.py` and `registry.yaml` formatting/metadata. The `champions` DB table keeps the same six-operator pool and weights in `operator_pool_json`; no generic core policy was changed.

The promoted `MoveOrder` no longer randomly moves an unlocked order or creates a new vehicle. It:

- computes base subcategory split count and total cost;
- finds subcategories already spread across at least two vehicles;
- moves an unlocked order only into another vehicle already containing the same `vehicle_subcategory`;
- checks pickup city, vehicle category, pickup-name cap, pallets, hazard capacity, and minimum feasible vehicle type;
- accepts only if subcategory splits decrease, or if splits tie and cost decreases.

That is a plausible warehouse repair: it directly attacks the split objective while preserving feasibility constraints. It also remains in the operator layer, not the Scion core.

Validation/frozen relationship:

- Screening is not promotion evidence by itself; it queued validation.
- Validation passed on hidden validation split aggregates and queued frozen.
- Frozen holdout was explicitly allowed/consumed, then passed.
- Promotion happened only after frozen pass.
- `champion_version=2` points to the frozen protocol metric event as `promotion_experiment_id`.

This matches Scion v3: Screening Gate is coarse, Validation Gate is formal, Frozen Gate is final confirmation.

## Branch-level analysis

### `7f6a27eb`: `subcategory_full_merge`

Direction: vehicle-level whole-subcategory merge into fewer feasible vehicles.

The hypothesis was reasonable but too broad. It attempted whole-subcategory repacking with locked anchors and up to 80 rebuild orders. Screening showed mixed local wins (`instance_v4_scr_s02`, `instance_v4_scr_ml02`) but more losses (`instance_v3_scr_m05`, `instance_v3_scr_m06`, `instance_v4_scr_s03`). Median delta was negative.

Handling was correct: Contract/Verification/Canary passed, protocol failed, branch was archived/discarded rather than promoted. The formal candidate artifact exists and has complete replay identity.

### `e9ffe275`: `split_drain_move`

Direction: order-level split drain move, moving one order from a split subcategory to another same-subcategory vehicle.

This had strong quality signal: 5 wins, 0 losses, 1 tie, CI entirely positive. However runtime was severe: median runtime ratio about `3.42`, runtime regression rate `0.917`, with sufficient runtime evidence. The decision abandoned the branch by `RUNTIME_REGRESSION`.

This is a useful stress test of the framework. It proves the agent can discover quality-improving ideas, and also proves the runtime guard can stop a too-expensive implementation. It also became a sibling lesson that later proposals avoided or contrasted against.

### `c7bd21e4`: `same_subcat_bin_completion`

Direction: vehicle-level `MergeVehicles` same-subcategory bin completion.

The code made a bounded same-subcategory vehicle pair selector, but screening had no case-level wins and two losses. Runtime looked faster, but runtime confidence was `low_cached_champion`, and the policy explicitly made that audit/proposal guidance only.

Handling was correct: no promotion, no runtime-only optimism, branch archived.

### `3e7eef00`: `subcategory_knapsack_pack` then promoted MoveOrder compaction

This is the successful research branch.

First hypothesis, `subcategory_knapsack_pack`, was a vehicle-level create-new local bin packer. It produced positive but insufficient signal: initial screening was 5/1/4 with CI crossing zero, expanded screening stayed at win rate `0.5`. The branch correctly continued exploration instead of forcing validation.

Second hypothesis, `split_preserving_same_subcat_compact`, moved to an order-level targeted compaction mechanism. This was the right refinement: smaller action surface, no new vehicles, same-subcategory destination, and lexicographic acceptance. It passed screening, validation, and frozen.

Handling was correct across all lifecycle states: marginal candidate expanded, failed-to-promote candidate retained as lineage evidence, stronger candidate queued validation/frozen, and frozen pass promoted to champion v2.

### `2578557a`: post-promotion singleton fragment evacuation

Direction: order-level follow-up against champion v2, adding singleton-fragment evacuation to `MoveOrder`.

This branch correctly used `base_champion_version=2`. The idea was plausible: evacuate tiny singleton fragments into compatible same-subcategory vehicles. It failed screening with no wins, two losses, and negative median delta.

Handling was correct: abandoned after screening regression. This is important because after promotion the framework did not keep evaluating against stale champion v1.

### `27af28e3`: guarded demix split follow-ups

Direction: vehicle-level `SplitVehicle` replacement/refinements after champion v2.

This branch did not reach promotion, but it is useful ongoing research. Three variants were screened:

- `c41307ce`: replace random split with guarded demix; 1 win, 0 losses, 5 ties, median delta `0.25`, CI crosses zero.
- `e7e07e84`: tighter activation and no new-vehicle demix; 1 win, 0 losses, 5 ties, median delta `0.25`, CI low `0.0`; retained as best weak-positive checkpoint.
- `64da715c`: cost-aware destination saturation trigger; 1 win, 0 losses, 5 ties, median delta `0.0`, CI crosses zero; active marginal head.

Handling was mostly correct: weak positives were retained, no validation was queued, no rollback was needed, and the active slot remains on a same-mechanism follow-up path. The branch evidence summary marks low cached runtime confidence and excludes aggregate runtime from decision features.

## Cross-branch information transfer

Cross-branch lesson visibility is present and advisory.

Campaign-level evidence:

- `policy=proposal_observability_only`
- `decision_input_policy=excluded_from_decision_features`
- `observable_step_count=10`
- `branch_lesson_record_count=16`
- `cross_branch_map_seen_count=10`
- `avoided_lesson_count=28`
- `contrasted_lesson_count=6`
- `borrowed_lesson_count=1`
- `preserved_same_branch_lesson_count=2`
- no near-duplicate or saturated signatures

Concrete example: session `047d4291-566d-49b0-817d-460d1f86cf7e/output.json` for guarded demix shows:

- avoided same-subcat merge as closed different-family lineage;
- avoided split-drain as runtime-regression order-level lineage;
- borrowed a stricter objective/runtime guard response;
- preserved the same-branch weak-positive signal.

This is the intended behavior: sibling lessons influenced proposal direction and duplication avoidance, but did not force a deterministic branch switch. The promoted branch still had to pass protocol; the lesson layer did not enter DecisionFeatures.

Residual issue: only 4 of 7 required semantic lesson-usage cases are marked satisfied, with 4 semantic mismatches and no blocks. That is acceptable for advisory visibility, but if future campaigns rely on cross-branch lessons for stronger de-duplication, semantic satisfaction should be tightened.

## Terminal cleanup and weight optimization

Wrapper cleanup is healthy:

- root `exit.txt`: `WRAPPER_EXIT_STATUS:0`
- campaign `exit.txt`: `CAMPAIGN_EXIT_STATUS:complete`, `RUN_VALIDITY_STATUS:valid`, `RUN_COMPLETE:True`
- `run_status.json`: `status=finished`, `exit_reason=command_returned`, `wrapper_signal=null`, started `2026-06-09T04:27:20Z`, ended `2026-06-09T05:42:14Z`

Weight optimization did not leave the wrapper stuck:

- `weight_optimization.pending_threads=0`
- `weight_optimization.active=[]`
- one async run exists with `phase=cancelled`, `active=false`
- `shutdown_requested=true`
- `shutdown_reason=final_wait_timeout`
- `final_wait_timeout_sec=5.0`
- `finished_at=1780983733.542511`

I checked the local process table for `weight_opt`, `run_offline`, `milp`, the experiment path, and run pid `1568022`; only the check command itself matched. I also searched the experiment tree for detached/marker/weight pid/shutdown filenames and found no residual detached marker. The latest terminal cleanup appears to have worked: parameter search/weight-opt was cancelled rather than blocking final exit.

## Remaining mechanism fixes

1. Persist explicit `DecisionFeatures` per protocol decision.

   The DB has a `decision_features_json` column, but the checked protocol rows were null. The decision can be reconstructed, but v3 auditability is stronger if the exact safe extractor output is stored.

2. Clarify `proposal_attempts_total` naming.

   In this run it equals the effective budget count (`12`), while raw LLM proposal sessions are 18 and unique hypotheses are 9. This is explainable, but the name is misleading. Prefer separate labels for `llm_proposal_sessions`, `unique_hypotheses`, and `effective_protocol_rounds`.

3. Add promotion artifact summary for validation/frozen.

   The promotion chain is reconstructable from DB, metrics, and champion table. A compact promotion dossier should directly link screening, validation, frozen, canary, code hash, patch hash, champion snapshot hash, and replay identity.

4. Tighten cross-branch semantic satisfaction.

   Advisory lesson visibility is working, but semantic mismatch counts remain non-trivial. Keep it advisory, but improve diagnostics so weak-positive follow-up and de-duplication are easier to audit.

5. Treat runtime regression as a first-class branch pressure signal.

   The promoted candidate is quality-reliable, but slower. Current policy treats runtime as supporting/tie-break only. For longer warehouse runs, keep that boundary but add predeclared runtime escalation: profile, tune, or park if repeated high-confidence runtime regression appears.

6. Keep terminal cleanup guard in all long runs.

   This run shows the final wait/cancel path works. Keep reporting `pending_threads`, `active`, `shutdown_requested`, `shutdown_reason`, and process audit in future 20R/40R summaries.

## Final assessment

This warehouse 12R run is a meaningful positive result for Scion v0.4. It demonstrates that the agent can generate problem-relevant operator hypotheses, use feedback to shift from broad vehicle-level repacking to a smaller order-level compaction move, and produce a candidate that survives screening, validation, and frozen holdout.

The promotion to `champion_version=2` is quality-reliable under the current warehouse lexicographic objective. It should not be interpreted as a runtime win. The framework correctly did not let sibling lessons or LLM rationale decide promotion; protocol did. With the audit fixes above, this campaign is strong enough to justify moving to 20R and then a monitored 40R run.
