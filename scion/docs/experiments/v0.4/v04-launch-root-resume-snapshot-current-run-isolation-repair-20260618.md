# Launch-Root Resume Snapshot Current-Run Isolation Repair

Date: 2026-06-18

## Purpose

Prevent prepared-only and pre-campaign-preflight-failed launch roots from
exposing copied resume-campaign branches, events, hypotheses, or LLM traces as
current-run evidence in the top-level postrun inventory.

The launcher lifecycle and Phase 4 coverage already marked these roots as
`current_run_evidence=false`, but a real WSL shell smoke showed that
`postrun_artifact_inventory.py` still populated top-level `branches`,
`events`, `hypotheses`, and `llm_traces` from the copied campaign snapshot.
That was too easy for delegated analysis to misread.

## Change

`postrun_artifact_inventory.py` now treats launch-only roots differently:

- top-level `branches`, `events`, `hypotheses`, and `llm_traces` represent only
  current-run evidence,
- prepared-only and preflight-failed roots zero those top-level current-run
  fields,
- copied campaign statistics move to an explicit `resume_snapshot` object with
  `current_run_evidence=false`,
- Markdown renders a `Resume Snapshot` section that says copied artifacts are
  launch input, not current-run evidence.

Normal postrun campaign inventories are unchanged.

## Boundary Check

This is report-only artifact accounting. It does not mutate campaign state,
scheduler state, promotion state, `DecisionFeatures`, Protocol evidence,
budgets, gates, lifecycle policy, or problem semantics.

## Verification

Focused local verification:

```bash
python -m py_compile \
  scion/tools/postrun_artifact_inventory.py \
  scion/tools/rebuild_postrun_acceptance.py \
  scion/tools/postrun_analysis_brief.py

PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion pytest -q \
  scion/scion/tests/test_postrun_artifact_inventory.py \
  scion/scion/tests/test_rebuild_postrun_acceptance.py \
  scion/scion/tests/test_postrun_analysis_brief.py
```

Result: `11 passed`.

The new inventory test covers a preflight-failed launch root with copied
campaign DB rows, copied formal candidate artifacts, and copied LLM traces. It
asserts that the top-level current-run evidence fields are empty while
`resume_snapshot` records the copied branch/event/hypothesis/trace counts.
