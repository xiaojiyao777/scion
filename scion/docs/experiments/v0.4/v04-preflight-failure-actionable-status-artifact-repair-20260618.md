# Preflight Failure Actionable Status Artifact Repair

Date: 2026-06-18

## Purpose

Make a prepared root that is actually started but stops before campaign startup
because completion preflight fails auditable without reading free-form logs.
This closes the gap between launch readiness, which already reports an
actionable auth/login step, and launcher failure artifacts, which previously
recorded only `pre_campaign_completion_preflight=failed`.

## Change

CVRP and warehouse launchers now write the proxy JSON result to
`pre_campaign_completion_preflight.v1.json` whenever `COMPLETION_PREFLIGHT=1`.
On pre-campaign failure they call
`scion/tools/write_completion_preflight_status.py`, which writes structured
report-only fields into `run_status.json`:

- failure classification,
- HTTP status and proxy error code,
- sanitized auth/account pool state,
- whether a login URL is present in the detail artifact,
- operator action text,
- detail artifact filename/path.

`postrun_artifact_inventory.py` now includes the detail artifact and projects
these status fields for delegated analysis. The full proxy detail remains a
separate artifact; `run.log` only records the detail artifact path marker.

## Boundary Check

This is launcher/reporting evidence only. It does not mutate campaign state,
scheduler state, promotion state, `DecisionFeatures`, Protocol evidence,
budgets, gates, lifecycle policy, or problem semantics.

## Verification

Focused local verification:

```bash
python -m py_compile \
  scion/tools/write_completion_preflight_status.py \
  scion/tools/launch_cvrp_agentic_campaign.py \
  scion/tools/launch_warehouse_agentic_campaign.py \
  scion/tools/postrun_artifact_inventory.py \
  scion/tools/check_launch_readiness.py

PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion pytest -q \
  scion/scion/tests/test_completion_preflight_status.py \
  scion/scion/tests/test_launch_readiness.py \
  scion/scion/tests/test_cvrp_agentic_launcher.py \
  scion/scion/tests/test_warehouse_agentic_launcher.py \
  scion/scion/tests/test_postrun_artifact_inventory.py \
  scion/scion/tests/test_rebuild_postrun_acceptance.py
```

Result: `41 passed`.

WSL verification after syncing commit `35de1b5`:

```bash
PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion \
/home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m pytest -q \
  scion/scion/tests/test_completion_preflight_status.py \
  scion/scion/tests/test_launch_readiness.py \
  scion/scion/tests/test_cvrp_agentic_launcher.py \
  scion/scion/tests/test_warehouse_agentic_launcher.py \
  scion/scion/tests/test_postrun_artifact_inventory.py \
  scion/scion/tests/test_rebuild_postrun_acceptance.py
```

Result: `41 passed`.

Prepared roots refreshed from commit `35de1b5`:

- CVRP:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-postpivot-resume-ready-actionpreflight-1r-gpt55-1r-gpt55-20260618T145045Z-claw`
- Warehouse:
  `/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-v2-followup-ready-actionpreflight-6r-gpt55-6r-gpt55-20260618T145046Z-claw`

Both refreshed roots have `static_ready=true`, `git_runtime_consistent=ok`, and
generated `run.sh` files containing the structured preflight-failure helper and
`pre_campaign_completion_preflight.v1.json` detail artifact path. Real
completion preflight still returns HTTP `401` with
`classification=not_authenticated`; do not launch until readiness reports
`launch_ready=true`.
