# Round 3 Analysis

Experiment: `v04-cli-command-package-sonnet-3r-20260519T073734Z`

Scope: round 3, from `20260519T074803...tool_selection` through
`20260519T075151...code`; no source files were modified by this audit.

## Timeline

- `07:48:03`: round-3 hypothesis session `f54a32a8-...` starts with required context preface: `context.list_surfaces`, `context.read_problem`, `context.list_algorithm_files`, `context.read_active_solver_design`, and `context.read_solver_call_graph`.
- `07:48:03`-`07:48:43`: planner selects solver-design file reads. It successfully reads `policies/baseline_algorithm.py`, `policies/baseline_modules/local_search.py`, and `policies/baseline_modules/destroy_repair.py`. It also selects `construction.py`, but the transcript records no successful construction observation; instead it stops planner-selected reads with `solver_design_algorithm_file_read_budget_reserved`.
- `07:48:43`: fallback context reads `memory.query`, `feedback.query_screening`, and `feedback.query_runtime`. Screening returns `0 of 0`; runtime feedback says no safe screening-derived runtime feedback is available.
- `07:48:43`-`07:49:16`: hypothesis trace `20260519T074843905541_hypothesis_a1fb7e8181_8f77d700.json` proposes modifying `policies/baseline_modules/scheduler.py`.
- `07:49:16`: after hypothesis generation, the session reads `scheduler.py`, then reads the `solver_design` interface and passes schema/target-permission preview. This means the target file was grounded after the hypothesis was already drafted.
- `07:49:24`: code session `3c335532-...` starts. It repeats required context, reads `baseline_algorithm.py`, `destroy_repair.py`, and `local_search.py`; `construction.py` is again selected but skipped by read-budget reserve. It later reads `scheduler.py` as required grounding, reads surface info compactly, and reads branch state.
- `07:50:07`: code attempt 1, `20260519T075007848880_code_65b3792ce7_edf35742.json`, replaces `scheduler.py`. Static contract preview passes; algorithm smoke fails telemetry activation for `adaptive_weight_reset_on_feasibility`.
- `07:51:01`: code attempt 2, `20260519T075101218929_code_874f349fd0_3bfde404.json`, retries with the activation failure in prompt. Static contract preview passes; algorithm smoke now fails effect evidence for the same mechanism.
- `07:51:51`: code attempt 3, `20260519T075151054592_code_b35d334968_5ec46fda.json`, retries with the effect failure in prompt. Static contract preview passes; algorithm smoke fails activation again.
- `07:52:42`: patch self-check fails closed after latest preview failure. `run.log` records the round rejected with `TELEMETRY_MECHANISM_ACTIVATION_NOT_OBSERVED`; campaign ends with `max_rounds_exhausted`, `experiments: 0`, champion unchanged.

## Prior Feedback In Context

Round-3 hypothesis prompt did include an `Experiment History - This Branch` section with Round 1 and Round 2 hypotheses and the broad status `FAILED_AGENT_QUALITY_BLOCKED`. It did not include the actionable failure detail in a usable form: both `failed_at` lines are clipped after `algorithm...`.

The detailed prior failures are present in `campaign_summary.json` and `run.log`:

- Round 1 failed inside solver smoke with `solver_algorithm_errors=1` and object-model repair guidance: `_Solution` has `.instance`, `_Route` objects, route methods, no `._instance`, and route edits must rebuild indexes.
- Round 2 failed telemetry guard activation for `vns_cross_route_tail_swap`, requiring positive evidence at `solver_algorithm_context_records.vns_cross_route_tail_swap_iterations` or `solver_algorithm_phase_runtime_ms.vns_cross_route_tail_swap`.

The agent absorbed only the coarse pattern: avoid the previously targeted files and move to `scheduler.py`. It did not absorb the true failure modes. The round-3 hypothesis repeated a conditional mechanism whose activation was not guaranteed on smoke, and the first code attempt repeated the exact telemetry-binding failure class from Round 2.

Code-attempt retry prompts were better, but only for failures inside round 3. Attempt 2 saw the prior activation failure and added exact mechanism telemetry. Attempt 3 saw the effect failure but regressed activation by restoring the impossible transition condition.

## Tool Calls

Hypothesis phase tool selections:

- `20260519T074803...`: selected `context.read_algorithm_file` for `policies/baseline_algorithm.py`; result ok.
- `20260519T074809...`: selected `context.read_algorithm_file` for `policies/baseline_modules/local_search.py`; result ok.
- `20260519T074817...`: selected `context.read_algorithm_file` for `policies/baseline_modules/destroy_repair.py`; result ok.
- `20260519T074825...`: selected `context.read_algorithm_file` for `policies/baseline_modules/construction.py`; no successful observation was recorded because file reads were stopped for budget reserve.
- Required/fallback observations then supplied active solver-design snapshot, call graph, memory, empty screening feedback, and no safe runtime feedback.
- `scheduler.py` and `context.read_surface` were read only after `generate_hypothesis`.

