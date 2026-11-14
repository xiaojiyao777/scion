# v0.4 Prepared Root Runtime Guard Refresh f93e55d

Date: 2026-06-18

## Purpose

The warehouse follow-up analysis-brief repair changed
`scion/tools/postrun_analysis_brief.py`, which is part of the prepared-root
runtime guard set. The previous `8d89fd9` prepared roots were still
prepare-only, but they were no longer aligned to the current guarded tooling.
New prepare-only roots were generated from checkout `f93e55d` without launching
a campaign.

## Current Launch Targets

CVRP:

`/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-postpivot-resume-ready-whbrief-f93e55d-1r-gpt55-20260618T200236Z-claw`

Warehouse:

`/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-v2-followup-ready-whbrief-f93e55d-6r-gpt55-20260618T200236Z-claw`

Both roots are prepare-only and remain unstarted.

## Verification

WSL checkout:

```text
f93e55d
```

WSL focused regression sweep:

```bash
PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion \
  /home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m pytest -q \
  scion/scion/tests/test_postrun_analysis_brief.py \
  scion/scion/tests/test_postrun_artifact_inventory.py \
  scion/scion/tests/test_warehouse_agentic_launcher.py
```

Result: `24 passed in 1.05s`.

Static launch readiness for both current roots:

- exit `0`
- `ready=true`
- `static_ready=true`
- `launch_ready=false`
- `git_runtime_consistent=ok`
- `prepared_contract_complete=ok`
- `not_already_started=ok`

Strict launch readiness for both current roots:

- exit `64`
- `static_ready=true`
- `launch_ready=false`
- `checks.completion_preflight.status=failed`
- chat HTTP `401`
- chat classification `not_authenticated`
- auth pool: `refreshing=1`, `active=0`
- `operator_action.login_url` is present under
  `checks.completion_preflight.detail.operator_action`

Warehouse prepared analysis brief:

- `warehouse_followup_summary.available=true`
- `warehouse_followup_summary.current_run_evidence=false`
- `warehouse_followup_summary.interpretation=prepared_only_launch_required`
- `warehouse_followup_summary.handoff_complete=true`
- all warehouse follow-up handoff requirements are available

Launch remains blocked until the strict command returns `launch_ready=true`:

```bash
scion/tools/check_launch_readiness.py <prepared-root> \
  --require-launch-ready \
  --format json
```

## Acceptance

Accepted as the current prepared-root refresh after the warehouse follow-up
analysis-brief repair. The current roots are aligned to guarded source
`f93e55d`; the only current launch blocker is external `gpt-5.5` auth.
