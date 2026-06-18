# v0.4 Research Continuity Brief Shape Projection Repair

Date: 2026-06-18

## Purpose

R3/R4 require postrun review to inspect branch depth and mechanism continuity,
not only whether one run promoted. `research-efficiency` reports already emit
research-shape diagnostics such as branch-depth distribution and active
mechanism-family breadth, but the delegated postrun analysis brief only showed
max depth and family count. That made shallow-scattered search look too similar
to real within-branch depth.

## Change

- `postrun_analysis_brief.py` now carries top-level `research_shape` diagnostics
  through each `research_continuity_summary` entry.
- The brief now computes a report-only research-continuity aggregate with:
  branch-depth distribution, max/mean depth, active shape counts, active branch
  and mechanism-family maxima, and mechanism-family observation counts.
- Markdown briefs now display those fields in `Research Continuity Summary`,
  including per-report depth distribution and active shape.

This is report-only. It does not change Decision, `DecisionFeatures`, Protocol
gates, lifecycle, scheduler, promotion, proposal selection, or problem
semantics.

## Verification

```bash
PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion pytest -q \
  scion/scion/tests/test_postrun_analysis_brief.py
# 6 passed in 0.27s

PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion pytest -q \
  scion/scion/tests/test_postrun_artifact_inventory.py \
  scion/scion/tests/test_rebuild_postrun_acceptance.py
# 13 passed in 1.29s

PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion pytest -q \
  scion/scion/tests/test_cli_report_research_efficiency.py \
  scion/scion/tests/unit/core/test_evidence_recorder_summary_status.py \
  -k 'research_shape or cross_branch or lesson'
# 1 passed, 56 deselected in 0.53s
```

## Acceptance

Accepted as a delegated-analysis evidence projection repair. Future postrun
briefs can distinguish a single deep branch from many shallow one-off branches
when reviewing CVRP/warehouse research continuity.
