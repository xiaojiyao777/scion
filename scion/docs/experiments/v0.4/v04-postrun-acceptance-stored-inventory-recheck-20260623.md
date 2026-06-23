# Postrun Acceptance Stored-Inventory Recheck Repair

Date: 2026-06-23

## Purpose

Completed run roots must remain checkable after the Scion checkout advances.
During the warehouse v2 positive-control postrun audit, re-running
`check_postrun_acceptance.py` from a newer WSL checkout failed with
`prepared_contract_git_mismatch` even though the stored postrun readiness file
and the stored analysis-brief/inventory artifacts agreed.

## Finding

`check_postrun_acceptance.build_readiness()` rebuilt inventory live from the
current checkout. That live rebuild recalculated launcher/prepared-contract
fields, including the git contract, while the analysis brief came from the
postrun artifact set generated at run time. After normal documentation or code
commits, a historical root could therefore fail current-run readiness because
the checker mixed current checkout inventory with stored postrun analysis
artifacts.

This is a generic postrun artifact-source bug. It is not warehouse-specific and
does not change Decision, Protocol, scheduler, promotion, or problem semantics.

## Change

`scion/tools/check_postrun_acceptance.py` now reads the stored inventory JSON
declared by the rebuild manifest when it is present. It falls back to live
`build_inventory()` only for legacy or incomplete roots without a stored
inventory artifact.

The readiness output now records the inventory source in
`checks.inventory_loaded.detail.source`:

- `stored_postrun_inventory`
- `live_inventory_rebuild`

## Verification

Local:

```bash
PYTHONPATH=scion pytest -q \
  scion/scion/tests/test_check_postrun_acceptance.py \
  scion/scion/tests/test_check_postrun_acceptance_inventory_source.py
# 86 passed
```

WSL conda `scion`:

```bash
PYTHONPATH=scion /home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m pytest -q \
  scion/scion/tests/test_check_postrun_acceptance.py \
  scion/scion/tests/test_check_postrun_acceptance_inventory_source.py
# 86 passed
```

WSL warehouse root recheck:

```bash
PYTHONPATH=scion /home/xjy-ubuntu/miniconda3/envs/scion/bin/python \
  scion/tools/check_postrun_acceptance.py \
  /home/xjy-ubuntu/research/scion-experiments/v04-wh-v2-positive-2f8e9f21-current-8r-gpt55-20260623T161630Z-claw \
  --require-current-run-ready --format json
```

Result: exit `0`, `current_run_analysis_ready=true`,
`delegation_ready=true`, no required failures,
`checks.inventory_loaded.detail.source=stored_postrun_inventory`, and
`analysis_brief_prepared_contract_consistency=ok`. The only optional failure
reported by the concise probe was `postrun_report_status_marker`; it does not
block current-run readiness.

## Boundary

The repair changes only the artifact source used by the postrun acceptance
checker. It preserves prepared-contract drift detection between the stored
analysis brief and stored inventory, and it keeps all postrun diagnostics
report-only and excluded from `DecisionFeatures`.
