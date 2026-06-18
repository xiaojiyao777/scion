# v0.4 Prepared Root Runtime Guard Refresh fa804e0

Date: 2026-06-18

## Purpose

Commit `fa804e0` changed report/control-plane source paths that are included in
prepared-root runtime consistency checks. The previous prepared roots from
`724c465` therefore became statically stale even though they had not been
launched.

## Refreshed Roots

- CVRP:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-postpivot-resume-ready-familyeffect-fa804e0-1r-gpt55-20260618T202615Z-claw`
- Warehouse:
  `/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-v2-followup-ready-familyeffect-fa804e0-6r-gpt55-20260618T202627Z-claw`

Both were generated prepare-only from the synchronized WSL checkout at
`fa804e0`; neither root has been launched. After the follow-up documentation
commit, the WSL checkout is at `67a43bd`, and the readiness guard still accepts
the roots because runtime guard paths are unchanged.

## Readiness

Strict launch readiness was rerun on WSL with
`--require-launch-ready --format json`.

- `static_ready=true` for both roots.
- `git_runtime_consistent=ok`. At the final checked state the detail is
  `checkout differs, but runtime guard paths are unchanged`.
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
