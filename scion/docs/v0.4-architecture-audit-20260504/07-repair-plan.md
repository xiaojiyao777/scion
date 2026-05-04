# Repair Plan

This plan is ordered to protect active experiments and formal-readiness interpretation. It assumes no source changes are made until the active runs are ready to be paused or post-audited.

## Repair Status As Of 2026-05-04

Completed in the first post-run repair pass:

- P0-1 formal CVRP `.vrp` baseline fail-closed.
- Post-run CVRP no-progress operator-loop break.
- Post-run context/evidence failure-cause rendering.
- Post-run CLI diagnostic `--disable-early-stop` mode.
- Post-run proposal-stage `StepRecord` evidence for Round-1 LLM/schema
  failures.

Still open:

- P0-2 frozen usage ledger.
- P0-3 formal readiness validator for final evidence refs.
- P1-1 strict runtime default for programmatic adapter campaigns.
- P1-2 further `campaign.py` composition cleanup.
- P1-3 broader static complexity guard.
- P1-4 route-native taxonomy and legacy fallback isolation.

## P0 Repairs

### P0-1: Make formal CVRP `.vrp` baseline fail closed

- Affected files: `scion/scion/problems/cvrp/solver.py`, `scion/scion/runtime/audit.py` if needed, `scion/scion/tests/test_cvrp_solver_vrp_smoke.py`, possibly `scion/scion/tests/test_cvrp_formal_readiness.py`
- Change:
  - Separate "baseline required" from "baseline root found".
  - For formal/data-root-relative `.vrp` cases, emit `baseline_required=True` before lookup.
  - Missing `vrp/src` or baseline exception must become solver failure or runtime audit failure.
  - Keep controlled synthetic fixtures explicitly allowed to use nearest-neighbor with `baseline_required=False`.
- Acceptance tests:
  - Formal `.vrp` with no `vrp/src` returns `baseline_runtime_error`.
  - Synthetic controlled `.vrp` still runs nearest-neighbor.
  - Protocol candidate required-baseline failure cannot pass screening/validation/frozen.

### P0-2: Enforce frozen holdout usage budget

- Affected files: `scion/scion/core/branch_step_runner.py`, `scion/scion/core/evaluation_orchestrator.py`, `scion/scion/core/campaign.py`, `scion/scion/core/models.py` or a new `core/frozen_budget.py`, branch/campaign persistence if needed, tests under `scion/scion/tests/unit/core/`
- Change:
  - Add campaign-level frozen usage ledger from `ProtocolConfig.frozen.max_uses_per_campaign`.
  - Increment on frozen evaluation attempt, not only success.
  - Block additional `READY_FROZEN`/`FROZEN_TESTING` work with deterministic reason code.
  - Persist usage in status/lineage.
- Acceptance tests:
  - Max uses 1 blocks second frozen branch.
  - Restart preserves used count.
  - Frozen-budget exhaustion is distinct from protocol/objective failure.

### P0-3: Add formal close/readiness validator for final evidence

- Affected files: new `scion/scion/evidence/formal_readiness.py` or `core/campaign_close.py`, `scion/scion/evidence/final_evidence_refs.py`, tests under `scion/scion/tests/unit/evidence/`, docs/readiness command if desired
- Change:
  - Keep final evaluation manual/post-campaign.
  - Validate top-level `final_evidence_refs` and all six artifact refs.
  - Record `formal_ready` status and missing reasons without mutating step schema.
- Acceptance tests:
  - No refs -> not ready.
  - Missing one artifact -> not ready.
  - Complete final package -> ready.

## P1 Repairs

### P1-1: Make runtime verification default for adapter-backed programmatic campaigns

- Affected files: `scion/scion/core/campaign.py`, maybe `scion/scion/core/problem_runtime.py`, `scion/scion/tests/unit/core/test_campaign_control_boundaries.py`
- Change:
  - If no `verification_gate` is provided and adapter is present, require a runner source.
  - If `experiment_protocol` exposes `runner`, construct strict runtime `VerificationGate`.
  - Otherwise fail construction for adapter production mode or require explicit compatibility opt-in.
- Acceptance tests:
  - Programmatic adapter+protocol construction executes runtime checks.
  - Missing runner fails closed unless compatibility mode is explicit.

### P1-2: Reduce `campaign.py` composition weight

- Affected files: `scion/scion/core/campaign.py`, new `scion/scion/core/campaign_factory.py` or equivalent
- Change:
  - Move dependency construction into explicit factories.
  - Replace callback clusters with typed collaborator/repository objects.
  - Keep public `CampaignManager` API stable.
- Acceptance tests:
  - Existing campaign tests stay green.
  - Factory unit test verifies service wiring and strict verification mode.

### P1-3: Broaden static complexity guard

- Affected files: `scion/scion/contract/gate.py`, `scion/scion/tests/test_contract.py`, possibly ProblemSpecV1 for adapter complexity policy
- Change:
  - Detect `permutations`, `product`, uncapped `while`, and high-depth loops over problem-scale collections.
  - Allow explicit bounded top-k/slice/range caps.
- Acceptance tests:
  - New slow operator families fail contract.
  - Existing valid bounded operators pass.

### P1-4: Isolate warehouse legacy fallbacks

- Affected files: `scion/scion/protocol/evaluation.py`, `scion/scion/protocol/experiment.py`, `scion/scion/proposal/search_memory.py`, `scion/scion/proposal/classifier.py`, `scion/scion/proposal/context_manager.py`, tests
- Change:
  - Require metric specs by default for adapter-backed protocols.
  - Mark warehouse fallback as explicit legacy mode.
  - Thread problem taxonomy into search memory/context classification.
- Acceptance tests:
  - Adapter-backed CVRP cannot evaluate through `subcategory_splits/total_cost`.
  - Warehouse legacy tests opt into legacy comparator.
  - CVRP search memory renders route-native families.

## P2 Repairs

### P2-1: Align runtime feedback threshold with protocol config

- Affected files: `scion/scion/proposal/context_manager.py`, `scion/scion/core/problem_runtime.py` or context setup code
- Change:
  - Pass `max_runtime_ratio` into runtime feedback extraction.
- Acceptance tests:
  - Rendered slow cases follow configured threshold.

### P2-2: Add artifact hashes for raw metrics/final refs

- Affected files: `scion/scion/core/evidence_recorder.py`, `scion/scion/evidence/final_evidence_refs.py`, tests
- Change:
  - Store content hashes for raw metrics refs and final evidence artifacts.
- Acceptance tests:
  - Hash in summary matches artifact content.

### P2-3: Clarify formal budget interpretation

- Affected files: docs and formal readiness tests
- Change:
  - Make readiness docs distinguish campaign solver budget from final evidence budget and from stage-specific budgets.
- Acceptance tests:
  - Formal budgets JSON and docs agree on stage/final time limits.

## Suggested Commit Order

1. P0-1 formal `.vrp` baseline fail-closed.
2. P0-2 frozen usage ledger.
3. P0-3 formal readiness validator for final evidence refs.
4. P1-1 strict runtime default for programmatic adapter campaigns.
5. P1-3 complexity guard expansion.
6. P1-4 legacy fallback isolation and taxonomy threading.
7. P1-2 campaign composition factory cleanup.
8. P2 polish items.

This order closes evidence validity before elegance refactors.
