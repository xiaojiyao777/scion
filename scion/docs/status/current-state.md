# Scion v0.4 Current State

*Last updated: 2026-05-10*

This file is the short operational snapshot for onboarding and day-to-day
handoff. Historical repair and experiment notes were moved to
[`v0.4-history.md`](v0.4-history.md). Detailed experiment analyses live under
[`../experiments/v0.4/`](../experiments/v0.4/).

## Status

v0.4 is not ready for long CVRP solver-quality validation. The framework
governance path is largely behaving, but CVRP `main_search_strategy` has not
yet produced case-level improvement.

Current branch: `v0.4-dev`

Current interpretation:

- Scion core remains problem-agnostic: proposal observations are tainted,
  Decision does not read proposal text, and problem semantics stay behind
  adapters/problem packages.
- Forced `main_search_strategy` diagnostics now stay on the selected surface,
  collect APS feedback, render tool observations into hypothesis/code prompts,
  and enforce selected-surface runtime audit.
- CVRP `main_search_strategy` is a controlled whole-algorithm orchestration
  surface, not permission to freely rewrite the original solver. It can choose
  and parameterize declared construction, baseline, improvement,
  acceptance/restart, perturbation, and optional post-baseline components.
- The higher-ceiling v3 path is no longer another small
  `main_search_strategy` knob. The current development slice adds a deep
  mechanism surface family with contracts, preview checks, and runtime audit:
  ALNS/VNS policy, destroy/repair policy, route-pair candidate policy, and
  acceptance/restart policy.
- APS observation budget for CVRP deep-surface diagnostics now uses the 48k
  default; the old 24k legacy budget is too tight once all mechanism contracts
  are visible.
- Latest campaign smoke evidence still predates that surface family and shows
  zero phase-best movement:
  `main_search_component_phase_delta_sum`, phase-improvement counts, and
  improvement-loop objective delta stayed zero for every screened candidate
  pair in the latest run.

Do not run long CVRP validation until a short diagnostic shows nonzero
phase-best improvement and screening-quality movement.

## Current Engineering State

### Framework Boundary

- Framework prompt assembly no longer hardcodes warehouse/VNS/CVRP mechanics.
- Problem-specific mechanics, objective semantics, feasibility, and runtime
  evidence interpretation live in problem adapters/packages.
- `ProblemSpecV1.research_surfaces` is the forward-compatible abstraction for
  optimization targets.
- Contract, Verification, Protocol, and Decision are surface-aware without
  embedding CVRP/warehouse-specific logic in core.
- Runtime env passthrough is generic for `SCION_*` variables.
- Legacy non-adapter paths remain compatibility-only; new problems should use
  `ProblemAdapter`.

### Campaign And APS

- `campaign.py` is now mostly a facade over extracted proposal, evaluation,
  promotion, evidence, failure-lifecycle, branch-stepping, workspace, and
  decision services.
- APS uses a two-phase proposal path for research/hypothesis and code
  implementation.
- Forced-surface controls are carried into APS tool context and fail closed
  before code generation.
- APS feedback defaults to same-campaign or forced-surface history for forced
  diagnostics.
- Tool observations are rendered into final hypothesis/code prompts.
- Observation-budget pressure is improved but still a recurring risk for large
  schema/contract previews.

### CVRP Runtime

- CVRP `.vrp` runs can use the repo-local `vrp/src` ALNS+VNS baseline when
  `SCION_PROBLEM_DATA_ROOT` points at the repo `vrp` directory.
- Required-baseline fallback or baseline errors are runtime audit failures, not
  objective ties.
- CVRPLIB internal node ids from `vrp/src` are mapped back into Scion's
  depot-first CVRP id space.
- Generated registry operators stop after a complete no-improvement round, so
  no-op post-baseline operators do not repeat for 20 rounds.
- Malformed, infeasible, exception-raising, or audit-incomplete outputs fail
  closed.

### CVRP Research Surfaces

CVRP currently exposes these declared surfaces:

- `route_local`
- `route_pair`
- `ruin_recreate`
- `search_policy`
- `baseline_policy`
- `construction_policy`
- `neighborhood_portfolio`
- `algorithm_blueprint`
- `main_search_strategy`
- `alns_vns_policy`
- `destroy_repair_policy`
- `route_pair_candidate_policy`
- `acceptance_restart_policy`

`main_search_strategy` is the preferred current diagnostic surface. It is a
singleton policy in `policies/main_search_strategy.py` and can coordinate:

- bounded construction ensemble;
- repo-local baseline budget and sanitized baseline params;
- package-owned improvement components: `intra_route_2opt`,
  `inter_route_relocate`, `route_pair_swap`, `bounded_destroy_repair`;
- strict-improvement acceptance threshold;
- restart and perturbation knobs, including explicit perturbation schedule;
- optional registry-operator round limit.

Current limitation: `main_search_strategy` can orchestrate declared components
but should not be treated as the whole research object. The deeper mechanism
surface family now exposes controlled hooks for ALNS/VNS params, destroy/repair
selection and repair budgets, route-pair candidate ranking, and
acceptance/restart/perturbation behavior. Active destroy/repair, route-pair, or
acceptance/restart mechanism policies can also trigger a package-owned default
main-search diagnostic plan, so those surfaces can generate runtime evidence
without simultaneously modifying `main_search_strategy.py`. Next validation
should be short and diagnostic-focused, proving nonzero mechanism-level behavior
before long formal CVRP validation.

## Latest Experiment

Active diagnostic run:

```text
run_root=/home/clawd/research/scion-experiments/v04-deep-mechanism-surfaces-sonnet-8r-20260510T161028Z
pid=2468567
model=claude-sonnet-4-6
protocol=formal
rounds=8
time_limit_sec=15
agentic_proposal=true
force_surface=none
status=running
analysis_doc=scion/docs/experiments/v0.4/v0.4-deep-mechanism-surfaces-sonnet-8r-20260510.md
```

Latest analyzed run:

```text
run_root=/home/clawd/research/scion-experiments/v04-perturbation-schedule-sonnet-8r-20260510T125915Z
scion_commit=c0d0c57
model=claude-sonnet-4-6
rounds=8/8
time_limit_sec=15
force_surface=main_search_strategy
exit_code=0
analysis_doc=scion/docs/experiments/v0.4/v0.4-perturbation-schedule-sonnet-8r-20260510.md
```

Summary:

- The run completed normally with five candidates reaching screening.
- Forced surface held for all hypotheses and code sessions:
  `modify/main_search_strategy -> policies/main_search_strategy.py`.
- APS used same-campaign screening/runtime feedback after prior rounds and
  rendered diagnosis/tool observations into prompts.
- The new `perturbation.schedule` field was exercised:
  `after_no_improvement`, `before_first_round`, `before_each_round`, and
  disabled perturbation.
- All screened candidates failed `SCREENING_FAIL_WIN_RATE`; best case-level
  win rate was `0.25`, and `median_delta=0.0` throughout.
- R4 failed hypothesis Contract at `C10_novelty` because the hypothesis omitted
  usable structured `novelty_signature` fields.
- R5/R7 passed proposal Contract but failed Verification because shallow-only
  plans left `main_search_deep_components_selected` empty.
- Runtime evidence showed accepted local moves did not become phase-best or
  case-level benefit.

Interpretation: `c0d0c57` validates perturbation-schedule surface control and
runtime reporting, not solver efficacy.

Detailed analysis:
[`v0.4-perturbation-schedule-sonnet-8r-20260510.md`](../experiments/v0.4/v0.4-perturbation-schedule-sonnet-8r-20260510.md)

## Validation

Latest full Scion test suite:

```bash
/home/clawd/miniconda3/envs/claw/bin/python -m pytest scion/scion/tests -q
```

```text
1533 passed, 1 skipped in 57.89s
```

Latest focused phase-benefit / forced-surface validation:

```bash
/home/clawd/miniconda3/envs/claw/bin/python -m pytest scion/scion/tests/test_cvrp_solver_operator_runtime.py scion/scion/tests/unit/test_agentic_proposal_tools.py scion/scion/tests/unit/test_research_surfaces.py -q
```

```text
189 passed in 12.30s
```

Latest selected-surface/proposal boundary validation:

```bash
/home/clawd/miniconda3/envs/claw/bin/python -m pytest scion/scion/tests/test_protocol.py::test_run_experiment_preserves_selected_surface_required_runtime_metrics scion/scion/tests/test_cvrp_protocol_smoke.py scion/scion/tests/test_cvrp_solver_vrp_smoke.py scion/scion/tests/unit/core/test_proposal_pipeline.py -q
```

```text
39 passed in 12.58s
```

Broader CVRP/protocol subset:

```bash
/home/clawd/miniconda3/envs/claw/bin/python -m pytest scion/scion/tests/test_cvrp_*.py scion/scion/tests/unit/evidence/test_cvrp_*.py scion/scion/tests/test_protocol.py scion/scion/tests/unit/test_agentic_proposal_tools.py -q
```

```text
227 passed in 34.29s
```

## Next Actions

P1:

- Align proposal/schema preview with the selected-surface runtime contract so
  shallow-only `main_search_strategy` plans either fail before code generation
  or encode an explicit valid no-deep-components state.
- Make missing or empty structured `novelty_signature` failures compact,
  preview-visible, and actionable before final hypothesis acceptance.
- Add proposal feedback reason tags for `MAIN_SEARCH_ZERO_PHASE_DELTA` and
  `RECOVERY_ONLY_ACCEPTED_MOVES`.
- Stop treating isolated orchestration tweaks as the next CVRP efficacy path.
  Use the deep mechanism surface family (`alns_vns_policy`,
  `destroy_repair_policy`, `route_pair_candidate_policy`, and
  `acceptance_restart_policy`) for the next CVRP diagnostics.
- Continue only short CVRP diagnostics until those surfaces show nonzero
  phase-best movement or clearly attributed mechanism-level behavior beyond
  component permutation.

P2:

- Persist actual `DecisionFeatures` lineage and improve soft-abandon decision
  provenance.
- Move remaining problem-specific runtime-field heuristics out of proposal
  context.
- Consider a typed-collaborator pass for campaign composition to reduce
  callback coupling.
- Add a dedicated CLI/readiness command for formal campaign closeout.

## Remaining Risks

- CVRP `main_search_strategy` is too shallow by itself to produce meaningful
  algorithmic gains; without the deep mechanism surface family, agents mostly
  permute a fixed algorithm.
- Proposal preview and runtime audit can still disagree for strategies that
  are syntactically valid but semantically incompatible with diagnostic
  expectations.
- Runtime isolation is resource-limited and env-sanitized, but not yet a full
  read-only mount sandbox.
- Stale/reconcile semantics still need a dedicated v3-aligned review.
- Legacy/no-adapter V8 objective-only comparison remains compatibility-only.

## History

- Full historical status log:
  [`v0.4-history.md`](v0.4-history.md)
- Experiment index:
  [`../experiments/v0.4/README.md`](../experiments/v0.4/README.md)
- Latest experiment analysis:
  [`v0.4-perturbation-schedule-sonnet-8r-20260510.md`](../experiments/v0.4/v0.4-perturbation-schedule-sonnet-8r-20260510.md)
