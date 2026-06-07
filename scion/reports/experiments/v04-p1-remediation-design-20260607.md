# Scion v0.4 P1 Remediation Design

Date: 2026-06-07

Scope: design for the next remediation wave after the 4R `gpt-5.5` campaign
`v04-post-runtime-guidance-4r-gpt55-20260607T062920Z-claw`.

Design anchors:

- `scion/design/scion-architecture-v3.md`
- `scion/docs/AGENT_ONBOARDING.md`
- `scion/reports/experiments/v04-post-runtime-guidance-4r-gpt55-20260607T062920Z-analysis.md`
- `scion/reports/experiments/v04-post-runtime-guidance-4r-gpt55-20260607T062920Z-retry-quality-audit.md`
- `scion/reports/experiments/v04-context-tooling-deep-audit-20260607.md`

Non-negotiable boundary:

- Decision reads only structured `DecisionFeatures`.
- LLM proposal text, tool observations, repair context, and cross-branch memory are tainted.
- CVRP/VRP facts remain in problem-owned artifacts, adapters, providers, problem specs, or solver policies.
- Production promotion remains fail-closed; incomplete runtime evidence must not promote.

## Current Confirmed State

Already implemented locally but not committed:

1. Itemized quality-block/accounting observability.
2. `screened_not_effective` / formal-effective accounting visibility.
3. Code-stage telemetry identity repair prompt/feedback strengthening.

Focused tests already passed in the main session:

- accounting/proposal: 100 passed
- agentic repair/session: 117 passed
- CLI/summary smoke: 18 passed
- `git diff --check`: passed

These changes should be committed before the next development wave, or kept as the
base patch while the next workers build on top of them.

## P1-A: Production Fail-Closed Boundary

Confirmed issue:

- `ProblemSpecV1` / bridged production path is mostly closed.
- The remaining gap is legacy `ProblemSpec + adapter`: `adapter is not None` can
  still avoid production boundary checks unless the legacy spec explicitly sets
  `requires_adapter_for_runtime`.
- `allow_non_strict_runtime_verification=True` can still be used as a non-skeleton
  escape hatch for adapter-backed legacy campaigns.

Design:

1. Extend production detection from "problem spec requires adapter runtime" to
   "adapter-backed campaign" unless explicit skeleton mode is enabled.
2. Add a single predicate used by composition and CLI wiring, for example:
   `is_adapter_backed_production_campaign(problem_spec, adapter, allow_skeleton_mode)`.
3. Validate the final constructed verification gate, not only a caller-supplied
   gate. The production boundary should run after default gate construction.
4. Reject non-strict runtime verification for adapter-backed non-skeleton
   campaigns.
5. Keep old demo/skeleton behavior only behind an explicit `allow_skeleton_mode`
   / `--allow-skeleton` path.

Patch surface:

- `scion/scion/core/production_boundary.py`
- `scion/scion/core/verification_factory.py`
- `scion/scion/core/campaign_composition.py`
- `scion/scion/cli/commands/init_run.py`

Tests:

- Adapter-backed legacy spec without metric specs fails unless skeleton mode.
- Adapter-backed legacy spec without canary split/seed fails unless skeleton mode.
- Adapter-backed legacy spec with non-strict runtime verification fails unless skeleton mode.
- Custom non-strict verification gate is rejected for adapter-backed non-skeleton campaigns.

## P1-B: Agentic Output Problem/Spec Anchors

Confirmed state:

- `CampaignManager` / `compose_campaign_services()` path already passes
  `problem_id`, `problem_spec_hash`, `split_manifest_hash`, and `seed_ledger_hash`.
- Agentic request/tool context carries those anchors.
- `AgenticValidationMixin` rejects missing/mismatched anchors when expected values
  are non-null.
- These anchors are not in `DecisionFeatures`, which matches v3.

Remaining hardening:

- Manual or external `ProposalPipeline(...)` construction can still leave expected
  anchors as `None`; validation then skips them.

Design:

1. Add a production/agentic preflight check that expected anchors are non-empty
   before building an agentic request in non-skeleton production mode.
2. Keep anchors as proposal validation/audit metadata only.
3. Do not add problem/spec/split/seed anchors to `DecisionFeatures`.

Patch surface:

- `scion/scion/core/proposal_pipeline/agentic_requests.py`
- `scion/scion/core/proposal_pipeline/agentic_validation.py`
- `scion/scion/core/campaign_composition.py`

Tests:

- Hypothesis and code agentic request contexts include all four anchors.
- Agentic output missing `problem_id` fails when expected anchor is set.
- Agentic output missing `seed_ledger_hash` fails when expected anchor is set.
- `DecisionFeatures` does not contain problem/spec/split/seed anchors.

## P1-C: Lifecycle Policy / Decision Boundary

Confirmed issue:

- Lifecycle policy currently runs inside `DecisionEngine` after the stage decision.
- It can turn a `CONTINUE_EXPLORE` stage outcome into `ABANDON` through
  `archive_lineage` or `soft_abandon`.
- `park_lineage` preserves `CONTINUE_EXPLORE` but changes branch fate in
  `DecisionFinalizer`.
