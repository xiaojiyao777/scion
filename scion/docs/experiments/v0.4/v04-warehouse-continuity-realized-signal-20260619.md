# v0.4 Warehouse Continuity Realized-Signal Tightening

Date: 2026-06-19

## Purpose

Warehouse plateau review should require substantive continuity evidence before
calling protocol-evaluated evidence plateau-review-ready. A continuity
opportunity or branch-lesson requirement is not the same thing as an observed
follow-up, transferred lesson, or accepted weak-positive transfer.

## Change

`scion/tools/postrun_analysis_brief.py` now treats warehouse follow-up
continuity as substantive only when at least one of these is true:

- branch depth reaches at least `2`;
- a same-mechanism follow-up was selected;
- a branch lesson was satisfied;
- a weak-positive transfer was accepted.

Observed-but-unselected opportunities, unsatisfied branch-lesson requirements,
and unaccepted weak-positive opportunities remain visible in the summary, but
they no longer make `protocol_evaluated_plateau_review_ready` possible by
themselves.

## Boundary

This is postrun delegated-review evidence accounting only. It does not change
Decision, `DecisionFeatures`, Protocol gates, promotion, scheduler state,
proposal semantics, warehouse solver behavior, or runtime behavior.

## Verification

Local verification:

```bash
PYTHONPATH=scion pytest -q scion/scion/tests/test_postrun_analysis_brief.py -k 'warehouse_followup_summary'
# 9 passed, 17 deselected

PYTHONPATH=scion pytest -q \
  scion/scion/tests/test_postrun_analysis_brief.py \
  scion/scion/tests/test_check_postrun_acceptance.py
# 50 passed
```

WSL checkout `ca5a7eb`:

```bash
PYTHONPATH=scion \
  /home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m pytest -q \
  scion/scion/tests/test_postrun_analysis_brief.py \
  scion/scion/tests/test_check_postrun_acceptance.py
# 50 passed
```

## Acceptance

Accepted for the warehouse follow-up plateau-review readiness path. Realized
continuity evidence is required before a protocol-evaluated warehouse run can
be called plateau-review-ready.
