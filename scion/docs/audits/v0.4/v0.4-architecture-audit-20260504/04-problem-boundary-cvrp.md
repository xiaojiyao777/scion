# Problem Boundary and CVRP Adaptation Audit

## Summary

CVRP is implemented as a real problem package behind `ProblemAdapter`, with route-native models, `.json` and `.vrp` loading, solver output recomputation, registry operator execution, and final evidence support. The main CVRP-specific P0 is formal baseline fail-closed behavior.

Framework boundary quality is improved but not perfect: production adapter paths are generic, while legacy fallback modules still carry warehouse-shaped assumptions.

## Findings

### Finding PBC1: Formal `.vrp` baseline required/fail-closed logic is wrong

- Severity: P0
- Evidence: `baseline_required` is computed as `resolved.suffix.lower() == ".vrp" and baseline_root is not None` (`scion/scion/problems/cvrp/solver.py:74-77`). If no baseline root exists, the final fallback emits `baseline_required=False` (`scion/scion/problems/cvrp/solver.py:113-119`). The branch at `scion/scion/problems/cvrp/solver.py:103-111` is unreachable because `baseline_required` cannot be true when `baseline_root is None`. Runtime audit only fails baseline fallback when `baseline_required` is true (`scion/scion/runtime/audit.py:97-105`). Current synthetic data-root test asserts `.vrp` fallback is not required (`scion/scion/tests/test_cvrp_solver_vrp_smoke.py:157-177`).
- Impact: A formal data-root-relative `.vrp` run can silently use Scion nearest-neighbor mode and still be treated as successful evidence. This directly undermines formal CVRP claims.
- Recommendation: Determine required baseline from run mode/path provenance, not from whether the baseline root was found. For formal manifests/data-root-relative CVRPLIB paths, set `baseline_required=True` before lookup; if no `vrp/src/solver.py` exists, fail the run or emit a runtime audit failure.
- Suggested tests: `SCION_PROBLEM_DATA_ROOT` with `cvrplib/foo.vrp` but no `src/solver.py` should produce `baseline_required=True` and `baseline_runtime_error`; controlled synthetic fixtures should be explicitly marked `baseline_required=False`.

### Finding PBC2: CVRP adapter recomputes route consistency, feasibility, and objective

- Severity: Implemented
- Evidence: Adapter loads JSON and `.vrp` through `load_instance()` (`scion/scion/problems/cvrp/adapter.py:71-77`); deserializes and normalizes routes (`scion/scion/problems/cvrp/adapter.py:79-106`); checks duplicate/missing/unknown/depot/customer/objective fields (`scion/scion/problems/cvrp/adapter.py:108-151`); checks capacity (`scion/scion/problems/cvrp/adapter.py:153-168`); recomputes `fleet_violation`, `total_distance`, and `routes` (`scion/scion/problems/cvrp/adapter.py:170-186`).
- Impact: The adapter does not trust solver-reported feasibility or objective fields for promotion/runtime verification.
- Recommendation: Keep adapter recomputation as the only CVRP verification path.
- Suggested tests: Existing duplicate/missing/over-capacity/objective mismatch tests are appropriate; add a solver output with `feasible=true` but over-capacity routes to assert fail closed.

### Finding PBC3: CVRPLIB parser has the expected fail-closed boundary for supported input

- Severity: Implemented
- Evidence: Parser requires `NAME`, `DIMENSION`, `CAPACITY`, `EDGE_WEIGHT_TYPE`, coordinate/demand/depot sections (`scion/scion/problems/cvrp/cvrplib.py:29-60`); rejects non-`EUC_2D` (`scion/scion/problems/cvrp/cvrplib.py:37-42`); checks dimension and section id equality (`scion/scion/problems/cvrp/cvrplib.py:48-55`); parses sibling `.sol` as report-only BKS and route count (`scion/scion/problems/cvrp/cvrplib.py:76-97`).
- Impact: Adapter-owned `.vrp` parsing is controlled and synthetic-tested without reading raw CVRPLIB instances.
- Recommendation: Preserve the parser's narrow supported surface until formal runs require other CVRPLIB variants.
- Suggested tests: Existing synthetic tests are sufficient for EUC_2D; add explicit missing section and duplicate depot cases if not already covered.

### Finding PBC4: BKS/gap is kept out of promotion and operator acceptance

- Severity: Implemented
- Evidence: Operator acceptance compares only `fleet_violation` and `total_distance` (`scion/scion/problems/cvrp/solver.py:191-202`, `scion/scion/problems/cvrp/solver.py:529-541`); adapter objective excludes BKS/gap (`scion/scion/problems/cvrp/adapter.py:170-186`); formal readiness policy asserts BKS gap final-report-only (`scion/scion/tests/test_cvrp_formal_readiness.py:90-100`).
- Impact: Candidates cannot promote by manipulating BKS/gap fields.
- Recommendation: Add one promotion-level regression where candidate reports negative gap but objective recomputation ignores it.
- Suggested tests: Candidate output includes fake `gap_pct=-10`; protocol comparison remains driven by recomputed `fleet_violation,total_distance`.

### Finding PBC5: Legacy warehouse-shaped fallback remains reachable outside production metric-spec paths

- Severity: P1
- Evidence: Legacy `protocol/evaluation.py` compares `subcategory_splits` then `total_cost` (`scion/scion/protocol/evaluation.py:6-58`); `ExperimentProtocol._compare_objectives()` falls back to those warehouse metrics when no `metric_specs` are present (`scion/scion/protocol/experiment.py:201-230`); `ExperimentProtocol.__init__()` only raises when `require_metric_specs=True` (`scion/scion/protocol/experiment.py:142-162`).
- Impact: Production CLI with ProblemSpecV1 is protected because it passes metric specs and `require_metric_specs=True`, but programmatic or legacy runs can still evaluate non-warehouse problems through warehouse semantics.
- Recommendation: Make missing metric specs fail by default for adapter-backed problems. Keep the warehouse fallback behind an explicit `legacy_warehouse_objective=True` compatibility flag.
- Suggested tests: Adapter-backed CVRP `ExperimentProtocol` without metric specs should raise; explicit legacy warehouse flag should allow old tests.

### Finding PBC6: Search memory and classifier defaults remain warehouse-specific

- Severity: P2
- Evidence: Default classifier taxonomy uses subcategory/order/vehicle labels (`scion/scion/proposal/classifier.py:13-45`); `CampaignSearchMemory` mechanism extraction uses subcategory/order/vehicle labels and is constructed without a problem taxonomy at `scion/scion/core/campaign.py:284-285`; context-manager fallback mechanism keywords are also warehouse-shaped (`scion/scion/proposal/context_manager.py:1007-1029`).
- Impact: This does not feed deterministic promotion decisions, but proposal guidance and summaries can mislabel CVRP families as warehouse concepts unless ProblemSpecV1 taxonomy is threaded everywhere.
- Recommendation: Thread `ProblemSpecV1.family_taxonomy` into `CampaignSearchMemory` and context family extraction, and provide route-native CVRP default taxonomy.
- Suggested tests: CVRP hypothesis text about route-pair 2-opt should classify/render as CVRP route-family, not `generic` or warehouse labels.
