# CVRP successor36 seed-post selector quality-block postrun

Date: 2026-07-05

## Run

Root:
`/home/clawd/research/scion-experiments/v04-cvrp-successor36-seed-post-optimization-selector-activation-server-clean-2r-gpt55-20260705T081741Z-claw`

Status:

- `status=finished`
- `run_validity_status=invalid_no_effective_rounds`
- `run_completeness_status=interrupted_incomplete`
- `completed_requested_rounds=false`
- `campaign_exit_status=incomplete`
- `last_stop_reason=repeated_quality_block_signature`
- `postrun_acceptance_status=failed`
- `wrapper_exit_status=64`

The launcher reached campaign execution and the completion preflight against
local `gpt-5.5` succeeded. No protocol row reached screening, validation, or
frozen, so this run is not solver evidence.

## Evidence Summary

The campaign consumed three proposal attempts and all three were blocked by the
same proposal-quality signature before verification/protocol metrics:

`agent_quality_blocked:cvrp_construction_seed_direct_effect_missing`

Postrun research-efficiency counters:

- `proposal_attempts_consumed=3`
- `proposal_attempts_total=3`
- `proposal_quality_blocks=3`
- `effective_protocol_rounds=0`
- `protocol_evaluated_candidates=0`
- `protocol_metric_results=0`
- `protocol_effects_vs_mde.interpretation=no_protocol_rows`

The failures report recorded `total_failures=0`; the useful taxonomy signal is
proposal quality, not model/tool/solver failure.

## Trace Audit

The three code traces all targeted the intended primary file,
`policies/baseline_modules/seed_selector.py`, and each included minimal
`policies/baseline_modules/scheduler.py` integration in `additional_changes`.

Each generated `seed_selector.py` candidate also recorded same-mechanism direct
effect telemetry inside the new module, for example:

`context.record_move(_SELECTOR_PHASE, attempted=..., accepted=..., delta=..., best_improved=...)`

or the equivalent `_MECHANISM` alias, where the alias value was the approved
`seed_post_optimization_selector` mechanism id.

The static CVRP construction-seed quality check was still scanning only:

- `policies/baseline_modules/construction.py`
- `policies/baseline_modules/scheduler.py`
- `policies/baseline_algorithm.py`

It did not include the newly promoted successor36 module path,
`policies/baseline_modules/seed_selector.py`. As a result, it missed legitimate
module-owned direct effect telemetry and incorrectly classified the proposals
as activation-only.

## Decision

Classify this successor36 root as a static-quality recognizer boundary gap, not
as solver-negative evidence and not as a model-call failure.

The direct-effect requirement remains correct and should not be relaxed. The
repair is to make the recognizer understand the successor36 module boundary:
`seed_selector.py` is a construction seed selector module, while scheduler.py
should remain minimal construction-boundary wiring.

## Repair

The current checkout repairs the CVRP static smoke check by including
`policies/baseline_modules/seed_selector.py` in construction seed patch paths.

Regression tests added:

- activation-only telemetry in `seed_selector.py` remains blocked;
- direct `record_move(..., delta=...)` telemetry in `seed_selector.py` via a
  local mechanism-id alias is accepted.

Validation:

- `/home/clawd/miniconda3/envs/claw/bin/python -m pytest scion/scion/tests/unit/test_cvrp_solver_design_provider.py -q`
- `/home/clawd/miniconda3/envs/claw/bin/python -m pytest scion/scion/tests/test_cvrp_agentic_launcher.py scion/scion/tests/unit/test_agentic_solver_design_prompt_payloads.py -q`
- `git diff --check`

## Next Direction

Relaunch as successor36b after committing the recognizer repair. Keep the same
research design:

- force `solver_design`;
- force `create_new`;
- force `policies/baseline_modules/seed_selector.py`;
- require direct pre-ALNS/VNS selected-seed-versus-baseline objective effect
  telemetry under `seed_post_optimization_selector`;
- keep scheduler edits to minimal construction-boundary integration.
