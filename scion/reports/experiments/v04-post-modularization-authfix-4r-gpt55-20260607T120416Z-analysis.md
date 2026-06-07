# v0.4 post-modularization authfix 4R GPT-5.5 run analysis

Run root:
`/home/clawd/research/scion-experiments/v04-post-modularization-authfix-4r-gpt55-20260607T120416Z-claw`

Report date: 2026-06-07

## Preface

This report analyzes the valid auth-fixed 4R run only. The nearby earlier run
`v04-post-modularization-4r-gpt55-20260607T113052Z-claw` is not used as solver
research evidence: its wrapper status finished, but campaign validity was
`invalid_no_effective_rounds`, with `effective_rounds_completed=0`,
`protocol_evaluated_candidates=0`, and repeated 401 `Invalid proxy API key`
proposal failures before circuit breaker stop.

The audit standard follows:

- `scion/design/scion-architecture-v3.md`: LLM Creative Layer output is
  tainted; Contract, Verification, Protocol, Safe Feature Extractor, and
  deterministic Decision are distinct boundaries; Decision reads
  `DecisionFeatures`, not free text.
- `scion/docs/AGENT_ONBOARDING.md`: branch governance is "one branch = one
  direction"; weak non-regressive screening may be preserved; proposal text and
  proposal-tool observations are tainted but can guide future proposals; active
  facts must stay adapter-owned and visible through a compact anchor.
- `scion/reports/experiments/v04-context-tooling-deep-audit-20260607.md`: do
  not equate "many tools" with a defect. Judge whether tools provide necessary
  evidence, whether default tool-selection is over-delegated to LLM calls, and
  whether framework behavior blocks research under the Rawls-style boundary
  audit.

## Run-Level Verdict

| Question | Verdict | Evidence |
|---|---|---|
| Complete? | Yes. | `campaign/run_status.json`: `campaign_exit_status=complete`, `run_complete=true`, `completed_requested_rounds=true`, `last_stop_reason=max_rounds_exhausted`. |
| Valid? | Yes. | `campaign/status.json.run_validity.status=valid`, `requested_rounds=4`, `effective_rounds_completed=4`, `formal_screened_candidates=4`. |
| All models GPT-5.5? | Yes. | All 59 `campaign/llm_traces/*.json` have `model=gpt-5.5`. |
| Promoted? | No. | `accepted_experiments=0`, `promoted_experiments=0`, protocol stages only `screening=4`, `validation=0`, `frozen=0`. |
| Quality blocked? | No for this valid run. | `quality_blocks=0`, `model_repair_failures=0`, `telemetry_failed_experiments=0`, `failure_categories={}`. |
| Research outcome? | Valid research, no promotion. Three branches regressed and were abandoned; one branch retained as weak positive. | DB `experiment_events`, `branches`, `campaign_summary.json.branch_history_cards`, and metrics refs. |
| Suitable next step? | Do not jump straight to 12R. A controlled 8R is reasonable after small Scion mechanism fixes; 12R should wait for repeated weak-positive or validation-grade signal. | Current run has one weak-positive retained checkpoint, but still no validation candidate and tool/context cost remains high. |

Run accounting:

| Field | Value |
|---|---:|
| requested rounds | 4 |
| effective rounds completed | 4 |
| proposal attempts total | 4 |
| formal screened candidates | 4 |
| protocol evaluated candidates | 4 |
| quality blocks | 0 |
| agentic sessions | 8 |
| LLM traces | 59 |

LLM request-kind accounting from `campaign_summary.json.cache_stats` and
`campaign/status.json.llm_request_kind_counts`:

| request_kind | Calls | Input tokens | Output tokens | Cache-read tokens |
|---|---:|---:|---:|---:|
| `tool_selection` | 47 | 688,585 | 1,764 | 72,320 |
| `hypothesis_target_intent` | 4 | 107,253 | 640 | 0 |
| `hypothesis` | 4 | 137,222 | 3,652 | 0 |
| `code` | 4 | 106,494 | 9,132 | 0 |
| total | 59 | 1,039,554 | 15,188 | 72,320 |

