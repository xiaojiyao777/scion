# v0.4 Warehouse Follow-up Plateau Review Coverage

Date: 2026-06-18

## Purpose

The current warehouse `v2` prepared root is the next simple proof that Scion can
recover continuous useful research. Before launching it, the postrun analysis
contract needs regression coverage for the distinction between:

- prepared-only roots that cannot support a plateau conclusion;
- proposal quality blocks that cannot support a plateau conclusion;
- screened candidates that have not reached protocol evaluation; and
- protocol-evaluated candidates that are ready for plateau-vs-follow-up review.

## Change

- Added postrun analysis brief coverage for
  `protocol_evaluated_plateau_review_ready`.
- Added postrun analysis brief coverage for
  `screened_without_protocol_evaluation`.
- Refreshed the CVRP prepared-handoff rebuild test fixture so its
  problem-specific default-avoid/opportunity coverage matches the current
  large-instance two-opt contract.

## Boundary Check

- This is test/report coverage only.
- No campaign, scheduler, promotion, `DecisionFeatures`, Protocol gate, or
  problem solver behavior changed.
- Warehouse follow-up interpretation remains report-only delegated-review
  evidence. It does not become a deterministic promotion or plateau decision.

## Verification

```bash
PYTHONPATH=scion pytest -q scion/scion/tests/test_postrun_analysis_brief.py
# 9 passed

PYTHONPATH=scion pytest -q \
  scion/scion/tests/test_postrun_analysis_brief.py \
  scion/scion/tests/test_postrun_artifact_inventory.py \
  scion/scion/tests/test_warehouse_agentic_launcher.py \
  scion/scion/tests/test_rebuild_prepared_handoff.py \
  scion/scion/tests/test_launch_readiness.py
# 43 passed
```

## Acceptance

Accepted as a warehouse follow-up auditability repair. Once `gpt-5.5` auth is
restored, postrun review has regression coverage for the key warehouse
continuous-improvement question: protocol-evaluated evidence can enter plateau
review, while prepared-only, quality-blocked, and screened-only states cannot be
treated as plateau conclusions.
