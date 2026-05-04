# Scion v0.4 Architecture Audit - Executive Summary

Date: 2026-05-04
Branch reviewed: v0.4-dev
Scope: read-only architecture/code audit; only this audit directory was written.

## Overall Conclusion

Scion v0.4 has substantially advanced from the v0.3 framework: the CVRP adapter is real, runtime evidence is represented in protocol stats and `DecisionFeatures`, CLI-driven adapter campaigns use strict runtime verification, and `campaign.py` has moved most executable branch-step logic into services.

The current implementation is not yet fully closed against the v3/v0.4 target claim for formal CVRP validation. Three P0 gaps remain:

1. Formal `.vrp` baseline selection can still fail open to Scion nearest-neighbor mode when the intended `vrp/src` baseline is unavailable.
2. `FrozenConfig.max_uses_per_campaign` is configuration-only; no campaign-level holdout usage budget is consumed or enforced.
3. Final evidence refs are attachable metadata but not a formal campaign close/readiness condition.

The practical status is "controlled CVRP path implemented; formal-readiness governance incomplete." Active experiments should be treated as plumbing/readiness evidence until these P0 items are repaired and re-audited.

## Highest Priority Findings

### P0-1: Formal `.vrp` baseline fallback is not fail-closed

- Severity: P0
- Evidence: `scion/scion/problems/cvrp/solver.py:74-119`, `scion/scion/runtime/audit.py:97-105`, `scion/scion/tests/test_cvrp_solver_vrp_smoke.py:157-177`
- Impact: A formal `.vrp` campaign can run with `baseline_mode=scion_nearest_neighbor` and `baseline_required=False` when no configured data root exposes `vrp/src/solver.py`. The runtime audit only fails required baseline fallbacks when `baseline_required` is true, so a formal run can look successful while evaluating the wrong baseline.
- Recommendation: Make formal/data-root-relative `.vrp` runs explicitly require the external baseline. If the baseline root is missing or raises, either exit the solver with a failure or emit `baseline_required=True` plus a `baseline_error` that `runtime_audit_failure_from_runtime()` will veto.
- Suggested tests: Add a synthetic data-root-relative `.vrp` test with no `vrp/src` under `SCION_PROBLEM_DATA_ROOT` and assert `runtime_audit_failure_from_raw()` returns `baseline_runtime_error`; add a CLI/formal smoke that fails before promotion when required baseline is missing.

### P0-2: Frozen holdout usage budget is not enforced

- Severity: P0
- Evidence: `scion/scion/config/protocol_config.py:53-66`, `scion/scion/protocol/experiment.py:383-847`, `scion/scion/core/branch_step_runner.py:99-126`, `scion/scion/tests/test_config.py:74-106`
- Impact: v3 and v0.4 treat frozen holdout as scarce promotion evidence. The current code validates the `max_uses_per_campaign` field but does not count or block frozen evaluations at campaign level.
- Recommendation: Add a frozen-budget service or campaign counter that increments before/after `ExperimentStage.FROZEN`, blocks additional frozen scheduling once exhausted, persists the count in lineage/status, and distinguishes "frozen budget exhausted" from objective failure.
- Suggested tests: Configure `max_uses_per_campaign=1`, queue two frozen branches, assert the second never runs `run_experiment(FROZEN)` and receives a deterministic abandon/block reason; restart from branch store and assert the usage count survives.

### P0-3: Final evidence refs are optional, not a close/readiness condition

- Severity: P0
- Evidence: `scion/scion/core/evidence_recorder.py:171-174`, `scion/scion/core/evidence_recorder.py:420-424`, `scion/scion/core/campaign_loop.py:66-72`, `scion/scion/evidence/final_evidence_refs.py:61-70`
- Impact: Campaign summaries can close without `final_evidence_refs`. This preserves post-campaign manual evaluation, but it does not enforce the v0.4 formal claim that final quality/runtime evidence is a readiness condition.
- Recommendation: Keep final evaluation outside the loop, but add a formal close/readiness validator that checks `evidence_manifest.json`, final quality CSV/JSON, per-case quality, runtime summary, and failure summary refs before declaring formal readiness.
- Suggested tests: A campaign with no final evidence should be "campaign complete but formal_ready=false"; attaching a complete package should flip readiness; missing one artifact should fail readiness.

## Important P1 Findings

- `CampaignManager` default construction can still skip runtime verification unless callers pass a strict `VerificationGate`, even when an `ExperimentProtocol` with a runner is present (`scion/scion/core/campaign.py:185-193`, CLI strict path at `scion/scion/cli/main.py:181-197`).
- `campaign.py` is better but still a large composition and compatibility hub: 1196 lines, a 500-line constructor, many private compatibility wrappers, and callback-heavy service wiring.
- Runtime complexity governance is present but narrow: contract rejects high-order `itertools.combinations`, but not other common unbounded patterns such as permutations, cartesian products, full route-pair nested scans, or uncapped while loops.
- Problem boundary is mostly adapter-native for production, but warehouse-shaped legacy fallbacks and labels remain in protocol fallback comparison, search memory, classifier defaults, and legacy verification comments/paths.

## Implemented / Strong Areas

- Runtime facts are represented structurally in `EvalStats` and `DecisionFeatures`, with runtime vetoes in `DecisionEngine`.
- Validation/frozen protocol exposure strips per-case feedback and preserves aggregate runtime counts.
- CVRP adapter recomputes consistency, feasibility, and objective rather than trusting solver output.
- BKS/gap is kept in final evidence paths rather than campaign promotion objective.
- CLI-driven adapter campaigns construct strict runtime verification and require adapter-backed runtime checks.
- Controlled CVRP smoke tests exercise screening -> validation -> frozen -> promote and final evidence attachment.

## Actual Review Scope

Read and reviewed required v3/v0.4 design docs, current-state/worklog docs, core campaign services, runtime/protocol/verification/proposal code, ProblemSpecV1/bridge, CVRP adapter/solver/parser/formal assets, final evidence modules, warehouse adapter boundary, and relevant tests. I did not open or read raw `vrp/cvrplib/**` benchmark instance files.
