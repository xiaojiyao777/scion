# CVRP Route-Merge Target-Intent Guidance Injection Repair

Date: 2026-06-18

Repair commit target: after `ce2fa45`

## Problem

The `ce2fa45` rerun was stopped early at:

- WSL:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-routemerge-guarded-agentic-1r-ce2fa45-20260618T003034Z`
- Server:
  `/home/clawd/research/scion-experiments/v04-cvrp-routemerge-guarded-agentic-1r-ce2fa45-20260618T003034Z`

It again selected `policies/baseline_modules/destroy_repair.py` but renamed the
mechanism to `route_limit_aware_repair`. This was not accepted as a valid
same-mechanism rerun.

The important diagnosis is that the added CVRP provider target-intent guidance
was present in the copied champion provider snapshot, but absent from the live
`hypothesis_target_intent` prompt. The live prompt path only injected
solver-design target-intent guidance when `forced_surface`,
`active_problem_boundary_surfaces`, or `operator_categories` contained
`solver_design`. In the real WSL run those fields were empty even though
`research_surfaces` declared `solver_design`.

## Repair

The target-intent solver-design context detector now also checks:

- `research_surfaces`
- `targetable_files`

This keeps the repair generic to solver-design prompt plumbing while preserving
CVRP-specific guidance in the CVRP provider. It does not change Decision,
Protocol, lifecycle, promotion, or `DecisionFeatures`.

## Acceptance

Focused tests now cover the realistic sanitized target-intent path where
`research_surfaces` is the only field proving the request is solver-design.

Verification:

```bash
/home/clawd/miniconda3/envs/claw/bin/python -m pytest \
  scion/scion/tests/unit/test_agentic_solver_design_prompt_payloads.py \
  scion/scion/tests/unit/test_cvrp_solver_design_provider.py -q
```

Result: `46 passed`.

Additional checks:

- Python compile on touched prompt/provider/test files passed.
- `git diff --check` passed.

## Next Action

Rerun the short WSL CVRP field check after this repair. The first acceptance
condition is prompt/agent behavior: target-intent, hypothesis, and code must
stay on `policies/baseline_modules/destroy_repair.py` and mechanism
`route_merge_repair`. Screening quality should only be interpreted after that
steering condition holds.
