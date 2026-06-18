# v0.4 Branch Lesson Semantic Diagnostics Brief Repair

Date: 2026-06-18

## Purpose

R3/R4 require postrun analysis to reconstruct whether follow-up hypotheses used
prior evidence, not merely whether a same-branch follow-up slot was selected.
The existing observability layer already counted branch-lesson usage failures
such as metadata-only payloads, unrecognized linkage, and semantic mismatch,
but the delegated postrun brief only surfaced a coarse semantic-gap count.

## Change

- `research-efficiency` now includes report-only branch-lesson semantic failure
  and block distributions under `research_continuity.branch_lesson_usage`.
- `postrun_analysis_brief.py` now aggregates those distributions and renders
  compact branch-lesson semantic failure, semantic block, and lesson-action
  summaries.
- The projection remains sanitized: no raw prompt text, raw LLM response,
  lesson body, patch body, or `DecisionFeatures` input is exposed.

This is report/control-plane evidence only. It does not change Decision,
`DecisionFeatures`, Protocol gates, lifecycle, scheduler, promotion, proposal
context, campaign execution, or problem semantics.

## Verification

```bash
PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion pytest -q \
  scion/scion/tests/test_cli_report_research_efficiency.py \
  scion/scion/tests/test_postrun_analysis_brief.py \
  -k 'research_efficiency or postrun_analysis_brief'
# 10 passed in 0.83s

PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion pytest -q \
  scion/scion/tests/test_cli_report_research_efficiency.py \
  scion/scion/tests/test_postrun_analysis_brief.py \
  scion/scion/tests/test_postrun_artifact_inventory.py \
  scion/scion/tests/test_rebuild_postrun_acceptance.py
# 23 passed in 1.49s

PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion python -m py_compile \
  scion/scion/core/research_efficiency_report.py \
  scion/tools/postrun_analysis_brief.py \
  scion/scion/tests/test_cli_report_research_efficiency.py \
  scion/scion/tests/test_postrun_analysis_brief.py
# clean
```

## Acceptance

Accepted as an R3/R4 delegated-analysis repair. Future postrun briefs can show
whether missing branch-lesson transfer came from absence, metadata-only output,
unrecognized linkage, or semantic mismatch.
