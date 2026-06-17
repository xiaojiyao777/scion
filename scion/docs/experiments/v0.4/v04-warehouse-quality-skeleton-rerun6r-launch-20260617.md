# Warehouse Quality-Skeleton Rerun 6R Launch

*Date: 2026-06-17*
*Commit under test: `9853dd4`*
*Status: interrupted; see postrun*

Postrun:
[`v04-warehouse-quality-skeleton-rerun6r-postrun-20260617.md`](v04-warehouse-quality-skeleton-rerun6r-postrun-20260617.md).

## Purpose

This single-cell field gate validates the warehouse problem-owned
quality-skeleton repair from commit `9853dd4`.

The prior field gate from `8688ac9` accepted the screening effect-zero
guidance repair, but research quality was still rejected with `6` proposal
quality blocks. The blocked `change_vehicle_type.py` exact-replace session
`f7851de0-0fee-4420-b20d-3c27df9bfd73` was classified as a true
`screening_or_lexicographic_guard` block: the recovered patch filtered only on
`cost_delta <= 0` and did not compute or enforce split/cost lexicographic
deltas.

This run checks whether the strengthened repair template and retry constraint
help the agent satisfy warehouse validation-transfer code requirements without
relaxing the detector, Decision, or `DecisionFeatures`.

## Launch

- Server root:
  `/home/clawd/research/scion-experiments/v04-warehouse-quality-skeleton-rerun6r-9853dd4-20260617T120052Z`
- tmux session:
  `scion_wh_quality_skeleton_rerun6r_9853dd4_20260617T120052Z`
- repo:
  `/home/clawd/research/or-autoresearch-agent`
- commit:
  `9853dd4`

Shape:

- problem: warehouse delivery production config copied into the experiment root
- protocol: `scion/problems/warehouse_delivery/protocol_prod.yaml`
- split: production split manifest copied into the experiment root
- seeds: `scion/problems/warehouse_delivery/seed_ledger.yaml`
- rounds: `6`
- time limit: `30s`
- measurement governance: `on`
- proposal context ablation: `compact-measurement-diagnostics`
- early stop: disabled
- proposal mode: agentic
- agentic session timeout: `900s`
- model endpoint: local `gpt-5.5`

Environment:

- `SCION_WAREHOUSE_DATA_ROOT=/home/clawd/research/scion-data`
- `SCION_PROBLEM_DATA_ROOT=/home/clawd/research/scion-data`

## Health Check

Initial tmux launch health check passed:

```text
status=running
commit=9853dd4
rounds=6
measurement_governance=on
context=compact-measurement-diagnostics
tmux_session=scion_wh_quality_skeleton_rerun6r_9853dd4_20260617T120052Z
```

The campaign log started with:

```text
Starting campaign: warehouse_delivery (max_rounds=6, mock_llm=False, disable_early_stop=True)
```

Early campaign artifacts exist: `llm_traces/`, `scion.db`, `status.json`, and
`run_status.json`.

## Wrapper Note

An earlier background `nohup` attempt at
`/home/clawd/research/scion-experiments/v04-warehouse-quality-skeleton-rerun6r-9853dd4-20260617T115932Z`
did not survive the exec session. It was marked
`status=aborted_wrapper_no_campaign`; no campaign directory or log was created,
so it consumed no LLM or protocol work.

## Acceptance Criteria

The repair is field-accepted only if:

- the run is valid and complete or any incompleteness is explained as
  non-research infrastructure failure;
- repeated `screening_or_lexicographic_guard` / cost-only downsize blocks stop,
  or any remaining block includes the strengthened code-shaped repair template;
- no Decision/core gate relaxation is involved;
- the run either reaches better research behavior than the `8688ac9` gate or
  provides enough prompt/session evidence to identify the next problem-owned
  repair.

Research-quality acceptance still requires validation/frozen/promotion
evidence or a clear branch-depth improvement; merely reducing proposal-quality
blocks is only field acceptance for this repair.
