# Scion v0.4 Current State

*Last updated: 2026-05-10*

## Status

v0.4 is in formal validation preparation after the CVRP adapter/runtime and
campaign-controller hardening pass. The current working branch is `v0.4-dev`.

The v0.4 focus remains:

- keep `scion/scion` as a problem-agnostic research framework;
- keep warehouse delivery and CVRP semantics behind problem adapters/packages;
- make algorithm efficiency and runtime completeness default promotion
  governance;
- make `campaign.py` thinner through extracted lifecycle/orchestration
  services;
- use CVRP as the second real problem class for adapter/protocol validation.

Latest interpretation: APS observation-budget/recovery repair from `af4ab5b`
has passed control-path validation, and selected-surface runtime reporting is
validated in real formal CVRP artifacts. The first `baseline_policy` Sonnet
diagnostic also completed. It proved that the problem-owned surface can be
selected, patched, loaded, audited, and screened through the formal VRP path,
with all declared runtime fields present for the evaluated candidate, but it
did not produce solver-quality evidence. CVRP now has a separate
`main_search_strategy` whole-algorithm surface in
`policies/main_search_strategy.py`; it governs construction, repo-local
baseline budget/params, package-owned main-loop components including
route-pair swap and bounded destroy/repair, acceptance/restart/perturbation,
and optional post-baseline registry operators. The current blocker remains
CVRP algorithm-surface efficacy. A tightly forced `main_search_strategy`
three-round diagnostic completed from the current dirty worktree using the
`claw` environment. It validated continuous forced-surface control and active
whole-algorithm runtime audit, but only one candidate reached screening and it
failed `SCREENING_FAIL_WIN_RATE`. Do not start a long solver-quality
validation yet. Singleton semantic novelty has been repaired so distinct
strategy identities are not collapsed by target file. APS surface reads have
also been repaired with a compact `surface-contract.v1` section view and a
48000-character default observation cap. A clean-worktree forced
`main_search_strategy` diagnostic from commit `b98196b` validated those control
repairs: all three candidates reached screening and all stayed on the forced
surface. It still did not produce solver-quality evidence; all three failed
`SCREENING_FAIL_WIN_RATE`, and none selected `route_pair_swap` or
`bounded_destroy_repair`. The current blocker is candidate use and efficacy of
the deeper problem-owned main-search components, not force-surface drift or
selected-surface runtime audit. A 2026-05-09 read-only Core/CVRP gap audit
also found that the C10 singleton novelty repair is incomplete when structured
semantic signature fields are unavailable: the implementation can still fall
back to hypothesis free text instead of strict target-file identity. Treat that
as a v0.4 core governance fix before relying on longer forced-surface
diagnostics. That governance repair and the first CVRP deep-component surface
repair are now implemented in the working tree after the 2026-05-09 audit:
C10 no longer falls back to free-text semantic identity, patch ContractGate
checks use the approved selected surface for interface/identity/complexity
validation, and `main_search_strategy` now records selected/attempted/
accepted/skipped component telemetry plus stronger route-pair-swap and bounded
destroy/repair behavior. Focused, boundary, and full test suites pass. The
short forced `main_search_strategy` smoke from clean commit `e25680a` has now
completed and is analyzed: it validated selected-surface runtime audit and the
new component telemetry for the evaluated candidate, and it produced
nontrivial pair-level screening movement, but it still did not select or
attempt `route_pair_swap` or `bounded_destroy_repair`. A second forced
hypothesis was blocked by `C10_novelty`, so only one candidate reached
screening. The follow-up optimization slice is now implemented: forced
semantic singleton proposal context renders declared structured novelty fields
and occupied signatures, APS draft/preview reports missing structured identity
before C10, C10 duplicate details distinguish structured duplicate from
strict-target fallback, and CVRP `main_search_strategy` emits explicit
deep-component coverage status for forced diagnostics. Do not launch long CVRP
solver-quality validation yet; the next short smoke should be a five-round
forced `main_search_strategy` diagnostic. That five-round smoke has now
completed: deep components were selected and attempted in every screened
candidate, and C10 no longer blocked follow-up hypotheses, but all screened
candidates still failed `SCREENING_FAIL_WIN_RATE`; `bounded_destroy_repair`
accepted zero moves despite many attempts. The blocker has moved from
surface-control plumbing to bounded destroy/repair efficacy and screening
quality. The next CVRP package repair is now implemented: bounded
destroy/repair splits repair budget across pending customers, falls back to
smaller bounded destroy subsets, records repair fallback counts, and has a
formal-like controlled regression showing accepted bounded destroy/repair moves
under `rounds=5, top_k=64`. The next step is another five-round forced
`main_search_strategy` smoke, not long validation. That smoke has completed:
bounded destroy/repair produced accepted moves in one screened candidate and
the dominant skip reason moved away from repair-budget exhaustion, but all
screened candidates still failed `SCREENING_FAIL_WIN_RATE`. The blocker is now
net case-level efficacy of accepted moves, not component execution. The next,
stronger CVRP package repair is now implemented: active `main_search_strategy`
formal-like runs apply a baseline quality guard and conservative baseline-param
clamps, route-pair improvement can gate bounded destroy/repair, destroy/repair
has a per-search accepted-move cap and positive improvement floor, and the main
loop explicitly returns the phase-best solution. The next smoke should test
whether these net-benefit guards improve case-level outcomes. That smoke has
now completed and is analyzed: it finished normally but did not improve
case-level screening quality. The forced diagnostic control regressed once,
with one round drifting to `route_local`; the three screened candidates all
failed `SCREENING_FAIL_WIN_RATE` with case-level `win_rate=0.0`. The
net-benefit guards executed and reduced uncontrolled destroy/repair acceptance,
but `bounded_destroy_repair` accepted zero moves and accepted route-pair moves
did not translate into case-level wins. Long CVRP validation remains blocked.
Deeper APS analysis found that the forced-surface drift occurred in the
hypothesis phase, not code generation or summary reporting: the agent still had
tool/task affordance to choose from all surfaces, then code generation
implemented the already-approved `route_local` hypothesis. The same analysis
also found that the APS sessions mostly read problem/surface context and did
not call memory or screening/runtime feedback tools, so the agent was not yet
doing deep evidence-driven strategy diagnosis. The next repair should first
restore hard forced-surface control, stabilize the
`main_search_baseline_param_clamps` runtime evidence contract, and make forced
diagnostics consume bounded screening/runtime feedback before further CVRP
strategy tuning. That repair is now implemented in the working tree: forced
surface/action/target constraints are carried into APS tool context and fail
closed before code generation, APS planner context requires all available
bounded memory/screening/runtime feedback tools, and CVRP
`main_search_baseline_param_clamps` now records a non-empty no-clamp evidence
object instead of `{}`. Focused, boundary, and full test suites pass. The next
step is another five-round forced `main_search_strategy` smoke to confirm that
no off-surface hypothesis reaches code generation, no no-clamp evidence false
failure recurs, and APS traces show bounded feedback use before hypothesis
finalization. That smoke has now completed: forced-surface drift did not
recur, no-clamp evidence no longer false-failed, and APS did read bounded
memory/screening/runtime feedback, but only one of five rounds produced a
screened candidate. The new blocker is APS observation-budget/fallback
behavior: repeated feedback/list-surface reads can exceed the 48000-character
observation budget before patch generation. The next repair should compact and
deduplicate APS feedback/fallback observations before another CVRP strategy
slice. That repair is now implemented and the follow-up five-round smoke from
commit `d17c8b4` has completed. The APS budget repair worked: no
observation-budget failures recurred, feedback/memory tools were still used,
and all five generated hypotheses stayed on forced `main_search_strategy`.
However, the run produced only one code patch and one screened candidate
because rounds 2-5 failed hypothesis Contract at `C10_novelty`. The causal
blocker is now singleton semantic novelty persistence: round 1 passed without
a structured `novelty_signature`, was later recorded as rejected after
screening failure, and then caused later structured `main_search_strategy`
proposals to fall back to strict target-file duplicate identity. Long CVRP
validation remains blocked. The singleton semantic novelty persistence repair
is now implemented in the working tree: C10 fails candidate semantic singleton
`modify` hypotheses that lack usable structured identity before code
generation, old empty-signature records no longer poison later valid
structured proposals, and forced-surface context renders occupied structured
signatures from active, blacklisted, and rejected hypotheses. The next step is
focused/boundary/full validation, then another five-round forced
`main_search_strategy` smoke. That smoke has now completed from commit
`7111d69`: C10 no longer blocked later singleton hypotheses, four code patches
reached screening, observation budget remained healthy, and selected-surface
audit was complete. All screened candidates still failed
`SCREENING_FAIL_WIN_RATE`; the best round reached only case-level
`win_rate=0.25` with `median_delta=0.0`. The current blocker is proposal
feedback and efficacy attribution: `feedback.query_screening` and
`feedback.query_runtime` returned empty/unavailable results even after prior
screening rounds, and accepted component moves still do not clearly translate
through phase deltas into final case-level benefit. Do not run long CVRP
validation.

The broader design conclusion is now captured in
[`v0.4-problem-algorithm-onboarding.md`](../../design/v0.4/v0.4-problem-algorithm-onboarding.md):
Scion core can govern autoresearch only after a solver has been made into a
Scion-native research object with adapter semantics, declared surfaces,
component libraries, runtime audit, and tests. The CVRP work is the manual
prototype of that onboarding layer. The version boundary is now recorded in
[`v0.5-onboarding-memo.md`](../roadmap/v0.5-onboarding-memo.md): v0.4 should
close around autoresearch feasibility on manually onboarded problem packages,
while v0.5 should make problem/algorithm onboarding a first-class module.

## Current Engineering State

### Framework Boundary

- Framework prompt assembly no longer hardcodes warehouse/VNS/CVRP mechanics.
- `ContextManager` exposes a generic `solver_mechanics` field.
- Problem-specific mechanics are rendered only through the problem adapter.
- Mechanism taxonomy classification is problem-spec driven: framework code only
  normalizes text and matches configured families/aliases, while warehouse and
  CVRP aliases live in their respective `problem-v1.yaml` files.
- Legacy objective/saturation fallbacks no longer embed warehouse metric names;
  compatibility paths use generic metric order or `champion_metrics` mappings.
- Framework runtime env passthrough is generic for `SCION_*` variables, not tied
  to any single research object.
- Legacy non-adapter feasibility/objective verification no longer reconstructs
  warehouse-specific objects in Scion. New problems must use `ProblemAdapter`;
  old non-adapter problems need generic legacy oracle hooks.

### CVRP Runtime

- CVRP `.vrp` runs can use the repo-local `vrp/src` ALNS+VNS baseline when
  `SCION_PROBLEM_DATA_ROOT` points at the repo `vrp` directory.
- Synthetic fixtures do not automatically trigger the full `vrp/src` baseline.
- Required-baseline fallback or baseline errors are runtime audit failures, not
  objective ties.
- Generated operators returning workspace-local `models.CvrpSolution` are
  accepted structurally when the route contract is valid.
- Malformed, infeasible, or exception-raising operator outputs fail closed via
  runtime audit.
- CVRPLIB internal node ids from `vrp/src` are mapped back into Scion's
  depot-first CVRP id space.
- Generated registry operators now stop after a complete no-improvement round;
  no-op post-baseline operators no longer repeat for 20 rounds and distort
  runtime evidence.

### Runtime-Aware Optimization

- Pair-level runtime fields are written into protocol raw metrics.
- Screening runtime feedback is injected into proposal context with explicit
  failure causes: failed pairs, candidate/champion failures, runtime ratios,
  operator attempts/accepted moves, operator errors, and invalid outputs.
- Selected-surface required runtime fields are copied into candidate-side
  protocol pair metrics using the problem-declared field list, including
  bounded non-scalar values such as `algorithm_plan` and executed phase lists.
- Protocol results carry a bounded `candidate_surface_runtime_summary` with
  per-required-field present/missing/empty/failed counts and representative
  values. `campaign_summary.json` includes that summary with the selected
  surface, without adding these tainted runtime values to DecisionFeatures.
- Screening feedback distinguishes no-op/weak operators: no accepted moves,
  tie-dominated evidence, and `operator_stop_reason=no_improvement_round` are
  proposal-quality signals rather than schema/runtime failures.
- Validation/frozen exposure remains aggregate-only and does not expose raw
  metrics paths or per-case feedback.
- Proposal slow-case feedback uses `protocol.runtime.max_runtime_ratio`.
- `V9_perf_guard` now uses the configured runtime slowdown threshold instead of
  a separate hardcoded verification threshold.
- Decision governance treats candidate runtime failures, incomplete runtime
  evidence, and large runtime regressions as promotion vetoes.
- Programmatic adapter-backed campaigns now build strict runtime verification
  by default when no explicit verification gate is supplied. Adapter-backed
  campaigns without a protocol runner fail closed unless compatibility mode is
  explicitly requested.

### ProblemSpecV1

- `ProblemSpecV1` is the authoritative schema when present.
- CLI loading now bridges `ProblemSpecV1` into the legacy runtime shape instead
  of trusting two independent specs.
- `problem-v1.yaml` files with `root_dir: PLACEHOLDER` resolve root relative to
  the YAML file.
- `ProblemSpecV1.research_surfaces` is now the forward-compatible abstraction
  for optimization targets. Operator design remains a first-class surface, and
  non-operator surfaces such as CVRP `search_policy` are declared by the
  problem package rather than hardcoded in Scion core.
- Surface metadata carries target files, action permissions, prompt hints, and
  optional module-level `required_functions`; ContractGate uses that metadata
  for surface-aware hypothesis and patch checks.

### Research Surface Model

- Scion's framework object is now "heuristic algorithm research surface", not
  universally "operator pool".
- Operator design optimization is preserved as the default/legacy surface:
  problems without `research_surfaces` still use `operator_interface.categories`
  as before.
- CVRP currently exposes nine surfaces: `route_local`, `route_pair`,
  `ruin_recreate`, `search_policy`, `baseline_policy`,
  `construction_policy`, `neighborhood_portfolio`, and
  `algorithm_blueprint`, plus the preferred whole-algorithm
  `main_search_strategy`.
- The CVRP `search_policy` surface allows bounded optimization of baseline
  time fraction, post-baseline operator round limit, and whether post-baseline
  operators run, without allowing LLM edits to `solver.py`.
- The CVRP `baseline_policy` surface is a singleton policy in
  `policies/baseline_policy.py`. It exposes bounded repo-local `vrp/src`
  ALNS+VNS main-search parameters: destroy ratio, ALNS segment length,
  adaptive reaction factor, VNS enablement/no-improvement limit, threshold
  gates, and max destroyed customers. Invalid returns are sanitized to
  defaults or clamped, recorded as `baseline_policy_errors`, and fail selected
  surface runtime audit.
- The CVRP `construction_policy` surface allows bounded selection among
  package-owned construction modes and a numeric demand bias. It emits
  `construction_surface_loaded`, `construction_errors`, `construction_mode`,
  `construction_elapsed_ms`, `construction_routes`, `construction_distance`,
  and `construction_feasible`; construction errors fail closed through runtime
  audit.
- The CVRP `neighborhood_portfolio` surface allows bounded scheduling of
  predeclared post-baseline registry component families. It controls enabled
  components, component weight multipliers, top-k scheduling, round caps, and
  attempt limits, and emits `portfolio_surface_loaded`, `portfolio_errors`,
  `enabled_components`, `component_weights`, `candidate_limits`,
  `component_attempts`, `component_accepted`, `component_runtime_ms`, and
  `portfolio_stop_reason`; portfolio errors fail closed through runtime audit.
- The CVRP `algorithm_blueprint` surface is a top-level config surface in
  `policies/algorithm_blueprint.py`. It is inactive by default, preserving the
  existing solver lifecycle. A valid enabled plan can coordinate bounded
  construction ensemble, baseline time fraction, package-owned local search
  (`intra_route_2opt`, `inter_route_relocate`), restart knobs, and
  post-baseline registry-operator toggle/round limit. Invalid plans record
  `algorithm_blueprint_errors`, do not take over the lifecycle, and fail
  selected-surface runtime audit.
- The CVRP `main_search_strategy` surface is a singleton whole-algorithm
  config surface in `policies/main_search_strategy.py`. It is inactive by
  default and disables post-baseline registry operators unless explicitly
  requested by the plan. A valid enabled plan takes over the main CVRP
  lifecycle: bounded construction ensemble, repo-local baseline budget and
  sanitized baseline params, package-owned improvement components
  (`intra_route_2opt`, `inter_route_relocate`, `route_pair_swap`,
  `bounded_destroy_repair`), strict-improvement acceptance threshold, restart
  and perturbation knobs, and optional registry-operator round limit. Invalid
  plans record `main_search_strategy_errors`, do not take over, and fail
  selected-surface runtime audit.
