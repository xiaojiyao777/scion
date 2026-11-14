# v0.4 Research-Continuity Report Metrics Repair

Date: 2026-06-18

## Purpose

Phase 4/5 acceptance asks whether repaired Scion actually supports branch depth,
same-mechanism follow-up, and useful cross-branch transfer. The existing
research-efficiency report exposed the underlying observability counters, but a
postrun reviewer still had to reconstruct the main rates by hand.

This repair adds a report-only `research_continuity` block to
`research_efficiency_report.v1.json`.

## Boundary

- Report-only: yes.
- Decision input: no.
- Mutates campaign, scheduler, lifecycle, protocol, promotion, proposal context,
  or problem semantics: no.
- Source data: existing `campaign_summary.json` / `status.json`
  `cross_branch_research_observability` and `research_shape_diagnostics`.

The block remains outside `DecisionFeatures`; it is postrun audit material for
humans and delegated analysis agents.

## Added Metrics

- `same_mechanism_followup`: selected and not-selected same-branch refinement
  opportunity counts, selection rate, and interpretation.
- `branch_lesson_usage`: requirement, present, satisfied, missing-block,
  semantic-gap counts and rates.
- `weak_positive_transfer`: accepted/rejected weak-positive transfer counts and
  acceptance rate.
- `lesson_action_counts`: borrowed, avoided, contrasted, preserved same-branch,
  and clean-fork contrast counts.
- `research_shape_summary`: max/mean depth, depth distribution, active shape,
  and mechanism-family breadth summary.

## Changed Files

- `scion/scion/core/research_efficiency_report.py`
- `scion/scion/tests/test_cli_report_research_efficiency.py`
- `scion/TASK.md`
- `scion/docs/status/current-state.md`
- `scion/docs/status/v0.4-history.md`
- `scion/docs/planning/v0.4/v0.4-evidence-repair-and-validation-plan-20260611.md`

## Verification

```bash
PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion pytest -q scion/scion/tests/test_cli_report_research_efficiency.py
python -m py_compile scion/scion/core/research_efficiency_report.py
```

Result: `4 passed`.

## Notes

`current-state.md` was also shortened so it remains an operational resume point
rather than an append-only list of repair reports. Detailed evidence stays in
`scion/docs/experiments/v0.4/`, while `v0.4-history.md` remains a curated
milestone index.
