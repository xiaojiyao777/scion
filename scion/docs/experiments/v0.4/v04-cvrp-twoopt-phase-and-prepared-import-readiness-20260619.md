# v0.4 CVRP Two-Opt Phase And Prepared Import Readiness

Date: 2026-06-19

## Purpose

Close two launch-blocking audit gaps found while rechecking the CVRP
large-twoopt delegated-review path.

1. `cvrp_large_twoopt_summary` accepted generic phase telemetry as the phase
   leg of direct evidence. Bounded two-opt review readiness now requires
   two-opt-specific phase telemetry on the same matching top effect row.
2. Prepared handoff rebuild and launch readiness could import an installed or
   stale Scion package when invoked without `PYTHONPATH`, making the warehouse
   active-subject code-constraint provider payload appear empty. Both tools now
   add the current checkout's `scion/` package directory to `sys.path`.

## Changes

- `scion/tools/postrun_analysis_brief.py`
  - Replaced generic phase detection for CVRP large two-opt direct evidence with
    two-opt-specific bucket/improvement-count matching.
  - Generic `runtime_observed_pairs` or unrelated `construction` /
    `local_search` telemetry no longer satisfies bounded two-opt review-ready
    evidence.
- `scion/tools/rebuild_prepared_handoff.py`
- `scion/tools/check_launch_readiness.py`
  - Self-locate the current checkout package path before importing
    problem-owned providers.

## Verification

Local:

```text
PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion pytest -q \
  scion/scion/tests/test_rebuild_prepared_handoff.py \
  scion/scion/tests/test_launch_readiness.py \
  scion/scion/tests/test_postrun_analysis_brief.py \
  scion/scion/tests/test_check_postrun_acceptance.py
# 157 passed in 38.70s
```

WSL:

```text
cd /home/xjy-ubuntu/research/or-autoresearch-agent
PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion \
  /home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m pytest -q \
  scion/scion/tests/test_rebuild_prepared_handoff.py \
  scion/scion/tests/test_launch_readiness.py \
  scion/scion/tests/test_postrun_analysis_brief.py \
  scion/scion/tests/test_check_postrun_acceptance.py
# 157 passed in 26.60s
```

## Current Prepared Roots

WSL runtime commit: `8ca17e34`.

Warehouse:

`/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-v2-followup-twooptphaseimport-8ca17e34-preflight-6r-gpt55-20260619T230608Z-claw`

Local mirror:

`/home/clawd/research/scion-experiments/v04-warehouse-v2-followup-twooptphaseimport-8ca17e34-preflight-6r-gpt55-20260619T230608Z-claw`

CVRP:

`/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-large-twoopt-phase4-twooptphaseimport-8ca17e34-preflight-4r-gpt55-20260619T230622Z-claw`

Local mirror:

`/home/clawd/research/scion-experiments/v04-cvrp-large-twoopt-phase4-twooptphaseimport-8ca17e34-preflight-4r-gpt55-20260619T230622Z-claw`

Strict launch readiness for both roots:

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
git_runtime_consistent=ok
prompt_context_readiness_complete=ok
```

## Boundary Check

- Both repairs are control-plane/report-only evidence guards.
- They do not change Decision, `DecisionFeatures`, Protocol gates, promotion,
  scheduler state, or solver semantics.
- CVRP/warehouse semantics remain problem-owned provider or postrun-review
  logic.

## Acceptance

Accepted as a v0.4 readiness/evidence repair. The prepared roots are statically
ready; launch remains blocked only by external `gpt-5.5` completion auth.
