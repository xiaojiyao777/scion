# Scion v0.4 Current State

*Last updated: 2026-05-14*

This file is the short operational snapshot for onboarding and day-to-day
handoff. Historical repair and experiment notes were moved to
[`v0.4-history.md`](v0.4-history.md). Detailed experiment analyses live under
[`../experiments/v0.4/`](../experiments/v0.4/).

## Status

v0.4 is not ready for long CVRP solver-quality validation. The framework
governance path is largely behaving, but the previous CVRP optimization path
was still too componentized: Scion could select `solver_design`, yet generated
candidates mostly filled a `main_search_plan` lifecycle table and optimized
exposed knobs rather than studying the algorithm itself.

The current repair changes the active CVRP research object. `solver_design`
now targets `policies/solver_algorithm.py`, a direct full-algorithm hook with
`solve(instance, rng, time_limit_sec, context)`. Candidates can implement
construction, local search, destroy/repair, recombination, acceptance,
restart/perturbation, and runtime scheduling in Python, while the adapter and
solver keep ownership of objective semantics, feasibility, parsing, seeds,
protocol splits, time limits, and Decision rules. Runtime evidence for this
boundary is now `solver_algorithm_*`, including phase runtime and recomputed
objective fields.

The older `policies/main_search_strategy.py` path remains declared as the
legacy `main_search_strategy` config surface for compatibility and regression
tests. It is no longer the preferred solver-design research object.

Current branch: `v0.4-dev`

Current interpretation:

- Scion core remains problem-agnostic: proposal observations are tainted,
  Decision does not read proposal text, and problem semantics stay behind
  adapters/problem packages.
- Forced single-surface diagnostics have done their job for governance and
  runtime-audit validation. They should not continue as the main optimization
  path.
- CVRP now declares `solver_design` as the top-level research boundary backed
  by `policies/solver_algorithm.py`. Deep mechanism policies and the legacy
  `main_search_strategy` table remain useful implementation hooks or
  regression surfaces, but they are not standalone optimization goals.
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
- For semantic-signature solver-design hypotheses, declared algorithm identity
  fields such as `algorithm_family`, `construction_strategy`,
  `improvement_strategy`, `acceptance_strategy`, and
  `runtime_budget_strategy` are required. Free-text rationale is not novelty
  identity.
- APS self-check failures now fail closed for real sessions. Schema/target
  preview failures, skipped Contract previews, or failed Contract previews stop
  the completed output before the patch enters evaluation.
- The higher-ceiling v3 path is now a problem-object algorithm path:
  instance model, solution model, objective policy, safe helper API, and
  whole-solver evidence are rendered by the adapter as one coherent object for
  Scion to reason over.
- The earlier route-pool and `algorithm_body` repairs are retained as legacy
  mechanism evidence, but they are no longer the main research object. The
  current blocker is whether APS can use the direct `solve(...)` boundary to
  produce repeated solver-quality movement without modifying objective or
  constraint semantics.
- Scion's role is boundary/protocol/audit control, not replacing the research
  agent with prompt-only field exposure. The latest short run showed that
  hypothesis-stage tools were not enough: the code stage also needs bounded
  access to memory, branch state, screening/runtime feedback, and the full
  approved problem object while implementing the algorithm.
- The previous short lifecycle diagnostic showed why this had to be deeper
  than field exposure: candidates declared smaller baseline fractions but
  runtime silently used the legacy formal 0.75 floor, `phase_sequence` did not
  control component order, construction candidates were not passed into the
  route-pool, and cleanup/adaptive-budget controls were mostly descriptive.
  Those execution gaps are now repaired and unit-tested.
- The follow-up execution-semantics diagnostic remains important historical
  evidence: componentized route-pool recombination was too expensive relative
  to its sparse gain. Under the new boundary, runtime should be handled inside
  the candidate algorithm and audited through `solver_algorithm_elapsed_ms` and
  `solver_algorithm_phase_runtime_ms`.
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

The balance-restored 2-round smoke from the slimmed code path completed
cleanly. Both candidates passed Contract/Verification and screened 16/16 valid
pairs. Round 1 was a fast low-quality replacement solver (`0` wins, `16`
losses, median pair delta `-119.5`, median runtime ratio about `0.029`).
Round 2 consumed that feedback and switched to a baseline-plus-ILS solver (`1`
win, `15` ties, `0` losses, median pair delta `0.0`, median runtime ratio
about `1.00045`). This is not promotion-quality, but it is a real
feedback-loop and whole-solver positive signal.