- CVRP still needs a successful surface-efficacy diagnostic that reaches the
  formal `.vrp` main search and shows nontrivial screening quality. The next
  diagnostic should force `main_search_strategy` so Scion governs the whole
  CVRP algorithm slice rather than another post-baseline operator or
  baseline-policy-only change.
- `scion run --force-surface <surface>` is a diagnostic experiment-control
  hook for proposal smoke tests. It accepts only declared research surfaces,
  fails closed during CLI/campaign startup for unknown surfaces, and can derive
  `action=modify` plus the singleton target file for surfaces such as
  `main_search_strategy` or `algorithm_blueprint`. This hook is not a Decision
  input, not solver-quality evidence, and should be used next to force
  `main_search_strategy` smoke coverage without hardcoding CVRP or any
  specific surface into framework core.
- CVRP policy-surface prompts and adapter interface rendering now expose the
  safe `CvrpInstance` policy API explicitly: `customer_ids`, `customer_count`,
  `demands[customer_id]`, `capacity`, and `distance(i, j)`. The problem package
  does not define `instance.customers`; reached uses fail in adapter preview or
  runtime audit rather than becoming a silent alias.

### Campaign Structure

- `campaign.py` has been reduced by extracted services for proposal, evaluation,
  promotion, evidence, failure lifecycle, branch stepping, workspace lifecycle,
  and decision coordination.
- Constructor-time service composition now lives in `core/campaign_composition.py`;
  `campaign.py` remains the public facade and compatibility owner.
- The controller still owns the top-level campaign loop and compatibility
  plumbing, but most side-effect-heavy paths now have dedicated modules.
- Proposal/schema failures during Round 1 now write `StepRecord` rows, so
  campaign summaries do not silently miss failed LLM proposal rounds.
- CLI diagnostic runs can use `--disable-early-stop` to keep fixed-round
  validation from being truncated by idle/stagnation early-stop policy.
- Frozen holdout attempts are governed by a campaign-level persisted ledger.
  Exhaustion is recorded as `frozen_budget_exhausted`, separate from objective
  failure.
- The initial v1 champion is now persisted in `ChampionStore` so campaign
  evidence has a durable base-champion anchor even before any promotion.
- Campaign summaries now include `formal_readiness`, derived from top-level
  final evidence refs, without changing per-step schema.
- CVRP search memory now uses route-native family taxonomy from
  `ProblemSpecV1` instead of warehouse-shaped fallback labels.
- Family extraction now prefers the step's declared problem locus when
  multiple problem-owned aliases are present in a hypothesis, preventing
  "unlike prior failed family" text from corrupting coverage/stagnation
  summaries.

## Validation

Full Scion test suite:

```text
cwd: /home/clawd/research/or-autoresearch-agent
command: /home/clawd/miniconda3/envs/claw/bin/python -m pytest scion/scion/tests -q
```

Latest result:

```text
1475 passed, 1 skipped in 51.70s
```

Latest focused APS compactness/proposal validation:

```bash
cd scion
/home/clawd/miniconda3/envs/claw/bin/python -m pytest scion/tests/unit/test_agentic_proposal_tools.py scion/tests/unit/core/test_proposal_pipeline.py scion/tests/test_proposal_validation.py -q
```

```text
101 passed in 0.94s
```

Latest focused CVRP main-search-surface validation:

```bash
cd /home/clawd/research/or-autoresearch-agent/scion
/home/clawd/miniconda3/envs/claw/bin/python -m pytest scion/tests/test_cvrp_adapter.py scion/tests/test_problem_bridge.py scion/tests/unit/test_research_surfaces.py::test_cvrp_problem_v1_exposes_policy_surfaces scion/tests/unit/test_research_surfaces.py::test_cvrp_main_search_strategy_contract_targets_and_required_functions scion/tests/unit/test_research_surfaces.py::test_cvrp_default_policy_files_match_declared_signatures scion/tests/unit/test_research_surfaces.py::test_cvrp_solver_loads_workspace_main_search_strategy_and_applies_bounds scion/tests/unit/test_research_surfaces.py::test_invalid_cvrp_main_search_strategy_counts_strategy_errors scion/tests/test_cvrp_solver_operator_runtime.py::test_default_main_search_strategy_policy_matches_contract_gate_interface scion/tests/test_cvrp_solver_operator_runtime.py::test_main_search_strategy_surface_declares_runtime_fields_and_default_is_inactive scion/tests/test_cvrp_solver_operator_runtime.py::test_enabled_main_search_strategy_runs_owned_main_loop_and_disables_registry_by_default scion/tests/test_cvrp_solver_operator_runtime.py::test_invalid_main_search_strategy_output_is_selected_surface_runtime_failure
```

```text
43 passed in 3.05s
```

Broader CVRP/protocol subset:

```bash
/home/clawd/miniconda3/envs/claw/bin/python -m pytest scion/scion/tests/test_cvrp_*.py scion/scion/tests/unit/evidence/test_cvrp_*.py scion/scion/tests/test_protocol.py scion/scion/tests/unit/test_agentic_proposal_tools.py -q
```

```text
227 passed in 34.29s
```

CVRP synthetic baseline smoke with explicit repo `vrp` baseline:

```text
success True
objective {'fleet_violation': 0, 'total_distance': 20.0, 'routes': 2}
baseline_mode vrp_alns_vns
baseline_required True
baseline_error None
```

## Completed Dual-Sonnet Diagnostic Run

Two independent Sonnet campaigns were launched and audited on 2026-05-04 UTC.

Run root:

```text
/home/clawd/research/scion-experiments/v04-dual-sonnet-20260504T091234Z
```

CVRP formal readiness campaign:

```text
model      = claude-sonnet-4-6
requested  = 50 rounds
actual     = 25 rounds
champion   = v1
promotions = 0
stop       = idle ratio 100.0% exceeds 60%
campaign   = /home/clawd/research/scion-experiments/v04-dual-sonnet-20260504T091234Z/cvrp/campaign
log        = /home/clawd/research/scion-experiments/v04-dual-sonnet-20260504T091234Z/cvrp/run.log
data_root  = /home/clawd/research/or-autoresearch-agent/vrp
protocol   = scion/scion/problems/cvrp/formal/protocol.yaml
split      = scion/scion/problems/cvrp/formal/split_manifest.yaml
seeds      = scion/scion/problems/cvrp/formal/seed_ledger.yaml
time_limit = 5 seconds per solver run
```

Warehouse delivery campaign:

```text
model      = claude-sonnet-4-6
requested  = 50 rounds
actual     = 25 rounds
champion   = v2
promotions = 1
stop       = idle ratio 88.0% exceeds 60%
campaign   = /home/clawd/research/scion-experiments/v04-dual-sonnet-20260504T091234Z/warehouse/campaign
log        = /home/clawd/research/scion-experiments/v04-dual-sonnet-20260504T091234Z/warehouse/run.log
problem    = scion/problems/warehouse_delivery/problem.yaml
protocol   = scion/problems/warehouse_delivery/protocol.yaml
split      = scion/problems/warehouse_delivery/split_manifest.yaml
seeds      = scion/problems/warehouse_delivery/seed_ledger.yaml
```

Detailed analysis is recorded in
`scion/docs/experiments/v0.4/v0.4-dual-sonnet-postrun-analysis-20260504.md`.

## Evidence Interpretation

The earlier full CVRP Sonnet run that produced all ties is not valid formal
quality evidence. It should be interpreted as a plumbing audit because the
prompt described the old high-invocation VNS pool while the CVRP wrapper was
actually applying a small post-baseline loop, generated operators hit a
workspace/package `CvrpSolution` class-identity mismatch, and the real
`vrp/src` baseline was not being used.

The dual-Sonnet run is not formal quality evidence. It is a framework audit run
that exposed CVRP runtime-loop noise, weak context failure-cause rendering,
diagnostic runs being truncated by early-stop, and missing proposal-failure
summary rows. The later post-repair prompt/context run is also invalid as
formal evidence because framework-level mechanism taxonomy still carried
problem labels instead of requiring aliases from the active problem spec.

## Post-Audit Repairs Completed

Completed after the dual-Sonnet audit:

- CVRP post-baseline operator loop stops after one complete no-improvement
  round and records `operator_stop_reason`.
- Data-root-relative formal `.vrp` cases require the external baseline and fail
  closed through runtime audit if it is unavailable.
- Proposal context now renders structured screening failure causes rather than
  compressing everything into `scr=0.00`.
- `scion run --disable-early-stop` supports fixed-round diagnostic experiments.
- Round-1 LLM proposal/schema failures now write `StepRecord` rows.
- Frozen holdout usage is enforced by a persisted campaign-level ledger.
- Formal readiness status is written into campaign summaries from final
  evidence refs.
- Programmatic adapter-backed campaigns default to strict runtime verification.
- Static complexity governance now rejects permutations, risky product over
  problem-scale iterables, uncapped while loops, and three-level problem-scale
  nested loops.
- CVRP search memory receives route-native family taxonomy from `ProblemSpecV1`.
- Mechanism taxonomy aliases are now problem-owned config, not framework code.
- Legacy protocol objective fallback and saturation case-feature fallback were
  made problem-agnostic.
- No-op/tie-dominated screening feedback is rendered as operator-quality
  guidance, and runtime slow-case feedback follows the configured threshold.
- Constructor-time campaign service wiring moved to
  `core/campaign_composition.py`.
- Initial v1 champion persistence, research-journal version/promotion counts,
  empty-pool strategy guidance, ambiguous family classification, CVRP route
  aliases, and CLI objective-policy plumbing were repaired after the
  2026-05-05 short CVRP boundary experiment.
- CVRP research surfaces now include a bounded `search_policy` policy surface;
  operator design remains a first-class surface, and ContractGate validates
  surface action/target/interface contracts.

Validation after these repairs and the research-surface slice:

```text
/home/clawd/miniconda3/envs/claw/bin/python -m pytest scion/tests -q
1246 passed, 1 skipped in 40.82s
```

## Completed Dual-Sonnet 50R Validation Run

Two independent Sonnet campaigns were launched and audited on 2026-05-05 UTC
after fixed-round execution, runtime feedback, framework-boundary cleanup, and
the first CVRP research-surface slice.

Run root:

```text
/home/clawd/research/scion-experiments/v04-dual-sonnet-50r-20260505T023113Z
```

Configuration:

```text
model=claude-sonnet-4-6
rounds=50
warehouse_time_limit=problem_default
cvrp_time_limit_sec=10
disable_early_stop=true
```

Outcome:

| Campaign | Status | Champion | Promotions | Interpretation |
| --- | --- | --- | ---: | --- |
| CVRP | `50/50`, `EXIT_CODE:0` | `v1_r0` | 0 | Valid framework run; no promotion because post-baseline CVRP surfaces were too weak/tie-dominated. |
| Warehouse | `50/50`, `EXIT_CODE:0` | `v4_r2` | 3 code promotions, 2 persisted weight revisions | Valid branch-governed promotion trajectory. |

Detailed analysis is recorded in:

```text
scion/docs/experiments/v0.4/v0.4-dual-sonnet-50r-20260505/
```

The run is valid as framework and campaign-dynamics evidence. It is not final
solver-quality evidence because both summaries remain `formal_ready=false` and
lack `final_evidence_refs`.

## Post-Run P0 Repairs Completed

After the 2026-05-05 dual-Sonnet analysis, the framework-level P0 repair slice
was completed without adding VRP- or warehouse-specific logic to Scion core.
Scion remains the generic campaign/research-surface governance framework;
warehouse delivery and CVRP remain problem packages / research objects.

Completed repairs:

- `C10_novelty` is now surface-aware for singleton policy surfaces. Distinct
  policy `modify` hypotheses against the same target file can be explored,
  while ordinary operator `modify/remove` remains strict by
  `(locus, action, target_file)`.
- `campaign_summary.json` now exposes DecisionEngine reason codes alongside
  protocol gate reason codes, so runtime vetoes such as
  `CANDIDATE_RUNTIME_FAILURE` are visible without SQLite inspection.
- Structural promotion now persists a non-empty
  `promotion_experiment_id` on promoted champion rows; weight-only revisions
  preserve the structural promotion id.
- `max_rounds_exhausted` closeout now terminalizes residual active branches
  with `MAX_ROUNDS_EXHAUSTED`, leaving final status/summary active-branch
  counts unambiguous.

Validation:

```text
/home/clawd/miniconda3/envs/claw/bin/python -m pytest scion/tests -q
1252 passed, 1 skipped in 39.48s
```

## Interrupted Follow-Up Dual Run

After the P0 repairs, a second dual Sonnet validation was started and then
stopped deliberately once it had already reproduced the key CVRP research-surface
signal.

Run root:

```text
/home/clawd/research/scion-experiments/v04-dual-sonnet-50r-20260505T104343Z
```

Stopped state:

| Campaign | Rounds | Experiments | Champion | Interpretation |
| --- | ---: | ---: | --- | --- |
| Warehouse | 30 | 27 | `v2_r1` | One evidence-backed promotion plus one weight revision; post-promotion search remained noisy. |
| CVRP | 17 | 10 | `v1_r0` | No promotions; completed candidates were screening-negative, again pointing to too-narrow CVRP algorithm exposure. |

The stop record is preserved at:

```text
/home/clawd/research/scion-experiments/v04-dual-sonnet-50r-20260505T104343Z/STOPPED.md
```

The key design conclusion is now captured in
[`v0.4-algorithm-design-space-optimization.md`](../../design/v0.4/v0.4-algorithm-design-space-optimization.md):
operator design optimization is a subset of heuristic algorithm design space
optimization. Scion core can now govern declared research surfaces, but CVRP must
expose richer problem-owned algorithm surfaces such as construction,
neighborhood portfolio, destroy/repair, and acceptance/restart policy surfaces.

## 2026-05-06 Short Sonnet CVRP Surface Validation

A detached five-round Sonnet CVRP run was launched after the
`research_surfaces v2` and `AgenticProposalSession` implementation pass to
validate the current formal CVRP path without reading raw run logs in the main
development session.

Run root:

```text
/home/clawd/research/scion-experiments/v04-short-agentic-sonnet-20260506T083427Z
```

Configuration:

```text
model=claude-sonnet-4-6
problem=cvrp
rounds=5
protocol=scion/scion/problems/cvrp/formal/protocol.yaml
cvrp_time_limit_sec=10
disable_early_stop=true
```

Outcome:

| Rounds | Experiments | Champion | Promotions | Stopped reason |
| ---: | ---: | --- | ---: | --- |
| 5 | 4 | `v1_r0` | 0 | `max_rounds_exhausted` |

Surface coverage from `campaign_summary.json`:

```text
create_new/route_local: 1
create_new/route_pair: 1
modify/construction_policy: 1
create_new/ruin_recreate: 1
modify/search_policy: 1
```

Interpretation:

- The run validates that the current CVRP problem package can expose multiple
  algorithm-level surfaces to Sonnet under the Scion governance path.
- Four evaluated candidates were abandoned by `CANDIDATE_RUNTIME_FAILURE`.
- One candidate failed verification with `V5_solution_consistency` because the
  runtime audit reported a policy clamp event.
- No frozen budget was spent and no final evidence refs were attached, so
  `formal_ready=false` is expected.

This is framework/control evidence, not solver-quality evidence. It supports the
next production-agent upgrade: `AgenticProposalSession` must use the declared
tool system as an auditable proposal-time observation layer before moving to a
free-form planner loop.

## Agentic Proposal Production Path

After the short CVRP validation, the agentic proposal path was upgraded from a
single-shot Creative Layer wrapper into a production-minimum bounded agent.

Completed capabilities:

- `AgenticProposalSession` uses declared proposal tools through
  `ProposalToolRegistry` and `ContextExposurePolicy`; tools cannot execute
  Verification, Protocol, Decision, or candidate workspace writes.
- Model-side tool selection is supported through the Creative Layer, but the LLM
  only selects tool names and JSON args. APS remains the execution boundary and
  validates every selection against the allowed tool set and schema.
- Deterministic fallback remains available when model tool selection is absent,
  malformed, forbidden, or fails.
- Tool-loop budgets, wall-time timeout, repeated tool-call fuse, static schema /
  target / contract preview, and fail-closed typed termination are implemented.
- Session artifacts are versioned, tainted, compact, replay-validatable, and
  safe for resume-context construction. They omit raw metrics refs, holdout
  detail, validation/frozen case feedback, transcript payloads, and patch code.
- Planner-backed APS sessions now fail over to compact feedback reads instead
  of stopping after only `context.list_surfaces` and `context.read_problem`;
  they also read the selected surface before code generation or partial
  finalization. Static target/schema/contract preview payloads are compact and
  omit full surface payloads and patch `code_content`.
