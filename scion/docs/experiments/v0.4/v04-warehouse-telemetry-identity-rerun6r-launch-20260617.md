# Warehouse Telemetry Identity Rerun 6R Launch

*Date: 2026-06-17*
*Commit under test: `7fe46a7`*
*Status: finished; invalid as research evidence*

## Purpose

This is the short warehouse production field gate for the warehouse
mechanism-identity telemetry repair after the `fdba51e` partial field gate
showed a positive `move_order.py` candidate abandoned by
`SCREENING_TELEMETRY_FAILED`.

The repair under test stays problem-owned in `WarehouseDeliveryAdapter`:

- modify-existing warehouse operators must use the existing runtime export key
  in declared telemetry, for example `operator_diagnostics.move_order.*` for
  `operators/move_order.py`;
- invented mechanism ids for existing operators now fail before Protocol with
  `warehouse_operator_telemetry_identity`;
- create-new operator modules may still use their new registered operator name;
- no `DecisionFeatures`, Decision, Protocol thresholds, validation/frozen
  gates, or promotion semantics changed.

## Launch

- Root:
  `/home/clawd/research/scion-experiments/v04-warehouse-telemetry-identity-rerun6r-7fe46a7-20260617T061211Z`
- tmux session:
  `scion_wh_telid_7fe46a7_061211`
- repo:
  `/home/clawd/research/or-autoresearch-agent`
- commit:
  `7fe46a7`
- script:
  `/home/clawd/research/scion-experiments/v04-warehouse-telemetry-identity-rerun6r-7fe46a7-20260617T061211Z/run_server.sh`

Run shape:

- warehouse production problem/protocol/split/seed configs;
- rounds: `6`;
- time limit: `30s`;
- measurement governance: `on`;
- proposal context ablation: `compact-measurement-diagnostics`;
- early stop disabled;
- agentic proposal with `900s` session timeout;
- local model endpoint `gpt-5.5`.

## Startup Evidence

Initial status:

```text
status=running
started_at_utc=2026-06-17T06:13:11Z
commit=7fe46a7
rounds=6
cell=rep01/on_compact
measurement_governance=on
context=compact-measurement-diagnostics
purpose=v0.4_warehouse_telemetry_identity_field_gate_after_7fe46a7
```

Campaign log confirms copied-config data-root activation and campaign startup:

```text
INFO: activated problem data root SCION_WAREHOUSE_DATA_ROOT=/home/clawd/research/scion-data
Starting campaign: warehouse_delivery (max_rounds=6, mock_llm=False, disable_early_stop=True)
```

## Acceptance Criteria

Accept only if:

- wrapper exits `0` and `run_validity.status=valid`;
- formal protocol rows are produced;
- modify-existing operator telemetry identity mismatches are blocked before
  Protocol, not consumed later as `SCREENING_TELEMETRY_FAILED`;
- no screening-positive candidate is lost because declared mechanism id and
  runtime `operator_diagnostics` export key differ;
- create-new operator telemetry remains consumable when registry/export key and
  declared mechanism id are aligned;
- validation/frozen/promotion gates remain strict and ordinary.

## Postrun Result

Final wrapper status:

```text
status=finished
finished_at_utc=2026-06-17T06:23:42Z
exit_code=0
commit=7fe46a7
rounds=6
cell=rep01/on_compact
```

Scientific validity:

```text
run_validity.status=invalid
run_validity.reason=invalid_no_effective_rounds
stopped_reason=telemetry_repair_attempt_budget_exhausted
effective_rounds_completed=0
protocol_metric_results=1
quality_blocks=1
```

The run is not accepted as warehouse research evidence. It produced one
Protocol screening row, but no effective screening round, validation row,
frozen row, or promotion.

## Diagnosis

The prior mechanism-identity mismatch blocker was cleared enough to reach
Protocol. The only formal screening row modified
`operators/merge_vehicles.py`, declared and consumed telemetry under the
runtime key `operator_diagnostics.merge_vehicles.*`, and therefore did not
repeat the earlier `move_order.py` identity mismatch.

The candidate itself was negative and non-effective:

```text
case W/L/T = 0/4/2
pair W/L/T = 0/8/4
median_delta = -4575.0
decision = continue_explore
reason_codes include TELEMETRY_VALIDATION_REPAIRABLE,
  SCREENING_TELEMETRY_REPAIRABLE,
  SCREENING_TELEMETRY_DIAGNOSTIC_RETRY,
  TELEMETRY_EFFECT_ZERO_DIAGNOSTIC,
  SCREENING_RUNTIME_BUDGET_SATURATION
```

Telemetry guard evidence showed the mechanism executed but produced no
improving effect: `operator_invocations` was positive on all candidate runs,
while accepted/effect counters were zero. This is a useful diagnostic, but not
an effective screening row.

The run stopped too early after the next hypothesis quality block. That block
missed `validation_transfer_risk`; because the branch was already
`telemetry_wiring_suspect`, the proposal failure was classified as a
`telemetry_repair` attempt for `merge_vehicles`. Combined with the previous
non-effective telemetry-repairable screening, the same branch/mechanism counter
hit the default limit of `2`, and the whole campaign stopped with
`telemetry_repair_attempt_budget_exhausted`.

Popper (`019ed442-338a-7122-ac18-58fa34d18965`) confirmed by read-only audit
that this is an implementation-level run stop, not a v3 boundary requirement.

## Follow-Up Repair

A local follow-up repair now:

- keeps `agent_quality_blocked` failures on repair-focused branches in the
  proposal quality-block path;
- preserves explicit repair-first policy violations as telemetry repair
  attempts;
- downgrades the same branch/mechanism telemetry repair cap from run-level
  termination to diagnostic status
  `telemetry_repair_attempt_limit_exhausted_keys`;
- leaves strict telemetry, Contract/Verification/Protocol, validation/frozen,
  and promotion gates unchanged;
- preserves invalid scientific validity for runs with no effective rounds.

Focused verification passed:

```text
PYTHONPATH=scion python -m pytest -q scion/scion/tests/unit/core/test_retry_round_accounting_campaign_loop.py
35 passed
PYTHONPATH=scion python -m pytest -q scion/scion/tests/unit/core/test_proposal_pipeline_hypothesis.py scion/scion/tests/unit/core/test_proposal_pipeline_quality_blocks.py
37 passed
PYTHONPATH=scion python -m pytest -q scion/scion/tests/unit/core/test_campaign_finalization_status_reconcile.py scion/scion/tests/unit/core/test_evidence_recorder_summary_status.py
61 passed
PYTHONPATH=scion python -m pytest -q scion/scion/tests/unit/test_warehouse_target_preview.py
29 passed
PYTHONPATH=scion python -m pytest -q scion/scion/tests/unit/test_runtime_telemetry_guard.py scion/scion/tests/unit/test_runtime_telemetry_guard_mechanism_diagnostics.py scion/scion/tests/unit/test_expected_telemetry_activation_contract.py
41 passed
PYTHONPATH=scion python -m pytest -q scion/scion/tests/unit/test_agentic_session_core_flow.py scion/scion/tests/unit/test_agentic_session_preview_repair.py
38 passed
PYTHONPATH=scion python -m py_compile scion/scion/core/campaign_loop.py scion/scion/core/explore_step/pipeline.py scion/scion/tests/unit/core/test_retry_round_accounting_campaign_loop.py scion/scion/tests/unit/core/test_proposal_pipeline_hypothesis.py
passed
git diff --check
passed
```

Next gate: commit the follow-up repair and run one short warehouse production
`6R` field check on the 2-core server. Larger matrices should remain on WSL.
