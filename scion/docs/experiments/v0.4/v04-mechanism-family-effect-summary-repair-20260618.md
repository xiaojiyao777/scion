# v0.4 Mechanism Family Effect Summary Repair

Date: 2026-06-18

## Purpose

R3 requires postrun review to reconstruct mechanism continuity and mechanism
effect shape, not only branch depth or aggregate promotion status. The previous
briefs exposed branch-depth distribution and mechanism-family breadth, and
separately exposed effect-vs-MDE rows, but delegated review still had to infer
whether a family had positive, negative, or sub-MDE evidence.

## Change

- Campaign research-shape diagnostics now include a report-only
  `branch_mechanism_family_map` derived from step history, branch rows, and
  branch history cards.
- `research-efficiency` reports now attach `mechanism_family` to sanitized
  effect rows and emit a report-only `mechanism_family_effect_summary`.
- `postrun_analysis_brief.py` now aggregates mechanism-family mapped/unmapped
  protocol rows and renders a compact family x effect table.

This is report/control-plane evidence only. It does not change Decision,
`DecisionFeatures`, Protocol gates, lifecycle, scheduler, promotion, proposal
context, campaign execution, or problem semantics.

## Verification

```bash
PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion pytest -q \
  scion/scion/tests/test_cli_report_research_efficiency.py \
  scion/scion/tests/test_postrun_analysis_brief.py \
  scion/scion/tests/test_postrun_artifact_inventory.py \
  scion/scion/tests/test_rebuild_postrun_acceptance.py
# 23 passed in 1.61s

PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion pytest -q \
  scion/scion/tests/unit/core/test_evidence_recorder_summary_status.py \
  -k 'research_shape or cross_branch or summary_status'
# 53 passed in 1.22s

PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion python -m py_compile \
  scion/scion/core/research_efficiency_report.py \
  scion/scion/core/evidence_recording/research_shape_diagnostics.py \
  scion/tools/postrun_analysis_brief.py \
  scion/scion/tests/test_cli_report_research_efficiency.py \
  scion/scion/tests/test_postrun_analysis_brief.py \
  scion/scion/tests/unit/core/test_evidence_recorder_summary_status.py
# clean
```

## Acceptance

Accepted as an R3/R4 delegated-analysis repair. Future postrun briefs can show
whether protocol effects came from the same mechanism family, whether rows were
unmapped, and whether a family produced above-MDE, below-MDE, positive, or
nonpositive evidence.
