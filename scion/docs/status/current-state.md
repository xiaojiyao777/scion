# Scion v0.4 Current State

*Last updated: 2026-05-11*

This file is the short operational snapshot for onboarding and day-to-day
handoff. Historical repair and experiment notes were moved to
[`v0.4-history.md`](v0.4-history.md). Detailed experiment analyses live under
[`../experiments/v0.4/`](../experiments/v0.4/).

## Status

v0.4 is not ready for long CVRP solver-quality validation. The framework
governance path is largely behaving, but CVRP short diagnostics still have not
produced reliable screening-quality improvement. The latest post-optimization
smoke improved deep-surface selection and ALNS/VNS attribution, and the
follow-up control-plane repair now compacts preview payloads and reserves
self-check observation budget more aggressively. Forced
`destroy_repair_policy` diagnostics now complete 8/8 rounds without
forced-surface violations or circuit breaker failure. The selector-semantics
rerun confirmed the selector fields are real, but still failed screening
quality and exposed a model-facing interface gap: candidates repeatedly put
`subset_strategy` values such as `route_diverse` and `single_worst` into
`destroy_selectors`. The latest code repairs the rendered surface interface by
listing the disjoint enum sets explicitly. Screening gates still fail.

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
- APS observation handling for CVRP deep-surface diagnostics now uses the 48k
  default, compact 800-character surface code previews, and an explicit
  terminal reserve for schema/target/interface/Contract previews after
  required diagnosis context has been gathered.
- The latest free-surface post-optimization smoke selected two newly added
  deep mechanism surfaces: `alns_vns_policy` and
  `acceptance_restart_policy`. `destroy_repair_policy` and
  `route_pair_candidate_policy` still were not selected.
- ALNS/VNS attribution is now explainable: the selected `alns_vns_policy`
  candidate recorded nonzero `alns_vns_phase_delta_sum`, construction-start
  distance, returned baseline distance, and objective deltas. This validates
  attribution plumbing, not solver efficacy.
- APS self-check reservation now preserves tool calls and observation-char
  headroom for compact schema/target/interface/Contract previews. The latest
  forced diagnostics reached final self-checks without `result_too_large`; the
  selector-semantics rerun's Contract preview found issues in 6/8 completed
  code sessions before real Verification failed those candidates.
- Forced-surface controls fail closed, and the final hypothesis-generation task
  now narrows `change_locus`, `action`, and `target_file` to active forced
  values instead of presenting the full surface list. The latest forced
  `destroy_repair_policy` rerun validated this in real APS traces.
- The latest code also makes `destroy_repair_policy` selector levers real:
  `route_diverse_worst` changes destroy ranking and `cheapest` uses a
  low-budget cheapest repair path instead of all selectors flowing through the
  same worst-removal/regret-2 implementation.
- The latest selector-semantics rerun shows those levers still do not produce
  useful movement by themselves: two screened candidates exhausted all
  destroy/repair budgets with zero accepted current or phase-best moves.
- The CVRP adapter-rendered `destroy_repair_policy` interface now lists valid
  `destroy_selectors`, `repair_selectors`, and `subset_strategy` values
  explicitly, including a warning not to put `single_worst` or `route_diverse`
  in `destroy_selectors`.

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
- Observation-budget pressure is mitigated by compact surface reads, compact
  preview payloads, and a self-check/static-preview reserve. Optional planner
  surface reads fail closed before consuming the reserve.
- Campaign-level forced-surface diagnostics now carry the forced
  surface/action/target into APS tools and the final CreativeLayer hypothesis
  task. APS still fails closed if a model produces an off-surface hypothesis.

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

`main_search_strategy` is the orchestration diagnostic surface. It is a
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
without simultaneously modifying `main_search_strategy.py`. Proposal feedback
now exposes generic diagnostic priorities and tags deep/mechanism surfaces that
have not yet been exercised, all-zero phase/objective-delta fields, and
accepted/recovery movement without phase-level benefit. Next validation should
be short and diagnostic-focused. Rerun `destroy_repair_policy` once after the
enum-interface repair, then move to `route_pair_candidate_policy` if valid
destroy/repair candidates still show no nonzero phase-best movement.

## Latest Experiment

Latest analyzed run:

```text
run_root=/home/clawd/research/scion-experiments/v04-forced-destroy-repair-policy-selector-repair-sonnet-8r-20260511T092047Z
model=claude-sonnet-4-6
problem=cvrp
protocol=formal
rounds_requested=8
rounds_completed=8
time_limit_sec=20
agentic_proposal=true
agentic_session_timeout_sec=360
force_surface=destroy_repair_policy
stop_reason=max_rounds_exhausted
analysis_doc=scion/docs/experiments/v0.4/v0.4-forced-destroy-repair-policy-selector-repair-sonnet-8r-20260511.md
```

Summary:

- The run completed all 8 requested rounds and stopped by
  `max_rounds_exhausted`; `circuit_breaker_tripped=false`.
- All 8 hypotheses targeted `modify/destroy_repair_policy` and
  `policies/destroy_repair_policy.py`. No forced-surface violation appeared in
  `campaign_summary.json`.
- The forced task line remains validated in real traces: all 8 hypothesis
  traces contained the forced `destroy_repair_policy` task line, and 0
  contained the old generic "Choose a research surface from ..." task line.
