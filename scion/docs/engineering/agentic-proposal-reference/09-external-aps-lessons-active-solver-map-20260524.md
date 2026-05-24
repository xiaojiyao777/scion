# External APS Lessons: Active Solver Map, Screening Tiers, And Branch Memory

Date: 2026-05-24

Source experiment:
`/home/clawd/research/scion-experiments/v04-v3-external-agent-gpt55-20260524T140321Z-claw`

This design note turns the six-round external APS control sample into Scion APS
engineering requirements. The goal is controlled capability transfer: give the
Scion proposal agent enough audited context to reason like the external agent did
without breaking the v3 boundary.

Scion core remains problem-generic. Research-object facts, code slices,
mechanism labels, telemetry fields, operator registries, and problem-specific
repair guidance must enter through adapter/provider/tool boundaries.

## Executive Summary

The external agent was useful because it could read the active solver as a
system: entry point, scheduler loop, operator registry, helper bodies, raw
screening deltas, and prior candidate traces. Internal Scion APS should not get
unbounded repository access. It should get a controlled equivalent:

- an adapter-filled active solver map;
- bounded source slices with read receipts and budgets;
- case-level and pair-level screening feedback tiers;
- branch-local memory for weak-positive and no-effect mechanisms;
- structured repair hints for novelty and multi-file target-file errors;
- optionally, an official external/alternate-agent patch runner that still uses
  Scion's gates.

The highest priority is P0/P1 inside the normal APS loop:

1. `context.read_active_solver_map`
2. screening feedback tier extraction
3. branch-local mechanism memory
4. structured C10/C4b repair guidance

The external patch runner is useful for reproducibility and future comparisons,
but it can remain P2 if engineering time is limited.

## Six-Round External APS Conclusions

All six external candidates passed contract/static preview, algorithm smoke,
VerificationGate, canary, and formal screening execution. All six failed the
screening promotion gate with `SCREENING_FAIL_WIN_RATE`. None should be promoted.

| Attempt | Mechanism | Screening | Classification | Branch lifecycle value |
|---|---|---:|---|---|
| 01 | `intra_route_or_opt` | 2W/1L/5T, win_rate 0.25, median_delta 0.0, runtime +22 ms | weak-positive with small runtime cost | Keep as active but insufficient; invite schedule/trigger/composition variants, not identical repeats. |
| 02 | `late_intra_reinsert` | 1W/1L/6T, win_rate 0.125, median_delta 0.0, runtime -13 ms | weak-positive but weaker than 01 | Records that a cheaper late variant reduces cost but also loses quality signal. |
| 03 | `vns_quality_gate` | 1W/1L/6T, median_delta -0.5, runtime -33 ms | quality-regression with runtime improvement | Warns lifecycle not to overvalue speed when objective quality regresses. |
| 04 | `tight_regret_repair` | 0W/0L/8T, median_delta 0.0, runtime +0.5 ms | no-effect | Records an activated but non-impacting repair operator; avoid unchanged repeats. |
| 05 | `compact_route_removal` | 0W/0L/8T, median_delta 0.0, runtime +29 ms | no-effect plus runtime-regression | Records operator noise: active but not useful and slightly slower. |
| 06 | `stagnation_scaled_destroy` | 0W/1L/7T, median_delta 0.0, runtime -5.5 ms | quality-regression / weak negative | Records that perturbation-scale policy changed behavior without useful wins. |

Why this matters to branch lifecycle:

- "Failed screening" is not one state. It can mean invalid, inactive, active
  no-effect, weak-positive, quality-regression, runtime-regression, or
  promotable-but-uncertain.
- Weak-positive attempts are valuable branch state. They identify a real
  mechanism and should shape the next proposal.
- No-effect attempts are also valuable. They prevent repeated unchanged operator
  additions and force the agent toward trigger, schedule, threshold, composition,
  or a different mechanism family.
- Runtime-improving but quality-regressing attempts should not keep a branch
  alive unless the problem's objective policy explicitly allows that tradeoff.

## Active Solver Map Tool Design