Interpretation: this run is much cleaner than the earlier context-tooling audit:
there are no repair loops and no quality blocks. Tool-selection still dominates
call count and input tokens, but the new ledger fields make that cost auditable.

## Evidence Used

Structured run artifacts:

- `campaign/status.json`
- `campaign/run_status.json`
- `campaign/campaign_summary.json`
- `campaign/agentic_sessions/agentic_session_trace_index.json`
- `campaign/agentic_sessions/*/output.json`
- `campaign/agentic_sessions/*/transcript.json`
- `campaign/agentic_sessions/*/scratch/api_visible_prompt_manifest_*.json`
- `campaign/agentic_sessions/*/scratch/self_check_preview_full_*.json`
- `campaign/agentic_sessions/*/scratch/algorithm_smoke_execution_evidence_0001.json`
- `campaign/llm_traces/*.json`
- `campaign/scion.db`
- `campaign/metrics/{e3a70478,4ec1c008,02182799,810ccf39}-*.json`

Important artifact caveat: the `transcript.json` files have empty `entries`, but
the same sessions preserve usable `compact_transcript`, `tool_selection_ledger`,
`observation_ledger`, prompts, outputs, self-check refs, and trace refs in
`output.json` plus `llm_traces`.

## Branch and Round Summary

| Round | Branch | Hypothesis | Target | Formal outcome |
|---:|---|---|---|---|
| 1 | `f7828329-07f4-4657-b08d-cb8295ccdbb2` | Add `string_exchange_vns`, a bounded cross-route contiguous string exchange. | `policies/baseline_modules/local_search.py` | Contract/Verification/Canary pass; screening regression; abandoned. |
| 2 | `c372b1ff-471d-4edb-add0-d0f035a6d816` | Add route-count-aware repair pressure to regret/greedy repair. | `policies/baseline_modules/destroy_repair.py` plus scheduler telemetry | Contract/Verification/Canary pass; screening regression; abandoned. |
| 3 | `87cab953-ebbd-406d-a9fd-6cee0d09c32f` | Retry `string_exchange_vns` as a more selective, route-pair-filtered version. | `policies/baseline_modules/local_search.py` | Contract/Verification/Canary pass; screening regression; abandoned. |
| 4 | `41e25749-b29d-49bf-8907-3cfa3d927596` | Create post-repair route compaction as all-or-nothing sparse-route elimination. | `policies/baseline_modules/route_compaction.py` plus scheduler hook | Contract/Verification/Canary pass; screening weak-positive retained; no promotion. |

Branch governance summary:

- R1-R3 were clean forks that failed screening win-rate and were archived as
  abandoned lineages, not parked.
- R4 is the only active branch at end of run: `state=explore`,
  `branch_code_status=active_weak_positive`, `best_quality_checkpoint_id` and
  `last_valid_checkpoint_id` both point to checkpoint
  `5a1606ff-35c4-4207-bf9e-e5d70171f785`.
- There were no rollback events and no lifecycle policy blocks.
- `campaign_summary.json.cross_branch_research_observability` reports
  `near_duplicate_count=1`, `saturated_signature_count=1`,
  `avoid_signature_count=1`, `novelty_pressure_seen_count=4`, and
  `same_branch_refinement_not_selected_count=4`. This matches the visible
  pattern: the scheduler kept opening clean forks while proposal context saw
  cross-branch feedback.

## Round 1: `f7828329` / `string_exchange_vns`

### LLM Call Trace

Hypothesis session `6d89f26c-d471-4d07-88e5-2dd75e56bbcc`:

| # | request_kind | Result |
|---:|---|---|
| 1 | `tool_selection` | `memory.query` |
| 2 | `tool_selection` | `feedback.query_screening`, empty |
| 3 | `tool_selection` | `feedback.query_runtime`, empty |
| 4 | `tool_selection` | `stop` |
| 5 | `hypothesis_target_intent` | selected `solver_design`, `modify`, `local_search.py`, mechanism `string_exchange_vns` |
| 6 | `hypothesis` | emitted hypothesis to add bounded contiguous string exchange |

Code session `d87626eb-47db-4898-ae69-17b23d3ed386`:

| # | request_kind | Result |
|---:|---|---|
| 1 | `tool_selection` | `memory.query` |
| 2 | `tool_selection` | `context.read_branch_state` |
| 3 | `tool_selection` | `context.read_surface` |
| 4 | `tool_selection` | `context.read_algorithm_file policies/baseline_algorithm.py` |
| 5 | `tool_selection` | `feedback.query_screening`, empty |
| 6 | `tool_selection` | `feedback.query_runtime`, empty |
| 7 | `tool_selection` | `stop` |
| 8 | `tool_selection` | `stop` |
| 9 | `code` | exact-replace patch |

All calls used `gpt-5.5`.

### Tool Observations

The hypothesis phase received required preface tools:
`context.list_surfaces`, `context.read_problem`,
`context.list_algorithm_files`, `context.read_active_solver_design`,
`context.read_solver_call_graph`, `context.read_active_solver_map`, and full
reads of `destroy_repair.py`, `local_search.py`, and `scheduler.py`. The
active solver map follow-up also read the operator registry and algorithm slice.

The code phase inherited most source observations as duplicate read receipts,
then added branch state, surface/interface, baseline entrypoint, schema preview,
target permission preview, contract preview, and algorithm smoke.

### Hypothesis and Patch

Hypothesis:

- Add `string_exchange_vns`, a bounded VNS operator that swaps short contiguous
  customer strings of length 1-3 between two routes.
- Only accept capacity-feasible negative-distance-delta exchanges.
- Preserve fleet violation by not creating routes and by no-op on infeasible or
  time-reserve cases.

Patch:

- Modified `_default_vns_operators()` to insert `_string_exchange` before
  `_two_opt_star`.
- Added `_string_exchange(solution, context, reserve)` before `_two_opt_star`.
- The implementation records `string_exchange_vns` iteration, move, phase
  runtime, and positive delta telemetry.
- It scans non-empty route pairs, segment lengths 1-3, optional reversals, and
  exits at `max_checks=1536` or time reserve.

This patch stayed inside the CVRP solver-design surface. It did not modify
Scion generic core.

### Gates and Protocol

| Gate / stage | Result |
|---|---|
| Schema preview | pass |
| Target/action permission preview | pass |
| Contract preview | pass |
| Algorithm smoke | pass |
| Contract | pass |
| Verification | pass |
| Canary | passed |
| Screening metrics | `metrics/e3a70478-3114-49b3-9c4a-0347a8b95a0d.json` |
| Decision | `abandon` |

Screening evidence:

- 8 cases, 16 valid pairs, 0 failed pairs.
- Case-level: 0 wins, 1 loss, 7 ties.
- Pair-level: 1 win, 4 losses, 11 ties.
- Median delta 0.0, CI [-1.0, 0.0].
- Runtime confidence high/sufficient; median runtime ratio 1.0037 and runtime
  regression rate 0.625.
- Runtime budget diagnostic: `SCREENING_RUNTIME_BUDGET_SATURATION`,
  saturation ratio 1.013.

Telemetry:

- Guard passed.
- `string_exchange_vns` activation observed in 16/16 pairs.
- Effect positive in 12/16 pairs for mechanism-level phase-improvement and
  phase-best-delta fields.
- Aggregate mechanism phase delta was positive, but it did not translate to
  objective wins; losses occurred on `B-n52-k7.vrp` and `E-n33-k4.vrp`.

Assessment: good implementation and instrumentation, but protocol correctly
rejected it because local mechanism activity was not reliable objective
improvement and runtime was slightly worse.

## Round 2: `c372b1ff` / `route_count_aware_repair`

### LLM Call Trace

Hypothesis session `f2150518-7ad6-461f-82fa-cec5772cc796`:

| # | request_kind | Result |
|---:|---|---|
| 1 | `tool_selection` | `memory.query` |
| 2 | `tool_selection` | `feedback.query_screening`, 1 row |
| 3 | `tool_selection` | `feedback.query_runtime`, runtime feedback |
| 4 | `tool_selection` | `stop` |
| 5 | `hypothesis_target_intent` | selected `solver_design`, `modify`, `destroy_repair.py`, mechanism `route_count_aware_repair` |
| 6 | `hypothesis` | emitted route-count-aware repair hypothesis |

