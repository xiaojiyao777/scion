# ExperimentProtocol Implementations and Protocol-Owned Evaluation Details

## Scope

Current source reviewed:

- `scion/scion/protocol/experiment/facade.py`
- `scion/scion/protocol/experiment/stages.py`
- `scion/scion/protocol/experiment/selection.py`
- `scion/scion/protocol/experiment/canary.py`
- `scion/scion/protocol/experiment/cache.py`
- `scion/scion/protocol/experiment/runtime_observation.py`
- `scion/scion/protocol/experiment/surface_runtime.py`
- `scion/scion/protocol/experiment/phase_telemetry.py`
- `scion/scion/protocol/evaluation.py`
- `scion/scion/protocol/stats.py`
- `scion/scion/protocol/gates.py`
- `scion/scion/problem/objectives.py`
- `scion/scion/runtime/audit.py`
- `scion/scion/runtime/subprocess_runner.py`
- `scion/scion/core/features.py`
- `scion/scion/core/decision.py`
- `scion/scion/core/evaluation_pipeline.py`
- `scion/scion/core/evaluation_orchestrator.py`
- `scion/scion/cli/commands/init_run.py`
- `scion/scion/cli/commands/data_roots.py`
- selected protocol, runtime, decision, CVRP smoke, and production-boundary tests

## Current Understanding

`ExperimentProtocol` owns the generic A/B evidence loop after contract and
verification have accepted a candidate workspace.

```text
EvaluationPipeline
  -> protocol.run_canary(candidate, champion, selected_surface)
  -> protocol.run_experiment(stage, candidate, champion, action, expand...)
       -> select deterministic stage cases and fixed stage seeds
       -> run paired champion/candidate solver calls
       -> audit runtime evidence and selected-surface telemetry
       -> compare objective metrics through ProblemSpecV1 metric specs when present
       -> aggregate seed pairs to case-level statistical units
       -> compute hierarchical or legacy stats
       -> apply stage gate
       -> emit ProtocolResult + raw metrics snapshot
  -> SafeFeatureExtractor
  -> DecisionEngine
```

The production CLI path builds `ExperimentProtocol` with ProblemSpecV1 objective
metrics and `require_metric_specs=True` for adapter-backed production campaigns.
That is the correct path. Direct construction without metric specs still falls
back to the legacy objective comparator.

Evidence:

- production protocol construction wires metric specs, objective policy, problem
  spec, time limit, and strict metric requirement:
  - `scion/scion/cli/commands/init_run.py:610`
  - `scion/scion/cli/commands/init_run.py:618`
  - `scion/scion/cli/commands/init_run.py:629`
- `ExperimentProtocol` stores metric specs and refuses production construction
  without them:
  - `scion/scion/protocol/experiment/facade.py:41`
  - `scion/scion/protocol/experiment/facade.py:68`
- the experiment loop selects cases/seeds and writes partial raw metrics before
  running pairs:
  - `scion/scion/protocol/experiment/stages.py:104`
  - `scion/scion/protocol/experiment/stages.py:115`
  - `scion/scion/protocol/experiment/stages.py:240`
- objective comparison uses ProblemSpecV1 metric specs when present:
  - `scion/scion/protocol/experiment/facade.py:102`
  - `scion/scion/problem/objectives.py:32`
  - `scion/scion/problem/objectives.py:88`
- stats are case-level, not pair-level:
  - `scion/scion/protocol/experiment/stages.py:724`
  - `scion/scion/protocol/stats.py:8`
- protocol result fields are converted into structured decision features:
  - `scion/scion/core/features.py:125`
  - `scion/scion/core/features.py:153`
  - `scion/scion/core/features.py:176`
- decision runtime vetoes consume failed runtime evidence:
  - `scion/scion/core/decision.py:250`
  - `scion/scion/core/decision.py:264`
  - `scion/scion/core/decision.py:274`

## Positive Boundary Observations

- Protocol is generic: split, seed, objective, runtime evidence, and telemetry
  are generic framework concepts; CVRP semantics stay in problem specs, adapters,
  and problem-owned runtime fields.
- Screening, validation, and frozen all use deterministic stage case selection.
  Expansion increases case count, not seed count.
- The statistical unit is case. Seed-level pairs are aggregated before gate
  stats are computed.