The follow-up 5-round exploratory run showed that this is still not ready for
long unattended solver-quality validation. It reached three screened
`solver_design` candidates with weak positive signal, then hung after a
successful code-generation trace. The likely failure point was post-code
Contract/CVRP synthetic preview executing a candidate with unbounded
improvement-flag loops. This is now repaired as a boundary-control issue:
static C9c rejects unbounded boolean-flag `while` loops, CVRP synthetic
preview times out `solve(...)`, and APS converts a hung
`proposal.contract_preview` into a controlled `tool_error`.

Next validation should be a 1-2 round independent smoke, not a long run. The
first gate is whether the slimmed code path reaches Contract preview and
Verification without another final `generate_patch` timeout. Preview-time
fail-closed behavior and solver-quality movement are later gates in the same
short run.

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
- Code phase is now agentic within the same boundary. After ContractGate
  approves a hypothesis, APS can run a bounded code-phase tool loop over
  exposure-controlled tools before final `PatchProposal` generation. The loop
  may read the selected surface at full code-preview budget, inspect branch
  state, query memory, and query screening/runtime feedback. It still cannot
  write candidate workspaces, read validation/frozen raw metrics, or make
  protocol/Decision calls.
- Failed Contract preview feedback is now fed into one bounded patch
  regeneration attempt before the session fails closed.
- Contract preview is also wall-time bounded before workspace materialization.
  A hung `proposal.contract_preview` now returns a controlled APS tool error
  instead of blocking the campaign.
- The first micro smoke after this repair confirmed code-phase tool selection
  and full `solver_design` surface read, but the final `generate_patch` call
  still timed out on a roughly 49k prompt. Prompt slimming now omits both the
  duplicate full champion policy bundle and duplicate surface-read
  `content_preview` code from final `solver_design` code prompts. The complete
  target file remains available once in the `Target File` section, while the
  audited full selected-surface read remains part of APS tool evidence.
- The balance-restored 2-round smoke showed the complete feedback loop working:
  `generate_patch` returned successfully, Contract-preview repair passed,
  Contract and Verification passed, screening feedback was stored, and the next
  hypothesis used that screening/runtime feedback to change algorithm strategy.
  Prompt slimming remains incomplete; the second-round code prompt still grew
  to roughly 55.6k characters.
- The latest preview-repair smoke still failed before preview because final
  code-generation prompts stayed too large and one planner prompt contained an
  empty tool name after holdout sanitization. Current repair compacts
  code-phase tool observations, filters holdout summary from model-facing
  planner specs, stops repeated code-phase surface reads, and normalizes
  timeout retry guidance.
- The compact-prompt smoke from commit `7f7ef04` reduced code prompt user text
  to roughly 35.5k-35.8k and reached screening in round 2, but round 1 still
  timed out at final `generate_patch`. Current prompt repair therefore filters
  final code observations to code-relevant feedback plus the latest full
  selected-surface read metadata, and caps solver-design static text fields
  before the target file is rendered.
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
- `main_search_strategy`
- `alns_vns_policy`
- `destroy_repair_policy`
- `route_pair_candidate_policy`
- `acceptance_restart_policy`

`solver_design` is the problem-owned full-algorithm surface. It is backed by
the singleton execution file `policies/solver_algorithm.py`:

- required function: `solve(instance, rng, time_limit_sec, context)`;
- allowed helpers: `context.make_solution`, `context.nearest_neighbor`,
  `context.baseline`, `context.objective`, `context.is_valid`,
  `context.remaining_time`, `context.elapsed_ms`, `context.record_phase`,
  `context.record_iteration`, `context.record_move`, and
  `context.set_stop_reason`;
- editable algorithm scope: construction, local search, destroy/repair,
  recombination, acceptance, restart/perturbation, and runtime scheduling;
- fixed boundary: objective, feasibility, parser, data, protocol splits,
  seeds, Decision, `solver.py`, `adapter.py`, `models.py`, and `cvrplib.py`;
- required evidence: `solver_algorithm_loaded`,
  `solver_algorithm_active`, `solver_algorithm_errors`,
  `solver_algorithm_elapsed_ms`, `solver_algorithm_phase_runtime_ms`,
  solution validity/routes/objective/distance/fleet violation,
  search-iteration/move-attempt/accepted-move counters, phase delta telemetry,
  and stop reason.

Current repair: `policies/solver_algorithm.py` is no longer only an empty
stub. It keeps the checked-in champion inactive by default, but now contains an
editable ALNS/VNS-style full-algorithm template with construction, capped
route-edit neighborhoods, destroy/repair, perturbation, acceptance, runtime
polling, and solver-algorithm telemetry. Adapter preview now rejects shallow
`context.baseline(...)` wrappers that do not run their own bounded search body.
It also fails closed on synthetic preview timeout, so generated
`solver_design` code cannot hang Scion before workspace materialization.
The timeout sentinel is outside normal `Exception` handling so generated
candidate code cannot swallow it with a broad `except Exception`.

