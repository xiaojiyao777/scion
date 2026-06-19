# v0.4 Postrun Launch-Required Flag Guard

Date: 2026-06-19

## Purpose

Postrun delegated review can now reject a contradictory problem-specific
summary that claims current-run review actionability while still saying launch
is required before a plateau or bounded two-opt conclusion.

This is a report-only readiness guard. It does not feed `DecisionFeatures`,
Protocol gates, promotion, scheduler state, or solver behavior.

## Change

`check_postrun_acceptance.py` now marks `problem_summary_actionability=failed`
when:

- `warehouse_followup_summary.current_run_evidence=true` and
  `launch_required_before_plateau_conclusion=true`; or
- `cvrp_large_twoopt_summary.current_run_evidence=true` and
  `launch_required_before_twoopt_conclusion=true`.

The readiness detail reports the exact stale launch-required field so a
delegated reviewer can distinguish a stale/prepared-only summary from a
current-run conclusion.

## Verification

Local focused verification:

`PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion pytest -q scion/scion/tests/test_check_postrun_acceptance.py`

Result: `42 passed in 35.73s`.

WSL focused verification:

`PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion /home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m pytest -q scion/scion/tests/test_check_postrun_acceptance.py`

Result: `42 passed in 22.20s`.

## Prepared Root Refresh

The repair touched `scion/tools`, which is covered by the warehouse and CVRP
runtime guards. The previous proxy-format prepared roots were superseded and
new roots were regenerated on WSL runtime commit `c91b4cec`.

Warehouse WSL root:

`/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-v2-followup-launchflag-c91b4cec-preflight-6r-gpt55-20260619T215212Z-claw`

Warehouse local mirror:

`/home/clawd/research/scion-experiments/v04-warehouse-v2-followup-launchflag-c91b4cec-preflight-6r-gpt55-20260619T215212Z-claw`

CVRP WSL root:

`/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-large-twoopt-phase4-launchflag-c91b4cec-preflight-4r-gpt55-20260619T215214Z-claw`

CVRP local mirror:

`/home/clawd/research/scion-experiments/v04-cvrp-large-twoopt-phase4-launchflag-c91b4cec-preflight-4r-gpt55-20260619T215214Z-claw`

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
