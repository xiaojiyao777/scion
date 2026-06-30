# Scion v0.4 Evidence Repair Task

*Branch: `codex/v04-evidence-repair-plan`*
*Last updated: 2026-06-30*

This is the active task definition for closing v0.4. It is not a run log.
Historical launch/root details live in focused experiment reports, sparse
milestones live in `scion/docs/status/v0.4-history.md`, and exact legacy
chronology remains available through git history.

## Basis

Primary sources:

- `scion/design/scion-architecture-v3.md`
- `scion/reports/v04-core-framework-review-20260611.md`
- `scion/reports/v04-core-framework-code-review-20260611.md`
- `scion/design/v0.5-evidence-uplift-roadmap.md`
- `scion/reports/v04-task-basis-alignment-audit-20260629.md`
- `scion/docs/status/current-state.md`

Current judgment after the basis audit and warehouse provenance clarification:
v3 boundaries and the main v0.4 framework repairs are broadly aligned, but
v0.4 is not closed. Successor19, successor20, successor21, successor22b, and
successor23 produced valid CVRP framework behavior but no promotion-grade
solver effect.
Successor21 tested `operator_pair_destroy_size_bands`, not the intended
stagnation schedule, and stayed below MDE. Successor22b correctly targeted
`stagnation_adaptive_destroy_size_schedule`, but formal q traces showed zero
aligned q difference versus champion and both rows had median delta `0.0`.
Successor23 repaired the observable q trajectory but produced no row at or
above MDE, missed explicit q-audit fields, and parked the branch as quality
regression.
v0.5 governance ablation is preregistered but must not start during v0.4, and
future code work must follow the design-first modularization plan rather than
add helper/projection growth.

## Objective

v0.4 must prove that Scion can support effective agent research before v0.5
starts broad experiment matrices. Do not defer framework stability, runtime
semantics, measurement readiness, prompt/context quality, or effective research
behavior to v0.5.

Effective research means:

- agents continue, reject, park, and clean-fork based on evidence;
- low-SNR CVRP evidence is interpreted against A/A MDE and case variance;
- warehouse remains a positive effective-research control;
- CVRP/warehouse facts stay problem-owned;
- generic core stays problem-neutral and deterministic;
- `DecisionFeatures` excludes LLM prose, raw problem diagnostics, raw
  calibration rows, BKS/case-gap facts, prompt text, and branch-lesson prose.

## Operating Principles

1. Use `scion-architecture-v3.md` as the boundary authority.
2. Keep measurement declarations and opportunity diagnostics problem-owned.
3. Treat budget-exhausting runtime ratios as observational for anytime solvers
   while preserving comparative runtime evidence where valid.
4. Do not add CVRP/VRP/warehouse exceptions to generic scheduler, protocol,
   lifecycle, prompt, or runtime code.
5. Do not use broad budgets, truncation, compression, or decorative gates as a
   substitute for measurement and evidence quality.
6. Preregister v0.5 governance on/off experiments, but do not run the broad
   matrix as a v0.4 closure requirement.
7. Before touching oversized production/test files, write or update a
   modularization design that names ports/providers and ownership boundaries.
8. Do not accrete helper functions as the default implementation style. Design
   the module/package boundary first; keep single files short enough to audit;
   make each functional module an independent, coherent package when behavior
   is larger than a narrow local patch.

## Phase Status

| Phase | Status | Current judgment |
|---|---|---|
| Phase 0 evidence baseline | Complete enough | Detailed run history moved to experiment reports and git history. |
| Phase 1 A/A calibration | Complete enough | CVRP and warehouse A/A artifacts exist; CVRP MDE is high enough that many screening losses are measurement-power limited. |
| Phase 2 framework repairs | Mostly complete | Runtime semantics, branch depth, prepared successor focus, proposal routing, postrun readiness, and context visibility have been materially repaired. |
| Phase 3 measurement declarations | Implemented | `MeasurementConsumerView` and problem-owned measurement specs feed protocol/runtime/proposal consumers without leaking raw diagnostics into `DecisionFeatures`. |
| Phase 4 focused validation | Active | Warehouse effective-research evidence is restored; CVRP framework behavior is repaired but solver improvement remains open. |
| Phase 5 governance comparison | v0.5 handoff only | v0.4 should prepare the design and avoid starting broad governance matrices under unresolved v0.4 debt. |

## Current Acceptance State

Accepted framework evidence:

- v3 `DecisionFeatures` boundary remains intact.
- Problem-owned measurement declarations, practical deltas, runtime model, MDE,
  opportunity summaries, and postrun review summaries are wired into proposal
  and readiness paths without becoming Decision input.
