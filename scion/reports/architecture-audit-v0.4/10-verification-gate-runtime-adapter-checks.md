# VerificationGate and Runtime/Adapter Checks

## Scope

Current source reviewed:

- `scion/scion/verification/gate.py`
- `scion/scion/verification/requirements.py`
- `scion/scion/verification/interface.py`
- `scion/scion/verification/tests.py`
- `scion/scion/verification/state_mutation.py`
- `scion/scion/verification/feasibility.py`
- `scion/scion/verification/objective.py`
- `scion/scion/verification/nondeterminism.py`
- `scion/scion/verification/perf_guard.py`
- `scion/scion/runtime/runner.py`
- `scion/scion/runtime/subprocess_runner.py`
- `scion/scion/runtime/audit.py`
- `scion/scion/problem/contracts.py`
- `scion/scion/problems/cvrp/adapter.py`
- `scion/scion/core/verification_factory.py`
- `scion/scion/core/production_boundary.py`
- `scion/scion/core/explore_step/pipeline.py`
- `scion/scion/core/explore_step/verification.py`
- `scion/scion/core/branch_step_runner.py`
- `scion/scion/core/evaluation_pipeline.py`
- `scion/scion/core/evidence_recording/artifact_refs.py`
- `scion/scion/core/evidence_recording/lineage.py`
- selected verification, runtime, production-boundary, and evidence tests

## Current Understanding

`VerificationGate` is the executable gate after `ContractGate` has accepted a
patch and after the candidate workspace has been materialized. It runs V1-V9 in
fail-fast order.

```text
PatchProposal + candidate workspace
  -> V1_syntax                 light, AST parse
  -> V2_interface              light, AST surface/operator interface
  -> V3_unit_tests             light, candidate workspace pytest when configured
  -> V4_regression_tests       light, candidate workspace pytest when configured
  -> V_runtime_config          heavy, strict-mode runtime prerequisites
  -> V5_solution_consistency   heavy, canary solver output consistency
  -> V6_feasibility            heavy, canary solver output feasibility
  -> V7_objective              heavy, canary objective recomputation
  -> V8_nondeterminism         heavy, same seed/case canonical artifact equality
  -> V9_perf_guard             heavy, candidate/champion wall-clock ratio
```

The most important production boundary is:

```text
ProblemSpecV1 / adapter-backed campaign
  -> CampaignVerificationFactory
  -> VerificationGate(strict_runtime_checks=True,
                      require_adapter_for_runtime=True,
                      adapter=<loaded adapter>)
  -> production boundary requires strict + adapter-required flags
```

Non-strict and skeleton paths intentionally keep legacy behavior. In those
paths, missing runner/spec/canary/test files can pass as skipped checks. This is
not the production path, but it is important for programmatic callers.

Evidence:

- gate construction auto-enables strict runtime checks for adapter-required
  problem specs unless skeleton fallback is explicitly allowed:
  - `scion/scion/verification/gate.py:65`
  - `scion/scion/verification/gate.py:93`
- V1-V9 are run in fail-fast order:
  - `scion/scion/verification/gate.py:115`
  - `scion/scion/verification/gate.py:239`
- non-strict runs skip runtime checks when runner/spec are absent:
  - `scion/scion/verification/gate.py:149`
  - `scion/scion/verification/gate.py:155`
- strict runtime config fails closed for missing canary, missing champion
  workspace, or missing required adapter:
  - `scion/scion/verification/gate.py:157`
  - `scion/scion/verification/gate.py:166`
  - `scion/scion/verification/gate.py:251`
  - `scion/scion/verification/gate.py:270`
- the campaign factory builds strict adapter-required gates for production
  campaigns and rejects non-strict production fallback:
  - `scion/scion/core/verification_factory.py:44`
  - `scion/scion/core/verification_factory.py:67`
- the production boundary checks that adapter-backed campaigns have adapter,
  protocol, metric specs, split/seed stages, and strict verification flags:
  - `scion/scion/core/production_boundary.py:47`
  - `scion/scion/core/production_boundary.py:107`

## Positive Boundary Observations

- The default CLI and default programmatic production path construct
  `VerificationGate` from the loaded adapter, protocol runner, metric/runtime
  config, problem spec, and operator signature.
