# 01 - Boundary And Governance

## Boundary Model Reviewed

The intended layering is:

1. APS/proposal tools produce tainted hypothesis and patch artifacts.
2. ContractGate rejects wrong targets, unsafe static patterns, and surface protocol violations.
3. Verification and Protocol run candidate workspaces under selected-surface runtime audit.
4. Decision applies promotion/abandon policy from protocol evidence.

The recent 3-round experiment is consistent with this control flow: all three completed APS candidates reached screening and were abandoned by Decision with `SCREENING_FAIL_WIN_RATE`. The issue is that several solver-design restrictions are enforced only in APS preview/problem preview, not in the core Contract/Verification/Protocol path.

## Findings

### F-01 - Dynamic sensitive API bypass in ContractGate

- Severity: Critical
- Files:
  - `scion/scion/contract/gate.py:716`
  - `scion/scion/contract/gate.py:725`
  - `scion/scion/contract/gate.py:730`
  - `scion/scion/runtime/subprocess_runner.py:27`
  - `scion/scion/runtime/subprocess_runner.py:144`
- Problem: C9 only flags direct sensitive names such as `eval`, `exec`, direct `open`, direct `os.system`, and attribute calls where the receiver is an `ast.Name`. It does not flag dynamic imports or attributes whose receiver is an expression.
- Trigger path: A patch can call `__import__("os").system("true")` or similar dynamic forms. C8 sees no `Import` or `ImportFrom` node, C9 sees an `ast.Attribute` whose receiver is an `ast.Call`, and the patch passes. The short probe in `appendix-commands.md` confirmed `passed True` for a solver-design patch containing `__import__('os').system('true')`.
- Impact: Candidate code can execute shell commands, inspect files, or access environment variables when run by Verification/Protocol/smoke. The runner passes `PATH`, `PYTHONPATH`, and every `SCION_*` variable into the subprocess, then prepends the candidate workspace to `PYTHONPATH`. This makes the C9 bypass a real boundary issue, not just a static-rule false negative.
- Suggested fix: Move from a blacklist toward a small allowlist for callable forms in generated code. At minimum reject `__import__`, `importlib`, `getattr`/`setattr` on sensitive modules, `globals`, `locals`, `compile`, dynamic receiver calls that resolve to sensitive modules, `os.environ`, and path/file read/write methods regardless of receiver expression shape. Add regression tests that assert these forms fail C8/C9.

### F-02 - `context.baseline` wrapper is blocked in APS preview but not in the core gate

- Severity: High
- Files:
  - `scion/scion/problems/cvrp/problem-v1.yaml:961`
  - `scion/scion/problems/cvrp/problem-v1.yaml:1030`
  - `scion/scion/problems/cvrp/adapter.py:1247`
  - `scion/scion/core/explore_step_pipeline.py:316`
  - `scion/scion/core/branch_step_runner.py:251`
  - `scion/scion/problems/cvrp/solver.py:8812`
- Problem: The preferred solver-design rule "do not call `context.baseline` from `policies/baseline_algorithm.py`" is present in prompt/spec text and adapter preview, but core ContractGate accepts such a patch. Core explore/reconcile paths call only `validate_patch` before applying and moving to Verification.
- Trigger path: A patch with `def solve(...): return context.baseline(...)` in `policies/baseline_algorithm.py` passes ContractGate. The short probe in `appendix-commands.md` confirmed `passed True` for C7/C9/C9e. APS `proposal.algorithm_smoke` currently catches this for normal agentic runs through the problem preview path, but non-APS proposals, stale-branch reconciliation, or any path that bypasses APS preview depends on Contract/Verification/Protocol and will not fail on the semantic rule itself.
- Impact: The research object can collapse back into a shallow wrapper around the repo-local baseline. Verification and Protocol runtime audit require solver algorithm fields for `solver_design`, but they do not reject `solver_algorithm_baseline_calls > 0`. The candidate may still be abandoned statistically, but the boundary claim "branch-owned algorithm body, not postprocessing/baseline wrapper" is not enforced at the core governance layer.
- Suggested fix: Promote the preferred-target `context.baseline` ban from adapter preview into ContractGate, or add a core problem-specific contract hook that runs during `validate_patch`. If limited seeding is allowed, encode the exact allowed pattern and require own-search telemetry in runtime audit.

### F-03 - APS surface tool reads champion code rather than current branch code