Code session `9834335b-fc30-475e-869b-5701b0541add`:

| # | request_kind | Result |
|---:|---|---|
| 1 | `tool_selection` | `memory.query` |
| 2 | `tool_selection` | `feedback.query_screening`, 1 row |
| 3 | `tool_selection` | `feedback.query_runtime` |
| 4 | `tool_selection` | `context.read_algorithm_file`, duplicate receipt |
| 5 | `tool_selection` | `context.read_branch_state` |
| 6 | `tool_selection` | `stop` |
| 7 | `tool_selection` | `stop` |
| 8 | `code` | exact-replace patch |

All calls used `gpt-5.5`.

### Tool Observations

The hypothesis had fresh R1 feedback. This is the first clear evidence that the
agent used history: after `string_exchange_vns` produced local effects but
failed screening with runtime pressure, the next branch moved from local-search
operator design to repair-route-count pressure.

The code phase received schema/permission/contract previews and algorithm smoke.
Smoke passed but carried an advisory `activation_not_observed_diagnostic`. This
was not a blocking failure and formal screening later observed activation and
effect, so it should be treated as smoke-level diagnostic noise rather than an
agent-quality block.

### Hypothesis and Patch

Hypothesis:

- Modify regret/greedy repair so customers without feasible existing-route
  insertion become urgent near the route limit, while blind new-route opening is
  avoided unless below the cap.
- Prefer low-delta insertions into existing routes over singleton route
  creation.
- Reduce downstream VNS spent on over-route or route-opening artifacts.

Patch:

- Modified `_greedy_insertion` to use `_route_limit`, `_can_open_new_route`,
  `_route_count_surcharge`, and best insertion deltas.
- Modified `_regret_insertion` similarly, making route-limit pressure part of
  repair scoring.
- Added helper logic around route limit, new-route permission, insertion cost,
  and route-count surcharge.
- Modified `scheduler.py` to record
  `route_count_aware_repair` phase runtime and move telemetry around repair
  execution.

This is still within solver-design/problem-owned modules. The extra scheduler
change is an integration hook in the branch solver package, not generic Scion
core.

### Gates and Protocol

| Gate / stage | Result |
|---|---|
| Schema preview | pass |
| Target/action permission preview | pass |
| Contract preview | pass |
| Algorithm smoke | pass with diagnostic advisory |
| Contract | pass |
| Verification | pass |
| Canary | passed |
| Screening metrics | `metrics/4ec1c008-ffde-4fbc-9e91-ff7511d2e559.json` |
| Decision | `abandon` |

Screening evidence:

- 8 cases, 16 valid pairs, 0 failed pairs.
- Case-level: 0 wins, 1 loss, 7 ties.
- Pair-level: 2 wins, 3 losses, 11 ties.
- Median delta 0.0, CI [0.0, 0.0].
- Runtime aggregate excluded because champion runtime was cached/low confidence:
  `RUNTIME_EVIDENCE_LOW_OR_CACHED_CONFIDENCE`,
  `RUNTIME_EVIDENCE_INCOMPLETE`, `RUNTIME_AGGREGATE_EXCLUDED`.
- Runtime budget diagnostic: saturation ratio 1.0246.

Telemetry:

- Guard passed.
- `route_count_aware_repair` effect observed in 14/16 pairs.
- Case win appeared on `E-n101-k8.vrp`, but `B-n52-k7.vrp` lost both seeds.

Assessment: the branch was a reasonable response to R1 and generated meaningful
mechanism evidence, but the loss without a case-level win-rate pass made
abandon appropriate.

## Round 3: `87cab953` / filtered `string_exchange_vns`

### LLM Call Trace

Hypothesis session `744c7c00-4b59-4d91-af85-2477b7fecc69`:

