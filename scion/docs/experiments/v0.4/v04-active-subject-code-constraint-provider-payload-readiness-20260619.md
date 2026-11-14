# v0.4 Active Subject Code Constraint Provider Payload Readiness

Date: 2026-06-19

## Purpose

Close a prepared-launch blind spot: the previous active-subject code-constraint
prompt bridge proved source markers existed, but did not prove the current
problem-owned provider resolved a non-empty normalized payload for the launch
family and code surface.

This matters for v0.4 because warehouse and CVRP code-generation prompts must
receive the problem-owned constraints that make follow-up research executable
and reviewable: warehouse validation-transfer diagnostics/acceptance constraints
and CVRP bounded large-instance two-opt object/API/runtime constraints.

## Change

- `rebuild_prepared_handoff.py` now records a report-only
  `scion.active_subject_code_constraints_provider_payload_summary.v1` under the
  prepared prompt-context readiness bridge.
- `check_launch_readiness.py` recomputes the current provider payload before
  launch and rejects missing, empty, unavailable, or stale summaries.
- The summary excludes raw prompt text and raw provider payload contents. It
  records only boundary flags, family/surface identity, version, subject id, and
  counts for constraints, object-model hints, API contracts, and forbidden
  patterns.
- CVRP/warehouse semantics remain problem-owned provider facts; generic launch
  readiness only checks report-only availability and identity.

Commits:

- Local: `afa8df39` (`Verify active subject code constraints before launch`)
- Local: `349981b9` (`Align CVRP postrun fixtures with calibration handoff`)
- WSL: `cb65f65b` (`Verify active subject code constraints before launch`)
- WSL: `79090dc6` (`Align CVRP postrun fixtures with calibration handoff`)

## Verification

Local:

```bash
PYTHONPATH=scion python -m py_compile \
  scion/tools/rebuild_prepared_handoff.py \
  scion/tools/check_launch_readiness.py
PYTHONPATH=scion pytest -q \
  scion/scion/tests/test_rebuild_prepared_handoff.py \
  scion/scion/tests/test_launch_readiness.py \
  scion/scion/tests/test_check_postrun_acceptance.py \
  scion/scion/tests/test_rebuild_postrun_acceptance.py \
  scion/scion/tests/test_postrun_analysis_brief.py \
  scion/scion/tests/test_postrun_artifact_inventory.py
```

Result: `170 passed in 38.99s`.

WSL:

```bash
PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion \
  /home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m py_compile \
  scion/tools/rebuild_prepared_handoff.py \
  scion/tools/check_launch_readiness.py
PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion \
  /home/xjy-ubuntu/miniconda3/envs/scion/bin/pytest -q \
  scion/scion/tests/test_rebuild_prepared_handoff.py \
  scion/scion/tests/test_launch_readiness.py \
  scion/scion/tests/test_check_postrun_acceptance.py \
  scion/scion/tests/test_rebuild_postrun_acceptance.py \
  scion/scion/tests/test_postrun_analysis_brief.py \
  scion/scion/tests/test_postrun_artifact_inventory.py
```

Result: `170 passed in 25.49s`.

## Refreshed Prepared Roots

Warehouse:

`/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-v2-followup-codepayload-79090dc6-6r-gpt55-20260619T194212Z-claw-6r-gpt55-20260619T194227Z-claw`

- WSL runtime commit: `79090dc6`
- Static readiness: `true`
- Launch readiness: `false`
- Completion preflight: HTTP `401`, `classification=not_authenticated`,
  `code=invalid_api_key`, auth pool `active=0`, `expired=1`, `total=1`
- Provider payload summary:
  `warehouse_operator_validation_transfer_code_constraints.v1`,
  constraints `5`, forbidden patterns `5`, total guidance items `10`

CVRP:

`/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-large-twoopt-codepayload-79090dc6-1r-gpt55-20260619T194212Z-claw-1r-gpt55-20260619T194241Z-claw`

- WSL runtime commit: `79090dc6`
- Static readiness: `true`
- Launch readiness: `false`
- Completion preflight: HTTP `401`, `classification=not_authenticated`,
  `code=invalid_api_key`, auth pool `active=0`, `expired=1`, `total=1`
- Provider payload summary:
  `cvrp_solver_design_code_constraints.v1`, constraints `2`,
  object-model hints `3`, API contracts `2`, forbidden patterns `6`,
  total guidance items `13`

## Current Blocker

The blocker is external WSL `gpt-5.5` provider auth, not Scion static
readiness. Do not launch either root until strict launch readiness reports
`launch_ready=true` with a successful real chat completion preflight.
