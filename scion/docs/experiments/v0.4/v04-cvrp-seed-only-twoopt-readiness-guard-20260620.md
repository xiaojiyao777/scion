# v0.4 CVRP Seed-Only Two-Opt Readiness Guard

Date: 2026-06-20

## Purpose

Close a postrun interpretation gap for the active CVRP large-instance two-opt
follow-up. The external
`large_instance_intra_route_two_opt_seed` evidence is proposal guidance only:
it must not by itself satisfy `bounded_twoopt_review_ready`. A live CVRP
conclusion must show a bounded or deadline-aware large two-opt mechanism with
current-run protocol effect, activation, objective-effect, and phase telemetry.

## Change

- `scion/tools/postrun_analysis_brief.py`
  - Treats `large_instance_intra_route_two_opt_seed` as a rejected
    two-opt-like family for review readiness with reason
    `seed_guidance_requires_bounded_implementation`.
  - Rejects large intra-route two-opt labels that lack bounded, deadline,
    guarded, capped, or size70 scope with reason
    `missing_bounded_deadline_twoopt_scope`.
  - Keeps `bounded_large_twoopt`, deadline-aware large two-opt, and size70
    bounded two-opt labels eligible for direct-evidence review.
- `scion/scion/tests/test_postrun_analysis_brief.py`
  - Covers seed-only and intra-only family rejection.
- `scion/scion/tests/test_check_postrun_acceptance.py`
  - Rejects a stale `bounded_twoopt_review_ready` summary when the realized
    measurement input is only the seed family.

## Verification

Local commit: `708e6f54`.

```text
python -m py_compile \
  scion/tools/postrun_analysis_brief.py \
  scion/tools/check_postrun_acceptance.py \
  scion/scion/tests/test_postrun_analysis_brief.py \
  scion/scion/tests/test_check_postrun_acceptance.py
# passed
```

```text
PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion pytest -q \
  scion/scion/tests/test_postrun_analysis_brief.py \
  scion/scion/tests/test_check_postrun_acceptance.py
# 32 passed; 48 passed
```

```text
PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion pytest -q \
  scion/scion/tests/test_rebuild_prepared_handoff.py \
  scion/scion/tests/test_launch_readiness.py \
  scion/scion/tests/test_postrun_analysis_brief.py \
  scion/scion/tests/test_check_postrun_acceptance.py \
  scion/scion/tests/test_cli_report_research_efficiency.py
# 175 passed in 43.40s
```

WSL commit: `2d0db1b6`.

```text
PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion \
  /home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m pytest -q \
  scion/scion/tests/test_rebuild_prepared_handoff.py \
  scion/scion/tests/test_launch_readiness.py \
  scion/scion/tests/test_postrun_analysis_brief.py \
  scion/scion/tests/test_check_postrun_acceptance.py \
  scion/scion/tests/test_cli_report_research_efficiency.py
# 175 passed in 29.97s
```

## Current Prepared Roots

Because `scion/tools` is runtime-guarded, the previous prepared roots were
superseded. New WSL prepare-only roots were generated from `2d0db1b6`.

Warehouse:

`/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-v2-followup-seedguard-2d0db1b6-preflight-6r-gpt55-20260620T004921Z-claw`

Local mirror:

`/home/clawd/research/scion-experiments/v04-warehouse-v2-followup-seedguard-2d0db1b6-preflight-6r-gpt55-20260620T004921Z-claw`

CVRP:

`/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-large-twoopt-phase4-seedguard-2d0db1b6-preflight-4r-gpt55-20260620T004921Z-claw`

Local mirror:

`/home/clawd/research/scion-experiments/v04-cvrp-large-twoopt-phase4-seedguard-2d0db1b6-preflight-4r-gpt55-20260620T004921Z-claw`

Strict launch readiness for both roots:

```text
static_ready=True
launch_ready=False
failed_static_required_checks=[]
failed_required_checks=[completion_preflight]
git_runtime_guard_commit_consistent=ok
run_script_runtime_guard_contract_consistency=ok
completion_preflight=failed
http_status=401
classification=not_authenticated
code=invalid_api_key
auth_pool_active=0
auth_pool_refreshing=1
```

The readiness JSON is saved as `readiness.strict.json` in each prepared root.

## Boundary Check

- This repair is postrun/reporting and launch-readiness evidence only.
- It does not change Decision, `DecisionFeatures`, Protocol gates, promotion,
  scheduler state, or solver semantics.
- CVRP problem semantics remain in the problem-owned postrun interpretation
  layer; generic core still sees only report-only readiness fields.
