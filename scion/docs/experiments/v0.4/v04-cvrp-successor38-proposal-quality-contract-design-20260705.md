# CVRP successor38 proposal-quality contract design

Date: 2026-07-05

## Purpose

Successor37 showed that CVRP proposals can complete the LLM, verification, and
screening path while still selecting weak hypotheses. The issue is not model
availability, protocol thresholds, or WSL capacity. The issue is that material
difference, direct mechanism effect, and CMT2/CMT4 protection were visible as
prompt narrative but not enforced as a proposal-side contract before code
generation.

This repair must happen before launching the next CVRP clean-fork experiment.

## Boundary

Keep the repair problem-owned:

- CVRP-specific proposal quality lives under
  `scion/problems/cvrp/proposal_quality/`.
- `CvrpAdapter.validate_hypothesis_quality()` delegates to that package.
- Generic proposal pipeline, protocol gates, lifecycle decisions, and
  `DecisionFeatures` remain problem-neutral.
- Rejections are proposal-only `agent_quality_blocked` artifacts and remain
  excluded from Decision features.

Do not continue adding CVRP rule branches directly to `adapter.py`.

## Contract

For `change_locus == "solver_design"`, the CVRP hypothesis-quality gate must
fail closed unless the proposal has a structured causal-path contract:

1. At least one concrete `mechanism_changes[].id`.
2. A non-empty `material_difference` record with changed/contrasted dimensions
   or evidence-status deltas, not only prose.
3. `expected_telemetry.effect` evidence that names the declared mechanism id or
   uses mechanism-specific effect paths.
4. Structured CMT2/CMT4 protection evidence in `branch_lesson_usage`, preferably
   under `clean_fork_diversity_claim`, with compatibility for explicit
   `protected_cases`, `protected_case_plan`, `case_protection`, or
   `protection_plan` fields.
5. Exact reviewed/default-avoid mechanism ids from successor37 remain blocked:
   `route_angle_aware_2opt_star` and `edge_frequency_penalty_repair`.

Prepared successor32 and successor36 focus guards remain intact. They are
special required-mechanism runs and should keep their current behavior.

## Rejection Shape

Every rejection should include:

- `agent_block_reason=agent_quality_blocked`
- `decision_features_excluded=True`
- a stable `gate_name`
- a stable failure code
- selected mechanism ids
- missing contract fields
- a retry constraint telling the agent to redraft a materially different
  CVRP-owned causal path with direct objective-effect telemetry and CMT2/CMT4
  protection before code generation

## Acceptance Tests

The repair is acceptable when tests cover:

- missing mechanism id blocks;
- missing `material_difference` blocks;
- missing direct effect telemetry blocks;
- missing CMT2/CMT4 protection blocks;
- a well-formed distinct mechanism passes;
- successor32/36 focus behavior still works;
- successor37 exact default-avoid mechanisms still block.

After this passes, launch the next server-local 2-round CVRP clean fork. Do not
move to WSL or long/concurrent runs until a candidate passes this repaired
proposal-quality filter and produces screening evidence worth scaling.