Code phase tool selections:

- `20260519T074924...`: selected `baseline_algorithm.py`; result ok.
- `20260519T074936...`: selected `destroy_repair.py`; result ok.
- `20260519T074944...`: selected `local_search.py`; result ok.
- `20260519T074950...`: selected `construction.py`; skipped by read-budget reserve.
- `20260519T075002...`: selected `scheduler.py`; skipped as already succeeded after required grounding read.
- Required code tools then read compact surface info and branch state.

Context was sufficient for basic API adherence in code generation, but not sufficient for the hypothesis premise. The target file was not read before the hypothesis; detailed prior failure repair hints were clipped; and the problem/objective exposure did not make the key invariant obvious enough: capacity violation is invalid, while objective `fleet_violation` is route-count excess over `allowed_routes`/`bks_routes`.

## Hypothesis

Final hypothesis: implement two-phase ALNS scheduling in `scheduler.py`. Phase 1 handles `fleet_violation > 0` with high SA temperature; on first feasibility crossing, reset adaptive operator weights and switch to a tighter distance phase.

Declared mechanisms:

- `alns_phase_gate` add
- `adaptive_weight_reset_on_feasibility` add
- `sa_temperature_phase_switch` modify

The hypothesis is only partially grounded. It is grounded in the existence of ALNS, adaptive weights, SA, and scheduler control. It is not grounded in the runtime state semantics:

- The active scheduler's `_initial_solution()` returns a capacity-feasible `_Solution` or raises.
- The ALNS loop rejects `not candidate.is_feasible()`.
- `baseline_algorithm.py` passes `max_routes=instance.allowed_routes or instance.bks_routes`, and scheduler rejects `len(candidate.routes) > max_routes`.
- Adapter `fleet_violation` is route-count excess, not per-route capacity violation.

Therefore the proposed "infeasible era" and "first feasibility crossing" do not normally exist in the active algorithm body. This is not just a short-smoke weakness; it is a premise mismatch with the baseline invariants.

## Code Attempts

All three attempts target only `policies/baseline_modules/scheduler.py`. No `additional_changes` field is present in the code responses. All three echo the approved `mechanism_changes`.

Attempt 1: `20260519T075007848880_code_65b3792ce7_edf35742.json`

- Adds `_fleet_violation(solution)` as count of routes whose load exceeds capacity.
- Initializes `in_phase2 = (_fleet_violation(best) == 0)` and `weight_reset_done = in_phase2`.
- Records `record_phase("phase2_transition", 0.0)` only inside `if not in_phase2 and _fleet_violation(best) == 0`.
- Fails activation because the initial solution is already capacity-feasible, so `weight_reset_done` is true and the declared mechanism id is never recorded. It also records `phase2_transition`, not `adaptive_weight_reset_on_feasibility`.

Attempt 2: `20260519T075101218929_code_874f349fd0_3bfde404.json`

- Sets `_in_phase2 = False` unconditionally, so the first ALNS iteration with `_fleet_violation(best) == 0` fires the reset.
- Records `context.record_phase("adaptive_weight_reset_on_feasibility", ...)` and `context.record_iteration("adaptive_weight_reset_on_feasibility", ...)`.
- This fixes activation, but there is no `context.record_move("adaptive_weight_reset_on_feasibility", ..., delta=..., best_improved=...)`. Runtime guard therefore finds no positive effect evidence at `solver_algorithm_phase_improvement_counts.adaptive_weight_reset_on_feasibility` or `solver_algorithm_phase_best_delta.adaptive_weight_reset_on_feasibility`.

Attempt 3: `20260519T075151054592_code_b35d334968_5ec46fda.json`

- Reverts to `in_phase2 = (_fleet_violation(best) == 0)` and `weight_reset_done = in_phase2`, so start-feasible smoke cases again suppress activation.
- Records `context.record_phase("adaptive_weight_reset_on_feasibility", ...)` only inside the impossible transition branch.
- Does not record exact mechanism iterations and still does not record mechanism effect moves.
- Fails activation again.

These were real algorithm-body candidate edits to `_ALNSVNSSolver.solve`, not adapter/protocol edits. However, because algorithm smoke failed closed, none were accepted into the branch baseline.

## Failure Chain

The contract/preview/smoke chain behaved as follows:

- Schema and target permission preview passed after hypothesis.
- Static contract preview passed for every code attempt.
- Algorithm smoke ran one runtime smoke case, then invoked telemetry guard.
- Telemetry guard used surface mechanism probes from `problem-v1.yaml`, not only the hypothesis' generic `expected_telemetry`.
- Required activation paths were `solver_algorithm_context_records.{mechanism}_iterations` and `solver_algorithm_phase_runtime_ms.{mechanism}`.
- Required effect paths were `solver_algorithm_phase_improvement_counts.{mechanism}` and `solver_algorithm_phase_best_delta.{mechanism}`.
- The retry loop provided the immediately prior smoke failure in the next code prompt.
- After three code attempts, latest preview failure caused fail-closed rejection.

