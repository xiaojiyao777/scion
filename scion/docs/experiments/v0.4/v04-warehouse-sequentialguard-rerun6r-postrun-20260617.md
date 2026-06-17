# Warehouse Sequential-Guard Rerun 6R Postrun

*Date: 2026-06-17*
*Commit under test: `6921f70`*
*Status: invalid field gate; copied-config data-root repair locally accepted*

## Artifacts

- Server root:
  `/home/clawd/research/scion-experiments/v04-warehouse-sequentialguard-rerun6r-6921f70-20260617T123751Z`
- Campaign:
  `/home/clawd/research/scion-experiments/v04-warehouse-sequentialguard-rerun6r-6921f70-20260617T123751Z/rep01/on_compact/campaign`
- Launch report:
  [`v04-warehouse-sequentialguard-rerun6r-launch-20260617.md`](v04-warehouse-sequentialguard-rerun6r-launch-20260617.md)
- Wrapper:
  `wrapper_exit_status=0`, `campaign_exit_status=complete`,
  `run_completeness_status=complete`

## Outcome

This run does not field-accept the sequential split/cost guard repair and is
not warehouse research evidence.

- `run_validity.status=invalid`
- `run_validity.reason=invalid_no_protocol_rows`
- `effective_rounds_completed=6/6`
- `proposal_attempts=13`
- `proposal_quality_blocks=7`
- `protocol_metric_results=0`
- `n_experiments=0`
- champion stayed v1

The run completed the requested loop budget but produced no formal screening
rows. It therefore cannot answer whether the repaired sequential split/cost
recognizer behaves correctly in Protocol.

## Root Cause

Five completed candidate sessions reached Contract and Verification, then all
were abandoned before Protocol with `CANARY_CONFIG_ERROR`.

The concrete canary failure was:

```text
Unsafe case path in strict ExperimentProtocol:
'artifact:instance_prod_can_s01.json#64a747f955e8'
status=absolute_outside_roots
reason=absolute case path is outside workspace and safe_data_roots
```

The `artifact:` form is the public redaction of the internal absolute case
path. The underlying setup failure is copied-config data-root wiring:

- the experiment-local `config/` copy did not include `budgets.json`;
- `split_manifest_prod.yaml` still had `safe_data_roots:
  ../../../../scion-data`;
- from the copied config directory, that relative root resolves to
  `/home/clawd/scion-data`, not `/home/clawd/research/scion-data`;
- strict protocol path safety then rejected the production canary absolute
  path before formal Protocol could run.

This is a framework/config wiring failure, not candidate algorithm evidence.
The `CANARY_CONFIG_ERROR` taxonomy correctly prevented it from being recorded
as ordinary warehouse operator failure, but the run still spent a field gate
without reaching Protocol.

## Local Repair

A narrow CLI data-root repair is locally accepted:

- if copied experiment configs omit sibling `budgets.json`, an explicit
  `SCION_PROBLEM_DATA_ROOT` is now used as a generic safe data root;
- existing problem-owned `budgets.json` behavior is unchanged;
- strict canary path safety remains enabled;
- no Decision, Protocol threshold, proposal-quality, or `DecisionFeatures`
  behavior changed.

Focused reproduction against this run's copied config now resolves
`instance_prod_can_s01.json` as `resolved_safe_data_root` under
`/home/clawd/research/scion-data`.

## Validation

Commands passed:

```text
PYTHONPATH=scion python -m pytest -q \
  scion/scion/tests/unit/test_cli_data_roots.py \
  scion/scion/tests/unit/protocol/test_case_path_safety.py
```

Result: `10 passed`.

```text
PYTHONPATH=scion python -m pytest -q \
  scion/scion/tests/unit/core/test_canary_failure_taxonomy.py \
  scion/scion/tests/unit/core/test_evaluation_orchestrator_telemetry.py
```

Result: `18 passed`.

Additional checks:

```text
PYTHONPATH=scion python -m py_compile \
  scion/scion/cli/commands/data_roots.py \
  scion/scion/tests/unit/test_cli_data_roots.py
git diff --check
```

Both passed.

## Next

Commit the data-root fallback repair, then rerun one short local warehouse
`6R` field gate from the repaired commit. Accept the detector repair only if
the run reaches formal Protocol and the sequential split/cost guard false
negative does not recur. Do not launch a broad WSL matrix from this state.
