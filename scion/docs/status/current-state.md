# Scion v0.4 Current State

Last updated: 2026-07-06

This file is the operational resume point, not a run log. Historical root
chronology belongs in focused experiment reports, sparse milestones, and git
history.

## Operating Frame

- Branch: `v0.4-dev`.
- Boundary authority: `scion/design/scion-architecture-v3.md`.
- Current task source: `scion/TASK.md`.
- Latest cross-document audit:
  `scion/reports/v04-task-basis-alignment-audit-20260629.md`.
- v0.4 closes only after Scion demonstrates effective research behavior on the
  repaired framework. v0.5 is for broad controlled experiment matrices, not
  deferred v0.4 framework repair.
- Server-local validation and small/single experiment runs use conda `claw`.
  WSL is retained as the high-resource runner for large or concurrent
  experiment batches; its conda environment is named `scion`.

## Current Decision

v0.4 is not closed.

The framework direction is largely correct:

- v3 `DecisionFeatures` boundaries remain intact.
- Measurement declarations, A/A/MDE diagnostics, opportunity summaries, and
  postrun review summaries are problem-owned and proposal/readiness-visible,
  not Decision input.
- CVRP `runtime_model=budget_exhausting` semantics are now treated as
  observational for comparative runtime pressure while preserving raw evidence.
- Branch depth, prepared successor focus, reviewed/default-avoid evidence,
  inactive-mechanism suppression, resume snapshots, and postrun readiness have
  materially improved.
- Warehouse is restored as a positive effective-research control and
  plateau-review-ready for v0.4 framework evidence.

The remaining closeout gaps are:

- CVRP remains solver-negative. Successor19 and successor20 prove repaired
  framework behavior on `bounded_route_segment_exchange`, but not
  promotion-grade solver improvement. Successor21 completed on WSL with active
  scheduler destroy-size telemetry and no infra/proposal failures, but the
  actual mechanism was `operator_pair_destroy_size_bands`, not
  `stagnation_adaptive_destroy_size_schedule`; its expanded row was
  loss-heavy below MDE. Successor22b correctly targeted
  `stagnation_adaptive_destroy_size_schedule`, but q was unchanged versus the
  champion in aligned ALNS traces and both screening rows had median delta
  `0.0`. Successor23 repaired the observable q trajectory for the same
  scheduler family, but both rows remained below MDE, the expanded row was
  negative, explicit q-audit fields were missing, and the branch parked as
  quality regression. Successor24 completed as a valid insertion-cost
  lookahead repair clean fork, but both rows remained below MDE and the v2 row
  recorded direct-effect-zero telemetry. Successor25 completed as a valid raw
  construction seed-baseline clean fork but stayed at median delta `0.0`.
  Successor26 first exposed a static-quality recognizer gap; successor26b then
  reran the repaired short-horizon construction seed trajectory selector path
  and completed valid screening, but both rows were below MDE and the v2 row
  lost on CMT2/CMT4. Successor27 completed as a valid non-seed destroy/repair
  clean fork, `route_pair_overlap_removal`; both rows were positive but below
  MDE, and the expanded row still lost on CMT4 and P-family cases. Successor28
  completed valid/complete/postrun-ready but tested alternative
  destroy/repair clean forks, not a true protected route-pair-overlap
  continuation; both rows failed screening with negative medians. Successor29
  completed valid/complete/postrun-ready and did test the true protected
  `route_pair_overlap_removal_protected_followup` mechanism, but both rows
  failed screening with negative aggregate medians. Treat the route-pair-
  overlap line as parked for v0.4. Successor30 then completed
  valid/complete/postrun-ready on the materially different
  `bounded_cross_route_double_bridge_polish` local-search design, but both
  screening rows had median delta `0.0`, CI `[0.0, 0.0]`, win rate `0.0`, and
  direct phase telemetry showed active runtime with zero objective effect.
  Treat unchanged double-bridge polish as reviewed/default-avoid. The
  successor31 design review then selected a different CVRP-owned runtime
  allocation path, `adaptive_embedded_vns_runtime_allocation`. Successor31
  completed valid/complete/postrun-ready with that required mechanism and
  direct phase runtime telemetry, but both screening rows stayed exact
  zero-effect: median delta `0.0`, CI high `0.0`, win rate `0.0`, and
  `rows_at_or_above_mde=0`. Treat unchanged adaptive embedded-VNS runtime
  allocation as reviewed/default-avoid too. Successor32 is now designed as
  `post_repair_effect_credit_weighting`, a narrow
  `acceptance_or_adaptive_weighting` clean fork in
  `policies/baseline_modules/scheduler.py`. It should credit ALNS
  destroy/repair adaptive weights from post-repair pre-polish objective effect
  while keeping destroy/repair patterns, local-search moves, construction
  seeds, embedded-VNS runtime allocation, simulated-annealing acceptance, and
  generic core unchanged. The first successor32 launch root
  `/home/clawd/research/scion-experiments/v04-cvrp-successor32-post-repair-effect-credit-weighting-server-2r-gpt55-20260701T135711Z-claw`
  was stopped before screening because the live hypothesis drifted to
  `pair_failure_cooldown_selection`; it is not successor32 solver evidence.
  A CVRP problem-owned `cvrp_successor32_focus` hypothesis quality gate now
  blocks scheduler.py successor32 proposals unless they name the required
  operator-credit mechanism before code generation. The guarded-live relaunch
  `/home/clawd/research/scion-experiments/v04-cvrp-successor32-post-repair-effect-credit-weighting-server-guarded-live-2r-gpt55-20260701T141225Z-claw`
  was stopped before screening after three formal quality blocks
  (`elite_current_restart`, `repair_failure_pair_filter`,
  `runtime_normalized_pair_credit`). It is fail-closed evidence for the guard,
  not solver evidence. The current checkout adds a generic proposal-only
  `target_intent_required_mechanism_ids` binding so target-intent selection
  can be pinned to `post_repair_effect_credit_weighting` while hard
  `required_mechanism_ids` stays empty. The target-bound successor32 relaunch
  then completed valid/complete/postrun-ready with two screened rows and no
  quality/model/telemetry/postrun failures. Both live target-intent and formal
  hypothesis bindings stayed on `post_repair_effect_credit_weighting`, and
  mechanism telemetry showed activation plus internal effect, but final
  objective evidence stayed zero at the case gate: both rows had median delta
  `0.0`, CI `[0.0, 0.0]`, `rows_at_or_above_mde=0`, and
  `max_effect_to_mde_ratio=0.0`. Treat unchanged post-repair effect credit
  weighting as reviewed/default-avoid; target binding is framework-positive,
  not solver-positive. Successor33 then forced `neighbor_list_vns_filter` in
  `policies/baseline_modules/local_search.py` and completed
  valid/complete/postrun-ready. The first candidate was negative, but the
  second customer-adjacency filter passed screening (`20/6/6`, median `6.25`)
  and validation (`24/7/1`, median `7.75`) with active telemetry before frozen
  abandoned it for six candidate-side timeouts on large X cases. Successor34
  then tested `frozen_safe_neighbor_list_vns_filter` and completed
  valid/complete/postrun-ready. It removed the frozen timeout blocker, but the
  best row stayed weak-positive below MDE (median `0.25`, CI high `3.25`) and
  CMT2 remained negative. Successor35 then tested
  `capacity_tightness_removal` in `policies/baseline_modules/destroy_repair.py`
  and completed valid/complete/postrun-ready, but both screening rows were
  solver-negative (`median_delta=-6.0` and `-3.5`, `rows_at_or_above_mde=0`)
  with CMT2 negative in both rows. Treat unchanged capacity-tight removal as
  reviewed/default-avoid. Successor36 then promoted
  `seed_post_optimization_selector` activation repair using a new
  `policies/baseline_modules/seed_selector.py` module and minimal scheduler
  construction-boundary wiring, but ended with zero effective protocol rows
  after three repeated static-quality blocks. Trace audit showed generated
  `seed_selector.py` candidates contained direct `record_move(..., delta=...)`
  telemetry; the CVRP static recognizer had not included `seed_selector.py` in
  construction-seed direct-effect paths. Successor36b reran after the
  recognizer repair from clean commit `9fc23c86` and completed
  valid/complete/postrun-ready with active direct telemetry, but both rows had
  zero aggregate medians, no positive row at MDE, and CMT2 regressed. Treat
  unchanged seed-post selector variants as reviewed/default-avoid. Successor37
  completed the next no-force clean fork but did not produce promotion-grade
  solver evidence: route-angle local search was negative, and edge-frequency
  repair scoring was weak-positive below MDE but direct-effect-zero with
  CMT2/CMT4 all-seed losses. Successor38 then tested the
  proposal-control/candidate-quality repair and completed valid/complete/
  postrun-ready. The CVRP-owned causal-path contract blocked the first weak
  hypothesis before code generation, but the accepted
  `radial_2opt_star_relink` candidate was active-no-effect: zero accepted
  mechanism moves, zero direct mechanism best delta, all case gates tied, and
  `mechanism_contract_status=observed_no_effect`. Treat unchanged
  `radial_2opt_star_relink` as reviewed/default-avoid; do not long-run or
  same-branch follow up despite weak pair-level lifecycle noise. Successor39 is
  now designed and target-intent-bound as `bounded_dual_repair_selector` in
  `policies/baseline_modules/scheduler.py`: compare the default repair against
  one bounded alternate repair before VNS, keep formal
  `required_mechanism_ids` empty, and require direct pre-VNS selector telemetry
  plus CMT2/CMT4 protection evidence before any long-run decision. The first
  successor39 launch root
  `/home/clawd/research/scion-experiments/v04-cvrp-successor39-bounded-dual-repair-selector-server-2r-gpt55-20260706T003754Z-claw`
  was stopped after a stale successor32 scheduler guard blocked the correct
  successor39 mechanism; do not treat it as solver evidence. The guard is now
  retargeted, and the clean retry root
  `/home/clawd/research/scion-experiments/v04-cvrp-successor39-bounded-dual-repair-selector-server-retry-2r-gpt55-20260706T004158Z-claw`
  completed valid/complete/postrun-ready with local `gpt-5.5`, four normal
  model calls, two screening rows, and no promotion. Row 1 had median delta
  `0.0`, CI `[-3.5, 6.5]`; row 2 had median delta `0.75`, CI
  `[-6.25, 6.5]`; both CI highs were below the 9.9 MDE. Treat unchanged
  `bounded_dual_repair_selector` as reviewed below-MDE evidence, not a long-run
  candidate. The successor39 trace audit exposed prompt/context degradation:
  prepared evidence obligations reached hypothesis context but were compressed
  before code generation. The current checkout now renders those obligations
  as a dedicated `Prepared Research Obligations` section in target-intent,
  hypothesis, and code prompts, and no longer accepts truncated target-file
  previews as sufficient solver-design grounding. The stale successor36/39
  file-level focus gate has been removed from the CVRP hypothesis quality
  contract; current target binding now comes from prepared
  `target_intent_required_mechanism_ids`, while reviewed/default-avoid and
  causal-path gates still block repeated weak mechanisms. Successor40 then
  completed valid/complete/postrun-ready on
  `bounded_two_for_one_exchange` in
  `policies/baseline_modules/local_search.py`. The first row had direct
  mechanism activation and A-n64 gains but stayed mixed below MDE with CMT2/X
  losses; the guarded same-mechanism follow-up reduced runtime and many losses
  into ties but still had median delta `0.0`, CI `[-2.0, 0.0]`, and residual
  B/CMT2 losses. Treat unchanged two-for-one exchange and threshold/gating
  variants as reviewed below-MDE evidence. The postrun report is
  `scion/docs/experiments/v0.4/v04-cvrp-successor40-bounded-two-for-one-exchange-postrun-20260706.md`.
  CVRP research guidance has been updated so unchanged
  `bounded_two_for_one_exchange` repeats are blocked as reviewed/default-avoid.
  Successor41 is now preregistered as `route_skeleton_regret_repair`, a
  proposal-only target-intent clean fork at the scheduler repair boundary. It
  compares the normal repaired candidate against one bounded route-skeleton-
  biased regret repair candidate before VNS/polish; formal
  `required_mechanism_ids` remains empty while
  `target_intent_required_mechanism_ids` contains
  `route_skeleton_regret_repair`. The design is
  `scion/docs/experiments/v0.4/v04-cvrp-successor41-route-skeleton-regret-repair-design-20260706.md`.