Why `adaptive_weight_reset_on_feasibility` was declared but not observed:

- Primary cause: trigger condition mismatch. Attempts 1 and 3 require transition from capacity-infeasible to capacity-feasible best solution, but the scheduler starts from a capacity-feasible solution and rejects infeasible candidates.
- Objective mismatch: candidate `_fleet_violation` measures capacity overload, while adapter objective `fleet_violation` measures route-count excess. The declared mechanism is tied to the wrong state variable.
- Telemetry binding gap: attempt 1 records no exact mechanism id; attempt 2 records activation but no effect; attempt 3 loses activation again.
- Smoke weakness is secondary. A stronger smoke with a route-count-hard instance would still not exercise a capacity-infeasible phase unless the algorithm intentionally allowed invalid intermediate states. The current baseline does not.
- Guard design is correct to fail the declaration, but its repair hints are too narrow. "Emit positive runtime evidence" led the agent to add record calls, not to question whether the mechanism can execute or has a meaningful effect path.

## Design Compliance

Compliant behavior:

- Framework failed closed. No experiment was promoted; no champion update; no accepted branch patch.
- Code attempts stayed inside the solver-design package and targeted an editable algorithm file.
- Static API contract protected frozen adapter/runtime/protocol files.
- Runtime smoke caught a semantic telemetry failure that static preview missed.

Weak compliance / design gaps:

- Hypothesis generation was allowed before reading the chosen target file. The later `scheduler.py` read improved post-hoc grounding but could not correct the already-generated hypothesis.
- File-read budgeting silently dropped `construction.py` even after planner selected it. The transcript records a skipped read, but the agent did not get an explicit "you selected this but it was not read" reasoning obligation.
- Static contract preview did not fail or warn when mechanism changes implied exact surface probes but code lacked exact mechanism records. Attempt 1 passed static preview despite recording `phase2_transition` instead of the declared id.
- Runtime guard requires effect evidence for all declared mechanisms on this surface. That is defensible for fail-closed evidence, but non-move mechanisms such as weight reset need clearer instructions on how to bind downstream improvements to the mechanism.

## Root Causes

1. **Wrong objective semantics.** The agent treated `fleet_violation` as capacity infeasibility. In the adapter, `fleet_violation = max(0, routes - allowed_routes)`; capacity violation is a hard invalid-output condition.
2. **Impossible phase transition.** The active scheduler constructs feasible solutions or raises, and the ALNS loop rejects infeasible candidates. The proposed feasibility crossing is not on the active path.
3. **Truncated prior failure context.** Round 1 object-model guidance and Round 2 exact telemetry activation failure were available in campaign artifacts but not in actionable form in the round-3 hypothesis prompt.
4. **Late target grounding.** `scheduler.py` was read after hypothesis generation, so the model proposed scheduler behavior before seeing the scheduler invariants.
5. **Telemetry repair myopia.** Retry prompts named missing fields, but the model treated this as a record-call placement problem rather than a mechanism-validity problem.
6. **Static/runtime contract gap.** Static preview did not enforce surface-declared mechanism probes strongly enough; runtime guard caught the issue only after generation.

## Recommended Fixes

- Put untruncated prior failure summaries into the next hypothesis prompt: failure class, exact mechanism id, exact missing runtime paths, and repair guidance. Do not reduce them to `algorithm...`.
- Require `target_file` or likely owner-file content before `generate_hypothesis` for `solver_design`, especially when the hypothesis names scheduler, acceptance, adaptive weights, or phase transitions.
- Make problem exposure explicit: `fleet_violation` is route-count excess over `allowed_routes`/`bks_routes`; capacity violation is invalid and cannot be used as a normal search phase unless the algorithm has an explicit internal-only relaxation and valid repair before output.
- Add a hypothesis-premise check for triggerability: if a declared mechanism activates only under a predicate, the prompt or preview should ask which smoke/current-path state can satisfy it.
- Strengthen static telemetry preview to expand surface mechanism probes from `mechanism_changes`, even when `expected_telemetry` uses generic fields. A patch that lacks exact `record_phase`/`record_iteration`/`record_move` calls for declared probes should fail before runtime smoke.
- For non-move mechanisms, add guard guidance or schema support for activation-only mechanisms, or require an explicit downstream effect binding such as "record accepted/improving phase-2 moves under the reset mechanism after activation."
- Adjust retry guidance to include causal diagnosis: "the current smoke did not activate because the predicate was false" when field absence comes from a skipped branch, not just "emit positive evidence."
- Consider adding a route-count-pressure smoke case if route-count mechanisms are desired. That will not rescue this capacity-feasibility hypothesis, but it would expose valid `fleet_violation` mechanisms.
- Keep the fail-closed policy. This run demonstrates it prevented a plausible-looking but unactivated mechanism from entering the branch.