- Surface context tools are compact by default: `context.list_surfaces` returns
  selection-oriented surface metadata, while `context.read_surface` defaults to
  `detail="compact"` with a bounded `surface-contract.v1` section view
  (`summary`, `interface`, `bounds`, `evidence`, `novelty`, `target_preview`)
  and a bounded code preview. `detail="full"`, `section`, and `max_code_chars`
  remain available as explicit debug/deep-inspection opt-ins.
- `AgenticSessionStore` maintains a file-backed recovery index with lookup by
  session id, idempotency key, and request. ProposalPipeline can inject sanitized
  resume context from prior valid artifacts without reusing patches or bypassing
  ContractGate.
- CLI inspection can validate one artifact or list agentic sessions under an
  artifact directory without printing transcript, observations, rationale, or
  raw refs.
- Compact proposal-session refs can appear in step/campaign summaries; agentic
  rationale, memory, and tool observations remain excluded from
  `DecisionFeatures`.

Validation:

```text
pytest scion/scion/tests/unit/test_agentic_proposal_tools.py \
  scion/scion/tests/unit/core/test_proposal_pipeline.py \
  scion/scion/tests/test_cli.py \
  scion/scion/tests/test_llm_client.py \
  scion/scion/tests/test_contract.py -q
193 passed

pytest scion/scion/tests -q
1385 passed, 1 skipped
```

Remaining production risks:

- The recovery index is a single JSON file updated atomically. It is adequate for
  this minimum slice, but a multi-writer-safe store is needed if several
  campaign processes write the same artifact directory concurrently.
- APS has a wall-time budget, but lower-level LLM/tool calls must also preserve
  their own timeouts so a blocking call cannot exceed the session budget before
  control returns.
- Completed sessions currently provide resume context only. Direct reuse of
  compact hypothesis/patch content is intentionally deferred because ContractGate
  must remain the mandatory path.

## 2026-05-06 APS/P5 Sonnet CVRP Smoke

A five-round detached Sonnet CVRP run was launched with the production-minimum
agentic proposal path enabled:

```text
run_root=/home/clawd/research/scion-experiments/v04-agentic-p5-sonnet-20260506T095427Z
model=claude-sonnet-4-6
problem=cvrp
rounds=5
agentic_proposal=true
disable_early_stop=true
cvrp_time_limit_sec=10
```

Outcome:

| Rounds | Experiments | Champion | Promotions | Stopped reason |
| ---: | ---: | --- | ---: | --- |
| 5 | 5 | `v1_r0` | 0 | `max_rounds_exhausted` |

Agentic proposal artifacts:

```text
agentic_session_index entries: 10
completed sessions: 5
partial_hypothesis_only sessions: 5
all entries tainted: true
all entries have idempotency_key: true
all entries have transcript_digest: true
```

Surface coverage:

```text
create_new/route_local: 1
create_new/route_pair: 1
modify/construction_policy: 1
create_new/ruin_recreate: 1
modify/neighborhood_portfolio: 1
```

Interpretation:

- The APS/P5 path is now campaign-usable: every round produced a completed
  versioned agentic session and a compact `proposal_session_ref` in the campaign
  summary.
- The earlier planner failure mode (`context.read_surface` with nonexistent
  surface `main`, followed by tool-loop/repeat-fuse termination) was repaired by
  recoverable-error fallback and did not recur in the successful smoke.
- Contract and verification passed for all five candidates; all five were later
  abandoned by `CANDIDATE_RUNTIME_FAILURE` in protocol decisioning.
- The next bottleneck is therefore not APS infrastructure. It is CVRP
  problem-package surface effectiveness and runtime/audit feedback: generated
  candidates are reaching governed evaluation but remain runtime-negative.

## 2026-05-06 Surface P0 Smoke

Surface P0 added generic declared function signatures for research surfaces,
ContractGate signature checks for module-style surfaces, richer CVRP
problem-package surface metadata, and tighter default CVRP neighborhood
portfolio limits.

Validation:

```text
pytest scion/scion/tests/unit/test_research_surfaces.py \
  scion/scion/tests/test_contract.py \
  scion/scion/tests/test_problem_bridge.py \
  scion/scion/tests/unit/test_agentic_proposal_tools.py \
  scion/scion/tests/test_cvrp_solver_operator_runtime.py -q
186 passed

pytest scion/scion/tests -q
1393 passed, 1 skipped
```

A three-round APS/P5 Sonnet CVRP smoke was then run:

```text
run_root=/home/clawd/research/scion-experiments/v04-surface-p0-sonnet-20260506T101326Z
model=claude-sonnet-4-6
rounds=3
agentic_proposal=true
```

Outcome:

| Rounds | Experiments | Champion | Promotions | Stopped reason |
| ---: | ---: | --- | ---: | --- |
| 3 | 2 | `v1_r0` | 0 | `max_rounds_exhausted` |

Observed surface behavior:

- APS artifacts remained healthy: three completed proposal sessions and three
  partial hypothesis sessions, all tainted and idempotency-keyed.
- One `route_local` candidate was rejected before runtime by
  `C9c_complexity_bound` for an uncapped while loop. This is the intended
  direction: unsafe implementations should fail in static governance, not in
  protocol runtime.
- Two candidates still reached screening and were abandoned by
  `CANDIDATE_RUNTIME_FAILURE`.

Interpretation:

Surface P0 improved the static interface/complexity boundary but did not solve
runtime-negative CVRP candidates. The next surface slice should move bounded
runtime-failure categories into `ProtocolResult` / campaign summary / proposal
context so the model can distinguish invalid output, operator exception,
policy return-shape errors, no accepted moves, and timeout-like failures without
reading raw metrics.

## 2026-05-06 Surface P1 Runtime Summaries

Surface P1 added bounded structured runtime-failure summaries to
`ProtocolResult`, step records, campaign summaries, proposal feedback, and APS
context tools. The summary is produced from public runtime result/audit fields,
not by opening raw metrics files in proposal context.

Validation:

```text
pytest scion/scion/tests/test_cvrp_solver_operator_runtime.py \
  scion/scion/tests/test_verification.py \
  scion/scion/tests/unit/test_agentic_proposal_tools.py \
  scion/scion/tests/unit/core/test_proposal_pipeline.py \
  scion/scion/tests/test_sprint_e2.py \
  scion/scion/tests/test_protocol.py \
  scion/scion/tests/unit/core/test_evidence_recorder.py -q
240 passed

pytest scion/scion/tests -q
1395 passed, 1 skipped
```

A two-round APS/P5 Sonnet CVRP smoke was then run:

```text
run_root=/home/clawd/research/scion-experiments/v04-surface-p1-sonnet-20260506T102812Z
model=claude-sonnet-4-6
rounds=2
agentic_proposal=true
```

Outcome:

| Rounds | Experiments | Champion | Promotions | Stopped reason |
| ---: | ---: | --- | ---: | --- |
| 2 | 2 | `v1_r0` | 0 | `max_rounds_exhausted` |

Both candidates were still abandoned by `CANDIDATE_RUNTIME_FAILURE`, but the
summary now exposed the actual bounded category:

```text
candidate_runtime_failure_categories: {"baseline_error": 24}
candidate_first_runtime_failure:
  category: baseline_error
  code: baseline_runtime_error
  component: runtime_audit
  detail_summary: required solver baseline failed: ModuleNotFoundError: No module named 'numpy'
```

Interpretation:

- Surface P1 achieved the intended observability change: the proposal-facing
  artifact can now distinguish infrastructure/baseline runtime failures from
  candidate algorithm failures without exposing raw metrics.
- This smoke should not be treated as solver-quality evidence because the
  active failure was an environment/baseline dependency issue, not a CVRP
  surface-design result.
- Before judging CVRP surface effectiveness, the formal CVRP execution
  environment must make the required baseline dependency set explicit and fail
  readiness before campaign launch when dependencies are missing.

## 2026-05-06 Claw Environment Preflight And Real Smoke

The previous Surface P1 smoke was run with the base Python interpreter, which
did not have `numpy`, while the project runtime environment is the conda
`claw` environment. The `claw` interpreter has the required dependency.

Repair:

- Added generic problem-owned runtime dependency declarations to
  `ProblemSpecV1`.
- Added framework preflight for declared Python modules and executables.
- CLI and campaign startup now fail closed before proposal generation when a
  declared dependency is missing, reporting the active `sys.executable`.
- CVRP declares its formal baseline dependency on `numpy` in its problem
  package; Scion core does not hardcode CVRP or numpy.

Validation under `claw`:

```text
/home/clawd/miniconda3/envs/claw/bin/python -m pytest scion/scion/tests -q
1402 passed, 1 skipped
```

A real APS/P5 CVRP smoke was then launched with the `claw` interpreter:

```text
run_root=/home/clawd/research/scion-experiments/v04-preflight-claw-sonnet-20260506T104100Z
model=claude-sonnet-4-6
rounds=3
agentic_proposal=true
python=/home/clawd/miniconda3/envs/claw/bin/python
```

Outcome:

| Rounds | Experiments | Champion | Promotions | Stopped reason |
| ---: | ---: | --- | ---: | --- |
| 3 | 3 | `v1_r0` | 0 | `max_rounds_exhausted` |

Agentic artifacts:

```text
agentic_session_index entries: 6
completed sessions: 3
partial_hypothesis_only sessions: 3
all entries tainted: true
all entries have idempotency_key: true
all entries have transcript_digest: true
```

Surface coverage:

```text
create_new/route_local: 1
create_new/route_pair: 1
create_new/ruin_recreate: 1
```

Interpretation:

- The environment issue is resolved for real campaign execution: failures no
  longer report `baseline_error` / missing `numpy`.
- All three candidates completed screening and were abandoned by
  `SCREENING_FAIL_WIN_RATE`, not by runtime infrastructure failure.
- Structured runtime summaries now expose the candidate-quality signal:
  `no_accepted_moves` dominated all three candidates, with accepted operator
  moves equal to 2/26, 0/24, and 0/24.
- The next surface optimization target is therefore no-op dominated
  post-baseline operator design. CVRP should steer Sonnet toward problem-owned
  policy surfaces that can alter construction, neighborhood portfolio, budget
  allocation, acceptance/restart, or destroy/repair behavior instead of adding
  more post-baseline polish operators.

## 2026-05-06 Surface P2 Runtime-Guided Steering

Surface P2 added problem-owned runtime-failure-aware steering metadata. Scion
core only aggregates structured screening categories and renders problem-declared
guidance; CVRP owns the actual recommendation that no-op dominated post-baseline
operators should shift attention toward algorithm-level surfaces such as
`construction_policy`, `neighborhood_portfolio`, and `search_policy`.

Validation:

```text
/home/clawd/miniconda3/envs/claw/bin/python -m pytest scion/scion/tests -q
1404 passed, 1 skipped
```

A three-round real APS/P5 CVRP smoke was then launched:

```text
run_root=/home/clawd/research/scion-experiments/v04-surface-p2-claw-sonnet-20260506T111322Z
model=claude-sonnet-4-6
rounds=3
agentic_proposal=true
python=/home/clawd/miniconda3/envs/claw/bin/python
```

Outcome:

| Rounds | Experiments | Champion | Promotions | Stopped reason |
| ---: | ---: | --- | ---: | --- |
| 3 | 2 | `v1_r0` | 0 | `max_rounds_exhausted` |

Surface coverage:

```text
create_new/route_local: 1
modify/construction_policy: 1
modify/search_policy: 1
```

Interpretation:

- The steering worked at the proposal level. After an initial no-op dominated
  route-local candidate, Sonnet moved to algorithm-level policy surfaces:
  `construction_policy` and then `search_policy`.
- The construction-policy candidate failed heavy verification with
  `V5_solution_consistency`; the search-policy candidate passed verification
  and screening but still failed `SCREENING_FAIL_WIN_RATE`.
- The next bottleneck is policy-surface correctness and efficacy, not surface
  selection. CVRP should add tighter static/preview checks for policy return
  values and a cheap problem-owned simulation/sanity preview for
  construction/search policy changes before full screening.

## 2026-05-06 Gate Audit And Policy Preview

A read-only audit of V1-V8 found that the v3 protocol structure remains valid,
but several early verification implementations still carry operator-space or
legacy warehouse assumptions. The intended direction is not to weaken the gates:
keep the v3 governance layers, but make the small gate implementations
surface-declared and adapter-declared.

Audit summary:

- V1 syntax, objective comparison, protocol gates, and `DecisionFeatures`
  remain generic framework controls.
- V2 interface checking is still operator-class oriented and needs to be
  surface-aware for module-style policy/config/portfolio/construction surfaces.
- V5/V6/V7 are generic when adapter-backed, and adapter-required problem-v1
  packages now fail closed before legacy fallback paths.
- V8 nondeterminism remains generic: adapter-backed checks compare canonical
  adapter artifacts, while objective-only comparison is legacy/no-adapter
  compatibility.
- Protocol/canary runtime audit should receive selected-surface context so
  problem-declared `evidence.required_runtime_fields` can fail closed outside
  the verification-only path.

Implemented policy-preview slice:

- Added generic surface-declared return-value metadata.
- ContractGate C7 now performs conservative static return checks only when the
  surface declares them.
- CVRP declares return constraints for `construction_policy`, `search_policy`,
  and `neighborhood_portfolio`.
- CVRP adapter owns a synthetic in-memory preview hook for policy imports,
  calls, modes, biases, search limits, components, weights, and portfolio
  bounds. This hook does not read raw CVRP data and does not replace
  VerificationGate.
- APS `interface_preview` / `contract_preview` can report adapter-owned preview
  results as tainted advisory observations; they do not affect DecisionEngine or
  protocol thresholds.

Validation:

```text
/home/clawd/miniconda3/envs/claw/bin/python -m pytest scion/scion/tests -q
1410 passed, 1 skipped
```

A three-round real APS/P5 CVRP smoke was then launched:

```text
run_root=/home/clawd/research/scion-experiments/v04-policy-preview-claw-sonnet-20260506T113906Z
model=claude-sonnet-4-6
rounds=3
agentic_proposal=true
python=/home/clawd/miniconda3/envs/claw/bin/python
```

Outcome:

| Rounds | Experiments | Champion | Promotions | Stopped reason |
| ---: | ---: | --- | ---: | --- |
| 3 | 2 | `v1_r0` | 0 | `max_rounds_exhausted` |

Surface coverage:

```text
create_new/route_local: 1
modify/construction_policy: 1
modify/search_policy: 1
```

Interpretation:

- Surface steering remained effective: after the initial no-op route operator,
  Sonnet moved to `construction_policy` and `search_policy`.
- The construction-policy candidate passed contract and verification, reached
  screening, and failed only on `SCREENING_FAIL_WIN_RATE`.
- The search-policy candidate still failed V5 solution consistency.
- The next gate modernization slices should therefore make Verification
  surface-aware and adapter-authoritative while preserving the v3 protocol
  gates unchanged.

## 2026-05-07 Protocol Surface Runtime Audit Gate Slice

Implemented the first gate-modernization follow-up for selected-surface runtime
audit outside Verification:

- `ExperimentProtocol` now stores the active problem spec and accepts
  `selected_surface` for canary and paired experiment execution.
- `EvaluationOrchestrator` carries the active hypothesis locus into
  `EvaluationRequest`; `EvaluationPipeline` forwards it only to protocol
  implementations that both accept `selected_surface` and carry declared
  research-surface metadata.
- Candidate-side canary/screening/validation/frozen runtime audit now calls
  `scion.runtime.audit` with `problem_spec` and `selected_surface`, so
  surface-declared `evidence.required_runtime_fields` fail closed outside the
  verification-only path.
- Champion-side protocol audit remains generic, avoiding false failures when the
  champion workspace does not emit candidate-surface evidence fields.
- CLI and CVRP protocol/campaign smoke construction pass the problem spec into
  `ExperimentProtocol`.

Validation:

```text
/home/clawd/miniconda3/envs/claw/bin/python -m pytest \
  scion/scion/tests/test_protocol.py \
  scion/scion/tests/unit/core/test_evaluation_pipeline.py \
  scion/scion/tests/test_cvrp_protocol_smoke.py \
  scion/scion/tests/test_cvrp_controlled_campaign.py \
  scion/scion/tests/test_sprint_n1.py -q
79 passed in 22.63s

/home/clawd/miniconda3/envs/claw/bin/python -m pytest scion/scion/tests -q
1413 passed, 1 skipped in 45.21s
```

## 2026-05-07 V2/V5 Gate Modernization Closeout

Completed the P0 V2/V5 modernization follow-up:

- V2 interface validation now uses the same AST-only research-surface
  interface validator as ContractGate C7 from the orchestrated
  `VerificationGate` path.