- Adapter-backed production campaigns cannot opt into non-strict runtime
  verification unless `allow_skeleton_mode` is explicitly enabled.
- `ProblemSpecV1` or specs with `requires_adapter_for_runtime` automatically
  disable legacy runtime fallback.
- V5-V8 run solver outputs through runtime audit before adapter checks or
  legacy oracle fallback. Solver-side fallback, surface errors, missing required
  runtime fields, and runtime error counters can turn a successful process exit
  into a verification failure.
- V5-V7 use adapter-owned semantics for instance loading, solver output
  deserialization, consistency, feasibility, and objective recomputation.
- V7 verifies declared objective metrics are present in both solver-reported
  and adapter-recomputed objectives.
- V8 compares adapter canonical signatures or adapter-declared fingerprints,
  not raw JSON payloads, so harmless diagnostics/nonces do not create false
  nondeterminism failures.
- V2 stays AST-only and reuses the contract surface interface checker instead of
  importing tainted candidate code into the orchestrator process.
- `LocalSubprocessRunner` isolates solver execution through a sanitized
  environment, `PYTHONHASHSEED=0`, process-group kill on timeout, resource
  limits, and workspace-first `PYTHONPATH`.
- `selected_surface` is forwarded through the verification gate into runtime
  subprocess execution as `SCION_SELECTED_SURFACE`, and runtime audit enforces
  selected-surface evidence contracts.
- Verification failure handling keeps light failures fixable and treats heavy
  failures as branch/hypothesis lifecycle events, with failed workspace
  archiving.

Evidence:

- CLI wiring from problem-v1, bridge, adapter, protocol, and strict
  verification gate:
  - `scion/scion/cli/commands/init_run.py:497`
  - `scion/scion/cli/commands/init_run.py:643`
- production factory and boundary tests:
  - `scion/scion/tests/unit/core/test_campaign_control_lifecycle_budget_runtime.py:261`
  - `scion/scion/tests/unit/core/test_campaign_control_lifecycle_budget_runtime.py:264`
  - `scion/scion/tests/unit/core/test_campaign_control_lifecycle_budget_runtime.py:293`
  - `scion/scion/tests/unit/core/test_campaign_control_lifecycle_budget_runtime.py:339`
  - `scion/scion/tests/unit/core/test_campaign_control_lifecycle_budget_runtime.py:546`
- adapter-required runtime checks fail closed:
  - `scion/scion/tests/test_verification_gate_integration.py:100`
  - `scion/scion/tests/test_verification_gate_integration.py:132`
  - `scion/scion/tests/test_verification_solution_checks.py:40`
  - `scion/scion/tests/test_verification_objective_runtime_checks.py:45`
- V5-V7 runtime audit and adapter paths:
  - `scion/scion/verification/state_mutation.py:78`
  - `scion/scion/verification/state_mutation.py:106`
  - `scion/scion/verification/feasibility.py:71`
  - `scion/scion/verification/feasibility.py:130`
  - `scion/scion/verification/objective.py:73`
  - `scion/scion/verification/objective.py:170`
- V8 runtime audit and canonical adapter comparison:
  - `scion/scion/verification/nondeterminism.py:94`
  - `scion/scion/verification/nondeterminism.py:205`
  - `scion/scion/tests/test_verification_objective_runtime_checks.py:300`
  - `scion/scion/tests/test_verification_objective_runtime_checks.py:398`
- selected-surface runtime audit:
  - `scion/scion/runtime/audit.py:88`
  - `scion/scion/runtime/audit.py:154`
  - `scion/scion/runtime/audit.py:230`
  - `scion/scion/runtime/audit.py:327`
  - `scion/scion/tests/test_verification_gate_integration.py:240`
  - `scion/scion/tests/test_verification_gate_integration.py:330`
- subprocess isolation:
  - `scion/scion/runtime/subprocess_runner.py:27`
  - `scion/scion/runtime/subprocess_runner.py:47`
  - `scion/scion/runtime/subprocess_runner.py:50`
  - `scion/scion/runtime/subprocess_runner.py:81`
  - `scion/scion/runtime/subprocess_runner.py:150`
  - `scion/scion/runtime/subprocess_runner.py:189`
- verification failure handling:
  - `scion/scion/core/explore_step/verification.py:77`
  - `scion/scion/core/explore_step/verification.py:202`

## Risks And Findings

