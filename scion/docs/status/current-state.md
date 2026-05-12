# Scion v0.4 Current State

*Last updated: 2026-05-12*

This file is the short operational snapshot for onboarding and day-to-day
handoff. Historical repair and experiment notes were moved to
[`v0.4-history.md`](v0.4-history.md). Detailed experiment analyses live under
[`../experiments/v0.4/`](../experiments/v0.4/).

## Status

v0.4 is not ready for long CVRP solver-quality validation. The framework
governance path is largely behaving, but CVRP short diagnostics still have not
produced reliable screening-quality improvement. The latest solver-design
problem-adaptation repair validates the live codegen/Contract path: APS can
generate `solver_design` patches whose `problem_adaptation.component_roles`
describe lifecycle role targets, whose `evidence_targets` name actual runtime
audit fields, and whose returned `main_search_plan()` does not leak
proposal-only `novelty_signature` metadata. Two consecutive completed code
sessions passed APS schema/target/Contract previews, formal Contract,
Verification, and selected-surface runtime audit with
`main_search_strategy_errors=0`, then failed screening with `win_rate=0.0`,
`median_delta=0.0`, and zero main-search phase-best movement.

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
- The latest contract repair is a framework/problem-boundary repair, not a
  solver-quality improvement. `novelty_signature` is hypothesis metadata only;
  generated policy/config dictionaries must not copy it unless a surface
  explicitly declares that key. `problem_adaptation.component_roles` may now
  describe lifecycle targets such as construction, repo-local baseline,
  strict-improvement acceptance, restart, perturbation, and package-owned
  main-search components. `evidence_targets` may name the actual
  `main_search_*` audit fields that proposal feedback uses.
- The first free solver-design diagnostic did select `solver_design` in round
  1, but a `V5_solution_consistency` failure made later APS sessions reason
  from "`solver_design` is blacklisted" and return to component surfaces. This
  is a governance/proposal-feedback failure, not evidence that the surface is
  exhausted.
- Heavy Verification failures under declared `solver_design` surfaces now mark
  only the candidate implementation `rejected`; hypothesis context and APS
  feedback explicitly recommend retrying the problem-object boundary rather
  than falling back to component policies.
- The follow-up boundary-repair diagnostic selected `solver_design` twice and
  reached screening both times, but then drifted to `baseline_policy` after
  zero-movement screening failures. The latest code now makes `solver_design`
  an active problem boundary: proposal context, APS tools, target preview, and
  final hypothesis prompts reject component-policy `change_locus` values when
  no forced diagnostic surface is active.
- The latest active-boundary and semantic-identity diagnostics confirm boundary
  control in live free-surface runs: all completed or partial APS outputs stayed
  on `solver_design` after heavy Verification and zero/low-movement screening
  failures.
- Active-boundary APS tool guidance now distinguishes a problem-object boundary
  from `--force-surface`: traces render `active_problem_boundary_rule` with
  `allowed_surface_ids=["solver_design"]`, not a fake forced-surface rule with
  `[null]`.
- For semantic-signature solver-design hypotheses, `selected_components` and
  `deep_components_selected` must be non-empty arrays. Schema preview and
  ContractGate fail closed on missing, false, empty, or empty-sequence identity.
- APS self-check failures now fail closed for real sessions. Schema/target
  preview failures, skipped Contract previews, or failed Contract previews stop
  the completed output before the patch enters evaluation.
- The higher-ceiling v3 path is now a problem-object adaptation path:
  instance model, solution model, objective policy, move/design affordances,
  solver lifecycle, and whole-solver evidence are rendered by the adapter as
  one coherent object for Scion to reason over. The current blocker is no
  longer failure to expose that object; it is that the package-owned CVRP
  main-search execution path still does not produce phase-best improvement over
  the repo-local baseline.
- APS observation handling for CVRP deep-surface diagnostics now uses the 64k
  default, compact 800-character surface code previews, and an explicit
  terminal reserve for schema/target/interface/Contract previews after
  required diagnosis context has been gathered. Terminal Contract preview keeps
  compact deterministic pass/fail evidence if the full preview payload would
  exceed the remaining observation budget. This is now validated in live
  free-surface runs: completed code sessions passed Contract preview and no APS
  `output.json` in the latest run contained `result_too_large`.
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
- When declared and not overridden by `--force-surface`, `solver_design` is
  carried as an active problem-object boundary into proposal context, APS tool
  context, target previews, and output validation. Component policies are
  implementation hooks or attribution evidence, not top-level `change_locus`
  replacements.
