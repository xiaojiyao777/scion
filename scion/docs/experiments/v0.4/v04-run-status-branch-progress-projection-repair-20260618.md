# v0.4 Run Status Branch Progress Projection Repair - 2026-06-18

## Conclusion

`run_status.json` now projects compact branch lifecycle/status fields directly
onto `current_progress` and `in_flight_protocol` during long formal protocol
work. This resolves the remaining status-progress projection caveat after the
branch-history card repair.

## Repair

- Updated `scion/scion/core/evidence_recording/status.py`.
- Updated `scion/scion/core/campaign.py`.
- `current_progress` and `in_flight_protocol` now sync these branch-card fields
  when a matching branch row is available:
  `branch_code_status`, `active_slot_status`, `counts_toward_active_slots`,
  `current_head_active_slot_release_reason`, `final_branch_classification`,
  `branch_final_classification`, `branch_next_action`, and
  `branch_classification_reason`.
- Existing `branch_card` payloads remain available for full detail; the repair
  makes the compact fields visible at the top level for status monitors and
  humans reading partial run state.

## Acceptance

- `PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion pytest -q scion/scion/tests/unit/core/test_evidence_recorder_summary_status.py -k "syncs_current_progress_checkpoint"`
  - `1 passed, 52 deselected`
- `PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion pytest -q scion/scion/tests/unit/core/test_evidence_recorder_summary_status.py`
  - `53 passed`
- `python -m py_compile scion/scion/core/evidence_recording/status.py scion/scion/core/campaign.py scion/scion/tests/unit/core/test_evidence_recorder_summary_status.py`
- `git diff --check`

## Boundary Check

This is report/status projection only. It does not change Decision,
`DecisionFeatures`, Protocol, scheduling, gates, budgets, lifecycle decisions,
or problem-owned semantics.