- Large files remain a design risk. Further behavior changes in oversized
  core/postrun/proposal/problem files should follow the new modularization
  design before implementation.
- The v0.5 governance ablation matrix is preregistered, but must not run as a
  v0.4 closeout substitute.

## Active Technical State

- Designs A-K in `scion/design/v0.4-effective-research-repair-design.md` are
  accepted local repairs for scheduling status, guidance contracts,
  lifecycle/failure routing, target-intent authority, launcher lifecycle, and
  mechanism-evidence follow-up.
- Designs L/M are accepted runtime repairs: budget-exhausting runtime evidence
  remains in raw artifacts but no longer creates numeric proposal-visible
  runtime-regression pressure or stale fresh-runtime clean-fork pressure.
- Design N moved postrun/readiness behavior toward typed generic ports and
  problem-owned review providers. Do not add new semantics to legacy postrun
  helper scripts when a named port/provider is the right boundary.
- Design O introduced `MeasurementConsumerView` as the typed consumer view for
  protocol/runtime/proposal/readiness paths.
- Designs P/Q/R introduced problem-owned opportunity summaries, opportunity
  evidence commitments, and postrun visibility for those commitments. These are
  proposal/report signals and remain excluded from Decision.
- Prepared successor-focus arbitration and scheduler filtering are generic and
  field-driven: reviewed or suppressed branch-local mechanism ids can be
  superseded for prepared runs, but mixed branches with non-excluded mechanisms
  remain schedulable under proposal guards.
- Prepared launch research obligations now reach target-intent, hypothesis,
  and code prompts as a first-class proposal-only section. Code generation no
  longer treats a compressed hypothesis brief as the only source of truth when
  prepared evidence obligations exist.
- Solver-design target grounding requires full target-file content or a full
  target slice. Truncated file previews remain diagnostic only and are not
  sufficient for modify/remove target binding.
- Resume launches quarantine copied terminal artifacts under
  `run_root/resume_snapshot/`; current-run canonical files must represent the
  current execution.

## Problem Frontiers

Warehouse:

- Treat the clean v2 positive-control run as restored effective-research and
  plateau-review evidence for v0.4 framework purposes.
