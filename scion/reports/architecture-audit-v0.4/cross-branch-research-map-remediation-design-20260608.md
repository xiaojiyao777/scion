# Cross-Branch Research Map Remediation Design

Date: 2026-06-08

Scope: source audit and repair design for the 12R cross-branch research map / branch lesson propagation finding. This report is design-only; no source files were changed.

## Executive Summary

The 12R result shows the current cross-branch research map is visible, tainted, and excluded from `DecisionFeatures`, which is the correct Architecture v3 boundary. The problem is not absence of context. The problem is that the context is mostly advisory: it describes sibling outcomes, near duplicates, material-difference pressure, and same-branch allowances, but it does not require the next hypothesis to name which sibling lesson it borrowed, avoided, contrasted, or preserved.

The minimal repair should not forbid same-family exploration. It should make clean forks and sibling-aware proposals carry a structured lesson-usage claim before code generation. Same-branch weak-positive refinement must remain allowed when the branch is actively refining its own evidence.

Recommendation: implement the P1 slice before treating a 20R run as a research-quality gate. A 20R run before this repair can still be useful as framework stress evidence, but not as strong evidence that global branch research layout has improved.

## Design Frame: Branch-Level Research And Cross-Branch Propagation

This design is explicitly about research behavior, not token/call efficiency and not Decision-layer inputs.

Scion should support two complementary research modes:

1. Branch-level research depth.
   A branch that finds a weak but real signal should be allowed to keep refining the same mechanism family. The right behavior is round 5-7 style: preserve the branch-local evidence, name the residual regression or uncertainty, and change a specific trigger, guard, activation path, or effect path. The framework should not force every weak-positive branch into a clean fork merely for portfolio diversity.

2. Cross-branch lesson propagation.
   A clean fork or sibling-aware proposal should not start as if prior sibling branches are just background text. It should explicitly say which sibling lesson it is applying:
   - borrow a weak-positive lesson into a different mechanism or target;
   - avoid a repeated no-effect/regression lesson;
   - contrast against a near-duplicate or saturated cluster;
   - bridge a low-confidence runtime/effect/activation evidence gap before spending another formal candidate.

The repair therefore adds proposal-visible structure around lesson application. It does not add cross-branch text or lesson fields to `DecisionFeatures`. The deterministic system only uses the structure for proposal quality governance before code generation and for reporting-only observability.

## Evidence Read

Required documents:

- `scion/design/scion-architecture-v3.md`
- `scion/reports/architecture-audit-v0.4/remediation-status.md`
- `scion/reports/experiments/v04-scheduler-reclaim-verify-12r-gpt55-20260607T233323Z-branch-research-analysis.md`
- `scion/reports/experiments/v04-scheduler-reclaim-verify-12r-gpt55-20260607T233323Z-framework-quality-acceptance.md`

Required source and tests:

- `scion/scion/proposal/context/cross_branch_research.py`
- `scion/scion/proposal/context/cross_branch_research_summary.py`
- `scion/scion/proposal/context/cross_branch_research_coverage.py`
- `scion/scion/proposal/context/cross_branch_research_support.py`
- `scion/scion/core/evidence_recording/cross_branch_observability.py`
- `scion/scion/proposal/context_manager/manager.py`
- `scion/scion/core/proposal_pipeline/facade.py`
- `scion/scion/tests/unit/test_cross_branch_research.py`
- `scion/scion/tests/unit/core/test_cross_branch_observability.py`
- `scion/scion/tests/unit/test_hypothesis_context_profiles.py`

Experiment artifacts sampled from:

`/home/clawd/research/scion-experiments/v04-scheduler-reclaim-verify-12r-gpt55-20260607T233323Z-12r-gpt55-20260607T233323Z-claw/campaign`

The final `campaign_summary.json` confirms `cross_branch_research_observability.policy=proposal_observability_only`, `decision_input_policy=excluded_from_decision_features`, `observable_step_count=12`, `cross_branch_map_seen_count=12`, `near_duplicate_count=1`, `material_difference_requirement_count=1`, `same_branch_refinement_allowance_count=5`, and `same_branch_refinement_not_selected_count=7`.

