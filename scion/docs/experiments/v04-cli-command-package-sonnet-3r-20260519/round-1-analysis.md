# Round 1 Analysis

Scope: first Scion round only, ending at `20260519T074227262930_code_fb148676ee_299bf10c.json` and the corresponding failed session finalization at `2026-05-19T07:43:40`. Traces from `20260519T074340...` onward are round 2 and are intentionally excluded.

## Timeline

- `07:37:34` `ed28c780...` hypothesis session starts. Required context preface succeeds: `context.list_surfaces`, `context.read_problem`, `context.list_algorithm_files`, `context.read_active_solver_design`, `context.read_solver_call_graph`.
- `07:37:34` to `07:38:08` hypothesis planner selects file reads: `policies/baseline_algorithm.py`, `policies/baseline_modules/local_search.py`, `policies/baseline_modules/destroy_repair.py`.
- `07:38:14` planner next selects `policies/baseline_modules/acceptance.py`, but framework skips it with `solver_design_algorithm_file_read_budget_reserved`, switches to fixed fallback, and collects `memory.query`, `feedback.query_screening`, and `feedback.query_runtime`.
- `07:38:14` `20260519T073814154434_hypothesis_b30db83927_b73f0e01.json` generates the hypothesis.
- `07:38:41` grounding checks skip already-read solver-design context, then `context.read_surface`, `proposal.schema_preview`, and `proposal.target_permission_preview` pass. Session pauses as `partial_hypothesis_only` with `hypothesis_awaiting_approval`.
- `07:38:45` `926ff944...` code session starts for the approved hypothesis. It repeats the same required context preface and reads `baseline_algorithm.py`, `local_search.py`, and `destroy_repair.py`.
- `07:39:15` a planned read of another active file is stopped by the same solver-design file-read budget. Fixed fallback and selected-surface checks pass. Code-phase inspection skips a duplicate `read_algorithm_file`, compresses `read_surface`, and reads branch state: branch `b717b08e...`, state `explore`, retry counters zero.
- `07:39:29` first code generation: `20260519T073929603528_code_40d1fb4968_3c2ec70d.json`.
- `07:40:44` static `proposal.contract_preview` passes. `07:40:50` `proposal.algorithm_smoke` fails: no activation evidence for declared telemetry field `solver_algorithm_fleet_violation`.
- `07:40:50` second code generation: `20260519T074050115391_code_fb148676ee_8afbd93f.json`.
- `07:42:21` contract preview passes again. `07:42:27` algorithm smoke repeats the same telemetry activation failure.
- `07:42:27` third code generation: `20260519T074227262930_code_fb148676ee_299bf10c.json`.
- `07:43:40` contract preview still passes, but algorithm smoke reports `solver_algorithm_errors=1`. Session finalizes `failed` / `code_generation_failed`; `patch` remains null.

## Tool Calls

Hypothesis-stage tool selection:

| Time | Trace | Selected tool | Result |
| --- | --- | --- | --- |
| `07:37:34` | `20260519T073734947335_tool_selection_be06874096_08fc7b50.json` | `context.read_algorithm_file` `policies/baseline_algorithm.py` | Executed, returned allowlisted solver-design file. |
| `07:37:47` | `20260519T073747580200_tool_selection_26663e5aa2_a9da2d9a.json` | `context.read_algorithm_file` `policies/baseline_modules/local_search.py` | Executed. |
| `07:37:53` | `20260519T073753086675_tool_selection_75cdd9de79_7154fb05.json` | `context.read_algorithm_file` `policies/baseline_modules/destroy_repair.py` | Executed. |
| `07:38:08` | `20260519T073808321849_tool_selection_8651f1d1da_c76a2e8a.json` | `context.read_algorithm_file` `policies/baseline_modules/acceptance.py` | Not executed; skipped by `solver_design_algorithm_file_read_budget_reserved`. |

After the budget skip, fixed fallback skipped already-satisfied context tools and executed `memory.query`, `feedback.query_screening` (`0 of 0` rows), and `feedback.query_runtime` (`No safe screening-derived runtime feedback is available`). No fuse was observed. The key budget event was the reserved solver-design file-read budget.

Code-session tool selection before patch generation:

| Time | Trace | Selected tool | Result |
| --- | --- | --- | --- |
| `07:38:45` | `20260519T073845279235_tool_selection_d247a00817_5e1facc9.json` | `baseline_algorithm.py` | Executed. |
| `07:38:51` | `20260519T073851639725_tool_selection_091a8b55c9_63ebaf26.json` | `local_search.py` | Executed. |
| `07:38:59` | `20260519T073859777594_tool_selection_4ae793098f_59108a84.json` | `destroy_repair.py` | Executed. |
| `07:39:09` | `20260519T073909462150_tool_selection_3d08528aa0_a7b1fca5.json` | `construction.py` | Stopped before execution by file-read budget reservation. |
| `07:39:15` | `20260519T073915650270_tool_selection_df31e44d38_a4a473d7.json` | `destroy_repair.py` | Code-phase duplicate; skipped as already succeeded. |

