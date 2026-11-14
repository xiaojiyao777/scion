# CVRP Construction Effect-Guidance Repair

Date: 2026-06-18
Branch: `codex/v04-evidence-repair-plan`

## Summary

The `acc21ba` construction-pivot field check proved that CVRP target guidance
could escape the rejected demand-slack, route-merge, local-search, and
destroy/repair defaults, but the selected `route_limit_seed_diversification`
mechanism only activated on `4/32` candidate runs and had missing direct effect
attribution. The previous provider lesson said a construction revisit must show
broader activation or direct seed-selection effect, but it did not state what
counts as causal effect evidence for a seed/portfolio mechanism.

This repair makes that expectation explicit in the CVRP problem-owned provider:
fallback construction activation and seed choice are activation/design evidence,
not objective effect. A construction seed/portfolio mechanism needs a same-run
candidate-vs-baseline seed comparison or an accepted delta recorded under the
declared mechanism id.

## Changes

- CVRP hypothesis guidance now says unchanged
  `route_limit_seed_diversification` must not be repeated and that direct
  construction seed effect requires a same-run candidate-vs-baseline seed
  comparison or same-mechanism accepted delta.
- CVRP target-intent guidance now requires construction revisit notes to use a
  same-run seed baseline or same-mechanism `context.record_move(..., delta=...)`
  instead of treating fallback activation as effect.
- CVRP solver-design code rules now tell agents how to instrument
  construction seed/portfolio mechanisms without confusing activation,
  seed-pool size, fallback use, or downstream ALNS/VNS improvement with direct
  construction effect.
- Provider and agentic prompt-payload tests now assert the new guidance is
  present on both direct provider output and sanitized provider-ref prompt
  paths.

## Boundary Check

This is CVRP provider guidance only. It does not change core
`DecisionFeatures`, protocol gates, budgets, lifecycle policy, runtime
compression, or generic telemetry validation. It does not add case-id, BKS,
seed, or split-membership hardcoding.

## Acceptance

Commands run from `/home/clawd/research/or-autoresearch-agent`:

```bash
PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion pytest -q scion/scion/tests/unit/test_cvrp_solver_design_provider.py -k "prompt_provider_owns_solver_design_specific_terms or hypothesis_guidance_exposes_route_merge_pivot_lessons or target_intent_guidance_prefers_pivot_after_route_merge_plateau"
PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion pytest -q scion/scion/tests/unit/test_agentic_solver_design_prompt_payloads.py -k "hypothesis_prompt_resolves_provider_from_ref or target_intent_prompt_resolves_provider_from_ref"
python -m py_compile scion/scion/problems/cvrp/solver_design_provider.py scion/scion/tests/unit/test_cvrp_solver_design_provider.py scion/scion/tests/unit/test_agentic_solver_design_prompt_payloads.py
PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion pytest -q scion/scion/tests/unit/test_cvrp_solver_design_provider.py
PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion pytest -q scion/scion/tests/unit/test_agentic_solver_design_prompt_payloads.py
git diff --check
```

Results:

- CVRP provider focused tests: `3 passed`
- Agentic prompt-payload focused tests: `2 passed`
- py_compile: passed
- CVRP provider file: `25 passed`
- Agentic prompt-payload file: `21 passed`
- `git diff --check`: passed

## Resume Use

After restoring a live `gpt-5.5` route, the next CVRP research slice should
still use launcher `--completion-preflight` and inspect live target-intent and
hypothesis traces. Construction is not forbidden, but a construction revisit
must now explain broader formal-surface activation or a same-run seed-effect
comparison with CMT2 protection. If that cannot be made concrete, pivot to a
different problem-owned solver-design owner.