## Current Flow

1. `ProposalPipeline.generate_hypothesis()` collects active siblings from the branch controller, passes full `step_history`, branch workspace, search memory, saturation signals, and research log into `problem_runtime.build_hypothesis_context()`. This is proposal-layer input only.

2. `ContextManager.build_hypothesis_context()` filters safe hypothesis steps, builds branch history and sibling summaries, then calls `build_cross_branch_research_map(branch, [branch, *siblings], safe_hypothesis_steps, available_actions=...)`.

3. `build_cross_branch_research_map()`:
   - filters to screening and safe pre-protocol records;
   - builds per-branch summaries;
   - emits `similarity_hints`, `lesson_cards`, `lessons`, `portfolio_coverage`, `avoid_bridge_guidance`, `opportunity_gaps`, `novelty_pressure`, `material_difference_audit_records`, `portfolio_guidance`, and `portfolio_steering`;
   - marks the payload with `taint=proposal_research_feedback` and `decision_input_policy=excluded_from_decision_features`.

4. `filter_hypothesis_context_for_prompt()` removes the full payload and audit records from the prompt-visible context, then re-renders a compact `compact_cross_branch_learning.v1` block. This keeps the map visible while hiding full audit metadata, raw signatures, and material-difference audit records.

5. The hypothesis schema accepts `material_difference`, `novelty_signature`, `expected_telemetry`, and `mechanism_changes`, but it has no first-class `branch_lesson_usage` / `borrowed_lessons` / `avoided_lessons` field.

6. A separate material-difference path already exists:
   - scheduler/branch metadata can set `material_difference_required`;
   - context manager exposes `material_difference_requirement`;
   - prompt task lines require a non-empty `material_difference`;
   - `ExploreStepPipeline` blocks before code generation if a required `material_difference` is missing or boilerplate.

7. `cross_branch_observability` writes summary/status counters. It counts map visibility, near duplicate signatures, material-difference requirement records, same-branch refinement allowance, and not-selected clean-fork-like events. It does not measure whether the hypothesis used lessons well.

## Visibility Boundary

Proposal-visible fields and artifacts:

- Prompt-visible compact text: `cross_branch_research`, `sibling_summary`, `experiment_history`, `branch_followup_policy`, `material_difference_requirement`.
- Proposal-context internal/audit fields: `cross_branch_research_payload`, `cross_branch_research_audit_records`, `cross_branch_research_session_metadata`, `material_difference_audit_records`.
- LLM output fields: `hypothesis_text`, `novelty_signature`, `material_difference`, `expected_telemetry`, `mechanism_changes`.
- Reporting-only artifacts: `cross_branch_research_observability`, prompt manifests, visibility ledgers, session outputs.

Fields that must remain excluded from `DecisionFeatures`:

- `cross_branch_research`, `cross_branch_research_payload`, `similarity_hints`, `lessons`, `lesson_cards`, `novelty_pressure`, `portfolio_guidance`, `portfolio_coverage`, `portfolio_steering`, `avoid_bridge_guidance`, `opportunity_gaps`.
- `material_difference`, `material_difference_requirements`, `material_difference_audit_records`, `branch_lesson_usage`, `branch_lesson_audit_records`.
- Raw sibling summaries, raw hypothesis text, prompt manifests, prompt visibility ledgers, LLM trace content, and free-text branch lessons.

Decision may continue to read only deterministic `DecisionFeatures`: pass/fail booleans, stage, case/pair statistics, structured runtime evidence status/confidence, retry/failure codes, and other numeric/enumerated fields already in the safe feature extractor.

## Why The Current Map Is Advisory

1. Lessons are not response obligations.
   `lesson_cards` contain `lesson_type`, `failure_mode`, `evidence_strength`, `transferability`, `recommended_action`, `confidence`, and text summary. The next hypothesis is not required to cite a stable lesson id, source branch id, or avoided sibling signature.

