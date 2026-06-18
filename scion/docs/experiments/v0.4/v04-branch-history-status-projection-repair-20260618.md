# v0.4 Branch History Status Projection Repair - 2026-06-18

## Conclusion

Branch history cards now preserve compact lifecycle/status fields when a
terminal branch is reconstructed from step history rather than from a live
branch row. This closes the abandoned/parked history-card projection gap without
changing Decision, Protocol, scheduling, gates, budgets, or problem semantics.

## Repair

- Updated `scion/scion/core/evidence_recording/summary_branch_history.py`.
- History-card projection now fills `branch_code_status`, `lineage_status`,
  `active_slot_status`, `counts_toward_active_slots`, and
  `final_branch_classification` for reconstructed abandoned/parked/terminal
  cards.
- Existing live-card values remain authoritative when present.
- Abandoned cards derive terminal compact status from formal evidence when the
  branch row is unavailable, so regression evidence projects as
  `quality_regression` instead of an unknown compact status.

## Acceptance

- `PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion pytest -q scion/scion/tests/unit/core/test_evidence_recorder_summary_status.py -k "branch_history"`
  - `2 passed, 51 deselected`
- `PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion pytest -q scion/scion/tests/unit/core/test_evidence_recorder_summary_status.py`
  - `53 passed`
- `python -m py_compile scion/scion/core/evidence_recording/summary_branch_history.py scion/scion/tests/unit/core/test_evidence_recorder_summary_status.py`
- `git diff --check`

## Residual Caveat

This repair covers campaign-summary branch history cards. Long-running
in-flight `run_status.json` snapshots can still be too coarse during formal
screening and should be handled as a separate status-progress projection task.
