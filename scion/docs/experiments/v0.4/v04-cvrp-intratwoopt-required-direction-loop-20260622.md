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
hypothesis generation, not only schema-preview retry. The follow-up repair
projected the required id into the target-intent prompt and host-rebinds a
non-required selected preflight mechanism id to the prepared id before target
binding.

## Target-Intent Required-Id Follow-up

A third follow-up WSL launch tested that target-intent repair:

- WSL root:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-targetintent-7382a090-postdrift-4r-gpt55-4r-gpt55-20260622T133014Z-claw`
- Local mirror:
  `/home/clawd/research/scion-experiments/v04-cvrp-targetintent-7382a090-postdrift-4r-gpt55-4r-gpt55-20260622T133014Z-claw`
- WSL commit: `7382a090`
- Strict launch readiness passed with no required blockers and healthy
  completion preflight.

The run failed closed before Protocol rows:

- `run_validity_status=invalid_no_effective_rounds`
- `run_completeness_status=interrupted_incomplete`
- `last_stop_reason=repeated_quality_block_signature`
- 0 effective rounds
- 0 screening rows
- 3 proposal quality blocks
- campaign wrapper exit `0`
- wrapper effective exit `64`
- `postrun_acceptance_status=failed`

This root validates the target-intent repair but is still not solver evidence.
Current target-intent sessions selected
`large_instance_intra_route_two_opt_seed`, and formal binding stayed aligned
instead of failing with `target_intent_binding_mismatch`.

The remaining blocker is a default-avoid false positive. The formal hypothesis
was deadline-aware, referenced `context.remaining_time()`, and contrasted
itself against an unbounded fallback, but the default-avoid matcher treated the
contrast text as matching the prepared avoid direction
`unbounded large-instance two-opt fallback without deadline...`. The follow-up
local repair narrows only this unbounded/deadline avoid shape so candidates
with positive deadline scope (`deadline-aware`, `remaining_time`, `wall-clock`,
or bounded+deadline evidence) are not rejected as the forbidden unbounded
fallback.

A fourth follow-up WSL launch tested the deadline-scope matcher repair:

- WSL root:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-deadlinescope-76d02567-postavoidfp-4r-gpt55-4r-gpt55-20260622T134246Z-claw`
- Local mirror:
  `/home/clawd/research/scion-experiments/v04-cvrp-deadlinescope-76d02567-postavoidfp-4r-gpt55-4r-gpt55-20260622T134246Z-claw`
- WSL commit: `76d02567`
- Strict launch readiness passed with no required blockers and healthy
  completion preflight.

The run still failed closed before Protocol rows:

- `run_validity_status=invalid_no_effective_rounds`
- `run_completeness_status=interrupted_incomplete`
- `last_stop_reason=repeated_quality_block_signature`
- 0 effective rounds
- 0 screening rows
- 3 proposal quality blocks
- campaign wrapper exit `0`
- wrapper effective exit `64`
- `postrun_acceptance_status=failed`

This root validates the deadline-scope repair but is still not solver
evidence. Current target-intent/formal hypotheses stayed aligned on
`large_instance_intra_route_two_opt_seed`, and the previous
unbounded/no-deadline fallback false positive did not recur.

The remaining blocker is a second default-avoid false positive. The failed
formal hypotheses declared the required mechanism id, but branch-lesson
contrast fields mentioned `route_merge` or `cross_route` as excluded families.
The guard then accepted weak overlap through generic identity tokens such as
`route` and `opt` as enough evidence that the proposal matched
`route-merge absorption` or `cross-route 2-opt reconnect`. The follow-up local
repair narrows multi-token default-avoid phrase/fallback matching so a match
requires non-weak candidate identity support; actual route-merge style
mechanism ids still fail the guard, while the required same-route two-opt seed
can proceed to code generation.

## Identity-Supported Default-Avoid Follow-up

A fifth follow-up WSL launch tested that weak-identity default-avoid repair:

- WSL root:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-avoididentity-f80d990f-postweakid-4r-gpt55-4r-gpt55-20260622T144637Z-claw`
- Local mirror:
  `/home/clawd/research/scion-experiments/v04-cvrp-avoididentity-f80d990f-postweakid-4r-gpt55-4r-gpt55-20260622T144637Z-claw`
- WSL commit: `f80d990f`
- Strict launch readiness passed, and postrun acceptance reported `ready`.

The run finished naturally:

- `run_validity_status=valid`
- `run_completeness_status=complete`
- `last_stop_reason=max_rounds_exhausted`
- wrapper exit `0`
- 4 effective screening rounds
- 4 protocol metric rows
- 0 quality blocks and 0 proposal quality blocks
- 0 promotions; champion remained `v1`

This root validates the default-avoid identity repair. The required
`large_instance_intra_route_two_opt_seed` direction crossed hypothesis,
target-intent, code generation, smoke, and Protocol. It is current-run-ready
effective negative research, not solver improvement.

The dense candidate branch `1d630ce3-fe33-4083-8769-3d3c573e207d` implemented a
large-instance intra-route two-opt seed operator in `local_search.py` and wired
it into the default VNS path. The first 32-pair screen had direct mechanism
telemetry and expanded; the 48-pair expansion retained direct telemetry
(`large_instance_intra_route_two_opt_seed` phase observed on 40/48 candidate
runs) and failed closed: 0 case wins, 4 losses, 8 ties, pair result 9/14/25,
median delta `0`, CI `[-0.5, 0]`. It was correctly abandoned.

The sparse refinement branch `ec052599-281d-40fc-9d8f-639b452904b3` exposed a
framework feedback bug. It changed the sparse intra-route two-opt polish path
and produced pair-level tie noise (32-pair row: 2/0/30 pair result; 48-pair
row: 2/0/46 pair result), but raw metrics showed the declared primary
mechanism was not evaluated or triggered:

- `metrics/5914c858-d77c-44f2-99af-1e27a4f6baf4.json`: every declared
  `large_instance_intra_route_two_opt_seed` activation/runtime/effect field was
  missing across 32 candidate runs.
- `metrics/8a325037-728a-4965-8f15-a6160c7519e1.json`: the same declared
  fields were missing across 48 candidate runs.
- Candidate phase buckets contained `alns_core`, `construction`,
  `vns_embedded`, and `vns_initial`; no
  `large_instance_intra_route_two_opt_seed` bucket was present.

The old run nevertheless left the branch as `explore` / `weak_positive`
because `screening_feedback` treated a passed telemetry guard and pair-level
positive noise as activation. That interpretation is wrong for v0.4 effective
research: missing declared primary telemetry should be inactive feedback and a
repair/abandon signal, not evidence for same-mechanism continuation.

Follow-up repair:

- Local commit `e9ec3635`
  (`Treat missing primary telemetry as inactive feedback`)
- WSL commit `01b1abb4`
- Tests:
  - Local: `PYTHONPATH=scion pytest scion/scion/tests/unit/test_screening_feedback_tiers_memory.py -q` -> 9 passed.
  - Local: related feedback/protocol/decision/prompt regression set -> 217 passed.
  - WSL: `PYTHONPATH=scion /home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m pytest scion/scion/tests/unit/test_screening_feedback_tiers_memory.py -q` -> 9 passed.
  - WSL: related regression set -> 208 passed.

Operational conclusion: relaunch from `01b1abb4` or later. Do not treat the
stale `ec052599` weak-positive branch state from the `f80d990f` run as accepted
evidence unless a future patched run observes the declared primary mechanism.