2. `material_difference` is too narrow and episodic.
   The hard pre-code check only triggers when branch/session metadata says a material difference is required. In the 12R run it appeared once, while many later proposals still relied on descriptive contrasts inside `hypothesis_text` or a loose `material_difference` object.

3. The similarity model is shallow.
   Current generic similarity mostly uses mechanism family, target file, action, and change locus. That is useful, but it misses broader mechanism-shape repeats when a candidate changes file or surface while preserving the same failure pattern. In 12R, route-compaction-adjacent ideas were able to reappear through local search, repair, cross-route reconnect, and construction seed changes. Those are not identical, so they should not be banned, but clean forks should be forced to state a stronger contrast.

4. Same-branch refinement is represented, but sibling transfer is not.
   The map has `same_branch_refinement_allowances` and `sibling_duplication_allowed=false`, which preserves the right boundary. Missing is a structured distinction between:
   - preserve same-branch weak positive;
   - borrow a sibling weak-positive lesson into a different branch;
   - avoid a no-effect/regression sibling lesson;
   - contrast against a saturated sibling cluster.

5. Observability proves visibility, not usage quality.
   `cross_branch_map_seen_count=12` proves the map was available. `near_duplicate_count=1` and `material_difference_requirement_count=1` prove some pressure existed. There is no counter for `lesson_usage_required_count`, `lesson_usage_satisfied_count`, `borrowed_lesson_count`, `avoided_lesson_count`, or `clean_fork_contrast_satisfied_count`.

6. Prompt compaction drops some enforcement-relevant detail.
   The compact context intentionally hides audit records and full signatures. That is good for safety, but if no stable compact lesson ids are projected, the LLM can only paraphrase lessons rather than cite exact structured obligations.

## Design Principles

- Keep the repair generic. No CVRP, VRP, route, ALNS, VNS, fleet, capacity, or demand semantics in generic Scion core.
- Do not let branch lessons enter `DecisionFeatures`.
- Do not ban same-family exploration. Require explicit contrast or borrowed/avoided lesson claims for clean forks and sibling-aware proposals.
- Preserve same-branch weak-positive refinement when the current branch is active and the proposal names the evidence it is preserving.
- Reuse the existing `material_difference` pattern: proposal-visible requirement, compact structured output, pre-code quality block, and reporting-only observability.

## P1 Repair Slice

P1 should be framed around two protected paths:

- Same-branch continuation path: preserve freedom to refine an active weak-positive branch when the hypothesis states the local evidence it is preserving and the specific failure/regression it is trying to avoid.
- Clean-fork / sibling-aware path: require explicit application or contrast of sibling lessons before code generation when the scheduler chooses a new branch or the proposal is near a sibling signature.

### P1.1 Add Stable Branch Lesson Records

Write domain:

- `scion/scion/proposal/context/cross_branch_research_support.py`
- `scion/scion/proposal/context/cross_branch_research.py`
- `scion/scion/proposal/context/research_portfolio.py` if cluster-owned lessons are easier to keep there.

Add a compact generic schema:

```json
{
  "schema_version": "branch_lesson.v1",
  "lesson_id": "lesson:<digest>",
  "source": "proposal_only",
  "decision_input_policy": "excluded_from_decision_features",
  "scope": "branch_local | cross_branch | cluster",
  "lesson_role": "preserve | borrow | avoid | contrast | bridge",
  "lesson_type": "weak_positive | no_effect | regression | abandoned | parked | near_duplicate | saturated_signature",
  "maturity": "fresh | repeated | saturated | closed",
  "source_branch_ids": ["..."],
  "shared_signature": {
    "mechanism_family": "...",
    "target_file": "...",
    "action": "...",
    "change_locus": "..."
  },
  "evidence_basis": {
    "outcome_patterns": {},
    "activation_statuses": {},
    "effect_statuses": {},
    "runtime_evidence_statuses": {}
  },
  "required_response": {
    "required_for": "clean_fork_new_branch | sibling_nearby_attempt | same_branch_refinement",
    "required_output_field": "branch_lesson_usage",
    "minimum_requirement": "name_borrowed_or_avoided_lesson_and_contrast_dimension",
    "required_contrast_dimensions": [
      "mechanism_family",
      "target_file",
      "action",
      "change_locus",
      "effect_path",
      "activation_path",
      "runtime_budget_strategy"
    ],
    "same_branch_refinement_allowed": true,
    "sibling_duplication_allowed": false
  },
  "reason_codes": ["BRANCH_LESSON_REQUIRED"]
}
```