- `VerificationGate.run()` forwards `problem_spec` and explicit or
  hypothesis-derived `selected_surface` into V2, so undeclared surfaces and
  patch targets outside the selected surface fail at `V2_interface`.
- Bridged `ProblemSpecV1` packages now carry generic adapter metadata on the
  legacy runtime `ProblemSpec`: `spec_version`, `adapter_import_path`, and
  `requires_adapter_for_runtime`.
- Adapter-backed problem-v1 packages without an adapter now fail closed at
  `V5_solution_consistency`; the legacy assignment/vehicles fallback remains
  available only for explicit legacy/no-adapter compatibility.
- The implementation stays problem-agnostic: no CVRP or warehouse semantics
  were added to core V2/V5 checks.

Validation:

```text
/home/clawd/miniconda3/envs/claw/bin/python -m pytest scion/scion/tests/test_verification.py scion/scion/tests/unit/test_research_surfaces.py scion/scion/tests/test_problem_bridge.py -q
131 passed in 3.09s

/home/clawd/miniconda3/envs/claw/bin/python -m pytest scion/scion/tests/test_verification.py scion/scion/tests/unit/test_research_surfaces.py scion/scion/tests/unit/test_agentic_proposal_tools.py scion/scion/tests/test_cvrp_adapter.py scion/scion/tests/test_cvrp_solver_operator_runtime.py scion/scion/tests/test_protocol.py scion/scion/tests/unit/core/test_evaluation_pipeline.py scion/scion/tests/unit/core/test_campaign_control_boundaries.py scion/scion/tests/test_cvrp_protocol_smoke.py scion/scion/tests/test_cvrp_controlled_campaign.py scion/scion/tests/test_sprint_n1.py -q
305 passed in 32.75s

/home/clawd/miniconda3/envs/claw/bin/python -m pytest scion/scion/tests -q
1422 passed, 1 skipped in 46.95s
```

## 2026-05-07 V6/V7/V8 Gate Modernization Closeout

Completed the follow-up verification modernization slice:

- Shared generic adapter-required metadata detection across V5/V6/V7/V8.
- V6 feasibility and V7 objective now fail closed for adapter-required
  problem-v1 specs when an adapter is missing, before legacy oracle fallback.
- V7 adapter-backed checks require declared objective metrics to appear in
  both the reported solver objective and adapter recomputation, while auxiliary
  recomputed keys are compared only when both sides report them.
- V8 now accepts an optional adapter and compares adapter-backed canonical
  solver artifact signatures based on normalized solution, filtered objective,
  and feasible flag, with an optional dynamic adapter fingerprint hook.
- Successful V8 comparisons persist bounded comparison mode, selected surface,
  adapter-backed, and equality metadata on `CheckResult` and lineage
  `verification_checks`, not on `DecisionFeatures`.
- Legacy V6/V7 oracle fallback and V8 objective-only comparison remain
  available only for legacy/no-adapter compatibility.
- V8 failure archives now prefer selected-surface target files declared in
  `problem_spec.research_surfaces`, falling back to `operators/`.

Validation:

```text
/home/clawd/miniconda3/envs/claw/bin/python -m pytest scion/scion/tests/test_verification.py scion/scion/tests/test_state_leak.py scion/scion/tests/test_problem_bridge.py -q
98 passed in 2.65s

/home/clawd/miniconda3/envs/claw/bin/python -m pytest scion/scion/tests/test_verification.py scion/scion/tests/unit/test_research_surfaces.py scion/scion/tests/test_protocol.py scion/scion/tests/unit/core/test_evaluation_pipeline.py scion/scion/tests/test_cvrp_adapter.py scion/scion/tests/test_cvrp_solver_operator_runtime.py scion/scion/tests/test_cvrp_protocol_smoke.py scion/scion/tests/test_cvrp_controlled_campaign.py -q
225 passed in 30.06s

/home/clawd/miniconda3/envs/claw/bin/python -m pytest scion/scion/tests -q
1435 passed, 1 skipped in 44.87s
```

## 2026-05-07 Sonnet CVRP Framework Smoke

A detached real Sonnet CVRP formal-path smoke was launched after the
V2-V8 gate modernization commits to validate that the governed APS/protocol
path still reaches real VRP evaluation.

Run root:

```text
/home/clawd/research/scion-experiments/v04-v678-sonnet-vrp-20260507T035528Z
```

Configuration:

```text
scion_commit=a80bd60
model=claude-sonnet-4-6
problem=cvrp formal VRP
rounds=5
agentic_proposal=true
disable_early_stop=true
cvrp_time_limit_sec=10
python=/home/clawd/miniconda3/envs/claw/bin/python
data_root=/home/clawd/research/or-autoresearch-agent/vrp
protocol=scion/scion/problems/cvrp/formal/protocol.yaml
split=scion/scion/problems/cvrp/formal/split_manifest.yaml
seeds=scion/scion/problems/cvrp/formal/seed_ledger.yaml
```

Outcome:

```text
exit_code=0
rounds=5/5
experiments=3
champion=v1
promotions=0
stop=max_rounds_exhausted
active_branches=0
formal_ready=false
final_evidence_refs=missing
```

Delegated post-run audit found:

- The run is valid framework/control evidence, not solver-quality evidence.
- Surface coverage hit `route_local`, `construction_policy`, `search_policy`,
  `neighborhood_portfolio`, and `route_pair`.
- Contract passed for all five candidates.
- Two policy-surface candidates failed `V5_solution_consistency` because
  generated code used nonexistent CVRP instance attributes such as
  `customer_count` before the package exposed it, or `customers`.
- Three candidates reached real VRP screening and failed
  `SCREENING_FAIL_WIN_RATE`; aggregate evidence was tie/no-op dominated:
  64/64 valid pairs, 2 wins, 62 ties, 0 losses, no candidate/champion runtime
  failures, and repo-local `vrp_alns_vns` baseline evidence.
- V8 did not fail and the remaining legacy/no-adapter objective-only V8 path
  did not affect this adapter-backed CVRP run. The useful V8 follow-up was
  auditability: persist bounded successful comparison metadata.
- APS artifacts were structurally healthy, but planner mode was too shallow and
  static preview observations were too large, causing `result_too_large`
  preview observations and misleading self-check failures.

Post-audit repairs completed:

- CVRP policy surfaces now expose safe instance helpers:
  `customer_ids`, `customer_count`, `demands[customer_id]`, `capacity`, and
  `distance(i, j)`, while intentionally keeping `instance.customers` undefined.
- CVRP adapter/problem guidance now tells generated policy code to use those
  helpers and avoid `instance.customers`; preview/runtime audit fails reached
  uses of that nonexistent alias.
- Planner-backed APS now falls back to compact feedback reads instead of
  stopping after only `context.list_surfaces` and `context.read_problem`, and it
  performs a deterministic selected-surface read before code generation or
  partial finalization.
- APS target/schema/contract preview payloads are compact and omit full surface
  payloads and patch `code_content`.
- V8 success checks now persist bounded comparison metadata on `CheckResult`
  and lineage `verification_checks`, not on `DecisionFeatures`.

Validation:

```text
/home/clawd/miniconda3/envs/claw/bin/python -m pytest scion/scion/tests/test_cvrp_solver_operator_runtime.py scion/scion/tests/test_cvrp_adapter.py scion/scion/tests/unit/test_research_surfaces.py -q
85 passed in 7.06s

/home/clawd/miniconda3/envs/claw/bin/python -m pytest scion/scion/tests/unit/test_agentic_proposal_tools.py scion/scion/tests/unit/core/test_proposal_pipeline.py scion/scion/tests/test_contract.py scion/scion/tests/test_cli.py -q
184 passed in 1.49s

/home/clawd/miniconda3/envs/claw/bin/python -m pytest scion/scion/tests/test_verification.py scion/scion/tests/unit/core/test_evidence_recorder.py -q
94 passed in 2.86s

/home/clawd/miniconda3/envs/claw/bin/python -m pytest scion/scion/tests/test_cvrp_solver_operator_runtime.py scion/scion/tests/test_cvrp_adapter.py scion/scion/tests/unit/test_research_surfaces.py scion/scion/tests/unit/test_agentic_proposal_tools.py scion/scion/tests/unit/core/test_proposal_pipeline.py scion/scion/tests/test_contract.py scion/scion/tests/test_cli.py scion/scion/tests/test_verification.py scion/scion/tests/unit/core/test_evidence_recorder.py -q
363 passed in 10.17s

/home/clawd/miniconda3/envs/claw/bin/python -m pytest scion/scion/tests -q
1446 passed, 1 skipped in 48.04s
```

## 2026-05-07 Post-Repair Sonnet CVRP Smoke Audited

A detached real Sonnet CVRP formal-path smoke completed after the CVRP
policy-surface, APS compactness, and V8 auditability repairs.

Run root:

```text
/home/clawd/research/scion-experiments/v04-post-aps-cvrp-sonnet-20260507T083649Z
```

Configuration:

```text
scion_commit=68c33d0
model=claude-sonnet-4-6
problem=cvrp formal VRP
rounds=5
agentic_proposal=true
disable_early_stop=true
cvrp_time_limit_sec=10
python=/home/clawd/miniconda3/envs/claw/bin/python
data_root=/home/clawd/research/or-autoresearch-agent/vrp
protocol=scion/scion/problems/cvrp/formal/protocol.yaml
split=scion/scion/problems/cvrp/formal/split_manifest.yaml
seeds=scion/scion/problems/cvrp/formal/seed_ledger.yaml
```

Outcome:

```text
exit_code=0
rounds=5/5
step_records=5
experiments=4
champion=v1_r0
promotions=0
weight_optimizations=0
stop=max_rounds_exhausted
formal_ready=false
final_evidence_refs=missing
frozen_budget_used=0
frozen_budget_remaining=2
```

Detailed delegated analysis is recorded in:

```text
scion/docs/experiments/v0.4/v0.4-post-aps-cvrp-sonnet-20260507.md
```

Interpretation:

- The run is valid framework/control smoke evidence, not formal solver-quality
  evidence. It was only five rounds, no candidate promoted, no validation or
  frozen stage was reached, and `final_evidence_refs` are absent.
- ContractGate passed 4/5 proposals; the only contract failure was
  `C9c_complexity_bound` on `operators/oropt_intra_route.py` for an uncapped
  while loop.
- Verification and canary are no longer the blocking issue for the tested CVRP
  surfaces: all four candidates that reached them passed both.
- Policy surfaces now clear Contract and Verification in this smoke:
  `construction_policy`, `neighborhood_portfolio`, and `search_policy` all
  reached real VRP screening with no policy/runtime API errors.
- V8 success metadata for policy surfaces is adapter-backed and persisted as
  audit metadata: `comparison_mode=adapter_canonical_signature` and
  `comparison_equal=true`.
- Screening evidence was complete and fail-closed rather than infrastructure
  failed: all 72 candidate/champion pairs were valid, with 0 failed pairs, and
  the real repo-local `vrp_alns_vns` baseline was used.
- All four screened candidates failed `SCREENING_FAIL_WIN_RATE`; no validation
  or frozen stage was reached and no frozen budget was spent.
- The route-local operator candidate remained no-op dominated: 24 attempts, 0
  accepted moves, and `no_improvement_round` on all screening pairs.
- `construction_policy` and `neighborhood_portfolio` cleared runtime audit but
  produced tie-dominated objective evidence; the portfolio candidate had no
  generated registry operators to schedule and stopped as
  `no_registry_operators`.
- `search_policy` produced the strongest nontrivial signal: runtime median
  ratio about `0.842`, median runtime delta about `-1312.5ms`, and mixed
  objective evidence of 2 wins, 1 loss, and 13 ties. It still failed the
  screening win-rate gate.
- APS artifacts remained tainted and digest-backed. A follow-up 3-round Sonnet
  smoke after adding `algorithm_blueprint` showed that APS could list the new
  surface and attempted `context.read_surface {"surface":"algorithm_blueprint"}`,
  but the surface read exceeded the session observation budget, so the agent
  retreated to `route_local` / `search_policy`. That short smoke is control-path
  evidence only, not solver-quality evidence.

## 2026-05-07 Forced Algorithm Blueprint Sonnet Smoke

A detached three-round Sonnet CVRP formal-path smoke was launched with the
diagnostic forced-surface control:

```text
run_root=/home/clawd/research/scion-experiments/v04-forced-blueprint-sonnet-20260507T125015Z
model=claude-sonnet-4-6
problem=cvrp formal VRP path
rounds=3
agentic_proposal=true
disable_early_stop=true
force_surface=algorithm_blueprint
cvrp_time_limit_sec=10
```

The artifacts did not include an explicit exit code, but stdout reported
`Campaign finished`. The summary state was `total_rounds=3`,
`n_experiments=3`, `stopped_reason=max_rounds_exhausted`,
`champion_version=1`, `n_active_branches=0`, `promotions=0`, frozen budget
`0/2`, and `formal_readiness=false` because final evidence refs were missing.

`--force-surface algorithm_blueprint` worked for the first forced hypothesis:
round 1 modified `policies/algorithm_blueprint.py` with
`change_locus=algorithm_blueprint`. It was not an every-round override; rounds
2 and 3 used `route_local` and `construction_policy`.

APS successfully performed the compact selected-surface read for
`algorithm_blueprint`, but compactness is still unresolved. Later
`result_too_large` observations came from other surface reads, and all six APS
sessions ultimately exceeded `max_observation_chars=24000`, affecting both
persisted recovery artifacts and live sessions.

All three evaluated candidates passed Contract, Verification, and canary, then
failed screening by `SCREENING_FAIL_WIN_RATE`. The round-1 blueprint candidate
did activate the top-level algorithm path (`algorithm_blueprint_loaded=true`,
`algorithm_blueprint_active=true`, `algorithm_blueprint_errors=0`) and
exercised `plan_loaded`, `construction_ensemble`, `baseline`, and
`local_search`, but it had `win_rate=0.0`, `median_delta=0.0`, no promotion,
and no validation/frozen evidence.

This is valid control-path evidence that the top-level CVRP
`algorithm_blueprint` surface can be selected, patched, loaded, audited, and
screened through Scion gates. It is not solver-quality evidence. Screening
summaries from that run still lacked full bounded `algorithm_*` audit fields;
that gap has since been addressed in protocol metrics and campaign summary
reporting. `construction_keep_top_k=2` meant the declared `demand_descending`
construction method was not actually tried.

Follow-up APS recovery compactness repair is now in code. Tool observations are
bounded before they are counted or persisted, optional planner
`context.read_surface` calls fail closed when remaining observation budget is
low, and APS-level surface reads are normalized to compact `max_code_chars=1200`
payloads. The replay validator remains fail-closed for genuinely over-budget
artifacts; the repair prevents new artifacts from being written with
`tool_budget_used.observation_chars > max_observation_chars`.

The whole-algorithm surface context repair is also in code: default
`context.read_surface` now returns a compact `surface-contract.v1` section view
instead of duplicating full prompt guidance, `main_search_strategy` compact
reads stay below the legacy 24000-char budget in focused tests, and the APS
default observation cap is 48000 chars. The larger cap is only a bounded
transcript allowance; individual observations still compact/strip raw refs
before APS records them.

Detailed delegated analysis is recorded in
`scion/docs/experiments/v0.4/v0.4-forced-algorithm-blueprint-sonnet-smoke-20260507.md`.

Validation after the recovery compactness repair:

```text
/home/clawd/miniconda3/envs/claw/bin/python -m pytest scion/tests/unit/test_agentic_proposal_tools.py -q
62 passed in 1.07s

/home/clawd/miniconda3/envs/claw/bin/python -m pytest scion/tests/unit/test_agentic_proposal_tools.py scion/tests/unit/core/test_proposal_pipeline.py scion/tests/test_cli.py -q
124 passed in 1.60s

/home/clawd/miniconda3/envs/claw/bin/python -m pytest scion/tests -q
1465 passed, 1 skipped in 49.41s
```

## 2026-05-07 Forced Blueprint Budget Sonnet Smoke

A detached one-round Sonnet CVRP formal-path smoke validated the APS
observation-budget/recovery repair after `af4ab5b Bound APS observation budget
artifacts`.

Run root:

```text
/home/clawd/research/scion-experiments/v04-forced-blueprint-budget-sonnet-20260507T133711Z
```

Configuration:

```text
model=claude-sonnet-4-6
rounds=1
agentic_proposal=true
disable_early_stop=true
force_surface=algorithm_blueprint
cvrp_time_limit_sec=10
```

Outcome:

```text
exit_code=0
total_rounds=1
n_experiments=1
n_steps=1
stop=max_rounds_exhausted
champion=v1_r0
active_branches=0
promotions=0
frozen_budget_used=0
frozen_budget_limit=2
frozen_budget_remaining=2
formal_ready=false
final_evidence_refs=missing
```

