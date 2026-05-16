# Scion v0.4 Current State

*Last updated: 2026-05-16*

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
now targets a branch-owned solver-design package: stable entrypoint
`policies/baseline_algorithm.py::solve(...)` plus focused algorithm modules
under `policies/baseline_modules/*.py`. When `solver_design` is the selected
surface, candidate and champion subprocesses run that copied branch entrypoint,
which imports the branch-owned modules. When another component surface is
selected, runtime skips this full-algorithm subject so legacy component tests
remain isolated. Candidates should study and modify the branch copy of the
algorithm modules; `policies/solver_algorithm.py` remains as a compatibility
hook only. APS `context.read_surface` now includes bounded support-module
previews for `solver_design`, so hypothesis and code phases can inspect the
actual algorithm internals rather than only the stable entrypoint. For module
targets, code-phase reads now keep the selected target narrow but also include
prioritized support artifacts for `state.py`, the stable entrypoint, and
sibling algorithm modules, with compact `python_api_summary` entries. This is
required because the branch-owned solver uses `_Solution.routes` as `_Route`
objects, not `list[list[int]]`; the code agent must see that object model
before editing scheduler or local-search logic. Algorithm-smoke retry feedback
now preserves concrete runtime/audit details such as failing case,
`solver_algorithm_errors`, and compact `solver_algorithm_events` instead of
only a generic failure code. Code-phase reads of a specific
`policies/baseline_modules/*.py` target are narrowed to a target-only preview
with a 6000-character code cap, preventing repeated module reads from
consuming the terminal Contract/smoke reserve. The adapter and solver keep
ownership of objective semantics,
feasibility, parsing, seeds, protocol splits, time limits, and Decision rules.
Runtime evidence for this boundary remains `solver_algorithm_*`, including
selected path, phase runtime, movement telemetry, and recomputed objective
fields.

The latest 2-round object-context smoke validated the new code-stage context:
LLM traces contained `support_artifacts` and `python_api_summary` for
`baseline_modules/state.py` when the target was `scheduler.py`. It also exposed
a Contract nuance: complete scheduler replacements inherited an existing
baseline exception message that referenced `instance.name`, and C9d treated it
as a new case-specific branch. Contract preview is now champion-snapshot aware
for C9d: exact inherited statement-level identity uses are not blockers, while
new `instance.name` branches remain forbidden. The follow-up smoke advanced
past that Contract blocker and failed in algorithm smoke; code-repair context
now carries the algorithm-smoke observation itself, with compact
`solver_algorithm_events`/stderr/run detail preferred over the generic
`solver_algorithm_errors=1` summary.

The follow-up 6-round module-object smoke showed the next control gap. APS
preview was champion-snapshot aware, but the main campaign `ContractGate` was
not, so completed scheduler candidates could still fail main `patch_contract`
on inherited `instance.name` text. That is now repaired with a dynamic champion
snapshot provider on the campaign gate. Solver-design code prompts now require
the primary JSON `file_path` to match the approved `target_file`, with
entrypoint/scheduler/module wiring in `additional_changes`; package-relative
imports inside `policies` are required. Contract also rejects inert
solver-design helper additions through `C9e_solver_design_integration`: new
module-level helper functions must be statically called from an existing
solver path in the same candidate patch.
The immediate 2-round validation after this repair produced two real screening
experiments, both normal algorithm-quality abandons rather than framework gate
failures: scheduler ensemble construction tied the champion with a small
runtime tie-speedup below the promotion threshold, while local-search
round-robin VNS worsened quality and slowed runtime.

The latest 6-round contract-integration validation showed that the framework
path is mostly healthy but C9e was too narrow for class-based solver modules.
Only three candidates entered screening because rounds 1 and 6 were falsely
rejected before screening: their new helpers were called from solver class
methods or a runtime `_ALNSVNSSolver = _PBIGSolver` alias, but C9e only
recognized module-level entrypoint/function reachability. Round 2 was a real
generated-code error with a repeated keyword argument that C6 should have
caught earlier. Repair: C6 now compiles parsed patch code, and C9e now treats
the runtime solver class `solve(...)` call chain as a valid integration root
while still rejecting helpers reachable only from detached classes. C9e was
also extracted from the monolithic `ContractGate` file into
`contract/checks/solver_design_integration.py`.

The follow-up Sonnet/Opus 6-round integration smokes confirmed a different
code-stage repairability gap. Screened candidates were correctly abandoned for
solver quality, including faster but objectively worse scheduler rewrites. The
pre-screen failures were mostly recoverable: `additional_changes` emitted as a
JSON string, inert helper-only local-search edits without scheduler/entrypoint
integration, and branch solver object-model mistakes such as `_Solution._instance`
or calling `.distance` on an integer. Current repair keeps the same
solver-design boundary but makes code-stage feedback deeper: schema parsing
tolerates JSON-string `additional_changes`, C9e reports inert helpers and
recognized roots, algorithm-smoke returns targeted repair guidance, and a
tainted non-promotional candidate-vs-champion canary micro-benchmark blocks
only candidates that lose every comparable smoke case before formal screening.
Repeated recent `solver_design` `win_rate=0` screening failures now produce
plateau guidance that demands a materially different algorithm-body hypothesis
instead of another shallow scheduler/budget/post-polish variant.

