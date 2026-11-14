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
  - artifact fallback for older runs that lack status-projected readiness,
    using copied `problem-v1.yaml` plus compatible
    `scion.aa_noise_floor.v1` calibration artifacts;
  - `protocol_effects_vs_mde`, including row counts, positive/nonpositive
    counts, effect/MDE ratios, stage-level summaries, CI-high-below-MDE counts,
    and compact top rows by effect/MDE;
  - compact `research_shape` diagnostics, including branch-depth distribution,
    max/mean depth, active research-shape signal, and mechanism-family breadth;
  - compact `cross_branch_observability` counters for branch lessons,
    same-branch refinement allowance, weak-positive transfer, clean-fork
    contrast, near duplicates, and material-difference pressure.
- `scion/scion/tests/test_cli_report_research_efficiency.py` now asserts those
  fields are present, that effect/MDE interpretation is computed, that copied
  calibration fallback works for legacy artifacts, and that `calibration_ref`
  and raw metrics refs are not leaked through the compact readiness/effect
  rows.

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
PYTHONPATH=scion python -m scion.cli.main report research-efficiency --campaign-dir /home/clawd/research/scion-experiments/v04-cvrp-postpivot-guidance-agentic-1r-acc21ba-20260618T064210Z/campaign --output /tmp/scion-cvrp-acc21ba-research-efficiency-fallback.json
PYTHONPATH=scion python -m scion.cli.main report research-efficiency --campaign-dir /home/clawd/research/scion-experiments/v04-warehouse-validation-transfer-contract-rerun6r-ce5d884-20260617T152944Z/rep01/full_context/campaign --output /tmp/scion-warehouse-ce5d884-research-efficiency-fallback.json
```

Results:

- Research-efficiency CLI report tests: `4 passed`
- py_compile: passed
- Report plus research-shape focused regression: `4 passed`
- Cross-branch/lesson focused regression: `15 passed, 52 deselected`
- Real artifact smoke:
  - CVRP `acc21ba`: artifact fallback readiness `ready`, MDE `9.9`,
    `protocol_effects_vs_mde.interpretation=all_available_ci_high_below_mde`.
  - Warehouse `ce5d884`: artifact fallback readiness `ready`, MDE `577.5`,
    `protocol_effects_vs_mde.interpretation=has_positive_protocol_effect_at_or_above_mde`.
