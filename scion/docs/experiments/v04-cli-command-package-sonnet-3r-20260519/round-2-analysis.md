# Round 2 Analysis

Experiment: `v04-cli-command-package-sonnet-3r-20260519T073734Z`

Round boundary used here:
- Prior boundary: round 1 code ended at `20260519T074227262930_code_fb148676ee_299bf10c.json`.
- Round 2 detailed scope: `20260519T074340...` through final failure at `2026-05-19T07:48:03`.
- Next boundary: round 3 starts at `20260519T074803766654_tool_selection_1fa9e3dd52_4793c32b.json`; not analyzed in detail.

## Timeline

- `07:43:40` - Round 2 hypothesis session starts (`fd357287-65c0-4bbc-8942-c89fc4453ab5`). Required preface tools load solver surface, problem summary, algorithm file list, active solver design, and call graph.
- `07:43:40` to `07:44:12` - Hypothesis tool-selection loop (`20260519T074340...` to `20260519T074406...`) reads `baseline_algorithm.py`, `local_search.py`, and `destroy_repair.py`. A later selected read of `construction.py` is not executed because the solver-design file-read budget is reserved.
- `07:44:12` to `07:44:40` - Hypothesis generation (`20260519T074412554057_hypothesis_54a01fc9d4_a6eed53e.json`) proposes a VNS cross-route tail-swap mechanism in `policies/baseline_modules/local_search.py`.
- `07:44:53` - Code session starts (`3626e95a-ba9e-4c9d-a176-6af44266411e`). It reuses required context and reads `local_search.py`, `destroy_repair.py`, and `acceptance.py`.
- `07:45:23` to `07:46:07` - Code attempt 0 (`20260519T074523229259_code_4f49578988_a5d1c4af.json`) emits a full replacement for `local_search.py`.
- `07:46:13` - Contract preview passes, algorithm smoke fails: no activation evidence for declared mechanism `vns_cross_route_tail_swap`.
- `07:46:13` to `07:46:56` - Repair attempt 1 (`20260519T074613099236_code_ea1d2ca896_6faaaa7a.json`) adds activation-oriented telemetry.
- `07:47:02` - Contract preview passes, algorithm smoke fails: no effect evidence for `vns_cross_route_tail_swap`.
- `07:47:02` to `07:47:57` - Repair attempt 2 (`20260519T074702127205_code_a885f979e7_943f6647.json`) adds mechanism-scoped `record_move` calls but removes the prior activation telemetry.
- `07:48:03` - Contract preview passes, algorithm smoke fails again: no activation evidence. The session fails closed with `code_generation_failed`.

## Prior Feedback In Context

Round 1 feedback did enter round 2, but only partially:

- In the round 2 hypothesis prompt, `Experiment History - This Branch` shows `Round 1 [FAILED_AGENT_QUALITY_BLOCKED]` and the failed capacity-first repair hypothesis targeting `policies/baseline_modules/destroy_repair.py`.
- The system-side `Agent Quality Feedback` also contains a round 1 quality block: `algorithm_smoke_failure; target=...destroy_repair.py; ... solver runtime audit reported solver_algorithm_errors=1`, but it is truncated before the useful object-model repair guidance.
- The full round 1 failure in `926ff944.../output.json` says `_Solution` has `.instance` and does not expose `._instance`; that detailed repair guidance is not visible in round 2 hypothesis context.
- `feedback.query_screening` returns `0 of 0`, and `feedback.query_runtime` says no safe screening-derived runtime feedback is available. The generated runtime diagnosis is the generic `solver_design_not_selected`, not the concrete round 1 object-model failure.

Agent absorption was therefore shallow:

- It avoided an exact repeat of the round 1 capacity-first regret repair signature, likely because the occupied novelty signature was present.
- It moved to a different target (`local_search.py`) and a different mechanism family.
- It did not make strong use of the actual failure cause, and it did not perform enough semantic grounding on the existing VNS implementation before proposing the next mechanism.

## Tool Calls

Hypothesis-stage tool selections and outcomes:

- Required preface:
  - `context.list_surfaces` - one active research surface: `solver_design`.
  - `context.read_problem` - adapter/spec-rendered problem summary.
  - `context.list_algorithm_files` - allowlisted solver-design files.
  - `context.read_active_solver_design` - active snapshot with entrypoint, call graph, mechanisms, provenance.
  - `context.read_solver_call_graph` - active call graph.