The first smoke after that repair showed the next code-repair control issue:
the model fixed an inert-helper C9e failure but introduced a fresh C9d
`instance.name` violation in the repair patch. C9d was correct; the APS loop
was too shallow. Code-stage preview repair now has two bounded attempts,
re-running Contract preview after each repair, and solver-design code prompts
explicitly forbid adding new `instance.name`/`getattr(instance, 'name')` uses
even in error messages.

The subsequent 2-round Sonnet smoke validated the framework repair. Round 1
passed Contract preview, algorithm smoke, Verification, and screening, then
was correctly abandoned for solver quality (`win_rate=0.0`, median delta
`0.0`, runtime ratio median `0.778`). Round 2 used round-1 feedback, hit an
algorithm-smoke runtime failure, then a C9c Contract failure, and the second
bounded repair produced a patch that passed Contract preview plus algorithm
smoke and reached formal screening. It was also correctly abandoned
(`win_rate=0.0`, median delta `0.0`, runtime ratio median `0.903`). This is
positive framework evidence: repair feedback is now sequential and auditable,
while promotion remains controlled by Contract, Verification, Protocol, and
Decision.

The May 15 runtime-governance repair makes algorithm compute time a real
positive optimization signal under strict boundaries. A candidate that ties the
lexicographic objective, has no runtime failures, and beats champion median
runtime by `runtime.tie_speedup_ratio` may pass screening, validation, and
frozen via `*_PASS_RUNTIME_TIE_IMPROVEMENT`; it still cannot bypass the
three-layer protocol. `ExperimentProtocol` computes these gates after runtime
stats are attached to `EvalStats`, so protocol gate outcomes and Decision
reason codes now agree on runtime tie-speedup evidence. CVRP `solver_design`
context now exposes
`context.remaining_time()` explicitly as seconds and
`context.remaining_time_ms()` for millisecond comparisons. Contract preview
rejects preferred `policies/baseline_algorithm.py` patches that compare
second-valued `remaining_time()` to millisecond-derived variables.

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
  by `policies/baseline_algorithm.py` and the
  `policies/baseline_modules/` package, with `policies/solver_algorithm.py`
  retained only for compatibility. Deep mechanism policies and the legacy
  `main_search_strategy` table remain useful implementation hooks or
  regression surfaces, but they are not standalone optimization goals.
- Solver subprocesses now receive the selected surface through
  `SCION_SELECTED_SURFACE`. This is the runtime switch that lets
  `solver_design` evaluate the branch-owned full algorithm while preventing
  that algorithm from swallowing unrelated component-surface experiments.
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

The 2026-05-14 code-self-check smoke from commit `06e9365` completed 2/2
rounds cleanly and validated the framework path: code-phase tool selection,
Contract-preview repair, `solver_algorithm` activation, runtime telemetry, and
fail-closed Decision all worked. Both candidates were abandoned by
`T4: win_rate < 0.3`. Round 1 had 3 wins, 1 loss, 12 ties, and median runtime
ratio about `1.234x`; round 2 had 1 win, 2 losses, 13 ties, and median runtime
ratio about `1.063x`. This is an algorithm-quality failure, not a boundary
failure.

The follow-up repair exposes adapter-rendered solver mechanics directly from
`context.read_problem`, so code phase sees the fixed objective/constraint
boundary and the direct `solve(...)` lifecycle without reconstructing it from
surface snippets. CVRP Contract preview now also runs `solver_design` on a
synthetic improvement-trap instance and fails baseline-seeded no-op wrappers
that do not improve the preview baseline. Screening feedback now prioritizes
`solver_algorithm_move_attempts`, `solver_algorithm_accepted_moves`,
`solver_algorithm_best_delta`, `solver_algorithm_search_iterations`, elapsed
time, and phase runtime fields, making "ran but did not move phase-best"
visible to the next agent turn.

The latest 2-round no-op-feedback smoke did not validate that micro-eval
repair because both rounds failed earlier in final `generate_patch` after
three provider timeout attempts. The important finding is framework control:
the code-phase tool loop reached the approved `solver_design` target and read
the full selected surface, but the approved hypotheses still invited broad
hybrid baseline/ILS/destroy-repair implementations that were too large for a
single static code response. Treat this as an APS code-generation scope
failure, not a reason to return to component-policy exposure.

