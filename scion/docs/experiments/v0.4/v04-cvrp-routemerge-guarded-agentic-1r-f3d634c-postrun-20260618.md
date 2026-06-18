# CVRP Route-Merge Guarded Agentic Rerun Postrun

Date: 2026-06-18

## Purpose

This rerun field-checks the target-intent guidance-injection repair from commit
`f3d634c`. The first acceptance condition is steering, not solver quality:
target-intent, hypothesis, and code must stay on
`policies/baseline_modules/destroy_repair.py` and mechanism
`route_merge_repair`. Only after that condition holds is screening evidence
interpretable.

## Run

- Commit: `f3d634c`
- Branch: `codex/v04-evidence-repair-plan`
- WSL run root:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-routemerge-guarded-agentic-1r-f3d634c-pypath-20260618T004101Z`
- Server copy:
  `/home/clawd/research/scion-experiments/v04-cvrp-routemerge-guarded-agentic-1r-f3d634c-pypath-20260618T004101Z`
- Model: all seven LLM traces used `gpt-5.5`.
- Wrapper exit: `0`
- Campaign status: `complete`, `valid`, `completed_requested_rounds=true`
- Time: `2026-06-18T00:41:03Z` to `2026-06-18T01:15:48Z`

The WSL launch explicitly set:

```bash
export PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion
```

This is required. Earlier WSL checks without `PYTHONPATH` imported stale Scion
core modules from `/home/xjy-ubuntu/projects/scion/scion`, while problem files
came from the synchronized worktree. `launch_meta.txt` for this run confirms:

- `SCION_CLI=/home/xjy-ubuntu/research/or-autoresearch-agent/scion/scion/cli/main.py`
- `SCION_HYPOTHESIS_PROMPTS=/home/xjy-ubuntu/research/or-autoresearch-agent/scion/scion/proposal/engine/hypothesis_prompts.py`
- `OPENAI_VERSION=2.43.0`

## Steering Result

Accepted.

- Target-intent selected
  `policies/baseline_modules/destroy_repair.py` and mechanism
  `route_merge_repair`.
- Hypothesis preserved the same mechanism id:
  `mechanism_changes=[{"change_type": "modify", "id": "route_merge_repair"}]`.
- Code generation stayed in `destroy_repair.py`, with scheduler wiring only to
  call the repair operator.
- Code retry failure count was `0`.
- The formal candidate artifact is complete:
  `campaign/artifacts/formal_candidates/1cddb283/screening-9e91b3b3-ffbe-4280-8fb6-519e09203d15-699b3682710f2d3d/candidate.patch.json`

This accepts the `research_surfaces` target-intent prompt repair in the field.

## Candidate Patch

The candidate added `_route_merge_repair` and `_try_absorb_route` in
`policies/baseline_modules/destroy_repair.py`, then replaced the scheduler
repair operator `regret3` with `route_merge_repair`.

The intended behavior was guarded route absorption:

- run normal regret-3 insertion first;
- activate absorption only when repair creates a route or route count is above
  the route limit;
- record only stable telemetry through `record_iteration`, `record_phase`, and
  `record_move`;
- require material distance gain in non-pressure cases before committing the
  absorption.

## Screening Result

Rejected as a solver improvement.

- Stage: `screening`
- Selected surface: `solver_design`
- Evidence status: `complete`
- Runtime evidence status: `sufficient`
- Runtime confidence: `high`
- Pair count: `32/32`
- Failed pairs: `0`
- Cases: `A-n64-k9`, `B-n63-k10`, `E-n101-k14`, `P-n65-k10`, `CMT2`,
  `CMT4`, `M-n200-k17`, `X-n110-k13`
- Seeds: `11`, `29`, `43`, `59`
- Pair W/L/T: `0/0/32`
- Metric deltas: `fleet_violation=0.0`, `total_distance=0.0` for every pair.
- Runtime ratio median: `0.9993194149832383`
- Runtime delta median: `-16.5ms`
- Runtime ratio range: `0.9693330130514853` to `1.0144194976685867`

Decision/lifecycle status:

- Champion remained `v1`.
- `accepted_experiments=0`.
- Branch code status: `active_no_effect`.
- Not-promoted reason codes include `SCREENING_FAIL_WIN_RATE`,
  `SCREENING_ZERO_WIN_STREAK_CONTINUE`,
  `SCREENING_TELEMETRY_EFFECT_ZERO_DIAGNOSTIC`, and
  `TELEMETRY_EFFECT_ZERO_DIAGNOSTIC`.

## Telemetry Diagnosis

The telemetry path is valid, but the mechanism had no objective effect.

- `route_merge_repair` activation/runtime telemetry was present in `30/32`
  candidate runs.
- `solver_algorithm_phase_runtime_ms.route_merge_repair` observed `30`
  nonzero values.
- `solver_algorithm_phase_improvement_counts.route_merge_repair` was `0` in
  all `30` observed activations.
- `solver_algorithm_phase_best_delta.route_merge_repair` was `0.0` in all
  `30` observed activations.
- Candidate telemetry guard passed with warnings for missing effect:
  `TELEMETRY_EFFECT_NOT_OBSERVED`.

The run therefore separates framework validity from algorithm value:

- Steering, source visibility, code-generation constraints, stable telemetry
  helpers, artifact accounting, and formal screening all worked.
- The guarded route-absorption idea did not improve any measured objective
  pair, so it must not be promoted or repeated unchanged.

## Conclusion

The target-intent guidance-injection repair is accepted. The guarded
`route_merge_repair` candidate is rejected as a solver improvement.

This is useful v0.4 research-loop evidence because Scion can now carry a
same-mechanism CVRP hypothesis through code generation and complete formal
screening without infrastructure failures. It is not yet effective CVRP solver
research in the stronger sense of producing an improving branch.

Next CVRP work should not rerun this guarded v2 unchanged. The next field check
should test whether the campaign can transfer this `active_no_effect` lesson:
either clean-fork into a materially different problem-owned solver-design
mechanism, or propose a route-merge variant with explicit preconditions showing
where absorption can produce nonzero best-delta effects before formal screening.