- Do not launch another warehouse run by default.
- Warehouse calibration provenance is resolved in the current checkout: both
  warehouse spec copies set `root_dir` to `surrogate`, so
  `calibration/aa_noise_floor.json` resolves to the checked-in canonical
  artifact at `surrogate/calibration/aa_noise_floor.json`.

CVRP:

- Treat current completed successor evidence as framework-positive and
  solver-negative. Successor19 completed locally with postrun readiness ready:
  two screening rows, no validation/frozen rows, `rows_at_or_above_mde=0`, and
  final `continue_explore`.
- Successor20 completed on WSL and is postrun-ready:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-successor20-bounded-segment-refine-2r-gpt55-20260629T150851Z-claw`.
  It resumed successor19 and forced `solver_design` / `modify` /
  `policies/baseline_modules/local_search.py`. The current-run metrics are:
  two screening rows, no validation/frozen rows, `positive_rows=0`,
  `rows_at_or_above_mde=0`, `max_median_delta=0.0`, and
  `interpretation=all_available_ci_high_below_mde`.
- Successor21 completed on WSL and is postrun-ready:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-successor21-adaptive-destroy-size-2r-gpt55-20260629T172740Z-claw`.
  It forced `solver_design` / `modify` /
  `policies/baseline_modules/scheduler.py`. The actual mechanism was
  `operator_pair_destroy_size_bands`; it activated and changed q, but row 1
  remained below MDE and row 2 failed closed with median delta `-5.5`, CI
  `[-8.0, 2.75]`, and CMT4 median `-2.0`.
- Successor22b completed on WSL and is postrun-ready:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-successor22b-stagnation-required-2r-gpt55-20260629T193044Z-claw`.
  It forced `solver_design` / `modify` /
  `policies/baseline_modules/scheduler.py`, used local `gpt-5.5`, and
  completed two screening rows with no proposal, verification, telemetry, or
  infra failure. The mechanism was
  `stagnation_adaptive_destroy_size_schedule`, but row 1 had `0 / 505` aligned
  ALNS q changes and row 2 had `0 / 737`; both rows had median delta `0.0`,
  CI `[0.0, 0.0]`, and no case-level wins.
- Continue using A/A MDE and case variance when interpreting CVRP effects.
- Do not repeat unchanged reviewed mechanisms. Successor23 already repaired the
  successor22b observable q-trajectory no-op, but it stayed solver-negative and
  missed explicit q-audit fields. Successor24 then completed as an active
  destroy/repair insertion-cost lookahead attempt, but row 1 stayed below MDE
  and row 2 was direct-effect-zero plus below MDE. The next solver attempt
  should clean-fork to a materially different CVRP-owned causal path.
- Successor23 completed on WSL and is postrun-ready:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-successor23-stagnation-q-delta-repair-2r-gpt55-20260630T020559Z-claw`.
  It was prepared from WSL runner commit `b0adf692`, passed completion
  preflight with `gpt-5.5`, base URL `http://127.0.0.1:8080`, and completed
  two screening rows. The mechanism was
  `stagnation_adaptive_destroy_size_schedule`; aligned q traces changed versus
  champion in most pairs, but explicit `baseline_q/adapted_q/q_delta` runtime
  fields were missing. Objective evidence stayed below MDE: row 1 median
  delta `0.0`, CI `[-2.0, 3.5]`; row 2 median delta `-0.5`, CI
  `[-3.0, 3.25]`; `rows_at_or_above_mde=0`. Treat the branch as
  `activation-repaired-but-below-MDE` with `quality-regression-parked` and
  `explicit-q-delta-telemetry-missing` caveats.
- Successor24 completed on WSL and is postrun-ready:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-successor24-lookahead-insertion-repair-2r-gpt55-20260630T073830Z-claw`.
  It passed completion preflight with `gpt-5.5`, used runner commit `462d6e0a`,
  and completed two screening rows. Row 1 mechanism
  `lookahead_insertion_cost_repair` had median delta `-0.75`, CI
  `[-5.5, 0.5]`; row 2 mechanism `lookahead_insertion_cost_repair_v2` had
  median delta `-2.0`, CI `[-12.0, 1.5]`, and direct-effect-zero telemetry
  (`candidate_present=60`, `candidate_positive=0`, `candidate_zero=60`).
  Treat both as reviewed/default-avoid. Postrun report:
  `scion/docs/experiments/v0.4/v04-cvrp-successor24-lookahead-insertion-repair-postrun-20260630.md`.
- The CVRP problem-owned guidance/catalog and measurement-opportunity adapter
  are aligned to that result: prepared handoffs emit an empty hard
  `required_mechanism_ids` list, treat successor23 and successor24 mechanisms as
  reviewed/default-avoid evidence, and now treat unchanged successor25 raw seed
  selection plus successor26b construction seed trajectory selection as
  reviewed/default-avoid evidence.
- Successor25 completed on WSL and is postrun-ready:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-successor25-cw-sweep-seed-baseline-selector-2r-gpt55-20260630T101601Z-claw`.
  It was prepared from WSL runner commit `d501b900`, used local `gpt-5.5`, and
  forced `solver_design` / `modify` /
  `policies/baseline_modules/construction.py`. It completed two screening rows
  with mechanism activation/runtime observed, but objective evidence stayed
  below MDE: both rows had median delta `0.0`, CI `[0.0, 0.0]`,
  `rows_at_or_above_mde=0`. The expanded row was abandoned as quality
  regression. It observed direct seed delta on `B-n67-k10`, but that effect did
  not survive downstream search. Postrun report:
  `scion/docs/experiments/v0.4/v04-cvrp-successor25-cw-sweep-seed-baseline-selector-postrun-20260630.md`.
- Successor25 plan/in-flight records:
  `cw_sweep_seed_baseline_selector`, owned by
  `policies/baseline_modules/construction.py` with scheduler edits limited to
  selector invocation and direct selected-seed versus baseline telemetry. Plan:
  `scion/docs/experiments/v0.4/v04-cvrp-successor25-cw-sweep-seed-baseline-selector-plan-20260630.md`.
  In-flight record:
  `scion/docs/experiments/v0.4/v04-cvrp-successor25-cw-sweep-seed-baseline-selector-inflight-20260630.md`.
- Successor26 targeted:
  `short_horizon_seed_trajectory_selector`, owned by
  `policies/baseline_modules/scheduler.py`. It compared a small existing
  seed set after a strictly bounded short-horizon trajectory and recorded
  baseline versus selected post-trajectory objective delta before full ALNS/VNS.
  Plan:
  `scion/docs/experiments/v0.4/v04-cvrp-successor26-short-horizon-seed-trajectory-selector-plan-20260630.md`.
