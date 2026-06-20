# Code Prompt Solver Source 96k Projection Repair

Date: 2026-06-20

## Decision

Code-generation prompts must preserve the same 96k solver/source read window
that the active solver-design tools expose. `context.read_algorithm_file` and
`context.read_algorithm_symbol` are proposal-only source-visibility material,
but they are the object the coding agent needs to reason about; they should not
be reduced by legacy prompt-projection caps while the current v0.4 no-cap roots
are testing effective research behavior.

## Issue

The tool layer had been repaired so active solver reads could return 96k
payloads, but the code prompt projection still used smaller caps:

- `_CODE_PROMPT_ALGORITHM_FILE_CHARS = 24000`
- `_CODE_PROMPT_ALGORITHM_SYMBOL_CHARS = 12000`

The dedicated full algorithm-file prompt section was built from the already
compacted observation payload, so a large read could be displayed as the
solver-design full file while still containing only the first 24k characters.
Algorithm-symbol reads were kept in the compact payload, but the final prompt
had no dedicated source section for them, leaving targeted symbol source easy to
lose behind generic observation receipts.

## Boundary

This repair changes only proposal/code prompt source projection. It does not
change Decision, `DecisionFeatures`, Protocol metrics, promotion, scheduler
state, problem diagnostics, solver semantics, or positive/negative evidence
interpretation.

## Implementation

- Code-prompt algorithm-file and algorithm-symbol caps now use the active solver
  source headroom constant: 96k.
- The final prompt now renders a dedicated solver-design algorithm-symbol source
  section, alongside the full algorithm-file section.
- Generic observation rendering deduplicates both dedicated full-file and
  dedicated symbol-source observations, so source remains visible once in the
  source sections instead of being replaced by receipts.
- Both dedicated source sections are grouped into the stable code-source cache
  block for solver-design code prompts, keeping source separate from dynamic
  retry and previous-patch feedback.
- Regression tests assert markers beyond the old 24k and 12k projection windows
  survive through the compact code payload and the complete rendered prompt.

## Verification

Local:

```bash
pytest -q scion/scion/tests/unit/test_agentic_solver_design_prompt_payloads.py::test_code_phase_projects_full_algorithm_file_source_to_96k_window scion/scion/tests/unit/test_agentic_solver_design_prompt_payloads.py::test_code_phase_projects_algorithm_symbol_source_to_96k_window
pytest -q scion/scion/tests/unit/test_agentic_solver_design_prompt_payloads.py scion/scion/tests/unit/test_agentic_active_algorithm_facts_prompt.py scion/scion/tests/unit/test_agentic_target_file_grounding.py scion/scion/tests/unit/test_code_edit_protocol.py
pytest -q scion/scion/tests/unit/test_agentic_session_surface_reads.py scion/scion/tests/unit/test_agentic_session_grounding.py scion/scion/tests/unit/test_agentic_session_budget_limits.py scion/scion/tests/unit/test_agentic_session_tool_selection.py scion/scion/tests/unit/test_agentic_session_model_planner_fallbacks.py scion/scion/tests/unit/test_agentic_session_model_planner.py
python -m py_compile scion/scion/proposal/agentic_code_context.py scion/scion/proposal/engine/prompt/solver_context_receipts.py scion/scion/proposal/engine/prompt/observations.py scion/scion/proposal/engine/prompt_common.py scion/scion/tests/unit/test_agentic_solver_design_prompt_payloads.py
git diff --check
```

Results: `2 passed`, `118 passed`, `67 passed`, compile clean, and diff check
clean. The symbol-source regression also asserts that the dedicated source
section and late marker are present in the stable system source block.

WSL with explicit checkout `PYTHONPATH` and launch Python:

```bash
PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion \
  /home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m py_compile \
  scion/scion/proposal/agentic_code_context.py \
  scion/scion/proposal/engine/prompt/solver_context_receipts.py \
  scion/scion/proposal/engine/prompt/observations.py \
  scion/scion/proposal/engine/prompt_common.py \
  scion/scion/tests/unit/test_agentic_solver_design_prompt_payloads.py

PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion \
  /home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m pytest -q \
  scion/scion/tests/unit/test_agentic_solver_design_prompt_payloads.py \
  scion/scion/tests/unit/test_agentic_active_algorithm_facts_prompt.py \
  scion/scion/tests/unit/test_agentic_target_file_grounding.py \
  scion/scion/tests/unit/test_code_edit_protocol.py

PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion \
  /home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m pytest -q \
  scion/scion/tests/unit/test_agentic_session_surface_reads.py \
  scion/scion/tests/unit/test_agentic_session_grounding.py \
  scion/scion/tests/unit/test_agentic_session_budget_limits.py \
  scion/scion/tests/unit/test_agentic_session_tool_selection.py \
  scion/scion/tests/unit/test_agentic_session_model_planner_fallbacks.py \
  scion/scion/tests/unit/test_agentic_session_model_planner.py
```

Results: compile clean, `118 passed`, and `67 passed`.

## Current Prepared Roots

Generated on WSL at launch-authoritative runtime commit `7468fbe4`; the local
runtime-equivalent commit is `0549df7c`. Both roots are mirrored under
`/home/clawd/research/scion-experiments/` with the same directory names.

- Warehouse:
  `/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-v2-followup-size70hypctx-7468fbe4-nocaps-aps0-sourceheadroom-codecap0-plannercap0-previewcap0-artifactcap0-reserve0-fullsurf-prompt96k-symbolcache-preflight-6r-gpt55-20260620T133929Z-claw`
- CVRP:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-large-twoopt-phase4-size70hypctx-7468fbe4-nocaps-aps0-sourceheadroom-codecap0-plannercap0-previewcap0-artifactcap0-reserve0-fullsurf-prompt96k-symbolcache-preflight-4r-gpt55-20260620T133930Z-claw`

Strict launch readiness for both reports:

- `static_ready=true`
- `launch_ready=false`
- exit `64`
- `failed_static_required_checks=[]`
- `failed_required_checks=["completion_preflight"]`
- prompt context readiness `ok`
- runtime guard `ok` for prepared commit `7468fbe4`

The remaining blocker is external `gpt-5.5` completion auth:
HTTP `401`, `classification=not_authenticated`, `code=invalid_api_key`;
auth pool `active=0`, `total=1`. The auth substate is volatile and may appear
as `expired` or `refreshing`; launch remains blocked until an active account is
available.
