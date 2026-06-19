# Quality-Blocked No-Protocol Consistency

Date: 2026-06-19

## Purpose

Warehouse and CVRP postrun acceptance now reject hand-written
`quality_blocked_no_protocol_*` conclusions when protocol accounting shows that
a candidate was already protocol-evaluated. A no-protocol quality-blocked
conclusion is valid only for proposal-quality blockage before protocol
evaluation; protocol-evaluated runs must satisfy the interpretation-specific
measurement, runtime, and continuity inputs.

This is report-only delegated-readiness hygiene. It does not change Decision,
`DecisionFeatures`, Protocol gates, promotion, scheduler state, or solver
behavior.

## Change

- `check_postrun_acceptance.py` now fails
  `problem_summary_input_consistency` with
  `quality_blocked_no_protocol_has_protocol_evaluated_candidates` whenever a
  quality-blocked no-protocol interpretation has protocol-evaluated candidates
  in either the problem summary or protocol-accounting review input.
- Regression coverage was added for both warehouse plateau and CVRP bounded
  two-opt summaries.

## Verification

Local:

- `python -m py_compile scion/tools/check_postrun_acceptance.py scion/scion/tests/test_check_postrun_acceptance.py`
- `PYTHONPATH=scion pytest -q scion/scion/tests/test_check_postrun_acceptance.py`
  - `41 passed`
- `PYTHONPATH=scion pytest -q scion/scion/tests/test_postrun_analysis_brief.py scion/scion/tests/test_rebuild_postrun_acceptance.py scion/scion/tests/test_postrun_artifact_inventory.py`
  - `47 passed`
- `git diff --check`

WSL:

- `/home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m py_compile scion/tools/check_postrun_acceptance.py scion/scion/tests/test_check_postrun_acceptance.py`
- `PYTHONPATH=scion /home/xjy-ubuntu/miniconda3/envs/scion/bin/pytest -q scion/scion/tests/test_check_postrun_acceptance.py`
  - `41 passed`
- `PYTHONPATH=scion /home/xjy-ubuntu/miniconda3/envs/scion/bin/pytest -q scion/scion/tests/test_postrun_analysis_brief.py scion/scion/tests/test_rebuild_postrun_acceptance.py scion/scion/tests/test_postrun_artifact_inventory.py`
  - `47 passed`

## Current Prepared Roots

Because this touched `scion/tools`, current WSL prepared roots were regenerated
from WSL runtime commit `bea482de`:

- Warehouse:
  `/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-v2-followup-noprotocol-bea482de-6r-gpt55-20260619T172019Z-claw`
- CVRP:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-large-twoopt-noprotocol-bea482de-1r-gpt55-20260619T172019Z-claw`

Strict WSL launch readiness for both roots reports `static_ready=true` and
`launch_ready=false`; the failed required check is still completion preflight.
Real chat completion preflight returns HTTP `401`,
`classification=not_authenticated`, `code=invalid_api_key`, with auth pool
`active=0`, `expired=1`, `total=1`.
