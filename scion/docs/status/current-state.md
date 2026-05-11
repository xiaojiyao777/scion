# Scion v0.4 Current State

*Last updated: 2026-05-11*

This file is the short operational snapshot for onboarding and day-to-day
handoff. Historical repair and experiment notes were moved to
[`v0.4-history.md`](v0.4-history.md). Detailed experiment analyses live under
[`../experiments/v0.4/`](../experiments/v0.4/).

## Status

v0.4 is not ready for long CVRP solver-quality validation. The framework
governance path is largely behaving, but CVRP short diagnostics still have not
produced reliable screening-quality improvement. The latest solver-design
problem-object diagnostic was terminated early because it exposed a control
loop bug: after one `solver_design` candidate failed heavy Verification, APS
treated the top-level surface as globally blacklisted and fell back to
component-policy exploration. That is not a valid test of the problem-object
research boundary. A repair now keeps heavy solver-design candidate failures
candidate-scoped and adds APS/context guidance; run one short free-surface
diagnostic to validate boundary control before solver-quality validation.

Current branch: `v0.4-dev`

Current interpretation:

- Scion core remains problem-agnostic: proposal observations are tainted,
  Decision does not read proposal text, and problem semantics stay behind
  adapters/problem packages.
- Forced single-surface diagnostics have done their job for governance and
  runtime-audit validation. They should not continue as the main optimization
  path.
- CVRP now declares `solver_design` as the top-level research boundary backed
  by `policies/main_search_strategy.py`. Deep mechanism policies remain useful
  implementation hooks and attribution sources, but they are not standalone
  research goals.
- The first free solver-design diagnostic did select `solver_design` in round
  1, but a `V5_solution_consistency` failure made later APS sessions reason
  from "`solver_design` is blacklisted" and return to component surfaces. This
  is a governance/proposal-feedback failure, not evidence that the surface is
  exhausted.
- Heavy Verification failures under declared `solver_design` surfaces now mark
  only the candidate implementation `rejected`; hypothesis context and APS
  feedback explicitly recommend retrying the problem-object boundary rather
  than falling back to component policies.
- The higher-ceiling v3 path should be a problem-object adaptation path:
  instance model, solution model, objective policy, move/design affordances,
  solver lifecycle, and whole-solver evidence should be rendered by the adapter
  as one coherent object for Scion to reason over.
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
  enum-interface rerun's Contract preview passed for all 7 completed code
  sessions.
- Forced-surface controls fail closed, and the final hypothesis-generation task
  now narrows `change_locus`, `action`, and `target_file` to active forced
  values instead of presenting the full surface list. The latest forced
  `destroy_repair_policy` rerun validated this in real APS traces.
- The latest code also makes `destroy_repair_policy` selector levers real:
  `route_diverse_worst` changes destroy ranking and `cheapest` uses a
  low-budget cheapest repair path instead of all selectors flowing through the
  same worst-removal/regret-2 implementation.
- The CVRP adapter-rendered `destroy_repair_policy` interface now lists valid
  `destroy_selectors`, `repair_selectors`, and `subset_strategy` values
  explicitly, including a warning not to put `single_worst` or `route_diverse`
  in `destroy_selectors`.
- The latest enum-interface rerun validates that model-facing repair but also
  demonstrates the limit of policy-by-policy exposure: 7 valid screened
  `destroy_repair_policy` candidates made 7,168 destroy/repair attempts across
  112 pairs with zero accepted current/recovery/phase-best moves and
  `destroy_repair_phase_delta_sum=0.0`.

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
- Solver-design pre-screening failures are rendered as boundary-control
  guidance: rejected or blacklisted solver-design entries are candidate
  failures, not retirement of the problem-level surface.
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
- `solver_design`
- `alns_vns_policy`
- `destroy_repair_policy`
- `route_pair_candidate_policy`
- `acceptance_restart_policy`

`solver_design` is the problem-owned solver-design surface. It is backed by
the singleton execution file `policies/main_search_strategy.py` and can
coordinate:

- bounded construction ensemble;
- repo-local baseline budget and sanitized baseline params;
- package-owned improvement components: `intra_route_2opt`,
  `inter_route_relocate`, `route_pair_swap`, `bounded_destroy_repair`;
- strict-improvement acceptance threshold;
- restart and perturbation knobs, including explicit perturbation schedule;
- optional registry-operator round limit.

Current limitation: the top-level boundary is declared and the control-loop
repair is implemented, but it has not yet been validated in a live diagnostic.
Stop forced component-policy diagnostics; next run a short free-surface
diagnostic and verify that a failed candidate implementation under
`solver_design` causes another solver-design attempt rather than a fallback to
isolated component surfaces.

## Latest Experiment

Latest analyzed run:

```text
run_root=/home/clawd/research/scion-experiments/v04-solver-design-problem-object-sonnet-12r-20260511T140118Z
model=claude-sonnet-4-6
problem=cvrp
protocol=formal
rounds_requested=12
rounds_completed_before_termination=11
screened_experiments=9
time_limit_sec=30
agentic_proposal=true
agentic_session_timeout_sec=720
force_surface=none
stop_reason=manual_termination_invalid_control_loop
analysis_doc=scion/docs/experiments/v0.4/v0.4-solver-design-problem-object-sonnet-12r-terminated-20260511.md
```

Summary:

- The run was launched from clean commit `7d78f2f` and manually terminated with
  `EXIT_CODE:143` during round 12.
- Round 1 selected `solver_design` and targeted
  `policies/main_search_strategy.py`; APS Contract preview passed with
  `main_search_problem_object_evidence_alignment`.
- The first solver-design implementation failed heavy Verification
  `V5_solution_consistency`.
- After that, `solver_design` was treated as blacklisted. Subsequent hypotheses
  repeatedly stated that premise and selected component surfaces instead:
  `baseline_policy`, `route_local`, `algorithm_blueprint`,
  `destroy_repair_policy`, `acceptance_restart_policy`, `alns_vns_policy`,
  `route_pair_candidate_policy`, `construction_policy`,
  `neighborhood_portfolio`, and active `search_policy` when terminated.
- All 9 screened non-`solver_design` candidates passed Contract and
  Verification but failed screening with `win_rate=0.0` and `median_delta=0.0`.

Interpretation: this is not solver-efficacy evidence. It is a control-loop
failure: a single candidate verification failure must not globally blacklist
the top-level problem-object surface. APS should retry `solver_design` with a
different lifecycle implementation and keep component policies as
implementation/attribution hooks, not fallback research goals.

Detailed analysis:
[`v0.4-solver-design-problem-object-sonnet-12r-terminated-20260511.md`](../experiments/v0.4/v0.4-solver-design-problem-object-sonnet-12r-terminated-20260511.md)

Previous analyzed run:

```text
run_root=/home/clawd/research/scion-experiments/v04-forced-destroy-repair-policy-enum-interface-sonnet-8r-20260511T114551Z
model=claude-sonnet-4-6
problem=cvrp
protocol=formal
rounds_requested=8
rounds_completed=8
time_limit_sec=20
agentic_proposal=true
agentic_session_timeout_sec=480
force_surface=destroy_repair_policy
stop_reason=max_rounds_exhausted
analysis_doc=scion/docs/experiments/v0.4/v0.4-forced-destroy-repair-policy-enum-interface-sonnet-8r-20260511.md
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
- The enum-interface repair is validated: all 7 completed code sessions passed
  `proposal.contract_preview`, and `verification_failure_breakdown={}`.
- Solver efficacy still failed: 7 candidates reached screening and all failed
  `SCREENING_FAIL_WIN_RATE`; all had `win_rate=0.125` and `median_delta=0.0`.
- One round failed at hypothesis Contract with `C10_novelty` because the
  structured novelty signature omitted required destroy/repair identity fields.
- Destroy/repair attribution was complete but non-beneficial across 112
  screened pairs: 7,168 attempts, 7,168 repair-budget units used, zero accepted
  current/recovery/phase-best moves, and
  `destroy_repair_phase_delta_sum=0.0`.
- The valid policies exercised both `regret_2` and `cheapest`, both allowed
  destroy selectors, and max-destroy/budget patterns from 2..10 and 6..16. The
  mechanism still produced only `repair_budget_exhausted` or
  `repair_produced_no_improvement`.

Interpretation: `destroy_repair_policy` is no longer blocked by prompt routing,
selector implementation, or selector enum clarity. It is exhausted as a forced
diagnostic target for the current solver-owned mechanism. More importantly,
this run confirms that continuing to force one policy hook at a time is the
wrong optimization strategy. The next step is the problem-object adaptation
pivot, not another forced policy run.

Detailed analysis:
[`v0.4-forced-destroy-repair-policy-enum-interface-sonnet-8r-20260511.md`](../experiments/v0.4/v0.4-forced-destroy-repair-policy-enum-interface-sonnet-8r-20260511.md)

Previous analyzed run:

```text
run_root=/home/clawd/research/scion-experiments/v04-forced-destroy-repair-policy-selector-repair-sonnet-8r-20260511T092047Z
model=claude-sonnet-4-6
problem=cvrp
protocol=formal
rounds=8/8
time_limit_sec=20
agentic_proposal=true
agentic_session_timeout_sec=360
force_surface=destroy_repair_policy
stop_reason=max_rounds_exhausted
analysis_doc=scion/docs/experiments/v0.4/v0.4-forced-destroy-repair-policy-selector-repair-sonnet-8r-20260511.md
```

## Validation

Latest solver-design boundary-control repair validation:

```bash
/home/clawd/miniconda3/envs/claw/bin/python -m pytest scion/scion/tests/unit/test_sprint_m.py scion/scion/tests/unit/test_research_surfaces.py scion/scion/tests/unit/test_agentic_proposal_tools.py scion/scion/tests/unit/core/test_proposal_pipeline.py scion/scion/tests/test_problem_bridge.py scion/scion/tests/test_cvrp_adapter.py scion/scion/tests/test_cvrp_solver_operator_runtime.py -q
```

```text
301 passed in 18.24s
```

Latest full Scion test suite:

```bash
/home/clawd/miniconda3/envs/claw/bin/python -m pytest scion/scion/tests -q
```

```text
1567 passed, 1 skipped in 62.12s
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
252 passed in 18.19s
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

- Run a short free-surface diagnostic validating the repaired solver-design
  control loop; terminate early if APS falls back to component surfaces after a
  solver-design candidate failure.
- If control holds, inspect whether solver-level hypotheses generate
  whole-solver evidence and nonzero phase-best movement.
- Stop forced single-policy diagnostics for now, including
  `route_pair_candidate_policy`.

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

- CVRP `solver_design` has not yet been validly evaluated. The control-loop
  repair is implemented in tests but not yet validated by a live short
  diagnostic.
- CVRP's current research-surface set still contains many component hooks. It
  risks optimizing whatever hook is exposed unless APS keeps prioritizing the
  problem-object solver-design boundary.
- Deep-surface runtime attribution is improved for `alns_vns_policy` and
  mechanically complete for `destroy_repair_policy`, but still thin for
  `acceptance_restart_policy` and `route_pair_candidate_policy`.
- `destroy_repair_policy` now has validated prompt routing, selector semantics,
  enum clarity, and complete runtime attribution, but no useful movement in the
  current solver-owned mechanism.
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
  [`v0.4-solver-design-problem-object-sonnet-12r-terminated-20260511.md`](../experiments/v0.4/v0.4-solver-design-problem-object-sonnet-12r-terminated-20260511.md)
- Problem-object adaptation pivot:
  [`problem-object-adaptation-pivot.md`](../engineering/problem-object-adaptation-pivot.md)