- Production metric comparison uses declared metric direction, priority,
  tolerance, and weighted-sum policy. Legacy all-minimize semantics are isolated
  to compatibility paths.
- Candidate process failures and candidate runtime-audit failures are counted as
  losses and also counted in `candidate_failed_pairs`.
- Validation and frozen fail closed on any incomplete evidence after valid stats
  are computed.
- Candidate runtime failures are elevated again at the decision layer through
  `CANDIDATE_RUNTIME_FAILURE`, including screening.
- Runtime tie improvement is guarded by fresh champion runtime evidence. Cached
  champion results cannot by themselves drive a runtime-tie pass.
- Champion result cache keys include workspace digest, case identity, seed, time
  limit, selected surface, objective digest, and runner identity.
- Cached champion runtime pairs are excluded from high-confidence runtime ratio
  samples and marked as `low_cached_champion`.
- Runtime and telemetry evidence is surfaced into raw metrics, exposed summaries,
  decision features, status summaries, and feedback context.
- Validation and frozen sanitize per-case feedback before exposure; screening
  keeps detailed feedback for agent repair guidance.

Evidence:

- case and seed selection:
  - `scion/scion/protocol/experiment/selection.py:54`
  - `scion/scion/protocol/experiment/selection.py:89`
  - `scion/scion/protocol/experiment/selection.py:127`
- candidate failure handling:
  - `scion/scion/protocol/experiment/stages.py:449`
  - `scion/scion/protocol/experiment/stages.py:560`
  - `scion/scion/tests/test_protocol_failure_runtime.py:19`
  - `scion/scion/tests/test_protocol_failure_runtime.py:207`
- validation/frozen incomplete evidence override:
  - `scion/scion/protocol/experiment/stages.py:794`
  - `scion/scion/tests/test_protocol_failure_runtime.py:281`
- runtime-tie gates:
  - `scion/scion/protocol/gates.py:123`
  - `scion/scion/protocol/gates.py:141`
  - `scion/scion/tests/unit/test_protocol_champion_result_cache.py:59`
- cache identity and runtime-confidence handling:
  - `scion/scion/protocol/experiment/cache.py:55`
  - `scion/scion/protocol/experiment/cache.py:81`
  - `scion/scion/protocol/experiment/cache.py:193`
  - `scion/scion/protocol/experiment/stages.py:321`
  - `scion/scion/protocol/experiment/stages.py:350`
  - `scion/scion/tests/unit/test_protocol_champion_result_cache.py:17`
- surface runtime and telemetry summaries:
  - `scion/scion/protocol/experiment/stages.py:156`
  - `scion/scion/protocol/experiment/stages.py:333`
  - `scion/scion/protocol/experiment/stages.py:802`
  - `scion/scion/tests/test_protocol_surface_runtime.py:38`
  - `scion/scion/tests/test_protocol_surface_runtime.py:197`
- exposure control:
  - `scion/scion/protocol/experiment/stages.py:938`
  - `scion/scion/core/evaluation_pipeline.py:229`

## Risks And Findings

### F-PROTOCOL-001 [P2] Direct protocol construction still has legacy all-minimize objective semantics

The production CLI and production campaign boundary require metric specs, but
`ExperimentProtocol` remains usable without them. In that mode it logs a warning
and falls back to `scion.protocol.evaluation`, where all objective keys are
treated as minimization metrics and missing metric keys default to zero.

This is acceptable as a compatibility mode only if all direct callers understand
it is non-production. It is risky for scripts, tests, or external integrations
that construct `ExperimentProtocol` directly and expect ProblemSpecV1 direction
or weighted-sum semantics.

Evidence:

- no metric specs switches to legacy fallback:
  - `scion/scion/protocol/experiment/facade.py:68`
  - `scion/scion/protocol/experiment/facade.py:116`
  - `scion/scion/protocol/experiment/facade.py:168`
- legacy fallback treats all metrics as minimization and uses key-order merge:
  - `scion/scion/protocol/evaluation.py:10`
  - `scion/scion/protocol/evaluation.py:26`
  - `scion/scion/protocol/evaluation.py:52`
- production/campaign tests protect the main path but preserve fallback tests:
  - `scion/scion/tests/test_sprint_n1.py:143`
  - `scion/scion/tests/test_protocol_stats_gates.py:40`

