# V0.4 Launcher Prepared Status Repair

Date: 2026-06-18

## Purpose

Copied campaign follow-up roots intentionally contain the source campaign's
`campaign/run_status.json`, `campaign/exit.txt`, and `campaign_summary.json`.
That is useful for resume, but a prepare-only root could be misread as already
launched if inspection starts inside `campaign/` instead of the run root.

This repair makes prepare-only CVRP and warehouse launcher roots write a
top-level `run_status.json` with schema `scion.launcher_prepare.v1` and
`status=prepared`. For copied campaign resumes it explicitly records whether
copied source `campaign/run_status.json` and `campaign_summary.json` are
present, so those files are auditable as resume-source state rather than new
wrapper completion evidence.

## Boundary Check

- This is launcher/reporting metadata only.
- It does not change Decision, `DecisionFeatures`, Protocol, scheduling, gates,
  lifecycle policy, proposal context, or problem semantics.
- CVRP and warehouse semantics remain in problem-owned layers. The new fields
  describe launcher state and copied-artifact provenance only.

## Changed Surface

- `scion/tools/launch_cvrp_agentic_campaign.py`
- `scion/tools/launch_warehouse_agentic_campaign.py`
- `scion/scion/tests/test_cvrp_agentic_launcher.py`
- `scion/scion/tests/test_warehouse_agentic_launcher.py`

## Verification

Local:

```bash
PYTHONPATH=scion pytest -q \
  scion/scion/tests/test_cvrp_agentic_launcher.py \
  scion/scion/tests/test_warehouse_agentic_launcher.py
python -m py_compile \
  scion/tools/launch_cvrp_agentic_campaign.py \
  scion/tools/launch_warehouse_agentic_campaign.py
git diff --check
```

Result:

- `23 passed`
- `py_compile` passed
- `git diff --check` passed

WSL prepared roots regenerated from commit `9b41269`:

- CVRP:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-postpivot-resume-ready-preparedstatus-1r-gpt55-20260618T111015Z-claw`
- Warehouse:
  `/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-v2-followup-ready-preparedstatus-6r-gpt55-20260618T111015Z-claw`

Both roots have top-level `run_status.json` with:

- `schema=scion.launcher_prepare.v1`
- `status=prepared`
- `prepared_only=true`
- `completion_preflight=true`
- copied campaign status/summary presence marked as copied resume-source state

Both roots passed `bash -n run.sh` and were synced back to:

- `/home/clawd/research/scion-experiments/v04-cvrp-postpivot-resume-ready-preparedstatus-1r-gpt55-20260618T111015Z-claw`
- `/home/clawd/research/scion-experiments/v04-warehouse-v2-followup-ready-preparedstatus-6r-gpt55-20260618T111015Z-claw`

## Residual Blocker

No campaign was launched. The WSL `gpt-5.5` proxy still fails real
`/v1/chat/completions` with HTTP `401` because the proxy account token is
invalidated. `/v1/models` and `/auth/status` are not sufficient launch
preflights.