- `runtime_model=budget_exhausting` suppresses meaningless comparative runtime
  pressure for CVRP-like anytime solvers while keeping raw evidence.
- CVRP can now execute evidence-backed continuation, MDE-aware rejection,
  branch parking, reviewed/default-avoid successor guidance, suppression of
  inactive mechanisms, and clean-fork behavior.
- Warehouse v2 positive-control evidence supports restored effective research
  and plateau-review readiness for v0.4 framework purposes.
- Postrun/readiness work has moved toward typed ports and problem-owned review
  providers instead of adding more generic problem semantics.

Open blockers before v0.4 closeout:

- CVRP has no promotion-grade solver improvement yet. Successor19 was valid and
  mechanism-active but below MDE. Successor20 completed on WSL as a valid,
  postrun-ready same-branch refinement of `bounded_route_segment_exchange`, but
  remained solver-negative for closeout. Successor21 completed on WSL as a
  valid scheduler destroy-size attempt, but the actual mechanism
  `operator_pair_destroy_size_bands` stayed below MDE and failed closed on the
  expanded row (`median_delta=-5.5`, CI `[-8.0, 2.75]`, CMT4 median `-2.0`).
  Successor22b completed on WSL as the intended
  `stagnation_adaptive_destroy_size_schedule`, but it was an inactive
  q-trajectory no-op: `0 / 505` aligned ALNS iterations changed q in row 1,
  `0 / 737` changed q in row 2, and both rows had median delta `0.0`.
  Successor23 then repaired the q trajectory but stayed solver-negative:
  row 1 median delta `0.0`, CI `[-2.0, 3.5]`; row 2 median delta `-0.5`,
  CI `[-3.0, 3.25]`; `rows_at_or_above_mde=0`; the branch parked as
  quality regression and did not emit explicit `baseline_q/adapted_q/q_delta`
  runtime fields. Successor24 then completed on WSL as a valid
  `lookahead_insertion_cost_repair` clean fork, but both the original and v2
  follow-up stayed solver-negative: row 1 median delta `-0.75`, CI
  `[-5.5, 0.5]`; row 2 median delta `-2.0`, CI `[-12.0, 1.5]`; v2 also
  recorded direct-effect-zero telemetry. Successor25 then completed on WSL as
  a valid `cw_sweep_seed_baseline_selector` construction clean fork, but both
  rows had median delta `0.0`, CI `[0.0, 0.0]`, and no row at or above MDE.
- Several production/test files remain over the 1000-line risk threshold and
  need design-first modularization before more behavior is added there.
- v0.5 governance ablation is preregistered as a clean experiment matrix, but
  it is a v0.5 task and must wait for v0.4 closeout.

## Current CVRP Direction

Do not repeat unchanged reviewed paths. The latest completed CVRP attempt is
successor22b: a WSL scheduler destroy-size clean fork constrained to
`solver_design` / `modify` / `policies/baseline_modules/scheduler.py`. It
correctly targeted and recorded `stagnation_adaptive_destroy_size_schedule`,
but the candidate q trajectory was identical to the champion in aligned ALNS
traces and objective evidence was all case-level ties. Treat unchanged
successor22b-style stagnation q scheduling as an inactive no-op, not as
solver-positive evidence.

The latest completed CVRP attempt is successor24:
`lookahead_insertion_cost_repair`, a bounded destroy/repair insertion-cost
lookahead repair. It completed on WSL:
`/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-successor24-lookahead-insertion-repair-2r-gpt55-20260630T073830Z-claw`.
It targeted the intended owner file and produced replayable formal candidates,
but objective evidence stayed below MDE and the v2 follow-up had direct-effect
zero telemetry. Treat unchanged successor24-style insertion-cost lookahead
repair as reviewed/default-avoid evidence, not as a telemetry-only fix. The
postrun report is
`scion/docs/experiments/v0.4/v04-cvrp-successor24-lookahead-insertion-repair-postrun-20260630.md`.

The latest completed CVRP attempt is successor25:
`cw_sweep_seed_baseline_selector`, a construction seed-baseline selector owned
by `policies/baseline_modules/construction.py`, with scheduler edits limited
to invoking the selector and recording same-run selected-seed versus baseline
objective telemetry. It completed on WSL:
`/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-successor25-cw-sweep-seed-baseline-selector-2r-gpt55-20260630T101601Z-claw`;
the postrun report is
`scion/docs/experiments/v0.4/v04-cvrp-successor25-cw-sweep-seed-baseline-selector-postrun-20260630.md`.
It observed a direct seed delta on `B-n67-k10`, but that effect did not survive
downstream search and aggregate objective evidence stayed below MDE.
The problem-owned CVRP guidance/catalog still emits no hard
`required_mechanism_ids`, and now treats unchanged successor25-style raw seed
selection as reviewed/default-avoid evidence.

