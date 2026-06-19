# v0.4 Prepared Root Refresh After Review-Input Boundary Guard

Date: 2026-06-19

## Purpose

Postrun acceptance readiness now requires current-run review-input summaries to
preserve report-only, non-quality-judgment, and `DecisionFeatures`-excluded
boundary markers. That change touched `scion/tools/check_postrun_acceptance.py`,
which is part of the prepared-root runtime guard set, so the unstarted
warehouse and CVRP prepared roots were regenerated before launch.

## Boundary Check

- This is delegated-review readiness validation only.
- It does not change Decision, `DecisionFeatures`, Protocol gates, lifecycle,
  scheduler, promotion, proposal selection, or solver semantics.
- CVRP and warehouse semantics remain in problem-owned prepared/postrun summary
  layers.

## Current Prepared Roots

WSL checkout: `85617a0`

- Warehouse:
  `/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-v2-followup-boundaryguard-85617a0-6r-gpt55-20260619T084748Z-claw`
- CVRP:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-large-twoopt-boundaryguard-85617a0-1r-gpt55-20260619T084801Z-claw`

Both roots are prepare-only and not started.

## Readiness Evidence

Both roots report:

- `static_ready=true`
- `launch_ready=false`
- `prepared_analysis_brief_current=ok`
- `prompt_context_readiness_complete=ok`
- `problem_specific_prepared_handoff=ok`
- `postrun_families_complete=ok`
- `run_script_strict_postrun_readiness=ok`
- `git_runtime_consistent=ok`
- `run_script_runtime_guard_enforced=ok`
- `run_script_postrun_reports_after_campaign=ok`
- `run_script_data_root_failure_reports=ok`
- `run_script_api_key_env_failure_reports=ok`
- `runtime_guard_paths_cover_launch_tools=ok`
- `runtime_guard_paths_cover_problem_runtime=ok`
- completion preflight `failed`, HTTP `401`, `code=invalid_api_key`
- auth pool `active=0`, `expired=1`, `total=1`

The current blocker remains external `gpt-5.5` auth, not prepared-root static
readiness.

## Verification

Local:

```bash
PYTHONPATH=scion pytest -q \
  scion/scion/tests/test_check_postrun_acceptance.py \
  scion/scion/tests/test_postrun_analysis_brief.py \
  scion/scion/tests/test_rebuild_postrun_acceptance.py \
  scion/scion/tests/test_postrun_artifact_inventory.py \
  scion/scion/tests/test_decision_feature_extraction.py
# 93 passed
```

WSL:

```bash
PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion \
  /home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m pytest -q \
  scion/scion/tests/test_check_postrun_acceptance.py \
  scion/scion/tests/test_postrun_analysis_brief.py \
  scion/scion/tests/test_rebuild_postrun_acceptance.py \
  scion/scion/tests/test_postrun_artifact_inventory.py \
  scion/scion/tests/test_decision_feature_extraction.py
# 93 passed
```

## Acceptance

Accepted as the current prepared-root refresh after the review-input boundary
guard. Do not launch either root until strict launch readiness reports
`launch_ready=true`.
