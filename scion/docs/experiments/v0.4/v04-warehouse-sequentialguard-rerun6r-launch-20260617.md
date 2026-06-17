# Warehouse Sequential-Guard Rerun 6R Launch

*Date: 2026-06-17*
*Commit under test: `6921f70`*
*Status: running on server*

## Purpose

This single-cell local field gate validates the warehouse-owned detector repair
from commit `6921f70`.

The preceding `9853dd4` quality-skeleton gate was interrupted by API balance
exhaustion after one effective round. Partial trace analysis still exposed a
warehouse detector false negative: one valid `change_vehicle_type.py` patch
computed base/candidate split and cost deltas, used sequential executable
candidate filters, and returned the original solution when no candidate passed.
The old recognizer missed it because it required split and cost terms in one
guard expression.

This run checks whether the repaired recognizer stops that false positive
without relaxing Decision, Protocol thresholds, or `DecisionFeatures`.

## Preflight

- Local gpt-5.5 structured-tool probe: passed.
- Local proxy `/v1/models`: exposed `gpt-5.5`.
- Server Scion process check before launch: no active experiment process.
- WSL reverse SSH: healthy.
- WSL runner checkout: fast-forwarded to `6921f70`.
- WSL conda `scion` env: `pytest`, `yaml`, and `sqlite3` available.
- WSL proxy `/v1/models`: exposed `gpt-5.5`.

The server worktree has unrelated dirty files outside this warehouse runtime
slice: `vrp/src/solver.py`, an untracked module-debt doc, and an untracked
agentic-runtime guard test. The warehouse adapter/runtime files under test are
from commit `6921f70`.

## Launch

- Server root:
  `/home/clawd/research/scion-experiments/v04-warehouse-sequentialguard-rerun6r-6921f70-20260617T123751Z`
- Cell:
  `rep01/on_compact`
- tmux session:
  `scion_wh_sequentialguard_rerun6r_6921f70_20260617T123751Z`
- repo:
  `/home/clawd/research/or-autoresearch-agent`
- commit:
  `6921f70`

Shape:

- problem: warehouse delivery production config copied into the experiment root
- protocol: copied `protocol_prod.yaml`
- split: copied `split_manifest_prod.yaml`
- seeds: copied `seed_ledger.yaml`
- rounds: `6`
- time limit: `30s`
- measurement governance: `on`
- proposal context ablation: `compact-measurement-diagnostics`
- early stop: disabled
- proposal mode: agentic
- agentic session timeout: `900s`
- model endpoint: local `gpt-5.5`

Environment:

- `SCION_MODEL=gpt-5.5`
- `SCION_BASE_URL=http://127.0.0.1:8080`
- `SCION_API_KEY=pwd`
- `SCION_WAREHOUSE_DATA_ROOT=/home/clawd/research/scion-data`
- `SCION_PROBLEM_DATA_ROOT=/home/clawd/research/scion-data`
- `SCION_SDK_MAX_RETRIES=0`
- `SCION_LLM_MAX_RETRIES=0`
- `SCION_STAGE_TRANSITION_DRAIN_LIMIT=4`

## Health Check

Initial launch health check passed:

```text
status=running
commit=6921f70
rounds=6
measurement_governance=on
context=compact-measurement-diagnostics
tmux_session=scion_wh_sequentialguard_rerun6r_6921f70_20260617T123751Z
```

The campaign log reached:

```text
Starting campaign: warehouse_delivery (max_rounds=6, mock_llm=False, disable_early_stop=True)
```

Early artifacts exist: `llm_traces/`, `agentic_sessions/`,
`run_status.json`, `status.json`, and `scion.db`.

## Acceptance Criteria

Field-accept the detector repair only if:

- the run is valid and completes, or any incompleteness is clearly an
  infrastructure interruption;
- the specific sequential split/cost candidate-filter false positive does not
  recur;
- split-only, cost-only, string/comment-only, and local-only diagnostic shapes
  remain blocked if they appear;
- no generic Decision, Protocol, or `DecisionFeatures` behavior changes.

Research-quality acceptance remains stricter: validation/frozen/promotion or a
clear branch-depth/research-quality improvement is required. A clean detector
field check alone is not warehouse efficacy evidence.