- Successor26 ran on the server-local `claw` environment because the WSL
  preflight failed before campaign execution with HTTPS TLS errors:
  `/home/clawd/research/scion-experiments/v04-cvrp-successor26-short-horizon-seed-trajectory-selector-server-2r-gpt55-20260630T132452Z-claw`.
  Commit `6896451f`, local `gpt-5.5`, completion preflight passed, forced
  `solver_design` / `modify` / `policies/baseline_modules/scheduler.py`. The
  run ended invalid with `invalid_no_effective_rounds`,
  `interrupted_incomplete`, stop reason `repeated_quality_block_signature`,
  `proposal_quality_blocks=3`, and `protocol_metric_results=0`. All proposals
  were blocked before effective screening by
  `agent_quality_blocked:cvrp_construction_seed_direct_effect_missing` because
  the candidate patches did not satisfy direct
  `context.record_move("short_horizon_seed_trajectory_selector", ...)` effect
  telemetry. This is not solver-negative evidence. In-flight record:
  `scion/docs/experiments/v0.4/v04-cvrp-successor26-short-horizon-seed-trajectory-selector-inflight-20260630.md`.
  Postrun report:
  `scion/docs/experiments/v0.4/v04-cvrp-successor26-short-horizon-seed-trajectory-selector-postrun-20260630.md`.
  The failed WSL preflight root is
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-successor26-short-horizon-seed-trajectory-selector-2r-gpt55-20260630T132127Z-claw`;
  it reported HTTP `502` / `tls handshake eof` and should be treated as an
  environment preflight failure, not campaign evidence.
- Successor26 follow-up selected a static-quality recognizer repair, not a
  relaxation of the direct-effect gate. The repair accepts module-level
  mechanism-id aliases used inside solver class methods and still rejects local
  dynamic alias shadowing. Retry guidance now asks for same-run
  seed/trajectory-vs-baseline objective effect, matching the short-horizon
  trajectory-selector design. Targeted CVRP tests pass locally.
- Successor26b completed on the server-local `claw` runner and is postrun-ready:
  `/home/clawd/research/scion-experiments/v04-cvrp-successor26b-short-horizon-seed-trajectory-selector-static-recognizer-server-2r-gpt55-20260630T134339Z-claw`.
  It used local `gpt-5.5`, completed two effective screening rows, had no
  proposal-quality blocks, no postrun failures, and readiness passed. Row 1
  `short_horizon_seed_trajectory_selector` had median delta `0.0`, CI
  `[0.0, 0.0]`, win rate `0.0`; row 2
  `short_horizon_seed_trajectory_selector_v2` had median delta `-5.0`, CI
  `[-8.0, 9.0]`, win rate `0.25`, CMT2 median `-8.0`, and CMT4 median
  `-19.0`. Treat unchanged construction seed trajectory selection as
  reviewed/default-avoid. Postrun report:
  `scion/docs/experiments/v0.4/v04-cvrp-successor26b-short-horizon-seed-trajectory-selector-postrun-20260630.md`.
- Successor27 completed as the next non-seed clean fork:
  `/home/clawd/research/scion-experiments/v04-cvrp-successor27-non-seed-clean-fork-server-2r-gpt55-20260630T151408Z-claw`.
  It launched from commit `5241eb22` on server-local `claw`, used local
  `gpt-5.5`, passed completion preflight, and forced
  `solver_design` / `modify` /
  `policies/baseline_modules/destroy_repair.py`. It finished
  valid/complete/postrun-ready with no quality, model, telemetry, or postrun
  failures. The mechanism was `route_pair_overlap_removal`. Row 1 median delta
  was `0.75`, CI `[-4.5, 12.5]`; row 2 median delta was `2.5`, CI
  `[-7.75, 7.0]`; rows at/above MDE remained `0`. Useful gains appeared on
  A/B/X cases, but CMT2/CMT4/P-family losses remain the follow-up blocker.
  In-flight record:
  `scion/docs/experiments/v0.4/v04-cvrp-successor27-non-seed-clean-fork-inflight-20260630.md`.
  Postrun:
  `scion/docs/experiments/v0.4/v04-cvrp-successor27-route-pair-overlap-postrun-20260701.md`.
  Successor28 plan:
  `scion/docs/experiments/v0.4/v04-cvrp-successor28-route-pair-overlap-protected-followup-plan-20260701.md`.
- Successor28 completed as a server-local follow-up run:
  `/home/clawd/research/scion-experiments/v04-cvrp-successor28-route-pair-overlap-protected-followup-server-2r-gpt55-20260701T001959Z-claw`.
  It launched from commit `ed051d93` on server-local `claw`, used local
  `gpt-5.5`, passed completion preflight, and forced
  `solver_design` / `modify` /
  `policies/baseline_modules/destroy_repair.py`. It finished
  valid/complete/postrun-ready with no quality, model, telemetry, or postrun
  failures, but it did not test a true protected same-mechanism
  `route_pair_overlap_removal` continuation. Row 1 tested
  `boundary_spoke_outlier_removal` and failed screening with median delta
  `-1.5`, CI `[-7.25, 13.0]`, and win rate `0.25`; CMT2 was `-5.5` and CMT4
  was `-8.0`. Row 2 tested `edge_conflict_endpoint_removal` and failed
  screening with median delta `-2.5`, CI `[-8.0, 2.0]`, and win rate `0.25`;
  CMT2 was `-8.0`, CMT4 was `-12.0`, and X-n110 was `-6.0`. Treat both
  mechanisms as reviewed/default-avoid unless a future proposal changes the
  causal path materially. In-flight record:
  `scion/docs/experiments/v0.4/v04-cvrp-successor28-route-pair-overlap-protected-followup-inflight-20260701.md`.
  Postrun:
  `scion/docs/experiments/v0.4/v04-cvrp-successor28-route-pair-overlap-protected-followup-postrun-20260701.md`.
- Successor29 completed as the true required route-pair-overlap follow-up:
  `/home/clawd/research/scion-experiments/v04-cvrp-successor29-route-pair-overlap-required-followup-server-2r-gpt55-20260701T031419Z-claw`.
  It launched from commit `9cfee8e3` on server-local `claw`, used local
  `gpt-5.5`, passed completion preflight, and forced `solver_design` /
  `modify` / `policies/baseline_modules/destroy_repair.py`. Unlike
  successor28, this run root had a single-run prepared-manifest override:
  `research_focus.required_mechanism_ids` and typed
  `research_guidance_contract.required_mechanisms` both required
  `route_pair_overlap_removal_protected_followup`. The run finished
  valid/complete/postrun-ready with no quality, model, telemetry, or postrun
  failures. The required mechanism reached formal screening, but both rows were
  abandoned: row 1 median delta `-1.75`, CI `[-6.75, 8.5]`, win rate `0.25`;
  row 2 median delta `-3.75`, CI `[-7.5, 12.0]`, win rate `0.25`, and
  direct-effect-zero telemetry. CMT2 was `-10.0` in both rows, CMT4 stayed
  negative, and `rows_at_or_above_mde=0`. Plan:
  `scion/docs/experiments/v0.4/v04-cvrp-successor29-route-pair-overlap-required-followup-plan-20260701.md`.
  In-flight record:
  `scion/docs/experiments/v0.4/v04-cvrp-successor29-route-pair-overlap-required-followup-inflight-20260701.md`.
  Postrun:
  `scion/docs/experiments/v0.4/v04-cvrp-successor29-route-pair-overlap-required-followup-postrun-20260701.md`.
- Successor30 completed as a materially different local-search follow-up:
  `/home/clawd/research/scion-experiments/v04-cvrp-successor30-bounded-cross-route-double-bridge-server-2r-gpt55-20260701T052131Z-claw`.
  It launched from commit `9cfee8e3` on server-local `claw`, used local
  `gpt-5.5`, passed completion preflight, and forced `solver_design` /
  `modify` / `policies/baseline_modules/local_search.py`. The run root
  required `bounded_cross_route_double_bridge_polish` in both
  `research_focus.required_mechanism_ids` and typed
  `research_guidance_contract.required_mechanisms`. It finished
  valid/complete/postrun-ready with `2` effective screening rows,
  `proposal_attempts_total=3`, `proposal_quality_blocks=1`, no postrun
  failures, and readiness passed. The quality block was a useful fail-closed
  guard against a single-route implementation of a claimed cross-route
  mechanism. The two formal rows both had median delta `0.0`, CI `[0.0, 0.0]`,
  win rate `0.0`, `rows_at_or_above_mde=0`, and
  `max_effect_to_mde_ratio=0.0`. Phase runtime telemetry was active, but
  effect-zero diagnostics reported `candidate_present=64`,
  `candidate_positive=0`, and `candidate_zero=64`. Treat unchanged
  `bounded_cross_route_double_bridge_polish` as reviewed/default-avoid; its
  `continue_explore` lifecycle decision is not solver-positive v0.4 evidence.
  Plan:
  `scion/docs/experiments/v0.4/v04-cvrp-successor30-bounded-cross-route-double-bridge-plan-20260701.md`.
  In-flight record:
  `scion/docs/experiments/v0.4/v04-cvrp-successor30-bounded-cross-route-double-bridge-inflight-20260701.md`.
  Postrun:
  `scion/docs/experiments/v0.4/v04-cvrp-successor30-bounded-cross-route-double-bridge-postrun-20260701.md`.
- Successor31 design review is written:
  `scion/docs/experiments/v0.4/v04-cvrp-successor31-design-review-20260701.md`.
  It rejects another same-mechanism local-search or destroy/repair follow-up by
  default and recommends `adaptive_embedded_vns_runtime_allocation`, a
  problem-owned scheduler/runtime-allocation path that changes how budget is
  split between ALNS exploration and embedded VNS exploitation.
- Successor31 completed on the server-local `claw` runner:
  `/home/clawd/research/scion-experiments/v04-cvrp-successor31-adaptive-embedded-vns-runtime-allocation-server-2r-gpt55-20260701T111631Z-claw`.
  It launched from commit `9cfee8e3`, passed live launch readiness and local
  `gpt-5.5` completion preflight, forced `solver_design` / `modify` /
  `policies/baseline_modules/scheduler.py`, and used a run-root-only
  prepared-manifest override requiring
  `adaptive_embedded_vns_runtime_allocation`. Initial target-intent/hypothesis
  binding kept the required mechanism and target file. The campaign finished
  valid/complete/postrun-ready with two effective screening rows, no quality
  blocks, no model failures, no telemetry failures, and no postrun failures.
  Both rows reached the required mechanism and observed phase runtime telemetry,
  but objective effect stayed zero: median delta `0.0`, CI high `0.0`, win
  rate `0.0`, `rows_at_or_above_mde=0`, and
  `max_effect_to_mde_ratio=0.0`. Case-level medians were flat except
  P-n101-k4 at `-0.5`; CMT2/CMT4 had no positive median. Treat unchanged
  `adaptive_embedded_vns_runtime_allocation` as reviewed/default-avoid.
  In-flight record:
  `scion/docs/experiments/v0.4/v04-cvrp-successor31-adaptive-embedded-vns-runtime-allocation-inflight-20260701.md`.
  Postrun:
  `scion/docs/experiments/v0.4/v04-cvrp-successor31-adaptive-embedded-vns-runtime-allocation-postrun-20260701.md`.
- Successor32 completed on the server-local `claw` runner after two earlier
  pre-screen guard roots:
  `/home/clawd/research/scion-experiments/v04-cvrp-successor32-post-repair-effect-credit-weighting-server-target-bound-2r-gpt55-20260701T142821Z-claw`.
  It launched from commit `76952d20`, used local `gpt-5.5`, passed completion
  preflight, and forced `solver_design` / `modify` /
  `policies/baseline_modules/scheduler.py`. The proposal-only
  `target_intent_required_mechanism_ids` binding worked: both target-intent
  calls selected `post_repair_effect_credit_weighting`, and both formal
  hypothesis bindings were `bound` while hard `required_mechanism_ids` stayed
  empty. The run finished valid/complete/postrun-ready with two effective
  screening rows, no quality blocks, no model failures, no telemetry failures,
  and no postrun failures. Row 1 branch `94224fba` was an
  `active_quality_regression` row with pair result `0` wins / `1` loss /
  `31` ties and median delta `0.0`; the only nonzero pair was
  `E-n101-k14` seed `11` at `-6.0`. Row 2 branch `32716e6f` was `clean` with
  pair result `1` win / `0` losses / `31` ties and median delta `0.0`; the
  only nonzero pair was `X-n110-k13` seed `43` at `+70.0`. Both rows had CI
  `[0.0, 0.0]`, case result all ties, `rows_at_or_above_mde=0`, and
  `max_effect_to_mde_ratio=0.0`. Mechanism activation/internal effect telemetry
  was observed, but objective effect was `zero_objective_effect`. Treat
  unchanged `post_repair_effect_credit_weighting` as reviewed/default-avoid.
  Design:
  `scion/docs/experiments/v0.4/v04-cvrp-successor32-post-repair-effect-credit-weighting-design-20260701.md`.
  In-flight record:
  `scion/docs/experiments/v0.4/v04-cvrp-successor32-post-repair-effect-credit-weighting-inflight-20260701.md`.
  Postrun:
  `scion/docs/experiments/v0.4/v04-cvrp-successor32-post-repair-effect-credit-weighting-postrun-20260701.md`.
- Successor33 completed on the server-local `claw` runner:
  `/home/clawd/research/scion-experiments/v04-cvrp-successor33-neighbor-list-vns-filter-server-2r-gpt55-20260701T160210Z-claw`.
  It launched from commit `b579797d`, used local `gpt-5.5`, passed completion
  preflight, and forced `solver_design` / `modify` /
  `policies/baseline_modules/local_search.py`. Both live target-intent and
  formal hypothesis traces stayed bound to `neighbor_list_vns_filter`. The
  first candidate failed screening, but the second customer-adjacency filter
  passed screening (`20/6/6`, median `6.25`) and validation (`24/7/1`, median
  `7.75`) with active mechanism telemetry. Frozen abandoned the branch for
  six candidate-side large-instance timeouts, so there was no promotion. Treat
  successor33 as validation-positive but frozen-unsafe. Successor34 then
  tested `frozen_safe_neighbor_list_vns_filter` and completed
  valid/complete/postrun-ready, but stayed weak-positive below MDE with CMT2
  negative. Treat unchanged successor34 as reviewed/default-avoid for v0.4.
  Postrun:
  `scion/docs/experiments/v0.4/v04-cvrp-successor33-neighbor-list-vns-filter-postrun-20260701.md`.
  Successor34 design:
  `scion/docs/experiments/v0.4/v04-cvrp-successor34-frozen-safe-neighbor-list-vns-filter-design-20260701.md`.
  Successor34 postrun:
  `scion/docs/experiments/v0.4/v04-cvrp-successor34-frozen-safe-neighbor-list-vns-filter-postrun-20260702.md`.
  Successor35 design:
  `scion/docs/experiments/v0.4/v04-cvrp-successor35-capacity-tightness-removal-design-20260702.md`.
  Successor35 in-flight:
  `scion/docs/experiments/v0.4/v04-cvrp-successor35-capacity-tightness-removal-inflight-20260702.md`.
  Successor35 postrun:
  `scion/docs/experiments/v0.4/v04-cvrp-successor35-capacity-tightness-removal-postrun-20260705.md`.
  Successor36 design:
  `scion/docs/experiments/v0.4/v04-cvrp-successor36-seed-post-optimization-selector-activation-design-20260705.md`.
  Successor36 in-flight:
  `scion/docs/experiments/v0.4/v04-cvrp-successor36-seed-post-optimization-selector-activation-inflight-20260705.md`.
  Successor36 quality-block postrun:
  `scion/docs/experiments/v0.4/v04-cvrp-successor36-seed-post-optimization-selector-quality-block-postrun-20260705.md`.
  Successor36b in-flight:
  `scion/docs/experiments/v0.4/v04-cvrp-successor36b-seed-post-selector-static-smoke-repair-inflight-20260705.md`.
  Successor36b postrun:
  `scion/docs/experiments/v0.4/v04-cvrp-successor36b-seed-post-selector-static-smoke-repair-postrun-20260705.md`.
  Successor37 in-flight:
  `scion/docs/experiments/v0.4/v04-cvrp-successor37-cleanfork-material-causal-path-inflight-20260705.md`.
- Successor22a was stopped before formal screening because the live hypothesis
  drifted to `bounded_repair_retry_on_reject`; treat it as a wrong-mechanism
  diagnostic, not solver evidence.
- The `seed_post_optimization_selector` repair plan is now reviewed/default-
  avoid for unchanged variants. Successor16/17 showed missing activation,
  successor36 showed a static-quality recognizer boundary gap, and successor36b
  completed valid active screening but stayed zero aggregate / no-positive-at-
  MDE with CMT2 regression. The current CVRP slot should not force
  `seed_selector.py`. Successor37 completed a no-force clean-fork slot from
  commit `289aaa8a`; treat unchanged `route_angle_aware_2opt_star` and
  `edge_frequency_penalty_repair` as reviewed/default-avoid.
- Successor38 proposal-control repair is implemented from
  `scion/docs/experiments/v0.4/v04-cvrp-successor38-proposal-quality-contract-design-20260705.md`.
  The first root from commit `ad014be2` was stopped before screening as
  feedback-shape evidence only. The retry root
  `/home/clawd/research/scion-experiments/v04-cvrp-successor38-proposal-quality-contract-cleanfork-server-retry-2r-gpt55-20260705T153833Z-claw`
  completed from commit `23e23a1d` with local `gpt-5.5`: 2/2 screening rows,
  valid/complete/postrun-ready, no postrun failures, one expected
  proposal-quality block, and accepted `radial_2opt_star_relink` with material
  difference, direct effect telemetry, and structured CMT2/CMT4 protection.
  Solver evidence is negative/no-effect: row medians were `0.0` and `0.0`,
  case gates were 0/0/20 wins/losses/ties, `radial_2opt_star_relink` had zero
  accepted mechanism moves and zero direct best delta across both rows, and the
  branch's weak-positive lifecycle lane conflicts with
  `mechanism_contract_status=observed_no_effect`. Treat unchanged
  `radial_2opt_star_relink` as reviewed/default-avoid.
- Use problem-owned successor review evidence, row-local `mechanism_family`,
  direct `mechanism_evidence.primary_mechanism`, and phase telemetry as the
  current source of truth.

## Next Actions

1. Treat successor26b as valid solver-negative evidence for unchanged
   short-horizon construction seed trajectory selection. Do not relaunch
   unchanged `short_horizon_seed_trajectory_selector` or
   `short_horizon_seed_trajectory_selector_v2`.
2. Park unchanged successor23-style scheduler q scheduling, successor24-style
   insertion-cost lookahead repair, successor25 raw construction seed-baseline
   selection, and successor26b construction seed trajectory selection.
3. Treat successor28 as valid negative evidence for unchanged
   `boundary_spoke_outlier_removal` and `edge_conflict_endpoint_removal`; do not
   treat it as a completed protected `route_pair_overlap_removal` follow-up.
4. Treat successor29 as valid negative evidence for the true protected
   `route_pair_overlap_removal_protected_followup` follow-up. Park the
   route-pair-overlap line for v0.4.
5. Treat successor30 as valid zero-effect solver-negative evidence for
   unchanged `bounded_cross_route_double_bridge_polish`. The first static
   quality block is useful fail-closed framework evidence, but the final
   `continue_explore` lifecycle decision is not solver-positive.
6. Treat successor31 as valid zero-effect solver-negative evidence for
   unchanged `adaptive_embedded_vns_runtime_allocation`. Runtime telemetry was
   active, but it produced no objective effect and should not continue on
   lifecycle status alone.
7. Treat successor32 as valid solver-negative evidence for unchanged
   `post_repair_effect_credit_weighting`. The target-bound run proves the
   proposal binding and mechanism telemetry work, but it produced no
   positive-at-MDE or case-gate objective evidence. Do not relaunch the
   unchanged operator-credit mechanism.
8. Treat successor34 as valid weak-positive below-MDE evidence for
   `frozen_safe_neighbor_list_vns_filter`: no model/quality/telemetry/postrun
   failure and no frozen timeout blocker, but no positive-at-MDE row and CMT2
   remained negative. Do not continue the unchanged neighbor-list filter line
   in the next slot.
9. Treat successor35 as valid solver-negative evidence for unchanged
   `capacity_tightness_removal`. The server-local run at
   `/home/clawd/research/scion-experiments/v04-cvrp-successor35-capacity-tightness-removal-server-2r-gpt55-20260702T004158Z-claw`
   completed valid/complete/postrun-ready with active mechanism telemetry, but
   row medians were negative and CMT2 stayed negative. Do not expand the
   unchanged capacity-tight removal line.
10. Treat successor36 as a recognizer-boundary quality block, not solver
   evidence. The clean root at
   `/home/clawd/research/scion-experiments/v04-cvrp-successor36-seed-post-optimization-selector-activation-server-clean-2r-gpt55-20260705T081741Z-claw`
   ended `invalid_no_effective_rounds` after three repeated
   `cvrp_construction_seed_direct_effect_missing` blocks. The current checkout
   includes the repair: `seed_selector.py` is now part of CVRP construction
   seed direct-effect static smoke paths, with tests covering activation-only
   rejection and alias-based direct-effect acceptance. Successor36b completed
   the same forced `solver_design` / `create_new` /
   `policies/baseline_modules/seed_selector.py` design at
   `/home/clawd/research/scion-experiments/v04-cvrp-successor36b-seed-post-selector-static-smoke-repair-server-2r-gpt55-20260705T104029Z-claw`
   from commit `9fc23c86`; it is valid active solver-negative evidence, so the
   next slot should not use `target_intent_required_mechanism_ids` or force
   `seed_selector.py`.
11. Treat successor37 as valid solver-negative/candidate-quality evidence. The
   server-local `claw` root is
   `/home/clawd/research/scion-experiments/v04-cvrp-successor37-cleanfork-material-causal-path-server-2r-gpt55-20260705T133809Z-claw`
   from experiment commit `289aaa8a`; the run completed
   valid/complete/postrun-ready. Do not long-run or repeat unchanged
   `route_angle_aware_2opt_star`; it screened negative. Do not repeat unchanged
   `edge_frequency_penalty_repair`; it was weak-positive below MDE,
   direct-effect-zero, and CMT2/CMT4 unsafe.
12. Treat successor38 as proposal-control positive but solver-negative. The
   causal-path contract blocked the first weak hypothesis, but the accepted
   `radial_2opt_star_relink` candidate produced zero accepted mechanism moves,
   zero direct mechanism best delta, all case gates tied, and
   `observed_no_effect` mechanism contract status. Do not long-run or repeat
   unchanged `radial_2opt_star_relink`; the next slot must clean-fork to a
   materially different CVRP-owned causal path.
13. Treat successor39 as valid current-run but solver-negative below-MDE
   evidence for unchanged `bounded_dual_repair_selector`. It activated and
   showed local positive selector telemetry, but both screening rows stayed
   below MDE and CMT4/B/P-family losses remain. Do not long-run or extend the
   unchanged mechanism; use the prompt/context repair before the next CVRP
   design.
14. Treat successor40 as valid current-run but solver-negative below-MDE
   evidence for `bounded_two_for_one_exchange`. Do not long-run or extend
   unchanged two-for-one exchange gating variants; the next CVRP slot should
   clean-fork to a materially different problem-owned causal path with direct
   objective-effect telemetry and CMT2/CMT4 protection. The CVRP guidance and
   prompt payload already park successor40 as reviewed/default-avoid rather
   than a live target-intent-required mechanism.
15. Launch successor41 as the next small server-local CVRP experiment:
   `route_skeleton_regret_repair` at the scheduler repair boundary, with
   optional small repair implementation in `destroy_repair.py`. Require direct
   pre-VNS objective telemetry, route-count/feasibility preservation, bounded
   effort, and CMT2/CMT4 protection.
16. Use the v0.4 large-file modularization plan before adding behavior to
   oversized files.
17. Keep the v0.5 governance ablation preregistration frozen until v0.4 closes.
18. Keep status documents compact; put detailed root counters and caveats in
   focused experiment reports.

## Runner Notes

Server:

- Repo: `/home/clawd/research/or-autoresearch-agent`
- Use conda `claw` for local validation and small/single runs, especially when
  WSL is unavailable.

WSL, only after rechecking connectivity:

- Primary repo: `/home/xjy-ubuntu/research/or-autoresearch-agent`
- Current synced runner copy:
  `/home/xjy-ubuntu/research/or-autoresearch-agent-v04dev-runner-20260629`
- Python/env: `/home/xjy-ubuntu/miniconda3/envs/scion/bin/python`
- Intended use: large or concurrent experiment batches that exceed the server's
  comfortable local capacity.
- Current caveat: SSH/env checks pass and the 2026-06-30 successor24 WSL root
  passed `gpt-5.5` completion preflight (HTTP 200) and completed. Still rerun
  completion preflight on any future freshly prepared root.

```bash
ssh -i /home/clawd/.ssh/id_ed25519_codex_wsl -p 2222 \
  -o BatchMode=yes -o ConnectTimeout=8 -o StrictHostKeyChecking=no \
  xjy-ubuntu@127.0.0.1 \
  'echo SSH_OK; hostname; whoami; /home/xjy-ubuntu/miniconda3/envs/scion/bin/python --version'