This record should be digest-stable like `material_difference_requirement.v1`, bounded, and raw-text-free.

### P1.2 Add Hypothesis `branch_lesson_usage`

Write domain:

- `scion/scion/core/models.py`
- `scion/scion/proposal/schemas/hypothesis.py`
- `scion/scion/proposal/engine/parsing.py`
- `scion/scion/proposal/engine/hypothesis_prompts.py`
- `scion/scion/proposal/tools/previews/schema.py`
- agentic schema retry/preview files if required by existing structured retry flow.

Add a proposal-only field:

```python
branch_lesson_usage: Dict[str, Any] = field(default_factory=dict)
```

Suggested normalized JSON shape:

```json
{
  "borrowed_lessons": [
    {"lesson_id": "lesson:...", "source_branch_ids": ["..."], "borrowed_signal": "activation_policy"}
  ],
  "avoided_lessons": [
    {"lesson_id": "lesson:...", "avoid_reason": "no_effect_cluster"}
  ],
  "contrasted_lessons": [
    {
      "lesson_id": "lesson:...",
      "contrast_dimensions": ["target_file", "effect_path"],
      "new_path": "compact_generic_token"
    }
  ],
  "preserved_same_branch_lesson": {
    "lesson_id": "lesson:...",
    "preserved_signal": "compact_generic_token",
    "risk_to_avoid": "compact_generic_token"
  },
  "clean_fork_diversity_claim": {
    "required": true,
    "changed_dimensions": ["mechanism_family", "target_file"],
    "sibling_duplication_allowed": false
  }
}
```

Normalization should mirror `normalize_material_difference()`: bounded strings, small arrays, shallow dicts, and removal of raw text, prompt, trace, transcript, rationale, and hypothesis prose keys.

### P1.3 Require Lesson Usage For Clean Forks And Sibling-Nearby Proposals

Write domain:

- `scion/scion/core/scheduling/audits.py`
- `scion/scion/core/branch_step_runner.py`
- `scion/scion/proposal/context_manager/manager.py`
- new `scion/scion/core/explore_step/branch_lesson_usage.py` or an extension beside `material_difference.py`
- `scion/scion/core/explore_step/pipeline.py`

Implement a record parallel to `material_difference_requirement_record()`:

```json
{
  "schema_version": "branch_lesson_usage_requirement.v1",
  "record_type": "branch_lesson_usage_requirement",
  "record_id": "branch_lesson_usage_requirement:<digest>",
  "requirement_source": "clean_fork_diversity_pressure | sibling_nearby_pressure | weak_positive_transfer",
  "required_for": "clean_fork_new_branch",
  "required_output_field": "branch_lesson_usage",
  "candidate_branch_ids": ["..."],
  "candidate_lesson_ids": ["lesson:..."],
  "proposal_visibility_only": true,
  "proposal_guidance_only": true,
  "decision_features_excluded": true
}
```

The pre-code check should block only when a requirement is active and `branch_lesson_usage` is missing, metadata-only, or boilerplate. It should not inspect raw hypothesis prose.

Policy:

- Clean fork after repeated no-effect, near duplicate, saturated signature, runtime-saturation reroute, or low-value branch release: require `branch_lesson_usage`.
- Sibling-nearby proposal: require at least one `avoided_lessons` or `contrasted_lessons` item and one changed generic dimension.
- Same-branch active weak-positive refinement: allow continuation with `preserved_same_branch_lesson`; do not require avoid/contrast against the same branch, but still disallow sibling duplication.
- Weak-positive transfer into a different branch: require `borrowed_lessons` plus `contrasted_lessons`, so it is a transfer, not a copy.

