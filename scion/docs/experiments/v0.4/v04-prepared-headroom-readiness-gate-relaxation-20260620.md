# v0.4 Prepared Headroom Readiness Gate Relaxation

Date: 2026-06-20

## Purpose

v0.4 launch readiness used fixed proposal/APS headroom thresholds as static
launch blockers. That protected prepared runs from accidentally tiny proposal
or tool budgets, but it also risked turning a temporary prepared-run policy
into another arbitrary gate. The current v0.4 objective is effective research,
so readiness should block missing or disconnected launch controls, not reject a
run solely because a headroom value is below the current recommendation.

## Change

- `check_launch_readiness.py` still fails when headroom fields are missing,
  unparsable, or not wired through `run.sh` from `launch.env`.
- Below-recommended proposal/APS values now appear in
  `run_script_proposal_headroom_enforced.detail.warnings`.
- The check status remains `ok` when warnings are the only issue, so static
  readiness does not become a fixed-number research gate.

## Verification

Local code commit: `2c3e409d`.
WSL launch-authoritative commit: `2827b672`.

Local:

```bash
python -m py_compile scion/tools/check_launch_readiness.py
# clean

pytest scion/scion/tests/test_launch_readiness.py -q
# 99 passed
```

WSL:

```bash
/home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m pytest \
  scion/scion/tests/test_launch_readiness.py -q
# 99 passed
```

## Prepared Roots

Regenerated on WSL from commit `2827b672` and mirrored locally.

Warehouse:

- WSL:
  `/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-v2-followup-size70hypctx-2827b672-preflight-6r-gpt55-20260620T103302Z-claw`
- Local mirror:
  `/home/clawd/research/scion-experiments/v04-warehouse-v2-followup-size70hypctx-2827b672-preflight-6r-gpt55-20260620T103302Z-claw`

CVRP:

- WSL:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-large-twoopt-phase4-size70hypctx-2827b672-preflight-4r-gpt55-20260620T103302Z-claw`
- Local mirror:
  `/home/clawd/research/scion-experiments/v04-cvrp-large-twoopt-phase4-size70hypctx-2827b672-preflight-4r-gpt55-20260620T103302Z-claw`

Strict launch readiness for both roots exits `64` because completion preflight
is required and external auth is unavailable, but static launch readiness is
clean:

- `static_ready=true`
- `launch_ready=false`
- `failed_static_required_checks=[]`
- `failed_required_checks=["completion_preflight"]`
- completion auth: HTTP `401`, `classification=not_authenticated`,
  `code=invalid_api_key`; auth pool `active=0`, `total=1`

## Boundary Check

This is a launcher/readiness control-plane change. It does not alter
`DecisionFeatures`, Protocol gates, scheduler state, promotion input,
problem-owned solver semantics, or LLM proposal material. The prepared roots
still carry the same explicit headroom values; readiness simply stops treating
the current recommendation as a launch-blocking research gate.