- Planner-selected reads:
  - `20260519T074340...`: `context.read_algorithm_file` for `policies/baseline_algorithm.py`; executed.
  - `20260519T074348...`: `context.read_algorithm_file` for `policies/baseline_modules/local_search.py`; executed.
  - `20260519T074401...`: `context.read_algorithm_file` for `policies/baseline_modules/destroy_repair.py`; executed.
  - `20260519T074406...`: selected `policies/baseline_modules/construction.py`, but the transcript stops file reads before executing it due `solver_design_algorithm_file_read_budget_reserved`.
- Fallback/required observations:
  - `memory.query` - search memory says `solver_design/modify: 1` and labels it over-explored.
  - `feedback.query_screening` - no screening rows.
  - `feedback.query_runtime` - no safe runtime feedback; diagnosis remains `solver_design_not_selected`.
  - `context.read_surface` - surface interface for `solver_design`.
  - `proposal.schema_preview` and `proposal.target_permission_preview` - both pass.

Code-stage tool selections and outcomes:

- Required context is reloaded in the code session.
- Planner-selected reads:
  - `20260519T074453...`: `local_search.py`; executed.
  - `20260519T074458...`: `destroy_repair.py`; executed.
  - `20260519T074505...`: `acceptance.py`; executed.
  - `20260519T074511...`: selected `construction.py`, but not executed due budget reserve.
  - `20260519T074517...`: selected `local_search.py` again, but by then the prior read already exists and the code context proceeds.
- Code-required observations:
  - `context.read_surface` is compacted to an already-read reference.
  - `context.read_branch_state` reports branch `b717b08e-0f71-4709-b735-ba1325354870`, `state=explore`, `retry_count=0`.
- Self-check chain:
  - Attempt 0: `proposal.contract_preview` passes; `proposal.algorithm_smoke` fails activation.
  - Attempt 1: `proposal.contract_preview` passes; `proposal.algorithm_smoke` fails effect.
  - Attempt 2: `proposal.contract_preview` passes; `proposal.algorithm_smoke` fails activation.

## Hypothesis

Final hypothesis fields:

- `change_locus`: `solver_design`
- `action`: `modify`
- `target_file`: `policies/baseline_modules/local_search.py`
- `mechanism_changes`:
  - add `vns_cross_route_tail_swap`
  - modify `vns_local_search_neighborhoods`
- `expected_telemetry`:
  - activation: `solver_algorithm_active`, `solver_algorithm_phase_runtime_ms`
  - activity: `solver_algorithm_move_attempts`, `solver_algorithm_search_iterations`
  - effect: `solver_algorithm_improving_moves`, `solver_algorithm_best_delta`, `solver_algorithm_total_distance`, `solver_algorithm_fleet_violation`
  - budget: `solver_algorithm_elapsed_ms`, `solver_algorithm_stop_reason`

Grounding assessment:

- The hypothesis is not well grounded. It claims the existing VNS lacks a cross-route segment exchange / tail-swap operator.
- The current `local_search.py` already has `_two_opt_star`, included in `_default_vns_operators`, and it constructs exactly:
  - `new_left = left.customers[:left_pos] + right.customers[right_pos:]`
  - `new_right = right.customers[:right_pos] + left.customers[left_pos:]`
  - with capacity checks and distance-improvement acceptance.
- That is already a cross-route suffix/tail exchange. The proposed `_cross_route_tail_swap` is mostly a renamed, capped, and in later attempts narrower variant of existing `_two_opt_star`.
- The hypothesis also frames `fleet_violation` as if it were capacity imbalance. In this adapter, `fleet_violation = max(0, route_count - allowed_routes)`. The proposed non-degenerate tail swaps generally preserve route count, and they operate inside a path that rejects infeasible candidates. The claimed direct fleet-violation effect is therefore weak.

The agent had enough context to catch this: `local_search.py` was fully read before hypothesis generation, and the code prompt included the existing `_two_opt_star` body. It still did not return `premise_check=duplicate`.

## Code Attempts

Attempt 0: `20260519T074523229259_code_4f49578988_a5d1c4af.json`

- Patch path: `policies/baseline_modules/local_search.py`
- `additional_changes`: none
- Declared mechanisms: `vns_cross_route_tail_swap` add, `vns_local_search_neighborhoods` modify.
- Body changes:
  - Adds `_cross_route_tail_swap`.
  - Appends `_cross_route_tail_swap` to `_default_vns_operators()`.
  - Uses capacity checks and distance delta before accepting.
