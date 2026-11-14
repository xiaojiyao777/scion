# CVRP Quality-Blocked Postrun Evidence

Date: 2026-06-19

## Purpose

CVRP postrun delegated analysis now exposes taxonomy-backed proposal
quality-block evidence for no-protocol bounded two-opt conclusions. This keeps a
quality-blocked run distinct from protocol-evaluated no-effect, missing
two-opt-signal, and bounded-two-opt-ready conclusions.

This is report-only audit surface. It does not change Decision,
`DecisionFeatures`, Protocol gates, promotion, scheduler state, or solver
behavior.

## Change

- `postrun_analysis_brief.py` renders CVRP quality-block signal counts and
  reason mix in the markdown brief, matching the warehouse follow-up surface.
- Postrun acceptance tests now cover
  `quality_blocked_no_protocol_twoopt_conclusion` as analysis-ready only when
  the problem summary and current-run `failure_taxonomy_summary` agree on
  quality-block evidence.
- The stale-summary case now fails readiness when the problem summary claims
  CVRP quality-blocked evidence but failure taxonomy has no current-run
  quality-block signal.

## Verification

Local:

- `python -m py_compile scion/tools/postrun_analysis_brief.py scion/scion/tests/test_postrun_analysis_brief.py scion/scion/tests/test_check_postrun_acceptance.py`
- `PYTHONPATH=scion pytest -q scion/scion/tests/test_postrun_analysis_brief.py scion/scion/tests/test_check_postrun_acceptance.py`
  - `66 passed`
- `git diff --check`

WSL:

- `/home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m py_compile scion/tools/postrun_analysis_brief.py scion/scion/tests/test_postrun_analysis_brief.py scion/scion/tests/test_check_postrun_acceptance.py`
- `PYTHONPATH=scion /home/xjy-ubuntu/miniconda3/envs/scion/bin/pytest -q scion/scion/tests/test_postrun_analysis_brief.py scion/scion/tests/test_check_postrun_acceptance.py`
  - `66 passed`

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
