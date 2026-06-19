# v0.4 Launch Readiness Problem-Specific Handoff Visibility

Date: 2026-06-19

## Purpose

Prepared CVRP and warehouse roots already carried problem-specific handoff
coverage in the prepared contract, but launch readiness exposed it only through
the broad `prepared_contract_complete` result. When a root is not static-ready,
the operator needs to see whether the missing evidence is CVRP bounded
large-twoopt handoff, warehouse champion-v2 follow-up handoff, or a generic
prepared-root issue.

## Change

- `check_launch_readiness.py` now emits report-only
  `problem_specific_prepared_handoff`.
- For CVRP, the check expands existing contract checks whose names start with
  `cvrp_`.
- For warehouse delivery, the check expands existing contract checks whose names
  start with `warehouse_`.
- Generic problems get a skipped, non-required result instead of a new gate.

## Boundary Check

- This repair is report-only launch-readiness visibility.
- It reuses prepared-contract checks as the authority.
- It does not change Decision, `DecisionFeatures`, Protocol gates, lifecycle,
  scheduler, promotion, proposal selection, or solver semantics.

## Current Prepared Roots

WSL checkout: `a57fd07`

- Warehouse:
  `/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-v2-followup-ready-a57fd07-6r-gpt55-20260619T004725Z-claw`
- CVRP:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-large-twoopt-bounded-ready-a57fd07-1r-gpt55-20260619T004725Z-claw`

Both roots are prepare-only and not started.

## Readiness Evidence

Both roots report:

- `static_ready=true`
- `launch_ready=false`
- `git_runtime_consistent=ok`
- `problem_specific_prepared_handoff=ok`
- `prompt_context_readiness_complete=ok`
- completion preflight `failed`
- HTTP `401`, `classification=not_authenticated`, `code=invalid_api_key`
- auth pool `active=0`, `expired=1`, `total=1`

The current blocker remains external `gpt-5.5` auth, not prepared-root static
readiness.

## Verification

Local:

```bash
PYTHONPATH=scion pytest -q \
  scion/scion/tests/test_launch_readiness.py \
  scion/scion/tests/test_postrun_artifact_inventory.py \
  scion/scion/tests/test_rebuild_prepared_handoff.py \
  scion/scion/tests/test_cvrp_agentic_launcher.py \
  scion/scion/tests/test_warehouse_agentic_launcher.py
# 51 passed
```

WSL:

```bash
PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion \
  /home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m pytest -q \
  scion/scion/tests/test_launch_readiness.py \
  scion/scion/tests/test_postrun_artifact_inventory.py \
  scion/scion/tests/test_rebuild_prepared_handoff.py \
  scion/scion/tests/test_cvrp_agentic_launcher.py \
  scion/scion/tests/test_warehouse_agentic_launcher.py
# 51 passed
```

## Acceptance

Accepted as launch-readiness auditability repair and prepared-root refresh. It
was later superseded after the postrun handoff review-ready guard changed a
runtime guard path.

Current refresh report:
`scion/docs/experiments/v0.4/v04-postrun-handoff-review-ready-guard-20260619.md`.
