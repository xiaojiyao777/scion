# v0.4 Prepared Root Runtime Guard Refresh 724c465

Date: 2026-06-18

## Purpose

The research-continuity brief shape projection repair changed
`scion/tools/postrun_analysis_brief.py`, which is part of the prepared-root
runtime guard set. The previous `f93e55d` prepared roots were still
prepare-only, but they were no longer aligned to the current guarded tooling.
New prepare-only roots were generated from checkout `724c465` without launching
a campaign.

## Current Launch Targets

CVRP:

`/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-postpivot-resume-ready-shape-724c465-1r-gpt55-20260618T201253Z-claw`

Warehouse:

`/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-v2-followup-ready-shape-724c465-6r-gpt55-20260618T201253Z-claw`

Both roots are prepare-only and remain unstarted.

## Verification

WSL checkout:

```text
724c465
```

WSL focused regression sweep:

```bash
PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion \
  /home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m pytest -q \
  scion/scion/tests/test_postrun_analysis_brief.py \
  scion/scion/tests/test_postrun_artifact_inventory.py \
  scion/scion/tests/test_rebuild_postrun_acceptance.py \
  scion/scion/tests/test_cli_report_research_efficiency.py \
  scion/scion/tests/unit/core/test_evidence_recorder_summary_status.py \
  -k 'research_shape or cross_branch or lesson or postrun_analysis_brief or postrun_artifact_inventory or rebuild_postrun_acceptance'
```

Result: `20 passed, 56 deselected in 1.45s`.

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
- auth pool: `active=0`, `refreshing=0`
- `operator_action.login_url` is present under
  `checks.completion_preflight.detail.operator_action`

Warehouse prepared analysis brief:

- `warehouse_followup_summary.available=true`
- `warehouse_followup_summary.current_run_evidence=false`
- `warehouse_followup_summary.interpretation=prepared_only_launch_required`
- `warehouse_followup_summary.handoff_complete=true`

Prepared-only roots have no current-run research-continuity evidence yet, so
`research_continuity_summary.aggregate` remains empty until launch/postrun
reports are generated.

Launch remains blocked until the strict command returns `launch_ready=true`:

```bash
scion/tools/check_launch_readiness.py <prepared-root> \
  --require-launch-ready \
  --format json
```

## Acceptance

Accepted as the current prepared-root refresh after the research-continuity
brief shape projection repair. The current roots are aligned to guarded source
`724c465`; the only current launch blocker is external `gpt-5.5` auth.
