# Scion v0.4 Current State

Last updated: 2026-07-01

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
  MDE, and the expanded row still lost on CMT4 and P-family cases.
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
- Successor28 is in flight as the protected same-mechanism follow-up:
  `/home/clawd/research/scion-experiments/v04-cvrp-successor28-route-pair-overlap-protected-followup-server-2r-gpt55-20260701T001959Z-claw`.
  It launched from commit `ed051d93` on server-local `claw`, used local
  `gpt-5.5`, passed completion preflight, and forced
  `solver_design` / `modify` /
  `policies/baseline_modules/destroy_repair.py`. Initial traces include
  `hypothesis_target_intent` and `hypothesis`; no protocol row had completed
  at the first health check. In-flight record:
  `scion/docs/experiments/v0.4/v04-cvrp-successor28-route-pair-overlap-protected-followup-inflight-20260701.md`.
- Successor22a was stopped before formal screening because the live hypothesis
  drifted to `bounded_repair_retry_on_reject`; treat it as a wrong-mechanism
  diagnostic, not solver evidence.
- The `seed_post_optimization_selector` repair plan remains a deferred
  diagnostic fallback because successor16/17 showed missing activation rather
  than evidence-complete negative solver effect.
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
3. Monitor the in-flight successor28 server-local run. After it completes,
   inspect wrapper status, postrun readiness, failures, LLM trace health, and
   effect-vs-MDE before changing guidance or launching another follow-up.
4. Use the v0.4 large-file modularization plan before adding behavior to
   oversized files.
5. Keep the v0.5 governance ablation preregistration frozen until v0.4 closes.
6. Keep status documents compact; put detailed root counters and caveats in
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
- CVRP deferred seed-post selector activation plan:
  `scion/docs/experiments/v0.4/v04-cvrp-successor21-seed-post-selector-activation-plan-20260629.md`
- v0.4 large-file modularization plan:
  `scion/docs/engineering/module-debt/v04-large-file-modularization-plan-20260629.md`
- Audit basis:
  `scion/reports/v04-core-framework-review-20260611.md`,
  `scion/reports/v04-core-framework-code-review-20260611.md`,
  `scion/design/v0.5-evidence-uplift-roadmap.md`
