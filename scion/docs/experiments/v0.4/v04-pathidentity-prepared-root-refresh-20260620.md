# v0.4 Path-Identity Prepared Root Refresh

Date: 2026-06-20

## Purpose

Regenerate the current focused warehouse and CVRP prepared roots after the
postrun acceptance path-identity repair. The previous
`febeaf11-runtimeinactive` roots were correctly rejected by launch readiness
after commit `f22ad5f4`, because `scion/tools/check_postrun_acceptance.py` is
part of the runtime-guarded tool surface.

## New WSL Prepared Roots

- Warehouse:
  `/home/xjy-ubuntu/research/scion-experiments/v04-wh-v2-f22ad5f4-pathidentity-6r-gpt55-20260620T153154Z-claw`
- CVRP:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-twoopt-f22ad5f4-pathidentity-4r-gpt55-20260620T153155Z-claw`

Local mirrors were synced under:

- `/home/clawd/research/scion-experiments/v04-wh-v2-f22ad5f4-pathidentity-6r-gpt55-20260620T153154Z-claw`
- `/home/clawd/research/scion-experiments/v04-cvrp-twoopt-f22ad5f4-pathidentity-4r-gpt55-20260620T153155Z-claw`

## Shape

- Warehouse: 6 rounds, champion-v2 follow-up, resumed from
  `/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-validation-transfer-contract-rerun6r-ce5d884-20260617T152944Z/rep01/full_context/campaign`.
- CVRP: 4 rounds, bounded large-two-opt follow-up, resumed from
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-postpivot-guidance-agentic-1r-acc21ba-20260618T064210Z/campaign`.
- Completion preflight is enabled.
- Proposal and APS research caps remain disabled with exact `0` values; wall
  time guard remains enabled.

## Readiness

Strict launch readiness with completion preflight was written to each root as
`readiness.strict.json`.

Both roots report:

- `static_ready=true`
- `launch_ready=false`
- `failed_static_required_checks=[]`
- `failed_required_checks=["completion_preflight"]`

The completion preflight failure is the known external auth blocker:

- HTTP `401`
- `classification=not_authenticated`
- `code=invalid_api_key`
- auth pool `active=0`, `total=1`, `refreshing=1`

No campaign was launched.