| # | request_kind | Result |
|---:|---|---|
| 1 | `tool_selection` | `memory.query` |
| 2 | `tool_selection` | `feedback.query_screening`, 2 rows |
| 3 | `tool_selection` | `feedback.query_runtime`, runtime feedback |
| 4 | `tool_selection` | `stop` |
| 5 | `hypothesis_target_intent` | selected `solver_design`, `modify`, `local_search.py`, mechanism `string_exchange_vns` |
| 6 | `hypothesis` | emitted filtered string-exchange hypothesis |

Code session `0c5864e5-4225-4295-b057-feb19d273d92`:

| # | request_kind | Result |
|---:|---|---|
| 1 | `tool_selection` | `memory.query` |
| 2 | `tool_selection` | `feedback.query_screening`, 2 rows |
| 3 | `tool_selection` | `feedback.query_runtime` |
| 4 | `tool_selection` | `context.read_algorithm_file`, summary-only receipt |
| 5 | `tool_selection` | `context.read_algorithm_file`, summary-only receipt |
| 6 | `tool_selection` | `stop` |
| 7 | `tool_selection` | `context.read_branch_state` |
| 8 | `tool_selection` | `stop` |
| 9 | `code` | exact-replace patch |

All calls used `gpt-5.5`.

### Tool Observations

The hypothesis context had two feedback rows and runtime feedback. The agent did
not ignore prior failure: it explicitly framed the new string-exchange attempt
as more selective than the broad R1 operator, with route-pair filters and a
shorter segment cap. That said, this is also the run's main near-duplicate
pressure: it returned to the same mechanism family after a clear regression.
The material difference was real but not strong enough to beat the search-risk
of another local-search expansion.

### Hypothesis and Patch

Hypothesis:

- Add a more selective `string_exchange_vns`, constrained to short segments,
  complementary slack/demand, nearest boundary-edge style route-pair pruning,
  and early exits.
- Target total distance while preserving route count and capacity.

Patch:

- Registered `_string_exchange_vns` in `_default_vns_operators()` before
  `_swap`.
- Added `_string_exchange_vns(solution, context, reserve)`.
- Used a dynamic max segment length: 3 only for small instances, otherwise 2.
- Built route pair scores, scanned bounded candidate pairs, checked capacity,
  and recorded `string_exchange_vns` telemetry.

### Gates and Protocol

| Gate / stage | Result |
|---|---|
| Schema preview | pass |
| Target/action permission preview | pass |
| Contract preview | pass |
| Algorithm smoke | pass |
| Contract | pass |
| Verification | pass |
| Canary | passed |
| Screening metrics | `metrics/02182799-b1cc-478f-83b8-9b8a9fe0c961.json` |
| Decision | `abandon` |

Screening evidence:

- 8 cases, 16 valid pairs, 0 failed pairs.
- Case-level: 0 wins, 1 loss, 7 ties.
- Pair-level: 1 win, 3 losses, 12 ties.
- Median delta 0.0, CI [-1.5, 0.0].
- Runtime aggregate excluded due low cached champion confidence.
- Runtime budget diagnostic: saturation ratio 1.0221.

Telemetry:

- Guard passed.
- `string_exchange_vns` effect positive in 15/16 pairs by mechanism fields.
- The effect was not globally reliable: `E-n101-k8.vrp` had a win, but
  `B-n31-k5.vrp` and `B-n52-k7.vrp` lost.

Assessment: this is an acceptable but marginal follow-up. It shows the agent can
adjust a failed idea, but it also demonstrates why Scion needs material
difference/near-duplicate governance: the refined version still consumed a full
screening round and ended as another regression.

## Round 4: `41e25749` / `post_repair_route_compaction`

### LLM Call Trace

Hypothesis session `b96a85ba-8062-48c5-81cc-5bc623f1fc1d`:

| # | request_kind | Result |
|---:|---|---|
| 1 | `tool_selection` | `memory.query` |
| 2 | `tool_selection` | `feedback.query_screening`, 3 rows |
| 3 | `tool_selection` | `feedback.query_runtime`, runtime feedback |
| 4 | `tool_selection` | `stop` |
| 5 | `hypothesis_target_intent` | selected `solver_design`, `create_new`, `route_compaction.py`, mechanism `post_repair_route_compaction` |
| 6 | `hypothesis` | emitted post-repair route-compaction hypothesis |

