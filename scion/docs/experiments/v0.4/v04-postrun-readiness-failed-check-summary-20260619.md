# v0.4 Postrun Readiness Failed-Check Summary

Date: 2026-06-19

## Purpose

Postrun acceptance readiness already recorded per-check `status` and
`required` fields, but delegated reviewers still had to scan the full check map
to find why `current_run_analysis_ready=false`. This was noisy for warehouse and
CVRP follow-up review, where the postrun bundle intentionally contains many
report-only surfaces.

## Change

`check_postrun_acceptance.py` now emits report-only aggregate fields:

- `failed_required_checks`
- `failed_optional_checks`

Markdown output also prints the failed required list. This does not add a gate
or change `current_run_analysis_ready`; it exposes the existing required-check
state in a directly delegable shape.

## Verification

Local:

```bash
PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion \
  pytest -q scion/scion/tests/test_check_postrun_acceptance.py
# 43 passed
```

WSL:

```bash
cd /home/xjy-ubuntu/research/or-autoresearch-agent
PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion \
  /home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m pytest -q \
  scion/scion/tests/test_check_postrun_acceptance.py
# 43 passed
```

Real historical warehouse champion-v2 smoke:

```text
run_root=/home/clawd/research/scion-experiments/v04-warehouse-validation-transfer-contract-rerun6r-ce5d884-20260617T152944Z/rep01/full_context
delegation_ready=True
current_run_analysis_ready=False
failed_required_checks=[problem_summary_actionability, prompt_source_visibility_actionability]
failed_optional_checks=[postrun_report_status_marker]
```

The problem-summary failure is the expected warehouse handoff-incomplete
interpretation, now visible at the top level.

## Prepared Root Refresh

Because `scion/tools` is in the prepared-root runtime guard, the warehouse and
CVRP roots were refreshed from WSL runtime commit `2a1c996c`.

Warehouse:

`/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-v2-followup-postfails-2a1c996c-preflight-6r-gpt55-20260619T223801Z-claw`

Local mirror:

`/home/clawd/research/scion-experiments/v04-warehouse-v2-followup-postfails-2a1c996c-preflight-6r-gpt55-20260619T223801Z-claw`

CVRP:

`/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-large-twoopt-phase4-postfails-2a1c996c-preflight-4r-gpt55-20260619T223802Z-claw`

Local mirror:

`/home/clawd/research/scion-experiments/v04-cvrp-large-twoopt-phase4-postfails-2a1c996c-preflight-4r-gpt55-20260619T223802Z-claw`

WSL strict readiness for both roots:

```text
static_ready=True
launch_ready=False
failed_required_checks=[completion_preflight]
failed_static_required_checks=[]
completion_preflight=failed
http_status=401
classification=not_authenticated
code=invalid_api_key
auth_pool.active=0
auth_pool.refreshing=1
manifest.git.commit=2a1c996c
git_runtime_consistent=ok
```

## Boundary Check

- This is delegated-review reporting only.
- It does not change Decision, `DecisionFeatures`, Protocol gates, lifecycle,
  scheduler, promotion, proposal selection, or solver semantics.
- It makes postrun review failures easier to delegate and resume after the live
  warehouse and CVRP runs finish.

## Acceptance

Accepted as a v0.4 postrun-readiness auditability repair. Current prepared
roots remain launch-blocked only by external `gpt-5.5` completion preflight
auth; warehouse should launch first once strict launch readiness reports
`launch_ready=true`.