- Telemetry binding:
  - No mechanism-specific activation telemetry.
  - The only existing `_vns` telemetry remains generic phase `"vns"`.
- Result:
  - Static contract preview passes.
  - Smoke fails: no activation evidence at `solver_algorithm_context_records.vns_cross_route_tail_swap_iterations` or `solver_algorithm_phase_runtime_ms.vns_cross_route_tail_swap`.

Attempt 1: `20260519T074613099236_code_ea1d2ca896_6faaaa7a.json`

- Patch path: `policies/baseline_modules/local_search.py`
- `additional_changes`: none
- Declared mechanisms unchanged.
- Body changes:
  - Adds `_TAIL_SWAP_MAX_SPLITS`.
  - Adds mechanism activation records at the end of `_cross_route_tail_swap`:
    - `context.record_phase("vns_cross_route_tail_swap", elapsed)`
    - `context.record_iteration("vns_cross_route_tail_swap", iterations)`
- Telemetry binding:
  - Activation is now bound to the guard paths through `record_phase` and `record_iteration`.
  - Effect is still not bound: no mechanism-scoped `record_move(... accepted=1, delta>0, best_improved=True ...)`.
- Result:
  - Static contract preview passes.
  - Smoke advances to a different failure: no effect evidence at `solver_algorithm_phase_improvement_counts.vns_cross_route_tail_swap` or `solver_algorithm_phase_best_delta.vns_cross_route_tail_swap`.

Attempt 2: `20260519T074702127205_code_a885f979e7_943f6647.json`

- Patch path: `policies/baseline_modules/local_search.py`
- `additional_changes`: none
- Declared mechanisms unchanged.
- Body changes:
  - Adds mechanism-scoped `context.record_move("vns_cross_route_tail_swap", ...)` on accepted and rejected candidate split trials.
  - Removes the prior `record_phase` and `record_iteration` activation records from attempt 1.
- Telemetry binding:
  - Effect is attempted through `record_move`, but only if the operator reaches split loops and finds a positive delta.
  - Activation is no longer bound to the guard's activation paths.
- Result:
  - Static contract preview passes.
  - Smoke fails again on activation, because the paths expected by the guard are absent.

No attempt writes `additional_changes`. If accepted, the operator would be connected through `_default_vns_operators()` and the existing scheduler import path. The helper is not physically inert, but it is semantically duplicative and its trigger/effect is too narrow for the declared mechanism evidence.

## Failure Chain

The critical chain is:

1. Hypothesis declares new mechanism `vns_cross_route_tail_swap`.
2. Telemetry guard derives mechanism-specific evidence paths from that id:
   - activation: `solver_algorithm_context_records.vns_cross_route_tail_swap_iterations`, `solver_algorithm_phase_runtime_ms.vns_cross_route_tail_swap`
   - effect: `solver_algorithm_phase_improvement_counts.vns_cross_route_tail_swap`, `solver_algorithm_phase_best_delta.vns_cross_route_tail_swap`
3. Attempt 0 implements an operator but emits no mechanism-specific telemetry; activation is not observed.
4. Repair feedback is effective and specific: it tells the agent to emit positive runtime evidence via the activation paths.
5. Attempt 1 follows that feedback and reaches the next guard: effect is not observed.
6. Repair feedback again is specific: emit positive effect evidence via `phase_improvement_counts` and `phase_best_delta`.
7. Attempt 2 tries to satisfy effect with `record_move`, but regresses activation by deleting `record_phase` and `record_iteration`.
8. The final guard correctly fails closed and the branch is rejected before any candidate is promoted or screened.

Why activation was not observed in the final attempt:

- The final code no longer writes either activation path the guard names.
- `record_move` populates move/effect fields, not `solver_algorithm_context_records.vns_cross_route_tail_swap_iterations` or `solver_algorithm_phase_runtime_ms.vns_cross_route_tail_swap`.
- The operator is last in the VNS list. It is reachable, but only after earlier operators fail to improve; if earlier neighborhoods keep resetting VNS or the smoke instance does not need this move, mechanism-specific records can easily remain absent unless activation is recorded independently.

Why effect was not observed in attempt 1:

