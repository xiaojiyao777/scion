# v0.4 CVRP Two-Opt Mechanism-Bound Direct Evidence

Date: 2026-06-19

## Purpose

Close the remaining CVRP large/bounded two-opt direct-evidence audit gap:
`cvrp_large_twoopt_summary` could count activation/effect statuses from
unrelated `mechanism_evidence` on an otherwise matching top effect row. Review
readiness now requires activation/effect evidence to belong to a matching
large/bounded two-opt mechanism, not merely to any mechanism reported on the
same row.

## Changes

- `scion/tools/postrun_analysis_brief.py`
  - CVRP direct-evidence counting now filters row-level
    `primary_activation_status`, `activation_evidence_status`,
    `primary_effect_status`, `objective_effect_status`, and nested
    `mechanisms[]` statuses through the same large/bounded two-opt family
    matcher used for the top-row protocol signal.
  - Unrelated, cross-route, unbounded/fallback, VNS, or two-opt-star mechanism
    evidence cannot complete bounded two-opt direct evidence.
- `scion/scion/tests/test_postrun_analysis_brief.py`
  - Added a regression where the top row has positive effect and
    two-opt-specific phase telemetry, but all activation/effect evidence is for
    `unrelated_probe`; the summary must stay
    `protocol_evaluated_without_large_twoopt_direct_evidence`.

## Verification

Local commit: `6fcb10e8`.

```text
PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion pytest -q \
  scion/scion/tests/test_postrun_analysis_brief.py \
  scion/scion/tests/test_check_postrun_acceptance.py
# 76 passed in 35.64s
```

```text
PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion pytest -q \
  scion/scion/tests/test_rebuild_prepared_handoff.py \
  scion/scion/tests/test_launch_readiness.py \
  scion/scion/tests/test_postrun_analysis_brief.py \
  scion/scion/tests/test_check_postrun_acceptance.py \
  scion/scion/tests/test_cli_report_research_efficiency.py
# 166 passed in 40.37s
```

WSL commit: `1c2c1bbb`.

```text
cd /home/xjy-ubuntu/research/or-autoresearch-agent
PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion \
  /home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m pytest -q \
  scion/scion/tests/test_rebuild_prepared_handoff.py \
  scion/scion/tests/test_launch_readiness.py \
  scion/scion/tests/test_postrun_analysis_brief.py \
  scion/scion/tests/test_check_postrun_acceptance.py \
  scion/scion/tests/test_cli_report_research_efficiency.py
# 166 passed in 28.47s
```

## Current Prepared Roots

WSL runtime commit: `1c2c1bbb`.

Warehouse:

`/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-v2-followup-mechanismbind-1c2c1bbb-preflight-6r-gpt55-20260619T234940Z-claw`

Local mirror:

`/home/clawd/research/scion-experiments/v04-warehouse-v2-followup-mechanismbind-1c2c1bbb-preflight-6r-gpt55-20260619T234940Z-claw`

CVRP:

`/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-large-twoopt-phase4-mechanismbind-1c2c1bbb-preflight-4r-gpt55-20260619T234941Z-claw`

Local mirror:

`/home/clawd/research/scion-experiments/v04-cvrp-large-twoopt-phase4-mechanismbind-1c2c1bbb-preflight-4r-gpt55-20260619T234941Z-claw`

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
auth_pool.expired=1
auth_pool.total=1
```

## Boundary Check

- The repair is a report-only postrun readiness guard.
- It does not change Decision, `DecisionFeatures`, Protocol gates, promotion,
  scheduler state, or solver semantics.
- CVRP mechanism semantics remain in the CVRP large-two-opt postrun review
  path, and raw mechanism diagnostics remain outside `DecisionFeatures`.

## Acceptance

Accepted as a v0.4 evidence/readiness repair. The active prepared roots were
refreshed from WSL runtime commit `1c2c1bbb`; launch remains blocked only by
external `gpt-5.5` completion auth.