The prepared successor26 direction is
`short_horizon_seed_trajectory_selector`, owned by
`policies/baseline_modules/scheduler.py`. It should compare a small existing
seed set after a strictly bounded short-horizon trajectory, record baseline
versus selected post-trajectory objective delta before full ALNS/VNS, and keep
generic core and `DecisionFeatures` unchanged. The design plan is
`scion/docs/experiments/v0.4/v04-cvrp-successor26-short-horizon-seed-trajectory-selector-plan-20260630.md`.

Reviewed or suppressed paths include the large two-opt seed line, cross
exchange, Or-opt reinsertion, 3-opt, ejection-chain relocation, several
destroy/repair variants, granular savings seed portfolio, exact short-route
polish, and unchanged seed-post selector activation. Use problem-owned
successor review evidence, row-local `mechanism_family`, direct
`mechanism_evidence.primary_mechanism`, and phase telemetry as the current
source of truth.

## Current Warehouse Direction

Warehouse is a positive effective-research control. Do not launch another
warehouse campaign by default. Run one narrow repeat only if an independent
solver-level plateau confirmation is explicitly needed.

The warehouse A/A calibration artifact is checked in at
`surrogate/calibration/aa_noise_floor.json`. Both warehouse spec copies set
`root_dir` to `surrogate`, so their `calibration/aa_noise_floor.json` refs
resolve to that canonical artifact and measurement readiness is reproducible
from the current checkout.

## Execution Environment

- Server-local validation and small/single experiment runs use the local conda
  `claw` environment.
- WSL is the high-resource runner for large or concurrent experiment batches.
  Its conda environment is named `scion` and lives under
  `/home/xjy-ubuntu/miniconda3/envs/scion`.
- Do not assume WSL is launch-ready. Recheck the reverse SSH path and local
  `gpt-5.5` completion preflight before assigning work there. The successor24
  root above passed completion preflight on 2026-06-30 with model `gpt-5.5`,
  base URL `http://127.0.0.1:8080`, and completed successfully.

## Next Actions

1. Use the successor25 postrun report as the current CVRP truth:
   `scion/docs/experiments/v0.4/v04-cvrp-successor25-cw-sweep-seed-baseline-selector-postrun-20260630.md`.
2. Park unchanged successor23-style scheduler q scheduling and successor24-style
   insertion-cost lookahead repair; also do not repeat unchanged successor25
   construction seed-baseline selection.
3. Launch successor26 from the WSL runner after syncing the updated
   guidance/catalog/tests and plan:
   `v04-cvrp-successor26-short-horizon-seed-trajectory-selector`, forced
   `solver_design` / `modify` /
   `policies/baseline_modules/scheduler.py`.
4. Use the new large-file modularization plan before further behavior changes
   in oversized core/postrun/proposal/problem files.
5. Keep the v0.5 governance ablation frozen as a preregistered design; do not
   start the broad matrix as v0.4 work.
6. Keep `TASK.md` and `current-state.md` compact. New detailed run facts belong
   in focused experiment reports.

## Status Cadence

Update current docs only when operating truth changes:

- phase gate pass/fail;
- experiment result that changes interpretation or next action;
- accepted/rejected repair that changes framework behavior;
- commit that changes task scope, protocol, measurement, context composition,
  runtime governance, or lifecycle policy.

Do not record every launch, rerun, intermediate failure, or subagent exchange
here. Detailed counters, commands, wrapper status, and artifact caveats belong
in launch/postrun reports.

Docs to keep aligned:

- `scion/TASK.md`
- `scion/docs/status/current-state.md`
- `scion/docs/planning/v0.4/v0.4-evidence-repair-and-validation-plan-20260611.md`
- `scion/docs/planning/v0.5/governance-ablation-preregistration-20260629.md`

## Git Hygiene

- Keep commits sliced by repair surface or documentation purpose.
- Do not mix experiment reports, framework repairs, and unrelated cleanup in
  one commit unless explicitly accepted.
- Do not revert user or subagent changes unless explicitly instructed.
- Before each non-doc commit, record tests and experiment artifacts used for
  acceptance.
