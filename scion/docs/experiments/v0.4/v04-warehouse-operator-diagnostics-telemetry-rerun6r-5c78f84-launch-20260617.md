# Warehouse Operator Diagnostics Telemetry Rerun 5c78f84 Launch

*Date: 2026-06-17*
*Commit under test: `5c78f84`*
*Status: stopped as invalid shakedown*

## Purpose

This reruns the warehouse operator diagnostics telemetry field gate after the
`9ad5465` shakedown exposed a pre-protocol `schema_retry_drift` blocker.

Commit `5c78f84` adds the follow-up repair:

- warehouse declares structural activation counter names through
  `active_subject_taxonomy`;
- schema retry mechanism-reference extraction can see nested runtime map
  mechanism segments while filtering structural counter leaves;
- tests preserve the real protection case: nested telemetry paths pointing at
  another mechanism still trigger `schema_retry_drift`.

## Launch

- Root:
  `/home/clawd/research/scion-experiments/v04-warehouse-operator-diagnostics-telemetry-rerun6r-5c78f84-20260617T050235Z`
- tmux session:
  `scion_wh_operator_diag_5c78f84_050235`
- repo:
  `/home/clawd/research/or-autoresearch-agent`
- commit:
  `5c78f84`
- script:
  `/home/clawd/research/scion-experiments/v04-warehouse-operator-diagnostics-telemetry-rerun6r-5c78f84-20260617T050235Z/run_server.sh`

Run shape:

- warehouse production problem/protocol/split/seed configs;
- rounds: `6`;
- time limit: `30s`;
- measurement governance: `on`;
- proposal context ablation: `compact-measurement-diagnostics`;
- early stop disabled;
- agentic proposal with `900s` session timeout;
- local model endpoint `gpt-5.5`.

This is one short server-side acceptance cell.

## Startup Evidence

Initial status:

```text
status=running
started_at_utc=2026-06-17T05:03:47Z
commit=5c78f84
rounds=6
cell=rep01/on_compact
measurement_governance=on
context=compact-measurement-diagnostics
purpose=v0.4_warehouse_operator_diagnostics_telemetry_field_gate_after_5c78f84
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
- at least one screening-positive candidate has formal metrics consuming
  declared `operator_diagnostics.{mechanism}.*` telemetry;
- activation/effect diagnostics are not stuck at `not_declared` for accepted
  standard-diagnostics operator patches.

## Stop Outcome

The run was stopped by the main thread at `2026-06-17T05:11:54Z` after two
repeated pre-protocol warehouse patch-quality blocks and no protocol rows.

Final status:

```text
status=finished
finished_at_utc=2026-06-17T05:11:54Z
exit_code=1
commit=5c78f84
rounds=6
cell=rep01/on_compact
```

Campaign validity:

```json
{
  "effective_rounds_completed": 0,
  "proposal_attempts_total": 3,
  "formal_screened_candidates": 0,
  "protocol_metric_results": 0,
  "protocol_stage_counts": {
    "screening": 0,
    "validation": 0,
    "frozen": 0
  },
  "quality_blocks": 2,
  "run_validity.status": "invalid",
  "run_validity.reason": "invalid_no_effective_rounds",
  "stopped_reason": "signal:SIGTERM"
}
```

Observed blocks:

- attempt 1, `operators/subcategory_bin_upgrade_consolidate.py`: blocked by
  `warehouse_validation_transfer_patch_quality_missing` with
  `missing=screening_or_lexicographic_guard`;
- attempt 2, `operators/move_order.py`: blocked by the same gate with
  `missing=activation_effect_diagnostic_code,screening_or_lexicographic_guard`;
- attempt 3, `operators/swap_orders.py`: still in code retry when the run was
  stopped after a separate action-target mismatch (`approved remove` versus
  emitted `modify`), so it produced no third warehouse patch-quality row.

This run is not scientific evidence and must not be interpreted as warehouse
research performance. It is a failed shakedown of the operator diagnostics
telemetry repair.

## Diagnosis

Read-only trace analysis found the schema-retry blocker fixed: the run reached
warehouse patch-quality validation rather than `schema_retry_drift`. The new
blocker is the mismatch between problem-owned gate expectations and code-phase
guidance/accepted code shapes.

The initial code prompt exposed warehouse validation-transfer guidance and the
standard `self.validation_transfer_diagnostics` keys, but it did not place the
exact gate-accepted code shape next to the code task. Later retries received the
repair template through `Prior Agent Quality Blocks For This Code Patch`, but
the gate still recognized only a narrow AST pattern: direct exportable
diagnostics plus an `if` test containing transfer-relevant split/cost terms and
an immediate original-solution return.

The second completed patch was directionally closer than the final rejection
suggests: it used helper-created diagnostics, alias mutation, and split/cost
guarding, but the static check did not recognize that shape. This preserves the
v3 boundary issue ordering:

- keep the check problem-owned and pre-protocol;
- do not weaken Decision or Protocol gates;
- make the problem-owned code constraints and static acceptance shapes precise
  enough that the agent can satisfy them without trial-and-error.

## Required Follow-Up

Before another field gate:

- expose warehouse active-subject code constraints in the first code prompt:
  standard diagnostics keys, activation/effect mutations, and an executable
  screening-only or lexicographic guard shape;
- adjust the warehouse patch-quality static check to accept helper-returned
  `self.validation_transfer_diagnostics` dictionaries, alias mutations, and
  positive split/cost guard forms, while still rejecting comments, local-only
  dictionaries, missing diagnostics, and missing guards;
- add regression tests using the attempt-2 shape so the same failure does not
  recur;
- keep `decision_features_excluded=true` for quality-block feedback.
