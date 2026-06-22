# CVRP Next-Local Default-Avoid Loop

Date: 2026-06-22

This report records the immediate CVRP follow-up after the completed forced
local-search postrun. The purpose was to resume from that evidence, keep the
target forced to `policies/baseline_modules/local_search.py`, and verify that
the new launcher focus would prevent repeats of rejected local-search
mechanisms.

## Run

- WSL root:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-nextlocal-6f40ebcb-postforcedlocal-4r-gpt55-20260622T122048Z-claw`
- Local mirror:
  `/home/clawd/research/scion-experiments/v04-cvrp-nextlocal-6f40ebcb-postforcedlocal-4r-gpt55-20260622T122048Z-claw`
- WSL commit: `6f40ebcb`
- Resume source:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-forced-local-eb2627e5-postroutepressure-4r-gpt55-20260622T081704Z-claw/campaign`
- Forced target:
  `--force-surface solver_design --force-action modify --force-target-file policies/baseline_modules/local_search.py`
- Strict launch readiness: `launch_ready=true`; completion preflight was
  healthy and authenticated; prepared default-avoid count was `18`.

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

The three blocked attempts were all default-avoid hits:

1. `pure ALNS/no-polish`
2. `cross-route 2-opt reconnect`
3. `unchanged bounded_interroute_2opt_bridge local-search bridge`

## Interpretation

The new guard worked: the third attempt proves that the follow-up
`bounded_interroute_2opt_bridge` default-avoid entry reaches schema preview and
blocks a repeated rejected mechanism before Protocol rows.

The agent behavior is still not good enough: even with the target forced to
`local_search.py`, it spent all proposal attempts on default-avoid mechanisms
and never produced a materially different local-search or destroy/repair causal
path. This is not solver evidence and not a current-run-ready research result.

Operational conclusion: do not relaunch the same prepared focus unchanged. The
next repair should strengthen positive target selection around a specific
allowed mechanism direction, especially the still-untried deadline-aware
large-instance intra-route two-opt seed, while keeping the existing
default-avoid guard as a pre-Protocol waste stopper.

## Follow-up Repair

The launcher focus now promotes that seed from optional guidance to an explicit
prepared direction:

- `next_required_direction` requires the first attempt to target
  `large_instance_intra_route_two_opt_seed` as a deadline-aware bounded
  local-search mechanism in `policies/baseline_modules/local_search.py`.
- The current question no longer offers a broad "select another materially
  different mechanism" escape inside the same prepared focus.
- Prepared prompt-context readiness now checks that
  `next_required_direction` is projected into proposal prompts; this remains
  launch/handoff evidence only and is excluded from Decision, Protocol,
  scheduler, promotion, and solver semantics.
