# 02 - Solver Design CVRP Object

## Runtime Shape

The declared v0.4 surface is `solver_design` in `problem-v1.yaml`. Its preferred entrypoint is `policies/baseline_algorithm.py::solve(instance, rng, time_limit_sec, context)`, with branch-owned helper modules under `policies/baseline_modules/*.py`. `policies/solver_algorithm.py` is described as a compatibility hook.

At runtime, `scion/scion/problems/cvrp/solver.py` loads the solver-design algorithm before legacy baseline/component policy code:

- `_main` calls `_load_solver_algorithm` before policy/baseline fallback at `scion/scion/problems/cvrp/solver.py:795`.
- If the algorithm is active, legacy policy audit dicts are set to defaults and the algorithm solution is used at `scion/scion/problems/cvrp/solver.py:805`.
- Preferred `baseline_algorithm.py` is only enabled when `_solver_design_runtime_enabled()` returns true at `scion/scion/problems/cvrp/solver.py:8472`.

## Findings

### F-02 - Preferred entrypoint can be reduced to `context.baseline` outside APS preview

- Severity: High
- Files:
  - `scion/scion/problems/cvrp/problem-v1.yaml:950`
  - `scion/scion/problems/cvrp/problem-v1.yaml:965`
  - `scion/scion/problems/cvrp/adapter.py:1247`
  - `scion/scion/problems/cvrp/solver.py:8812`
  - `scion/scion/problems/cvrp/solver.py:8820`
- Problem: The object model correctly says `baseline_algorithm.py` is the branch-owned algorithm body and must not call `context.baseline`, but the runtime helper remains available and the core ContractGate does not reject it. Adapter preview catches the direct preferred-target call in APS smoke, but runtime audit treats it as telemetry, not a hard failure.
- Trigger path: A candidate can submit `policies/baseline_algorithm.py` with `solve(...)` returning `context.baseline(...)`. ContractGate passes. If the path is not guarded by APS algorithm smoke/problem preview, Verification and Protocol will execute it as an active solver algorithm and merely record `solver_algorithm_baseline_calls`.
- Impact: This violates the intended v0.4 research-object boundary. The branch candidate may be statistically abandoned, but Scion has still spent evaluation budget on a baseline wrapper rather than a branch-owned solver-design algorithm.
- Suggested fix: Enforce the preferred-target `context.baseline` ban in ContractGate or a mandatory core problem preview. Runtime audit for `solver_design` should optionally fail when `solver_algorithm_path == "policies/baseline_algorithm.py"` and `solver_algorithm_baseline_calls > 0`, unless an explicit allowlist policy is introduced.

### F-03 - Branch-owned module context can be stale in APS tool observations

- Severity: High
- Files:
  - `scion/scion/proposal/context_manager.py:371`
  - `scion/scion/proposal/tools.py:795`
  - `scion/scion/proposal/tools.py:804`
  - `scion/scion/proposal/tools.py:3336`
- Problem: `build_code_context` can read the current branch workspace for the target file, but `context.read_surface` and solver-design support artifacts are always read from champion. This is a real mismatch for branch-owned baseline modules because support-module APIs are part of the algorithm body.
- Trigger path: Branch A modifies `policies/baseline_modules/destroy_repair.py` and then enters a repair loop or a follow-up code generation. The base code context may include branch target code, but `context.read_surface` support artifacts describe champion scheduler/local-search/destroy-repair APIs. The model can import or call names that do not exist in the branch workspace, or reintroduce champion assumptions.
- Impact: This can produce import failures, adapter mismatch, and low-quality repair loops. It also weakens audit provenance because the transcript does not clearly distinguish "branch code" from "champion reference code" for the tool observation.
- Suggested fix: Add branch-source provenance to tool payloads and read from branch workspace whenever available. Include branch/champion source, code hash, and path root in `surface_contract.current_artifact` and support artifacts.

### F-04 - Compatibility alias has inconsistent runtime semantics

- Severity: High
- Files:
  - `scion/scion/problems/cvrp/problem-v1.yaml:864`
  - `scion/scion/problems/cvrp/solver.py:8466`
  - `scion/scion/problems/cvrp/solver.py:8472`
  - `scion/scion/proposal/solver_design_smoke.py:63`
  - `scion/scion/runtime/audit.py:247`
- Problem: The codebase still has the older `solver_algorithm.py` compatibility path, and ContractGate recognizes the name `solver_algorithm` as solver-design. Other layers do not normalize it. Preferred `baseline_algorithm.py` will not load for that selected surface, smoke will not run, and required runtime fields will not be found by selected-surface name.
- Trigger path: Any forced or legacy proposal path that uses the selected surface name `solver_algorithm` rather than `solver_design` enters a compatibility mode where the declared solver-design evidence fields and smoke controls are not consistently applied.
- Impact: A candidate can appear to be in solver-design territory to ContractGate while avoiding the preferred object model and smoke behavior. This is especially risky because `problem-v1.yaml` says `solver_algorithm.py` is retained only for older compatibility candidates.
- Suggested fix: Remove `solver_algorithm` as an accepted selected-surface name, or normalize it to `solver_design` before every layer. Keep `policies/solver_algorithm.py` as a target file only under the declared `solver_design` surface.

### F-09 - Solver-design runtime telemetry is incomplete in generic feedback summaries

- Severity: Medium
- Files:
  - `scion/scion/protocol/experiment.py:995`
  - `scion/scion/protocol/experiment.py:1035`
  - `scion/scion/protocol/experiment.py:1194`
  - `scion/scion/protocol/experiment.py:1202`
- Problem: `_candidate_runtime_observation` tracks operator/policy/construction/portfolio counters and `operator_stop_reason`, but it does not track `solver_algorithm_stop_reason`, `solver_algorithm_search_iterations`, `solver_algorithm_move_attempts`, or baseline call counts. `_runtime_audit_summary` includes `solver_algorithm_*` only if the selected surface provides them as required runtime fields.
- Trigger path: A solver-design candidate can have meaningful algorithm telemetry in raw solver output, but generic runtime feedback categories and stop reasons stay blank or operator-oriented unless required fields are passed through for that exact surface.
- Impact: Decision still receives protocol statistics, and selected `solver_design` currently has required fields. The maintenance risk is that future feedback/guidance and summaries can miss solver-design effort/no-op signals if selected surface normalization is wrong or if the summary is consumed without the selected-surface field list.
- Suggested fix: Make solver-design runtime observation first-class. Record solver algorithm stop reasons, search iterations, move attempts, accepted/improving move counts, and baseline calls in the same generic runtime observation structure used for feedback and summaries.

## Positive Evidence

- `problem-v1.yaml` declares strong solver-design required runtime fields from `solver_algorithm_loaded` through `solver_algorithm_stop_reason`.
- `solver.py` runs the solver-design algorithm before legacy baseline/component policies.
- Recent 3-round experiment protocol results recorded `selected_surface: solver_design` and Decision abandoned all candidates rather than promoting weak evidence.

