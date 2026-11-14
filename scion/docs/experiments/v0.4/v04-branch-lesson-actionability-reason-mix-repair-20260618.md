# v0.4 Branch Lesson Actionability Reason-Mix Repair

Date: 2026-06-18

## Purpose

Improve postrun delegated review of prior-evidence transfer without changing
runtime decisions. Before this repair,
`research_context_actionability_summary` exposed total branch-lesson semantic
failure/block counts, but it did not carry the reason distribution into the
joined prompt/context actionability surface. A reviewer could see that prior
evidence transfer failed, but still had to chase lower-level continuity reports
to distinguish metadata-only payloads, unrecognized target/action/mechanism
linkage, and true semantic mismatch.

## Change

- `research_context_actionability_summary.indicators` now includes:
  - `branch_lesson_semantic_failure_counts`
  - `branch_lesson_semantic_block_counts`
- The Markdown brief now renders:
  - branch lesson semantic failure mix
  - branch lesson semantic block mix
- Recommendations now include reason-specific report-only follow-up:
  - inspect metadata-only `branch_lesson_usage` payloads
  - normalize target/action/mechanism linkage aliases
  - inspect lesson ids, changed dimensions, and borrow/contrast/reject semantics

## Boundary Check

This is postrun analysis only:

- `quality_judgment=false`
- `decision_features_excluded=true`
- no campaign, scheduler, promotion, gate, or `DecisionFeatures` behavior
  changes
- no CVRP/warehouse-specific semantics added to generic Decision input

## Verification

```bash
PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion \
python -m py_compile scion/tools/postrun_analysis_brief.py

PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion \
pytest -q \
  scion/scion/tests/test_postrun_analysis_brief.py \
  scion/scion/tests/test_cli_report_research_efficiency.py \
  scion/scion/tests/unit/core/test_cross_branch_observability.py \
  scion/scion/tests/unit/core/test_branch_lesson_usage.py
```

Result:

- `py_compile`: passed.
- Focused tests: `55 passed`.

## Residual Risk

This does not prove a live agent will use prior evidence correctly. It improves
the postrun audit path so the main session and delegated reviewers can identify
why prior-evidence use failed and decide whether the next fix belongs in prompt
context, branch-lesson schema aliases, or hypothesis semantics.
