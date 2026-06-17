# Warehouse Patch-Quality Shape Rerun 6R Launch

*Date: 2026-06-17*
*Commit under test: `fdba51e`*
*Status: stopped; failed field acceptance*

## Purpose

This is the short warehouse production field gate for the local
patch-quality-shape repair after the `5c78f84` shakedown stopped with repeated
`warehouse_validation_transfer_patch_quality_missing` blocks and no protocol
rows.

Commit `fdba51e` keeps the repair problem-owned:

- code prompts receive warehouse active-subject code constraints for
  exportable `self.validation_transfer_diagnostics` and executable split/cost
  guards;
- the warehouse static patch-quality gate accepts helper-returned standard
  diagnostics dictionaries assigned to `self.validation_transfer_diagnostics`,
  alias mutations, split/cost delta guards, and candidate/base split-cost
  guards;
- comments, strings, local-only dictionaries, missing diagnostics keys, and
  missing guards still fail closed;
- no Decision, Protocol, or promotion gate was changed.

## Launch

- Root:
  `/home/clawd/research/scion-experiments/v04-warehouse-patch-quality-shape-rerun6r-fdba51e-20260617T052828Z`
- tmux session:
  `scion_wh_patchshape_fdba51e_052828`
- repo:
  `/home/clawd/research/or-autoresearch-agent`
- commit:
  `fdba51e`
- script:
  `/home/clawd/research/scion-experiments/v04-warehouse-patch-quality-shape-rerun6r-fdba51e-20260617T052828Z/run_server.sh`

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
started_at_utc=2026-06-17T05:29:34Z
commit=fdba51e
rounds=6
cell=rep01/on_compact
measurement_governance=on
context=compact-measurement-diagnostics
purpose=v0.4_warehouse_patch_quality_shape_field_gate_after_fdba51e
```

Campaign log confirms copied-config data-root activation and campaign startup:

```text
INFO: activated problem data root SCION_WAREHOUSE_DATA_ROOT=/home/clawd/research/scion-data
Starting campaign: warehouse_delivery (max_rounds=6, mock_llm=False, disable_early_stop=True)
```

First health check:

```json
{
  "effective_rounds_completed": 0,
  "proposal_attempts_total": 1,
  "formal_screened_candidates": 0,
  "protocol_metric_results": 0,
  "quality_blocks": 0
}
```

## Acceptance Criteria

Accept only if:

- wrapper exits `0` and `run_validity.status=valid`;
- formal protocol rows are produced;
- the previous repeated `warehouse_validation_transfer_patch_quality_missing`
  shape loop does not recur before protocol;
- at least one screening-positive candidate has formal metrics consuming
  declared `operator_diagnostics.{mechanism}.*` telemetry;
- activation/effect diagnostics are not stuck at `not_declared` for accepted
  standard-diagnostics operator patches.

## Stop And Postrun Evidence

The main thread stopped this field gate with `SIGTERM` after the acceptance
failure was already clear. The wrapper completed postrun report generation.

- final status: `exit_code=1`
- `run_validity.status=valid`
- `run_validity.reason=valid_partial_interrupted`
- `effective_rounds_completed=4`
- `protocol_metric_results=4`
- `quality_blocks=6`
- protocol stages: `screening=4`, `validation=0`, `frozen=0`

Postrun artifacts:

- summary:
  `/home/clawd/research/scion-experiments/v04-warehouse-patch-quality-shape-rerun6r-fdba51e-20260617T052828Z/postrun_acceptance/summaries/rep01_on_compact.summary.json`
- failures:
  `/home/clawd/research/scion-experiments/v04-warehouse-patch-quality-shape-rerun6r-fdba51e-20260617T052828Z/postrun_acceptance/failures/rep01_on_compact.failures.json`
- research efficiency:
  `/home/clawd/research/scion-experiments/v04-warehouse-patch-quality-shape-rerun6r-fdba51e-20260617T052828Z/postrun_acceptance/research_efficiency/rep01_on_compact.research_efficiency.v1.json`
- proposal trajectory manifest:
  `/home/clawd/research/scion-experiments/v04-warehouse-patch-quality-shape-rerun6r-fdba51e-20260617T052828Z/postrun_acceptance/manifests/rep01_on_compact.proposal_trajectory_manifest.v1.json`

## Acceptance Decision

Failed field acceptance.

What improved:

- The prior `5c78f84` zero-protocol-row blocker is cleared. This run produced
  four formal screening protocol rows.
- Newly created operator telemetry can be consumed correctly. Metrics
  `9b304408-e179-4a11-a856-6fb3e00a29b6.json` for
  `operators/same_subcategory_residual_merge.py` used the declared mechanism
  `same_subcategory_residual_merge`, exported matching
  `operator_diagnostics.same_subcategory_residual_merge.*`, passed telemetry,
  and continued same-mechanism exploration.

What still fails:

- Repeated warehouse quality blocks recurred: `5` code-generation blocks for
  `warehouse_validation_transfer_patch_quality_missing`, plus one
  hypothesis-stage `warehouse_validation_transfer_quality_missing` for missing
  `validation_transfer_risk`.
- No validation, frozen, or promotion row occurred.
- A positive screening candidate was abandoned by telemetry mismatch:
  `metrics/a7345ba3-934c-4f0d-a632-d5e40989c5f0.json` modified
  `operators/move_order.py` and scored case W/L/T `2/1/3`, pair W/L/T `5/3/4`,
  and median delta `+225.0`, but Decision reason was
  `SCREENING_TELEMETRY_FAILED`. The candidate declared
  `split_preserving_vehicle_elimination`, while runtime exported diagnostics
  under the existing registry key `move_order`.

Next repair:

- Keep the fix warehouse-owned. For modified existing operators, expected
  telemetry keys must align with the actual registry/export key, or the
  proposal/patch must fail before Protocol with structured warehouse-owned
  repair guidance. Do not change `DecisionFeatures`, Decision, Protocol
  thresholds, validation/frozen gates, or promotion semantics.

## Follow-Up Repair

The follow-up mechanism-identity telemetry repair is locally accepted in
`WarehouseDeliveryAdapter`. Modified existing warehouse operators now fail
before Protocol with `warehouse_operator_telemetry_identity` when declared
telemetry mechanism ids do not match the runtime export key derived from the
target module. The concrete blocked shape is the `move_order.py` failure from
this run: declaring `split_preserving_vehicle_elimination` while runtime can
only export `operator_diagnostics.move_order.*`. New operator modules still may
use their new registered operator name.

Main-thread verification:

- `PYTHONPATH=scion python -m pytest -q scion/scion/tests/unit/test_warehouse_target_preview.py`
  -> `29 passed`
- `PYTHONPATH=scion python -m pytest -q scion/scion/tests/unit/core/test_proposal_pipeline_quality_blocks.py`
  -> `21 passed`
- `PYTHONPATH=scion python -m pytest -q scion/scion/tests/unit/test_agentic_session_core_flow.py scion/scion/tests/unit/test_agentic_session_preview_repair.py`
  -> `38 passed`
- `PYTHONPATH=scion python -m pytest -q scion/scion/tests/unit/test_runtime_telemetry_guard.py scion/scion/tests/unit/test_runtime_telemetry_guard_mechanism_diagnostics.py scion/scion/tests/unit/test_expected_telemetry_activation_contract.py`
  -> `41 passed`
- `PYTHONPATH=scion python -m pytest -q scion/scion/tests/unit/test_cvrp_solver_design_provider.py scion/scion/tests/unit/core/test_proposal_pipeline_quality_blocks.py`
  -> `43 passed`
- `py_compile` and `git diff --check` passed