`main_search_strategy` is a legacy config surface backed by
`policies/main_search_strategy.py`. It preserves the earlier `main_search_plan`
and `algorithm_body` tests, but it is not the default optimization direction.

Current limitation: the direct full-algorithm boundary is code-validated but
not yet experiment-validated. Run short diagnostics before any long CVRP
validation, and judge success by repeated solver-quality movement plus runtime
control under `solver_algorithm_*` evidence.

## Latest Experiment

Latest analyzed preview-repair smoke:

```text
run_root=/home/clawd/research/scion-experiments/v04-preview-timeout-repair-smoke-sonnet-2r-20260513T232347Z
model=claude-sonnet-4-6
problem=cvrp
protocol=formal
rounds_requested=2
rounds_completed=2 APS attempts, 0 screened experiments
time_limit_sec=60
agentic_session_timeout_sec=1800
git_commit=0361d1a
exit_code=0
status=max_rounds_exhausted
terminal_reason=code_generation_failed
analysis_doc=scion/docs/experiments/v0.4/v0.4-full-solver-subject-code-phase-agentic-repair-20260513.md
```

Summary:

- The run did not validate the preview-timeout repair because neither round
  reached Contract preview. Both final `generate_patch` calls timed out after
  three provider attempts.
- Code prompt sizes were still roughly 49k and 51k characters. The target file
  appeared once in the normal `Target File` section and again through the full
  code-phase `context.read_surface` observation payload.
- Code phase repeated selected-surface reads instead of stopping after the
  required full read was already available.
- Strict planner sanitization erased `feedback.query_holdout_summary` inside
  model-facing allowed-tool specs, leaving an empty tool name in the prompt.
- The current repair compacts code-phase observations, caps code-phase
  agentic context more tightly, stops after a successful full selected-surface
  read, filters holdout-summary from model-facing planner specs, and gives
  timeout retries a smaller bounded-code instruction.
- The follow-up compact-prompt smoke validated part of that repair: one round
  still timed out in final `generate_patch`, but the next round generated a
  patch, passed Contract and Verification, and screened 16/16 valid pairs.
  Code prompt user text fell to roughly 35.5k-35.8k characters and no trace
  contained empty tool names or raw `content_preview` code payloads. The
  screened candidate was active and had nonzero `solver_algorithm_best_delta`,
  but was weaker than champion (`win_rate=0.0`, `median_delta=-71.0`,
  `runtime_ratio_median=0.192`).
- The current follow-up repair is more aggressive: code-generation prompts
  keep only memory, screening/runtime feedback, branch state, errors, and the
  latest full selected-surface read metadata; they omit initial compact surface
  reads, list/problem reads, and schema/target preview observations. The
  solver-design problem object, solver mechanics, interface spec, hypothesis
  detail, and agentic observation/diagnosis blocks are separately capped.

Next validation should again be a 1-2 round independent smoke. The first gate
is reaching Contract preview/Verification without final code-generation
timeout; solver-quality promotion remains a later criterion.

Previous analyzed code-phase exploratory run after the 2-round smoke:

```text
run_root=/home/clawd/research/scion-experiments/v04-code-phase-slim-exploratory-sonnet-5r-20260513T190909Z
model=claude-sonnet-4-6
problem=cvrp
protocol=formal
rounds_requested=5
rounds_observed_before_termination=4
screened_experiments=3
time_limit_sec=60
agentic_session_timeout_sec=1800
git_commit=febca19
exit_code=143
status=manually_terminated_for_preview_hang
analysis_doc=scion/docs/experiments/v0.4/v0.4-full-solver-subject-code-phase-agentic-repair-20260513.md
```

Summary:

- The run confirmed the repaired whole-solver path could repeatedly reach
  screening under `solver_design`, but solver quality remained weak: screened
  candidates had median deltas `-152`, `0`, and `0`.
- The second and third screened candidates showed small positive tails
  (`2` wins each) while mostly tying the champion, so there is some signal but
  still no promotion-quality movement.
- The campaign then stopped producing artifacts after a successful code trace.
  The process remained CPU-active for more than two hours, indicating a
  post-code preview hang rather than an LLM-provider timeout.
- Root cause: C9c allowed unbounded boolean-flag loops because reassignment of
  the loop condition variable was mistakenly counted as collection shrinkage;
  preview execution also had no hard wall-time guard.
- Repair: C9c now rejects unbounded improvement-flag loops, CVRP synthetic
  preview hard-times out `solve(...)`, and APS hard-times out
  `proposal.contract_preview` before workspace materialization.
- Next run: a 1-2 round independent smoke should validate fail-closed preview
  behavior before any 5-8 round validation.

