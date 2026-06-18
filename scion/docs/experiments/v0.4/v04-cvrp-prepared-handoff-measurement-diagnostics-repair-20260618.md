# v0.4 CVRP Prepared Handoff Measurement Diagnostics Repair

Date: 2026-06-18

## Purpose

Ensure delegated postrun analysis and future resume points receive the same
CVRP measurement/opportunity guidance that hypothesis proposal context now
receives.

Before this repair, the CVRP prepared-run handoff carried default-avoid and
branch-continuation focus, but it did not carry the compact MDE/low-SNR
diagnostics or measurable opportunity classes added to CVRP proposal context.
That made subagent analysis more dependent on status docs or historical reports.

## Change

- `launch_cvrp_agentic_campaign.py` now writes
  `research_focus.measurement_opportunity_diagnostics` into the prepared-run
  manifest.
- The CVRP prepared research focus now includes:
  - metric `total_distance`;
  - `runtime_model=budget_exhausting`;
  - `pairing_validity=trajectory_divergent`;
  - practical screen delta `2.0`;
  - screening MDE `9.9`;
  - recommended minimum seeds `8`;
  - reason codes for low-SNR/MDE/runtime interpretation;
  - measurable opportunity classes for construction seed portfolios,
    destroy/repair selection, bounded local search, and acceptance/adaptive
    weighting.
- Prepared manifest markdown, prepared analysis briefs, and prepared artifact
  inventories now render those fields for delegated review.

## Boundary Check

- This is launch/handoff metadata only.
- It is marked proposal/delegated-analysis guidance and
  `decision_features_excluded`.
- It does not mutate campaign state, scheduler state, Decision, Protocol gates,
  lifecycle, or promotion.

## Verification

```bash
PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion pytest -q \
  scion/scion/tests/test_cvrp_agentic_launcher.py \
  scion/scion/tests/test_postrun_analysis_brief.py \
  scion/scion/tests/test_postrun_artifact_inventory.py
# 24 passed

PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion pytest -q \
  scion/scion/tests/test_cvrp_agentic_launcher.py \
  scion/scion/tests/test_warehouse_agentic_launcher.py \
  scion/scion/tests/test_launch_readiness.py \
  scion/scion/tests/test_rebuild_postrun_acceptance.py \
  scion/scion/tests/test_postrun_artifact_inventory.py \
  scion/scion/tests/test_postrun_analysis_brief.py
# 43 passed

PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion python -m py_compile \
  scion/tools/launch_cvrp_agentic_campaign.py \
  scion/tools/postrun_analysis_brief.py \
  scion/tools/postrun_artifact_inventory.py \
  scion/scion/tests/test_cvrp_agentic_launcher.py
```

## Acceptance

Accepted as a Phase 4 handoff/evidence-availability repair. The next prepared
CVRP root must be regenerated so its prepared manifest and delegated handoff
include these measurement diagnostics.
