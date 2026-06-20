# v0.4 Postrun Runtime Evidence Consistency Guard

Date: 2026-06-20

Status: accepted as a report-only postrun-readiness repair.

## Reason

The 2026-06-11 runtime audits require budget-exhausting runtime semantics to
stay auditable instead of being rendered as generic speed/regression feedback.
Postrun acceptance already compared runtime review readiness and drain status,
but it did not verify that problem summaries preserved runtime raw availability,
runtime model counts, or runtime budget diagnostic counts from the
`runtime_feedback_summary` input.

That left a small delegated-review gap: a problem summary could look review
ready while silently dropping the budget-exhausting runtime evidence needed to
interpret CVRP/warehouse results.

## Change

- `scion/tools/check_postrun_acceptance.py` now rejects stale problem-summary
  runtime evidence when raw availability, drain/review readiness, runtime model
  counts, or runtime budget diagnostic counts differ from the runtime-feedback
  review input.
- `scion/scion/tests/test_check_postrun_acceptance.py` adds a regression test
  where a warehouse summary hides `budget_exhausting` runtime diagnostics and is
  rejected by `problem_summary_input_consistency`.

Boundary: this is postrun/reporting validation only. It does not enter
`DecisionFeatures`, Protocol gates, scheduler state, promotion, or problem
solver semantics.

## Verification

Local:

- `python -m py_compile scion/tools/check_postrun_acceptance.py scion/scion/tests/test_check_postrun_acceptance.py`
- `PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion pytest -q scion/scion/tests/test_check_postrun_acceptance.py -k 'stale_runtime_evidence'`
  passed: `1 passed, 50 deselected`.
- `PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion pytest -q scion/scion/tests/test_check_postrun_acceptance.py`
  passed: `51 passed`.
- `PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion pytest -q scion/scion/tests/test_launch_readiness.py scion/scion/tests/test_check_postrun_acceptance.py scion/scion/tests/test_rebuild_prepared_handoff.py`
  passed: `142 passed`.

WSL:

- `PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion /home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m pytest -q scion/scion/tests/test_check_postrun_acceptance.py -k 'stale_runtime_evidence'`
  passed: `1 passed, 50 deselected`.
- `PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion /home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m pytest -q scion/scion/tests/test_launch_readiness.py scion/scion/tests/test_check_postrun_acceptance.py scion/scion/tests/test_rebuild_prepared_handoff.py`
  passed: `142 passed`.

Commits:

- Local: `f307b7c4`
- WSL runtime checkout: `3e0512f1`

## Prepared Root Refresh

Because `scion/tools` is part of the runtime guard set, the active prepared roots
were regenerated from WSL commit `3e0512f1` before launch:

- Warehouse:
  `/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-v2-followup-runtimeev-3e0512f1-preflight-6r-gpt55-20260620T014618Z-claw`
- CVRP:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-large-twoopt-phase4-runtimeev-3e0512f1-preflight-4r-gpt55-20260620T014619Z-claw`

Both roots were mirrored locally under `/home/clawd/research/scion-experiments/`.
Strict launch readiness for both roots reports:

- `static_ready=true`
- `launch_ready=false`
- `failed_static_required_checks=[]`
- `failed_required_checks=["completion_preflight"]`
- completion preflight HTTP `401`, `classification=not_authenticated`,
  `code=invalid_api_key`, auth pool `active=0`, `expired=1`, `total=1`

No campaign was launched. Refresh the WSL/local proxy login and rerun strict
launch readiness before starting warehouse, then CVRP.
