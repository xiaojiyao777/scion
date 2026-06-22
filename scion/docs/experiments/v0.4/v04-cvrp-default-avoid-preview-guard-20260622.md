# CVRP Default-Avoid Preview Guard

Date: 2026-06-22

This report records the first post route-pressure CVRP relaunch attempt after
the launcher marked rank-gap and route-pressure acceptance variants as
default-avoid directions. The attempt was intentionally stopped before Protocol
evaluation because the live proposal still selected an acceptance-family target.

## Run

- WSL root:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-nonaccept-443b1a51-postroutepressure-4r-gpt55-20260622T073501Z-claw`
- WSL commit: `443b1a51`
- Resume source:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-nextmech-1aae436c-postrankgap-4r-gpt55-20260622T041502Z-claw/campaign`
- Strict launch readiness passed before launch.
- The run was manually stopped after the first proposal attempt and before any
  protocol rows were produced.
- Campaign status after stop: `last_stop_reason=signal:SIGTERM`,
  `run_validity_status=invalid_no_experiments`,
  `run_completeness_status=interrupted_incomplete`, 0 effective rounds, and 0
  protocol-evaluated rows.

## Finding

Prompt-only default-avoid guidance was not enough. The prepared handoff told the
agent not to spend the next branch slot on rank-gap, route-pressure, or generic
acceptance/adaptive-weighting variants unless it supplied a new non-acceptance
causal path and direct objective-effect telemetry. The live proposal still
started an acceptance-family candidate:

- Target file: `policies/baseline_modules/acceptance.py`
- Mechanism id: `distance_scaled_sa_reheat`
- Hypothesis shape: distance-scaled simulated-annealing reheating.

The root is not evidence about CVRP solver quality. It is evidence about
proposal control: `launch_research_focus.default_avoid_directions` must be
enforced in the proposal preview/quality path, not only rendered in the prompt.

## Repair

The follow-up repair keeps the v3 boundary intact:

- `launch_research_focus` remains proposal-only context.
- `DecisionFeatures`, Protocol, scheduler state, promotion, and solver
  semantics do not consume the prepared focus payload.
- `proposal.schema_preview` now returns a structured
  `launch_research_focus_default_avoid_guard` result and fails the hypothesis
  preview when the candidate matches a prepared default-avoid direction.

Focused tests cover both the blocked acceptance-family case and a nonmatching
bounded local-search case.

## Next

After synchronizing the repair to WSL, prepare a fresh CVRP root from the new
commit and monitor the first hypothesis. The first live proposal should either
target bounded local search or another materially different non-acceptance
solver-design causal path. If it still proposes an acceptance-family target,
the run should fail at schema preview before consuming Protocol rows.
