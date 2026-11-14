# CVRP Route-Merge Pivot Guidance Repair

Date: 2026-06-18
Branch: `codex/v04-evidence-repair-plan`

## Purpose

The last CVRP field checks proved that Scion can steer, evaluate, continue, and
reject `route_merge_repair` branches with evidence, but they also showed a
research-loop failure: static CVRP provider text still pulled the agent back
toward another route-merge absorption/guarded-v2 variant after repeated
low-effect evidence.

This repair changes only problem-owned proposal guidance. It does not change
Decision, Protocol, lifecycle gates, promotion rules, generic budgets, or
`DecisionFeatures`.

## Change

- `CvrpSolverDesignProvider.solver_design_hypothesis_guidance()` now presents
  the route-merge branch as a plateau lesson rather than the default next
  mechanism.
- `CvrpSolverDesignProvider.solver_design_target_intent_guidance()` now tells
  target-intent to choose `route_merge_repair` only when it can name a new
  causal path beyond tested guarded-v2 / pressure-material-gain absorption.
- Otherwise, the provider asks the agent to pivot to a materially different
  problem-owned solver-design lever: construction diversity, destroy selection,
  local-search move scheduling, acceptance/temperature policy, or stable
  algorithm entrypoint integration.

## Acceptance

- `PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion pytest -q scion/scion/tests/unit/test_cvrp_solver_design_provider.py scion/scion/tests/unit/test_agentic_solver_design_prompt_payloads.py scion/scion/tests/unit/test_hypothesis_context_profiles.py`
  - Result: `61 passed`.
- `PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion python -m py_compile scion/scion/problems/cvrp/solver_design_provider.py scion/scion/tests/unit/test_cvrp_solver_design_provider.py scion/scion/tests/unit/test_agentic_solver_design_prompt_payloads.py`
  - Result: passed.

## Next Field Check

Run a short WSL CVRP target-intent/proposal check from this commit. Acceptance
is not promotion. Acceptance is that live traces either pivot away from
route-merge absorption or explicitly justify a genuinely new route-merge causal
path that is not another local absorption refinement.