### F-VERIFICATION-001 [P2] Production custom gates are accepted by private flags, not by verified behavior

The default production factory path is strict. The weak point is custom
`verification_gate` injection. `CampaignVerificationFactory.build(...)` returns
a custom gate unchanged. The production boundary then checks only
`_strict_runtime_checks is True` and `_require_adapter_for_runtime is True`.
It does not prove that the custom object actually runs V1-V9, uses the provided
adapter, invokes the protocol runner, performs runtime audit, or fails closed.

There is a test that intentionally accepts a custom "strict" always-pass gate
whose behavior is inherited from an always-pass stub and whose strictness comes
only from private attributes. That is useful for tests, but it documents the
production boundary's current trust model.

Evidence:

- custom verification gate is returned unchanged:
  - `scion/scion/core/verification_factory.py:37`
  - `scion/scion/core/verification_factory.py:38`
- production boundary checks only private flags:
  - `scion/scion/core/production_boundary.py:96`
  - `scion/scion/core/production_boundary.py:107`
- test support always-pass gate returns a passing result without V1-V9:
  - `scion/scion/tests/unit/core/campaign_control_boundaries_test_support.py:109`
  - `scion/scion/tests/unit/core/campaign_control_boundaries_test_support.py:114`
- custom strict always-pass gate is accepted for a production campaign:
  - `scion/scion/tests/unit/core/test_campaign_control_lifecycle_budget_runtime.py:505`
  - `scion/scion/tests/unit/core/test_campaign_control_lifecycle_budget_runtime.py:525`

Why this matters:

- Programmatic production callers can bypass the runtime gate by supplying an
  object with two attributes set to `True`.
- A bypassed VerificationGate is more dangerous than a bypassed preview: it is
  directly upstream of protocol evaluation and decision.
- This is especially relevant because heavy verification failures drive
  hypothesis rejection/blacklisting. A fake gate can both hide real invalidity
  and produce misleading evidence that verification passed.

Suggested fix direction:

- Disallow custom gates in adapter-backed production unless an explicit
  `allow_test_verification_gate` or `allow_custom_verification_gate` flag is set
  outside the normal production path.
- Or require a formal `VerificationGate` capability protocol with immutable
  identity, adapter/spec binding, runner binding, and a self-test/dry-run
  method.
- At minimum, validate that a custom gate's `run(...)` returns checks including
  the required runtime checks for a controlled adapter-backed canary case before
  accepting it as production-capable.

### F-VERIFICATION-002 [P2] V9 performance guard fails open when the champion run is unavailable or invalid

`_validate_runtime_config(...)` checks that the champion workspace path exists,
but it does not run the champion. `V9_perf_guard` runs the candidate first and
fails the candidate if that run fails. It then runs the champion; if the
champion run fails, times out, or reports runtime audit failure, V9 returns
`passed=True` with `detail="skipped: champion solver run failed"`. If champion
time is zero, it also returns a passing skipped check.

This avoids blocking research because of an infra/champion problem. But it also
means a strict production VerificationGate can pass without an actual
candidate/champion performance comparison.

Evidence:

- strict config validates only champion workspace directory existence:
  - `scion/scion/verification/gate.py:258`
  - `scion/scion/verification/gate.py:264`
- V9 skips/passes when champion workspace is absent, champion run fails, or
  champion time is zero:
  - `scion/scion/verification/perf_guard.py:40`
  - `scion/scion/verification/perf_guard.py:41`
  - `scion/scion/verification/perf_guard.py:117`
  - `scion/scion/verification/perf_guard.py:136`
- candidate run failure is a blocking failure, so the asymmetry is explicit:
  - `scion/scion/verification/perf_guard.py:92`
  - `scion/scion/verification/perf_guard.py:115`
- tests assert no champion workspace is a passing skip:
  - `scion/scion/tests/test_verification_objective_runtime_checks.py:409`
  - `scion/scion/tests/test_verification_objective_runtime_checks.py:416`

Why this matters:

- Runtime performance evidence becomes unavailable exactly when the baseline is
  unhealthy, but the gate still records a pass.
- The decision feature extractor treats V9 check status as a structured runtime
  guard input, so a skipped/pass V9 can look safer than an invalid comparison.
- Protocol evaluation may still catch runtime regressions later, but
  VerificationGate no longer acts as a performance screen in this scenario.