Code session `e0149e27-3faa-4de1-a717-4c9415f6f7f3`:

| # | request_kind | Result |
|---:|---|---|
| 1 | `tool_selection` | `memory.query` |
| 2 | `tool_selection` | `feedback.query_screening`, 3 rows |
| 3 | `tool_selection` | `feedback.query_runtime` |
| 4 | `tool_selection` | `context.read_algorithm_file`, summary-only receipt |
| 5 | `tool_selection` | `context.read_algorithm_file`, summary-only receipt |
| 6 | `tool_selection` | `context.read_branch_state` |
| 7 | `tool_selection` | `stop` |
| 8 | `tool_selection` | `stop` |
| 9 | `code` | full-file create plus scheduler integration |

All calls used `gpt-5.5`.

### Tool Observations

The hypothesis had three prior feedback rows and runtime feedback. This is the
clearest history-driven shift: after homogeneous local-search/string-exchange
and repair-bias branches failed on win rate with runtime pressure, the agent
moved to a distinct whole-route cleanup pass.

Prompt manifests show this was expensive but well grounded:

- Hypothesis prompt total visible chars: 144,173.
- Largest sections: full algorithm file reads 30,568 chars; cross-branch map
  22,696; tool observations 21,571; active solver map receipts 21,008;
  runtime feedback 8,909.
- Code prompt total visible chars: 99,086.
- Largest sections: branch-current integration files 19,147; tool observations
  18,577; full solver rules 8,459; constraints 8,450; implementation scope
  7,042.

### Hypothesis and Patch

Hypothesis:

- Create `route_compaction.py` with `post_repair_route_compaction`.
- After repair and optional VNS, try to empty sparse/high-detour routes by
  moving all their customers into existing routes via capacity-feasible cheapest
  insertions.
- Accept only an all-or-nothing lexicographically feasible improvement; no-op
  otherwise.

Patch:

- Created `policies/baseline_modules/route_compaction.py`.
- Implemented `_post_repair_route_compaction(solution, max_routes, context,
  reserve)`.
- Candidate selection ranks sparse routes by load ratio, depot-leg detour, and
  route length; tries up to the top three route candidates.
- `_try_empty_route` copies the solution, removes one route, reinserts its
  customers using `_best_insertion`, rebuilds indices, and returns only feasible
  candidates.
- Records `post_repair_route_compaction` iteration, move, phase runtime, and
  delta telemetry.
- Modified `scheduler.py` to import `_post_repair_route_compaction` and call it
  after repair/VNS block integration.

This was a new branch-owned solver module, not a CVRP hard-code in Scion core.

### Gates and Protocol

| Gate / stage | Result |
|---|---|
| Schema preview | pass |
| Target/action permission preview | pass |
| Contract preview | pass |
| Algorithm smoke | pass |
| Contract | pass |
| Verification | pass |
| Canary | passed |
| Screening metrics | `metrics/810ccf39-282b-4387-97b0-f7e4b0efd418.json` |
| Decision | `continue_explore` |

Screening evidence:

- 12 cases, 24 valid pairs, 0 failed pairs.
- Case-level: 0 wins, 0 losses, 12 ties.
- Pair-level: 1 win, 1 loss, 22 ties.
- Median delta 0.0, CI [0.0, 0.0].
- Runtime confidence low cached champion but sufficient; median runtime ratio
  1.00006; runtime regression rate 0.5.
- Runtime budget diagnostic: saturation ratio 1.0191.

Telemetry:

- Guard passed.
- `post_repair_route_compaction` activation observed in 24/24 pairs.
- Effect positive in 6/24 pairs by phase-improvement and phase-best-delta
  mechanism fields.
- Case-level pair signal: win on `E-n76-k8.vrp` and loss on `A-n39-k5.vrp`,
  but each case remained aggregate tie.

Decision:

- Not promoted because screening win-rate failed and objective effect was zero.
- Not abandoned because branch had weak-positive pair-level signal without
  case-level regression.