### Tool Set

Recommended APS context tools:

- `context.read_active_solver_map`
- `context.read_operator_registry`
- `context.read_algorithm_slice`
- `context.read_scheduler_integration`
- `context.read_mechanism_memory`

These tools are Creative Layer context tools. They produce tainted proposal
context, not decision features. They must not expose validation/frozen details or
unbounded raw repository state.

### Core Schema

Scion core should define generic schema objects. It should not define CVRP
operators, CVRP file paths, or CVRP-specific mechanisms.

`ActiveSolverMap`:

```yaml
surface: string
subject_id: string
snapshot_digest: string
entrypoints:
  - id: string
    file_path: string
    symbol: string
    summary: string
    calls:
      - target_id: string
        evidence: [string]
call_graph_edges:
  - from: string
    to: string
    mechanism: string
    evidence: [string]
editable_files:
  - file_path: string
    role: entrypoint|scheduler|operator_module|state|config|helper|test
    digest: string
    read_budget_hint: int
frozen_files:
  - file_path: string
    reason: string
operator_registries:
  - registry_id: string
    owner_file: string
    owner_symbol: string
    registry_kind: local_search|destroy|repair|acceptance|construction|custom
    operators:
      - id: string
        symbol: string
        file_path: string
        order: int|null
        role: string
        summary: string
        mechanism_tags: [string]
        telemetry_ids: [string]
scheduler_integrations:
  - integration_id: string
    file_path: string
    symbol: string
    phase: string
    summary: string
    calls: [string]
    guard_conditions: [string]
    state_variables: [string]
    telemetry_events: [string]
algorithm_slices:
  - slice_id: string
    file_path: string
    symbols: [string]
    purpose: string
    exposure_level: summary|signature|body|excerpt
    source_digest: string
    token_estimate: int
    redaction_reason: string|null
telemetry_fields:
  - field: string
    role: activation|activity|effect|budget|safety|debug
    mechanism_id_template: string|null
    declared_by: string
known_mechanism_facts:
  - fact_id: string
    claim: string
    evidence: [string]
    provenance: adapter|provider|screening_memory|contract
source_policy:
  max_total_tokens: int
  max_body_tokens_per_tool_call: int
  allowed_files_digest: string
  redaction_policy: string
```

`OperatorRegistry` is a narrower read result for the code stage:

```yaml
registry_id: string
surface: string
snapshot_digest: string
operators:
  - id: string
    symbol: string
    file_path: string
    order: int|null
    summary: string
    signature: string|null
    body_slice_id: string|null
    related_helpers: [string]
    existing_mechanism_claims: [string]
integration_points:
  - file_path: string
    symbol: string
    insert_policy: string
    required_telemetry_pattern: string|null
```

`AlgorithmSlice`:

```yaml
slice_id: string
surface: string
file_path: string
symbols: [string]
slice_kind: symbol_body|symbol_excerpt|registry_block|integration_block|diff_context
content: string
content_digest: string
line_start: int|null
line_end: int|null
token_estimate: int
why_visible: string
source_policy_receipt:
  allowed: bool
  reason: string
  remaining_budget: int
```

### CVRP Provider Fill Strategy

CVRP adapter/provider should fill the generic schema from its existing active
solver design provider and source allowlist.

For the current CVRP `solver_design` surface, the provider would map:

- entrypoint: `policies/baseline_algorithm.py::solve`
- scheduler integration: `_ALNSVNSSolver.solve`
- construction phase: `_initial_solution`
- local search registry: `_default_vns_operators`
- destroy registry: `destroy_ops` in scheduler
- repair registry: `repair_ops` in scheduler
- acceptance path: `_SimulatedAnnealing.accept`
- adaptive weighting: `_AdaptiveWeights.choose/record/update`
- state and feasibility helpers: `_Solution`, `_Route`, `is_feasible`,
  `remove_empty_routes`, `rebuild_index`

The provider owns CVRP-specific summaries such as "embedded VNS after repair" or
"route-limit rejection after repair". Core only sees generic fields.

