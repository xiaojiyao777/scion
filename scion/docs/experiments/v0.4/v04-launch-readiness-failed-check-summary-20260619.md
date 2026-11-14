# v0.4 Launch Readiness Failed-Check Summary

Date: 2026-06-19

## Purpose

Strict launch readiness is the operator-facing authority before starting
warehouse or CVRP. The detailed `checks` map already carried per-check status,
but the top-level JSON did not summarize which required checks failed. That made
resume-time diagnosis noisier, especially while the only launch blocker is the
external `gpt-5.5` completion preflight.

## Change

`check_launch_readiness.py` now emits report-only aggregate fields:

- `failed_required_checks`
- `failed_static_required_checks`
- `failed_optional_checks`

`failed_static_required_checks` excludes `completion_preflight`, so a prepared
root can show `static_ready=true` and still clearly report that launch is blocked
only by completion auth. Markdown output also prints the failed required list.

This does not add a gate or change readiness semantics. It only exposes the
existing required-check state in a more directly actionable shape.

## Verification

Local:

```bash
PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion \
  pytest -q scion/scion/tests/test_launch_readiness.py
# 82 passed
```

WSL:

```bash
cd /home/xjy-ubuntu/research/or-autoresearch-agent
PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion \
  /home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m pytest -q \
  scion/scion/tests/test_launch_readiness.py
# 82 passed
```

## Prepared Root Refresh

Because `scion/tools` is in the prepared-root runtime guard, the warehouse and
CVRP roots were refreshed from WSL commit `ecf3a2d4`.

Warehouse:

`/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-v2-followup-failsummary-ecf3a2d4-preflight-6r-gpt55-20260619T222606Z-claw`

CVRP:

`/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-large-twoopt-phase4-failsummary-ecf3a2d4-preflight-4r-gpt55-20260619T222606Z-claw`

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
auth_pool.refreshing=1
manifest.git.commit=ecf3a2d4
```

The roots were mirrored locally under `/home/clawd/research/scion-experiments/`.
Local mirror readiness is not launch-authoritative because prepared handoff
artifacts intentionally record WSL absolute paths; use WSL readiness for launch.

## Boundary Check

- This is launch-reporting only.
- It does not change Decision, `DecisionFeatures`, Protocol gates, lifecycle,
  scheduler, promotion, proposal selection, or solver semantics.
- It makes existing readiness failures easier to delegate and resume, which
  supports the v0.4 requirement that framework state be auditable.

## Acceptance

Accepted as a v0.4 operator-readiness repair. The next operator-visible launch
blocker is now unambiguous in the top-level JSON: only `completion_preflight`.