- Real APS sessions fail closed when schema/target/Contract self-check
  previews fail or are skipped.
- APS feedback defaults to same-campaign or forced-surface history for forced
  diagnostics.
- Tool observations are rendered into final hypothesis/code prompts.
- Observation-budget pressure is mitigated by compact surface reads, compact
  preview payloads, and a self-check/static-preview reserve. Optional planner
  surface reads fail closed before consuming the reserve.
- Solver-design pre-screening and screening failures are rendered as
  boundary-control guidance: rejected or blacklisted solver-design entries are
  candidate failures, not retirement of the problem-level surface.
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
  `inter_route_relocate`, `route_pair_swap`, `bounded_destroy_repair`,
  `route_pool_recombination`;
- strict-improvement acceptance threshold;
- restart and perturbation knobs, including explicit perturbation schedule;
- optional registry-operator round limit.

Current limitation: the top-level boundary, active-boundary tool guidance,
Contract-preview budget repair, non-empty semantic identity, and
problem-adaptation codegen contract are live-validated. Solver-design candidate
quality is still too weak. The bounded destroy/repair execution repair is
complete but insufficient: live screening showed accepted/recovery movement
and clean runtime attribution, yet zero phase-best movement. The route-pool
repair now gives `solver_design` a package-owned whole-solution component and
feedback telemetry, but live screening did not validate quality:
`route_pool_recombination` built route pools and branch-searched on 16/16
pairs, yet accepted zero recombined route sets and produced zero route-pool
phase-best movement. Do not run long CVRP validation until route-pool
candidate generation/recombination can produce local and short-screening
phase-best movement.

## Latest Experiment

Latest analyzed run:

```text
run_root=/home/clawd/research/scion-experiments/v04-route-pool-recombination-telemetry-sonnet-8r-20260512T121501Z
model=claude-sonnet-4-6
problem=cvrp
protocol=formal
rounds_requested=8
rounds_completed_before_termination=1
screened_experiments=1
time_limit_sec=45
agentic_proposal=true
agentic_session_timeout_sec=900
force_surface=none
stop_reason=manual_termination_after_first_complete_screening_route_pool_telemetry_valid_but_zero_recombination_phase
analysis_doc=scion/docs/experiments/v0.4/v0.4-route-pool-recombination-telemetry-sonnet-terminated-20260512.md
```

Summary:

- The run was terminated early after one complete screening because it
  validated route-pool execution/telemetry but repeated the same zero route-pool
  quality failure; continuing the same 8-round campaign would spend budget on a
  known-bad lifecycle shape.
- The completed candidate stayed on `solver_design`, targeted
  `policies/main_search_strategy.py`, passed screening execution with
  `main_search_strategy_errors=0`, and produced 16/16 valid pairs.
- Screening result: 1 win, 3 losses, 12 ties, `median_delta=0.0`, and decision
  abandon (`T4: win_rate < 0.3`). Median runtime ratio was 1.083 and runtime
  regression rate was 1.0.
- Runtime result: runtime selected and attempted `route_pool_recombination`,
  `route_pair_swap`, and `bounded_destroy_repair` on all 16 pairs.
  Route-pool telemetry was present on all pairs:
  source-solution counts 6-8, route-pool sizes 16-64, and 580 total branch
  calls. `main_search_route_pool_recombined_routes=0` and
  `main_search_component_phase_delta_sum.route_pool_recombination=0.0` on all
  16 pairs.

Interpretation: the route-pool repair fixed the exposure/feedback problem.
Scion can now see and execute the whole-solution primitive. The remaining
blocker is route-pool solver quality: generated pools are too weak or the
bounded recombination search is too restrictive to produce accepted route-set
recombinations over the repo-local phase best.

Detailed analysis:
[`v0.4-route-pool-recombination-telemetry-sonnet-terminated-20260512.md`](../experiments/v0.4/v0.4-route-pool-recombination-telemetry-sonnet-terminated-20260512.md)

Previous analyzed run:

```text
run_root=/home/clawd/research/scion-experiments/v04-solver-design-semantic-identity-guidance-sonnet-4r-20260512T020020Z
model=claude-sonnet-4-6
problem=cvrp
protocol=formal
rounds_requested=4
rounds_completed=4
screened_experiments=3
time_limit_sec=30
agentic_proposal=true
agentic_session_timeout_sec=600
force_surface=none
stop_reason=max_rounds_exhausted
analysis_doc=scion/docs/experiments/v0.4/v0.4-solver-design-semantic-identity-guidance-sonnet-4r-20260512.md
```

Summary:

- The run launched from clean commit `8618917` and completed with
  `EXIT_CODE:0`.
- All persisted hypotheses and completed/partial APS outputs stayed on
  `solver_design` targeting `policies/main_search_strategy.py`. No
  component-policy fallback occurred.
- The repaired active-boundary trace used `active_problem_boundary_rule` with
  `allowed_surface_ids=["solver_design"]`; the invalid pre-run bug
  (`forced_surface_rule`, `allowed_surface_ids=[null]`) did not recur.
- All four persisted hypotheses supplied non-empty `selected_components` and
  `deep_components_selected`.
- Four code sessions completed with `schema_valid=true` and
  `contract_preview_passed=true`; no APS `output.json` contained
  `result_too_large`.
- Three candidates passed Contract and Verification, then failed screening with
  `win_rate` values `0.0`, `0.125`, and `0.0`; all had `median_delta=0.0`.
- The fourth candidate passed Contract but failed heavy Verification
  `V5_solution_consistency` because selected-surface runtime evidence had empty
  `main_search_deep_components_selected`.
- Candidate diversity improved: the run tried different baseline fractions,
  component sets, restart/perturbation patterns, rounds, and top-k values.

Interpretation: active boundary control, active-boundary tool guidance,
Contract-preview budget retention, and non-empty semantic identity are
live-validated. Solver-design quality remains the blocker: screened candidates
still had zero main-search phase-best movement, and the only nonzero win-rate
signal came with runtime regression.

Detailed analysis:
[`v0.4-solver-design-semantic-identity-guidance-sonnet-4r-20260512.md`](../experiments/v0.4/v0.4-solver-design-semantic-identity-guidance-sonnet-4r-20260512.md)

Previous analyzed run:

```text
run_root=/home/clawd/research/scion-experiments/v04-active-boundary-contract-preview-budget-sonnet-4r-20260512T003103Z
model=claude-sonnet-4-6
problem=cvrp
protocol=formal
rounds_requested=4
rounds_completed=4
screened_experiments=2
time_limit_sec=30
agentic_proposal=true
agentic_session_timeout_sec=600
force_surface=none
stop_reason=max_rounds_exhausted
analysis_doc=scion/docs/experiments/v0.4/v0.4-active-boundary-contract-preview-budget-sonnet-4r-20260512.md
```

Summary:

- The run launched from clean commit `4e88a2d` and completed with
  `EXIT_CODE:0`.
- All persisted hypotheses and completed/partial APS outputs stayed on
  `solver_design` targeting `policies/main_search_strategy.py`.
- Three code sessions completed with `schema_valid=true` and
  `contract_preview_passed=true`; no APS `output.json` contained
  `result_too_large`.
- Two candidates passed Contract and Verification, then failed screening with
  `win_rate=0.0` and `median_delta=0.0`; one candidate passed Contract but
  failed heavy Verification.
- The final hypothesis session failed closed before approval because schema
  preview found `novelty_signature.deep_components_selected=[]`.

Interpretation: active boundary control and Contract-preview budget retention
were live-validated. The next repair tightened semantic identity and
active-boundary tool guidance.

Detailed analysis:
[`v0.4-active-boundary-contract-preview-budget-sonnet-4r-20260512.md`](../experiments/v0.4/v0.4-active-boundary-contract-preview-budget-sonnet-4r-20260512.md)

Previous analyzed run:

```text
run_root=/home/clawd/research/scion-experiments/v04-active-solver-design-boundary-sonnet-4r-20260511T180413Z
model=claude-sonnet-4-6
problem=cvrp
protocol=formal
rounds_requested=4
rounds_completed=4
screened_experiments=1
time_limit_sec=30
agentic_proposal=true
agentic_session_timeout_sec=600
force_surface=none
stop_reason=max_rounds_exhausted
analysis_doc=scion/docs/experiments/v0.4/v0.4-active-solver-design-boundary-sonnet-4r-20260511.md
```

Summary:

- The run launched from clean commit `1c79c1e` and completed with
  `EXIT_CODE:0`.
- All persisted hypotheses and APS outputs stayed on `solver_design` targeting
  `policies/main_search_strategy.py`. No component-policy fallback occurred.
- The first candidate failed heavy Verification `V5_solution_consistency`.
- The second candidate passed Contract and Verification, then failed screening
  with `win_rate=0.0` and `median_delta=0.0`.
- The third hypothesis stayed on `solver_design`, but two code sessions failed
  closed because Contract preview was replaced by `result_too_large,
  tool_error` after APS had consumed about `44.3k/48k` observation chars.