Current repair: solver-design code generation now defaults to a compact
whole-algorithm implementation shape. The prompt asks for one construction or
seeding path plus one bounded improvement/search loop, discourages preserving
or expanding the branch-owned ALNS/VNS-style algorithm body unless the change
is material, and explicitly allows the replacement file to be much shorter
than the current implementation.
When final patch generation times out, APS performs one semantic retry inside
the same session with `code_generation_mode=compact_timeout_retry`, injects
`prior_code_failure=code_generation_timeout`, tightens problem/interface/
hypothesis caps, and records the retry in the transcript. This is separate
from Contract-preview or code-self-check repair attempts.

The 2026-05-14 2-round code-scope smoke from commit `2e6a888` passed the first
gate: final `generate_patch` returned in all three code traces, and round 1
reached Contract, Verification, and screening. It also exposed the next APS
control issue. Screening/runtime feedback consumed almost the entire 64k
session observation budget in round 2, leaving too little space for terminal
Contract-preview evidence; the session failed closed with
`contract preview did not pass (result_too_large, tool_error)`.

The follow-up 2-round feedback-budget smoke from commit `ff7ae66` validated
that APS repair: both code sessions completed, both retained terminal
Contract-preview evidence, and no session failed with `result_too_large`.
Round 2 also proved Contract-preview repair in-session by rejecting an initial
uncapped-loop patch and accepting the regenerated patch.

The deeper research-object repair now makes `policies/baseline_algorithm.py`
the preferred solver-design target and forbids `context.baseline(...)` calls
from that file in CVRP problem-owned preview. This changes the research loop
from "call baseline, then polish" to "modify the controlled algorithm body and
let the candidate become the next champion if it passes the gates." The
original `vrp/` implementation remains frozen; all candidate changes happen
inside Scion branch snapshots.

Code phase now has an explicit debug/effectiveness gate:
`proposal.algorithm_smoke`. After static Contract preview passes, APS runs a
tainted, non-promotional synthetic CVRP smoke by calling the candidate
`solve(...)`. For `solver_design` patches to `policies/baseline_algorithm.py`
or `policies/solver_algorithm.py`, APS now materializes a temporary tainted
workspace, applies the patch, and runs the configured canary case under the
selected `solver_design` runtime. A failed smoke can feed one bounded repair
attempt before the patch enters official evaluation. This smoke does not write
candidate/champion workspaces and does not count as promotion evidence; final
validation remains Contract, Verification, Protocol, and Decision.

The same smoke exposed the next direction-level blocker. `solver_design` is a
full-algorithm hook, but the agent is still being induced to treat the
repo-local baseline as an oracle/seed and then write small post-baseline local
search code. The first-round hypothesis was too shallow because it did not
study the ALNS+VNS baseline algorithm body before choosing the mechanism, and
the code phase effectively wrote a generic cleanup solver around
`context.baseline(...)`. This is not Scion's intended loop. Scion should let
the research agent study the algorithm under boundary/protocol/audit control,
modify a controlled candidate copy of that algorithm, and let successful
candidate branches become the next champion/baseline. The original `vrp/`
files remain frozen; candidate algorithm changes must happen inside
Scion-controlled branches.

Current repair target: improve the CVRP research-object adapter so hypothesis
and code phases can study and modify the algorithm body that actually matters,
instead of producing baseline-wrapper post-processing solvers. The budget and
Contract-preview control path is now healthy enough to support that deeper
repair.

Operational cost/control note: real-cost smoke and validation runs should use
`SCION_MODEL=claude-sonnet-4-6` unless there is an explicit reason to spend an
Opus round. Provider SDK retries are disabled by default in `LLMClient` so
Scion's own traced retry loop is the single audited retry layer; tune with
`SCION_LLM_MAX_RETRIES` and only opt into SDK retries with
`SCION_SDK_MAX_RETRIES` deliberately. Code/fix tool calls are now treated as
long non-streaming generation requests: by default they use
`timeout_sec=max(SCION_LLM_TIMEOUT_SEC, 180)` and `max_retries=0`, with
per-kind overrides through `SCION_LLM_CODE_TIMEOUT_SEC`,
`SCION_LLM_CODE_MAX_RETRIES`, `SCION_LLM_FIX_TIMEOUT_SEC`, and
`SCION_LLM_FIX_MAX_RETRIES`.

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
- The no-op-feedback smoke from commit `a653388` reached the same code-phase
  tool path, but both final `generate_patch` calls timed out before Contract
  preview. APS now handles this as a controlled code-scope issue:
  solver-design prompts default to compact single-mechanism solver bodies, and
  timeout failures trigger one in-session semantic retry with a smaller
  compact-timeout mode instead of repeating the same broad request.
- Observation-budget pressure is mitigated by compact surface reads, compact
  preview payloads, and a self-check/static-preview reserve. Optional planner
  surface reads fail closed before consuming the reserve.
- Screening/runtime feedback is now compacted again at the APS observation
  boundary. The model still sees reason codes, recent screening stats,
  runtime-attribution highlights, and research diagnosis, but bulky case
  feedback and raw-sized value lists no longer crowd out terminal Contract
  preview evidence.
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

