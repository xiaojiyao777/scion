# Warehouse Research-Loop Repair Rerun 6R Launch - 2026-06-16

## Purpose

Run the short live warehouse field gate after commit `d666311`
(`fix: repair warehouse research loop blockers`). The prior short `6R` field
check was valid execution evidence but failed research-quality acceptance. This
rerun checks whether the targeted repairs reduce the observed failure modes:

- concrete branch-lesson usage that is repairable by the skeleton should not
  block before code;
- existing imported warehouse operator deletion should be rejected by the
  problem-owned preview layer instead of reaching heavy V5 verification;
- fragile local nested dict state-key edits should be rejected before V5;
- retained marginal branches should still receive same-mechanism causal
  follow-up.

This is not a warehouse longrun and not an efficacy claim. It is a short
acceptance gate for the repair slice.

## Launch

- Branch: `codex/v04-evidence-repair-plan`
- Commit: `d666311` (`fix: repair warehouse research loop blockers`)
- WSL repo: `/home/xjy-ubuntu/research/or-autoresearch-agent`
- WSL root:
  `/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-research-loop-repair-rerun6r-20260616T173136Z`
- Server sync root:
  `/home/clawd/research/scion-experiments/v04-warehouse-research-loop-repair-rerun6r-20260616T173136Z`
- WSL tmux session: `scion_wh_repair_rerun6r_173136`
- Started at UTC: `2026-06-16T17:33:02Z`
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

- WSL checkout fast-forwarded to `d666311`.
- WSL Python, `pytest`, `yaml`, `sqlite3`, warehouse data roots, and surrogate
  root were present.
- Local proxy `/v1/models` exposed `gpt-5.5`.
- The tmux session started and wrote `status=running`.
- `run.log` reached campaign startup:
  `Starting campaign: warehouse_delivery (max_rounds=6, mock_llm=False, disable_early_stop=True)`.
- Initial artifacts were synced to the server root above.

## Acceptance

Accept this field check only if:

- wrapper exits `0`;
- `run_validity.status=valid`;
- requested rounds, proposal attempts, Protocol rows, verification-only
  failures, quality blocks, and formal candidate artifacts reconcile;
- all LLM traces use `gpt-5.5` and have no auth/API failure;
- compared with the failed `0bb99ec` 6R check, the run has fewer or repaired
  branch-lesson semantic quality blocks and fewer verification-consumed unsafe
  warehouse operator failures;
- any retained marginal branch receives same-mechanism causal follow-up with
  concrete activation/no-op/effect-path reasoning;
- prompt/context visibility remains clean enough to interpret the behavior
  path.

Decision/Protocol boundaries remain unchanged. The new repairs are proposal
canonicalization and problem-owned preview checks only; they do not alter
`DecisionFeatures`, promotion, or protocol gates.
