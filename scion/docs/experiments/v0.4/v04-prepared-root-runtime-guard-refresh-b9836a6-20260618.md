# v0.4 Prepared Root Runtime Guard Refresh b9836a6

Date: 2026-06-18

## Purpose

Commit `b9836a6` changed report/control-plane source paths that are included in
prepared-root runtime consistency checks. The previous `fa804e0` prepared roots
therefore became statically stale even though they had not been launched.

## Refreshed Roots

- CVRP:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-postpivot-resume-ready-lessondiag-b9836a6-1r-gpt55-20260618T203729Z-claw`
- Warehouse:
  `/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-v2-followup-ready-lessondiag-b9836a6-6r-gpt55-20260618T203741Z-claw`

Both were generated prepare-only from the synchronized WSL checkout at
`b9836a6`; neither root has been launched.

## Readiness

Strict launch readiness was rerun on WSL with
`--require-launch-ready --format json`.

- `static_ready=true` for both roots.
- `git_runtime_consistent=ok` with detail `checkout matches manifest commit`.
- `prepared_contract_complete=ok`.
- `not_already_started=ok`.
- `launch_ready=false` only because completion preflight still fails.
- Completion preflight: HTTP `401`, classification `not_authenticated`,
  auth pool `active=0`, `refreshing=1`, and `operator_action.login_url`
  present.

## Acceptance

Accepted as the current prepared-root handoff state. Do not launch either root
until `check_launch_readiness.py <root> --require-launch-ready --format json`
returns `launch_ready=true`.