`solver_design` is the problem-owned full-algorithm surface. It is backed
first by the singleton execution file `policies/baseline_algorithm.py`, with
`policies/solver_algorithm.py` retained as an older compatibility hook:

- required function: `solve(instance, rng, time_limit_sec, context)`;
- allowed helpers: `context.make_solution`, `context.nearest_neighbor`,
  `context.objective`, `context.is_valid`, `context.remaining_time`,
  `context.elapsed_ms`, `context.record_phase`, `context.record_iteration`,
  `context.record_move`, and `context.set_stop_reason`;
- `context.nearest_neighbor(...)` returns a `CvrpSolution`; use it directly as
  a candidate solution. `context.make_solution(...)` accepts route iterables
  and is idempotent for existing solution objects;
- compatibility helper: `context.baseline(...)` may exist for older
  `solver_algorithm.py` experiments, but preferred
  `baseline_algorithm.py` candidates must not call it;
- editable algorithm scope: construction, local search, destroy/repair,
  recombination, acceptance, restart/perturbation, and runtime scheduling;
- fixed boundary: objective, feasibility, parser, data, protocol splits,
  seeds, Decision, `solver.py`, `adapter.py`, `models.py`, and `cvrplib.py`;
- required evidence: `solver_algorithm_loaded`,
  `solver_algorithm_active`, `solver_algorithm_errors`,
  `solver_algorithm_elapsed_ms`, `solver_algorithm_phase_runtime_ms`,
  solution validity/routes/objective/distance/fleet violation,
  search-iteration/move-attempt/accepted-move counters, improving-vs-neutral
  accepted-move counters, phase delta telemetry, and stop reason.

Current repair: `policies/baseline_algorithm.py` is now the active
solver-design algorithm subject when `solver_design` is selected. It contains a
controlled ALNS/VNS-style algorithm body with construction, capped route-edit
neighborhoods, destroy/repair, perturbation, acceptance, runtime polling, and
solver-algorithm telemetry. Candidate branches should modify that branch copy
directly. Adapter preview rejects preferred-target `context.baseline(...)`
wrappers, so the candidate cannot reduce the research task to "call champion,
then polish." It also fails closed on synthetic preview timeout, so generated
`solver_design` code cannot hang Scion before workspace materialization. The
timeout sentinel is outside normal `Exception` handling so generated candidate
code cannot swallow it with a broad `except Exception`.

`main_search_strategy` is a legacy config surface backed by
`policies/main_search_strategy.py`. It preserves the earlier `main_search_plan`
and `algorithm_body` tests, but it is not the default optimization direction.

Current limitation: the direct full-algorithm boundary is now smoke-validated
for framework stability, but not solver quality. The first gate is satisfied:
candidates can target `baseline_algorithm.py`, pass Contract plus
`proposal.algorithm_smoke`, enter official Verification, and run 16/16 formal
screening pairs as controlled algorithm-body changes. Solver promotion quality
is still a later gate under the existing `solver_algorithm_*` evidence.

## Latest Experiment

Latest contract-integration gate validation and repair:

```text
run_root=/home/clawd/research/scion-experiments/v04-contract-integration-gate-sonnet-6r-20260515T230605Z
model=claude-sonnet-4-6
rounds_requested=6
screened_experiments=3
champion_version=1
stopped_reason=max_rounds_exhausted
```

Interpretation: the three screened candidates were valid solver-design
algorithm edits and were correctly abandoned by `SCREENING_FAIL_WIN_RATE`.
The agent behavior was directionally reasonable: it stayed on branch-owned
solver modules, used screening/runtime feedback, pivoted from scheduler to
local search, and eventually attempted a larger PBIG-style solver
restructure. The non-screened rounds revealed framework gate issues rather
than research-object drift. Detailed analysis:
[`v0.4-contract-integration-gate-sonnet-6r-20260515.md`](../experiments/v0.4/v0.4-contract-integration-gate-sonnet-6r-20260515.md)

Latest solver-design module-subject smoke and repair:

```text
run_root=/home/clawd/research/scion-experiments/v04-solver-design-module-subject-sonnet-2r-20260515T142828Z
model=claude-sonnet-4-6
rounds_requested=2
screened_experiments=0
stopped_reason=max_rounds_exhausted
last_result=code generation failed
```

This smoke validated the new research-object direction but exposed a budget
control issue. APS selected `solver_design` and targeted
`policies/baseline_modules/local_search.py`, proving the agent can now choose
focused branch-owned algorithm modules instead of regenerating the stable
entrypoint. It then failed before official evaluation because post-repair
Contract preview was replaced by `result_too_large` after the session spent
too much of its observation budget.

Current repair: code-phase reads for solver-design support modules use
`section=target_preview`, cap code preview at 6000 chars, and count that
module-target read as sufficient so the deterministic fallback does not read
the same module again. The full Scion suite passes after this repair
(`1670 passed, 1 skipped`).

Follow-up smoke after this repair:

```text
run_root=/home/clawd/research/scion-experiments/v04-solver-design-module-budget-repair-sonnet-2r-20260515T144636Z
rounds_requested=2
screened_experiments=0
stopped_reason=max_rounds_exhausted
last_result=code generation failed
```

The previous `result_too_large` failure did not recur. Contract preview
retained concrete C4b/C9c failures, so the budget repair is validated. The new
blocker is patch protocol expressiveness: the agent proposed
`create_new/policies/baseline_modules/intensification.py`, but the intended
algorithm change also required modifying scheduler/entrypoint code to call the
new module. Current `PatchProposal` was single-file, so generated code either
created an inert module or switched to `baseline_algorithm.py` and violated
the approved action/target.

Current repair: `PatchProposal` remains backward-compatible but now supports
optional `additional_changes`. Contract validates the primary change against
the approved hypothesis and validates every additional file independently
inside the same selected research-surface boundary. Workspace materialization
and `proposal.algorithm_smoke` apply all file changes together, so a
`solver_design` candidate can create a module and wire it into
`baseline_algorithm.py` or `baseline_modules/scheduler.py` without bypassing
editable/frozen path checks, interface checks, import whitelist, C9/C9b/C9c,
tainted smoke, Verification, Protocol, or Decision. Agentic output artifacts
omit all additional code bodies while preserving path/action/body-size audit
metadata.

Focused validation after this repair: `310 passed` across APS proposal tools,
research-surface Contract tests, workspace materialization, base Contract
tests, and proposal validation. Full suite validation:
`1672 passed, 1 skipped`. The next step is a 2-round Sonnet smoke; if it passes
the framework gate, start a 6-round independent validation run.

First 2-round smoke after the multi-file repair reached Contract repair and
then failed in `proposal.algorithm_smoke` with a framework compatibility bug:
live campaign context carried a legacy `ProblemSpec` with
`spec_version=problem-v1`, and smoke attempted to bridge it as if it were a
`ProblemSpecV1` with `id`. Runtime-audit spec handling now bridges only real
v1 specs with an `id` and uses already-legacy specs directly. Focused
regression after this fix: `311 passed`. Full suite after the compatibility
fix: `1673 passed, 1 skipped`.

Second 2-round smoke:
`/home/clawd/research/scion-experiments/v04-multifile-smoke-repair-sonnet-2r-20260515T152117Z`
completed with exit code 0. It confirmed multi-file/code-phase framework
control is stable, but showed `proposal.algorithm_smoke` was too narrow:
round 1 passed Contract, Verification, and canary, then failed official
screening on `tiny_6` with `solver_algorithm_runtime_error` (`'_Route' object
is not subscriptable`). Round 2 was blocked by schema/target preview for
overlong semantic-signature fields. Repair: solver-design algorithm smoke now
runs canary plus up to two public screening cases using the first public
screening seed. It remains tainted/non-promotional and reads no
validation/frozen cases. Validation after this repair: targeted smoke
regression `5 passed`, focused subset `312 passed`, full suite
`1674 passed, 1 skipped`.

The follow-up 2-round smoke completed with exit code 0 and showed the previous
`tiny_6` runtime leak was fixed: screening had 4/4 valid pairs and zero
candidate runtime failures, then abandoned normally for
`SCREENING_FAIL_WIN_RATE`. It also exposed a budget-control issue in round 2:
after screening/runtime feedback and code context, required
`proposal.contract_preview` had too little remaining observation budget and
collapsed to `result_too_large`. Repair: default agentic observation budget is
now 96k, required self-check tools have a minimal preview fallback that
preserves pass/fail and compact failed-check/runtime summaries, and repeated
compaction retains failed-check names. Validation after this repair: targeted
budget regressions `3 passed`, focused subset `313 passed`, full suite
`1675 passed, 1 skipped`.

2-round smoke after the self-check budget repair:
`/home/clawd/research/scion-experiments/v04-selfcheck-budget-sonnet-2r-20260515T161843Z`
completed with exit code 0. No `result_too_large` recurred. Contract preview
retained concrete `C4b_patch_action_target` and
`C9d_surface_instance_identity` feedback, and another candidate passed Contract
but was stopped by expanded `proposal.algorithm_smoke` for
`solver_algorithm_errors=1` before official screening. This is acceptable for
the repair: bad candidate code is rejected inside tainted self-checks, with
auditable failure evidence.

Latest code-generation timeout-policy diagnosis and repair:

```text
analyzed_run_root=/home/clawd/research/scion-experiments/v04-sdk-retry-control-sonnet-8r-20260514T181734Z
model=claude-sonnet-4-6
problem=cvrp
protocol=formal
rounds_requested=8
time_limit_sec=60
agentic_session_timeout_sec=1800
status=max_rounds_exhausted
```

Trace analysis corrected the prior interpretation. The 8-round run had
57/57 successful tool-selection calls and 5/5 successful hypothesis calls, but
only 2/15 code-generation calls succeeded. The 13 failed code traces all
clustered around `125.1s`, matching `60s client timeout + 5s backoff + 60s
client timeout` under `SCION_LLM_MAX_RETRIES=1`. Successful code calls were
not materially smaller; one succeeded in about `50s` and one in about `114s`.
The primary issue was therefore a non-streaming client timeout policy mismatch,
not prompt size alone.

