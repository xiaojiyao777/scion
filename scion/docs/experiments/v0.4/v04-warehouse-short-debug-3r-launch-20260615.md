# Warehouse Short Debug 3R Launch - 2026-06-15

## Purpose

This is the short warehouse follow-up after the one-candidate lifecycle gate
passed. It is designed to test whether the repaired warehouse path can produce
multiple Protocol rows, preserve branch continuity, and use marginal screening
evidence in later proposals before any full `3 x 24R` longrun is relaunched.

This is not a governance on/off comparison and not a promotion-power
experiment. It is a compact ON-arm debug.

## Launch

- Server root:
  `/home/clawd/research/scion-experiments/v04-warehouse-short-debug-3r-20260615T201259Z`
- WSL root:
  `/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-short-debug-3r-20260615T201259Z`
- WSL tmux session: `scion_warehouse_short3r_201259`
- Started at UTC: `2026-06-15T20:14:17Z`
- Repository on WSL: `/home/xjy-ubuntu/research/or-autoresearch-agent`
- Commit: `dabfcee`
- Python: `/home/xjy-ubuntu/miniconda3/envs/scion/bin/python`
- Model: local `gpt-5.5`
- API base: `http://127.0.0.1:8080`

## Shape

- Problem: warehouse production package
- Protocol: `scion/problems/warehouse_delivery/protocol_prod.yaml`
- Split: experiment-local copied `split_manifest_prod.yaml`
- Safe data root: `/home/xjy-ubuntu/research/scion-data`
- Rounds: `3`
- Cells: `1`
- Measurement governance: `on`
- Context profile: `compact-measurement-diagnostics`
- Time limit: `30s`
- Early stop: disabled
- Agentic proposal: enabled
- Session timeout: `900s`
- Wrapper timeout: `4h`

## Launch Health Check

Initial server-side probe after launch confirmed:

- `status.txt` exists and reports `status=running`
- `commit=dabfcee`
- `run_status.json`, `status.json`, `scion.db`, and `run.log` exist
- `run.log` reached campaign startup:
  `Starting campaign: warehouse_delivery (max_rounds=3, mock_llm=False, disable_early_stop=True)`

## Acceptance

Accept this run as a valid short debug only if:

- wrapper exits `0`;
- `run_validity.status=valid`;
- more than one Protocol row is present, or any shortfall is explained by a
  concrete postrun failure class;
- Contract, Verification, and canary failures are reconciled separately from
  Protocol negatives;
- branch depth, same-mechanism continuation, prompt composition, and use of
  prior marginal screening evidence are inspected.

The next full warehouse longrun remains blocked until this short debug is
postrun-audited.
