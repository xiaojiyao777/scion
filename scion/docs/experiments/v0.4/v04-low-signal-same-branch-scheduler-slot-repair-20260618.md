# Low-Signal Same-Branch Scheduler Slot Repair

Date: 2026-06-18

## Summary

The scheduler already selected one low-signal same-branch sample before forcing
a clean fork, but the emitted `SchedulerAction.slot` still came from the
generic no-effect diagnostic classifier. That made
`same_branch_low_signal_observation_sample` appear as `repair_diagnostic` in
step results and scheduler lineage metadata.

This repair aligns the scheduler slot with the selected action: low-signal
same-branch observation samples now emit `refine_active`. True pending retries,
actionable diagnostics, runtime diagnostics, and telemetry repair paths still
use `repair_diagnostic`.

## Boundary Check

- No `DecisionFeatures` fields were changed.
- No protocol gate, lifecycle threshold, budget, truncation, or compression
  behavior was changed.
- The change is generic scheduler semantics; CVRP/warehouse problem facts stay
  outside core.
- The scheduler audit metadata remains proposal/reporting evidence and does not
  become Decision input.

## Changed Files

- `scion/scion/core/scheduler.py`
- `scion/scion/tests/unit/core/test_scheduler_runtime_evidence_pressure.py`
- `scion/scion/tests/unit/core/test_branch_step_runner_scheduler_metadata.py`

## Verification

Local:

```bash
python -m py_compile \
  scion/scion/core/scheduler.py \
  scion/scion/core/branch_step_runner.py
PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion pytest -q \
  scion/scion/tests/unit/core/test_scheduler_runtime_evidence_pressure.py \
  scion/scion/tests/unit/core/test_branch_step_runner_scheduler_metadata.py
PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion pytest -q \
  scion/scion/tests/test_scheduler.py \
  scion/scion/tests/unit/core/test_branch_lifecycle_policy.py \
  scion/scion/tests/unit/core/test_branch_hygiene_status.py \
  scion/scion/tests/unit/core/test_proposal_pipeline_hypothesis.py \
  scion/scion/tests/unit/test_branch_prompt_projection.py
```

Results:

- `43 passed`
- `128 passed`

## Acceptance

Accepted as a narrow v0.4 research-loop semantics repair. It prevents
low-signal retained branches from being reported to downstream audit/status
surfaces as repair work when the scheduler intentionally selected a
same-mechanism observation sample.
