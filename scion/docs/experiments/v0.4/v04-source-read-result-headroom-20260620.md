# Source Read Result Headroom

Date: 2026-06-20

## Decision

The current v0.4 source-visibility guarantee requires direct solver/source
reads to survive both the requested source window and the generic tool result
boundary. `context.read_algorithm_file`, `context.read_algorithm_symbol`, and
`context.read_surface` now align tool schema defaults, registry result caps,
ledger argument normalization, and active solver source-preview headroom around
the 96k source window used by current solver-design/code prompts.

This is generic proposal/source visibility behavior. It does not add
CVRP/warehouse semantics to `DecisionFeatures`, promotion, scheduler state, or
solver behavior.

## Repaired Failure Mode

The active-solver and surface-read schemas exposed large enough source windows
for code-phase research, but the tools still inherited smaller generic result
caps. A valid source read between 32k and 96k characters could therefore fail
as `RESULT_TOO_LARGE` before the agent saw the research object code.

Two related drift points were also repaired:

- Observation-ledger normalization defaulted algorithm source reads to 12k,
  smaller than the actual source-read schema.
- Active solver symbol lookup previewed only the first 12k characters, so a
  symbol later in a large target file could be missed even when the caller
  requested a large source window.

## Implementation

- `ContextReadAlgorithmFileTool.max_result_chars=160000`
- `ContextReadAlgorithmSymbolTool.max_result_chars=160000`
- `ContextReadSurfaceTool.max_result_chars=180000`
- `read_algorithm_file` and `read_algorithm_symbol` ledger defaults now use
  `max_chars=96000`
- Active solver source-preview headroom is now 96k

## Verification

Local:

```bash
pytest \
  scion/scion/tests/unit/test_agentic_solver_design_active_tools.py \
  scion/scion/tests/unit/test_agentic_proposal_tools_context.py \
  scion/scion/tests/unit/test_agentic_observation_ledger.py -q
```

Result: `38 passed`.

Local adjacent APS source-visibility suite:

```bash
pytest \
  scion/scion/tests/unit/test_agentic_session_tool_selection.py \
  scion/scion/tests/unit/test_agentic_session_surface_reads.py \
  scion/scion/tests/unit/test_agentic_target_file_grounding.py \
  scion/scion/tests/unit/test_agentic_solver_design_grounding.py \
  scion/scion/tests/unit/test_agentic_session_model_planner.py \
  scion/scion/tests/unit/test_agentic_session_model_planner_fallbacks.py -q
```

Result: `87 passed`.

WSL focused suite with explicit checkout `PYTHONPATH`:

```bash
PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion \
  /home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m pytest \
  scion/scion/tests/unit/test_agentic_solver_design_active_tools.py \
  scion/scion/tests/unit/test_agentic_proposal_tools_context.py \
  scion/scion/tests/unit/test_agentic_observation_ledger.py \
  scion/scion/tests/unit/test_agentic_session_tool_selection.py \
  scion/scion/tests/unit/test_agentic_session_surface_reads.py \
  scion/scion/tests/unit/test_agentic_target_file_grounding.py \
  scion/scion/tests/unit/test_agentic_solver_design_grounding.py \
  scion/scion/tests/unit/test_agentic_session_model_planner.py \
  scion/scion/tests/unit/test_agentic_session_model_planner_fallbacks.py -q
```

Result: `125 passed`.

## Prepared Roots From This Repair

These roots are superseded by the later disabled code-tool-call cap runtime
repair. See `scion/docs/status/current-state.md` for the current launch roots.

Generated on WSL at launch-authoritative runtime commit `37feae79`; the local
runtime-equivalent commit is `f7745a8e`. Both roots are mirrored under
`/home/clawd/research/scion-experiments/` with the same directory names.

- Warehouse:
  `/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-v2-followup-size70hypctx-37feae79-nocaps-aps0-sourceheadroom-preflight-6r-gpt55-20260620T113041Z-claw`
- CVRP:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-large-twoopt-phase4-size70hypctx-37feae79-nocaps-aps0-sourceheadroom-preflight-4r-gpt55-20260620T113058Z-claw`

Strict launch readiness for both reports:

- `static_ready=true`
- `launch_ready=false`
- `failed_static_required_checks=[]`
- `failed_required_checks=["completion_preflight"]`
- runtime guard OK for prepared commit `37feae79`
- proposal/APS disabled-cap details remain explicit with `disabled_count=18`
- source/budget/headroom warning count is `0`

The remaining blocker is external `gpt-5.5` completion auth:
HTTP `401`, `classification=not_authenticated`, `code=invalid_api_key`;
auth pool `active=0`, `total=1`.