- Retained checkpoint:
  `5a1606ff-35c4-4207-bf9e-e5d70171f785`.

Assessment: this is the run's useful outcome. It is not validation-grade, but it
is a real weak-positive research signal and a differentiated direction worth
one same-branch refinement or a controlled 8R follow-up after framework
mechanism cleanup.

## Research Quality Assessment

### Were Hypotheses Based on Feedback?

Yes.

- R1 had no prior feedback and selected a plausible local-search gap from active
  solver facts.
- R2 used R1's runtime pressure and weak local effect to shift to repair-route
  count control.
- R3 used R1/R2 failures to make the repeated string-exchange idea more
  selective. This was a reasonable but marginal near-duplicate follow-up.
- R4 used three failed/weak branches to move away from another homogeneous
  local-search or repair-bias change and create a route-compaction module.

The agent did not behave like a blank-prompt generator. It used screening and
runtime feedback, but it still spent one round on a near-duplicate mechanism
family.

### Did It Fit Scion's Generic Combinatorial-Optimization Framework?

Yes, with the expected problem-owned CVRP vocabulary.

All hypotheses stayed under `solver_design`, which is the declared active
research boundary. They modified branch-owned solver modules under
`policies/baseline_modules/` or the branch solver scheduler, not generic Scion
`core`, `proposal`, `contract`, `protocol`, `runtime`, or `governance` code.

The proposals mention CVRP route, depot, capacity, and fleet terms. That is
appropriate here because those facts come from adapter/problem-owned active
solver facts and problem-owned solver-design files. There is no evidence from
the patches or artifacts that CVRP-specific semantics leaked into Scion generic
core.

### Did It Produce Effective Research?

Yes, but not promotion-grade research.

- No branch reached validation or frozen.
- No champion promotion occurred.
- Three branches produced mechanism activation/effect but regressed at
  screening.
- One branch produced a weak-positive retained checkpoint: no case losses,
  pair-level positive signal, and activation/effect telemetry.

The negative branches are still useful:

- R1 and R3 show `string_exchange_vns` can be active and internally positive but
  is not reliable enough under current runtime budget.
- R2 shows route-count-aware repair can create pair wins but has case-level
  downside on `B-n52-k7.vrp`.
- R4 gives the next branch-local research direction: post-repair route
  compaction should be refined, bounded, or integrated more selectively rather
  than replaced with another local-search operator.

## Framework Behavior Audit

### Quality Blocks

No valid-run quality block occurred:

- `quality_blocks=0`
- `quality_block_ledger=[]`
- `model_repair_failures=0`
- `telemetry_failed_experiments=0`

The earlier invalid run's API-key proposal blocks are an environment/provider
incident and should not be used as solver or framework-quality evidence for
this run.

### Proposal Attempts

The valid run consumed exactly four proposal attempts and produced exactly four
formal screened candidates. There were no non-effective screenings, no repair
attempts, and no infra attempts. This is a healthy run-control signal.

### Tool Selection

Observed `tool_selection_ledger` aggregate:

| Selected tool | Count |
|---|---:|
| `memory.query` | 8 |
| `feedback.query_screening` | 8 |
| `feedback.query_runtime` | 8 |
| `context.read_algorithm_file` | 6 |
| `context.read_branch_state` | 4 |
| `context.read_surface` | 1 |
| `stop` | 12 |

Important details:

- `default_triad_satisfied=true` in sessions, but
  `deterministic_prefetch_plan_id=none`. The framework records the field but
  still asks the LLM to select the default triad.
- `tool_result_novelty` is now useful: early feedback was empty, later feedback
  was new, and repeated code-phase file reads were `summary_only` or
  duplicate receipts.
- Duplicate file reads were often compact receipts, which is a real improvement
  over blindly injecting full duplicate content.
- The repeated stop calls remain pure planner overhead.

Rawls audit read: tools did not block the agent. The agent needed memory,
screening, runtime, active facts, problem summary, source files, branch state,
previews, and smoke. The issue is not tool existence; it is that deterministic
default information needs are still routed through 47 LLM tool-selection calls.

### Telemetry Identity Repair