This is the central behavior change. A weak-positive branch keeps local freedom if it can state "I am preserving this local signal and changing this activation/effect/guard dimension." A clean fork gets stricter because it is spending global search budget; it must state "I am borrowing/avoiding/contrasting these sibling lessons and changing these generic dimensions." Both paths remain proposal-visible only.

### P1.4 Improve Generic Mechanism Similarity Clusters

Write domain:

- `scion/scion/proposal/context/cross_branch_research_coverage.py`
- `scion/scion/proposal/context/research_portfolio.py`
- tests in `test_cross_branch_research.py`.

Add `mechanism_similarity_clusters` or extend `portfolio_steering.clusters` with generic fields:

```json
{
  "cluster_id": "cluster:<digest>",
  "cluster_type": "generic_mechanism_similarity",
  "similarity_basis": [
    "mechanism_family",
    "target_file",
    "action",
    "change_locus",
    "effect_status",
    "activation_status",
    "runtime_budget_strategy",
    "novelty_signature_keys"
  ],
  "branch_ids": ["..."],
  "outcome_patterns": {},
  "cluster_signal": "no_effect_plateau | weak_positive_transfer | regression_cluster | near_repeat",
  "recommended_action": "avoid | borrow | contrast | bridge | refine",
  "required_contrast_dimensions": ["effect_path", "activation_path", "target_file"],
  "same_branch_refinement_allowed": true,
  "sibling_duplication_allowed": false
}
```

This should be generic. The default implementation can use existing mechanism ids, target/action/locus, evidence profile, runtime budget strategy text tokens, and normalized novelty signature keys. Problem-owned semantic providers can be P2, not required for P1.

### P1.5 Extend Observability To Measure Usage Quality

Write domain:

- `scion/scion/core/evidence_recording/cross_branch_observability.py`
- `scion/scion/core/evidence_recording/summary_visibility.py`
- `scion/scion/core/evidence_recording/summary.py`
- `scion/scion/core/evidence_recording/status.py`

Add reporting-only counters:

- `branch_lesson_record_count`
- `branch_lesson_usage_requirement_count`
- `branch_lesson_usage_satisfied_count`
- `branch_lesson_usage_missing_block_count`
- `borrowed_lesson_count`
- `avoided_lesson_count`
- `contrasted_lesson_count`
- `preserved_same_branch_lesson_count`
- `clean_fork_contrast_satisfied_count`
- `weak_positive_transfer_count`

These counters must be derived from proposal/session/branch metadata and `HypothesisProposal.branch_lesson_usage`, never from raw prompt text.

## P2 Follow-Ups

1. Problem-owned similarity provider extension.
   Add an optional adapter/provider hook that can emit problem-specific similarity tokens into generic cluster inputs. Generic Scion should only consume opaque tokens and must not contain CVRP/VRP terms.

2. Target-intent diversity steering.
   Feed high-priority lesson requirements into hypothesis target-intent preflight so the host selection step can avoid selecting a near-repeat target before formal hypothesis generation.

3. Post-run research-quality analytics.
   Add report helpers that compare `branch_lesson_usage` against actual mechanism family spread, formal candidate layout, and repeated no-effect clusters.

4. Stronger code-session self-check.
   During code generation, make the self-check verify that implemented `mechanism_changes` and telemetry still match the approved `branch_lesson_usage` contrast. This remains proposal/Contract/preview quality governance, not Decision.

## Test Plan

P1 unit tests:

- `test_cross_branch_research.py`
  - emits stable `branch_lesson.v1` records with `lesson_id`;
  - projects `required_response` for no-effect, regression, near duplicate, saturated cluster, and active weak-positive branch;
  - verifies generic core still contains no problem-specific terms;
  - verifies same-branch weak-positive allows refinement while sibling duplication remains false.