- Severity: High
- Files:
  - `scion/scion/proposal/tools.py:223`
  - `scion/scion/proposal/tools.py:795`
  - `scion/scion/proposal/tools.py:804`
  - `scion/scion/proposal/tools.py:3336`
  - `scion/scion/proposal/context_manager.py:371`
- Problem: `context.read_surface` reads `context.champion.code_snapshot_path` for the target file and solver-design support artifacts. `ProposalToolContext` does not carry a branch workspace path. Separately, `ContextManager.build_code_context` can read `branch_workspace` for `target_file_code`, so the base code context and tool observations can disagree.
- Trigger path: In a repair loop or long-lived branch with existing branch-owned solver-design edits, the code phase can see branch target code from `build_code_context` while `context.read_surface(detail="full")` and support artifacts are from champion. The model can then generate against stale scheduler/module APIs or overwrite branch-owned helper changes.
- Impact: This weakens the core v0.4 direction: the agent is supposed to research and modify the branch-owned solver-design algorithm subject. Stale champion reads make repairs less reliable and can turn multi-module algorithm work into accidental resets or adapter/API mismatches.
- Suggested fix: Add branch workspace or branch snapshot root to `ProposalToolContext`. Make `context.read_surface` return branch code when the branch has current code, and label champion reads explicitly as `reference_artifact`. Include source root, code hash, and branch/champion provenance in the structured payload.

### F-04 - Partial `solver_algorithm` alias mapping can bypass solver-design runtime controls

- Severity: High
- Files:
  - `scion/scion/contract/gate.py:1620`
  - `scion/scion/proposal/solver_design_smoke.py:63`
  - `scion/scion/problems/cvrp/solver.py:8472`
  - `scion/scion/runtime/audit.py:247`
  - `scion/scion/runtime/audit.py:250`
  - `scion/scion/problems/cvrp/problem-v1.yaml:851`
- Problem: ContractGate treats selected surface `solver_algorithm` as solver-design, but `proposal.algorithm_smoke` only runs for exact `solver_design`, CVRP runtime only enables preferred `baseline_algorithm.py` for exact `solver_design`, and runtime audit required fields are looked up by exact surface name. `problem-v1.yaml` declares `solver_design`, not a separate `solver_algorithm` surface.
- Trigger path: If any compatibility path or forced selection uses `selected_surface="solver_algorithm"`, static checks may treat it as solver-design while smoke returns `None`, runtime loads only `policies/solver_algorithm.py`, and required solver-design runtime fields are not found because `_find_research_surface` returns `None`.
- Impact: This creates a split-brain boundary. The compatibility alias can lose APS repair smoke and runtime-field enforcement, even though ContractGate applies solver-design-specific assumptions. It is also difficult to audit because some layers use the alias and others do not.
- Suggested fix: Normalize selected surface names once at the boundary. Either reject `solver_algorithm` as an external surface or map it to `solver_design` before Contract, APS smoke, runtime, and audit. Add tests covering all four layers.

### F-08 - Protocol status can lag after champion-side failure branches

- Severity: Medium
- Files:
  - `scion/scion/protocol/experiment.py:627`
  - `scion/scion/protocol/experiment.py:658`
  - `scion/scion/protocol/experiment.py:761`
  - `scion/scion/protocol/experiment.py:793`
  - `scion/scion/core/evidence_recorder.py:163`
- Problem: Candidate-side process and audit failures write metrics and call `_emit_progress`. Champion-side process and audit failures write metrics but do not emit progress before continuing.
- Trigger path: If champion solver execution fails or champion runtime audit fails during a long Protocol stage, `status.json` will not receive the latest attempted/completed pair state until a later progress event or final status write.
- Impact: The normal path is likely unaffected because champion failures should be rare. In the exact failure mode where status matters most, background status can lag and make the run look stuck or less complete than the metrics file.
- Suggested fix: Use a helper that always calls `_write_metrics_snapshot` and `_emit_progress` after appending a raw pair/failure, including champion failure branches. Add a protocol fake-runner test for both champion failure paths.

## Open Questions

- Should APS problem preview be considered a mandatory governance layer, or only a repair aid? If mandatory, core explore/reconcile paths should also call the same problem preview hook.
- Should the runner expose any inherited `SCION_*` variable to candidate code, or only `SCION_SELECTED_SURFACE` and an audited data-root variable?

