# Scion v0.4 Current State

*Last updated: 2026-05-06*

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
- CVRP currently exposes six surfaces: `route_local`, `route_pair`,
  `ruin_recreate`, `search_policy`, `construction_policy`, and
  `neighborhood_portfolio`.
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

```bash
cd scion
/home/clawd/miniconda3/envs/claw/bin/python -m pytest scion/tests -q
```

Latest result:

```text
1246 passed, 1 skipped in 40.82s
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
- V5/V6/V7 are generic when adapter-backed, but legacy warehouse fallbacks
  should not apply to new problem-v1 packages.
- V8 nondeterminism is conceptually generic but still has operator/warehouse
  diagnostics and should eventually use adapter-declared canonical solution
  fingerprints.
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
- The next gate modernization slice should therefore make V2/V5
  surface-aware through shared interface validators and adapter-declared policy
  invariant previews, while preserving the v3 protocol gates unchanged.

## Remaining Optimization Backlog

The post-run P0 governance findings are closed in code: formal `.vrp`
baseline selection fails closed, frozen holdout usage is enforced, and campaign
summaries expose fail-closed formal readiness status for final evidence refs.

P1:

- Campaign composition is now owner-backed and centralized, but a future
  typed-collaborator pass can still reduce callback coupling further.
- CVRP formal research needs implementation slices for problem-owned algorithm
  surfaces beyond `construction_policy` and `neighborhood_portfolio`.
  `search_policy` proved useful as a generic surface model but too narrow as an
  optimization lever because it still acts around the post-baseline operator
  layer. Next candidates are destroy/repair and acceptance/restart policy
  surfaces once the CVRP package can expose bounded hooks and runtime audit.

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
