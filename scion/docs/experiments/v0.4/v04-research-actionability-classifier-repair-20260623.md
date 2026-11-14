# v0.4 Research Actionability Classifier Repair

Date: 2026-06-23

## Summary

The accepted target-intent authority validation root exposed two postrun
research-context actionability false positives:

- accepted clean-fork policy choices were counted as missed same-mechanism
  opportunities;
- voluntary `branch_lesson_usage` without an active requirement was counted as
  a semantic gap.

This repair stays report-only and problem-neutral. It does not mutate campaign,
scheduler, Protocol, promotion, or `DecisionFeatures` state.

## Changes

- `scion/scion/core/evidence_recording/actionability_classification.py`
  classifies same-branch followup metadata into selected followup, true missed
  followup, and accepted clean-fork policy choices.
- `scion/scion/core/evidence_recording/cross_branch_observability.py` records
  the accepted clean-fork policy-choice diagnostic count in summary/status
  observability.
- `scion/scion/core/research_efficiency_report.py` computes branch-lesson
  semantic gaps from explicit semantic failure/block counts instead of
  `present_count - satisfied_count` or global requirement projection deltas.
- Completed summaries with older same-mechanism counters can be reclassified
  from their step scheduler metadata during report generation.

## Validation Roots

CVRP source root:

`/home/clawd/research/scion-experiments/v04-cvrp-authority-542d1f99-postweakpressure-4r-gpt55-20260623T055230Z-claw`

A temporary postrun acceptance rebuild using the current worktree completed all
families and reported:

- `actionability_gaps=[]`
- `same_mechanism_selected=3`
- `same_mechanism_observed=3`
- `same_mechanism_missed=0`
- `branch_lesson_semantic_gap_count=0`
- `branch_lesson_semantic_failure_count=0`
- `accepted_clean_fork_policy_choice_count=1`

This changes only the delegated-review/actionability interpretation. The root
remains framework evidence rather than solver progress: champion stayed `v1`,
there were 0 promotions, and the current Protocol rows remained below CVRP MDE.

Warehouse source root:

`/home/xjy-ubuntu/research/scion-experiments/v04-wh-v2-60029d30-apsretry-6r-gpt55-20260622T014615Z-claw`

A temporary WSL postrun acceptance rebuild using conda `scion` also completed
all families and reported:

- `actionability_gaps=[]`
- `same_mechanism_selected=6`
- `same_mechanism_observed=6`
- `same_mechanism_missed=0`
- `branch_lesson_semantic_gap_count=0`
- `branch_lesson_semantic_failure_count=0`
- `accepted_clean_fork_policy_choice_count=4`

The warehouse root remains current-run-ready partial evidence, not a completed
continuous-optimization conclusion: it stopped at
`repeated_quality_block_signature`, champion stayed `v2`, and no promotion was
made in that run.

## Tests

Local focused checks:

```bash
PYTHONPATH=scion python -m pytest -q \
  scion/scion/tests/unit/core/test_cross_branch_actionability_observability.py \
  scion/scion/tests/unit/core/test_cross_branch_observability.py \
  scion/scion/tests/test_cli_report_research_efficiency.py \
  scion/scion/tests/test_postrun_analysis_brief.py \
  scion/scion/tests/test_check_postrun_acceptance.py \
  -k 'research_context_actionability or branch_lesson or same_mechanism or research_continuity or cross_branch_observability or research_efficiency_report'
```

Result: `28 passed, 119 deselected`.

```bash
python -m py_compile \
  scion/scion/core/evidence_recording/actionability_classification.py \
  scion/scion/core/evidence_recording/cross_branch_observability.py \
  scion/scion/core/research_efficiency_report.py \
  scion/scion/tests/unit/core/test_cross_branch_actionability_observability.py \
  scion/scion/tests/unit/core/test_cross_branch_observability.py \
  scion/scion/tests/test_cli_report_research_efficiency.py
git diff --check
```

Result: passed.

## Boundary

The classifier reads generic scheduler/actionability metadata and
branch-lesson requirement/failure counters only. It does not interpret
CVRP/warehouse mechanism semantics, case ids, BKS/gap facts, raw proposal text,
or prompt contents as decision features.
