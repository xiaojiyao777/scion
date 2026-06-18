# v0.4 Research-Efficiency Observability Projection Repair - 2026-06-18

## Conclusion

`campaign_summary.json` and `status.json` already carried cross-branch
observability and research-shape diagnostics, but
`report research-efficiency` only summarized accounting and failure taxonomy.
Postrun acceptance still needed manual joins across artifacts to answer Phase 4
questions about branch depth, same-branch lesson use, refinement allowance,
measurement readiness, and whether protocol effects exceeded the A/A MDE.

The research-efficiency report now projects those existing deterministic,
report-only fields directly.

## Repair

- `scion/scion/core/research_efficiency_report.py` now includes:
  - reduced `measurement_readiness`;
  - `protocol_effects_vs_mde`, including row counts, positive/nonpositive
    counts, effect/MDE ratios, stage-level summaries, CI-high-below-MDE counts,
    and compact top rows by effect/MDE;
  - compact `research_shape` diagnostics, including branch-depth distribution,
    max/mean depth, active research-shape signal, and mechanism-family breadth;
  - compact `cross_branch_observability` counters for branch lessons,
    same-branch refinement allowance, weak-positive transfer, clean-fork
    contrast, near duplicates, and material-difference pressure.
- `scion/scion/tests/test_cli_report_research_efficiency.py` now asserts those
  fields are present, that effect/MDE interpretation is computed, and that
  `calibration_ref` and raw metrics refs are not leaked through the compact
  readiness/effect rows.

## Boundary Check

This is report-only projection. It reads existing summary/status artifacts and
does not mutate campaign, scheduler, protocol, promotion, lifecycle, gates,
budgets, problem semantics, proposal context, or `DecisionFeatures`. The report
continues to mark `decision_features_excluded=true`.

## Acceptance

Commands run from `/home/clawd/research/or-autoresearch-agent`:

```bash
PYTHONPATH=scion pytest -q scion/scion/tests/test_cli_report_research_efficiency.py
python -m py_compile scion/scion/core/research_efficiency_report.py scion/scion/tests/test_cli_report_research_efficiency.py
PYTHONPATH=scion pytest -q scion/scion/tests/test_cli_report_research_efficiency.py scion/scion/tests/unit/core/test_evidence_recorder_summary_status.py::test_campaign_summary_and_status_report_research_shape_diagnostics
PYTHONPATH=scion pytest -q scion/scion/tests/unit/core/test_cross_branch_observability.py scion/scion/tests/unit/core/test_evidence_recorder_summary_status.py -k "research_shape or cross_branch or lesson"
```

Results:

- Research-efficiency CLI report tests: `3 passed`
- py_compile: passed
- Report plus research-shape focused regression: `4 passed`
- Cross-branch/lesson focused regression: `15 passed, 52 deselected`
