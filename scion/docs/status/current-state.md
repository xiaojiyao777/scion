# Scion v0.4 Current State

*Last updated: 2026-05-07*

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
has now passed a one-round forced `algorithm_blueprint` Sonnet CVRP formal
smoke. APS is fixed enough to unblock the next control-path slice, but the
budget headroom is low. The current bottleneck is `algorithm_blueprint`
audit/contract/reporting, especially preserving and reporting required
`algorithm_*` runtime fields through formal screening metrics and campaign
summaries. This is not solver-quality evidence, and no candidate promoted.

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
- CVRP currently exposes seven surfaces: `route_local`, `route_pair`,
  `ruin_recreate`, `search_policy`, `construction_policy`,
  `neighborhood_portfolio`, and `algorithm_blueprint`.
- The CVRP `search_policy` surface allows bounded optimization of baseline
  time fraction, post-baseline operator round limit, and whether post-baseline
  operators run, without allowing LLM edits to `solver.py`.
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
- `scion run --force-surface <surface>` is a diagnostic experiment-control
  hook for proposal smoke tests. It accepts only declared research surfaces,
  fails closed during CLI/campaign startup for unknown surfaces, and can derive
  `action=modify` plus the singleton target file for surfaces such as
  `algorithm_blueprint`. This hook is not a Decision input, not solver-quality
  evidence, and should be used to force algorithm-blueprint smoke coverage
  without hardcoding CVRP or any specific surface into framework core.
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
cwd: /home/clawd/research/or-autoresearch-agent/scion
command: /home/clawd/miniconda3/envs/claw/bin/python -m pytest scion/tests -q
```

Latest result:

```text
1463 passed, 1 skipped in 48.27s
```

Latest focused APS compactness/proposal validation:

```bash
cd scion
/home/clawd/miniconda3/envs/claw/bin/python -m pytest scion/tests/unit/test_agentic_proposal_tools.py scion/tests/unit/core/test_proposal_pipeline.py scion/tests/test_proposal_validation.py -q
```

```text
101 passed in 0.94s
```

Latest focused CVRP algorithm-blueprint validation:

```bash
/home/clawd/miniconda3/envs/claw/bin/python -m pytest scion/scion/tests/test_problem_bridge.py scion/scion/tests/test_cvrp_adapter.py scion/scion/tests/test_cvrp_solver_operator_runtime.py scion/scion/tests/unit/test_research_surfaces.py -q
```

```text
98 passed in 6.96s
```

Broader CVRP subset:

```bash
/home/clawd/miniconda3/envs/claw/bin/python -m pytest scion/scion/tests/test_cvrp_*.py scion/scion/tests/unit/evidence/test_cvrp_*.py -q
```

```text
111 passed in 30.63s
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
  `detail="compact"` with a bounded code preview. `detail="full"` and
  `max_code_chars` remain available as explicit debug/deep-inspection opt-ins.
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
summaries still need full bounded `algorithm_*` audit fields, and
`construction_keep_top_k=2` meant the declared `demand_descending` construction
method was not actually tried.

Follow-up APS recovery compactness repair is now in code. Tool observations are
bounded before they are counted or persisted, optional planner
`context.read_surface` calls fail closed when remaining observation budget is
low, and APS-level surface reads are normalized to compact `max_code_chars=1200`
payloads. The replay validator remains fail-closed for genuinely over-budget
artifacts; the repair prevents new artifacts from being written with
`tool_budget_used.observation_chars > max_observation_chars`.

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
construction-mode changes, but explicit `algorithm_*` fields were still missing
from screening pair runtime metrics and the campaign screening summary.

Detailed delegated analysis is recorded in:

```text
scion/docs/experiments/v0.4/v0.4-forced-blueprint-budget-sonnet-smoke-20260507.md
```

The current bottleneck is now `algorithm_blueprint`
audit/contract/reporting rather than APS compactness, gate modernization, or
longer CVRP runs. The next CVRP slice should preserve and report the required
`algorithm_*` runtime fields through formal screening pair metrics and campaign
summaries before judging solver quality or broadening algorithm development.

## Remaining Optimization Backlog

The post-run P0 governance findings are closed in code: formal `.vrp`
baseline selection fails closed, frozen holdout usage is enforced, and campaign
summaries expose fail-closed formal readiness status for final evidence refs.

P1:

- Campaign composition is now owner-backed and centralized, but a future
  typed-collaborator pass can still reduce callback coupling further.
- CVRP formal research needs an `algorithm_blueprint`
  audit/contract/reporting slice before longer runs or new algorithm surfaces.
  Preserve and report required `algorithm_*` runtime fields through formal
  screening pair metrics and campaign summaries. Future compactness work may
  improve the very low APS budget headroom, but it is not the current blocker.
  Destroy/repair and acceptance/restart surfaces remain later candidates once
  the CVRP package can expose bounded hooks and runtime audit.

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
  `algorithm_blueprint` reporting slice.
