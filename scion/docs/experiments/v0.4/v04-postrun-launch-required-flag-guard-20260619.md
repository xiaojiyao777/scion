# v0.4 Postrun Launch-Required Flag Guard

Date: 2026-06-19

## Purpose

Postrun delegated review can now reject a contradictory or incomplete
problem-specific summary that claims current-run review actionability without
explicitly clearing the launch-required flag before a plateau or bounded two-opt
conclusion.

This is a report-only readiness guard. It does not feed `DecisionFeatures`,
Protocol gates, promotion, scheduler state, or solver behavior.

## Change

`check_postrun_acceptance.py` now marks `problem_summary_actionability=failed`
unless current-run problem summaries explicitly set their launch-required field
to `false`:

- `warehouse_followup_summary.current_run_evidence=true` and
  `launch_required_before_plateau_conclusion` is not `false`; or
- `cvrp_large_twoopt_summary.current_run_evidence=true` and
  `launch_required_before_twoopt_conclusion` is not `false`.

The readiness detail reports the exact stale launch-required field so a
delegated reviewer can distinguish a stale/prepared-only summary from a
current-run conclusion.

## Verification

Local focused verification:

`PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion pytest -q scion/scion/tests/test_check_postrun_acceptance.py`

Result: `42 passed in 35.73s`.

After tightening missing-field behavior:

`PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion pytest -q scion/scion/tests/test_check_postrun_acceptance.py`

Result: `42 passed in 32.27s`.

WSL focused verification:

`PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion /home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m pytest -q scion/scion/tests/test_check_postrun_acceptance.py`

Result: `42 passed in 22.20s`.

After tightening missing-field behavior:

`PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion /home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m pytest -q scion/scion/tests/test_check_postrun_acceptance.py`

Result: `42 passed in 22.34s`.

## Prepared Root Refresh

The repair touched `scion/tools`, which is covered by the warehouse and CVRP
runtime guards. The previous prepared roots were superseded and new roots were
regenerated on WSL runtime commit `567a29dd`.

Warehouse WSL root:

`/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-v2-followup-explicitlaunch-567a29dd-preflight-6r-gpt55-20260619T220040Z-claw`

Warehouse local mirror:

`/home/clawd/research/scion-experiments/v04-warehouse-v2-followup-explicitlaunch-567a29dd-preflight-6r-gpt55-20260619T220040Z-claw`

CVRP WSL root:

`/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-large-twoopt-phase4-explicitlaunch-567a29dd-preflight-4r-gpt55-20260619T220040Z-claw`

CVRP local mirror:

`/home/clawd/research/scion-experiments/v04-cvrp-large-twoopt-phase4-explicitlaunch-567a29dd-preflight-4r-gpt55-20260619T220040Z-claw`

Strict readiness for both regenerated roots reports:

- `static_ready=true`
- `launch_ready=false`
- Failed check: `completion_preflight`
- `git_runtime_consistent=ok` with `checkout matches manifest commit`
- Completion preflight: HTTP `401`, `classification=not_authenticated`,
  `code=invalid_api_key`
- Auth pool: `active=0`, `expired=1`, `total=1`

The only current launch blocker remains external `gpt-5.5` proxy auth.

## Acceptance

Accepted as the current postrun delegated-review consistency guard and
prepared-root refresh. Do not launch either root until strict launch readiness
reports `launch_ready=true`.