Interpretation: active boundary control was validated. The remaining blocker
was APS preview-budget handling; this has since been repaired and validated in
the 2026-05-12 short diagnostic.

Detailed analysis:
[`v0.4-active-solver-design-boundary-sonnet-4r-20260511.md`](../experiments/v0.4/v0.4-active-solver-design-boundary-sonnet-4r-20260511.md)

Previous analyzed run:

```text
run_root=/home/clawd/research/scion-experiments/v04-solver-design-boundary-repair-sonnet-4r-20260511T164524Z
model=claude-sonnet-4-6
problem=cvrp
protocol=formal
rounds_requested=4
rounds_completed_before_termination=3
screened_experiments=2
time_limit_sec=30
agentic_proposal=true
agentic_session_timeout_sec=600
force_surface=none
stop_reason=manual_termination_invalid_active_boundary
analysis_doc=scion/docs/experiments/v0.4/v0.4-solver-design-boundary-repair-sonnet-4r-terminated-20260511.md
```

Previous analyzed run:

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

Latest solver-design problem-adaptation contract validation:

```bash
PYTHONPATH=scion /home/clawd/miniconda3/envs/claw/bin/python -m pytest -q scion/scion/tests/test_cvrp_adapter.py::test_cvrp_main_search_strategy_preview_accepts_lifecycle_roles_and_runtime_targets scion/scion/tests/test_cvrp_adapter.py::test_cvrp_main_search_strategy_preview_rejects_novelty_signature_in_plan scion/scion/tests/unit/test_research_surfaces.py::test_cvrp_main_search_strategy_problem_adaptation_drives_order_and_thresholds scion/scion/tests/unit/test_research_surfaces.py::test_context_exposes_search_policy_surface_and_modify_when_no_operator_pool scion/scion/tests/test_proposal_validation.py::test_hypothesis_runtime_intent_fields_parse_and_format
```

```text
5 passed in 0.42s
```

Latest related proposal/CVRP subset:

```bash
PYTHONPATH=scion /home/clawd/miniconda3/envs/claw/bin/python -m pytest -q scion/scion/tests/test_cvrp_adapter.py scion/scion/tests/unit/test_research_surfaces.py scion/scion/tests/test_proposal_validation.py
```

```text
133 passed in 4.66s
```

Latest full Scion test suite:

```bash
PYTHONPATH=scion /home/clawd/miniconda3/envs/claw/bin/python -m pytest -q scion/scion/tests
```

```text
1590 passed, 1 skipped in 67.22s
```

Latest main-search route-pool telemetry contract validation:

```bash
PYTHONPATH=scion /home/clawd/miniconda3/envs/claw/bin/python -m pytest -q scion/scion/tests/test_cvrp_adapter.py scion/scion/tests/test_cvrp_solver_operator_runtime.py scion/scion/tests/test_cvrp_protocol_smoke.py scion/scion/tests/unit/test_research_surfaces.py
```

```text
179 passed in 30.00s
```

Previous main-search route-pool/execution validation:

```bash
PYTHONPATH=scion /home/clawd/miniconda3/envs/claw/bin/python -m pytest -q scion/scion/tests/test_cvrp_solver_operator_runtime.py
```

```text
53 passed in 12.49s
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

- Repair route-pool candidate generation/recombination so source pools produce
  accepted recombined route sets. Success requires nonzero
  `main_search_route_pool_recombined_routes` and nonzero
  `main_search_component_phase_delta_sum.route_pool_recombination` locally
  before another short formal diagnostic.
- Keep the top-level target on `solver_design`; do not add another forced
  singleton mechanism-policy diagnostic to work around route-pool quality.
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

- CVRP `solver_design` is now validly routed, self-checked, and contract-valid
  with declared problem adaptation. Code-level main-search execution semantics
  are repaired, and route-pool recombination has runtime/feedback coverage, but
  live screening shows zero accepted route-pool recombinations and zero
  route-pool phase-best movement.
- CVRP's current research-surface set still contains many component hooks. It
  risks optimizing whatever hook is exposed unless APS keeps prioritizing the
  problem-object solver-design boundary.
- APS can still produce shallow solver-design hypotheses that satisfy the
  contract but only reshuffle lifecycle knobs around weak package-owned
  primitives.
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
  [`v0.4-active-boundary-contract-preview-budget-sonnet-4r-20260512.md`](../experiments/v0.4/v0.4-active-boundary-contract-preview-budget-sonnet-4r-20260512.md)
- Problem-object adaptation pivot:
  [`problem-object-adaptation-pivot.md`](../engineering/problem-object-adaptation-pivot.md)
