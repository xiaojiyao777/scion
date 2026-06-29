# Scion v0.4 Task Basis Alignment Audit - 2026-06-29

## Scope

This audit compares the current Scion checkout and `TASK.md` against the
documents that define the v0.4 repair basis:

- `scion/design/scion-architecture-v3.md`
- `scion/reports/v04-core-framework-code-review-20260611.md`
- `scion/reports/v04-core-framework-review-20260611.md`
- `scion/design/v0.5-evidence-uplift-roadmap.md`
- `scion/TASK.md`
- `scion/docs/status/current-state.md`

It is a current-state alignment review, not a historical chronology.

## Executive Judgment

v0.4 is substantially aligned with the audit requirements for restoring
effective research behavior, but it is not ready to close.

The framework has made the right repairs:

- v3 `DecisionFeatures` boundaries remain intact.
- measurement declarations and MDE diagnostics are problem-owned and
  proposal-visible, not decision input.
- CVRP `budget_exhausting` runtime semantics are now generic and deterministic.
- branch depth, mechanism-family visibility, prepared successor focus,
  reviewed/suppressed mechanism handling, and postrun readiness are materially
  repaired.
- warehouse has restored effective-research/plateau-review evidence.
- CVRP can now execute evidence-backed continuation, rejection, branch parking,
  and clean-fork behavior.

The remaining gap is evidence closure:

- CVRP still has no promotion-grade solver improvement.
- warehouse calibration artifacts are not present in the checked-in path
  referenced by `problem-v1.yaml`.
- `TASK.md` still contains too much accumulated history for a task source and
  should be reduced after the current audit result is integrated. `current-state`
  is also near the same risk boundary and should remain a live snapshot, not a
  run log.
- several production and test files exceed 1000 lines; this is now an
  engineering-risk backlog item for design-first modularization, not a reason
  to add more helper/projection layers.

## Alignment Matrix

| Requirement | Source | Current status | Judgment |
|---|---|---|---|
| Decision reads only deterministic `DecisionFeatures`; LLM text remains tainted | v3 §§1,4; 2026-06-11 reviews | `core/decision.py`, `core/features.py`, and serialization still validate no free text. Problem diagnostics are repeatedly marked `decision_features_excluded`. | Satisfied |
| Problem facts stay problem-owned; generic core stays problem-neutral | v3 data matrix; user architecture constraint | CVRP successor evidence, opportunity summaries, measurement handoff, and postrun checks live under `scion/problems/cvrp`; warehouse equivalents live under `scion/problems/warehouse_delivery`. Boundary test `test_v3_problem_boundary_no_cvrp_terms_in_generic_layers.py` protects generic layers. | Mostly satisfied |
| A/A calibration and MDE diagnostics exist before interpreting CVRP failures | core reviews P0/F1; roadmap W1/M1 | `tools/calibrate_aa_noise.py`, `MeasurementConsumerView`, `ProtocolConfig.with_problem_measurement()`, CVRP `formal/calibration/aa_noise_floor.json`, and MDE handoff exist. | Partially satisfied |
| `practical_delta` is problem-owned, not a dead hardcoded config | core reviews F1/F5; roadmap W1 | `protocol_config.py` resolves `practical_delta_screen` and `practical_delta_validate` from the measurement view. CVRP declares raw-delta practical thresholds. | Satisfied for current CVRP path |
| budget-exhausting runtime semantics stop polluting gates and feedback | core reviews F2/F6; roadmap W1/W4 | `runtime_model=budget_exhausting` disables runtime-tie fresh champion requirement in gates and renders runtime regression as not-applicable in proposal feedback. Fresh-runtime pressure ignores budget-exhausting markers. | Satisfied |
| Low-SNR CVRP can go deep rather than shallow-park everything | core reviews F3/F4; roadmap M2.5 | Current CVRP roots show branch depth, same-mechanism follow-up, mechanism-family continuity, branch parking, clean forks, and reviewed/default-avoid transfer. | Framework behavior satisfied, solver improvement not satisfied |
| Context signal density improves without hiding research objects | core reviews F4; roadmap W4 | Hypothesis prompts now use mechanism-level distilled cross-branch maps, bounded runtime feedback, source visibility summaries, opportunity summaries, and evidence commitments. | Partially satisfied |
| warehouse remains a positive effective-research control | roadmap M2.5; current-state | Warehouse v2 positive-control root is valid/complete/postrun-ready and plateau-review ready with deep focused follow-up. | Satisfied as framework evidence |
| v0.5 is for controlled experiment matrices, not continued instrument repair | roadmap §0.5, W2-W4 | `TASK.md` previously blurred this by making governance on/off a v0.4 step. This audit corrected the wording so v0.4 preregisters the design and v0.5 runs the matrix. | Corrected |

