# v3 Boundary and Lifecycle Repair - 2026-05-21

This note records the repair pass following
`scion-code-audit-20260521-v3-alignment`.

## Scope

The pass addressed three v3-alignment items before any further short
experiments:

1. Problem semantics leaking into generic proposal/context prompts.
2. Generic telemetry guard code hardcoding CVRP solver-design runtime fields.
3. Branch lifecycle preserving regressive low-to-mid screening branches and
   treating validation telemetry repair as ordinary exploration.

## P0-A: Provider-Owned Solver-Design Guidance

- Generic proposal/schema/hypothesis prompts no longer carry CVRP, ALNS/VNS,
  `_ALNSVNSSolver`, `_Solution`, `_Route`, route-capacity, or CVRP objective
  telemetry examples.
- `ContextManager.build_code_context()` now carries the resolved
  solver-design prompt provider to rendering while prompt-manifest sanitization
  removes live provider/adapter/spec objects from persisted artifacts.
- CVRP-specific solver-design rules remain under the CVRP provider.
- A v3 generic-boundary sentinel test now scans generic layers for problem
  semantic leakage with a narrow documented allowlist.

## P0-B: Declared Telemetry Field Roles

- Research surface evidence now supports `runtime_field_roles`.
- Generic telemetry guard code consumes declared roles such as
  `mechanism_activation`, `mechanism_effect`, `objective_outcome`,
  `protected_outcome`, `aggregate_effect`, and `budget`.
- CVRP `solver_algorithm_*` field meanings moved to
  `scion/problems/cvrp/problem-v1.yaml`.
- Synthetic non-CVRP telemetry tests verify the guard can validate telemetry
  without any `solver_algorithm_*` field names.

## P1: Branch Lifecycle and Validation Telemetry

- `BranchLifecyclePolicy` now applies low-signal screening lifecycle checks
  across the `<0.5` win-rate region, not only `<0.3`.
- Candidate runtime failures, negative median delta, runtime slowdown, and high
  runtime regression can soft-abandon low-to-mid win-rate branches.
- `DecisionFinalizer` no longer preserves a workspace solely because
  `win_rate > 0`; preservation is tied to explicit non-regressive lifecycle
  reasons or telemetry repair.
- Validation telemetry activation-missing uses
  `VALIDATION_TELEMETRY_REPAIRABLE` and `validation_telemetry_repairable`
  attempt kind. Frozen telemetry failure fails closed.

## Validation

Main-session verification:

```text
P0-A targeted: 145 passed
P0-A full unit: 937 passed

P0-B targeted telemetry suite: 73 passed
P0-B full unit: 940 passed

P1 targeted lifecycle suite: 40 passed
P1 core unit: 149 passed
P1 full unit: 951 passed
```

No short experiment was run in this stage. The next step is a 3-round short
experiment with per-LLM-call analysis after the code changes are committed.