Suggested fix direction:

- Make direct non-metric construction require an explicit
  `allow_legacy_objective_fallback=True`.
- Include a structured `objective_semantics="legacy_all_minimize"` marker in
  `ProtocolResult` and raw metrics when fallback is used.
- Prefer changing generic tests to pass metric specs where the behavior is not
  explicitly testing legacy compatibility.

### F-PROTOCOL-002 [P2] Surface runtime summary undercounts failed `*_active` evidence fields

Runtime audit treats `*_loaded`, `*_executed`, and `*_active` fields as generic
boolean evidence fields that must be truthy. Surface runtime summaries only treat
`*_loaded` and `*_executed` as boolean failure fields. As a result, a candidate
with a required runtime field such as `solver_algorithm_active=False` will be
failed by runtime audit, but the aggregate surface summary can show that field as
present with `failed=0`.

This does not let the bad candidate pass; the audit gate still fails it. The risk
is evidence quality: agent feedback, status cards, and postmortem summaries may
point at missing/error fields but under-report inactive mechanisms.

Evidence:

- runtime audit counts `*_active` false as a failed runtime evidence field:
  - `scion/scion/runtime/audit.py:552`
  - `scion/scion/runtime/audit.py:568`
  - `scion/scion/runtime/audit.py:662`
- surface runtime summary omits `*_active` from true-evidence failure detection:
  - `scion/scion/protocol/experiment/surface_runtime.py:68`
  - `scion/scion/protocol/experiment/surface_runtime.py:72`
  - `scion/scion/protocol/experiment/surface_runtime.py:272`
- tests cover true active values but not false active summary counts:
  - `scion/scion/tests/test_protocol_surface_runtime.py:83`
  - `scion/scion/tests/test_protocol_surface_runtime.py:104`
  - `scion/scion/tests/test_protocol_surface_runtime.py:197`

Suggested fix direction:

- Reuse the runtime-audit helper or align `_is_runtime_true_evidence_field(...)`
  with `_is_generic_true_evidence_field(...)`.
- Add a focused test with a declared `*_active` required runtime field set to
  `False`, asserting both audit failure and surface summary `failed > 0`.

### F-PROTOCOL-003 [P2] Screening can advance after champion-side invalid pairs

Champion process failures and champion runtime-audit failures are recorded as
invalid pairs and excluded from pair feedback. Validation and frozen later fail
closed on any `failed_pairs`, but screening does not. The decision layer vetoes
candidate failures in every stage and incomplete failed pairs only in validation
or frozen. Therefore a screening run with some champion invalid pairs and enough
remaining valid wins can still queue validation.

That may be an intentional throughput tradeoff. It is still a gate semantics
risk because screening evidence can be biased toward cases where the champion
was healthy, while failures are visible only as `failed_pairs` in summaries.
Promotion is still protected by later validation/frozen incomplete-evidence
checks, so this is mainly a research-budget and feedback-quality risk.

Evidence:

- champion failures are invalid and do not append `PairwiseCaseFeedback`:
  - `scion/scion/protocol/experiment/stages.py:385`
  - `scion/scion/protocol/experiment/stages.py:628`
  - `scion/scion/protocol/experiment/stages.py:724`
- incomplete evidence override applies only to validation/frozen:
  - `scion/scion/protocol/experiment/stages.py:794`
- decision runtime veto ignores generic `failed_pairs` in screening:
  - `scion/scion/core/decision.py:264`
  - `scion/scion/core/decision.py:273`
- screening decision then uses win rate and median delta:
  - `scion/scion/core/decision.py:118`
  - `scion/scion/core/decision.py:128`
- tests assert champion failure accounting, but not a mixed screening
  champion-failure plus remaining-wins advance case:
  - `scion/scion/tests/test_protocol_failure_runtime.py:46`
  - `scion/scion/tests/test_protocol_failure_runtime.py:281`

Suggested fix direction:

- If intentional, add a reason code such as
  `SCREENING_PARTIAL_CHAMPION_EVIDENCE` when screening passes/expands with
  `champion_failed_pairs > 0`.
- Consider blocking `QUEUE_VALIDATE` when `champion_failed_pairs / total_pairs`
  exceeds a small threshold.
- Add a regression test for mixed screening evidence so the chosen behavior is
  explicit.

