# Disabled Proposal Research Caps

Date: 2026-06-20

## Decision

Focused v0.4 warehouse and CVRP prepared roots now pass
`--proposal-attempt-limit 0` and `--proposal-quality-loop-limit 0`.

`0` means the proposal-attempt and proposal-quality research caps are disabled.
The core campaign loop still preserves a high-water
`campaign_safety_step_limit`, the normal circuit breaker, and explicit
per-path guards such as scheduler active-slot and telemetry-repair limits.

This removes the previous prepared-run behavior where agentic proposal repair,
schema-quality retries, or hypothesis/code-generation blocks could exhaust a
fixed 64-attempt headroom before Scion reached useful effective research rounds.

## Boundary

This is generic runtime control-plane behavior. It does not add CVRP,
warehouse, BKS, case-hardness, prompt text, or mechanism ranking fields to
`DecisionFeatures`. Problem-specific diagnostics remain problem-owned,
proposal-only inputs.

## Implementation

- Core `CampaignLoop` treats configured proposal-attempt and proposal-quality
  limits of `0` as disabled.
- The old aggregate `attempt_limit_exhausted` fallback is now a
  `campaign_safety_step_limit_exhausted` safety stop.
- Warehouse and CVRP focused launchers default both proposal caps to `0`.
- Launch readiness accepts `0` as a valid wired value and reports below-64
  values as audit warnings, not static readiness failures.

## Verification

Local:

```bash
pytest scion/scion/tests/unit/core/test_retry_round_accounting_campaign_loop.py -q
pytest scion/scion/tests/test_cvrp_agentic_launcher.py scion/scion/tests/test_warehouse_agentic_launcher.py -q
pytest scion/scion/tests/test_launch_readiness.py -q
pytest scion/scion/tests/test_cli_run_options.py -q
pytest scion/scion/tests/test_campaign_basics_continue.py -q
```

WSL with explicit checkout `PYTHONPATH`:

```bash
PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion \
  /home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m pytest \
  scion/scion/tests/unit/core/test_retry_round_accounting_campaign_loop.py \
  scion/scion/tests/test_cvrp_agentic_launcher.py \
  scion/scion/tests/test_warehouse_agentic_launcher.py \
  scion/scion/tests/test_launch_readiness.py \
  scion/scion/tests/test_cli_run_options.py \
  scion/scion/tests/test_campaign_basics_continue.py -q
```

WSL result: `204 passed`.

## Current Prepared Roots

- Warehouse:
  `/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-v2-followup-size70hypctx-44388e29-nocaps-preflight-6r-gpt55-20260620T104927Z-claw`
- CVRP:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-large-twoopt-phase4-size70hypctx-44388e29-nocaps-preflight-4r-gpt55-20260620T104927Z-claw`

Strict launch readiness for both reports:

- `static_ready=true`
- `launch_ready=false`
- `failed_static_required_checks=[]`
- `failed_required_checks=["completion_preflight"]`
- `completion_status=failed`
- `proposal_attempt_limit=0`
- `proposal_quality_loop_limit=0`
- proposal-cap readiness check `ok` with warning-only below-recommendation
  headroom

The remaining blocker is external `gpt-5.5` completion auth:
HTTP `401`, `classification=not_authenticated`, `code=invalid_api_key`.