### Source Exposure Control

The external agent benefited from reading full files. Scion should expose enough
target code without making raw source unlimited.

Recommended policy:

- `read_active_solver_map` returns summaries, registry membership, file digests,
  and slice ids, not full file text.
- `read_operator_registry` returns registry order, operator symbols, signatures,
  summaries, and bounded helper references.
- `read_algorithm_slice` returns exact source bodies only for allowlisted
  symbols or integration blocks selected by the provider.
- Each source result carries a digest and read receipt. Repeated reads should
  return a compact receipt unless the caller asks for a different symbol/slice.
- Code prompt assembly should prefer target file, integration point, related
  helpers, and telemetry pattern before unrelated editable files.
- Adapter/provider can mark a slice `summary` only if the source body is too
  large or not needed; it should explain how to request narrower sub-slices.

This preserves v3 control: the adapter decides which research-object code is
visible, core only enforces budgets and provenance.

## Screening Feedback Tier Design

### Pair-Level And Case-Level Exposure

Current promotion is case-level. The agent also needs pair-level information to
understand weak positives and noisy mechanisms.

Expose to agent prompt:

```yaml
screening_feedback:
  stage: screening
  gate_outcome: pass|fail
  tier: invalid|inactive|weak_positive|no_effect|quality_regression|runtime_regression|promotable|uncertain
  reason_codes: [string]
  case_summary:
    n_cases: int
    wins: int
    losses: int
    ties: int
    win_rate: float
    median_delta: float
    statistical_status: positive|negative|uncertain|tie|null
  pair_summary:
    total_pairs: int
    valid_pairs: int
    wins: int
    losses: int
    ties: int
    median_delta: float
  runtime_summary:
    runtime_ratio_median: float|null
    runtime_delta_median_ms: float|null
    runtime_regression_rate: float|null
  mechanism_summary:
    declared_mechanisms: [string]
    activation_observed: bool
    effect_observed: bool|null
    telemetry_guard_failures: [string]
  next_step_hint:
    repeat_unchanged_allowed: bool
    allowed_followup_variants: [trigger|schedule|threshold|composition|telemetry_repair|different_mechanism]
    warning: string|null
```

Audit-only:

- raw per-run metric files;
- full per-case identifiers if hidden by split policy;
- command lines, workspaces, and stdout/stderr;
- full candidate/champion runtime payloads;
- validation/frozen details;
- exact raw metrics for protected holdout stages.

The prompt can include small exemplar deltas for screening cases only if the
problem policy allows them. Otherwise it should include aggregate buckets and
feature summaries.

### Tier Rules

Suggested first pass, using screening only:

- `invalid`: candidate or champion runtime failures, contract/verification not
  passed, telemetry guard hard failure, or invalid objective output.
- `inactive`: declared mechanism activation was expected but not observed and
  diagnostic is wiring-suspect or activation missing across screening.
- `promotable`: `gate_outcome == pass`.
- `weak_positive`: gate failed, candidate is valid, activation observed, case
  wins > 0 or pair wins > pair losses, no safety failures, median_delta >= 0 or
  statistical status is not negative.
- `no_effect`: valid, activation observed, case wins == 0, case losses == 0,
  median_delta == 0, and runtime is within policy tolerance.
- `quality_regression`: valid but case losses > wins, median_delta < 0, or
  statistical status negative.
- `runtime_regression`: valid, quality is no-effect or weak-positive, but
  runtime ratio/delta/regression rate exceeds the configured soft threshold.
- `uncertain`: valid but does not cleanly fit above, often mixed wins/losses
  with wide intervals.

Classification must be advisory to the proposal agent. Decision remains governed
by existing gates and `DecisionFeatures`.

## Branch-Local Memory Design

### Memory Record

Add a branch-local mechanism memory record that is visible to future proposal
sessions but does not directly control promotion.

