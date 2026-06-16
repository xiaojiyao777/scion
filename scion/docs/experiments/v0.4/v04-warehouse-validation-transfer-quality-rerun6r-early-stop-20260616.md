# Warehouse Validation-Transfer Quality Rerun 6R Early-Stop - 2026-06-16

## Scope

This is not a completed warehouse efficacy run. It is an early-stop acceptance
sample for the warehouse validation-transfer proposal-quality repair from
commit `88e31d7`.

The run was stopped deliberately after it exposed a remaining research-quality
gap: warehouse hypotheses can now be blocked before code when they omit
validation-transfer diagnostics, but code-stage patches can still pass without
actually implementing the activation/effect diagnostics promised by the
hypothesis.

## Artifacts

- Launch report:
  `scion/docs/experiments/v0.4/v04-warehouse-validation-transfer-quality-rerun6r-launch-20260616.md`
- WSL root:
  `/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-validation-transfer-quality-rerun6r-20260616T195153Z`
- Server sync root:
  `/home/clawd/research/scion-experiments/v04-warehouse-validation-transfer-quality-rerun6r-20260616T195153Z`
- Commit: `88e31d7`
- Cell: `rep01/on_compact`
- Model: `gpt-5.5`
- Wrapper exit: `143` / `SIGTERM`
- Ended at UTC: `2026-06-16T19:58:17Z`

## Observed State At Stop

- `proposal_attempts_total=4`
- `effective_rounds_completed=1`
- `llm_model_counts={"gpt-5.5": 8}`
- `llm_request_kind_counts={"hypothesis": 4, "tool_selection": 2, "code": 2}`
- `proposal_quality_blocks=2`
- `protocol_stage_counts={"screening": 1, "validation": 0, "frozen": 0}`
- `formal_screened_candidates=1`
- `validation_protocol_results=0`
- `frozen_protocol_results=0`

The proposal-quality hook fired twice before code:

- branch `8d734d45-a229-463d-ae67-f8a8d307bf2e` was blocked for
  `missing=activation_effect_diagnostics`;
- branch `eb9afc76-7f94-4593-855c-1a4e5bc23a04` was blocked for
  `missing=validation_transfer_risk`.

This proves the hypothesis-stage warehouse gate is active and counted as
`agent_quality_blocked`, not infra.

## Acceptance Failure

The first non-blocked candidate reached screening and failed badly:

- branch `8d734d45-a229-463d-ae67-f8a8d307bf2e`
- mechanism `same_subcategory_group_merge`
- tier `regression`
- case-level W/L/T `0/4/2`
- median delta `-4575.0`
- screening reason `SCREENING_FAIL_WIN_RATE`
- lifecycle archived by loss/non-positive-ci/negative-delta rules
- phase activation summary:
  `activation_status=not_declared`, `effect_status=not_declared`,
  `telemetry_outcome=fail`

The corresponding accepted hypothesis explicitly claimed validation-transfer
risk and diagnostic expectations such as `operator_invocations`,
`eligible_vehicle_or_order_groups_seen`, `accepted_moves`, `split_delta_sum`,
`cost_delta_sum`, and `improving_move_count`. The code patch did not provide a
recognizable diagnostic state, counter path, or telemetry/instrumentation route
for those promised activation/effect signals. In other words, the agent learned
to write the right proposal language, but the framework did not force the code
patch to make that language executable or observable.

The second non-blocked hypothesis showed the same pattern: it mentioned
eligible groups, accepted moves, `cost_delta_sum`, and `split_delta_sum`, but
its patch was still an operator rewrite without a code-stage quality gate that
requires those diagnostics to exist in the patch.

## Decision

Reject this rerun as a research-quality acceptance run. Do not interpret the
`SIGTERM` as a campaign failure and do not loosen validation/frozen gates.

Accepted next repair direction:

- add a generic core problem-owned patch/code quality hook that runs after code
  generation and before Protocol;
- keep warehouse-specific semantics in `WarehouseDeliveryAdapter`;
- block high-risk warehouse operator patches when the approved hypothesis
  promised validation-transfer diagnostics but the patch does not expose
  recognizable activation/effect counters or an explicit instrumentation path;
- record such failures as `agent_quality_blocked`, not infra, and exclude them
  from `DecisionFeatures`.

Worker `Raman` (`019ed204-5f15-7132-b16c-f5b65c744b22`) owns the concrete code
repair. Main-session acceptance requires focused unit tests, compile,
`git diff --check`, and then a fresh short warehouse rerun from the repair
commit.
