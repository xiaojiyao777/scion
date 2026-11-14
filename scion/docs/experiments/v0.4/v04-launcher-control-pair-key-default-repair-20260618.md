# v0.4 Launcher Control-Pair-Key Default Repair

Date: 2026-06-18

## Purpose

The launchers exposed `--control-pair-key` as optional report-only metadata, but
the prepared-root contract requires a non-empty control-pair key. Omitting the
flag produced a prepare-only root whose manifest looked usable but whose
launch-readiness contract failed.

This repair makes both focused launchers write a deterministic default
control-pair key when the operator does not pass one explicitly.

## Behavior

- CVRP default: `cvrp.<safe-label>:prepared`
- Warehouse default: `warehouse.<safe-label>:prepared`
- Explicit `--control-pair-key` values remain unchanged.
- Overlong labels are shortened with a stable SHA-1 suffix so the key stays
  within the existing proposal-trajectory `128` character limit.

The key remains report-only metadata. It is passed to postrun acceptance rebuild
and proposal-trajectory reporting only; it is not passed to `scion run`, not
used by Decision, and not used by Protocol gates.

## Changed Files

- `scion/tools/launch_cvrp_agentic_campaign.py`
- `scion/tools/launch_warehouse_agentic_campaign.py`
- `scion/scion/tests/test_cvrp_agentic_launcher.py`
- `scion/scion/tests/test_warehouse_agentic_launcher.py`

## Verification

```bash
PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion pytest -q \
  scion/scion/tests/test_cvrp_agentic_launcher.py \
  scion/scion/tests/test_warehouse_agentic_launcher.py \
  scion/scion/tests/test_launch_readiness.py \
  scion/scion/tests/test_postrun_artifact_inventory.py \
  scion/scion/tests/test_rebuild_postrun_acceptance.py

python -m py_compile \
  scion/tools/launch_cvrp_agentic_campaign.py \
  scion/tools/launch_warehouse_agentic_campaign.py \
  scion/tools/check_launch_readiness.py \
  scion/tools/postrun_artifact_inventory.py \
  scion/tools/rebuild_postrun_acceptance.py
```

Result: `39 passed`.

## Current Roots

The current `f481f15` CVRP and warehouse prepared roots already include
explicit control-pair keys and remain the active prepared roots. They do not
need regeneration for this launcher-default repair.