```

If WSL-origin roots are mirrored locally, WSL postrun acceptance remains
authoritative because mirrored artifacts can keep WSL absolute paths.

## Preserved Guarantees

- Generic core must not contain CVRP/VRP/warehouse-specific scheduler,
  target-intent, launcher-lifecycle, mechanism-evidence, or runtime-pressure
  exceptions.
- Raw calibration rows, BKS data, case-level problem facts, LLM prose, prompt
  text, runtime feedback prose, and branch-lesson prose stay out of
  `DecisionFeatures`.
- Candidate crashes, invalid outputs, telemetry guard failures, hard negative
  evidence, verification failures, and actionable comparative runtime
  regressions remain fail-closed.
- Problem-owned declarations define runtime model, effect scale, pairing
  validity, practical delta, and readiness diagnostics; generic consumers use
  normalized deterministic views.
- New behavior should not be added by piling helper functions into oversized
  files. Design package/module boundaries first, then implement through named
  ports/providers or coherent independent modules.
- Status docs should replace stale facts rather than append chronology.

## Pointers

- Architecture: `scion/design/scion-architecture-v3.md`
- Task source: `scion/TASK.md`
- Current basis audit:
  `scion/reports/v04-task-basis-alignment-audit-20260629.md`
- Framework repair design:
  `scion/design/v0.4-effective-research-repair-design.md`
- Postrun/readiness port design:
  `scion/design/v0.4-postrun-readiness-and-opportunity-ports.md`
- v0.4 planning:
  `scion/docs/planning/v0.4/v0.4-evidence-repair-and-validation-plan-20260611.md`
- v0.5 governance ablation preregistration:
  `scion/docs/planning/v0.5/governance-ablation-preregistration-20260629.md`
- Sparse milestone index: `scion/docs/status/v0.4-history.md`
- Detailed experiment evidence: `scion/docs/experiments/v0.4/`
- Warehouse calibration provenance:
  `scion/docs/experiments/v0.4/v04-warehouse-calibration-provenance-resolution-20260629.md`
- CVRP successor19 plan:
  `scion/docs/experiments/v0.4/v04-cvrp-successor19-cleanfork-plan-20260629.md`
- CVRP successor19 in-flight record:
  `scion/docs/experiments/v0.4/v04-cvrp-successor19-cleanfork-inflight-20260629.md`
- CVRP successor19 local postrun:
  `scion/docs/experiments/v0.4/v04-cvrp-successor19-cleanfork-local-postrun-20260629.md`
- CVRP successor20 in-flight record:
  `scion/docs/experiments/v0.4/v04-cvrp-successor20-bounded-segment-refine-inflight-20260629.md`
- CVRP successor20 WSL postrun:
  `scion/docs/experiments/v0.4/v04-cvrp-successor20-bounded-segment-refine-postrun-20260629.md`
- CVRP successor21 adaptive destroy-size plan:
  `scion/docs/experiments/v0.4/v04-cvrp-successor21-adaptive-destroy-size-plan-20260629.md`
- CVRP successor21 adaptive destroy-size in-flight:
  `scion/docs/experiments/v0.4/v04-cvrp-successor21-adaptive-destroy-size-inflight-20260629.md`
- CVRP successor21 adaptive destroy-size postrun:
  `scion/docs/experiments/v0.4/v04-cvrp-successor21-adaptive-destroy-size-postrun-20260629.md`
- CVRP successor22 stagnation destroy-size plan:
  `scion/docs/experiments/v0.4/v04-cvrp-successor22-stagnation-destroy-size-plan-20260629.md`
- CVRP successor22 stagnation destroy-size in-flight:
  `scion/docs/experiments/v0.4/v04-cvrp-successor22-stagnation-destroy-size-inflight-20260629.md`
- CVRP successor22b stagnation required postrun:
  `scion/docs/experiments/v0.4/v04-cvrp-successor22b-stagnation-required-postrun-20260630.md`
- CVRP successor23 q-delta activation repair plan:
  `scion/docs/experiments/v0.4/v04-cvrp-successor23-stagnation-q-delta-repair-plan-20260630.md`
- CVRP successor23 q-delta activation repair in-flight:
  `scion/docs/experiments/v0.4/v04-cvrp-successor23-stagnation-q-delta-repair-inflight-20260630.md`
- CVRP successor23 q-delta activation repair postrun:
  `scion/docs/experiments/v0.4/v04-cvrp-successor23-stagnation-q-delta-repair-postrun-20260630.md`
- CVRP successor24 lookahead insertion repair plan:
  `scion/docs/experiments/v0.4/v04-cvrp-successor24-lookahead-insertion-repair-plan-20260630.md`
- CVRP successor24 lookahead insertion repair in-flight:
  `scion/docs/experiments/v0.4/v04-cvrp-successor24-lookahead-insertion-repair-inflight-20260630.md`
- CVRP successor24 lookahead insertion repair postrun:
  `scion/docs/experiments/v0.4/v04-cvrp-successor24-lookahead-insertion-repair-postrun-20260630.md`
- CVRP successor25 CW/sweep seed-baseline selector plan:
  `scion/docs/experiments/v0.4/v04-cvrp-successor25-cw-sweep-seed-baseline-selector-plan-20260630.md`
- CVRP successor25 CW/sweep seed-baseline selector in-flight:
  `scion/docs/experiments/v0.4/v04-cvrp-successor25-cw-sweep-seed-baseline-selector-inflight-20260630.md`
- CVRP successor25 CW/sweep seed-baseline selector postrun:
  `scion/docs/experiments/v0.4/v04-cvrp-successor25-cw-sweep-seed-baseline-selector-postrun-20260630.md`
- CVRP successor26 short-horizon seed trajectory selector plan:
  `scion/docs/experiments/v0.4/v04-cvrp-successor26-short-horizon-seed-trajectory-selector-plan-20260630.md`
- CVRP successor26 short-horizon seed trajectory selector in-flight:
  `scion/docs/experiments/v0.4/v04-cvrp-successor26-short-horizon-seed-trajectory-selector-inflight-20260630.md`
- CVRP successor26 short-horizon seed trajectory selector invalid postrun:
  `scion/docs/experiments/v0.4/v04-cvrp-successor26-short-horizon-seed-trajectory-selector-postrun-20260630.md`
- CVRP successor27 route-pair overlap postrun:
  `scion/docs/experiments/v0.4/v04-cvrp-successor27-route-pair-overlap-postrun-20260701.md`
- CVRP successor28 route-pair overlap protected follow-up plan:
  `scion/docs/experiments/v0.4/v04-cvrp-successor28-route-pair-overlap-protected-followup-plan-20260701.md`
- CVRP successor28 route-pair overlap protected follow-up in-flight:
  `scion/docs/experiments/v0.4/v04-cvrp-successor28-route-pair-overlap-protected-followup-inflight-20260701.md`
- CVRP successor28 route-pair overlap protected follow-up postrun:
  `scion/docs/experiments/v0.4/v04-cvrp-successor28-route-pair-overlap-protected-followup-postrun-20260701.md`
- CVRP successor29 required route-pair overlap follow-up plan:
  `scion/docs/experiments/v0.4/v04-cvrp-successor29-route-pair-overlap-required-followup-plan-20260701.md`
- CVRP successor29 required route-pair overlap follow-up in-flight:
  `scion/docs/experiments/v0.4/v04-cvrp-successor29-route-pair-overlap-required-followup-inflight-20260701.md`
- CVRP successor29 required route-pair overlap follow-up postrun:
  `scion/docs/experiments/v0.4/v04-cvrp-successor29-route-pair-overlap-required-followup-postrun-20260701.md`
- CVRP successor30 bounded cross-route double-bridge plan:
  `scion/docs/experiments/v0.4/v04-cvrp-successor30-bounded-cross-route-double-bridge-plan-20260701.md`
- CVRP successor30 bounded cross-route double-bridge in-flight:
  `scion/docs/experiments/v0.4/v04-cvrp-successor30-bounded-cross-route-double-bridge-inflight-20260701.md`
- CVRP successor30 bounded cross-route double-bridge postrun:
  `scion/docs/experiments/v0.4/v04-cvrp-successor30-bounded-cross-route-double-bridge-postrun-20260701.md`
- CVRP successor31 design review:
  `scion/docs/experiments/v0.4/v04-cvrp-successor31-design-review-20260701.md`
- CVRP successor31 adaptive embedded VNS runtime allocation in-flight:
  `scion/docs/experiments/v0.4/v04-cvrp-successor31-adaptive-embedded-vns-runtime-allocation-inflight-20260701.md`
- CVRP successor31 adaptive embedded VNS runtime allocation postrun:
  `scion/docs/experiments/v0.4/v04-cvrp-successor31-adaptive-embedded-vns-runtime-allocation-postrun-20260701.md`
- CVRP successor32 post-repair effect credit weighting design:
  `scion/docs/experiments/v0.4/v04-cvrp-successor32-post-repair-effect-credit-weighting-design-20260701.md`
- CVRP successor32 post-repair effect credit weighting in-flight:
  `scion/docs/experiments/v0.4/v04-cvrp-successor32-post-repair-effect-credit-weighting-inflight-20260701.md`
- CVRP successor32 post-repair effect credit weighting postrun:
  `scion/docs/experiments/v0.4/v04-cvrp-successor32-post-repair-effect-credit-weighting-postrun-20260701.md`
- CVRP successor33 neighbor-list VNS filter design:
  `scion/docs/experiments/v0.4/v04-cvrp-successor33-neighbor-list-vns-filter-design-20260701.md`
- CVRP successor33 neighbor-list VNS filter in-flight:
  `scion/docs/experiments/v0.4/v04-cvrp-successor33-neighbor-list-vns-filter-inflight-20260701.md`
- CVRP successor33 neighbor-list VNS filter postrun:
  `scion/docs/experiments/v0.4/v04-cvrp-successor33-neighbor-list-vns-filter-postrun-20260701.md`
- CVRP successor34 frozen-safe neighbor-list VNS filter design:
  `scion/docs/experiments/v0.4/v04-cvrp-successor34-frozen-safe-neighbor-list-vns-filter-design-20260701.md`
- CVRP successor34 frozen-safe neighbor-list VNS filter in-flight:
  `scion/docs/experiments/v0.4/v04-cvrp-successor34-frozen-safe-neighbor-list-vns-filter-inflight-20260701.md`
- CVRP successor34 frozen-safe neighbor-list VNS filter postrun:
  `scion/docs/experiments/v0.4/v04-cvrp-successor34-frozen-safe-neighbor-list-vns-filter-postrun-20260702.md`
- CVRP successor35 capacity-tightness removal design:
  `scion/docs/experiments/v0.4/v04-cvrp-successor35-capacity-tightness-removal-design-20260702.md`
- CVRP successor35 capacity-tightness removal in-flight:
  `scion/docs/experiments/v0.4/v04-cvrp-successor35-capacity-tightness-removal-inflight-20260702.md`
- CVRP successor38 proposal-quality contract design:
  `scion/docs/experiments/v0.4/v04-cvrp-successor38-proposal-quality-contract-design-20260705.md`
- CVRP successor38 proposal-quality contract in-flight:
  `scion/docs/experiments/v0.4/v04-cvrp-successor38-proposal-quality-contract-inflight-20260705.md`
- CVRP successor38 proposal-quality contract postrun:
  `scion/docs/experiments/v0.4/v04-cvrp-successor38-proposal-quality-contract-postrun-20260706.md`
- CVRP deferred seed-post selector activation plan:
  `scion/docs/experiments/v0.4/v04-cvrp-successor21-seed-post-selector-activation-plan-20260629.md`
- v0.4 large-file modularization plan:
  `scion/docs/engineering/module-debt/v04-large-file-modularization-plan-20260629.md`
- Audit basis:
  `scion/reports/v04-core-framework-review-20260611.md`,
  `scion/reports/v04-core-framework-code-review-20260611.md`,
  `scion/design/v0.5-evidence-uplift-roadmap.md`