Previous analyzed direct full-solver run after validation-feedback repair:

```text
run_root=/home/clawd/research/scion-experiments/v04-full-solver-subject-validation-feedback-repair-sonnet-8r-20260513T160209Z
model=claude-sonnet-4-6
problem=cvrp
protocol=formal
rounds_requested=8
rounds_observed_before_repair=5
screened_experiments=3
time_limit_sec=60
agentic_session_timeout_sec=1800
force_surface=none
status=manually_terminated_for_code_phase_agentic_repair
analysis_doc=scion/docs/experiments/v0.4/v0.4-full-solver-subject-code-phase-agentic-repair-20260513.md
```

Summary:

- The run stayed on the direct `solver_design` subject and generated
  `policies/solver_algorithm.py` patches for the screened candidates.
- Three candidates passed Contract and Verification and reached screening with
  16/16 valid pairs, but all failed `SCREENING_FAIL_WIN_RATE`.
- Round 1 was fast but worse than champion (`win_rate=0.0`,
  `median_delta=-98.5`). Rounds 2 and 3 mostly tied the repo-local ALNS+VNS
  champion (`win_rate=0.0`, `median_delta=0.0`).
- The next distinct population/recombination hypothesis failed at code
  generation after static prompts reached roughly 58k characters.
- Interpretation: boundary control is working, but code generation was still a
  one-shot static `generate_patch` call. The repair now adds a bounded
  code-phase tool loop and preview-feedback regeneration. The solver-quality
  problem remains separate: future candidates must use runtime as an
  optimization objective and produce a genuinely different algorithmic search,
  not just baseline warm-start plus small polish.
- Follow-up micro smoke from commit `f77b263` confirmed `code_phase=true`
  tool-selection traces and full selected-surface reads before patch
  generation, but final patch generation timed out and the retry ended on API
  balance exhaustion before Contract or screening. Do not start the planned
  5-8 round validation until a 1-2 round smoke reaches at least
  Contract/Verification with restored API balance.

Detailed analysis:
[`v0.4-full-solver-subject-code-phase-agentic-repair-20260513.md`](../experiments/v0.4/v0.4-full-solver-subject-code-phase-agentic-repair-20260513.md)

Latest completed experiment before the direct solver-algorithm boundary repair:

```text
run_root=/home/clawd/research/scion-experiments/v04-algorithm-body-execution-semantics-sonnet-8r-20260512T173014Z
model=claude-sonnet-4-6
problem=cvrp
protocol=formal
rounds_requested=8
rounds_completed=8
screened_experiments=1
time_limit_sec=60
agentic_proposal=true
agentic_session_timeout_sec=1200
force_surface=none
exit_code=0
stopped_reason=circuit_breaker
finished_utc=2026-05-12T18:14:35Z
analysis_doc=scion/docs/experiments/v0.4/v0.4-algorithm-body-execution-semantics-repair-20260512.md
```

Summary:

- The run stayed on `solver_design` for all eight rounds
  (`action_locus_coverage.modify/solver_design=8`).
- Round 1 passed Contract and Verification and reached screening. It had
  16 attempted pairs, 15 valid pairs, one candidate timeout,
  `runtime_ratio_median=1.2115`, `runtime_delta_median_ms=10231`,
  and `runtime_regression_rate=1.0`; Decision abandoned it with
  `CANDIDATE_RUNTIME_FAILURE`.
- Runtime evidence confirmed the previous execution-semantics repair:
  `baseline_budget_policy="declared"` produced an effective baseline fraction
  of 0.7 with no hidden 0.75 guard; phase/component order followed the
  declared body; construction pool size was 2; route-pool source solutions
  were 14-20; and route-pool telemetry was present.
- Solver efficacy was still sparse. Only one observed pair recorded
  route-pool phase-best improvement
  (`main_search_component_phase_delta_sum.route_pool_recombination=3.0`,
  `main_search_route_pool_recombined_routes=8`), while
  `route_pool_recombination` consumed roughly 16s per observed pair.
- Rounds 2-8 failed before patch application because Contract preview failed
  with only generic failure text in campaign logs. The circuit breaker then
  ended the run after repeated proposal failures.

Interpretation: this run showed that the componentized `algorithm_body` path
was not enough. Runtime is already part of framework governance, but asking
Scion to optimize lifecycle-table knobs still kept the research object too
indirect.

Current repair: `solver_design` now targets the direct
`policies/solver_algorithm.py` full-algorithm hook and records
`solver_algorithm_*` evidence. The next short experiment should validate that
APS edits this algorithm subject directly and does not fall back to
component-policy or lifecycle-table optimization.

Detailed analysis:
[`v0.4-direct-solver-subject-adapter-repair-20260513.md`](../experiments/v0.4/v0.4-direct-solver-subject-adapter-repair-20260513.md)

