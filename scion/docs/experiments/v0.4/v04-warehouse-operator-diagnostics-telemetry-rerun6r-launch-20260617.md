# Warehouse Operator Diagnostics Telemetry Rerun Launch

*Date: 2026-06-17*
*Commit under test: `9ad5465`*
*Status: stopped invalid before protocol rows; schema retry repair implemented next*

## Purpose

This single-cell server rerun validates the warehouse operator diagnostics
telemetry repair from commit `9ad5465`.

The previous valid data-root rerun proved copied production split cases can
reach canary and screening, but branch-level analysis showed a remaining
problem-owned measurement wiring defect: accepted operators wrote
`validation_transfer_diagnostics`, while formal metrics still reported
activation/effect diagnostics as `not_declared`.

This run tests whether screening-positive candidates now expose consumed
declared telemetry under `operator_diagnostics.{mechanism}.*`.

## Launch

- Root:
  `/home/clawd/research/scion-experiments/v04-warehouse-operator-diagnostics-telemetry-rerun6r-9ad5465-20260617T045136Z`
- tmux session:
  `scion_wh_operator_diag_9ad5465_045136`
- repo:
  `/home/clawd/research/or-autoresearch-agent`
- commit:
  `9ad5465`
- script:
  `/home/clawd/research/scion-experiments/v04-warehouse-operator-diagnostics-telemetry-rerun6r-9ad5465-20260617T045136Z/run_server.sh`

Run shape:

- problem: warehouse delivery production config copied into the experiment root;
- protocol: `scion/problems/warehouse_delivery/protocol_prod.yaml`;
- split: production split manifest copied into the experiment root;
- seeds: `scion/problems/warehouse_delivery/seed_ledger.yaml`;
- rounds: `6`;
- time limit: `30s`;
- measurement governance: `on`;
- proposal context ablation: `compact-measurement-diagnostics`;
- early stop: disabled;
- proposal mode: agentic;
- agentic session timeout: `900s`;
- model endpoint: local `gpt-5.5`.

This is one short acceptance cell, so it runs on the 2-core server. Larger
parallel matrices remain WSL work.

## Startup Evidence

Initial status:

```text
status=running
started_at_utc=2026-06-17T04:52:34Z
commit=9ad5465
rounds=6
cell=rep01/on_compact
measurement_governance=on
context=compact-measurement-diagnostics
purpose=v0.4_warehouse_operator_diagnostics_telemetry_field_gate_after_9ad5465
```

Campaign log confirms copied-config data-root activation and campaign startup:

```text
INFO: activated problem data root SCION_WAREHOUSE_DATA_ROOT=/home/clawd/research/scion-data
Starting campaign: warehouse_delivery (max_rounds=6, mock_llm=False, disable_early_stop=True)
```

## Early Stop

The run was stopped manually at `2026-06-17T04:55:34Z` after two consecutive
pre-protocol `schema_retry_drift` failures and zero protocol rows:

```text
exit_code=1
effective_rounds_completed=0
protocol_metric_results=0
quality_blocks=2
```

The repeated failure was not warehouse research evidence. It exposed a schema
retry preservation bug: the retry guard treated bare activation counter leaf
names such as `operator_invocations`, `eligible_vehicle_or_order_groups_seen`,
and `accepted_moves` as mechanism ids. That conflicted with the new warehouse
guidance, where these names are structural runtime counters under
`operator_diagnostics.{mechanism}.*`.

Follow-up repair:

- warehouse adapter declares these names as problem-owned structural activation
  refs through `active_subject_taxonomy`;
- schema retry mechanism-ref extraction now sees nested runtime map mechanism
  segments while allowing structural refs to filter leaf counters;
- tests verify that bare structural counter names no longer trigger mechanism
  drift, while nested paths pointing at another mechanism still do.

This stopped run is therefore an invalid shakedown, not a failed mechanism or
framework efficacy result. Rerun from the follow-up repair commit.

## Acceptance Criteria

Accept this repair's field gate only if:

- wrapper exits `0` and `run_validity.status=valid`;
- formal protocol rows are produced;
- at least one screening-positive candidate has formal metrics consuming
  declared `operator_diagnostics.{mechanism}.*` telemetry;
- activation/effect diagnostics are not stuck at `not_declared` for accepted
  standard-diagnostics operator patches;
- any remaining screening-only outcome is explained by objective/pair evidence
  and declared activation/effect diagnostics, not by missing telemetry wiring.