No telemetry identity repair failure occurred in this run. All code sessions
passed schema preview, target permission preview, contract preview, and smoke.
Formal telemetry guards passed for all four mechanisms.

R2 smoke had an advisory `activation_not_observed_diagnostic` while still
passing. Formal screening later observed `route_count_aware_repair` activation
and effect, so the advisory did not block research and should remain a tainted
diagnostic signal rather than a quality block.

### Runtime Evidence and Fresh Champion

Runtime evidence handling was conservative and appropriate:

- R1 had high/sufficient runtime evidence with fresh champion comparisons.
- R2 and R3 used cached champion runtime; aggregate runtime was excluded and
  treated as proposal/audit guidance only.
- R4 had low cached champion confidence but sufficient runtime pairs; runtime
  still remained non-standalone and proposal-guidance only.
- `fresh_champion_required_count=0`.

This is aligned with v3: runtime did not bypass objective evidence, and runtime
aggregate exclusion did not stop the agent from receiving useful audit/proposal
feedback.

### Lifecycle Second-Decision Risk

The event log records both protocol decisions and lifecycle/scheduler follow-up
events. This is coherent but easy to misread:

- R1-R3 protocol decision was `abandon`; lifecycle archived lineage and
  scheduler opened a clean fork.
- R4 protocol decision was `continue_explore`; lifecycle retained a weak-positive
  checkpoint and scheduler metadata still says `create_branch` /
  `new_exploration_slot_available`.

There is no evidence of a conflicting second decision in this run, but the
artifact shape is a readability risk. Human readers can confuse "scheduler
next action: create branch" with "candidate action: promote/abandon". Reports
and status payloads should more explicitly separate:

1. protocol result,
2. branch lifecycle result,
3. scheduler next action,
4. final branch state and checkpoint state.

## Next-Step Recommendation

Do not move directly to 12R. The run is valid and unblocked, but one weak-positive
screening checkpoint is not enough to justify a long solver-quality run.

Recommended path:

1. Make small Scion mechanism changes first.
2. Run a controlled 8R as a framework/search-trajectory observation.
3. Only consider 12R after 8R shows repeated weak-positive retention,
   a validation queue, or an actual promotion candidate.

Mechanism changes should stay Scion-level, not CVRP algorithm hard-coding:

- Implement deterministic prefetch or bundled feedback summary for the default
  `memory.query + feedback.query_screening + feedback.query_runtime` packet.
  The ledger exists; `deterministic_prefetch_plan_id` is still `none`.
- Convert repeated `stop` planner calls into deterministic terminal conditions
  when required context is satisfied.
- Keep duplicate-read receipts, and extend them across same-branch retry and
  sibling-branch context where digests match.
- Add a material-difference explanation field when a new clean fork repeats a
  recently abandoned mechanism family. Do not forbid repetition; require the
  proposal to say why it is not the same failed idea.
- Split context profiles further: new branch, same-branch weak-positive refine,
  near-duplicate repair, runtime-pressure diagnostic, code retry, and
  construction/local-search/repair targets.
- In lifecycle artifacts, explicitly separate protocol decision, lifecycle
  decision, scheduler next action, and final branch/checkpoint state.
- For weak-positive branches with low cached champion runtime pressure, consider
  a Scion protocol-level fresh-champion refresh trigger before validation or a
  longer run. This should be generic runtime-evidence policy, not a CVRP solver
  rule.

If an 8R is run immediately without these fixes, it is still likely valid, but
it will spend unnecessary LLM budget rediscovering deterministic tool choices
and may produce another ambiguous lifecycle/status audit trail.

## Unverified / Not Replayed

- I did not rerun the campaign or replay solver metrics; conclusions are from
  persisted artifacts, SQLite, LLM traces, prompt manifests, self-checks, and
  metrics JSONs.
- I did not inspect generated branch workspaces beyond artifact refs and patch
  traces. For abandoned branches, the authoritative code-change evidence used
  here is the `code` LLM trace response plus DB/metric outcomes.
- `transcript.json` files had empty `entries`; `compact_transcript` in
  `output.json` was used for tool-observation sequence.
- No source code was modified for this report.