Previous repair:
[`v0.4-algorithm-body-execution-semantics-repair-20260512.md`](../experiments/v0.4/v0.4-algorithm-body-execution-semantics-repair-20260512.md)

Previous analyzed/stopped run:

```text
run_root=/home/clawd/research/scion-experiments/v04-algorithm-body-lifecycle-sonnet-8r-20260512T145345Z
model=claude-sonnet-4-6
problem=cvrp
protocol=formal
rounds_requested=8
rounds_completed_before_termination=7_plus_partial_round_8
screened_experiments=4_complete_plus_partial_round_8
time_limit_sec=60
agentic_proposal=true
agentic_session_timeout_sec=1200
force_surface=none
stop_reason=manual_termination_for_execution_semantics_repair
analysis_doc=scion/docs/experiments/v0.4/v0.4-algorithm-body-execution-semantics-repair-20260512.md
```

Summary:

- The run validated that APS/codegen could declare `algorithm_body`, but the
  live semantics were still too shallow. Completed screenings had low sparse
  movement (`win_rate` values of 0.125, 0.0, 0.125, and 0.125 with
  `median_delta=0.0`), and the partial round-8 screening was again all ties
  with runtime regression.
- The decisive finding was an execution-layer mismatch: generated candidates
  could declare `baseline.time_fraction` around 0.55-0.60, but formal runtime
  silently applied the legacy 0.75 baseline floor. `phase_sequence`,
  `local_cleanup_after_recombination`, and `adaptive_component_budget` also
  did not sufficiently control the actual main-search schedule, and the
  bounded construction pool was not fed into route-pool recombination.
- The run was stopped before completion so the validation path could test a
  real algorithm-body execution contract rather than another audit-only
  exposure slice.

Interpretation: Scion had enough object-level context to stay on
`solver_design`, but it still did not have meaningful control over the full
CVRP solver body. The repair now makes declared baseline budget policy,
phase/component order, construction-pool route-pool input, cleanup coupling,
and adaptive component top-k visible in runtime behavior and required audit
evidence.

Detailed analysis:
[`v0.4-algorithm-body-execution-semantics-repair-20260512.md`](../experiments/v0.4/v0.4-algorithm-body-execution-semantics-repair-20260512.md)

## Current Repair Validation

The May 13 direct solver-algorithm boundary repair has passed focused and
boundary regression tests:

```text
/home/clawd/miniconda3/envs/claw/bin/python -m pytest \
  scion/scion/tests/unit/test_research_surfaces.py \
  scion/scion/tests/unit/test_agentic_proposal_tools.py \
  scion/scion/tests/test_cvrp_adapter.py \
  scion/scion/tests/test_cvrp_solver_operator_runtime.py \
  scion/scion/tests/test_cvrp_protocol_smoke.py \
  scion/scion/tests/test_protocol.py \
  scion/scion/tests/test_problem_bridge.py \
  scion/scion/tests/unit/core/test_proposal_pipeline.py \
  scion/scion/tests/unit/test_sprint_m.py \
  scion/scion/tests/test_contract.py -q

466 passed

/home/clawd/miniconda3/envs/claw/bin/python -m pytest scion/scion/tests -q

1610 passed, 1 skipped
```

The first direct-solver-algorithm validation launch did not reach screening.
It selected free `solver_design` and generated direct
`policies/solver_algorithm.py` patches, which is the important positive
boundary signal, but then blocked before experiments after three proposal/code
failures:

- two candidates failed Contract on `time` imports plus bounded algorithm
  `while` patterns that the old complexity heuristic treated as uncapped;
- one candidate failed synthetic preview because preview/runtime
  `context.baseline` signatures disagreed on seed solution and
  `time_limit_sec` alias handling;
- the campaign marked both active branches `blocked_infra`, with
  `n_experiments=0`.

Follow-up repair: the direct solver context now accepts
`context.baseline(initial_solution=None, time_budget_sec=None,
time_limit_sec=None, params=None)`, `context.objective` remains a mapping but
supports lexicographic `(fleet_violation, total_distance)` comparison and
indexing, `context.objective_key`/`context.is_better` are exposed, `time` is
whitelisted for monotonic timing, `instance.depot` is documented, and C9c now
recognizes finite algorithm-body while loops with shrinking collections,
incrementing counters, or bounded-break/time guards. Replaying all five
rejected code traces from the blocked run now passes C8, C9c, and CVRP
synthetic preview locally.

Blocked diagnostic:

```text
run_root=/home/clawd/research/scion-experiments/v04-direct-solver-algorithm-boundary-sonnet-8r-20260513T084740Z
model=claude-sonnet-4-6
problem=cvrp
protocol=formal
rounds_requested=8
rounds_completed_before_block=0
screened_experiments=0
time_limit_sec=60
agentic_session_timeout_sec=1200
force_surface=none
launcher=nohup+setsid
pid=2618289
started_utc=2026-05-13T08:47:40Z
status=blocked_infra_after_proposal_failures
```

Follow-up validation is running from commit `8d8f01f`:

```text
run_root=/home/clawd/research/scion-experiments/v04-direct-solver-algorithm-api-repair-sonnet-8r-20260513T092116Z
model=claude-sonnet-4-6
problem=cvrp
protocol=formal
rounds_requested=8
time_limit_sec=60
agentic_session_timeout_sec=1200
force_surface=none
launcher=nohup+setsid
pid=2621512
started_utc=2026-05-13T09:21:16Z
git_commit=8d8f01f4efaabe6d7c2ac7d425caf354e47a9ae2
```

Initial status check: the run reached `stage=screening` on round 1 with
`target_file=policies/solver_algorithm.py`, so the previous C8/C9c/preview
blocker is cleared at least for the first generated direct-algorithm
candidate.

Completed status check:

- `total_rounds=8`, `n_experiments=3`, `stopped_reason=max_rounds_exhausted`;
- all 8 hypotheses stayed on `modify/solver_design` and targeted
  `policies/solver_algorithm.py`;
- 3 candidates reached screening with 16/16 valid pairs and non-empty
  `solver_algorithm_*` evidence;
- all 3 screened candidates failed `SCREENING_FAIL_WIN_RATE` with median
  total-distance delta 0.0;
- one screened candidate had runtime regression
  (`runtime_ratio_median=1.236`, `runtime_regression_rate=0.75`), while two
  were faster (`runtime_ratio_median=0.902` and `0.939`) but still lacked win
  rate;
- 2 verification failures were `V5_solution_consistency`;
- 3 code-generation attempts still failed C9c on runtime-guarded full
  algorithm `while` loops.

Important framework issue found during this check: runtime evidence reported
`solver_algorithm_active=true`, `solver_algorithm_solution_valid=true`, and
`solver_algorithm_errors=0`, but still left
`solver_algorithm_stop_reason="inactive"`. This was a default-audit overwrite
bug, not inactive solve behavior, and it visibly polluted later hypotheses
that tried to solve a nonexistent "still inactive" problem. Follow-up code now
sets active successful direct algorithms to
`solver_algorithm_stop_reason="completed"`, accepts `context.remaining_time()`
guarded C9c loops, and makes synthetic preview decrement remaining time so
preview cannot hang on the same runtime guards. Replaying the previously
C9c-rejected runtime-guarded code traces now passes C9c and CVRP preview
locally.

Validation after this follow-up repair:

```text
/home/clawd/miniconda3/envs/claw/bin/python -m pytest \
  scion/scion/tests/unit/test_research_surfaces.py \
  scion/scion/tests/unit/test_agentic_proposal_tools.py \
  scion/scion/tests/test_cvrp_adapter.py \
  scion/scion/tests/test_cvrp_solver_operator_runtime.py \
  scion/scion/tests/test_cvrp_protocol_smoke.py \
  scion/scion/tests/test_protocol.py \
  scion/scion/tests/test_problem_bridge.py \
  scion/scion/tests/unit/core/test_proposal_pipeline.py \
  scion/scion/tests/unit/test_sprint_m.py \
  scion/scion/tests/test_contract.py -q

468 passed

/home/clawd/miniconda3/envs/claw/bin/python -m pytest scion/scion/tests -q

1612 passed, 1 skipped
```

Current preview-timeout repair validation:

```text
/home/clawd/miniconda3/envs/claw/bin/python -m py_compile \
  scion/scion/contract/gate.py \
  scion/scion/problems/cvrp/adapter.py \
  scion/scion/proposal/agentic_session.py \
  scion/scion/tests/unit/test_agentic_proposal_tools.py

/home/clawd/miniconda3/envs/claw/bin/python -m pytest \
  scion/scion/tests/test_contract.py \
  scion/scion/tests/test_cvrp_adapter.py \
  scion/scion/tests/unit/test_research_surfaces.py \
  scion/scion/tests/unit/test_agentic_proposal_tools.py \
  scion/scion/tests/unit/core/test_proposal_pipeline.py -q

329 passed

/home/clawd/miniconda3/envs/claw/bin/python -m pytest scion/scion/tests -q

1618 passed, 1 skipped
```

Current prompt/tool-loop repair validation:

```text
/home/clawd/miniconda3/envs/claw/bin/python -m pytest \
  scion/scion/tests/unit/test_agentic_proposal_tools.py -q

102 passed

/home/clawd/miniconda3/envs/claw/bin/python -m pytest \
  scion/scion/tests/unit/test_research_surfaces.py \
  scion/scion/tests/test_cvrp_adapter.py \
  scion/scion/tests/test_contract.py -q

198 passed

/home/clawd/miniconda3/envs/claw/bin/python -m pytest \
  scion/scion/tests/unit/test_g4_plumbing.py \
  scion/scion/tests/unit/test_sprint_j3_prompt_plumbing.py -q

29 passed

/home/clawd/miniconda3/envs/claw/bin/python -m pytest scion/scion/tests -q

1619 passed, 1 skipped
```

Current aggressive compact-prompt repair validation:

```text
/home/clawd/miniconda3/envs/claw/bin/python -m pytest \
  scion/scion/tests/unit/test_agentic_proposal_tools.py -q

102 passed

/home/clawd/miniconda3/envs/claw/bin/python -m pytest \
  scion/scion/tests/unit/test_research_surfaces.py \
  scion/scion/tests/test_cvrp_adapter.py \
  scion/scion/tests/test_contract.py -q

198 passed

/home/clawd/miniconda3/envs/claw/bin/python -m pytest \
  scion/scion/tests/unit/test_g4_plumbing.py \
  scion/scion/tests/unit/test_sprint_j3_prompt_plumbing.py -q

29 passed

/home/clawd/miniconda3/envs/claw/bin/python -m pytest scion/scion/tests -q

1619 passed, 1 skipped
```

Previous analyzed run:

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

Summary: validated route-pool execution/telemetry on 16/16 pairs, but
`main_search_route_pool_recombined_routes=0` and
`main_search_component_phase_delta_sum.route_pool_recombination=0.0` on all
pairs.

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

Latest algorithm-body execution-semantics focused validation:

```bash
cd scion && /home/clawd/miniconda3/envs/claw/bin/python -m pytest scion/tests/test_cvrp_adapter.py scion/tests/test_cvrp_solver_operator_runtime.py -q
```

```text
109 passed in 15.27s
```

Latest boundary/protocol regression subset:

```bash
cd scion && /home/clawd/miniconda3/envs/claw/bin/python -m pytest scion/tests/unit/test_research_surfaces.py scion/tests/unit/test_agentic_proposal_tools.py scion/tests/test_protocol.py -q
```

```text
217 passed in 3.91s
```

Latest full Scion test suite:

```bash
cd scion && /home/clawd/miniconda3/envs/claw/bin/python -m pytest scion/tests -q
```

```text
1601 passed, 1 skipped in 69.52s
```

Previous related proposal/CVRP subset:

```bash
PYTHONPATH=scion /home/clawd/miniconda3/envs/claw/bin/python -m pytest -q scion/scion/tests/test_cvrp_adapter.py scion/scion/tests/unit/test_research_surfaces.py scion/scion/tests/test_proposal_validation.py
```

```text
133 passed in 4.66s
```

Previous full Scion test suite:

```bash
PYTHONPATH=scion /home/clawd/miniconda3/envs/claw/bin/python -m pytest -q scion/scion/tests
```

```text
1593 passed, 1 skipped in 67.54s
```

Latest route-pool quality/boundary validation:

```bash
PYTHONPATH=scion /home/clawd/miniconda3/envs/claw/bin/python -m pytest -q scion/scion/tests/test_cvrp_solver_operator_runtime.py -k 'route_pool'
```

```text
7 passed, 51 deselected in 0.51s
```

Latest main-search route-pool telemetry contract validation:

```bash
PYTHONPATH=scion /home/clawd/miniconda3/envs/claw/bin/python -m pytest -q scion/scion/tests/test_cvrp_adapter.py scion/scion/tests/test_cvrp_solver_operator_runtime.py scion/scion/tests/test_cvrp_protocol_smoke.py scion/scion/tests/unit/test_research_surfaces.py
```

