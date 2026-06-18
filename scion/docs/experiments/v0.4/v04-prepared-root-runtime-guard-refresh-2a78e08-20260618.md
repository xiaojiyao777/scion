# Prepared Root Runtime Guard Refresh 2a78e08

Date: 2026-06-18
Branch: `codex/v04-evidence-repair-plan`
Commit: `2a78e08`

## Summary

The low-signal same-branch lesson-usage repair changed a runtime guard path in
proposal context. The previous `7e12c62` CVRP prepared root failed launch
readiness with `git_runtime_consistent=failed` and detail
`checkout differs and runtime guard paths changed`.

Both follow-up roots were regenerated from the WSL checkout at `2a78e08`. They
are prepared-only, unstarted, contract-complete, and static-ready. They remain
blocked only by the external GPT-5.5 proxy authentication preflight.

## Current Prepared Roots

CVRP:

`/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-postpivot-resume-ready-2a78e08-1r-gpt55-1r-gpt55-20260618T160627Z-claw`

Warehouse:

`/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-v2-followup-ready-2a78e08-6r-gpt55-6r-gpt55-20260618T160640Z-claw`

## Readiness

`check_launch_readiness.py --completion-preflight --format json` reports for
both roots:

- `static_ready=true`
- `git_runtime_consistent=ok`
- `prepared_contract_complete=ok`
- `prepared_only_not_started=ok`
- `zero_current_run_counters=ok`
- `decision_features_excluded=true`
- `scheduler_state_mutated=false`
- `promotion_state_mutated=false`
- `campaign_state_mutated=false`
- `launch_ready=false`

The remaining failure is `completion_preflight=failed` with HTTP `401`,
`classification=not_authenticated`, `code=invalid_api_key`,
`authenticated=false`, `active=0`, `expired=1`, and `refreshing=0`.
Readiness includes an `operator_action.login_url`; refresh the local proxy
login and rerun launch readiness before starting either root.