## Source Spot Checks

The audit checked the following current source areas:

- `scion/scion/core/decision.py`
- `scion/scion/core/features.py`
- `scion/scion/core/scheduler.py`
- `scion/scion/protocol/gates.py`
- `scion/scion/config/protocol_config.py`
- `scion/scion/measurement/`
- `scion/tools/calibrate_aa_noise.py`
- `scion/scion/problems/cvrp/research_guidance.py`
- `scion/scion/problems/cvrp/successor_evidence_catalog.py`
- `scion/scion/problems/cvrp/opportunity.py`
- `scion/scion/problems/cvrp/postrun_handoff.py`
- `scion/scion/problems/warehouse_delivery/`
- `scion/scion/tests/unit/test_v3_problem_boundary_no_cvrp_terms_in_generic_layers.py`

The checked implementation shape is consistent with v3: generic code handles
schemas, deterministic routing, rendering, redaction, scheduling, and
readiness; problem packages own CVRP/warehouse semantics.

## TASK.md Alignment

`TASK.md` correctly reflects the three audit documents in these ways:

- it treats v3 as the boundary authority;
- it makes measurement proof and A/A/MDE interpretation a v0.4 obligation;
- it keeps CVRP/warehouse semantics problem-owned;
- it defines effective research as continuation, rejection, transfer, and
  branch learning, not promotion-only;
- it requires CVRP evidence to be interpreted against MDE and case variance;
- it keeps warehouse as the positive-control / plateau-review reference;
- it requires focused validation and status updates for repairs.

However, `TASK.md` is no longer a good operational task file in its current
size. It mixes phase gates, current status, detailed run history, repair notes,
and repeated experiment records. That conflicts with the current-state policy
that status docs should not become a run log.

Recommended cleanup:

- keep only current phase gates, acceptance criteria, and the next 3-5 actions
  in `TASK.md`;
- move completed run chronology to focused experiment reports and
  `docs/status/v0.4-history.md` milestones;
- keep this audit report as the current cross-document basis check;
- preserve exact artifact paths only in focused reports or current-state when
  they are needed for resuming work.

## Remaining Gaps Before v0.4 Closeout

1. **Warehouse calibration artifact mismatch.**
   Both warehouse spec copies,
   `scion/problems/warehouse_delivery/problem-v1.yaml` and
   `scion/scion/problems/warehouse_delivery/problem-v1.yaml`, reference
   `calibration/aa_noise_floor.json`, but this checkout has no checked-in file
   under either corresponding `calibration/` directory. Either restore the
   artifact, point both specs at the correct checked-in artifact, or document
   why warehouse calibration is intentionally external.

2. **CVRP solver improvement remains open.**
   Successor18b verifies framework behavior but remains solver-negative:
   `granular_savings_seed_portfolio` is below MDE and
   `exact_short_route_polish` is loss-heavy. The next CVRP slot should
   clean-fork to a materially different problem-owned causal path or explicitly
   repair `seed_post_optimization_selector` activation.

3. **TASK.md and current-state need compaction.**
   `TASK.md` is over 2000 lines and `current-state.md` is at the 1000-line risk
   boundary. Reduce them after this audit. Keep audit-relevant acceptance
   criteria and the active snapshot; move history out.

4. **Large-file risk needs design-first modularization.**
   Several production files exceed 1000 lines, including
   `core/branch_step_runner.py`, `core/decision_finalizer.py`,
   `core/research_efficiency_report.py`, `proposal/engine/hypothesis_prompts.py`,
   `proposal/context/cross_branch_research_support.py`,
   `problems/cvrp/solver_design_provider.py`, and large postrun tools.
   This is manageable for v0.4 only if new behavior stops accumulating there
   and future changes split named ports/providers instead of adding helpers.

5. **v0.5 governance experiments should not start under v0.4 debt.**
   v0.4 should preregister the comparison design and prove repaired execution.
   The broad governance on/off matrix belongs to v0.5.

## Recommended Next Order

1. Restore or explicitly resolve the warehouse calibration artifact mismatch.
2. Compact `TASK.md` into an operational task source.
3. Continue one CVRP run from the current guidance: clean fork to a
   non-reviewed causal path or seed-post activation repair.
4. Do a lightweight large-file modularization design note before further
   touching oversized core/postrun/proposal files.
5. Prepare, but do not run, the v0.5 governance ablation preregistration.