```text
182 passed in 29.81s
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

Latest direct solver-design smoke and repair:

- Independent smoke:
  `/home/clawd/research/scion-experiments/v04-code-phase-aggressive-compact-smoke-sonnet-2r-20260514T061603Z`
  completed 2/2 rounds on commit `14f7f29`.
- Code-generation prompt compaction worked: both code calls completed with
  roughly 30k-33k user-prompt characters and no raw `content_preview` payloads.
- Round 1 passed Contract/Verification and reached screening, but had
  `win_rate=0.0`, `median_delta=0.0`, and `runtime_ratio_median=0.343`.
- Round 2 failed heavy Verification at `V5_solution_consistency`; replaying the
  generated solver in the correct workspace exposed the underlying candidate
  error `solve failed: list index out of range`.
- Runtime audit now reports `solver_algorithm_errors` as a dedicated
  `solver_algorithm_runtime_error` instead of burying full-solver hook failures
  behind generic surface evidence failures.
- CVRP solver-design preview now runs the hook on a controlled-canary-shaped
  synthetic instance and uses a 5s synthetic time window under the existing 2s
  wall-clock timeout. The exact failed round-2 solver is now rejected during
  Contract preview with `synthetic_preview_canary_5: solve raised during
  synthetic preview: list index out of range`.

Latest validation:

```bash
/home/clawd/miniconda3/envs/claw/bin/python -m pytest scion/scion/tests/test_cvrp_adapter.py scion/scion/tests/test_cvrp_solver_operator_runtime.py scion/scion/tests/test_verification.py -q
```

```text
209 passed in 21.75s
```

```bash
/home/clawd/miniconda3/envs/claw/bin/python -m pytest scion/scion/tests/unit/test_agentic_proposal_tools.py -q
```

```text
102 passed in 2.99s
```

```bash
/home/clawd/miniconda3/envs/claw/bin/python -m pytest scion/scion/tests -q
```

```text
1621 passed, 1 skipped in 73.91s
```

Latest code self-check repair:

- Independent smoke:
  `/home/clawd/research/scion-experiments/v04-solver-preview-repair-smoke-sonnet-2r-20260514T073717Z`
  completed 2/2 rounds on commit `c011ac2` with `n_experiments=0`.
- Round 1 failed after three code-generation provider timeouts.
- Round 2 failed closed in Contract preview: first on
  `C9c_complexity_bound` for an uncapped `while` loop, then on
  `C6_ast_syntax` at line 341 after repair.
- The repair response's own `test_hint` said the generated
  `_destroy_repair_regret` code still had a syntax error needing a fix, yet APS
  still passed it to Contract preview.
- APS now treats such self-reported unresolved code issues as code self-check
  failures before Contract preview. It may spend the one configured code-repair
  attempt with explicit `agentic_code_self_check_feedback`; if the repaired
  patch still self-reports unresolved syntax/compile/incomplete/TODO issues,
  the session fails closed as `code_generation_failed`.
- Code self-check repair and Contract-preview repair now share
  `max_code_repair_attempts`.

Latest focused validation:

```bash
/home/clawd/miniconda3/envs/claw/bin/python -m pytest scion/scion/tests/unit/test_agentic_proposal_tools.py -q
```

```text
104 passed in 2.88s
```

```bash
/home/clawd/miniconda3/envs/claw/bin/python -m pytest scion/scion/tests -q
```

```text
1623 passed, 1 skipped in 74.48s
```

## Next Actions

P1:

- Run and analyze the repaired algorithm-body execution diagnostic. The first
  gate is not promotion; it is whether APS-generated `solver_design`
  candidates use the full CVRP lifecycle semantics now that baseline budget,
  phase order, construction-pool reuse, cleanup coupling, and adaptive
  component budgets have real runtime effect.
- Run a short independent smoke after the solver-design preview/audit repair.
  The first gate is that bad full-solver candidates fail in Contract preview
  with concrete synthetic runtime diagnostics instead of reaching heavy
  Verification with opaque V5/no-output symptoms.
- Re-run the short smoke after the code self-check repair. The first gate is
  that generated patches whose own `test_hint` admits unresolved syntax or
  implementation issues fail before Contract preview or are repaired once with
  explicit self-check feedback.
- Keep route-pool telemetry as evidence inside that lifecycle:
  `main_search_route_pool_sample_count`,
  `main_search_route_pool_recombined_routes`, and
  `main_search_component_phase_delta_sum.route_pool_recombination` should
  remain first-class feedback fields.
- If the short diagnostic still produces only shallow knob reshuffles, the
  next repair should expose a more direct package-owned algorithm-body subject
  for Scion to study, not another singleton mechanism policy.
- Do not add another forced singleton mechanism-policy diagnostic to work
  around solver-design quality.
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
  as a direct full-algorithm hook. It has not yet shown experiment-level solver
  efficacy under the new boundary.
- CVRP's current research-surface set still contains many component hooks. It
  risks optimizing whatever hook is exposed unless APS keeps prioritizing the
  problem-object solver-design boundary.
- APS can still produce shallow solver-design hypotheses that wrap old helper
  behavior. The next validation must check whether Scion actually edits and
  reasons about the full algorithm subject while respecting the fixed
  objective/constraint boundary.
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
  [`v0.4-full-solver-subject-code-phase-agentic-repair-20260513.md`](../experiments/v0.4/v0.4-full-solver-subject-code-phase-agentic-repair-20260513.md)
- Problem-object adaptation pivot:
  [`problem-object-adaptation-pivot.md`](../engineering/problem-object-adaptation-pivot.md)