Repair: `LLMClient` now resolves request policy by request kind. `code` and
`fix` tool calls default to a longer `180s` timeout and zero same-prompt
LLMClient retries, while APS keeps its single semantic compact timeout retry.
`CreativeLayer` writes the effective request policy into each LLM trace for
auditability. Streaming remains a useful follow-up but is not required for the
first repair validation.

Validation smoke:

```text
run_root=/home/clawd/research/scion-experiments/v04-codegen-timeout-policy-sonnet-2r-20260515T011055Z
rounds=2
stopped_reason=max_rounds_exhausted
code_trace_durations=121.68s, 125.41s, 143.88s, 144.25s
code_trace_policy=timeout_sec=180.0, max_retries=0
```

All four code-generation traces returned successfully and would have been
prematurely killed by the old 60s non-streaming timeout. Round 1 reached
screening and was normally abandoned by `SCREENING_FAIL_WIN_RATE`; round 2
generated code successfully but failed closed at Contract preview on
`C9c_complexity_bound`, which is a generated-algorithm boundary/quality issue
rather than an LLM timeout issue.

Follow-up 5-round Sonnet validation confirmed the LLM timeout repair:
10/10 `code/generate_patch` traces succeeded, with code durations from
`45.60s` to `124.55s` and no old 60s/125s timeout-failure pattern. The new
blocking issue was APS observation-budget handling: several branches generated
code and passed or repaired Contract preview, but `proposal.algorithm_smoke`
was replaced by `result_too_large` because the remaining transcript budget was
too small. The smoke tool had effectively run; the error message implied
otherwise.

Current repair: APS now compacts `proposal.algorithm_smoke` observations the
same way it compacts Contract preview observations, preserving pass/fail,
issue summary, static contract summary, and tainted/non-promotional flags while
dropping large preview bodies. The self-check observation reserve now scales
for Contract + smoke previews, and residual budget failures are reported as
smoke observation-budget failures rather than code-generation failures.

Validation smoke:

```text
run_root=/home/clawd/research/scion-experiments/v04-algorithm-smoke-budget-repair-sonnet-3r-20260515T042430Z
rounds=3
stopped_reason=max_rounds_exhausted
code_traces=5/5 ok
algorithm_smoke=3/3 ok with compact smoke preview retained
screening=3/3 reached
decision=3/3 abandon by SCREENING_FAIL_WIN_RATE
```

This confirms the framework path is now past the LLM timeout and
algorithm-smoke observation-budget blockers at short-run scale. The remaining
negative signal is solver quality: generated solver-design candidates reach
screening but lose to the champion.

Latest runtime-smoke/C9c repair validation:

```text
run_root=/home/clawd/research/scion-experiments/v04-runtime-smoke-audit-repair-sonnet-2r-20260515T113941Z
rounds=2
stopped_reason=max_rounds_exhausted
screened_experiments=0
round_1=full baseline_algorithm.py rewrite; failed old C9c before smoke
round_2=provider 500 during code generation
post_repair_replay=round_1 repaired patch passed Contract C9c and proposal.algorithm_smoke runtime canary
```

The replay matters more than the noisy 2-round run: after C9c learned to
recognize local runtime-guard helpers such as `while within_budget():`, the
Round 1 repaired patch passed static Contract preview and the new tainted
runtime smoke. The canary run loaded
`policies/baseline_algorithm.py`, produced a valid solution, recorded
`solver_algorithm_errors=0`, and split activity into
`solver_algorithm_improving_moves=1` and
`solver_algorithm_neutral_accepted_moves=14679`.

Detailed analysis:
[`v0.4-runtime-smoke-audit-c9c-repair-20260515.md`](../experiments/v0.4/v0.4-runtime-smoke-audit-c9c-repair-20260515.md)

Claude Code comparison: the next deeper design step is a Scion-native
continuous tool-use loop. Scion should keep permission, taint, exposure,
transcript, and promotion gates, but expose controlled proposal tools as native
LLM tools throughout hypothesis/code work. `generate_patch` should become the
code-phase finalizer after the agent has had a bounded chance to inspect
surface/branch/memory/feedback, draft, run Contract preview and algorithm
smoke, and repair from returned observations.

Detailed analysis:
[`v0.4-codegen-timeout-policy-repair-20260515.md`](../experiments/v0.4/v0.4-codegen-timeout-policy-repair-20260515.md)

Earlier same-day notes:

- `/home/clawd/research/scion-experiments/v04-sdk-retry-control-sonnet-1r-20260514T174450Z`
  completed the full 1-round branch-owned algorithm-subject path. It targeted
  `policies/baseline_algorithm.py`, passed Contract, Verification, and 16/16
  formal screening pairs, then was normally abandoned by
  `SCREENING_FAIL_WIN_RATE`. This validated framework stability but not solver
  quality.
