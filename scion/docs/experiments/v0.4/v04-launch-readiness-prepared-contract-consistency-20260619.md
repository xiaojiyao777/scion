# v0.4 Launch Readiness Prepared Contract Consistency

Date: 2026-06-19

## Purpose

Postrun acceptance already rejects an analysis brief whose
`prepared_run_contract` drifts from the inventory/launcher prepared contract.
Because prepared roots are launch-gated before any campaign runs, the same
contract drift must be visible in `check_launch_readiness.py` as a required
static check. Otherwise a prepared root could be called static-ready while the
postrun checker would later reject its analysis brief routing evidence.

## Change

- Added launch-readiness check
  `analysis_brief_prepared_contract_consistency`.
- The check compares each prepared analysis brief's `prepared_run_contract`
  against the inventory/launcher prepared contract.
- Compared fields include report-only and boundary flags, manifest identity,
  problem family, model, analysis intent, acceptance and research focus,
  resume/control-pair identity, completion-preflight and postrun-report
  declarations, execution, git, and contract checks.
- Launch readiness now fails before campaign start if a stale prepared analysis
  brief can steer warehouse/CVRP readiness through a different prepared
  contract than the launcher manifest.

## Boundary

This is a control-plane readiness guard only. It does not change Decision,
`DecisionFeatures`, Protocol gates, promotion, scheduler state, solver code,
runtime budgets, or CVRP/warehouse problem semantics.

## Verification

Local checkout `48e2b774`:

```bash
python -m py_compile \
  scion/tools/check_launch_readiness.py \
  scion/scion/tests/test_launch_readiness.py

PYTHONPATH=scion pytest -q \
  scion/scion/tests/test_launch_readiness.py
# 55 passed

PYTHONPATH=scion pytest -q \
  scion/scion/tests/test_launch_readiness.py \
  scion/scion/tests/test_postrun_artifact_inventory.py \
  scion/scion/tests/test_postrun_analysis_brief.py \
  scion/scion/tests/test_check_postrun_acceptance.py \
  scion/scion/tests/test_rebuild_postrun_acceptance.py
# 127 passed in 25.81s
```

WSL checkout `cc11e7e`:

```bash
PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion \
  /home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m pytest -q \
  scion/scion/tests/test_launch_readiness.py
# 55 passed in 1.03s

PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion \
  /home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m pytest -q \
  scion/scion/tests/test_launch_readiness.py \
  scion/scion/tests/test_postrun_artifact_inventory.py \
  scion/scion/tests/test_postrun_analysis_brief.py \
  scion/scion/tests/test_check_postrun_acceptance.py \
  scion/scion/tests/test_rebuild_postrun_acceptance.py
# 127 passed in 18.20s
```

## Current Prepared Roots

Prepare-only roots were regenerated from WSL runtime commit `cc11e7e` because
`scion/tools/check_launch_readiness.py` is part of the guarded launch/readiness
runtime surface.

Warehouse:

`/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-v2-followup-launchcontract-cc11e7e-6r-gpt55-6r-gpt55-20260619T131623Z-claw`

CVRP:

`/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-large-twoopt-launchcontract-cc11e7e-1r-gpt55-1r-gpt55-20260619T131625Z-claw`

Strict launch readiness for both roots exits `64` and reports:

- `static_ready=true`
- `launch_ready=false`
- `git_runtime_consistent=ok` with `checkout matches manifest commit`
- `prepared_analysis_brief_current=ok`
- `analysis_brief_prepared_contract_consistency=ok`
- `prompt_context_readiness_complete=ok`
- `problem_specific_prepared_handoff=ok`
- `postrun_families_complete=ok`
- all run-script guard checks ok, including model route, active-checkout
  `PYTHONPATH`, completion preflight command, preflight-failure reports,
  no-early-stop launch semantics, strict postrun readiness, postrun reports
  after campaign, and runtime guard coverage for launch tools and matching
  problem runtime paths

The remaining blocker is external GPT-5.5 auth: completion preflight returns
HTTP `401`, `classification=not_authenticated`, `code=invalid_api_key`; latest
auth pool is `active=0`, `expired=1`, `refreshing=0`, `total=1`.

Do not launch either root until strict launch readiness reports
`launch_ready=true`.
