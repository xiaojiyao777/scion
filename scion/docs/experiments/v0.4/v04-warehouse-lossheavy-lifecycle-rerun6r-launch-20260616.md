# Warehouse Loss-Heavy Lifecycle Rerun 6R Launch - 2026-06-16

Purpose:

- Field-check the generic loss-dominated marginal lifecycle repair from commit
  `6e3988c`.
- Verify that a warehouse branch with repeated loss-dominated marginal evidence
  no longer consumes repeated same-branch formal screening rows.
- Preserve the pair-signal diagnostic protocol repair: pair-positive,
  non-regressive expanded-borderline evidence may still enter diagnostic
  validation, but validation/frozen/promotion gates remain strict.

Architecture boundary:

- This run tests generic lifecycle governance over deterministic
  `DecisionFeatures` numbers and generic lifecycle tiers.
- Warehouse problem semantics remain in the warehouse problem package and
  proposal context.
- Raw LLM text, branch lessons, prompt content, and raw observability do not
  enter Decision.

Run:

- Branch: `codex/v04-evidence-repair-plan`
- Commit: `6e3988c`
- WSL root:
  `/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-lossheavy-lifecycle-rerun6r-20260616T184031Z`
- Expected server sync root:
  `/home/clawd/research/scion-experiments/v04-warehouse-lossheavy-lifecycle-rerun6r-20260616T184031Z`
- WSL tmux session: `scion_wh_lossheavy_rerun6r_20260616T184031Z`
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
- Control pair key: `warehouse.loss-heavy-lifecycle-rerun6r:rep01`

Launch health:

- WSL checkout was fast-forwarded cleanly to `6e3988c`.
- Local `gpt-5.5` proxy preflight is delegated to `run_wsl.sh`.
- `status.txt` reached `status=running` at `2026-06-16T18:40:32Z`.
- `tmux has-session` confirmed the session is running.

Acceptance:

- Validity: wrapper exit `0`, copied configs present, reports generated, and all
  formal candidates reconciled.
- Lifecycle repair: repeated loss-dominated marginal/no-effect follow-ups should
  park or reroute instead of producing a four-row same-branch loop like
  `1/2/3` case W/L/T and `3/4/5` pair W/L/T.
- Preservation: pair-positive marginal evidence should not be parked by the new
  loss-heavy rule.
- Strictness: no loss-heavy or negative-median candidate may reach validation;
  validation/frozen/promotion must still require ordinary protocol evidence or
  the conservative pair-level diagnostic route.
