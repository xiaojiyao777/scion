# v0.4 Solver Source-Read Headroom Readiness

Date: 2026-06-19

## Purpose

Focused warehouse and CVRP v0.4 launches must give the agent enough source
visibility to make concrete solver changes. The CVRP active solver files were
close enough to the old 24k solver-read defaults that source grounding could
become fragile, even though final code prompts already carried approved target
source. This repair gives solver-design reads enough headroom without turning
generic code tools into unbounded context dumps.

## Repair

- Local commit: `eef75f17` (`Raise solver source read headroom`).
- WSL commit: `cf8fb5a7` (`Raise solver source read headroom`).
- Solver-design target-file reads and code-phase surface reads now use `96000`
  chars.
- Generic non-solver code-surface reads remain at `12000` chars.
- Bounded algorithm slices remain at `24000` chars.
- CVRP solver-design support artifacts now keep enough compact budget to include
  the active object-model summary alongside `baseline_algorithm.py`,
  `scheduler.py`, and `state.py` context.

## Verification

Local:

```bash
PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion pytest -q \
  scion/scion/tests/unit/test_agentic_session_tool_selection.py \
  scion/scion/tests/unit/test_agentic_session_surface_reads.py \
  scion/scion/tests/unit/test_agentic_proposal_tools_context.py \
  scion/scion/tests/unit/test_agentic_solver_design_active_tools.py \
  scion/scion/tests/unit/test_agentic_target_file_grounding.py \
  scion/scion/tests/unit/test_agentic_session_model_planner.py \
  scion/scion/tests/unit/test_agentic_session_model_planner_fallbacks.py \
  scion/scion/tests/unit/test_agentic_session_grounding.py \
  scion/scion/tests/unit/test_agentic_solver_design_grounding.py \
  scion/scion/tests/unit/test_agentic_observation_ledger.py \
  scion/scion/tests/unit/test_agentic_active_algorithm_facts_prompt.py

PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion pytest -q \
  scion/scion/tests/unit/test_agentic_session_budget_limits.py \
  scion/scion/tests/unit/test_agentic_schema_permissions_budget.py \
  scion/scion/tests/unit/test_cvrp_active_solver_map_provider.py \
  scion/scion/tests/unit/test_research_surfaces_cvrp_context.py \
  scion/scion/tests/unit/test_agentic_code_stage_invariants.py \
  scion/scion/tests/unit/test_agentic_solver_design_prompt_payloads.py
```

Result: `142 passed in 95.38s`; `65 passed in 2.50s`.

WSL:

```bash
PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion \
  /home/xjy-ubuntu/miniconda3/envs/scion/bin/pytest -q \
  scion/scion/tests/unit/test_agentic_session_tool_selection.py \
  scion/scion/tests/unit/test_agentic_session_surface_reads.py \
  scion/scion/tests/unit/test_agentic_proposal_tools_context.py \
  scion/scion/tests/unit/test_agentic_solver_design_active_tools.py \
  scion/scion/tests/unit/test_agentic_target_file_grounding.py \
  scion/scion/tests/unit/test_agentic_session_model_planner.py \
  scion/scion/tests/unit/test_agentic_session_model_planner_fallbacks.py \
  scion/scion/tests/unit/test_agentic_session_grounding.py \
  scion/scion/tests/unit/test_agentic_solver_design_grounding.py \
  scion/scion/tests/unit/test_agentic_observation_ledger.py \
  scion/scion/tests/unit/test_agentic_active_algorithm_facts_prompt.py

PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion \
  /home/xjy-ubuntu/miniconda3/envs/scion/bin/pytest -q \
  scion/scion/tests/unit/test_agentic_session_budget_limits.py \
  scion/scion/tests/unit/test_agentic_schema_permissions_budget.py \
  scion/scion/tests/unit/test_cvrp_active_solver_map_provider.py \
  scion/scion/tests/unit/test_research_surfaces_cvrp_context.py \
  scion/scion/tests/unit/test_agentic_code_stage_invariants.py \
  scion/scion/tests/unit/test_agentic_solver_design_prompt_payloads.py
```

Result: `142 passed in 77.42s`; `65 passed in 1.08s`.

## Initial Prepared Roots

Warehouse:

`/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-v2-followup-sourceheadroom-cf8fb5a7-preflight-6r-gpt55-20260619T210116Z-claw`

CVRP:

`/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-large-twoopt-sourceheadroom-cf8fb5a7-preflight-1r-gpt55-20260619T210116Z-claw`

The CVRP 1R root above was a source-headroom diagnostic root. It has been
superseded for Phase 4 launch by the 4R root documented in
`scion/docs/experiments/v0.4/v04-cvrp-phase4-four-round-root-readiness-20260619.md`.

The warehouse root above was the initial source-headroom prepared root. It has
been superseded for launch by the measurement-note regenerated root documented
in
`scion/docs/experiments/v0.4/v04-warehouse-measurement-note-root-readiness-20260619.md`
because `scion/problems/warehouse_delivery/protocol_prod.yaml` is covered by the
runtime guard.

Both roots report:

- `static_ready=true`
- `launch_ready=false`
- `git_runtime_consistent=ok`
- `git_runtime_worktree_clean=ok`
- `run_script_pythonpath_enforced=ok`
- APS headroom values: `3600`/`240`/`200`/`200`/`2000000`
- Proposal headroom values: `64`/`64`

The remaining launch blocker is external WSL `gpt-5.5` provider auth. Strict
completion preflight returns HTTP `401`, `classification=not_authenticated`,
`code=invalid_api_key`, with auth pool `active=0` and no launch-usable account.

## Acceptance

Accepted as the prepare-only source-read repair evidence. Its initial prepared
roots have both been superseded for launch by later current roots. It does not
close v0.4; closure still requires live warehouse follow-up to show useful
post-v2 research behavior and live CVRP follow-up to produce evidence-backed
solver-design progress.