The forced surface worked for the evaluated round:
`change_locus=algorithm_blueprint`, `action=modify`, and
`target_file=policies/algorithm_blueprint.py`. Surface coverage recorded
`modify/algorithm_blueprint: 1`, with family coverage
`algorithm_blueprint: 1`.

APS budget/recovery is fixed enough to unblock. The delegated analysis found
no `agentic recovery artifact invalid`,
`tool budget exceeded: observation_chars`, or `result_too_large` matches. The
partial APS session used `23502/24000` observation characters, the completed
session used `23990/24000`, and CLI inspect validated both artifacts with
`validation.ok=true` and `errors=[]`. Compact transcripts still contain
bounded `observation_budget_exhausted` stops, but the sessions did not fail and
the completed session produced a patch. Headroom is therefore very low, but
more compaction is no longer the blocking item.

The first session produced only a partial hypothesis. The second completed
session used the same idempotency key and same hypothesis object, and included
a patch. No explicit `resume_context` or `recovered_partial_hypothesis` was
reported; the behavior was a new APS/code session over the approved
hypothesis, not a semantically fresh proposal.

Contract, Verification, and canary passed. Screening produced 16/16 valid
pairs with 0 failures, `win_rate=0.125`, `median_delta=0.0`, and
`statistical_status=tie`. The candidate was abandoned for
`SCREENING_FAIL_WIN_RATE` / `T4 win_rate < 0.3`. No promotion occurred and no
validation or frozen evidence was produced.

The generated blueprint enabled the algorithm path with
`nearest_neighbor`, `nearest_neighbor_demand_bias`, and `demand_descending`
construction methods, `construction_keep_top_k=2`,
`baseline_time_fraction=0.75`, local search
`intra_route_2opt` / `inter_route_relocate` with `rounds=2` and `top_k=32`,
and restart enabled with `stagnation=8`. The V8 tiny runtime audit showed
`algorithm_blueprint_loaded=true`, `active=true`, `errors=0`, and phases
including `plan_loaded`, `construction_ensemble`, `baseline`, and
`local_search`.

This is valid control-path evidence only. Formal screening raw metrics showed
indirect algorithm-blueprint effects such as `baseline_time_fraction=0.75` and
construction-mode changes, and motivated the reporting refinement that now
copies selected-surface required runtime fields into pair metrics and campaign
summaries.

Detailed delegated analysis is recorded in:

```text
scion/docs/experiments/v0.4/v0.4-forced-blueprint-budget-sonnet-smoke-20260507.md
```

## 2026-05-07 Blueprint Reporting Sonnet 5R VRP Validation

The post-reporting five-round Sonnet CVRP formal VRP validation completed and
is analyzed in:

```text
scion/docs/experiments/v0.4/v0.4-blueprint-reporting-sonnet-5r-20260507.md
```

Run root:

```text
/home/clawd/research/scion-experiments/v04-blueprint-reporting-sonnet-5r-20260507T141342Z
```

Configuration:

```text
scion_commit=278d543
model=claude-sonnet-4-6
problem=cvrp formal VRP
rounds=5
agentic_proposal=true
disable_early_stop=true
force_surface=algorithm_blueprint
cvrp_time_limit_sec=10
python=/home/clawd/miniconda3/envs/claw/bin/python
data_root=/home/clawd/research/or-autoresearch-agent/vrp
```

Outcome:

```text
exit_code=0
rounds=5/5
champion=v1_r0
active_branches=0
promotions=0
frozen_budget_used=0
frozen_budget_remaining=2
formal_ready=false
final_evidence_refs=missing
stop=max_rounds_exhausted
```

Surface coverage:

```text
modify/algorithm_blueprint: 1
create_new/route_local: 1
modify/neighborhood_portfolio: 1
modify/construction_policy: 1
create_new/route_pair: 1
```

Reporting validation result:

- The intended selected-surface reporting path is now validated in real formal
  campaign artifacts.
- Round 1 selected `algorithm_blueprint`; `campaign_summary.json` and the
  round's raw metrics both record
  `selected_surface=algorithm_blueprint`.
- All declared `algorithm_blueprint` required runtime fields were present for
  16/16 candidate-side screening pairs, with `runtime_missing_pairs=0`.
- The candidate had `algorithm_blueprint_loaded=true`,
  `algorithm_blueprint_active=true`, `algorithm_blueprint_errors=0`,
  executed `plan_loaded`, `construction_ensemble`, `baseline`, and
  `local_search`, and preserved the required `algorithm_plan`,
  `algorithm_*` counters, phase deltas, and runtime fields in pair metrics.
- APS artifact validation passed for all ten persisted sessions. Observation
  headroom remains very low, but no invalid recovery artifact,
  `result_too_large`, or observation-budget persistence failure was found.

Solver-quality interpretation:

- This remains control-path evidence, not solver-quality evidence.
- All five candidates passed Contract, Verification, and canary, then failed
  screening with `SCREENING_FAIL_WIN_RATE`.
- The blueprint candidate improved runtime
  (`runtime_ratio_median=0.821`, `runtime_delta_median_ms=-1497.5`) but did
  not improve objective quality enough: pair-level evidence was 1 win, 3
  losses, and 12 ties, collapsing to case-level `win_rate=0.0` and
  `median_delta=0.0`.
- The blueprint local-search phase attempted 192 bounded moves per pair and
  accepted 0. The current package-owned local-search primitives are not
  compensating for the reduced baseline budget.
- Other surfaces were also tie/no-op dominated: route-local had 2 winning
  pairs but no winning cases, neighborhood portfolio and construction policy
  produced all ties, and route-pair produced 0 wins, 1 loss, and 23 ties.

Recommendation:

- Do not launch a long formal solver-quality validation yet.
- The next work should validate the new focused CVRP surface-efficacy slice:
  use `baseline_policy` to expose bounded repo-local `vrp/src` ALNS+VNS
  main-search parameters, then test whether Sonnet can generate nontrivial
  screening behavior through that surface. If it remains tie/no-op dominated,
  follow with deeper problem-owned hooks such as real destroy/repair or
  acceptance/perturbation/restart behavior with declared runtime audit fields.
- Tighten `algorithm_blueprint` guidance so candidates do not trade away
  baseline budget unless the compensating package-owned phase shows accepted
  moves or objective improvement in diagnostic evidence.
- Run another 5-10 round diagnostic only after that slice. Move to a longer
  Sonnet validation once a diagnostic candidate shows nontrivial screening
  quality rather than only speed or no-op/tie evidence.

## 2026-05-07 CVRP Baseline Policy Surface Slice

Implemented the first focused CVRP surface-efficacy slice after the
blueprint-reporting validation:

- Added `baseline_policy` as a problem-owned singleton policy surface in
  `policies/baseline_policy.py`.
- The surface exposes bounded repo-local `vrp/src` ALNS+VNS parameters:
  destroy ratio, ALNS segment length, adaptive reaction factor, VNS toggle,
  VNS no-improvement limit, construction/search threshold gates, and maximum
  destroyed customers.
- The solver loads, validates, clamps, and sanitizes those values before
  passing them into `_solve_with_vrp_baseline()` / `solve_vrp`; defaults
  preserve current baseline behavior.
- Runtime audit emits `baseline_policy_loaded`, `baseline_policy_errors`,
  `baseline_policy_params`, `baseline_destroy_ratio`,
  `baseline_segment_length`, `baseline_reaction_factor`,
  `baseline_use_vns`, `baseline_vns_max_no_improve`,
  `baseline_max_destroy_customers`, and related threshold fields. Selected
  surface audit fails closed when declared fields are missing or
  `baseline_policy_errors` is positive.
- Proposal feedback now includes bounded selected-surface runtime summaries in
  screening/holdout tool payloads and renders compact selected-surface runtime
  notes in hypothesis context, without adding those tainted values to
  `DecisionFeatures`.
- Focused tests include adapter preview/rendering, ContractGate interface
  checks, runtime audit defaults/failures, and a fake repo-local `vrp/src`
  baseline proving modified policy values are passed as baseline kwargs.

Validation:

```text
/home/clawd/miniconda3/envs/claw/bin/python -m pytest scion/scion/tests/test_cvrp_adapter.py scion/scion/tests/test_cvrp_solver_operator_runtime.py scion/scion/tests/unit/test_research_surfaces.py -q
101 passed in 8.28s

/home/clawd/miniconda3/envs/claw/bin/python -m pytest scion/scion/tests/test_cvrp_adapter.py scion/scion/tests/test_cvrp_solver_operator_runtime.py scion/scion/tests/unit/test_research_surfaces.py scion/scion/tests/unit/test_agentic_proposal_tools.py -q
163 passed in 8.92s
```

This is implementation/control readiness, not solver-quality evidence. The
first short Sonnet diagnostic for `baseline_policy` has since completed and is
recorded below; it validated runtime/audit plumbing but did not show enough
screening quality to justify a long solver-quality validation.

## 2026-05-07 Baseline Policy Sonnet Diagnostic Audited

A detached three-round Sonnet CVRP formal-path diagnostic completed to test the
new `baseline_policy` surface:

```text
run_root=/home/clawd/research/scion-experiments/v04-baseline-policy-sonnet-3r-20260507T153355Z
scion_commit=605cfa5
model=claude-sonnet-4-6
problem=cvrp formal VRP
rounds=3
agentic_proposal=true
disable_early_stop=true
force_surface=baseline_policy
cvrp_time_limit_sec=10
python=/home/clawd/miniconda3/envs/claw/bin/python
data_root=/home/clawd/research/or-autoresearch-agent/vrp
started_utc=2026-05-07T15:33:55Z
ended_utc=2026-05-07T15:52:56Z
exit_code=0
```

Outcome:

```text
rounds=3/3
experiments=3
steps=3
champion=v1
weight_revision=0
promotions=0
frozen_budget_used=0
frozen_budget_limit=2
frozen_budget_remaining=2
formal_ready=false
final_evidence_refs=missing
stop=max_rounds_exhausted
```

Detailed delegated analysis is recorded in:

```text
scion/docs/experiments/v0.4/v0.4-baseline-policy-sonnet-3r-20260507.md
```

Interpretation:

- This is valid implementation/control evidence, not solver-quality evidence.
- Round 1 selected `baseline_policy`, modified
  `policies/baseline_policy.py`, passed Contract, Verification, and canary,
  and reached formal screening.
- The selected-surface runtime audit was complete for all 16 candidate-side
  screening pairs: `baseline_policy_loaded=true`,
  `baseline_policy_errors=0`, and all declared `baseline_*` parameter fields
  were present. The raw metrics also recorded the repo-local
  `vrp_alns_vns` baseline path with `baseline_required=true`.
- The candidate produced weak pair-level movement but failed case-level
  screening: 4 wins, 2 losses, 10 ties at pair level, case-level
  `win_rate=0.125`, `median_delta=0.0`, and median runtime ratio about
  `0.9997`.
- The launched `--force-surface baseline_policy` control did not hold across
  all three rounds. Round 2 moved to `route_local` and round 3 moved to
  `algorithm_blueprint`; both also failed screening with tie/no-op dominated
  evidence.
- APS artifacts were sufficient to produce governed candidates, but not clean:
  each completed session used the full 9/9 tool-call budget, `result_too_large`
  appeared repeatedly, and contract previews were skipped because the tool loop
  was exhausted. Deterministic Contract/Verification/canary still passed, so
  the final blocker was screening quality, not gate validity.

Next step: rerun a tightly forced `main_search_strategy` diagnostic before
treating further CVRP runs as solver-quality evidence. Singleton semantic
novelty now has a code-level repair: `main_search_strategy` and other singleton
policy/config surfaces can carry structured `novelty_signature` identity, and
missing structured identity does not collapse all later attempts by target
file. APS compact surface reads are also repaired in code.

## 2026-05-08 Main Search Strategy Governance Repair And Diagnostic Audited

Implemented the whole-algorithm CVRP surface and repaired the diagnostic
controls needed to test it cleanly:

- Added `main_search_strategy` as a problem-owned singleton surface in
  `policies/main_search_strategy.py`.
- Enabled valid plans can take over the CVRP algorithm slice through bounded
  construction, repo-local baseline budget/params, package-owned main-loop
  components (`route_pair_swap` and `bounded_destroy_repair`),
  acceptance/restart/perturbation controls, and optional registry operators.
- `--force-surface <surface>` is now a persistent diagnostic proposal
  constraint across proposal rounds, not a one-shot plateau/diversification
  hint.
- Selected-surface runtime audit now treats declared `*_active` fields like
  `*_loaded` and `*_executed`: they must be truthy. This prevents selected
  `main_search_strategy` candidates from returning inactive plans while still
  passing runtime audit.
- Contract governance now blocks common file-read APIs (`open()`,
  `*.open()`, `*.read_text()`, `*.read_bytes()`) and blocks direct
  `instance.name` / `getattr(instance, "name")` / `hasattr(instance, "name")`
  probes on non-operator and singleton surfaces before candidate code runs.
- `proposal.interface_preview` now requires full ContractGate success before
  executing problem-owned preview hooks.

Validation:

```text
/home/clawd/miniconda3/envs/claw/bin/python -m pytest scion/scion/tests -q
1495 passed, 1 skipped in 53.50s
```

A detached three-round Sonnet CVRP formal-path diagnostic completed:

```text
run_root=/home/clawd/research/scion-experiments/v04-main-search-strategy-sonnet-3r-20260508T133838Z
scion_commit=45e2be9
worktree_dirty=true
model=claude-sonnet-4-6
problem=cvrp formal VRP
rounds=3
agentic_proposal=true
disable_early_stop=true
force_surface=main_search_strategy
cvrp_time_limit_sec=10
python=/home/clawd/miniconda3/envs/claw/bin/python
data_root=/home/clawd/research/or-autoresearch-agent/vrp
started_utc=2026-05-08T13:38:38Z
ended_utc=2026-05-08T13:45:29Z
exit_code=0
```

Outcome:

```text
rounds=3/3
steps=3
experiments=1
champion=v1
weight_revision=0
promotions=0
frozen_budget_used=0
frozen_budget_limit=2
frozen_budget_remaining=2
formal_ready=false
final_evidence_refs=missing
stop=max_rounds_exhausted
```

Detailed delegated analysis is recorded in:

```text
scion/docs/experiments/v0.4/v0.4-main-search-strategy-sonnet-3r-20260508.md
```

Interpretation:

- This is valid control-path and whole-algorithm surface plumbing evidence,
  not solver-quality evidence.
- Persistent `--force-surface main_search_strategy` worked: all three
  campaign step hypotheses used `change_locus=main_search_strategy`,
  `action=modify`, and `target_file=policies/main_search_strategy.py`.
- Round 1 passed Contract, Verification, and canary, selected and activated
  `main_search_strategy`, and reached formal screening.
- Selected-surface runtime audit was complete for the 16 candidate-side
  screening pairs: 27 required runtime fields present, missing pairs `0`,
  `main_search_strategy_loaded=true`,
  `main_search_strategy_active=true`, and
  `main_search_strategy_errors=0`.
- The evaluated plan executed `plan_loaded`, `construction`, `baseline`,
  `improvement_loop`, and `perturbation`, disabled post-baseline registry
  operators, and ran inside the problem-owned main-search path.
- The evaluated plan only exercised `intra_route_2opt` and
  `inter_route_relocate`: 944 attempts each, with 20 and 2 accepted moves
  respectively. It did not exercise `route_pair_swap` or
  `bounded_destroy_repair`.
- Screening produced nonzero but insufficient signal: 4 wins, 2 losses, and
  10 ties at pair level; case-level `win_rate=0.25`; `median_delta=0.0`;
  median runtime ratio about `0.9413`; no validation/frozen/promote.
- Rounds 2 and 3 were not surface drift. They stayed on
  `main_search_strategy` but failed Contract at `C10_novelty` as duplicate
  hypotheses, so only one candidate was evaluated.
- At run time, APS artifacts were the bottleneck for this large surface:
  `context.read_surface(main_search_strategy)` produced repeated
  `result_too_large`, all sessions used 9/9 tool calls, observation budget was
  near 24k, and only one of four sessions completed.

Do not expand directly to 5-10 rounds without another smoke check. The APS
surface-context blocker is repaired in code: default compact
`context.read_surface(main_search_strategy)` no longer returns prompt-block
duplicates and stays under the legacy 24k budget in focused tests. The C10
singleton semantic novelty blocker has also been repaired in code: distinct
structured strategy identities are no longer rejected merely because they edit
`policies/main_search_strategy.py`. The next run should verify that multiple
distinct `main_search_strategy` candidates can now reach screening and that the
problem-owned route-pair-swap / bounded destroy-repair components are actually
selected by candidate plans.

