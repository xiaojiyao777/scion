# v0.4 Prompt Signal Density Coverage Repair

Date: 2026-06-18

## Purpose

R4 requires prompt manifests to report problem-domain signal density without
hiding source/code context. Postrun analysis briefs already aggregate prompt
block-family signal density, but Phase 4 artifact inventories did not expose
that evidence as a separate coverage requirement. A delegated reviewer could
therefore see source visibility coverage while missing that prompt signal
density itself was absent.

## Change

- Added Phase 4 inventory requirement `prompt_signal_density`.
- The requirement is satisfied only when proposal trajectory manifests include
  prompt block-family accounting from `block_family_summary` or
  `block_family_accounting`.
- Prepared-only and preflight-failed launch roots report the requirement as
  unavailable with the existing "not current-run evidence" reason.
- The field is report-only and remains outside `DecisionFeatures`, Protocol
  gates, lifecycle, scheduler, and promotion.

No runtime decision behavior changed.

## Verification

Focused check:

```bash
PYTHONPATH=scion pytest -q \
  scion/scion/tests/test_postrun_artifact_inventory.py::test_inventory_json_with_db_trace_index_and_traces \
  scion/scion/tests/test_postrun_artifact_inventory.py::test_phase4_coverage_separates_generic_and_code_source_visibility
```

Local result: `2 passed in 0.15s`.

Adjacent postrun acceptance sweep:

```bash
PYTHONPATH=scion pytest -q \
  scion/scion/tests/test_postrun_artifact_inventory.py \
  scion/scion/tests/test_postrun_analysis_brief.py \
  scion/scion/tests/test_rebuild_postrun_acceptance.py
```

Local result: `17 passed in 1.34s`.

## Acceptance

Accepted as an R4 evidence-coverage repair. Future postrun inventories now make
prompt signal-density evidence independently auditable instead of bundling it
under generic prompt/source visibility.
