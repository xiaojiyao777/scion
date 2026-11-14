# CVRP Successor26 Short-Horizon Seed Trajectory Selector Postrun - 2026-06-30

## Status

Successor26 did not produce a valid solver experiment.

- Run root:
  `/home/clawd/research/scion-experiments/v04-cvrp-successor26-short-horizon-seed-trajectory-selector-server-2r-gpt55-20260630T132452Z-claw`
- Git commit: `6896451f`
- Wrapper status: `finished`
- Wrapper exit status: `64`
- Run completeness: `interrupted_incomplete`
- Run validity: `invalid_no_effective_rounds`
- Stop reason: `repeated_quality_block_signature`
- Effective protocol rounds: `0`
- Protocol metric results: `0`
- Screening protocol results: `0`
- Proposal attempts total: `3`
- Proposal quality blocks: `3`
- Postrun reports: rebuilt
- Postrun readiness: failed

This is not evidence that `short_horizon_seed_trajectory_selector` is
solver-negative. No candidate reached Contract/Verification/Protocol screening.

## Environment

The server-local `claw` environment ran successfully through completion
preflight and campaign execution. Local `gpt-5.5` calls worked.

The earlier WSL attempt failed before campaign execution due HTTPS/TLS errors:

- WSL run root:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-successor26-short-horizon-seed-trajectory-selector-2r-gpt55-20260630T132127Z-claw`
- WSL wrapper exit status: `64`
- Preflight classification: `request_failed`
- HTTP status: `502`
- Detail: `tls handshake eof`

Treat the WSL attempt as an environment preflight failure, not campaign
evidence.

## What Happened

All three server-local proposal attempts were blocked by the same CVRP static
quality signature before any effective round:

`agent_quality_blocked:cvrp_construction_seed_direct_effect_missing`

The gate reported that patches for `short_horizon_seed_trajectory_selector`
were missing direct same-mechanism objective-effect attribution:

- required mechanism id:
  `short_horizon_seed_trajectory_selector`;
- required evidence:
  `context.record_move("short_horizon_seed_trajectory_selector", attempted=1,
  accepted=..., delta=..., best_improved=...)`;
- rejected pattern:
  activation/runtime/candidate telemetry without direct objective-effect
  attribution.

Postrun artifact families were present, but readiness failed because the run had
no effective rounds and no protocol metric rows.

## Interpretation

The quality gate did the right high-level job: it prevented a construction seed
trajectory claim from entering Protocol without direct effect telemetry.

The next step should not be another unchanged launch. First inspect whether the
candidate patch genuinely lacked `context.record_move(...)`, or whether the
static recognizer missed an equivalent call pattern such as a module-level
mechanism-id alias. If the recognizer is too narrow, repair the recognizer and
add focused tests. If the candidate genuinely omitted the call, tighten the
successor26b guidance so the required code shape is explicit before relaunch.

## Recommended Successor26b Gate Repair

Design before development:

- keep `short_horizon_seed_trajectory_selector` as the mechanism;
- keep target ownership in `policies/baseline_modules/scheduler.py`;
- do not relax direct-effect requirements;
- make the retry/template language explicitly require:
  `context.record_iteration("short_horizon_seed_trajectory_selector", 1)`,
  `context.record_phase("short_horizon_seed_trajectory_selector", elapsed_ms)`,
  and `context.record_move("short_horizon_seed_trajectory_selector",
  attempted=1, accepted=accepted_flag,
  delta=baseline_post_trajectory_distance -
  selected_post_trajectory_distance, best_improved=best_improved_flag)`;
- if static recognition is repaired, include tests for literal mechanism id and
  any accepted alias style;
- relaunch only after targeted tests pass.

Follow-up decision: use a static-quality recognizer repair plus clearer retry
language, not a relaxation of the construction-seed direct-effect gate. The
recognizer should accept module-level mechanism-id aliases used inside solver
class methods, while still rejecting dynamic local alias shadowing. The retry
language should describe same-run seed/trajectory-vs-baseline objective effect
so successor26b can record the short-horizon post-trajectory delta directly.

## Next Checkpoints

Completed follow-up:

- The recognizer/template-language repair was committed after targeted tests
  passed.
- Successor26b launched on the server-local `claw` runner with the same forced
  owner:
  `solver_design` / `modify` / `policies/baseline_modules/scheduler.py`.
- Successor26b completed as a valid two-row solver-negative run with no
  proposal-quality, telemetry, model-call, or postrun-readiness failure.

Follow-up report:

`scion/docs/experiments/v0.4/v04-cvrp-successor26b-short-horizon-seed-trajectory-selector-postrun-20260630.md`
