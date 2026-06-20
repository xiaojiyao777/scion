# Disabled Code Surface Full-Read Repair

Date: 2026-06-20

## Decision

When APS observation caps are disabled, mandatory code-phase surface reads must
remain full reads. The fallback path may still compact a required surface read
under a real positive observation budget, but a no-cap root must not downgrade
`context.read_surface(detail="full")` to the 800-character compact surface
merely because the target algorithm file is already visible.

## Issue

`_run_code_context_fixed_tools()` read the solver target file first and then
treated `target_read_available=true` as enough reason to compress the mandatory
code-phase surface read. In current no-cap warehouse/CVRP roots this meant the
agent could receive a 96k `context.read_algorithm_file` target read, but the
required `context.read_surface` fallback still appeared as
`code_phase_required_compact` with the compact 800-character surface preview.

That was still proposal-only context, but it contradicted the v0.4 no-cap
launch intent: code-phase prompts should keep direct source visibility for the
research object instead of inheriting a leftover observation-budget reserve
heuristic.

## Boundary

This repair changes only APS proposal-tool source visibility under disabled
observation caps. It does not change Decision, `DecisionFeatures`, Protocol
metrics, promotion, scheduler state, problem-owned diagnostics, solver
semantics, or positive-cap compact behavior.

## Implementation

- Code-phase mandatory target/surface reads now set preserved observation chars
  only when `agentic_observation_max_chars` is greater than zero.
- Mandatory surface compaction now requires a real enabled observation budget;
  `target_read_available` alone no longer compresses no-cap surface reads.
- A no-cap regression asserts that fixed code-phase fallback reads the solver
  target file at 96k and keeps the required solver surface read `full`,
  `max_chars=96000`, and `truncated=false`, with no
  `code_phase_required_compact` transcript entry.

## Verification

Local:

```bash
pytest -q scion/scion/tests/unit/test_agentic_session_surface_reads.py
pytest -q scion/scion/tests/unit/test_agentic_session_surface_reads.py scion/scion/tests/unit/test_agentic_session_grounding.py scion/scion/tests/unit/test_agentic_session_budget_limits.py scion/scion/tests/unit/test_agentic_session_tool_selection.py scion/scion/tests/unit/test_agentic_session_model_planner_fallbacks.py
python -m py_compile scion/scion/proposal/agentic_session_code_tools.py scion/scion/tests/unit/test_agentic_session_surface_reads.py
git diff --check
```

Results: `5 passed`, `53 passed`, compile clean, and diff check clean.

WSL with explicit checkout `PYTHONPATH` and launch Python:

```bash
PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion \
  /home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m py_compile \
  scion/scion/proposal/agentic_session_code_tools.py \
  scion/scion/tests/unit/test_agentic_session_surface_reads.py

PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion \
  /home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m pytest -q \
  scion/scion/tests/unit/test_agentic_session_surface_reads.py \
  scion/scion/tests/unit/test_agentic_session_grounding.py \
  scion/scion/tests/unit/test_agentic_session_budget_limits.py \
  scion/scion/tests/unit/test_agentic_session_tool_selection.py \
  scion/scion/tests/unit/test_agentic_session_model_planner_fallbacks.py
```

Results: compile clean and `53 passed`.

## Prepared Roots From This Repair

These roots captured the prepared state immediately after the disabled
code-surface full-read repair. They are no longer the active launch roots; the
current launch-authoritative roots live in
`scion/docs/status/current-state.md`.

Generated on WSL at launch-authoritative runtime commit `9a81e10b`; the local
runtime-equivalent commit is `dcbc0d57`. Both roots are mirrored under
`/home/clawd/research/scion-experiments/` with the same directory names.

- Warehouse:
  `/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-v2-followup-size70hypctx-9a81e10b-nocaps-aps0-sourceheadroom-codecap0-plannercap0-previewcap0-artifactcap0-reserve0-fullsurf-preflight-6r-gpt55-20260620T130253Z-claw`
- CVRP:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-large-twoopt-phase4-size70hypctx-9a81e10b-nocaps-aps0-sourceheadroom-codecap0-plannercap0-previewcap0-artifactcap0-reserve0-fullsurf-preflight-4r-gpt55-20260620T130255Z-claw`

Strict launch readiness for both reports:

- `static_ready=true`
- `launch_ready=false`
- exit `64`
- `failed_static_required_checks=[]`
- `failed_required_checks=["completion_preflight"]`
- prompt context readiness `ok`
- runtime guard `ok` for prepared commit `9a81e10b`

The remaining blocker is external `gpt-5.5` completion auth:
HTTP `401`, `classification=not_authenticated`, `code=invalid_api_key`;
auth pool `active=0`, `expired=1`, `total=1`.
