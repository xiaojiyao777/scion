# v0.4 Prepared Root Refresh After Agentic Partial Recovery

Date: 2026-06-20

## Summary

The warehouse and CVRP prepared roots were refreshed on WSL after commit
`cec86a07` added agentic partial-hypothesis recovery. The refresh keeps the
same focused v0.4 launch intent as the previous roots, but ensures a restart can
reuse valid waiting-approval partial hypotheses instead of duplicating the
hypothesis LLM call.

Both refreshed roots are static-ready and fail launch readiness only at the
external `gpt-5.5` completion preflight:

- `static_ready=true`
- `launch_ready=false`
- `failed_static_required_checks=[]`
- `failed_required_checks=["completion_preflight"]`
- completion auth: HTTP `401`, `classification=not_authenticated`,
  `code=invalid_api_key`, auth pool `active=0`, `expired=1`, `total=1`

## Roots

Warehouse:

- WSL:
  `/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-v2-followup-partialrec-cec86a07-preflight-6r-gpt55-20260620T030033Z-claw`
- Local mirror:
  `/home/clawd/research/scion-experiments/v04-warehouse-v2-followup-partialrec-cec86a07-preflight-6r-gpt55-20260620T030033Z-claw`
- Runtime guard commit: `cec86a07`
- Runtime guard paths:
  `scion/scion :(exclude)scion/scion/tests scion/tools scion/problems/warehouse_delivery surrogate`
- Resume campaign:
  `/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-validation-transfer-contract-rerun6r-ce5d884-20260617T152944Z/rep01/full_context/campaign`
- Rounds/time limit: `6` rounds, `10s`

CVRP:

- WSL:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-large-twoopt-phase4-partialrec-cec86a07-preflight-4r-gpt55-20260620T030045Z-claw`
- Local mirror:
  `/home/clawd/research/scion-experiments/v04-cvrp-large-twoopt-phase4-partialrec-cec86a07-preflight-4r-gpt55-20260620T030045Z-claw`
- Runtime guard commit: `cec86a07`
- Runtime guard paths:
  `scion/scion :(exclude)scion/scion/tests scion/tools scion/problems/cvrp vrp`
- Resume campaign:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-postpivot-guidance-agentic-1r-acc21ba-20260618T064210Z/campaign`
- Rounds/time limit: `4` rounds, `30s`
- Stage-transition drain limit: `4`

## Commands

Prepare-only commands were run on WSL from
`/home/xjy-ubuntu/research/or-autoresearch-agent` with
`PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion` and Python
`/home/xjy-ubuntu/miniconda3/envs/scion/bin/python`.

Strict readiness was then rerun for each root:

```bash
python scion/tools/check_launch_readiness.py <root> --require-launch-ready --format json > <root>/readiness.strict.json
```

The roots were mirrored back to the server with `rsync`.

## Boundary Check

This refresh is launch/handoff evidence only. It does not change Protocol,
Decision, `DecisionFeatures`, promotion input, scheduler state, or problem
solver semantics. Agentic partial-hypothesis recovery remains tainted proposal
material and still passes through the normal deterministic approval checks
before any code phase.

## Next Step

Refresh the local proxy login, then rerun strict launch readiness on the root to
be launched. Do not start either campaign until `launch_ready=true`.
