# CVRP Intra-Two-Opt Required-Direction Loop

Date: 2026-06-22

This report records the CVRP follow-up after adding an explicit
`next_required_direction` to the prepared launcher focus. The purpose was to
test whether naming the still-untried
`large_instance_intra_route_two_opt_seed` as the next prepared direction was
enough to move the agent away from default-avoid local-search loops.

## Run

- WSL root:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-intratwoopt-4b7e78b7-postavoidloop-4r-gpt55-20260622T123924Z-claw`
- Local mirror:
  `/home/clawd/research/scion-experiments/v04-cvrp-intratwoopt-4b7e78b7-postavoidloop-4r-gpt55-20260622T123924Z-claw`
- WSL commit: `4b7e78b7`
- Resume source:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-forced-local-eb2627e5-postroutepressure-4r-gpt55-20260622T081704Z-claw/campaign`
- Forced target:
  `--force-surface solver_design --force-action modify --force-target-file policies/baseline_modules/local_search.py`
- Strict launch readiness passed with `launch_ready=true`, authenticated
  completion preflight, clean runtime guard, and
  `cvrp_next_required_direction_present=true` in prepared prompt-context
  readiness.

## Result

The run failed closed before Protocol rows:

- `run_validity_status=invalid_no_effective_rounds`
- `run_completeness_status=interrupted_incomplete`
- `last_stop_reason=circuit_breaker`
- 0 effective rounds
- 0 screening rows
- 3 proposal quality blocks
- `wrapper_exit_status=64`
- `postrun_acceptance_status=failed`
- `postrun_readiness_exit_status=64`

The three blocked proposal attempts were default-avoid repeats:

1. unchanged `bounded_interroute_2opt_bridge`
2. `cross-route 2-opt reconnect`
3. unchanged `bounded_interroute_2opt_bridge`

## Interpretation

The prepared prompt carried the positive direction, but the agent still did not
declare or attempt the required large-instance two-opt seed. Natural-language
positive focus is therefore insufficient for this CVRP control problem.

This is not solver evidence and not a current-run-ready research result. It is
evidence that the next control repair must make the required mechanism
structured and machine-checked before code generation.

## Follow-up Repair

The launcher focus now exposes
`required_mechanism_ids=["large_instance_intra_route_two_opt_seed"]`, and
`proposal.schema_preview` checks that the hypothesis declares one of those ids
in `mechanism_changes`. This remains proposal-only launch guidance and is
excluded from Decision, Protocol, scheduler, promotion, and solver semantics.

## Required-Mechanism Guard Follow-up

A follow-up WSL launch tested the structured guard:

- WSL root:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-requiredmech-1e4c2dde-postintratwoopt-4r-gpt55-20260622T124949Z-claw`
- Local mirror:
  `/home/clawd/research/scion-experiments/v04-cvrp-requiredmech-1e4c2dde-postintratwoopt-4r-gpt55-20260622T124949Z-claw`
- WSL commit: `1e4c2dde`
- Strict launch readiness passed.

The run failed closed before Protocol rows:

- `run_validity_status=invalid_no_effective_rounds`
- `run_completeness_status=interrupted_incomplete`
- `last_stop_reason=repeated_quality_block_signature`
- 0 effective rounds
- 0 screening rows
- 3 proposal quality blocks
- `wrapper_exit_status=64`
- `postrun_acceptance_status=failed`

All three proposal attempts were blocked by
`launch_research_focus_required_mechanism`. This proves the schema-preview
guard is wired and fail-closed, but it is still not solver evidence: the agent
never generated a formal candidate or Protocol row.

The root exposed a second repair point. The guard payload contained the full
required id and retry constraint, but the agentic hypothesis session did not
convert that guard into in-session schema retry feedback, so the outer
quality-block path only saw a truncated failure reason. The follow-up local
repair adds a launch-focus required-mechanism retry feedback path and prompt
projection that preserves full `required_mechanism_ids`, candidate ids, allowed
repair shape, and a retry rule allowing the previous mechanism id to be
replaced by the prepared required id.

## Required-Mechanism Retry Follow-up

A second follow-up WSL launch tested that retry-feedback repair:

- WSL root:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-requiredmechretry-f75cd321-postguard-4r-gpt55-4r-gpt55-20260622T130938Z-claw`
- Local mirror:
  `/home/clawd/research/scion-experiments/v04-cvrp-requiredmechretry-f75cd321-postguard-4r-gpt55-4r-gpt55-20260622T130938Z-claw`
- WSL commit: `f75cd321`
- Strict launch readiness passed with no required blockers.

The run again failed closed before Protocol rows:

- `run_validity_status=invalid_no_effective_rounds`
- `run_completeness_status=interrupted_incomplete`
- `last_stop_reason=circuit_breaker`
- 0 effective rounds
- 0 screening rows
- 3 proposal quality blocks
- wrapper effective exit `64`
- `postrun_acceptance_status=failed`

This root proved the retry-feedback path partially worked: the first two
formal hypotheses were rewritten to
`large_instance_intra_route_two_opt_seed`. They were still blocked before code
generation because target-intent preflight had selected different mechanism ids
(`intra_route_relocate_polish` and `capacity_slack_segment_exchange`), so the
target-intent binding gate correctly reported `target_intent_binding_mismatch`.
The third attempt omitted the required id again and was blocked by
`launch_research_focus_required_mechanism`.

Interpretation: this is not solver evidence. It exposes that prepared
`required_mechanism_ids` must bind target-intent preflight before formal
hypothesis generation, not only schema-preview retry. The current local repair
projects the required id into the target-intent prompt and host-rebinds a
non-required selected preflight mechanism id to the prepared id before target
binding.
