# CVRP Adaptive Trigger Proposal Context Repair

Date: 2026-06-17

## Verdict

Accepted as a problem-owned proposal-context repair. The cadence-2 adaptive
embedded-VNS opportunity is now visible to CVRP solver-design hypothesis
generation as advisory research context.

This is not a Decision, Protocol, lifecycle, promotion, or `DecisionFeatures`
change. It does not change the canonical solver default. It gives the agent a
specific, evidence-backed refinement target instead of a vague "improve ALNS"
or "remove VNS" prompt.

## Rationale

The compact adaptive-trigger matrix from commit `eddaf8c` selected cadence-2
as the best current opportunity source:

- embedded-VNS share: `0.653 -> 0.528`;
- mean ALNS iterations: `4.0 -> 6.0`;
- median paired delta: `0.0`;
- mean paired delta: `+1.8`;
- route/fleet regressions: `0`;
- cadence-4 and broad VNS removal remain rejected.

The agent should refine cadence-2 using objective, remaining-budget, recent
best-update, or repaired-candidate-improvement signals. It must not hardcode
case ids, BKS values, seeds, split membership, or broad VNS removal.

## Implementation

Files changed:

- `scion/scion/problems/cvrp/solver_design_provider.py`
- `scion/scion/proposal/context_manager/manager.py`
- `scion/scion/tests/unit/test_cvrp_solver_design_provider.py`
- `scion/scion/tests/unit/test_research_surfaces_cvrp_context.py`

Behavior:

- `CvrpSolverDesignProvider.solver_design_hypothesis_guidance()` includes the
  cadence-2 opportunity as proposal-only advisory guidance.
- `ContextManager.build_hypothesis_context()` now returns the resolved
  solver-design prompt provider, matching the existing code-context behavior,
  so hypothesis prompts can consume problem-owned provider guidance.
- Tests assert that the actual CVRP hypothesis prompt contains the cadence-2
  opportunity and the anti-overfit constraints.

## Local Acceptance

Commands:

```bash
PYTHONPATH=$PWD/scion python -m py_compile \
  scion/scion/problems/cvrp/solver_design_provider.py \
  scion/scion/proposal/context_manager/manager.py

PYTHONPATH=$PWD/scion pytest -q \
  scion/scion/tests/unit/test_cvrp_solver_design_provider.py \
  scion/scion/tests/unit/test_research_surfaces_cvrp_context.py \
  scion/scion/tests/unit/test_agentic_solver_design_prompt_payloads.py

git diff --check
```

Results:

- py_compile passed.
- Provider/context/prompt tests: `44 passed`.
- `git diff --check` passed.

A broader context/manifest sweep was also attempted:

```bash
PYTHONPATH=$PWD/scion pytest -q \
  scion/scion/tests/unit/test_hypothesis_context_profiles.py \
  scion/scion/tests/unit/test_context_manager_modularization.py \
  scion/scion/tests/unit/test_agentic_proposal_tools_context.py \
  scion/scion/tests/unit/test_prompt_manifest_accounting.py \
  scion/scion/tests/unit/core/test_proposal_pipeline_hypothesis.py
```

It produced `58 passed, 1 failed`. The failure was
`test_read_main_search_strategy_default_returns_compact_contract_below_budget`,
which expected `policies/baseline_modules/state.py` in `context.read_surface`
support artifacts. That path is separate from this proposal-provider repair and
does not exercise the new hypothesis-context provider hook.

## Next Gate

Run a short CVRP agentic refinement campaign from this context. Acceptance
should require:

- hypothesis prompt manifests contain the cadence-2 opportunity;
- generated hypotheses refine adaptive embedded-VNS scheduling rather than
  removing VNS broadly;
- telemetry declarations use a specific mechanism id and problem-owned runtime
  evidence;
- the resulting candidate is evaluated against canonical ALNS+VNS and the
  current CVRP MDE, not only aggregate win rate.
