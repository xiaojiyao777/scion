# Tests And Ops

This file records coverage and operational gaps that make the v3 architecture harder to defend, even when the current CVRP path works.

## Finding TEST-P1-1 - Boundary Tests Do Not Cover Runtime/Protocol Telemetry

Severity: P1

Type: test gap.

Evidence:
- Existing boundary tests are useful:
  - `scion/scion/tests/test_contract_solver_design_provider.py:55-70` checks the generic C9e facade for CVRP solver terms.
  - `scion/scion/tests/unit/test_agentic_solver_design_active_tools.py:6-25` checks generic active solver snapshot code for CVRP mechanism tokens.
  - `scion/scion/tests/unit/test_research_surfaces_generic_context.py:100-120` checks generic context prompt terms.
- But runtime/protocol tests still encode `solver_algorithm_*` as generic behavior:
  - `scion/scion/tests/test_protocol_surface_runtime.py:367-407` asserts runtime summaries include `solver_algorithm_*` telemetry without a selected surface.
  - CVRP-specific runtime tests correctly use `solver_algorithm_*`, but there is no equivalent non-CVRP synthetic telemetry surface proving generic behavior is descriptor-driven.

Why this matters for v3:
- The strongest remaining boundary violation lives outside the modules currently protected by sentinel tests.
- Without a synthetic non-CVRP adapter, generic code can keep depending on CVRP-shaped telemetry and still pass.

Recommended fix:
- Add a synthetic problem/adapter fixture with a non-CVRP active algorithm surface and non-`solver_algorithm_*` telemetry.
- Extend boundary sentinel tests to generic runtime/protocol/proposal-smoke modules.
- Keep allowlists narrow and explicit for legacy compatibility code.

Suggested tests:
- Non-CVRP descriptor fields are summarized and audited.
- No generic module outside an allowlist mentions CVRP, ALNS, VNS, route, fleet, capacity, demand, `solver_algorithm_total_distance`, or `solver_algorithm_fleet_violation`.
- CVRP-specific tests remain under `problems/cvrp` or CVRP-named test files.

## Finding TEST-P2-1 - Large Test Files Reduce Reviewability

Severity: P2

Type: test architecture debt.

Evidence from current line counts:
- `scion/scion/tests/unit/test_cvrp_mechanism_novelty_provider.py`: 1155 lines.
- `scion/scion/tests/unit/test_mechanism_novelty.py`: 968 lines.
- `scion/scion/tests/unit/test_agentic_solver_design_algorithm_smoke.py`: 937 lines.
- `scion/scion/tests/unit/test_agentic_session_model_planner.py`: 872 lines.
- `scion/scion/tests/unit/core/test_retry_round_accounting.py`: 831 lines.
- `scion/scion/tests/unit/test_runtime_telemetry_guard.py`: 822 lines.

Why this matters:
- The large files concentrate many separate contracts in one place, making it harder to see whether a new test actually covers a v3 boundary or just reinforces current CVRP behavior.

Recommended fix:
- Split by contract:
  - active facts / prompt facts
  - semantic novelty false positives
  - telemetry declarations and guard summaries
  - retry/repair loop accounting
  - runtime/protocol descriptor behavior

Suggested tests:
- Preserve current tests, but split them before adding new boundary coverage so failures map to one contract.

## Finding OPS-P2-1 - Signal/Exit Observability Needs A First-Class Artifact

Severity: P2

Type: experiment/ops problem.

Evidence:
- CLI SIGTERM/SIGINT handling is present in `scion/scion/cli/commands/init_run.py:30-49`.
- Graceful stop status/summary writing is present in `scion/scion/core/campaign.py:238-252`.
- The runbook writes `exit.txt` through shell traps in `scion/docs/operations/experiment-runbook.zh.md:215-224`.
- Active launch scripts are only found under `scion/archive/run-scripts/`, so current runs can still omit `exit.txt` if launched manually.

Recommended fix:
- Add a CLI-managed exit artifact or check in a current launch wrapper.
- Make the runbook reference the checked artifact path.

Why this matters:
- Experiment termination evidence is part of the v3 audit trail. If it depends on a manually copied shell trap, the next stopped run can again lack an explicit exit reason.

Suggested tests:
- Unit or subprocess test for SIGTERM producing status and exit artifact.
- Runbook path validation for referenced scripts.

## Finding TEST-P2-2 - Current Verification Was Focused, Not Exhaustive

Severity: P2

Type: audit limitation.

Evidence:
- This audit ran a focused subset:
  - active algorithm facts prompt/tool tests
  - active solver design tools
  - runtime telemetry guard
  - decision finalizer lifecycle
  - contract solver-design provider
- Result: 43 passed.

Why this matters:
- The focused suite is enough to support the line-level audit conclusions.
- It is not a substitute for full CI before a production run or before refactoring runtime/protocol telemetry.

Recommended fix:
- Before the next code change touching CORE-P1-1, run the full unit suite plus targeted non-CVRP descriptor tests.
- Before another formal validation campaign, add the validation telemetry repair tests described in `03-proposal-gates-telemetry.md`.

Suggested tests:
- Add one meta-test that prints the current audit-focused suite list, so future reviewers can distinguish focused audit verification from full CI.
- Add a CI job or marker group for v3 boundary tests once TEST-P1-1 is implemented.

## Operational Readiness Summary

- Short CVRP screening run: no P0 blocker found.
- Formal validation run: resolve or consciously accept GATE-P1-1 first.
- Generic v3 framework claim or new non-CVRP adapter: resolve CORE-P1-1 and TEST-P1-1 first.