## 2026-05-08 Clean Main Search Strategy Diagnostic Audited

A detached three-round Sonnet CVRP formal-path diagnostic completed after the
singleton novelty and APS compact surface-read repairs:

```text
run_root=/home/clawd/research/scion-experiments/v04-main-search-strategy-sonnet-3r-20260508T142513Z
scion_commit=b98196b
worktree_dirty=false
model=claude-sonnet-4-6
problem=cvrp formal VRP
rounds=3
agentic_proposal=true
disable_early_stop=true
force_surface=main_search_strategy
cvrp_time_limit_sec=10
python=/home/clawd/miniconda3/envs/claw/bin/python
data_root=/home/clawd/research/or-autoresearch-agent/vrp
started_utc=2026-05-08T14:25:13Z
ended_utc=2026-05-08T14:42:29Z
exit_code=0
```

Outcome:

```text
rounds=3/3
steps=3
experiments=3
champion=v1
weight_revision=0
promotions=0
frozen_budget_used=0
frozen_budget_limit=2
frozen_budget_remaining=2
formal_ready=false
final_evidence_refs=missing
stop=max_rounds_exhausted
```

Detailed delegated analysis is recorded in:

```text
scion/docs/experiments/v0.4/v0.4-main-search-strategy-clean-sonnet-3r-20260508.md
```

Interpretation:

- This is valid control-path evidence for the C10 and APS compact-read repairs,
  not solver-quality evidence.
- Persistent `--force-surface main_search_strategy` worked for all three
  rounds: coverage was `modify/main_search_strategy: 3`.
- C10 singleton semantic novelty no longer blocked follow-up hypotheses. All
  three rounds passed Contract, Verification, and canary, then reached formal
  screening.
- `main_search_strategy` selected-surface audit was complete in every screened
  candidate: `loaded=true`, `active=true`, `errors=0`, and all 27 required
  runtime fields present for all 16 candidate-side pairs per round.
- APS compact selected-surface reads worked: every session read
  `main_search_strategy` successfully, and the remaining `result_too_large`
  events came from optional reads guarded by remaining observation budget.
- Screening remained negative and tie-dominated:
  round 1 pair W/L/T `1/1/14`, case `win_rate=0.0`;
  round 2 `1/2/13`, `win_rate=0.0`;
  round 3 `3/3/10`, `win_rate=0.125`. No validation/frozen/promote.
- The candidates still did not select the deeper components
  `route_pair_swap` or `bounded_destroy_repair`; evaluated plans used only
  `intra_route_2opt` and/or `inter_route_relocate`.

Remaining question: whether Sonnet can select and use the deeper problem-owned
main-search components through `main_search_strategy`, and whether those
components can produce objective improvement on formal cases.

## 2026-05-09 Core/CVRP Gap Audit

A read-only audit separated four objects that should not be conflated:
Architecture v3, Scion core framework code, the CVRP Scion problem package, and
the original `vrp/` baseline solver. The audit is recorded in:

```text
scion/docs/audits/v0.4/v0.4-core-cvrp-gap-audit-20260509.md
```

Interpretation:

- v0.4 has not violated the v3 architecture. LLM outputs remain tainted,
  Contract / Verification / Protocol / Decision remain separate, and
  `DecisionEngine` does not directly read proposal free text.
- The current blocker is not that Scion cannot connect to CVRP. The CVRP
  package is a valid Scion-native integration object, but not yet a strong
  research object: the deepest algorithm levers from the original `vrp`
  baseline are only partially exposed through bounded surfaces and runtime
  telemetry.
- The original `vrp` baseline's high-leverage structure is construction,
  adaptive ALNS destroy/repair, VNS portfolio, simulated-annealing acceptance,
  thresholds, and adaptive weights. v0.4 should map these manually into the
  CVRP problem package; v0.5 should generalize that mapping as onboarding.
- Do not run a long CVRP solver-quality validation until a short forced
  diagnostic proves that deep components are selected, attempted, audited, and
  produce nontrivial screening quality.

Core governance findings to fix before v0.4 closeout:

- C10 semantic novelty still has a free-text fallback for singleton surfaces
  when structured signature fields are unavailable.
- Patch-level ContractGate checks should use the approved selected surface
  rather than re-inferring surfaces from patch target paths.
- Lineage should persist the actual schema-versioned `DecisionFeatures`
  snapshot used by `DecisionEngine`, not a reconstructed metadata subset.
- Soft-abandon should either live inside `DecisionEngine` or be represented as
  an explicit coordinated decision with independent reason-code provenance.
- Proposal context should stop hardcoding CVRP/ALNS runtime field names and
  use problem/surface-declared feedback metadata instead.
- If `main_search_strategy` is the v0.4 closeout surface, core needs either a
  minimal nested-plan return contract extension or a problem-owned static
  validator hook; broad surface-schema generalization belongs in v0.5.

CVRP problem-package findings to address before another long run:

- `main_search_strategy` needs a problem-owned component-coverage contract for
  diagnostics, with selected / attempted / accepted / skipped-reason telemetry.
- `route_pair_swap` and `bounded_destroy_repair` should be strengthened or
  remapped to the original baseline's real VNS/ALNS components.
- Controlled fixtures should prove route-pair swap and bounded destroy/repair
  can improve known cases before formal screening is used to judge them.

## 2026-05-09 Core Governance And CVRP Deep-Surface Repair

Implemented the immediate repair slice identified by the Core/CVRP gap audit:

- C10 singleton semantic novelty no longer uses hypothesis free text as a
  fallback identity. If a semantic singleton surface lacks usable structured
  signature fields, duplicate detection falls back to strict
  locus/action/target-file identity.
- Patch-level ContractGate checks now use the approved selected surface for
  C7 interface validation, C9d instance-identity checks, and C9c complexity
  scale terms. Explicit selected-surface/target mismatches fail closed.
- APS contract/interface previews now pass the selected surface consistently
  with the formal ContractGate path.
- CVRP `main_search_strategy` now emits component-coverage telemetry:
  selected, attempted, accepted, skipped components, skip reasons, best deltas,
  improvement counts, and bounded destroy/repair remove/reinsert counts.
- CVRP route-pair swap now ranks bounded route-pair/customer swap candidates
  before applying `top_k`.
- CVRP bounded destroy/repair now uses a bounded worst-removal plus
  regret-2/cheapest-insertion style repair subset instead of single-customer
  remove/reinsert only.
- Controlled runtime tests now prove `route_pair_swap` and
  `bounded_destroy_repair` can be selected, attempted, accepted, and audited on
  small constructed cases.

Validation:

```text
/home/clawd/miniconda3/envs/claw/bin/python -m pytest scion/scion/tests/unit/test_research_surfaces.py scion/scion/tests/unit/test_agentic_proposal_tools.py scion/scion/tests/test_contract.py -q
205 passed in 2.17s

/home/clawd/miniconda3/envs/claw/bin/python -m pytest scion/scion/tests/test_cvrp_solver_operator_runtime.py scion/scion/tests/test_cvrp_protocol_smoke.py scion/scion/tests/test_cvrp_adapter.py -q
65 passed in 20.27s

/home/clawd/miniconda3/envs/claw/bin/python -m pytest scion/scion/tests/test_verification.py scion/scion/tests/unit/test_research_surfaces.py scion/scion/tests/unit/test_agentic_proposal_tools.py scion/scion/tests/test_contract.py scion/scion/tests/test_cvrp_adapter.py scion/scion/tests/test_cvrp_solver_operator_runtime.py scion/scion/tests/test_protocol.py scion/scion/tests/unit/core/test_evaluation_pipeline.py scion/scion/tests/test_cvrp_protocol_smoke.py scion/scion/tests/test_cvrp_controlled_campaign.py -q
414 passed in 40.13s

/home/clawd/miniconda3/envs/claw/bin/python -m pytest scion/scion/tests -q
1508 passed, 1 skipped in 54.78s
```

## 2026-05-09 Main Search Surface Repair Smoke Audited

A detached two-round Sonnet CVRP formal-path smoke completed after the core
governance and CVRP deep-surface repair:

```text
run_root=/home/clawd/research/scion-experiments/v04-main-search-surface-repair-sonnet-2r-20260509T133405Z
scion_commit=e25680a
worktree_dirty=false
model=claude-sonnet-4-6
problem=cvrp formal VRP
rounds=2
agentic_proposal=true
disable_early_stop=true
force_surface=main_search_strategy
cvrp_time_limit_sec=10
python=/home/clawd/miniconda3/envs/claw/bin/python
data_root=/home/clawd/research/or-autoresearch-agent/vrp
exit_code=0
```

Detailed delegated raw-artifact analysis is recorded in:

```text
scion/docs/experiments/v0.4/v0.4-main-search-surface-repair-sonnet-2r-20260509.md
```

Outcome:

```text
rounds=2/2
steps=2
experiments=1
champion=v1
promotions=0
frozen_budget_used=0
frozen_budget_limit=2
frozen_budget_remaining=2
formal_ready=false
final_evidence_refs=missing
stop=max_rounds_exhausted
```

Interpretation:

- Persistent `--force-surface main_search_strategy` held for both hypotheses.
- Round 1 passed Contract, Verification, and canary, activated
  `main_search_strategy`, reached formal screening, then failed
  `SCREENING_FAIL_WIN_RATE`.
- Round 2 stayed on `main_search_strategy` but failed hypothesis Contract at
  `C10_novelty` duplicate, so only one candidate reached screening.
- Selected-surface runtime audit was complete for the evaluated candidate:
  16/16 candidate-side pairs had `main_search_strategy_loaded=true`,
  `main_search_strategy_active=true`, `main_search_strategy_errors=0`, and
  all 34 required runtime fields present.
- The new component telemetry path worked, but the deep components still were
  not selected: `route_pair_swap` and `bounded_destroy_repair` both had
  selected/attempted/accepted counts of zero. The candidate used
  `intra_route_2opt` and `inter_route_relocate`; 2-opt produced accepted moves,
  relocate did not.
- Screening had nontrivial but insufficient signal: 4 pair wins, 2 pair losses,
  10 ties, case-level `win_rate=0.125`, `median_delta=0.0`, and median runtime
  ratio about `0.9412`.
- APS artifacts were usable but still under pressure: one completed session,
  two partial hypothesis sessions, no invalid recovery artifact, no observation
  budget exhaustion, and bounded `result_too_large` events on optional surface
  reads.

This is valid control-path evidence for selected-surface audit and telemetry,
not solver-quality evidence. The run does not satisfy the long-validation
condition because the intended deep components were not selected or attempted.
The next v0.4 slice should make deep component use explicit in forced
`main_search_strategy` diagnostics and investigate why the second forced
hypothesis still collapsed to `C10_novelty` duplicate.

## 2026-05-09 Deep Component Diagnostic Coverage Slice

Implemented the next, stronger optimization slice after the two-round
post-repair smoke:

- Forced semantic singleton surface context now renders declared
  `novelty.signature_fields`, occupied structured signatures for the selected
  surface, and explicit guidance that free-text hypothesis prose is not novelty
  identity.
- APS draft/schema/contract preview reports missing structured semantic
  identity early for `semantic_signature` surfaces, before a later C10 duplicate
  failure.
- C10 duplicate details now distinguish duplicate structured
  `novelty_signature` values from fallback strict locus/action/target-file
  duplicates caused by missing structured identity.
- CVRP `main_search_strategy` metadata now makes forced diagnostic
  deep-component coverage explicit: candidates should select
  `route_pair_swap` and `bounded_destroy_repair`, use 5 improvement rounds, and
  carry structured novelty fields such as selected/deep components, budget
  pattern, and destroy/repair pattern.
- CVRP adapter preview adds a problem-owned diagnostic advisory when an enabled
  `main_search_strategy` plan omits either deep component. This is not a normal
  promotion hard fail.
- CVRP runtime audit now emits `main_search_component_coverage_status` and
  `main_search_deep_components_selected`, so summaries can distinguish
  inactive, missing deep components, selected-but-not-attempted, and attempted
  deep-component coverage.

Validation:

```text
/home/clawd/miniconda3/envs/claw/bin/python -m pytest scion/scion/tests/unit/test_agentic_proposal_tools.py scion/scion/tests/unit/test_research_surfaces.py scion/scion/tests/test_contract.py scion/scion/tests/unit/core/test_proposal_pipeline.py scion/scion/tests/test_cvrp_adapter.py scion/scion/tests/test_cvrp_solver_operator_runtime.py -q
294 passed in 13.28s

/home/clawd/miniconda3/envs/claw/bin/python -m pytest scion/scion/tests/test_verification.py scion/scion/tests/unit/test_research_surfaces.py scion/scion/tests/unit/test_agentic_proposal_tools.py scion/scion/tests/test_contract.py scion/scion/tests/test_cvrp_adapter.py scion/scion/tests/test_cvrp_solver_operator_runtime.py scion/scion/tests/test_protocol.py scion/scion/tests/unit/core/test_evaluation_pipeline.py scion/scion/tests/test_cvrp_protocol_smoke.py scion/scion/tests/test_cvrp_controlled_campaign.py scion/scion/tests/unit/core/test_proposal_pipeline.py -q
444 passed in 42.09s

/home/clawd/miniconda3/envs/claw/bin/python -m pytest scion/scion/tests -q
1511 passed, 1 skipped in 56.68s
```

Next step: commit this slice and run a five-round forced
`main_search_strategy` smoke. The smoke should be judged first on whether
`main_search_component_coverage_status.status` reaches
`deep_components_attempted`, with both `route_pair_swap` and
`bounded_destroy_repair` present in selected/attempted component telemetry.
Only if that holds and screening remains nontrivial should longer validation be
considered.

## 2026-05-09 Main Search Deep Diagnostic 5R Smoke Audited

A detached five-round Sonnet CVRP formal-path smoke completed after the deep
component diagnostic coverage slice:

```text
run_root=/home/clawd/research/scion-experiments/v04-main-search-deep-diagnostic-sonnet-5r-20260509T150855Z
scion_commit=114727e
worktree_dirty=false
model=claude-sonnet-4-6
problem=cvrp formal VRP
rounds=5
agentic_proposal=true
disable_early_stop=true
force_surface=main_search_strategy
cvrp_time_limit_sec=10
python=/home/clawd/miniconda3/envs/claw/bin/python
data_root=/home/clawd/research/or-autoresearch-agent/vrp
exit_code=0
```

Detailed delegated raw-artifact analysis is recorded in:

```text
scion/docs/experiments/v0.4/v0.4-main-search-deep-diagnostic-sonnet-5r-20260509.md
```

Outcome:

```text
rounds=5/5
steps=5
experiments=5
screened_candidates=4
verification_failed_candidates=1
promotions=0
frozen_budget_used=0
formal_ready=false
final_evidence_refs=missing
stop=max_rounds_exhausted
```

Interpretation:

- Persistent `--force-surface main_search_strategy` held for all five rounds.
- C10 was no longer the blocker: all five hypotheses carried structured
  `novelty_signature` values and no C10 rejection occurred.
- Four candidates passed Contract, Verification, canary, and reached screening.
  One candidate failed heavy verification at `V5_solution_consistency` because
  selected-surface runtime audit reported missing
  `main_search_deep_components_selected`.
- The intended deep-component coverage target was reached for all screened
  candidates: `main_search_component_coverage_status.status` was
  `deep_components_attempted` for 16/16 candidate-side pairs in each screened
  round.
- `route_pair_swap` was selected, attempted, and accepted in rounds 1, 4, and
  5. `bounded_destroy_repair` was selected and attempted in all screened
  rounds, but accepted zero moves; its dominant skip reason was
  `repair_budget_exhausted`.
- Screening remained insufficient: the four screened candidates had case-level
  win rates `0.125`, `0.0`, `0.125`, and `0.25`, with `median_delta=0.0` in
  every round. All failed `SCREENING_FAIL_WIN_RATE`.
- APS remained usable but budget pressured: 10 sessions, 5 completed, 5
  partial hypothesis sessions, no invalid recovery artifacts, selected-surface
  reads succeeded 10/10, and bounded `result_too_large` observations still
  occurred on optional surface reads.

This is valid evidence that the forced diagnostic can now drive deep-component
selection and runtime audit. It is not solver-quality evidence and should not
trigger long validation. The next optimization target is
`bounded_destroy_repair` efficacy: it must produce accepted moves under formal
budgeted search before the run can support a longer validation.

## 2026-05-09 Bounded Destroy/Repair Efficacy Slice

Implemented the next CVRP problem-package repair after the 5R deep diagnostic:

- `bounded_destroy_repair` no longer lets the first removed customer consume
  the whole `top_k` repair budget.
- Regret/cheapest insertion repair now splits bounded candidate budget across
  pending customers.
- When multi-customer repair fails or produces no improvement, the component
  can spend remaining budget on smaller bounded destroy subsets before giving
  up.