- `test_hypothesis_context_profiles.py`
  - compact prompt keeps lesson ids, role, maturity, required output field, and required contrast dimensions;
  - full audit records and raw text remain hidden;
  - `branch_lesson_usage_requirement` is kept only when active and non-empty.

- proposal schema/parsing tests
  - parses and normalizes `branch_lesson_usage`;
  - drops raw/prose/trace/prompt/transcript/rationale keys;
  - keeps bounded compact fields.

- new or extended explore-step tests
  - blocks before code when `branch_lesson_usage_requirement` is active and output is missing;
  - rejects boilerplate-only lesson usage;
  - allows same-branch weak-positive refinement with `preserved_same_branch_lesson`;
  - requires clean-fork contrast when sibling-nearby pressure is active.

- `test_cross_branch_observability.py`
  - counts lesson records, usage requirements, satisfied usage, missing blocks, borrowed/avoided/contrasted/preserved lessons;
  - confirms all new observability remains `proposal_observability_only` and `excluded_from_decision_features`.

- Decision boundary tests
  - extend existing assertions so `branch_lesson_usage`, `branch_lesson_records`, `branch_lesson_usage_requirement`, and related counters are not `DecisionFeatures` fields.

Focused validation after implementation:

```bash
python -m pytest -q \
  scion/scion/tests/unit/test_cross_branch_research.py \
  scion/scion/tests/unit/test_hypothesis_context_profiles.py \
  scion/scion/tests/unit/core/test_cross_branch_observability.py \
  scion/scion/tests/unit/core/test_branch_step_runner_scheduler_metadata.py \
  scion/scion/tests/test_models.py
```

Then run the existing core focused suite that covers proposal pipeline and scheduler metadata.

## Acceptance Criteria

P1 is accepted when all of the following are true:

1. Branch-level research depth is preserved: an active weak-positive branch can continue same-mechanism refinement when the hypothesis includes `preserved_same_branch_lesson`, names the local signal being preserved, and names the specific regression/uncertainty being guarded against.

2. Clean fork lesson propagation is enforced: a clean fork selected under repeated low-value/no-effect/near-duplicate pressure exposes an active `branch_lesson_usage_requirement` in prompt-visible context.

3. A hypothesis on a required clean fork cannot reach code generation unless it has compact `branch_lesson_usage` naming at least one borrowed, avoided, or contrasted sibling lesson and at least one changed generic contrast dimension.

4. Sibling-aware proposals distinguish borrow vs copy: transferring a weak-positive lesson across branches requires both `borrowed_lessons` and `contrasted_lessons`; repeating a no-effect/regression sibling pattern requires an `avoided_lessons` or `contrasted_lessons` claim.

5. Sibling-nearby duplication remains allowed only with explicit contrast dimensions; there is no deterministic Decision-layer block.

6. `DecisionFeatures` has no cross-branch lesson fields, no raw text fields, and no prompt/session manifest fields.

7. `campaign_summary.json` exposes reporting-only usage counters, so a future 12R/20R report can distinguish "map was visible" from "map shaped branch-level research and clean-fork layout".

8. Generic Scion core remains free of CVRP/VRP/domain terms in the new cross-branch lesson code.

## Recommended Development Order

1. Add `branch_lesson.v1` records and compact prompt projection.
2. Add `HypothesisProposal.branch_lesson_usage` schema/parsing/normalization.
3. Add `branch_lesson_usage_requirement.v1` metadata and pre-code block.
4. Add observability counters and Decision exclusion tests.
5. Run focused unit suites.
6. Run a short 4R/8R smoke to verify prompt manifests, usage counters, and no Decision boundary regression.
7. Re-run 12R or proceed to 20R only after the usage counters prove the agent is naming borrowed/avoided/contrasted lessons.

## Recommendation

Develop P1 now. It is small enough to implement without changing Decision semantics and directly addresses the 12R failure mode: visibility without enough instruction pressure. P2 can wait until after one post-P1 smoke run shows whether generic lesson usage is sufficient.