### F-PROTOCOL-004 [P2] Champion result cache key omits SCION environment variables passed to solver subprocesses

`LocalSubprocessRunner` passes through all `SCION_*` environment variables to the
solver process. The champion cache key records runner class/version but does not
include a digest of the effective `SCION_*` environment. Data-root effects are
usually covered indirectly by resolved case path and case content digest, but a
problem adapter or solver can legally use other `SCION_*` variables to alter
behavior. If such a variable changes, the cached champion result may compare an
old-environment champion against a new-environment candidate.

Evidence:

- runner explicitly passes all `SCION_*` variables and injects selected surface:
  - `scion/scion/runtime/subprocess_runner.py:27`
  - `scion/scion/runtime/subprocess_runner.py:38`
  - `scion/scion/runtime/subprocess_runner.py:150`
- cache key records runner identity, not effective environment:
  - `scion/scion/protocol/experiment/cache.py:55`
  - `scion/scion/protocol/experiment/cache.py:86`
  - `scion/scion/protocol/experiment/cache.py:193`
- cache tests cover seed, time limit, selected surface, objective policy, case
  content, and workspace digest, but not environment changes:
  - `scion/scion/tests/unit/test_protocol_champion_result_cache.py:148`
  - `scion/scion/tests/unit/test_protocol_champion_result_cache.py:175`

Suggested fix direction:

- Add a runner-provided `runtime_identity()` or `cache_identity()` hook that
  includes the effective sanitized environment digest.
- Or include a sorted digest of non-secret `SCION_*` variables from
  `_build_clean_env()` in `runner_runtime_identity(...)`, with explicit redaction
  for credentials if any are later allowed.
- Add a cache test that changes a `SCION_*` runtime variable and expects a cache
  miss.

### F-PROTOCOL-005 [P3] Case path safety is enforced mostly by CLI preflight, not by ExperimentProtocol itself

`SplitManifest.from_yaml(...)` resolves `safe_data_roots`, and the CLI production
path validates declared data-root cases before constructing the protocol. But
`ExperimentProtocol` path resolution itself accepts absolute paths as-is and
returns unresolved relative paths unchanged when workspace and safe data roots do
not contain them.

For the main CLI path this is largely mitigated by data-root activation and
split-case validation. For direct protocol construction, external ingest, or
research scripts, the protocol boundary trusts the manifest and runner to deal
with arbitrary or unresolved case paths.

Evidence:

- split manifest resolves safe roots but does not reject absolute cases:
  - `scion/scion/config/split_manifest.py:40`
  - `scion/scion/config/split_manifest.py:91`
- protocol path resolver returns absolute paths unchanged and unresolved paths
  unchanged:
  - `scion/scion/protocol/experiment/selection.py:140`
  - `scion/scion/protocol/experiment/selection.py:148`
  - `scion/scion/protocol/experiment/selection.py:154`
- CLI preflight activates and validates declared data-root cases:
  - `scion/scion/cli/commands/init_run.py:551`
  - `scion/scion/cli/commands/data_roots.py:71`
  - `scion/scion/cli/commands/data_roots.py:137`

Suggested fix direction:

- Add an optional strict mode on `SplitManager` or `ExperimentProtocol` that
  rejects unresolved relative paths and absolute paths outside workspace or safe
  data roots.
- At minimum, record path-resolution status in raw metrics so failures caused by
  unresolved cases are easier to diagnose.

## Open Questions

- Is `solver_design` intended to be a generic first-class surface in v0.4, or is
  it a CVRP-era surface name that should eventually be entirely problem-owned?
  This affects how much selected-surface telemetry should live in protocol vs
  adapter packages.
- Should screening be allowed to queue validation when `champion_failed_pairs >
  0`, or should champion-side baseline health be a hard screening prerequisite?
- Should the champion cache be disabled by default for production frozen runs,
  even though runtime-tie gates already require fresh runtime evidence?

## Suggested Next Audit Step

Move to the Decision engine / BranchLifecyclePolicy deep pass next. The protocol
layer is now clearly feeding structured features into decision, and the remaining
high-impact question is how lifecycle policy uses weak/marginal/no-effect,
runtime confidence, repeated signals, and telemetry diagnostics to park,
archive, retain, or roll back branches.