Suggested fix direction:

- In strict production mode, make champion run failure a blocking
  `V9_perf_guard` failure or a separate non-passing `V9_baseline_runtime_config`
  result.
- If fail-open is intentional for agent throughput, make the result status
  explicit, for example `passed=False, diagnosis=ENV` or
  `metadata.comparison_valid=False`, and keep it out of "verification passed"
  evidence.
- Pass a `strict_runtime_checks` or `allow_perf_baseline_skip` flag into
  `check_perf(...)` instead of hardcoding the same behavior for all modes.

### F-VERIFICATION-003 [P2] Runtime gate budgets are hardcoded and can block valid research independent of protocol config

V5, V6, V7, and V8 all run canary solver calls with a hardcoded
`time_limit_sec=30`. V9 uses `SCION_PERF_GUARD_TIMEOUT` or a default of 60
seconds. The factory passes `max_runtime_ratio` from protocol config into the
gate, but it does not pass the protocol solver time limit or any
surface/problem-declared verification budget.

Because V5-V9 failures are heavy, a candidate that is valid under the protocol's
declared runtime budget can be rejected or blacklisted by the verification gate
before protocol evaluation. This module is therefore a likely source of agent
research obstruction when canary cases or active surfaces need more than the
fixed 30 second budget.

Evidence:

- V5-V8 hardcode 30 second solver budgets:
  - `scion/scion/verification/state_mutation.py:53`
  - `scion/scion/verification/state_mutation.py:62`
  - `scion/scion/verification/feasibility.py:40`
  - `scion/scion/verification/feasibility.py:49`
  - `scion/scion/verification/objective.py:46`
  - `scion/scion/verification/objective.py:55`
  - `scion/scion/verification/nondeterminism.py:70`
  - `scion/scion/verification/nondeterminism.py:79`
- V9 has an environment/default timeout separate from protocol time limit:
  - `scion/scion/verification/perf_guard.py:43`
  - `scion/scion/verification/perf_guard.py:56`
- the subprocess runner enforces a wall-clock guard close to the solver budget:
  - `scion/scion/runtime/subprocess_runner.py:120`
  - `scion/scion/runtime/subprocess_runner.py:134`
- factory passes only runtime ratio, not time limit:
  - `scion/scion/core/verification_factory.py:40`
  - `scion/scion/core/verification_factory.py:67`
- heavy failures become non-fixable branch lifecycle events:
  - `scion/scion/core/explore_step/verification.py:161`
  - `scion/scion/core/explore_step/verification.py:202`

Why this matters:

- The verification gate can reject candidates for exceeding an implicit canary
  budget that is not visible in the problem/protocol contract.
- This is a direct agent-productivity risk: heavy verification failures are not
  routed through the light repair path.
- The hardcoded budget may be too permissive for some quick problems and too
  strict for larger adapter-owned problems.

Suggested fix direction:

- Thread `ExperimentProtocol` time limit or a dedicated
  `verification_runtime_budget_sec` through `CampaignVerificationFactory` into
  `VerificationGate`.
- Let `ProblemSpecV1` or a problem-owned provider declare canary verification
  budgets by surface/case class.
- Preserve a short default for skeleton/demo mode, but make production budgets
  explicit and visible in failure details.
- Consider classifying timeout-heavy failures as `ENV` vs `CANDIDATE` based on
  whether the candidate exceeded the declared production budget or only the
  gate's screening budget.

### F-VERIFICATION-004 [P2] Durable verification audit drops `detail` for most checks

Failure handling builds a rich `verification_detail` string for failed
verification steps. But the lineage/internal audit serializer records
verification checks with `name`, `passed`, `severity`, `elapsed_ms`, and
`metadata` only. It omits `check.detail` for V1-V8. V9 is special-cased through
`runtime_guard` and keeps detail.

This is less severe for immediate LLM repair because failure steps keep
`verification_detail`. It is still an audit risk for passed or skipped checks:
later evidence review can see that V5-V8 passed, but not whether they passed
through adapter checks, legacy fallback, skipped canary, or a narrow diagnostic
detail unless that fact was also encoded in metadata.

Evidence:

- generic verification check serialization omits `detail`:
  - `scion/scion/core/evidence_recording/artifact_refs.py:123`
  - `scion/scion/core/evidence_recording/artifact_refs.py:135`