The code-phase mandatory surface read was compressed to preserve patch self-check budget, returning an already-read reference rather than duplicating the payload. `context.read_branch_state` succeeded.

## Hypothesis

Final hypothesis: add `capacity_first_regret_repair` in `policies/baseline_modules/destroy_repair.py`, with a scheduler-side `repair_selector_fleet_violation_check` that chooses the new repair operator when `fleet_violation > 0`. The stated mechanism was to pack customers into high-capacity-slack routes while capacity-infeasible, then return to standard regret-2 after `fleet_violation == 0`.

Grounding was incomplete. The agent saw:

- Problem summary/object and active `solver_design` surface metadata.
- Active solver-design snapshot and call graph.
- Full-ish reads of `baseline_algorithm.py`, `local_search.py`, and `destroy_repair.py`.
- No full read of `scheduler.py`, `state.py`, `construction.py`, `config.py`, or `solution_checks.py` during hypothesis generation.

The hypothesis was therefore under-grounded for a scheduler-selector mechanism. More importantly, it misunderstood the objective. In `solution_checks.py`, `fleet_violation` is `max(0, routes - allowed_routes)` using `allowed_routes` or `bks_routes`; it is not route capacity overload. Capacity overload is a hard feasibility failure. The baseline scheduler also initializes feasible `_Solution` objects and rejects infeasible candidates with `candidate.is_feasible()`, so a condition based on overloaded routes is normally unreachable.

This means the hypothesis was semantically weak even before code generation: it targeted a real algorithm body, but its activation condition did not correspond to the adapter's `fleet_violation` metric.

## Code Attempts

### Attempt 1

Trace: `20260519T073929603528_code_40d1fb4968_3c2ec70d.json`.

Context: first code manifest included the approved hypothesis, target file code for `destroy_repair.py`, compact sibling APIs, full branch-current integration files including `scheduler.py` and `state.py`, active mechanisms, code-scope controls, and branch state. `agentic_tool_observations` was truncated but not omitted.

Output:

- Top-level `file_path`: `policies/baseline_modules/destroy_repair.py`.
- Added `_capacity_first_regret_insertion` and `_best_insertions_slack_ordered`.
- `additional_changes`: full replacement of `policies/baseline_modules/scheduler.py`, importing the new repair op and forcing it when `_fleet_violation(current) > 0`.
- Declared mechanisms: `capacity_first_regret_repair`, `repair_selector_fleet_violation_check`.

Problems:

- `_fleet_violation` in scheduler counted overloaded routes, not adapter fleet violation.
- Baseline current solutions are feasible and candidates are rejected if infeasible, so `_fleet_violation(current) > 0` is effectively inactive.
- `_best_insertions_slack_ordered` iterated routes in slack order but then sorted all insertions only by cost, largely erasing the slack bias.
- It did not bind declared telemetry to a field that would show positive activation.

Result: `proposal.contract_preview` passed; `proposal.algorithm_smoke` failed with `TELEMETRY_ACTIVATION_NOT_OBSERVED` for `solver_algorithm_fleet_violation`.

### Attempt 2

Trace: `20260519T074050115391_code_fb148676ee_8afbd93f.json`.

Context: included the previous code failure summary and prior smoke feedback. The manifest records `prior_code_failure`; full `agentic_tool_observations` and full preview feedback were omitted/truncated for budget, but the top failure message was visible.

Output:

- Revised capacity-first insertion with `_best_insertions_slack_biased`.
- `additional_changes`: scheduler import and selector logic, plus `context.record_phase("fleet_violation_init", float(initial_fleet_violation))` and final `fleet_violation_final`.
- Also included an unnecessary `baseline_algorithm.py` additional change that appears to preserve the stable entrypoint.

Problems:

- `context.record_phase` records phase runtime and context-record counts. It does not write `solver_algorithm_fleet_violation`.
- The runtime-owned `solver_algorithm_fleet_violation` is computed from the returned solution objective after validation; if the solution respects `max_routes`, it stays zero.
- The mechanism still used overloaded-route count as the condition, not route-count violation against `allowed_routes`/`bks_routes`.

Result: contract preview passed; algorithm smoke repeated `TELEMETRY_ACTIVATION_NOT_OBSERVED` for `solver_algorithm_fleet_violation`.

### Attempt 3

Trace: `20260519T074227262930_code_fb148676ee_299bf10c.json`.

Context: included two smoke observations and the prior failure summary. The agent was specifically told to avoid missing `solver_algorithm_fleet_violation` activation.

Output:

- Added `_fleet_violation(solution)` to `destroy_repair.py`, still counting routes with `route.load > solution.instance.capacity`.
- Scheduler imported `_fleet_violation`.
- Tried to emit telemetry with `context.record_phase(..., extra={"solver_algorithm_fleet_violation": fv})` at init, segment boundaries, and final.

Problems:

- `record_phase` has no `extra` parameter in both preview and runtime contexts. The signature is `record_phase(name, elapsed_ms)`.
- Static contract preview did not catch this helper-signature mismatch.
- Algorithm smoke caught the runtime failure as `solver_algorithm_errors=1`.

Result: contract preview passed; algorithm smoke failed; retry budget was exhausted and the session failed closed.

## Failure Chain

The first failure point was not static contract compatibility. All three contract previews passed. The failing chain was:

1. Hypothesis self-check passed schema and target permissions, then waited for approval.
2. Code attempt 1 produced algorithm-body changes, but algorithm smoke rejected the patch because declared activation telemetry `solver_algorithm_fleet_violation` was not observed.
3. Code attempt 2 tried to satisfy telemetry by phase records, but those records do not bind to the declared field. Smoke failed the same guard again.
4. Code attempt 3 tried to force custom telemetry through an unsupported `record_phase(extra=...)` API. Smoke then failed on runtime audit with `solver_algorithm_errors=1`.
5. The framework applied fail-closed behavior: `output.patch` stayed null, branch state did not receive a code hash, and the hypothesis was rejected.

This is a mixed failure:

- Algorithm-code quality: attempt 3 used an invalid context API; attempt 1 also had a slack-ordering implementation bug.
- Problem-object understanding: the hypothesis confused route capacity feasibility with adapter `fleet_violation`.
- Tool/context design: hypothesis generation did not read the scheduler/state files it reasoned about; problem exposure did not state the actual `fleet_violation = extra routes over allowed/bks route count` formula.
- Framework control: fail-closed behavior was appropriate, but the telemetry guard was too tightly bound to an outcome field and pushed the agent toward invalid telemetry hacks.
- Telemetry binding: `solver_algorithm_fleet_violation` is runtime-owned outcome telemetry, not an exposed mechanism-activation sink.

## Design Compliance

Compliant with v3-style controls:

- Active boundary was enforced: the agent only targeted `solver_design` files under `policies/baseline_algorithm.py` and `policies/baseline_modules/*.py`.
- Legacy component-policy/operator surfaces were excluded from active evidence.
- API-visible prompt manifests were recorded for hypothesis and all code attempts.
- Screening/runtime feedback was exposed as tainted proposal context, not Decision input.
- Contract/schema/target previews ran before acceptance.
- Algorithm smoke ran before screening/verification, caught the failures, and prevented branch mutation.
- The branch did not receive an applied patch; this was not a post-processing or adapter edit.

Weak or non-compliant-by-design areas:

- Hypothesis grounding was allowed to proceed after skipping full `scheduler.py` even though the hypothesis depended on scheduler selection behavior.
- The problem object exposed "fleet_violation" as an objective but not its adapter definition. The agent filled the gap with a wrong capacity-overload interpretation.
- The telemetry guard treated `solver_algorithm_fleet_violation` as activation evidence requiring positive observation. For this adapter, that field is an output objective that a good feasible solution may keep at zero.
- Static contract preview did not validate context helper keyword signatures.

## Root Causes

1. Adapter/problem exposure gap: `fleet_violation` semantics were not rendered clearly enough. It is route-count excess over `allowed_routes`/`bks_routes`, while capacity is a hard feasibility constraint.
2. Agent hypothesis error: it proposed an unreachable condition (`capacity infeasible current solution`) and chose a target-file split where the key selector lived in scheduler but the primary target was `destroy_repair.py`.
3. Telemetry guard design error: it required positive activation for an outcome field that the framework itself computes after validation.
4. Context/tool-policy weakness: the hypothesis stage did not force full reads of the files owning the proposed mechanism (`scheduler.py`, and arguably `state.py`/objective semantics).
5. Code API misuse: the final retry invented `record_phase(extra=...)` rather than staying within the exposed helper signature.

## Recommended Fixes

1. Fix adapter/problem exposure first. Render the exact objective formula: `fleet_violation = max(0, len(routes) - (allowed_routes or bks_routes))`; separately state that capacity overload is infeasible and cannot be used as an internal improvement state.
2. Fix telemetry binding. Do not require positive activation evidence for `solver_algorithm_fleet_violation`. Treat it as an effect/outcome field. Mechanism activation should use fields the algorithm can actually affect through exposed helpers, such as search iterations, move attempts, accepted moves, phase deltas, or explicit future mechanism telemetry APIs.
3. Add a hypothesis grounding rule: if the hypothesis mentions scheduler selection, state internals, telemetry helpers, or objective computation, require the owning active files or a rendered objective/API contract before hypothesis finalization.
4. Strengthen static contract preview to reject unsupported context helper signatures, especially extra keyword arguments to `record_phase`, `record_iteration`, and `record_move`.
5. Update agent prompt policy with a premise check: before targeting `fleet_violation`, state whether the proposed mechanism reduces route count versus capacity overload, and explain how it can be nonzero in valid solver outputs.
6. Keep the fail-closed preview chain. It worked as a safety gate here; the needed repair is not loosening acceptance, but making problem semantics and telemetry contracts actionable before code generation.

