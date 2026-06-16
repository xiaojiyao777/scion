# Warehouse Pair-Signal Diagnostic Rerun 6R Launch - 2026-06-16

## Purpose

Run the short live warehouse field gate after commit `3ca26a0`
(`fix: admit warehouse pair signals to diagnostic validation`).

The prior `d666311` rerun accepted the targeted blocker repair but failed
research-quality acceptance because all six formal rows remained screening-only.
This rerun checks whether the warehouse measurement/protocol repair lets
pair-positive, non-regressive low-SNR branches enter diagnostic validation
without relaxing validation, frozen, or promotion gates.

## Launch

- Branch: `codex/v04-evidence-repair-plan`
- Commit: `3ca26a0`
- WSL repo: `/home/xjy-ubuntu/research/or-autoresearch-agent`
- WSL root:
  `/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-pairsignal-diagnostic-rerun6r-20260616T180447Z`
- Server sync root:
  `/home/clawd/research/scion-experiments/v04-warehouse-pairsignal-diagnostic-rerun6r-20260616T180447Z`
- WSL tmux session: `scion_wh_pairsignal_rerun6r_180447`
- Started at UTC: `2026-06-16T18:05:15Z`
- Python: `/home/xjy-ubuntu/miniconda3/envs/scion/bin/python`
- Model: local `gpt-5.5`
- API base: `http://127.0.0.1:8080`
- API key: WSL local proxy accepted `Authorization: Bearer pwd`; the key is
  not written into repo artifacts.

## Shape

- Problem: warehouse production package
- Protocol: `scion/problems/warehouse_delivery/protocol_prod.yaml`
- Split: experiment-local WSL copy of `split_manifest_prod.yaml`
- Safe data root: `/home/xjy-ubuntu/research/scion-data`
- Rounds: `6`
- Cells: `1` (`rep01/on_compact`)
- Measurement governance: `on`
- Context profile: `compact-measurement-diagnostics`
- Time limit: `30s`
- Early stop: disabled
- Agentic proposal: enabled
- Agentic session timeout: `900s`
- Wrapper timeout: `6h`

## Launch Health

Initial checks passed:

- WSL checkout fast-forwarded to `3ca26a0`.
- WSL Python, `pytest`, `yaml`, `sqlite3`, warehouse data roots, and surrogate
  root were present.
- Local proxy `/v1/models` exposed `gpt-5.5`.
- The tmux session started and wrote `status=running`.
- `run.log` reached campaign startup:
  `Starting campaign: warehouse_delivery (max_rounds=6, mock_llm=False, disable_early_stop=True)`.

## Acceptance

Accept this field gate only if:

- wrapper exits `0`;
- `run_validity.status=valid`;
- requested rounds, proposal attempts, protocol rows, validation/frozen rows,
  verification-only failures, quality blocks, and formal candidate artifacts
  reconcile;
- all LLM traces use `gpt-5.5` and have no auth/API failure;
- compared with the `d666311` rerun, pair-positive low-SNR screening evidence
  is no longer trapped as screening-only when the protocol policy applies;
- any validation or frozen rows are interpreted strictly, with no promotion
  unless frozen evidence passes the unchanged gate;
- branch-level postrun distinguishes confirmed signal from diagnostic
  validation rejection.

This is a short protocol-behavior field gate, not a warehouse efficacy claim.