- V9 is separately preserved with detail:
  - `scion/scion/core/evidence_recording/artifact_refs.py:138`
  - `scion/scion/core/evidence_recording/artifact_refs.py:149`
- lineage internal audit payload uses this serializer:
  - `scion/scion/core/evidence_recording/lineage.py:98`
  - `scion/scion/core/evidence_recording/lineage.py:119`
- failed exploration steps keep rich verification detail:
  - `scion/scion/core/explore_step/verification.py:217`
  - `scion/scion/core/explore_step/verification.py:229`

Why this matters:

- A pass/skipped distinction inside `detail` can be lost for V5-V8.
- Adapter-backed vs legacy details are not consistently persisted across all
  checks.
- Later architecture/evidence audits have to reconstruct gate behavior from
  source code and partial metadata instead of from the run artifact.

Suggested fix direction:

- Persist sanitized/truncated `detail` for all verification checks in internal
  audit payloads.
- Add structured metadata fields such as `mode`, `skipped`, `adapter_backed`,
  `legacy_fallback`, `canary_case`, and `selected_surface` consistently across
  V5-V8.
- Keep decision features free of text, but do not drop check detail from
  internal audit artifacts.

### F-VERIFICATION-005 [P2] Validation/frozen eval steps reuse screening verification instead of rerunning V1-V9

Explore/screening and stale-branch reconcile paths call `VerificationGate`.
Validation/frozen evaluation steps in `BranchStepRunner._run_eval_step(...)`
create `VerificationResult(passed=True, checks=())` and
`ContractResult(passed=True, checks=())` before running protocol evaluation.
`EvaluationPipeline` has the same default no-op verification evaluator unless a
caller injects one.

This can be a reasonable design if validation/frozen stages are meant to reuse
the exact workspace already verified during screening and if workspace hygiene
guarantees no code drift. But the gate's scope should be documented as
"screening/reconcile verification", not "every stage verification".

Evidence:

- validation/frozen eval step uses synthetic passing gate results:
  - `scion/scion/core/branch_step_runner.py:262`
  - `scion/scion/core/branch_step_runner.py:304`
- reconcile reruns contract and verification before re-screening:
  - `scion/scion/core/branch_step_runner.py:354`
  - `scion/scion/core/branch_step_runner.py:402`
- `EvaluationPipeline` defaults verification to passed unless an evaluator is
  injected:
  - `scion/scion/core/evaluation_pipeline.py:124`
  - `scion/scion/core/evaluation_pipeline.py:130`
  - `scion/scion/core/evaluation_pipeline.py:465`
  - `scion/scion/core/evaluation_pipeline.py:466`

Why this matters:

- If branch workspace contents change after screening, validation/frozen
  protocol runs may not be protected by a fresh VerificationGate pass.
- Evidence for later stages records `verification_passed=True` even though no
  V1-V9 checks were run in that stage.
- This is another place where gate semantics can be misunderstood by users
  reading status/evidence.

Suggested fix direction:

- Document stage semantics explicitly: V1-V9 run at screening and reconcile,
  while validation/frozen rely on immutable workspace hash plus protocol checks.
- Add an invariant check that the workspace code hash at validation/frozen still
  matches the last verified screening hash.
- Consider rerunning cheap static V1/V2 and selected-surface runtime audit smoke
  before validation/frozen if workspace drift cannot be ruled out cheaply.

## Open Questions

- Should `V9_perf_guard` be allowed to pass in strict production mode when the
  champion run fails?
- What is the intended production verification budget for V5-V8, and should it
  come from protocol config, problem spec, or a problem-owned runtime provider?
- Are custom verification gates a supported production extension point or only
  a test seam?
- Should validation/frozen stage evidence say "verification reused" instead of
  `verification_passed=True` with empty checks?
- Which verification check details should be decision-visible structured
  features, and which should remain internal audit-only text?

## Suggested Next Audit Target

`ExperimentProtocol implementations / protocol-owned evaluation details` should
come next. VerificationGate proves that a candidate can execute on a canary and
survive adapter-owned runtime checks. The statistical, split/seed, objective
policy, runtime-regression, and telemetry-evidence semantics live in the
protocol layer, and several VerificationGate risks are only acceptable if the
protocol layer catches or records them cleanly.