- `/home/clawd/research/scion-experiments/v04-bounded-while-repair-smoke-opus-1r-dataroot-20260514T172756Z`
  also completed the full chain with 16/16 valid pairs and 16/16
  `solver_algorithm_*` runtime observations after a compact timeout retry,
  but it used Opus and is retained only as a secondary framework sample.
- `/home/clawd/research/scion-experiments/v04-branch-algorithm-subject-smoke-opus-1r-20260514T164018Z`
  selected `modify/solver_design`, targeted
  `policies/baseline_algorithm.py`, and reasoned about the ALNS+VNS algorithm
  body, but failed before official experiment pairs on a static C9c
  `while`-loop boundary that is now repaired. That failure was a
  Contract-preview rejection, not research-object drift: generated code used
  `while True` inside route construction and failed `C9c_complexity_bound` for
  `uncapped while loop`.
- `/home/clawd/research/scion-experiments/v04-bounded-while-repair-smoke-opus-1r-20260514T171241Z`
  completed code generation and Contract preview, but was launched without
  `SCION_PROBLEM_DATA_ROOT`; all formal pairs failed on missing CVRPLIB files,
  so it is an invalid launch-environment sample rather than solver evidence.

Follow-up repair: C9c now still rejects true unbounded `while True` and
unbounded improvement-flag loops, but recognizes two statically bounded
algorithm-body patterns: `while True` with a visible counter-bound break, and
`while True` that directly shrinks a finite collection on each non-break
iteration. Contract detail now includes the offending loop line. CVRP
solver-design prompts also tell code agents to prefer `for range(max_*)` loops
and to make any `while` bound statically obvious.

Latest baseline-algorithm subject smoke:

```text
run_root=/home/clawd/research/scion-experiments/v04-baseline-algorithm-subject-smoke-opus-2r-20260514T154153Z
model=claude-opus-4-6
problem=cvrp
protocol=formal
rounds_requested=2
time_limit_sec=60
agentic_session_timeout_sec=1800
status=terminated_for_invalid_research_object_analysis at 2026-05-14T16:11:51Z
target_file=policies/baseline_algorithm.py
```

Post-run analysis:

- Round 1 selected `modify/solver_design` with target
  `policies/baseline_algorithm.py`.
- Code phase generated an activated algorithm-body patch in that file, passed
  static Contract preview, then passed `proposal.algorithm_smoke` on tainted
  synthetic CVRP preview before entering official evaluation.
- Screening confirmed why the previous adapter was still wrong. The first
  candidate was 0 wins, 4 ties, 12 losses, median pair delta `-6.0`, and
  abandoned by `SCREENING_FAIL_WIN_RATE`.
- The failure was not just weak code quality. The candidate rewrote a
  simplified, inactive Scion template instead of modifying a branch copy of
  the real algorithm body. The original CVRP algorithm was still effectively a
  reference object, so Scion was training the agent to become a postprocessor
  or replacement-template author.
- That invalid experiment was terminated and the repair now makes
  `baseline_algorithm.py` a branch-owned, active ALNS+VNS algorithm subject
  under selected `solver_design` runtime. Promotion still requires the normal
  Contract, Verification, Protocol, and Decision gates; only a promoted branch
  becomes champion.

Previous analyzed code-scope/feedback-budget smoke:

```text
run_root=/home/clawd/research/scion-experiments/v04-code-scope-control-smoke-opus-2r-20260514T122210Z
model=claude-opus-4-6
problem=cvrp
protocol=formal
rounds_requested=2
rounds_completed=2 APS rounds, 1 screened experiment
time_limit_sec=60
agentic_session_timeout_sec=1800
git_commit=2e6a888
exit_code=0
status=max_rounds_exhausted
terminal_reason=code_generation_failed
analysis_doc=scion/docs/experiments/v0.4/v0.4-code-scope-control-feedback-budget-opus-2r-20260514.md
```

Summary:

- The prior code-scope repair worked for final code generation: all three code
  traces returned successfully instead of timing out.
- Round 1 reached Contract, Verification, and screening under
  `modify/solver_design`. It had 16/16 valid pairs, `win_rate=0.125`,
  `median_delta=0.0`, and median runtime ratio about `0.771`.
- The screened candidate produced real solver telemetry
  (`solver_algorithm_accepted_moves` nonzero on 7/16 pairs and
  `solver_algorithm_best_delta` weighted sum `53`), but it was still abandoned
  by `SCREENING_FAIL_WIN_RATE`.
- Round 2 used the feedback correctly at the hypothesis level, identifying
  baseline bootstrap as consuming too much runtime and proposing a no-baseline
  construction/local-search solver.
- Round 2 then failed before useful preview evidence could be retained because
  screening/runtime observations had already consumed almost the entire 64k
  APS observation budget. Contract preview was recorded as
  `result_too_large`, not as a deterministic pass/fail preview.

