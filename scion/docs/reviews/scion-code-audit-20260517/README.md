# Scion Code Audit 2026-05-17

## Scope

Repository: `/home/clawd/research/or-autoresearch-agent`

Commit reviewed: `633508a` (`Document API manifest validation smoke`)

Recent context:

- `88e27aa` repaired the solver-design destroy-repair API context.
- `633508a` documented the API manifest validation smoke.
- The 3-round experiment at `/home/clawd/research/scion-experiments/v04-api-manifest-sonnet-3r-20260517T034512Z` completed 3 steps and abandoned all candidates by Decision with `SCREENING_FAIL_WIN_RATE`.
- The 6-round background experiment at `/home/clawd/research/scion-experiments/v04-api-manifest-sonnet-6r-20260517T042338Z` had `status.json` at 4 steps when inspected and no `campaign_summary.json` yet.

Constraints followed:

- No code was modified.
- The raw `vrp/` research object files were not touched.
- No live LLM experiment was run.
- Only read-only commands and short ContractGate probes were used, then this review documentation was added.

## Method

The audit covered:

- APS/proposal taint, tool exposure policy, two-phase agentic proposal sessions, repair loops, trace artifacts, and prompt/code context.
- ContractGate C6/C8/C9/C9b/C9c/C9d/C9e plus solver-design integration checks.
- CVRP solver-design runtime entrypoints, `baseline_algorithm.py`, `solver_algorithm.py`, baseline modules, adapter preview, smoke, Verification, Protocol, and Decision.
- Formal split/smoke data resolution, `SCION_PROBLEM_DATA_ROOT`, runtime telemetry, campaign status/summary behavior, and background launch artifacts.
- Existing tests and maintainability risks around large files and string/prompt contracts.

## Overall Conclusion

Scion v0.4 has moved in the right direction: the declared `solver_design` surface is now the preferred CVRP research boundary, `problem-v1.yaml` carries solver-design runtime evidence fields, APS sessions persist tainted transcript/artifact metadata, algorithm smoke runs real branch materializations for the declared `solver_design` path, and Decision correctly abandoned the recent 3-round candidates.

The remaining risk is not that candidates are currently being promoted incorrectly. The higher-priority risk is that the boundary is not fail-closed in the core layers. Several important solver-design rules exist in prompts, adapter preview, and APS smoke, but not in ContractGate/Verification/Protocol. That leaves bypass paths for non-APS proposals, stale branch-context repairs, compatibility aliases, and generated code that uses dynamic Python features.

## Highest Priority Findings Index

| ID | Severity | Finding |
| --- | --- | --- |
| F-01 | Critical | ContractGate C9 misses dynamic import and dynamic sensitive API calls, allowing `__import__("os").system(...)` through static checks. |
| F-02 | High | Core ContractGate accepts a preferred `policies/baseline_algorithm.py` patch that only calls `context.baseline(...)`; APS preview catches this, but the core gate does not. |
| F-03 | High | APS `context.read_surface` returns champion snapshot code/support artifacts, not the current branch workspace, so repair/code context can contradict branch-owned solver-design state. |
| F-04 | High | The `solver_algorithm` compatibility alias is only partially mapped: Contract treats it as solver-design, but algorithm smoke and required runtime-field audit do not. |
| F-05 | Medium | C9e solver-design helper integration can be spoofed by dead load references such as `unused = helper`. |
| F-06 | Medium | C9d instance-identity checks only catch `instance.name` and literal `getattr/hasattr`; dataclass `repr(instance)`, `vars(instance)`, and `instance.__dict__` still expose case identity. |
| F-07 | Medium | Agentic code phase can skip the mandatory full surface read when the observation budget is reserved for self-check. |
| F-08 | Medium | Protocol progress is not emitted after champion-side process/audit failure branches, so background status can lag in rare failure paths. |
| F-09 | Medium | Generic runtime feedback/summary omits solver-design stop reasons and counters except when they are explicitly required runtime fields. |
| F-10 | Medium | Solver-design smoke resolves absolute case paths and `SCION_PROBLEM_DATA_ROOT` without binding the resolved file to an audited data root. |

## Documents

- `01-boundary-and-governance.md`: proposal/APS taint and Contract/Verification/Protocol/Decision boundary risks.
- `02-solver-design-cvrp-object.md`: branch-owned solver-design runtime and CVRP object-model risks.
- `03-agentic-session-and-tools.md`: APS tool loops, code context, repair, budgets, and trace artifacts.
- `04-contract-and-static-gates.md`: C9/C9c/C9d/C9e static-gate findings.
- `05-runtime-smoke-and-experiments.md`: smoke, formal split, telemetry, status/summary, background launch.
- `06-tests-and-maintainability.md`: test gaps and maintainability risks.
- `appendix-commands.md`: read-only commands and short probes used for this audit.

## Open Questions

- Is `solver_algorithm` still intended to be a user-selectable surface, or should it be only an internal compatibility file under the declared `solver_design` surface?
- Should `context.baseline(...)` be completely forbidden from `policies/baseline_algorithm.py`, or allowed only for controlled seeding with mandatory own-search telemetry?
- Should APS tools read branch workspace snapshots after a branch has any current code hash, while using champion snapshots only as an explicit reference artifact?
- Are all `SCION_*` environment variables safe to expose to candidate solver subprocesses, or should the runner whitelist only known runtime variables?

## Suggested Verification

- Add ContractGate tests for `__import__("os").system(...)`, dynamic `getattr`, `importlib`, `Path.read_text`, and `os.environ`.
- Add a core ContractGate test asserting that preferred `policies/baseline_algorithm.py` cannot call `context.baseline(...)`.
- Add an APS tool test where branch workspace code differs from champion code and `context.read_surface(detail="full")` must return the branch version.
- Add an algorithm-smoke test for selected surface alias handling, either mapping `solver_algorithm` to `solver_design` everywhere or rejecting it before launch.
- Add C9e tests for dead helper references and C9d tests for `repr(instance)`, `vars(instance)`, and `instance.__dict__`.
- Add Protocol progress tests for champion-side process failure and champion runtime-audit failure.

