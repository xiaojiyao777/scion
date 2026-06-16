# Warehouse Validation-Transfer Quality Rerun 6R Launch - 2026-06-16

## Purpose

Field-check the warehouse validation-transfer proposal-quality repair from
commit `88e31d7` (`fix: gate warehouse validation-transfer quality`).

The preceding warehouse positive-diagnostic rerun restored validation
reachability but still failed research-quality acceptance:
`VALIDATION_FAIL_NO_HIERARCHICAL_GAIN`, no frozen row, and no promotion. This
rerun checks whether the new proposal-quality gate changes the live research
path before code generation.

Acceptance is not promotion-only. The field gate passes if the run is valid and
shows one of the following:

- transfer-blind warehouse operator hypotheses are blocked before code as
  `agent_quality_blocked:warehouse_validation_transfer_quality_missing`; or
- screened candidates carry explicit validation-transfer risk,
  proposal-level activation/effect diagnostic plans, and screening-only guards
  before their protocol outcomes are interpreted.

Do not loosen validation/frozen gates to compensate for weak research output.

## Launch

- Branch: `codex/v04-evidence-repair-plan`
- Commit: `88e31d7`
- WSL repo: `/home/xjy-ubuntu/research/or-autoresearch-agent`
- WSL root:
  `/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-validation-transfer-quality-rerun6r-20260616T195153Z`
- Server sync root:
  `/home/clawd/research/scion-experiments/v04-warehouse-validation-transfer-quality-rerun6r-20260616T195153Z`
- WSL tmux session: `scion_wh_transferqual_rerun6r_195153`
- Started at UTC: `2026-06-16T19:53:08Z`
- Python: `/home/xjy-ubuntu/miniconda3/envs/scion/bin/python`
- Model: local `gpt-5.5`
- API base: `http://127.0.0.1:8080`

## Shape

- Problem: warehouse production package
- CLI problem path: experiment-local WSL copy of `problem.yaml`
- Adapter/problem-v1 source: experiment-local WSL copy of `problem-v1.yaml`
- Protocol: `scion/problems/warehouse_delivery/protocol_prod.yaml`
- Split: experiment-local WSL copy of `split_manifest_prod.yaml`
- Seeds: `scion/problems/warehouse_delivery/seed_ledger.yaml`
- Rounds: `6`
- Cells: `1` (`rep01/on_compact`)
- Measurement governance: `on`
- Context profile: `compact-measurement-diagnostics`
- Time limit: `30s`
- Early stop: disabled
- Agentic proposal: enabled
- Agentic session timeout: `900s`
- Wrapper timeout: `6h`
- Control pair key: `warehouse.validation-transfer-quality-rerun6r:rep01`

## Launch Health

Initial checks passed:

- WSL checkout fast-forwarded cleanly to `88e31d7`.
- WSL Python dependencies, warehouse data roots, and surrogate root were
  present.
- Local proxy `/v1/models` exposed `gpt-5.5`.
- The tmux session started and wrote `status=running`.
- Initial artifacts were synced to the server root above.

## Acceptance

Postrun must inspect:

- wrapper `exit_code` and `run_validity.status`;
- effective rounds, proposal attempts, protocol rows, validation/frozen rows,
  formal candidate artifacts, verification failures, and proposal quality
  blocks;
- whether any blocked proposal uses the new
  `warehouse_validation_transfer_quality` gate and is counted as
  `agent_quality_blocked`, not infra;
- whether all non-blocked warehouse operator hypotheses visible in LLM traces
  include validation-transfer risk, activation/effect diagnostic plan, and
  screening-only guard;
- whether validation/frozen remain strict and no holdout per-case details leak
  into proposal context.

This is a short research-quality gate, not a warehouse longrun or v0.3
continuity claim.
