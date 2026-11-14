# Warehouse Validation-Transfer Contract Rerun 6R Launch

Date: 2026-06-17

Commit under test: `ce5d884`

Status: running on WSL

## Purpose

This short field gate validates the warehouse problem-owned
validation-transfer acceptance-contract guidance after the latest detector and
CVRP diagnostic slice.

The local repair requires warehouse order-level/swap-style candidates to prefer
split-positive moves, accept split-preserving cost-only moves only with
executable `split_delta == 0` and `cost_delta > 0`, export those deltas, and
fall back to the original solution when no candidate qualifies. This run checks
whether the live agent now proposes and codes that contract, without changing
generic Decision, Protocol thresholds, validation/frozen/promotion gates, or
`DecisionFeatures`.

## Launch

- WSL root:
  `/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-validation-transfer-contract-rerun6r-ce5d884-20260617T152944Z`
- Server sync root:
  `/home/clawd/research/scion-experiments/v04-warehouse-validation-transfer-contract-rerun6r-ce5d884-20260617T152944Z`
- Cell:
  `rep01/full_context`
- tmux session:
  `scion_wh_vt_contract_rerun6r_ce5d884_152944`
- repo:
  `/home/xjy-ubuntu/research/or-autoresearch-agent`
- commit:
  `ce5d884`

Shape:

- problem: warehouse delivery production config copied into the experiment root
- protocol: `scion/problems/warehouse_delivery/protocol_prod.yaml`
- split: production split manifest copied into the experiment root
- seeds: `scion/problems/warehouse_delivery/seed_ledger.yaml`
- rounds: `6`
- time limit: `30s`
- measurement governance: `on`
- proposal context: `full`
- early stop: disabled
- proposal mode: agentic
- model endpoint: WSL-local `gpt-5.5`

Environment:

- `SCION_MODEL=gpt-5.5`
- `SCION_BASE_URL=http://127.0.0.1:8080`
- `SCION_API_KEY=pwd`
- `SCION_WAREHOUSE_DATA_ROOT=/home/xjy-ubuntu/research/scion-data`
- `SCION_PROBLEM_DATA_ROOT=/home/xjy-ubuntu/research/scion-data`

No `SCION_STAGE_TRANSITION_DRAIN_LIMIT`, SDK/LLM retry cap override, prompt
truncation cap, or agentic session timeout override is set for this gate. The
run uses full proposal context to avoid validating this repair under another
compact-context/compression setting.

## Initial Health Check

Initial WSL health check passed:

```text
status=running
commit=ce5d884
rounds=6
cell=rep01/full_context
measurement_governance=on
context=full
```

The campaign log reached:

```text
Starting campaign: warehouse_delivery (max_rounds=6, mock_llm=False, disable_early_stop=True)
```

Early artifacts exist: `llm_traces/`, `agentic_sessions/`, `run_status.json`,
`status.json`, and `scion.db`.

## Acceptance Criteria

Field-accept the repair only if:

- the run is valid and complete, or any incompleteness is clearly
  infrastructure-only;
- warehouse validation-transfer proposal/code behavior follows the executable
  split/cost contract or fails with useful problem-owned quality feedback;
- repeated cost-only or split-unsafe validation-transfer candidates do not
  recur as accepted formal candidates;
- no generic Decision, Protocol, validation/frozen/promotion, or
  `DecisionFeatures` semantics change.

Research-quality acceptance remains stricter: validation/frozen/promotion
evidence or a clear branch-depth/research-quality improvement is required.