```yaml
MechanismMemoryRecord:
  record_id: string
  branch_id: string
  surface: string
  mechanism_id: string
  mechanism_signature:
    algorithm_family: string|null
    construction_strategy: string|null
    improvement_strategy: string|null
    acceptance_strategy: string|null
    runtime_budget_strategy: string|null
  source_attempt:
    experiment_id: string
    candidate_id: string
    patch_digest: string
    selected_surface: string
  status:
    tier: weak_positive|no_effect|quality_regression|runtime_regression|invalid|promotable
    promoted: bool
    failure_reason_codes: [string]
  evidence:
    case_wins: int
    case_losses: int
    case_ties: int
    pair_wins: int|null
    pair_losses: int|null
    pair_ties: int|null
    median_delta: float|null
    runtime_ratio_median: float|null
    runtime_delta_median_ms: float|null
    activation_observed: bool
    effect_observed: bool|null
  interpretation:
    why_not_promoted: string
    repeat_unchanged_allowed: bool
    allowed_followup_variants: [string]
    blocked_followup_variants: [string]
    caution: string
  provenance:
    created_by: screening_feedback|manual_audit|external_runner
    raw_metrics_ref: string|null
    audit_refs: [string]
```

### How Follow-Up Should Work

For weak-positive records:

- Disallow unchanged repeats of the same mechanism signature.
- Encourage variants in trigger, schedule, threshold, composition, or narrower
  target locus.
- Require the next hypothesis to explain how it addresses prior losses, runtime
  cost, or insufficient win rate.
- Keep the branch alive only if the lifecycle policy sees valid activation and
  nontrivial evidence.

For no-effect records:

- Treat as neutral/negative unless the next proposal changes the integration
  point or effect path.
- Do not allow "add the same operator again" as a valid novelty claim.

For runtime-regression records:

- Require explicit runtime budget strategy and expected telemetry.
- Prefer schedule/gating/bounded-scan variants over broader mechanism expansion.

For quality-regression records:

- Warn that runtime savings are not enough under the current objective policy.
- Require a quality-preserving correction, not just a speed argument.

### Avoiding Weak-Positive Overclaiming

Prompt wording should be explicit:

- "Weak-positive is not promotable evidence."
- "Do not claim the mechanism works broadly."
- "Use it as a lead for a targeted variant."
- "A next proposal must change trigger, schedule, threshold, composition, or
  target locus."

Lifecycle should store weak-positive separately from promoted lineage. It should
not influence champion selection except through normal future gated candidates.

## Multi-File Patch, Novelty, And Target-File Repair Guidance

External attempts exposed two repairable friction points.

### C10 Novelty Signature Repair

Attempt 02 initially failed C10 because the novelty signature omitted required
solver-design identity fields.

Core should emit a structured repair template:

```yaml
repair_type: novelty_signature_missing_fields
check: C10_novelty
severity: light
missing_fields:
  - construction_strategy
  - acceptance_strategy
  - runtime_budget_strategy
required_template:
  novelty_signature:
    algorithm_family: "<generic family>"
    construction_strategy: "<unchanged|modified|new construction behavior>"
    improvement_strategy: "<what changes search/improvement behavior>"
    acceptance_strategy: "<unchanged|modified acceptance behavior>"
    runtime_budget_strategy: "<how runtime is bounded or reallocated>"
    mechanism_id: "<must match mechanism_changes and expected telemetry>"
agent_instruction:
  - "Do not invent problem facts."
  - "If a strategy is unchanged, say unchanged and name the baseline component from the active solver map."
  - "Mechanism id must match expected telemetry mechanism id."
```

Adapter/provider can add examples, but core owns the generic missing-field
diagnostic shape.

### Multi-File Target-File Repair

Attempt 04 initially failed patch contract because the primary
`PatchProposal.file_path` was the scheduler integration file while the approved
hypothesis `target_file` named the helper module.

The fix was to set `target_file` to the primary integration file and put helper
edits in `additional_changes`.

Structured repair template:

```yaml
repair_type: patch_primary_target_mismatch
check: C4b_patch_action_target
severity: heavy
observed:
  hypothesis_target_file: "..."
  patch_primary_file: "..."
  additional_change_files: ["..."]
recommended_shape:
  hypothesis_target_file: "<primary integration file>"
  patch:
    file_path: "<same primary integration file>"
    additional_changes:
      - file_path: "<helper module>"
reasoning:
  - "The primary target file is where the mechanism is wired into the active algorithm body."
  - "Helper modules may be modified as additional changes if allowlisted and reachable."
agent_instruction:
  - "If adding an operator plus registering it, use the registry/integration file as primary."
  - "If changing only a helper body already called by baseline, that helper can be primary."
```

For CVRP, the adapter can annotate integration files such as scheduler and
operator registries. Core should not hard-code those paths.

## External / Alternate-Agent Patch Runner

### Priority

P2 unless the team wants repeated external-agent comparisons. It is important
for reproducibility but not required for the internal APS capability uplift.

### Minimal CLI

Proposed command:

```bash
scion external-eval \
  --problem cvrp \
  --surface solver_design \
  --base-workspace /path/to/champion \
  --hypothesis hypothesis.json \
  --patch patch.json \
  --campaign-dir /path/to/output \
  --stage screening \
  --time-limit-sec 5 \
  --validation-if-pass
```

Inputs:

- `HypothesisProposal` JSON or YAML.
- `PatchProposal` JSON or YAML, including `additional_changes`.
- problem id and surface id.
- base workspace or champion snapshot.
- output directory.
- protocol mode: preview-only, verify-only, screening, validation-if-pass.

Outputs:

- normalized `external_eval_results.json`;
- contract result payloads;
- static preview payload;
- algorithm smoke payload;
- VerificationGate payload;
- canary/screening/validation/frozen protocol payloads as applicable;
- patch artifact and digests;
- raw metrics refs for audit;
- final advisory tier.

Required gate sequence:

1. schema load
2. hypothesis contract
3. patch contract
4. adapter static preview
5. proposal smoke
6. workspace materialization
7. VerificationGate
8. canary
9. screening
10. validation/frozen only if prior stage passes and flag allows

The runner must not expose validation/frozen details to the proposal agent. It is
an evaluation/reproducibility interface, not a bypass around Scion control.

### API Boundary

Core module boundary:

- `scion.external_eval.runner`: orchestration wrapper around existing gates.
- `scion.external_eval.io`: parse/validate proposal payloads.
- `scion.external_eval.report`: normalized result serialization.

Reuse existing modules:

- `ContractGate`
- adapter static preview
- solver-design smoke preview
- `WorkspaceMaterializer`
- `VerificationGate`
- `ExperimentProtocol`
- decision feature/tier extraction

Do not fork gate logic.

## Acceptance Criteria

P0/P1 active solver map:

- Proposal agent can call `context.read_active_solver_map` and receive a generic
  schema with entrypoints, editable files, registries, scheduler integrations,
  telemetry fields, and slice ids.
- CVRP provider fills the map for `solver_design` without adding CVRP-specific
  fields to core schema.
- `context.read_algorithm_slice` returns bounded source slices with digests,
  line spans where available, and read receipts.
- Repeated reads produce compact receipts unless requesting a new slice.
- Unit tests verify that validation/frozen details are never returned.

Screening feedback tiers:

- A mock screening result with 2W/1L/5T and activation observed classifies as
  `weak_positive`.
- A 0W/0L/8T active result classifies as `no_effect`.
- A runtime-saving but negative median-delta result classifies as
  `quality_regression`, not runtime success.
- A no-effect result with runtime over soft threshold classifies as
  `runtime_regression`.
- Tier output separates prompt-visible fields from audit-only refs.

Branch-local memory:

- Weak-positive memory blocks unchanged repeats but allows schedule/trigger/
  threshold/composition variants.
- No-effect memory blocks unchanged mechanism repeats.
- Quality-regression memory warns against speed-only hypotheses.
- Memory records store provenance and raw metric refs without embedding raw
  metrics into the prompt.

Novelty/target repair:

- Missing C10 novelty fields produce a structured repair template.
- Multi-file target mismatch produces a structured C4b repair template.
- Tests cover helper-primary vs integration-primary patch shapes.

External runner P2:

- A fixture hypothesis+patch can run through contract, preview, smoke,
  VerificationGate, canary, and screening using existing modules.
- The runner emits normalized results equivalent to internal candidate results.
- It cannot run validation/frozen unless screening/validation passes naturally.
- It writes audit artifacts under the requested output directory only.

## Test Plan

### Unit Tests

Core schema and tools:

- `test_active_solver_map_schema_is_problem_generic`
- `test_algorithm_slice_enforces_budget_and_receipt`
- `test_operator_registry_has_no_problem_specific_core_fields`
- `test_validation_frozen_not_exposed_by_context_tools`

CVRP provider:

- `test_cvrp_solver_design_active_map_contains_entrypoint_and_scheduler`
- `test_cvrp_solver_design_vns_registry_is_reported_by_provider`
- `test_cvrp_algorithm_slice_returns_target_function_body`
- `test_cvrp_provider_marks_integration_files_for_multifile_patch`

Feedback tiers:

- `test_screening_tier_weak_positive_pair_case_split`
- `test_screening_tier_no_effect_active_zero_wins`
- `test_screening_tier_quality_regression_overrides_runtime_speedup`
- `test_screening_tier_runtime_regression_for_no_effect_slowdown`

Memory:

- `test_mechanism_memory_blocks_unchanged_repeat`
- `test_mechanism_memory_allows_schedule_variant_for_weak_positive`
- `test_no_effect_memory_requires_changed_integration_or_mechanism`

Repair templates:

- `test_c10_novelty_missing_fields_returns_template`
- `test_c4b_multifile_primary_target_returns_template`

### Mock Campaign Tests

Create a mock APS session with these scripted outcomes:

1. candidate activates and has pair/case weak-positive result;
2. next candidate repeats unchanged mechanism and is rejected by memory guidance;
3. next candidate changes schedule/trigger and is allowed to proceed;
4. no-effect candidate writes neutral memory and changes future prompt hints.

Assertions:

- prompt context contains active solver map summaries and requested slices;
- prompt context contains weak-positive memory with caution text;
- decision still uses bounded `DecisionFeatures`;
- no raw validation/frozen detail leaks.

### Short Experimental Validation

Run 2-4 short APS rounds after implementation on the CVRP solver-design surface:

- Compare to a baseline APS run without active solver map/memory.
- Check whether the agent reads target/integration slices before code.
- Check whether it avoids unchanged repeats of no-effect mechanisms.
- Check whether weak-positive mechanisms are refined by trigger/schedule/
  threshold/composition rather than repeated.
- Check whether C10/C4b retries decrease.

Success is not immediate promotion. Success is better proposal behavior:

- fewer schema/target-file repair loops;
- fewer duplicate unchanged mechanisms;
- more grounded hypotheses tied to active solver map facts;
- clearer branch lifecycle records for valid but non-promoting candidates.

## Development Decomposition

Parallelizable:

- Active solver map core schema and context tool wrappers.
- CVRP provider implementation for map/registry/slices.
- Screening tier extraction and prompt rendering.
- Branch-local memory data model and prompt rendering.
- C10/C4b structured repair template rendering.
- P2 external runner scaffolding after result schemas stabilize.

Serial dependencies:

1. Core generic schemas should land before CVRP provider implementation.
2. Screening tier extraction should land before branch-local memory consumes it.
3. Active solver map tool output should land before prompt/read-receipt behavior
   is tuned.
4. Repair templates should land before final agent prompt tests are updated.
5. External runner should reuse finalized tier/report schemas rather than create
   its own result model.

## Sources

- External multiround report:
  `/home/clawd/research/scion-experiments/v04-v3-external-agent-gpt55-20260524T140321Z-claw/external_agent_multiround_report.md`
- Related prior note:
  `scion/docs/engineering/agentic-proposal-reference/08-p1-agentic-smoke-tooling-fixes-20260524.md`
