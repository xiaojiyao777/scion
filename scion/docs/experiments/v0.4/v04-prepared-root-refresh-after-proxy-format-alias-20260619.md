# v0.4 Prepared Root Refresh After Proxy Format Alias

Date: 2026-06-19

## Purpose

`check_gpt55_proxy.py` now accepts `--format json` as an alias-compatible
operator interface. The code change touched `scion/tools`, which is covered by
both current prepared roots' runtime guards. The previous warehouse and CVRP
prepared roots were therefore correctly rejected by launch readiness with
`git_runtime_consistent=failed`, because the checkout differed and runtime guard
paths had changed.

Both roots were regenerated on WSL from runtime commit `ae9f71d3`.

## Current Prepared Roots

Warehouse:

`/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-v2-followup-proxyfmt-ae9f71d3-preflight-6r-gpt55-20260619T213723Z-claw`

Local mirror:

`/home/clawd/research/scion-experiments/v04-warehouse-v2-followup-proxyfmt-ae9f71d3-preflight-6r-gpt55-20260619T213723Z-claw`

CVRP:

`/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-large-twoopt-phase4-proxyfmt-ae9f71d3-preflight-4r-gpt55-20260619T213724Z-claw`

Local mirror:

`/home/clawd/research/scion-experiments/v04-cvrp-large-twoopt-phase4-proxyfmt-ae9f71d3-preflight-4r-gpt55-20260619T213724Z-claw`

## Prepared Manifest Summary

Both roots keep the previous experiment shape:

- Model route: `gpt-5.5` at `http://127.0.0.1:8080`
- Proposal headroom: `proposal_attempt_limit=64`,
  `proposal_quality_loop_limit=64`
- APS headroom: `agentic_session_timeout_sec=3600`,
  `agentic_tool_max_steps=240`, `agentic_tool_max_calls=200`,
  `agentic_code_tool_max_calls=200`,
  `agentic_observation_max_chars=2000000`
- Measurement governance: `on`
- Proposal context ablation: `full`
- No early stop: enabled

Warehouse-specific:

- Rounds: `6`
- Time limit: `30`
- Resume source:
  `/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-validation-transfer-contract-rerun6r-ce5d884-20260617T152944Z/rep01/full_context/campaign`
- Runtime guard paths:
  `scion/scion :(exclude)scion/scion/tests scion/tools scion/problems/warehouse_delivery surrogate`

CVRP-specific:

- Rounds: `4`
- Time limit: `30`
- Stage transition drain limit: `4`
- Resume source:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-postpivot-guidance-agentic-1r-acc21ba-20260618T064210Z/campaign`
- Runtime guard paths:
  `scion/scion :(exclude)scion/scion/tests scion/tools scion/problems/cvrp vrp`

## Readiness

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

Accepted as the proxy-format prepared-root refresh evidence. It was later
superseded for launch by
`scion/docs/experiments/v0.4/v04-postrun-launch-required-flag-guard-20260619.md`
because a runtime-guarded `scion/tools` file changed again. Do not launch either
root until strict launch readiness reports `launch_ready=true`.
