# Warehouse Research-Loop Repair Short 6R Launch - 2026-06-16

## Purpose

Run a short warehouse field check after the first research-loop quality repair
slice. This is not a warehouse longrun and not a promotion/efficacy claim. It
checks whether the repaired proposal loop changes agent behavior after the
previous no-hard-truncation `4R` field check passed prompt/context validity but
failed research quality.

Primary questions:

- Does the deterministic branch-lesson repair skeleton reduce semantic
  `branch_lesson_usage` quality blocks?
- Does warehouse `vehicle_level` guidance avoid a repeat unsafe split/merge
  removal that fails `V5_solution_consistency`?
- If a marginal branch survives screening, does the next same-branch hypothesis
  perform causal follow-up on positive cases with `effect_path` and
  `no_op_condition`, rather than broad unrelated exploration?

## Launch

- Branch: `codex/v04-evidence-repair-plan`
- Commit: `0bb99ec` (`fix: steer warehouse research followups`)
- WSL repo: `/home/xjy-ubuntu/research/or-autoresearch-agent`
- WSL root:
  `/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-research-loop-repair-short-6r-20260616T165145Z`
- Server sync root:
  `/home/clawd/research/scion-experiments/v04-warehouse-research-loop-repair-short-6r-20260616T165145Z`
- WSL tmux session: `scion_wh_repair6r_20260616T165145Z`
- Started at UTC: `2026-06-16T16:51:45Z`
- Python: `/home/xjy-ubuntu/miniconda3/envs/scion/bin/python`
- Model: local `gpt-5.5`
- API base: `http://127.0.0.1:8080`
- API key source: WSL-local `codex-proxy/data/local.yaml:server.proxy_api_key`
  read at runtime; the key is not written into artifacts.

## Shape

- Problem: warehouse production package
- Protocol: experiment-local copy of `protocol_prod.yaml`
- Split: experiment-local copy of `split_manifest_prod.yaml`
- Safe data root: `/home/xjy-ubuntu/research/scion-data`
- Rounds: `6`
- Cells: `1`
- Measurement governance: `on`
- Context profile: `compact-measurement-diagnostics`
- Time limit: `30s`
- Early stop: disabled
- Agentic proposal: enabled
- Agentic session timeout: `900s`
- Wrapper timeout: `6h`

## Launch Health

Initial checks passed:

- WSL checkout fast-forwarded to `0bb99ec`.
- WSL Python, `gpt-5.5` `/v1/models`, warehouse data roots, and surrogate root
  were present.
- The run entered `status=running` and created `status.json` /
  `run_status.json`.
- `run.log` reached campaign startup:
  `Starting campaign: warehouse_delivery (max_rounds=6, mock_llm=False, disable_early_stop=True)`.
- Initial artifacts were synced to the server root above.

## Acceptance

Accept this field check only if:

- wrapper exits `0`;
- `run_validity.status=valid`;
- all LLM traces use `gpt-5.5` and have no auth/API failure;
- requested rounds, proposal attempts, Protocol rows, verification-only
  failures, quality blocks, and formal candidate artifacts reconcile;
- compared with the prior no-hard-truncation `4R` field check, research-loop
  behavior improves: fewer or better-repaired branch-lesson semantic quality
  blocks, no repeat unsafe split/merge removal `V5_solution_consistency`
  failure, and any retained marginal branch receives same-mechanism causal
  follow-up with `effect_path`/`no_op_condition` language;
- prompt/context checks remain clean enough to interpret the behavior path, but
  prompt visibility alone is not sufficient for acceptance.

Decision/Protocol boundaries remain unchanged. Branch lessons, prompt guidance,
and marginal follow-up instructions are proposal-only material and excluded
from `DecisionFeatures`.
