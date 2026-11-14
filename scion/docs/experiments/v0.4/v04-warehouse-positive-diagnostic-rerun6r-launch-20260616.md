# Warehouse Positive Diagnostic Rerun 6R Launch - 2026-06-16

Purpose:

- Field-check the warehouse-owned positive diagnostic protocol repair from
  commit `41d02d1`.
- Verify that expanded-exhausted, non-regressive, positive-CI low-SNR warehouse
  evidence can reach diagnostic validation instead of remaining screening-only.
- Preserve fail-closed behavior for negative-median and loss-dominated
  evidence.

Run:

- Branch: `codex/v04-evidence-repair-plan`
- Commit: `41d02d1`
- WSL root:
  `/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-positive-diagnostic-rerun6r-20260616T190605Z`
- Expected server sync root:
  `/home/clawd/research/scion-experiments/v04-warehouse-positive-diagnostic-rerun6r-20260616T190605Z`
- WSL tmux session: `scion_wh_posdiag_rerun6r_20260616T190605Z`
- Cell: `rep01/on_compact`
- Rounds: `6`
- Problem: warehouse production package
- Protocol: `scion/problems/warehouse_delivery/protocol_prod.yaml`
- Split: production warehouse split copied into the experiment config directory
- Seeds: `scion/problems/warehouse_delivery/seed_ledger.yaml`
- Model: local `gpt-5.5`
- Proposal mode: `--agentic-proposal`
- Measurement governance: `on`
- Proposal context ablation: `compact-measurement-diagnostics`
- Solver cap: `30s`
- Early stop: disabled
- Control pair key: `warehouse.positive-diagnostic-rerun6r:rep01`

Launch health:

- WSL checkout was fast-forwarded cleanly to `41d02d1`.
- `status.txt` reached `status=running` at `2026-06-16T19:06:05Z`.
- `tmux has-session` confirmed the run is active.

Acceptance:

- Validity: wrapper exit `0`, copied configs present, reports generated, and all
  formal candidates reconciled.
- Protocol repair: any expanded-exhausted positive field shape like `3/1/10`
  case W/L/T, `13/6/9` pair W/L/T, median `300`, CI low `0` should queue
  diagnostic validation.
- Strictness: negative-median and loss-dominated evidence must not queue
  validation.
- Research quality: validation/frozen/promotion evidence is required before
  accepting warehouse efficacy; more screening-only rows are insufficient.