- Solver efficacy still failed: 2 candidates reached screening and both failed
  `SCREENING_FAIL_WIN_RATE`; 6 candidates failed Verification with
  `V5_solution_consistency`.
- Screened candidates had win rates `0.125` and `0.25`, both with
  `median_delta=0.0`.
- Destroy/repair attribution was complete but non-beneficial across 32
  screened pairs: 2,048 attempts, 2,048 repair-budget units used, zero accepted
  current/recovery/phase-best moves, and
  `destroy_repair_phase_delta_sum=0.0`.
- `proposal.contract_preview` found issues for 6/8 completed code sessions,
  but preview remains advisory; real Verification caught the selected-surface
  runtime evidence failures.
- Failed workspaces repeatedly used `route_diverse` or `single_worst` as
  `destroy_selectors`, even though those values belong only in
  `subset_strategy`. The latest code repairs the rendered interface by listing
  these enum sets explicitly.

Interpretation: forced-surface routing and selector implementation are no
longer the active blockers. The active blocker is valid, useful mechanism
variation in `destroy_repair_policy`. Rerun once after the enum-interface
repair; if valid candidates still show zero phase movement, move to
`route_pair_candidate_policy`.

Detailed analysis:
[`v0.4-forced-destroy-repair-policy-selector-repair-sonnet-8r-20260511.md`](../experiments/v0.4/v0.4-forced-destroy-repair-policy-selector-repair-sonnet-8r-20260511.md)

Previous analyzed run:

```text
run_root=/home/clawd/research/scion-experiments/v04-forced-destroy-repair-policy-prompt-repair-sonnet-8r-20260511T073512Z
model=claude-sonnet-4-6
problem=cvrp
protocol=formal
rounds=8/8
time_limit_sec=20
agentic_proposal=true
agentic_session_timeout_sec=360
force_surface=destroy_repair_policy
stop_reason=max_rounds_exhausted
analysis_doc=scion/docs/experiments/v0.4/v0.4-forced-destroy-repair-policy-prompt-repair-sonnet-8r-20260511.md
```

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

Latest APS/CVRP optimization validation:

```bash
/home/clawd/miniconda3/envs/claw/bin/python -m pytest scion/scion/tests/unit/test_agentic_proposal_tools.py scion/scion/tests/unit/test_research_surfaces.py scion/scion/tests/test_problem_bridge.py scion/scion/tests/test_cvrp_solver_operator_runtime.py scion/scion/tests/test_cvrp_adapter.py -q
```

```text
247 passed in 17.62s
```

Latest focused APS preview-budget validation:

```bash
/home/clawd/miniconda3/envs/claw/bin/python -m pytest scion/scion/tests/unit/test_agentic_proposal_tools.py -q
```

```text
86 passed in 1.97s
```

Latest forced-prompt narrowing validation:

```bash
/home/clawd/miniconda3/envs/claw/bin/python -m pytest scion/scion/tests/unit/test_sprint_j3_prompt_plumbing.py scion/scion/tests/unit/test_research_surfaces.py scion/scion/tests/unit/test_agentic_proposal_tools.py scion/scion/tests/unit/core/test_proposal_pipeline.py -q
```

```text
198 passed in 3.03s
```

Latest CVRP destroy/repair selector/proposal validation:

```bash
/home/clawd/miniconda3/envs/claw/bin/python -m pytest scion/scion/tests/test_cvrp_solver_operator_runtime.py scion/scion/tests/test_cvrp_adapter.py scion/scion/tests/unit/test_sprint_j3_prompt_plumbing.py scion/scion/tests/unit/test_research_surfaces.py scion/scion/tests/unit/test_agentic_proposal_tools.py scion/scion/tests/unit/core/test_proposal_pipeline.py -q
```

```text
285 passed in 18.53s
```

## Next Actions

P1:

- Rerun the forced `destroy_repair_policy` 8-round diagnostic after the
  enum-interface repair. Judge it first on whether invalid selector
  Verification failures disappear and whether valid `route_diverse_worst` or
  `cheapest` variants reduce repair-budget exhaustion or produce nonzero
  accepted phase-best movement.
- If valid destroy/repair policies still show zero phase movement, stop forcing
  `destroy_repair_policy` and move to `route_pair_candidate_policy`.
- Add a route-local runtime-summary bridge if future operator-surface runs keep
  showing useful generic operator telemetry but empty selected-surface summaries.
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
- Fix model-facing tool-selection prompt sanitization that can render
  `feedback.query_holdout_summary` as an empty allowed tool name.

## Remaining Risks

- CVRP `main_search_strategy` is too shallow by itself to produce meaningful
  algorithmic gains; without explicit deep-surface prioritization, agents
  mostly revisit orchestration and legacy policy surfaces.
- Deep-surface runtime attribution is improved for `alns_vns_policy` and
  mechanically complete for `destroy_repair_policy`, but still thin for
  `acceptance_restart_policy` and `route_pair_candidate_policy`.
- The `destroy_repair_policy` enum-interface repair is unit-tested but not yet
  validated by a real forced campaign.
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
  [`v0.4-forced-destroy-repair-policy-selector-repair-sonnet-8r-20260511.md`](../experiments/v0.4/v0.4-forced-destroy-repair-policy-selector-repair-sonnet-8r-20260511.md)
