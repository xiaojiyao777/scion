# CVRP Route-Merge Guarded Follow-Up Field Failure

Date: 2026-06-18

Commit: `71666ae` (`Guide CVRP route merge follow-up`)

WSL run:
`/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-routemerge-guarded-agentic-1r-71666ae-20260618T000143Z`

Server sync:
`/home/clawd/research/scion-experiments/v04-cvrp-routemerge-guarded-agentic-1r-71666ae-20260618T000143Z`

## Purpose

This was the first field check after adding provider guidance that should have
kept the next CVRP agent on the active `route_merge_repair` branch. The desired
behavior was a guarded same-mechanism refinement in
`policies/baseline_modules/destroy_repair.py`, not a new scheduler or
local-search branch.

## Launch Shape

The run used the same short CVRP formal field-check shape as the previous
post-share70 target-selection check:

```bash
python -m scion.cli.main run \
  --problem .../cvrp/problem.yaml \
  --protocol .../cvrp/formal/protocol.yaml \
  --split .../cvrp/formal/split_manifest.yaml \
  --seeds .../cvrp/formal/seed_ledger.yaml \
  --campaign-dir "$ROOT/campaign" \
  --rounds 1 \
  --time-limit-sec 30 \
  --agentic-session-timeout-sec 900 \
  --measurement-governance on \
  --proposal-context-ablation compact-measurement-diagnostics \
  --disable-early-stop \
  --agentic-proposal
```

Model/proxy settings:

- `SCION_MODEL=gpt-5.5`
- `SCION_BASE_URL=http://127.0.0.1:8080`
- `SCION_API_KEY=pwd`
- `SCION_LLM_TIMEOUT_SEC=120`
- `SCION_LLM_CODE_TIMEOUT_SEC=240`
- `SCION_LLM_MAX_RETRIES=1`
- `SCION_SDK_MAX_RETRIES=0`

An earlier WSL attempt at
`/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-routemerge-guarded-agentic-1r-71666ae-20260617T235956Z`
stopped before any experiment because the WSL Python environment lacked the
`openai` package. The WSL runner was repaired by installing `openai-2.43.0` and
verifying `gpt-5.5` through the local OpenAI-compatible proxy before launching
the run reported here.

## Outcome

This run is not accepted as CVRP solver-improvement evidence. It did not
complete a valid same-mechanism field check.

- Wrapper status: manually stopped after it drifted into off-target screening,
  `SIGTERM`, exit `143`.
- Campaign summary: `proposal_attempts_total=3`, `quality_blocks=2`,
  `effective_rounds_completed=0`, `formal_screened_candidates=0`.
- LLM accounting: `26` traces, all `gpt-5.5`.
- Partial metric artifact:
  `campaign/metrics/685e9e4d-3b6e-4d86-8e6b-7c2ffbe2d14b.json`.
- Partial metric status: `attempted_pairs=19`, `valid_pairs=0`,
  `failed_pairs=19`, `champion_failed_pairs=19`,
  `screening_evidence_status=partial_champion_evidence`.

The partial metrics are not interpretable as candidate quality evidence. They
belong to an off-target scheduler candidate and the run was stopped before
formal screening completed.

## Steering Evidence

The run exposed two concrete guidance gaps.

First, the initial target stayed in the right file but did not preserve the
active mechanism identity:

- Attempt 1 target: `policies/baseline_modules/destroy_repair.py`.
- Attempt 1 mechanism: `route_limit_aware_repair`, not `route_merge_repair`.
- This is adjacent route-pressure reasoning, but not the same-mechanism
  `route_merge_repair` refinement requested by the current branch lesson.

Second, fallback attempts drifted away from the active branch:

- Attempt 2 target: `policies/baseline_modules/local_search.py`,
  mechanism `node_shift_local_search`.
- Attempt 3 target: `policies/baseline_modules/scheduler.py`,
  mechanism `stagnation_adaptive_destroy_size`.

This means commit `71666ae` guidance was strong enough to point the first target
toward destroy/repair, but not strong enough to preserve same-mechanism branch
identity or prevent fallback target drift.

## Code/API Evidence

The two quality-blocked attempts repeatedly invented or relied on unstable
telemetry helpers in candidate code:

- `SolverAlgorithmContext` had no usable candidate-facing
  `record_objective_probe` helper in the smoke context.
- Later retries called `record_best_update`, causing the same runtime-audit
  failure shape.

The framework correctly failed these proposals before accepting them as valid
formal candidates. The repair is therefore prompt/provider/API guidance, not a
generic Decision, Protocol, lifecycle, or promotion-gate change.

## Accepted Repair Direction

The follow-up repair is problem-owned CVRP provider guidance:

- same-mechanism continuation must keep `mechanism_changes` id
  `route_merge_repair`;
- `route_merge_repair_guarded_v2` means guarded trigger/acceptance refinement
  under the existing `route_merge_repair` id, not a renamed route-limit,
  local-search, or scheduler mechanism;
- candidate-facing telemetry should use only stable
  `record_phase`, `record_iteration`, and `record_move` helpers;
- candidate code should not add new calls to `record_best_update`,
  `record_objective_probe`, `record_alns_iteration`, or
  `record_solution_progress`.

Next CVRP action: rerun the same short WSL field check after committing this
provider repair. Acceptance requires target-intent, hypothesis, and code to
stay on `destroy_repair.py` / `route_merge_repair` before formal screening
results are interpreted.
