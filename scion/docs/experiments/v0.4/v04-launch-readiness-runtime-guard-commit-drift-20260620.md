# v0.4 Launch Readiness Runtime Guard Commit Drift

Date: 2026-06-20

## Purpose

Close an operator-facing launch-readiness gap: `run.sh` already rejected
prepared roots when committed runtime/control-plane/problem code changed after
prepare time, but `check_launch_readiness.py` did not recompute that committed
drift before reporting readiness. Launch readiness now matches the wrapper
semantics before launch.

## Change

- `scion/tools/check_launch_readiness.py`
  - Adds required check `git_runtime_guard_commit_consistent`.
  - If the current checkout commit equals the prepared manifest commit, the
    check passes.
  - If commits differ, readiness runs `git diff --quiet <prepared> HEAD --`
    over the prepared `runtime_guard_paths`.
  - Test/docs-only commit drift passes when guarded paths are unchanged.
  - Committed drift under guarded runtime/control-plane/problem paths fails
    readiness before launch.
- `scion/scion/tests/test_launch_readiness.py`
  - Covers committed guarded-path drift rejection.
  - Covers committed docs-only drift allowance.

## Verification

Local commit: `6a745062`.

```text
PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion pytest -q \
  scion/scion/tests/test_launch_readiness.py
# 85 passed in 6.30s
```

```text
PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion pytest -q \
  scion/scion/tests/test_rebuild_prepared_handoff.py \
  scion/scion/tests/test_launch_readiness.py \
  scion/scion/tests/test_postrun_analysis_brief.py \
  scion/scion/tests/test_check_postrun_acceptance.py \
  scion/scion/tests/test_cli_report_research_efficiency.py
# 170 passed in 44.35s
```

WSL commit: `576209e8`.

```text
cd /home/xjy-ubuntu/research/or-autoresearch-agent
PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion \
  /home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m pytest -q \
  scion/scion/tests/test_rebuild_prepared_handoff.py \
  scion/scion/tests/test_launch_readiness.py \
  scion/scion/tests/test_postrun_analysis_brief.py \
  scion/scion/tests/test_check_postrun_acceptance.py \
  scion/scion/tests/test_cli_report_research_efficiency.py
# 170 passed in 29.19s
```

## Current Prepared Roots

WSL runtime commit: `576209e8`.

Warehouse:

`/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-v2-followup-runtimeguard-576209e8-preflight-6r-gpt55-20260620T000946Z-claw`

Local mirror:

`/home/clawd/research/scion-experiments/v04-warehouse-v2-followup-runtimeguard-576209e8-preflight-6r-gpt55-20260620T000946Z-claw`

CVRP:

`/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-large-twoopt-phase4-runtimeguard-576209e8-preflight-4r-gpt55-20260620T000948Z-claw`

Local mirror:

`/home/clawd/research/scion-experiments/v04-cvrp-large-twoopt-phase4-runtimeguard-576209e8-preflight-4r-gpt55-20260620T000948Z-claw`

Strict launch readiness for both roots:

```text
static_ready=True
launch_ready=False
failed_required_checks=[completion_preflight]
failed_static_required_checks=[]
git_runtime_guard_commit_consistent=ok
completion_preflight=failed
http_status=401
classification=not_authenticated
code=invalid_api_key
auth_pool.active=0
auth_pool.refreshing=1
auth_pool.total=1
```

## Boundary Check

- The repair is launch/readiness control-plane logic.
- It does not change Decision, `DecisionFeatures`, Protocol gates, promotion,
  scheduler state, or solver semantics.
- Problem semantics remain in problem-owned packages and postrun review paths.

## Acceptance

Accepted as a v0.4 launch-readiness repair. Active prepared roots were
refreshed from WSL runtime commit `576209e8`; launch remains blocked only by
external `gpt-5.5` completion auth.