Current repair compacts feedback observations at the APS boundary, reserves
self-check observation budget through code phase, skips late feedback pulls
when that reserve is at risk, and tightens solver-design code scope to one
compact algorithm slice. This is a framework-control repair; it does not
change CVRP objective, feasibility, parser, splits, seeds, or Decision rules.

Previous analyzed no-op-feedback smoke:

```text
run_root=/home/clawd/research/scion-experiments/v04-solver-noop-feedback-smoke-sonnet-2r-20260514T112251Z
model=claude-opus-4-6
problem=cvrp
protocol=formal
rounds_requested=2
rounds_completed=2 APS attempts, 0 screened experiments
time_limit_sec=60
agentic_session_timeout_sec=1800
git_commit=a653388
exit_code=0
status=max_rounds_exhausted
terminal_reason=code_generation_failed
analysis_doc=scion/docs/experiments/v0.4/v0.4-full-solver-subject-code-phase-agentic-repair-20260513.md
```

Summary:

- The run did not validate no-op micro-eval or screening feedback priority
  because neither round generated a patch.
- Both rounds stayed on `modify/solver_design` and code phase read the full
  selected surface, so boundary/tool plumbing was not the blocker.
- Both final `generate_patch` calls timed out after three provider attempts,
  with roughly 30k user characters plus a 9k system block.
- The hypotheses were over-broad: hybrid construction, baseline-bootstrapped
  iterative local search, and destroy/repair all in one patch.
- Current repair therefore treats solver-design timeout as a scope-control
  failure: the first code prompt is compact by default, and a timeout triggers
  one in-session compact semantic retry.

This run is superseded by the code-scope/feedback-budget smoke above.

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

Latest solver-design module-subject repair validation:

- `policies/baseline_algorithm.py` is now a stable entrypoint backed by the
  branch-owned `policies/baseline_modules/` package.
- `context.read_surface("solver_design")` includes bounded support-module
  previews for the default entrypoint read; target-specific module reads stay
  under tool result budgets.
- Focused CVRP/APS/Contract subset:
  `404 passed in 49.03s`.
- Full Scion suite:
  `1669 passed, 1 skipped in 89.96s`.
- Direct CVRP canary with `SCION_SELECTED_SURFACE=solver_design` loaded
  `policies/baseline_algorithm.py`, returned active solver-design telemetry,
  and had `solver_algorithm_errors=0`.

Latest solver-design no-op feedback repair:

- Independent smoke:
  `/home/clawd/research/scion-experiments/v04-code-self-check-smoke-sonnet-2r-20260514T091556Z`
  completed 2/2 rounds on commit `06e9365` with `n_experiments=2`,
  `champion_version=1`, `stopped_reason=max_rounds_exhausted`, and exit code
  `0`.
- Both candidates were valid and active under `solver_algorithm`, but both
  were abandoned by `T4: win_rate < 0.3`.
- Round 1: 3 wins, 1 loss, 12 ties; median runtime ratio about `1.234x`;
  several formal cases hit `time_limit`.
- Round 2: 1 win, 2 losses, 13 ties; median runtime ratio about `1.063x`;
  `solver_algorithm_move_attempts` was positive but
  `solver_algorithm_accepted_moves` and `solver_algorithm_best_delta` were
  zero on nearly all pairs.
- The repair adds a CVRP synthetic improvement-trap micro-eval to Contract
  preview for baseline-seeded `solver_design` patches and improves runtime
  feedback ordering so solver move/no-op telemetry reaches the next code and
  hypothesis prompts.

## Next Actions

P1:

- Run a 1-2 round smoke after the latest C9c/smoke permission repair. The
  first gate is that the 6-round failure modes no longer recur: bounded
  `while len(collection) < cap/q` loops should pass Contract preview, true
  unbounded `while improved` loops should still fail, and
  `proposal.algorithm_smoke` should apply patches inside copied read-only
  champion snapshots without `PermissionError`.
- Run a 1-2 round smoke after the solver-design module-subject repair. The
  first gate is that APS can legally choose a focused
  `policies/baseline_modules/*.py` target, static preview defers module
  interface checks to workspace smoke, and `proposal.algorithm_smoke` runs the
  stable `baseline_algorithm.py::solve(...)` entrypoint after applying a module
  patch.
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
- Re-run a 1-2 round smoke after the no-op feedback repair. The first gate is
  that the next hypothesis/code phase explicitly reasons from
  `solver_algorithm_accepted_moves`, `solver_algorithm_best_delta`, and runtime
  regression instead of proposing another baseline-heavy wrapper.
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
  [`v0.4-solver-design-boundary-c9c-smoke-permission-repair-20260515.md`](../experiments/v0.4/v0.4-solver-design-boundary-c9c-smoke-permission-repair-20260515.md)
- Problem-object adaptation pivot:
  [`problem-object-adaptation-pivot.md`](../engineering/problem-object-adaptation-pivot.md)
