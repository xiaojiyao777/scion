# Warehouse Validation-Transfer Patch Quality Rerun 6R Launch - 2026-06-16

## Purpose

Field-check the warehouse validation-transfer patch-quality repair. This rerun
starts after the local acceptance report:

`scion/docs/experiments/v0.4/v04-warehouse-validation-transfer-patch-quality-repair-20260616.md`

The target failure mode is specific: a warehouse operator hypothesis can satisfy
the validation-transfer text requirements, but its code patch may still omit
the activation/effect diagnostics or instrumentation path it promised. The new
gate should block those patches before Protocol as
`agent_quality_blocked:warehouse_validation_transfer_patch_quality_missing`.

This is not a warehouse longrun or v0.3 continuity claim. Do not loosen
validation/frozen gates.

## Launch

- Branch: `codex/v04-evidence-repair-plan`
- Commit: `b7627fc` (`fix: normalize agentic quality block details`)
- Repair commit: `e07bcc9` (`fix: gate warehouse validation-transfer patch quality`)
- WSL repo: `/home/xjy-ubuntu/research/or-autoresearch-agent`
- WSL root:
  `/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-validation-transfer-patch-quality-rerun6r-20260616T201601Z`
- Server sync root:
  `/home/clawd/research/scion-experiments/v04-warehouse-validation-transfer-patch-quality-rerun6r-20260616T201601Z`
- WSL tmux session: `scion_wh_patchqual_rerun6r_201601`
- Started at UTC: `2026-06-16T20:16:19Z`
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
- Control pair key:
  `warehouse.validation-transfer-patch-quality-rerun6r:rep01`

## Launch Health

Initial checks passed:

- WSL checkout fast-forwarded cleanly to `b7627fc`.
- WSL Python dependencies, warehouse data roots, and surrogate root were
  present.
- Local proxy `/v1/models` exposed `gpt-5.5`.
- The tmux session started and wrote `status=running`.
- Initial artifacts were synced to the server root above.
- A first hypothesis-stage quality block was recorded without the former
  duplicate `agent_quality_blocked:agent_quality_blocked` detail prefix.

An earlier shakedown root ending `20260616T201139Z` was stopped before
acceptance because it exposed the duplicate quality-block prefix fixed by
`b7627fc`. Treat that root as launch/debug evidence only.

## Acceptance

Postrun must inspect:

- wrapper `exit_code` and `run_validity.status`;
- effective rounds, proposal attempts, protocol rows, validation/frozen rows,
  formal candidate artifacts, verification failures, and proposal quality
  blocks;
- whether weak hypotheses are blocked by
  `warehouse_validation_transfer_quality_missing`;
- whether text-qualified but code-underdelivered patches are blocked by
  `warehouse_validation_transfer_patch_quality_missing` before Protocol;
- whether any non-blocked patch includes executable or observable
  activation/effect diagnostics plus a screening-only or lexicographic guard;
- whether validation/frozen remain strict and no holdout per-case details leak
  into proposal context.

Acceptance is not promotion-only. The gate passes if the run validly proves the
new patch-quality route either blocks the target failure mode or lets only
diagnostic-bearing patches proceed to ordinary Contract/Verification/Protocol.
