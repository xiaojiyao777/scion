# Scion v0.4 Evidence Repair Task

*Branch: `codex/v04-evidence-repair-plan`*
*Last updated: 2026-06-29*

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

Current judgment from the basis audit: v3 boundaries and the main v0.4
framework repairs are broadly aligned, but v0.4 is not closed. CVRP remains
solver-negative, warehouse calibration provenance still needs explicit
resolution, and future code work must be design-first modularization rather
than more helper/projection growth.

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

- CVRP has no promotion-grade solver improvement. Recent successor evidence is
  framework-positive but solver-negative.
- Warehouse spec copies reference `calibration/aa_noise_floor.json`, but the
  corresponding calibration artifact is not checked in under either warehouse
  calibration directory.
- Several production/test files remain over the 1000-line risk threshold and
  need design-first modularization before more behavior is added there.
- v0.5 governance ablation is not yet preregistered as a clean experiment
  matrix.

## Current CVRP Direction

Do not repeat unchanged reviewed paths. The next CVRP attempt should either:

- clean-fork to a materially different, non-reviewed CVRP-owned causal path; or
- explicitly repair `seed_post_optimization_selector` activation with
  pre-protocol and formal mechanism evidence.

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

Resolve the warehouse calibration artifact mismatch before treating warehouse
measurement readiness as fully checked-in and reproducible.

## Next Actions

1. Resolve warehouse calibration provenance:
   restore `calibration/aa_noise_floor.json`, point both warehouse specs at the
   correct checked-in artifact, or document why the calibration is intentionally
   external.
2. Continue one CVRP successor attempt using the current problem-owned review
   guidance: new non-reviewed causal path or explicit seed-post activation
   repair.
3. Add a lightweight large-file modularization design before further behavior
   changes in oversized core/postrun/proposal/problem files.
4. Preregister the v0.5 governance on/off experiment design without starting
   the broad matrix as v0.4 work.
5. Keep `TASK.md` and `current-state.md` compact. New detailed run facts belong
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

## Git Hygiene

- Keep commits sliced by repair surface or documentation purpose.
- Do not mix experiment reports, framework repairs, and unrelated cleanup in
  one commit unless explicitly accepted.
- Do not revert user or subagent changes unless explicitly instructed.
- Before each non-doc commit, record tests and experiment artifacts used for
  acceptance.
