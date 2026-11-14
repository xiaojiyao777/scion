# Disabled Code Planner Reserve Repair

Date: 2026-06-20

## Decision

When APS step/tool/observation caps are disabled, code-phase planner prompts
must not present a fixed self-check reserve budget. The planner should see the
same reserve semantics that runtime uses: disabled limits have zero reserve,
not a hardcoded 4 tool calls and 4 steps.

## Issue

`_run_code_context_tool_loop()` used runtime helpers for the actual
code-tool-call limit, but its planner context still hardcoded:

- `reserved_for_self_check.tool_calls=4`
- `reserved_for_self_check.steps=4`

For current no-cap v0.4 roots, that was not a runtime gate, but it was still
provider-visible budgeting advice. It could make the LLM self-throttle
code-phase source reads even though `agentic_tool_max_steps=0`,
`agentic_tool_max_calls=0`, and `agentic_observation_max_chars=0` are meant to
disable those research caps.

## Boundary

This is proposal-only planner prompt metadata. It does not change Decision,
`DecisionFeatures`, Protocol metrics, promotion, scheduler state,
problem-owned diagnostics, solver semantics, or positive-cap runtime reserves.

## Implementation

- Code-phase planner context now builds `reserved_for_self_check` from
  `_self_check_tool_call_reserve()`, `_self_check_step_reserve()`, and
  `_self_check_observation_reserve_chars()`.
- The planner context also records `reserved_for_self_check.enabled`, so
  disabled caps are explicit rather than represented as fixed reserve slots.
- A no-cap code-phase regression asserts that the planner context keeps
  `max_code_tool_calls_enabled=false` and exposes zero self-check reserve.

## Verification

Local:

```bash
pytest scion/scion/tests/unit/test_agentic_session_surface_reads.py::test_zero_code_tool_call_budget_does_not_disable_code_phase_planner -q
python -m py_compile scion/scion/proposal/agentic_session_code_tools.py scion/scion/tests/unit/test_agentic_session_surface_reads.py
pytest scion/scion/tests/unit/test_agentic_session_surface_reads.py scion/scion/tests/unit/test_agentic_session_tool_selection.py scion/scion/tests/unit/test_agentic_session_model_planner_fallbacks.py -q
pytest scion/scion/tests/unit/test_agentic_session_grounding.py scion/scion/tests/unit/test_agentic_session_preview_budget.py -q
git diff --check
```

Results: `1 passed`, compile clean, `33 passed`, `20 passed`, and diff check
clean.

WSL with explicit checkout `PYTHONPATH` and launch Python:

```bash
PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion \
  /home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m pytest \
  /home/xjy-ubuntu/research/or-autoresearch-agent/scion/scion/tests/unit/test_agentic_session_surface_reads.py \
  /home/xjy-ubuntu/research/or-autoresearch-agent/scion/scion/tests/unit/test_agentic_session_tool_selection.py \
  /home/xjy-ubuntu/research/or-autoresearch-agent/scion/scion/tests/unit/test_agentic_session_model_planner_fallbacks.py -q

PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion \
  /home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m pytest \
  /home/xjy-ubuntu/research/or-autoresearch-agent/scion/scion/tests/unit/test_agentic_session_grounding.py \
  /home/xjy-ubuntu/research/or-autoresearch-agent/scion/scion/tests/unit/test_agentic_session_preview_budget.py -q
```

Results: `33 passed`, `20 passed`.

## Prepared Roots From This Repair

Generated on WSL at launch-authoritative runtime commit `8427fc84`; the local
runtime-equivalent commit is `5bc05de0`. Both roots are mirrored under
`/home/clawd/research/scion-experiments/` with the same directory names.

These roots were superseded after the disabled code-surface full-read repair.
Use `scion/docs/status/current-state.md` for the current launch roots.

- Warehouse:
  `/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-v2-followup-size70hypctx-8427fc84-nocaps-aps0-sourceheadroom-codecap0-plannercap0-previewcap0-artifactcap0-reserve0-preflight-6r-gpt55-20260620T124740Z-claw`
- CVRP:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-large-twoopt-phase4-size70hypctx-8427fc84-nocaps-aps0-sourceheadroom-codecap0-plannercap0-previewcap0-artifactcap0-reserve0-preflight-4r-gpt55-20260620T124755Z-claw`

Strict launch readiness for both reports:

- `static_ready=true`
- `launch_ready=false`
- exit `64`
- `failed_static_required_checks=[]`
- `failed_required_checks=["completion_preflight"]`
- prompt context readiness `ok`
- runtime guard `ok` for prepared commit `8427fc84`

The remaining blocker is external `gpt-5.5` completion auth:
HTTP `401`, `classification=not_authenticated`, `code=invalid_api_key`;
auth pool `active=0`, `total=1`.