- Runtime telemetry now records
  `main_search_component_repair_fallback_counts` alongside removed and
  reinserted counts.
- Skip reasons now distinguish budget exhaustion, infeasible insertion, and
  repaired candidates that produced no improvement.
- CVRP surface guidance and adapter preview recommend 5 improvement rounds and
  `top_k` 64 or 128 for forced destroy/repair diagnostics.
- A formal-like controlled regression now proves `bounded_destroy_repair` can
  be selected, attempted, accepted, and audited under `rounds=5, top_k=64`.

Validation:

```text
/home/clawd/miniconda3/envs/claw/bin/python -m pytest scion/scion/tests/test_cvrp_solver_operator_runtime.py scion/scion/tests/test_cvrp_adapter.py scion/scion/tests/unit/test_research_surfaces.py -q
130 passed in 11.28s

/home/clawd/miniconda3/envs/claw/bin/python -m pytest scion/scion/tests/test_verification.py scion/scion/tests/unit/test_research_surfaces.py scion/scion/tests/unit/test_agentic_proposal_tools.py scion/scion/tests/test_contract.py scion/scion/tests/test_cvrp_adapter.py scion/scion/tests/test_cvrp_solver_operator_runtime.py scion/scion/tests/test_protocol.py scion/scion/tests/unit/core/test_evaluation_pipeline.py scion/scion/tests/test_cvrp_protocol_smoke.py scion/scion/tests/test_cvrp_controlled_campaign.py -q
418 passed in 40.81s

/home/clawd/miniconda3/envs/claw/bin/python -m pytest scion/scion/tests -q
1512 passed, 1 skipped in 56.46s
```

Next step: commit this slice and run another five-round forced
`main_search_strategy` smoke. The first acceptance condition is no longer just
deep selected/attempted; it is that `bounded_destroy_repair` produces accepted
moves in formal screening pairs, while selected-surface audit remains complete.

## 2026-05-09 Bounded Destroy/Repair 5R Smoke Audited

A detached five-round Sonnet CVRP formal-path smoke completed after the
bounded destroy/repair efficacy slice:

```text
run_root=/home/clawd/research/scion-experiments/v04-bounded-destroy-repair-sonnet-5r-20260509T160637Z
scion_commit=8a37fd6
worktree_dirty=false
model=claude-sonnet-4-6
problem=cvrp formal VRP
rounds=5
agentic_proposal=true
disable_early_stop=true
force_surface=main_search_strategy
cvrp_time_limit_sec=10
python=/home/clawd/miniconda3/envs/claw/bin/python
data_root=/home/clawd/research/or-autoresearch-agent/vrp
exit_code=0
```

Detailed delegated raw-artifact analysis is recorded in:

```text
scion/docs/experiments/v0.4/v0.4-bounded-destroy-repair-sonnet-5r-20260509.md
```

Outcome:

```text
rounds=5/5
steps=5
experiments=4
screened_candidates=4
verification_failed_candidates=1
promotions=0
frozen_budget_used=0
formal_ready=false
final_evidence_refs=missing
stop=max_rounds_exhausted
```

Interpretation:

- Persistent `--force-surface main_search_strategy` held for all five rounds.
- C10 remained healthy: all five hypotheses carried structured novelty
  signatures and no C10 rejection occurred.
- Four candidates passed Contract, Verification, canary, and reached screening.
  One candidate failed verification because selected-surface runtime audit was
  incomplete and the strategy did not activate cleanly.
- Screening runtime audit was complete in the four screened candidates,
  including `main_search_component_coverage_status`,
  `main_search_deep_components_selected`, and
  `main_search_component_repair_fallback_counts`.
- `bounded_destroy_repair` improved from the previous smoke: round 5 selected
  and attempted it, accepted 21 moves, recorded positive best deltas in 12/16
  pairs, and used 157 repair fallbacks. The dominant skip reason shifted to
  `repair_produced_no_improvement` instead of `repair_budget_exhausted`.
- Rounds 2 and 4 did not select `bounded_destroy_repair`, so forced diagnostic
  guidance still does not guarantee every candidate exercises the repaired
  component.
- Screening quality remained insufficient. The four screened candidates had
  case-level win rates `0.25`, `0.125`, `0.0`, and `0.125`; all failed
  `SCREENING_FAIL_WIN_RATE`, and none reached validation/frozen/promotion.

This validates local component repair, not solver-quality improvement. The
next optimization target is net case-level efficacy: accepted route-pair and
destroy/repair moves must translate into stronger case-level wins rather than
mixed pair-level movement.

## 2026-05-09 Main-Search Net-Benefit Guard Slice

Implemented the next stronger CVRP problem-package repair after the bounded
destroy/repair smoke:

- Active `main_search_strategy` formal-like `.vrp` runs now apply a
  problem-owned baseline quality guard: effective baseline time fraction is at
  least `0.75`, and runtime records
  `main_search_baseline_time_fraction_effective` plus
  `main_search_baseline_quality_guard_applied`.
- Active main-search baseline params are conservatively clamped to avoid the
  aggressive R5 pattern that degraded baseline quality: destroy-ratio high cap,
  segment-length cap, reaction-factor floor, VNS no-improvement cap, and
  customer-count-scaled `max_destroy_customers`. Runtime records
  `main_search_baseline_params_clamped` and
  `main_search_baseline_param_clamps`.
- `bounded_destroy_repair` now has a problem-owned positive distance
  improvement floor and per-search accepted-move cap. Runtime records
  per-component minimum improvement and the destroy/repair accept limit.
- If `route_pair_swap` already improves the same round, bounded
  destroy/repair can be gated off with an audited
  `route_pair_phase_improved` skip reason.
- The main search loop explicitly returns the phase-best solution and records
  `main_search_best_returned`, preventing later perturbation/current-state
  movement from degrading the returned candidate.
- Adapter preview and surface guidance now recommend R1-like safe defaults:
  baseline fraction around `0.75`, conservative ALNS/VNS params, route-pair
  before bounded destroy/repair, 5 rounds, `top_k=64`, perturbation strength
  `2-3`, and max perturbations `2`.

Validation:

```text
/home/clawd/miniconda3/envs/claw/bin/python -m pytest scion/scion/tests/test_cvrp_solver_operator_runtime.py scion/scion/tests/test_cvrp_adapter.py scion/scion/tests/unit/test_research_surfaces.py -q
134 passed in 11.77s

/home/clawd/miniconda3/envs/claw/bin/python -m pytest scion/scion/tests/test_verification.py scion/scion/tests/unit/test_research_surfaces.py scion/scion/tests/unit/test_agentic_proposal_tools.py scion/scion/tests/test_contract.py scion/scion/tests/test_cvrp_adapter.py scion/scion/tests/test_cvrp_solver_operator_runtime.py scion/scion/tests/test_protocol.py scion/scion/tests/unit/core/test_evaluation_pipeline.py scion/scion/tests/test_cvrp_protocol_smoke.py scion/scion/tests/test_cvrp_controlled_campaign.py -q
422 passed in 43.72s

/home/clawd/miniconda3/envs/claw/bin/python -m pytest scion/scion/tests -q
1516 passed, 1 skipped in 56.54s
```

Next step: commit this slice and run another five-round forced
`main_search_strategy` smoke. The acceptance condition is improved net
case-level outcome, not merely accepted component moves: screening should move
beyond the previous `0.0` to `0.25` case-level win-rate range while preserving
complete selected-surface runtime audit.

## 2026-05-09 Main-Search Net-Benefit 5R Smoke Audited

A detached five-round Sonnet CVRP formal-path smoke completed after the
main-search net-benefit guard slice:

```text
run_root=/home/clawd/research/scion-experiments/v04-main-search-net-benefit-sonnet-5r-20260509T165217Z
scion_commit=8d49abe
worktree_dirty=false
model=claude-sonnet-4-6
problem=cvrp formal VRP
rounds=5
agentic_proposal=true
disable_early_stop=true
force_surface=main_search_strategy
cvrp_time_limit_sec=10
python=/home/clawd/miniconda3/envs/claw/bin/python
data_root=/home/clawd/research/or-autoresearch-agent/vrp
exit_code=0
```

Detailed delegated raw-artifact analysis is recorded in:

```text
scion/docs/experiments/v0.4/v0.4-main-search-net-benefit-sonnet-5r-20260509.md
```

Outcome:

```text
rounds=5/5
steps=5
experiments=3
screened_candidates=3
verification_failed_candidates=2
promotions=0
frozen_budget_used=0
formal_ready=false
final_evidence_refs=missing
stop=max_rounds_exhausted
```

Interpretation:

- This is valid short diagnostic evidence, not solver-quality evidence.
- The run finished normally, but persistent `--force-surface
  main_search_strategy` did not hold for every proposal: coverage was
  `modify/main_search_strategy: 4` and `create_new/route_local: 1`. Round 4
  drifted to `operators/oropt_intra_route.py`, which should not happen in a
  forced main-search diagnostic.
- Delegated APS trace analysis found that the drift happened in the hypothesis
  phase. Command/launch artifacts carried `force_surface=main_search_strategy`,
  but the hypothesis task and tool context still allowed all declared surfaces;
  the code phase then implemented the approved off-surface `route_local`
  hypothesis.
- APS behavior was shallow relative to the intended research loop: sessions
  mostly used problem/surface reads and did not call memory or
  screening/runtime feedback tools in the analyzed artifacts.
- C10 was healthy; no novelty rejection blocked the run.
- Three candidates passed Contract, Verification, canary, and reached
  screening; all failed `SCREENING_FAIL_WIN_RATE`.
- Two main-search candidates failed verification at `V5_solution_consistency`
  because selected-surface runtime audit found empty
  `main_search_baseline_param_clamps`. The deeper analysis indicates this is a
  no-clamp representation issue: `{}` is a valid no-op value for the field but
  the generic required-field audit treats empty objects as failure.
- The two screened `main_search_strategy` candidates had complete
  selected-surface runtime audit: `main_search_strategy_loaded=true`,
  `main_search_strategy_active=true`, `main_search_strategy_errors=0`, and
  no missing required runtime fields across 16/16 candidate-side pairs.
- Net-benefit guards executed: effective baseline fractions were `0.8` and
  `0.85`, baseline params were clamped, bounded destroy/repair had a positive
  improvement floor and accept cap, route-pair gating produced
  `route_pair_phase_improved` skips, and `main_search_best_returned=true`.
- The guards did not improve case-level evidence. The screened candidates had
  pair W/L/T of `2/3/11`, `3/2/11`, and `1/0/23`, but all three had
  case-level `win_rate=0.0` and `median_delta=0.0`.
- `bounded_destroy_repair` accepted zero moves in this smoke. `route_pair_swap`
  accepted 22 moves in one screened main-search candidate, but those moves did
  not translate into case-level wins.

This does not satisfy the long-validation condition. The next repair should
restore hard forced-surface proposal control, make
`main_search_baseline_param_clamps` stable runtime evidence even when no clamp
is present, make APS forced diagnostics use bounded screening/runtime feedback,
and diagnose why accepted route-pair movement does not improve the final
returned case-level objective.

## 2026-05-10 APS Forced-Surface And No-Clamp Evidence Repair

Implemented the immediate repair slice from the deep net-benefit APS analysis:

- Persistent diagnostic forced-surface controls now propagate into
  `ProposalToolContext` as forced surface/action/target constraints.
- APS hypothesis outputs fail closed before code generation when
  `change_locus`, forced action, or forced target file differs from the active
  diagnostic constraint.
- Normal non-APS hypothesis generation applies the same forced-surface
  rejection before hypothesis records are created.
- Proposal tools now expose or validate the forced constraint in
  `context.list_surfaces`, `proposal.draft_hypothesis`,
  `proposal.schema_preview`, and `proposal.target_permission_preview`.
- APS planner context is not considered complete until all available compact
  feedback tools have succeeded. Availability is generic: proposal memory or
  research log enables `memory.query`, and screening-stage step history enables
  `feedback.query_screening` and `feedback.query_runtime`.
- The forced constraint remains proposal-side tainted context and is not added
  to `DecisionFeatures`.
- CVRP `main_search_baseline_param_clamps` is now always a non-empty JSON-safe
  evidence object. The no-clamp case records `applied=false`,
  `status=no_clamps`, `count=0`, and empty nested `fields`/`clamps`; clamp
  cases still record requested/effective values for fields such as
  `destroy_ratio` and `max_destroy_customers`.
- The generic runtime audit rule was not loosened. CVRP fixed the valid no-op
  representation at the problem-package boundary.
- Experiment analysis rules in `AGENT_ONBOARDING.md` now require per-round APS
  hypothesis/code chain analysis for APS-backed runs.

Validation:

```text
/home/clawd/miniconda3/envs/claw/bin/python -m pytest scion/scion/tests/unit/core/test_proposal_pipeline.py scion/scion/tests/unit/test_agentic_proposal_tools.py -q
99 passed in 1.69s

/home/clawd/miniconda3/envs/claw/bin/python -m pytest scion/scion/tests/test_cvrp_solver_operator_runtime.py scion/scion/tests/unit/test_research_surfaces.py -k 'main_search_strategy or cvrp_main_search' -q
20 passed, 86 deselected in 3.85s

/home/clawd/miniconda3/envs/claw/bin/python -m pytest scion/scion/tests/test_verification.py scion/scion/tests/unit/test_research_surfaces.py scion/scion/tests/unit/test_agentic_proposal_tools.py scion/scion/tests/unit/core/test_proposal_pipeline.py scion/scion/tests/test_contract.py scion/scion/tests/test_cvrp_adapter.py scion/scion/tests/test_cvrp_solver_operator_runtime.py scion/scion/tests/test_protocol.py scion/scion/tests/unit/core/test_evaluation_pipeline.py scion/scion/tests/test_cvrp_protocol_smoke.py scion/scion/tests/test_cvrp_controlled_campaign.py -q
454 passed in 41.19s

/home/clawd/miniconda3/envs/claw/bin/python -m pytest scion/scion/tests -q
1521 passed, 1 skipped in 63.29s
```

Next step: commit this slice and run another five-round forced
`main_search_strategy` smoke. This smoke should be judged first on diagnostic
control and APS behavior: all hypotheses must stay on `main_search_strategy`,
no valid no-clamp strategy should fail runtime audit solely because
`main_search_baseline_param_clamps` is empty, and APS artifacts should show
bounded feedback reads before hypothesis finalization.

## 2026-05-10 APS Forced Diagnostic Repair 5R Smoke Audited

A detached five-round Sonnet CVRP formal-path smoke completed after the APS
forced-surface and CVRP no-clamp evidence repairs:

```text
run_root=/home/clawd/research/scion-experiments/v04-aps-forced-diagnostic-repair-sonnet-5r-20260510T024646Z
scion_commit=3a4649f
worktree_dirty=false
model=claude-sonnet-4-6
problem=cvrp formal VRP
rounds=5
agentic_proposal=true
disable_early_stop=true
force_surface=main_search_strategy
cvrp_time_limit_sec=10
python=/home/clawd/miniconda3/envs/claw/bin/python
data_root=/home/clawd/research/or-autoresearch-agent/vrp
```

Detailed delegated raw-artifact analysis is recorded in:

```text
scion/docs/experiments/v0.4/v0.4-aps-forced-diagnostic-repair-sonnet-5r-20260510.md
```

Outcome:

```text
rounds=5/5
steps=5
experiments=1
champion=v1
promotions=0
frozen_budget_used=0
formal_ready=false
final_evidence_refs=missing
stop=max_rounds_exhausted
```

Interpretation:

- The run normally completed at the campaign level. `exit.txt` was missing,
  but `status.json`, `campaign_summary.json`, SQLite, and `run.log` showed a
  complete `max_rounds_exhausted` closeout.
- Forced-surface drift was fixed for successful hypotheses. All successful
  hypotheses were `modify/main_search_strategy` targeting
  `policies/main_search_strategy.py`; the `create_new/proposal: 1` summary
  entry was a round-5 proposal-failure placeholder, not a real off-surface
  candidate.
- No-clamp runtime evidence false failures were fixed. The screened candidate
  had `main_search_baseline_param_clamps` present, non-empty, and not failed
  for all 16 candidate-side pairs.
- APS did read bounded feedback and memory. Round 1/2/4 hypothesis sessions
  called `memory.query`, `feedback.query_screening`, and
  `feedback.query_runtime`.
- The repair exposed a new APS blocker: repeated feedback and list-surface
  observations exceeded the observation budget in rounds 2, 4, and 5, causing
  code-generation or proposal failures before a patch was produced.
- Only round 1 reached screening. It had 16/16 valid pairs, pair W/L/T
  `4/2/10`, case-level `win_rate=0.125`, `median_delta=0.0`, and median
  runtime ratio about `0.9521`, then failed `SCREENING_FAIL_WIN_RATE`.