- This is deterministic and mostly based on structured `DecisionFeatures`, not
  LLM free text, but it is not explicit enough as a single final decision.

Design:

1. Keep lifecycle-affecting behavior inside `DecisionEngine`; do not move it to a
   post-decision external policy.
2. Make the output explicit:
   - candidate/stage decision
   - final decision
   - lifecycle action
   - lifecycle reason codes
   - decision layer/source
3. Remove or tightly deprecate finalizer fallback that reconstructs lifecycle
   action from legacy reason strings. New runs should only honor explicit
   `DecisionResult.lifecycle_action`.
4. Scheduler may honor Decision-origin park markers for resource reconciliation,
   but should not independently convert candidate outcome into archive/abandon.

Patch surface:

- `scion/scion/core/decision.py`
- `scion/scion/core/decision_finalizer.py`
- `scion/scion/core/models.py`
- relevant decision/finalizer tests

Tests:

- `QUEUE_VALIDATE`, `QUEUE_FROZEN`, and `PROMOTE` cannot receive lifecycle rewrites.
- Lifecycle-caused `ABANDON` has structured lifecycle action and reason codes.
- Finalizer does not park/archive when `lifecycle_action` is empty, even if legacy
  lifecycle-like reason strings exist.
- `decision_features_json` excludes proposal text / branch direction / free-text history.

## P1-D: Runtime Evidence / Fresh Champion Routing

Confirmed state:

- Promotion strictness is correct and should stay fail-closed.
- This 4R run does not show runtime/fresh champion gating blocking a candidate that
  had already passed objective-quality screening.
- `low_cached_champion` / `fresh_champion_required` was reasonable in the observed
  all-tie or marginal cases.

Confirmed gap:

- At screening, `fresh_champion_required` becomes generic `CONTINUE_EXPLORE`; there
  is no explicit "rerun same candidate with fresh champion runtime" route.

Design:

1. Do not relax validation/frozen/promotion runtime evidence gates.
2. Separate reason semantics:
   - objective fail
   - runtime fresh champion required
   - runtime incomplete advisory
   - runtime budget saturation
3. For now, implement audit/routing visibility before changing experiment behavior:
   `fresh_champion_required` at screening should be visible as a distinct rerun
   recommendation, not only generic continue.
4. A future behavior change can add a capped fresh-champion re-screen path for
   runtime-tie candidates. Do not implement this until the audit fields show it is
   needed, because it adds runtime cost and campaign accounting complexity.

Patch surface:

- `scion/scion/protocol/gates.py`
- `scion/scion/protocol/experiment/stages.py`
- `scion/scion/core/decision.py`
- `scion/scion/core/screening_visibility.py`
- status/summary accounting if a new audit field is added

Tests:

- Validation/frozen with insufficient or cached runtime evidence cannot promote.
- Screening `fresh_champion_required` exposes distinct reason/rerun recommendation.
- Objective-fail and runtime-evidence-incomplete reason codes are distinguishable.

## P1-E: Context / Tooling After Rawls

Rawls conclusion:

- Tools are necessary and aligned with v3.
- The problem is not tool existence; the cost is repeated LLM `tool_selection` for
  a mostly deterministic default sequence.
- The 4R run had 94/116 traces as `tool_selection`, with 1.45M input tokens.
- Evidence that framework rules consumed model effort is narrow and real only
  around telemetry identity repair; tooling did not prevent research.

Design for this wave:

1. Do not cut tools.
2. Do not remove contract/schema/telemetry governance.
3. Add observability first:
   - per-session tool-selection ledger
   - result novelty (`new`, `duplicate`, `empty`, `summary_only`)
   - deterministic prefetch plan id
   - prompt block profile and inclusion reason
   - repair guidance trigger
4. Defer deterministic prefetch and context profile behavior changes until after
   the next 4R shows the ledger data.

Patch surface:

- `scion/scion/proposal/engine/tool_selection.py`
- agentic session trace/session artifact writing
- prompt manifest generation
- status/summary trace index if already centralized

Tests:

- Tool-selection ledger is emitted for hypothesis and code sessions.
- Repeated/empty feedback observations are classified.
- Prompt manifest sections carry block family/profile/inclusion reason.

## Recommended Development Order

1. Commit the already verified quality-block/accounting/telemetry-repair patch.
2. Worker 1: production fail-closed + anchor hardening.
3. Worker 2: lifecycle explicit final decision semantics and finalizer fallback removal.
4. Worker 3: runtime/fresh champion audit reason separation, no promotion relaxation.
5. Worker 4: context/tooling observability only, no behavioral prefetch yet.
6. Main session runs focused tests plus `git diff --check`.
7. Run fresh 4R on local `gpt-5.5`.

Acceptance before next 4R:

- New code does not add CVRP/VRP facts to generic Scion core.
- New fields are audit/proposal visibility unless they are structured
  `DecisionFeatures`.
- No incomplete runtime evidence can promote.
- Quality/retry/tool ledgers let a reviewer map every attempt/block/retry to a
  concrete artifact.
