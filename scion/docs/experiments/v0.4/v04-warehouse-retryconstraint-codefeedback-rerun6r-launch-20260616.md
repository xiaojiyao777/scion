# Warehouse Retry-Constraint Code Feedback Rerun Launch

*Date: 2026-06-16*
*Commit: `3c2b7b5`*
*Status: running on WSL*

## Purpose

Field-check commit `3c2b7b5` (`fix: preserve quality retry constraints`).

The previous `5f2d418` rerun restored the full warehouse research path and
promoted champion v2, but quality-block ledgers still carried a generic novelty
retry constraint. This rerun keeps the same short production shape and checks
whether problem-owned warehouse retry constraints remain visible in durable
quality feedback and the next code prompt.

This is a quality-feedback acceptance rerun. Promotion is useful evidence but
not required for the narrow gate.

## Launch

- WSL root:
  `/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-retryconstraint-codefeedback-rerun6r-3c2b7b5-20260616T214445Z`
- Expected server sync root:
  `/home/clawd/research/scion-experiments/v04-warehouse-retryconstraint-codefeedback-rerun6r-3c2b7b5-20260616T214445Z`
- WSL tmux session:
  `scion_wh_retryconstraint_rerun6r_3c2b7b5_214445`
- Status file:
  `/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-retryconstraint-codefeedback-rerun6r-3c2b7b5-20260616T214445Z/status.txt`

## Shape

- Problem: warehouse production package with copied WSL-safe configs.
- Protocol: `scion/problems/warehouse_delivery/protocol_prod.yaml`.
- Split: copied `split_manifest_prod.yaml` with WSL safe data root.
- Seeds: `scion/problems/warehouse_delivery/seed_ledger.yaml`.
- Rounds: `6`.
- Solver cap: `--time-limit-sec 30`.
- Measurement governance: `on`.
- Proposal context ablation: `compact-measurement-diagnostics`.
- Early stop: disabled.
- Agentic proposal: enabled.
- Agentic session timeout: `900s`.
- Model: local `gpt-5.5`.
- Control pair key: `warehouse.retryconstraint-codefeedback-rerun6r:rep01`.

## Initial Health Check

WSL launch succeeded:

```text
status=running
started_at_utc=2026-06-16T21:45:20Z
commit=3c2b7b5
rounds=6
cell=rep01/on_compact
```

The first observed output was a hypothesis-stage
`warehouse_validation_transfer_quality_missing` block with missing
`validation_transfer_risk`, `activation_effect_diagnostics`, and
`screening_only_guard`. This is expected under the gate. Acceptance depends on
whether the resulting ledger and later prompts preserve the problem-owned
constraint fields.

Early synced status after two quality blocks already shows the repaired field
path:

- `warehouse_validation_transfer_quality` preserves:
  `Rewrite the warehouse operator hypothesis before code: state the
  screening-to-validation transfer risk, declare expected activation/effect
  diagnostics, and explain the guard against screening-only improvements.`
- `warehouse_validation_transfer_patch_quality` preserves:
  `Revise the warehouse operator patch before protocol: add code-visible
  activation/effect diagnostic counters or a named instrumentation path, and
  include a guard that prevents screening-only or lexicographically dominated
  moves.`
- `missing_code_elements` is present for the patch-quality block.

This is an early field signal only. Final acceptance still requires wrapper
exit, synced final artifacts, code prompt visibility, and a full postrun audit.