- Selected-surface runtime audit was complete for the screened candidate, and
  both `route_pair_swap` and `bounded_destroy_repair` were selected and
  attempted. `bounded_destroy_repair` accepted zero moves.

This smoke validates the previous repair slice only partially. It confirms
forced-surface, no-clamp evidence, and bounded-feedback use, but it does not
provide enough screened candidates to judge CVRP strategy changes. The next
repair should reduce APS observation payloads and deduplicate fallback tool
calls so forced diagnostics can produce multiple code patches under the
feedback requirement.

## 2026-05-10 APS Feedback/Fallback Budget Repair

Implemented the follow-up APS repair after the forced diagnostic repair smoke:

- APS fallback now treats successful compact observations as reusable session
  facts. It only fills missing `context.list_surfaces`,
  `context.read_problem`, `memory.query`, `feedback.query_screening`, and
  `feedback.query_runtime` observations instead of repeating successful calls.
- Planner-selected duplicate reads of those reusable observations now switch
  to missing-only fallback rather than consuming another large observation.
- An already successful selected `context.read_surface` is not read again after
  hypothesis approval.
- During forced-surface diagnostics, `context.list_surfaces` returns the forced
  surface's compact listing plus the total declared-surface count, avoiding
  repeated full design-space listings while preserving the constraint record.
- `feedback.query_screening` and `feedback.query_runtime` bound compact JSON
  payloads before the tool result-size guard, preserving safe summaries without
  exposing raw metric refs.

Validation:

```text
/home/clawd/miniconda3/envs/claw/bin/python -m pytest scion/scion/tests/unit/test_agentic_proposal_tools.py scion/scion/tests/unit/core/test_proposal_pipeline.py -q
102 passed in 2.49s

/home/clawd/miniconda3/envs/claw/bin/python -m pytest scion/scion/tests/test_verification.py scion/scion/tests/unit/test_research_surfaces.py scion/scion/tests/unit/test_agentic_proposal_tools.py scion/scion/tests/unit/core/test_proposal_pipeline.py scion/scion/tests/test_contract.py scion/scion/tests/test_cvrp_adapter.py scion/scion/tests/test_cvrp_solver_operator_runtime.py scion/scion/tests/test_protocol.py scion/scion/tests/unit/core/test_evaluation_pipeline.py scion/scion/tests/test_cvrp_protocol_smoke.py scion/scion/tests/test_cvrp_controlled_campaign.py -q
457 passed in 48.35s

/home/clawd/miniconda3/envs/claw/bin/python -m pytest scion/scion/tests -q
1524 passed, 1 skipped in 65.90s
```

Next step: commit this slice and run another five-round forced
`main_search_strategy` smoke. Acceptance should first check whether all five
rounds can produce forced-surface hypotheses and multiple code patches without
observation-budget failures, while still showing bounded feedback/memory use.

## 2026-05-10 APS Feedback Budget Repair 5R Smoke Audited

A detached five-round Sonnet CVRP formal-path smoke completed after the APS
feedback/fallback budget repair:

```text
run_root=/home/clawd/research/scion-experiments/v04-aps-feedback-budget-repair-sonnet-5r-20260510T032202Z
scion_commit=d17c8b4
worktree_dirty=false
model=claude-sonnet-4-6
problem=cvrp formal VRP
rounds=5
agentic_proposal=true
disable_early_stop=true
force_surface=main_search_strategy
cvrp_time_limit_sec=10
python=/home/clawd/miniconda3/envs/claw/bin/python
data_root=/home/clawd/research/or-autoresearch-agent/vrp
```

Detailed delegated raw-artifact analysis is recorded in:

```text
scion/docs/experiments/v0.4/v0.4-aps-feedback-budget-repair-sonnet-5r-20260510.md
```

Outcome:

```text
rounds=5/5
steps=5
experiments=1
champion=v1
promotions=0
frozen_budget_used=0/2
formal_ready=false
final_evidence_refs=missing
stop=max_rounds_exhausted
```

Interpretation:

- The run completed normally at the campaign level. `exit.txt` was missing,
  but `run.log`, `status.json`, `campaign_summary.json`, and SQLite were
  internally consistent.
- The APS feedback/fallback budget repair worked. No `result_too_large`,
  observation-budget exhaustion, or tool-budget failure recurred; session
  observation usage stayed below the 48000-character cap.
- Bounded feedback and memory were still used. APS sessions called
  `memory.query`, `feedback.query_screening`, and `feedback.query_runtime`,
  and runtime feedback became available after round 1.
- Forced-surface control held. All five generated hypotheses were
  `modify/main_search_strategy` targeting `policies/main_search_strategy.py`.
- The acceptance condition for multiple code patches failed. Round 1 generated
  one patch and reached screening; rounds 2-5 failed hypothesis Contract at
  `C10_novelty` before code generation.
- The new blocker is singleton semantic novelty persistence. Round 1 passed
  without a structured `novelty_signature`; after it was rejected by screening,
  later materially distinct structured proposals could not be compared
  semantically against that empty-signature record, so C10 fell back to strict
  `(locus, action, target_file)` duplicate identity.
- The only screened candidate had 16/16 valid pairs, pair W/L/T `3/2/11`,
  case-level `win_rate=0.0`, `median_delta=0.0`, median runtime ratio about
  `0.9482`, and failed `SCREENING_FAIL_WIN_RATE`.
- Selected-surface runtime audit was complete for the screened candidate:
  `main_search_strategy_loaded=true`, `main_search_strategy_active=true`,
  `main_search_strategy_errors=0`, and required runtime fields were present on
  all candidate-side pairs. `main_search_baseline_param_clamps` was present
  and non-empty for all pairs.
- Deep components were selected and attempted in the screened candidate.
  `route_pair_swap` accepted six moves across three pairs, but those benefits
  did not survive case-level aggregation. `bounded_destroy_repair` accepted
  zero moves and remained dominated by repair-budget exhaustion.

This smoke validates the APS compaction repair but does not provide enough
screened candidates to judge CVRP strategy efficacy. Do not enter long
validation. The next repair should make APS/Contract require and persist
usable structured `novelty_signature` values for forced singleton semantic
surfaces, then rerun a five-round forced `main_search_strategy` smoke and
require multiple code patches plus screened candidates before judging solver
quality.

## 2026-05-10 Singleton Semantic Novelty Persistence Repair

Implemented the next core governance repair after the APS feedback budget
smoke:

- C10 now fails candidate `modify` hypotheses on `semantic_signature` surfaces
  before code generation when the candidate lacks usable structured identity
  for declared `novelty.signature_fields`.
- C10 no longer lets historical active/blacklisted/rejected singleton records
  with empty or unusable structured identity poison later candidates that do
  provide valid structured `novelty_signature` values.
- Duplicate valid structured semantic signatures still fail closed with
  structured `novelty_signature` duplicate detail.
- Forced-surface context now renders occupied structured signatures from
  active, blacklisted, and rejected hypotheses, so APS can see the identities
  that C10 may block.
- Hypothesis tool/schema guidance now states that `novelty_signature` is
  required when the selected surface declares
  `novelty.strategy=semantic_signature`.

Focused validation:

```text
/home/clawd/miniconda3/envs/claw/bin/python -m pytest scion/scion/tests/unit/test_research_surfaces.py scion/scion/tests/unit/test_agentic_proposal_tools.py scion/scion/tests/unit/core/test_proposal_pipeline.py scion/scion/tests/test_proposal_validation.py scion/scion/tests/test_contract.py -q
258 passed in 2.64s
```

Broader boundary validation:

```text
/home/clawd/miniconda3/envs/claw/bin/python -m pytest scion/scion/tests/test_verification.py scion/scion/tests/unit/test_research_surfaces.py scion/scion/tests/unit/test_agentic_proposal_tools.py scion/scion/tests/unit/core/test_proposal_pipeline.py scion/scion/tests/test_contract.py scion/scion/tests/test_cvrp_adapter.py scion/scion/tests/test_cvrp_solver_operator_runtime.py scion/scion/tests/test_protocol.py scion/scion/tests/unit/core/test_evaluation_pipeline.py scion/scion/tests/test_cvrp_protocol_smoke.py scion/scion/tests/test_cvrp_controlled_campaign.py -q
458 passed in 42.58s
```

Full suite:

```text
/home/clawd/miniconda3/envs/claw/bin/python -m pytest scion/scion/tests -q
1525 passed, 1 skipped in 56.37s
```

Next step: launch another five-round forced `main_search_strategy` smoke. The
first smoke acceptance condition is multiple code patches and screened
candidates under bounded APS feedback; solver-quality validation remains
blocked until that happens.

## 2026-05-10 Semantic Novelty Repair 5R Smoke Audited

A detached five-round Sonnet CVRP formal-path smoke completed after the
singleton semantic novelty persistence repair:

```text
run_root=/home/clawd/research/scion-experiments/v04-semantic-novelty-repair-sonnet-5r-20260510T043306Z
scion_commit=7111d69
worktree_dirty=false
model=claude-sonnet-4-6
problem=cvrp formal VRP
rounds=5
agentic_proposal=true
disable_early_stop=true
force_surface=main_search_strategy
cvrp_time_limit_sec=10
python=/home/clawd/miniconda3/envs/claw/bin/python
data_root=/home/clawd/research/or-autoresearch-agent/vrp
exit_code=0
```

Detailed delegated raw-artifact analysis is recorded in:

```text
scion/docs/experiments/v0.4/v0.4-semantic-novelty-repair-sonnet-5r-20260510.md
```

Outcome:

```text
rounds=5/5
steps=5
experiments=4
champion=v1
promotions=0
frozen_budget_used=0/2
formal_ready=false
final_evidence_refs=missing
stop=max_rounds_exhausted
```

Interpretation:

- The run completed normally with `EXIT_CODE:0`.
- The C10 repair is validated for this diagnostic. Four approved hypotheses
  had complete structured `novelty_signature`, no `C10_novelty` failure
  occurred, and rounds 1, 2, 4, and 5 generated code patches that reached
  screening.
- APS observation budget remained healthy: successful hypothesis sessions used
  about 21k-26k chars, code sessions about 30k-35k chars, under the 48000 cap.
- Forced-surface governance stayed fail-closed. Round 3 drafted
  `baseline_policy`, but the proposal-side forced-surface constraint rejected
  it before code generation.
- All four screened candidates selected `main_search_strategy`; selected
  surface runtime audit was complete with all 44 required runtime fields
  observed on 16/16 candidate pairs.
- All screened candidates failed `SCREENING_FAIL_WIN_RATE`. Pair W/L/T by
  screened round was `3/2/11`, `3/1/12`, `3/1/12`, and `5/1/10`; case-level
  win rates were `0.0`, `0.0`, `0.0`, and `0.25`, with `median_delta=0.0` in
  every screened round.
- Component activity improved but did not prove net benefit. Round 5 selected
  both `route_pair_swap` and `bounded_destroy_repair`, accepted 43 route-pair
  moves and 11 bounded destroy/repair moves, and produced the best case-level
  signal, but still failed screening. Delegated analysis found the
  improvement-loop phase delta still did not clearly reflect accepted moves as
  final returned benefit.
- Proposal feedback appears broken or scoped too narrowly. APS called
  `feedback.query_screening` and `feedback.query_runtime` every successful
  round, but later rounds still saw 0 screening feedback rows and no safe
  runtime feedback even after earlier screening had completed.

This smoke validates the core C10/APS-control repair. It does not justify long
validation. The next repair should make proposal feedback tools return
same-campaign compact screening/runtime history after prior screening exists,
and should add or expose bounded attribution from component accepted moves to
phase delta and final pair/case outcome.

## Remaining Optimization Backlog

The post-run P0 governance findings are closed in code: formal `.vrp`
baseline selection fails closed, frozen holdout usage is enforced, and campaign
summaries expose fail-closed formal readiness status for final evidence refs.

P1:

- Core governance closeout should fix the 2026-05-09 audit findings before
  another long validation: C10 free-text novelty fallback, actual
  `DecisionFeatures` lineage persistence, patch-level selected-surface
  propagation, soft-abandon decision provenance, and problem-specific
  runtime-field heuristics in proposal context.
- The C10 free-text fallback and patch-level selected-surface propagation
  repairs are now implemented and validated. Remaining core governance backlog
  from the audit is actual `DecisionFeatures` lineage persistence,
  soft-abandon decision provenance, and moving problem-specific runtime-field
  heuristics out of proposal context.
- Campaign composition is now owner-backed and centralized, but a future
  typed-collaborator pass can still reduce callback coupling further.
- CVRP formal research should now prioritize surface efficacy and diagnostic
  control, not reporting plumbing. Required `algorithm_*` runtime fields are
  present in fresh formal screening pair metrics and campaign summaries,
  `baseline_policy` validated bounded baseline-param plumbing, and
  `main_search_strategy` now exposes the whole-algorithm CVRP slice with
  bounded construction, baseline params, package-owned route-pair
  swap/destroy-repair components, acceptance, restart, perturbation, and
  optional registry toggles. The first forced diagnostic validated active
  runtime plumbing but evaluated only one candidate because APS surface reads
  were too large and C10 novelty rejected later hypotheses. C10 now supports
  structured singleton semantic identity through `novelty_signature`, and APS
  surface context is compact by default. The clean-worktree diagnostic from
  commit `b98196b` validated those control repairs but still failed screening
  for all three candidates and did not exercise route-pair-swap or
  destroy-repair components. The post-repair smoke from commit `e25680a`
  validated the new component telemetry and produced some pair-level movement,
  but still selected only shallow local-search components; `route_pair_swap`
  and `bounded_destroy_repair` were never selected or attempted, and a second
  forced hypothesis failed C10 duplicate detection. Deep-component selection
  is now explicit in forced diagnostic prompt metadata, APS preview, C10
  feedback, and runtime coverage telemetry. The five-round smoke from commit
  `114727e` showed that both deep components can now be selected and attempted,
  but screening still failed and `bounded_destroy_repair` accepted zero moves.
  The bounded destroy/repair efficacy slice is implemented and validated in
  controlled tests with formal-like `rounds=5, top_k=64`. The follow-up smoke
  from commit `8a37fd6` showed destroy/repair accepted moves in formal
  screening, but case-level screening quality still topped out at `0.25` and
  all candidates failed `SCREENING_FAIL_WIN_RATE`. Keep long validation blocked
  until accepted component moves translate into stronger case-level outcomes.
  The main-search net-benefit guard slice is implemented and validated, and
  the follow-up smoke from commit `8d49abe` finished normally, but it did not
  improve screening quality: one forced diagnostic round drifted to
  `route_local`, all screened candidates had case-level `win_rate=0.0`,
  `bounded_destroy_repair` accepted zero moves, and accepted route-pair moves
  did not become case-level wins. The hard forced-surface proposal control,
  APS compact feedback completeness, and no-clamp runtime evidence semantics
  repairs are now implemented and validated. The follow-up smoke from commit
  `3a4649f` confirmed those controls in real APS artifacts but produced only
  one screened candidate because repeated feedback/list observations exhausted
  APS observation budget in later rounds. APS feedback/fallback budget control
  is now repaired and validated in focused and full suites. The follow-up smoke
  from commit `d17c8b4` confirmed bounded-feedback budget behavior and stable
  forced-surface control, but still produced only one code patch because C10
  rejected rounds 2-5 after comparing later structured singleton proposals
  against a rejected round-1 hypothesis with empty structured novelty identity.
  The singleton semantic novelty persistence repair is now implemented: C10
  requires candidate structured identity before code generation and does not
  let old empty-signature records block later valid structured candidates.
  The follow-up smoke from commit `7111d69` validated that repair: four code
  patches reached screening and no C10 failure recurred. The next blocker is
  proposal-feedback retrieval plus net efficacy attribution: feedback tools
  returned empty same-campaign history, and accepted route-pair/destroy-repair
  moves still did not clearly become phase-level and case-level benefit.

P2:

- Formal CVRP interpretation should account for stage-specific budgets from the
  v0.4 P4-05 readiness design. The dual-Sonnet run used one 5 second solver
  budget and is acceptable for readiness plumbing, but not as final benchmark
  evidence.

## Remaining Risks

- Formal readiness is now recorded in summaries, but a dedicated CLI/readiness
  command can still make post-campaign closeout easier to run consistently.
- Runtime isolation is resource-limited and env-sanitized, but not yet a full
  read-only mount sandbox.
- Stale/reconcile semantics still need a dedicated v3-aligned review after this
  formal-readiness run.
- Legacy/no-adapter V8 objective-only comparison remains intentionally
  compatibility-only; do not prioritize it ahead of the
  CVRP surface-efficacy slice.
