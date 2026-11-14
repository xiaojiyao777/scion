# Warehouse 1-Candidate Lifecycle Debug Postrun - 2026-06-15

## Purpose

This gate checked whether the repaired warehouse campaign path can again reach
formal Protocol after the aborted longrun exposed pre-Protocol environment and
fix-stage failures.

This is a lifecycle/path-health gate, not a warehouse promotion experiment. It
does not prove continuous warehouse improvement potential. It only verifies
that Contract, Verification, canary, and screening Protocol can run again for a
single production warehouse candidate under the compact context profile.

## Artifacts

- Design report:
  `scion/docs/experiments/v0.4/v04-warehouse-1candidate-lifecycle-debug-design-20260615.md`
- Invalid first root:
  `/home/clawd/research/scion-experiments/v04-warehouse-1candidate-lifecycle-debug-20260615T1950Z`
- Accepted rerun root:
  `/home/clawd/research/scion-experiments/v04-warehouse-1candidate-lifecycle-debug-20260615T2000Z`
- WSL accepted rerun root:
  `/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-1candidate-lifecycle-debug-20260615T2000Z`
- Accepted rerun commit: `9204315`
- Accepted rerun shape: `rounds=1`, `cells=1`,
  `measurement_governance=on`, `compact-measurement-diagnostics`,
  local `gpt-5.5`, `time_limit_sec=30`, disabled early stop.

## Invalid T1950 Attempt

The first run is invalid evidence:

- `run_validity.status=invalid`
- `run_validity.reason=invalid_no_protocol_rows`
- `protocol_metric_results=0`
- `formal_screened_candidates=0`

It did reach a candidate and canary invocation, but canary failed before formal
Protocol because the copied split manifest resolved `safe_data_roots` to the
wrong WSL root:

```text
canary configuration error: Unsafe case path in strict ExperimentProtocol:
'artifact:instance_prod_can_s01.json#309b0fc79d05'
status=absolute_outside_roots reason=absolute case path is outside workspace
and safe_data_roots
```

Root cause: the experiment-local copied `split_manifest_prod.yaml` still used a
relative `../../../../scion-data` safe root. From the experiment config
directory that resolved to `/home/xjy-ubuntu/scion-data`, not the real WSL data
root `/home/xjy-ubuntu/research/scion-data`.

## Accepted T2000 Rerun

The rerun copied warehouse configs into the experiment root and rewrote the
split manifest safe root to the absolute WSL data root:
`/home/xjy-ubuntu/research/scion-data`.

Wrapper status:

- `status=finished`
- `exit_code=0`
- `finished_at_utc=2026-06-15T20:02:16Z`
- cell runtime: `2026-06-15T19:58:38Z` to `20:02:16Z`

Run validity and accounting:

- `run_validity.status=valid`
- `run_validity.effective_rounds_completed=1`
- `protocol_metric_results=1`
- `protocol_metric_stage_counts.screening=1`
- `formal_screened_candidates=1`
- `formal_candidate_artifact_count=1`
- `agentic_sessions=2`
- `llm_request_kind_counts`: `hypothesis=2`, `tool_selection=5`, `code=1`
- `verification_failure_breakdown=null`
- postrun failure report: `total_failures=0`

Candidate:

- Action: `create_new`
- Surface: `vehicle_level`
- Mechanism: `subcategory_consolidate_upgrade`
- Target: `operators/subcategory_consolidate_upgrade.py`
- Candidate intent: `algorithm_quality_candidate`

Lifecycle:

- Contract: passed
- Verification: passed
- Canary: passed
- Canary cases:
  - `case:instance_prod_can_s01.json#309b0fc79d05`
  - `case:instance_prod_can_s02.json#d425ca52b98f`
- Canary seed: `999`
- Canary attempted pairs: `2`
- Decision: `continue_explore`
- Decision reason codes:
  - `SCREENING_FAIL_WIN_RATE`
  - `SCREENING_MARGINAL_SIGNAL_CONTINUE`

Screening metrics:

- Case W/L/T: `1/2/7`
- Pair W/L/T: `5/8/7`
- Case win rate: `0.10`
- Pair win rate: `0.25`
- Median delta: `0.0`

Postrun prompt/accounting manifest:

- `formal_candidate_count=1`
- `formal_candidate_joined_session_count=1`
- `formal_candidate_replayable_count=1`
- `session_count=2`
- `trace_count=8`
- prompt manifest refs loaded: `8`
- aggregate prompt characters: `317,980`
- estimated prompt tokens: `79,498`
- block-family token share:
  - `tool_selection`: `52.5019%`
  - `general`: `31.2775%`
  - `research_signal`: `5.9976%`
  - `tool_observation`: `5.8027%`
  - `governance`: `4.4039%`
  - `source_context`: `0.0226%`

## Interpretation

The T2000 rerun passes the intended one-candidate lifecycle gate. Warehouse can
again proceed through proposal, code, Contract, Verification, canary, and
screening Protocol after the preflight and fix-stage repairs.

The single candidate did not pass screening, but it produced useful marginal
evidence and a live branch state (`continue_explore`) instead of dying before
Protocol. This is exactly the gate needed before a short warehouse rerun.

The T1950 failure should be treated as a launch/configuration lesson, not a
warehouse research result. The safe-root correction should be preserved for all
future WSL warehouse launches that use experiment-local copied split manifests.

The prompt manifest still shows low source-context share and large total prompt
payloads. That remains a context-density audit item for later warehouse
analysis, but it did not block the lifecycle path in this one-candidate gate.

## Next Gate

Do not jump directly back to the full `3 x 24R` warehouse longrun. The next
accepted step is a short compact warehouse debug:

- `3` to `5` rounds
- one compact ON arm
- same fixed WSL safe-root launch pattern
- local `gpt-5.5`
- warehouse production protocol/split/seeds
- inspect branch depth, same-mechanism continuation, prompt composition, and
  whether marginal screening evidence influences the next proposal.

Only if that short run reaches multiple protocol rows without returning to
pre-Protocol failures should the full warehouse longrun be relaunched.

All canary path diagnostics, prompt ratios, and warehouse problem semantics in
this report are problem-owned postrun evidence. They remain outside
`DecisionFeatures`.