- Attempt 1 records phase and iteration but never records a mechanism-scoped accepted/improving move.
- Even if the operator is called, the proposed move is a duplicate of `_two_opt_star` and may not have unique positive effect on the smoke instance.
- Later attempts exclude degenerate split positions and generally preserve route count, so the claimed fleet-violation effect is not a reliable runtime effect.

## Design Compliance

Framework behavior:

- Correct fail-closed behavior: no round 2 candidate passed algorithm smoke, and the branch was rejected before code generation/promotion.
- Correct boundary control: all generated patches targeted the active solver-design package, not adapter/protocol/Decision files.
- Static contract preview did its job narrowly: the replacement module was syntactically/import-wise acceptable and stayed within editable paths.
- Runtime smoke did the more important job: it caught that declared mechanisms were not activated/effective in runtime telemetry.

Agent behavior:

- The hypothesis stayed on `solver_design`, but its mechanism was not semantically novel.
- The code generator used the correct file path and connected the helper into `_default_vns_operators()`.
- It did not preserve previously fixed telemetry while addressing the next telemetry failure.
- It did not use `premise_check=duplicate` despite the existing `_two_opt_star` implementation.

Contract/preview gap:

- Contract preview does not detect "renamed duplicate of an existing neighborhood".
- Contract preview also does not validate mechanism-specific activation/effect bindings before smoke. That is acceptable if smoke remains mandatory, but it means the repair loop spends attempts on avoidable telemetry issues.

## Root Causes

1. Semantic duplicate missed during hypothesis grounding.
   The existing `_two_opt_star` is already a cross-route tail/suffix exchange. The agent read the file but still proposed a near-duplicate mechanism.

2. Objective semantics were underexposed.
   The prompt says fleet violation is high priority, but the agent reasoned as if it were route capacity imbalance. In the adapter, fleet violation is route-count excess over allowed/BKS routes.

3. Mechanism telemetry binding was too implicit at hypothesis time.
   The hypothesis listed generic telemetry fields. The guard enforced mechanism-specific paths derived from the mechanism id. The agent only learned the exact paths after failing smoke.

4. Repair prompts did not require monotonic preservation of fixed guard categories.
   Attempt 1 fixed activation. Attempt 2 chased effect but removed activation, causing a regression to the original failure class.

5. The declared effect was brittle.
   A local-search operator that only records effect on a strict improving accepted move needs a smoke instance where the new move actually fires. Here the operator was duplicative, last in VNS order, and often no-op.

6. Prior round feedback was visible but not sufficiently actionable.
   Round 1 appeared as a failed history/signature and a truncated quality block. The full root-cause guidance did not enter round 2 hypothesis context.

## Recommended Fixes

1. Add a semantic-neighborhood grounding check for solver-design hypotheses.
   Surface summaries should label `_two_opt_star` as "cross-route suffix/tail exchange" and force a `premise_check=duplicate` path when a proposed mechanism only renames or caps an existing neighborhood.

2. Expose objective definitions in the hypothesis prompt.
   Include a short statement such as: `fleet_violation is max(0, route_count - allowed_routes), not capacity overload; capacity overload is infeasible and rejected.` This would have invalidated the claimed capacity-balancing/fleet-violation mechanism.

3. Emit mechanism telemetry requirements before code generation.
   For each `mechanism_changes[].id`, show the exact activation/effect paths expected by telemetry guard, not only generic `expected_telemetry` categories.

4. Make repair feedback monotonic.
   On the second repair prompt, include a small checklist: "keep activation evidence from the previous attempt; additionally add effect evidence." The code agent should be penalized or blocked for removing previously satisfying telemetry bindings.

5. Add a telemetry binding preview.
   Before runtime smoke, statically or dynamically check whether declared mechanism ids appear in `record_phase`, `record_iteration`, and `record_move` calls with the exact id.

6. Improve tainted prior feedback compaction.
   Do not truncate previous round root-cause guidance before the key object-model or telemetry repair clauses. A compact structured form is better than a long clipped sentence.

7. Improve smoke/problem exposure for declared local-search effects.
   Either provide a deterministic synthetic case where the declared local-search mechanism can uniquely activate and improve, or make the agent declare a no-op-safe mechanism without effect claims. If the mechanism cannot produce positive effect in the controlled smoke, failing closed is correct.

8. Keep `additional_changes` guidance but do not require it here.
   This round's candidate did not need scheduler wiring because `_default_vns_operators()` is already imported and called by the scheduler. The problem was not missing integration; it was duplicate semantics plus broken telemetry binding.
