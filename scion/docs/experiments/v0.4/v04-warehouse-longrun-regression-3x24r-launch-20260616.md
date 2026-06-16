# Warehouse Longrun Regression 3x24R Launch - 2026-06-16

## Purpose

Run a valid warehouse longrun after the latest v0.4 warehouse prompt/guidance
and preflight repairs. The goal is to test whether the current Scion v0.4
warehouse research path has regressed relative to the v0.3 evidence that showed
repeat promotions and continuous improvement.

This is not a governance ON/OFF comparison. It is a single intended-default arm
to answer whether v0.4 can still perform effective warehouse research under a
longer budget, or whether it plateaus for substantive reasons.

## v0.3 Reference

The v0.3 archive establishes the regression reference:

- Production rerun after evidence/runtime fixes: Sonnet `3/3` campaigns
  promoted.
- Strongest synthetic Sonnet campaign reached `4` promotions
  (`v2` through `v5`).
- v0.3 closure validation expected at least `2.0` average Sonnet synthetic
  promotions across three seeds when checking regression recovery.

The v0.4 warehouse run is production warehouse, not the old synthetic matrix, so
the pass/fail interpretation must include champion quality/gap, branch depth,
Protocol rows, and whether no-promotion means real plateau rather than
framework failure.

## Design

- Problem: warehouse production protocol/split/seeds.
- Model: local `gpt-5.5`.
- Arm: `measurement_governance=on`.
- Prompt context: `compact-measurement-diagnostics`.
- Rounds: `24` per repeat.
- Repeats: `3`.
- Solver cap: `--time-limit-sec 30`.
- Early stop: disabled.
- Agentic session timeout: `900s`.
- Commit: `f384884`.
- WSL scheduling: max two concurrent cells; `rep02` starts after a `900s`
  stagger; `rep03` starts after `rep01` completes.

## Artifacts

Server prep root:

`/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z`

WSL run root:

`/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z`

Script:

`/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z/run_wsl.sh`

WSL tmux session:

`scion_wh_longrun_reg_071323`

Launch status:

- Started at `2026-06-16T07:16:00Z`.
- Initial health check confirmed the tmux session is live.
- `status.txt` reports `status=running`, commit `f384884`, rounds `24`,
  repeats `3`, parallelism `2`, `measurement_governance=on`, and
  `context=compact-measurement-diagnostics`.
- `rep01/on_compact/run.log` has started and reports
  `Starting campaign: warehouse_delivery (max_rounds=24, mock_llm=False,
  disable_early_stop=True)`.

The script writes experiment-local WSL copies of `problem.yaml`,
`problem-v1.yaml`, and `split_manifest_prod.yaml`, replacing server absolute
paths with WSL paths.

## Preflight

The launch script includes the short-debug preflight that the invalid 3x24R run
lacked:

- Python deps: `pytest`, `yaml`, `sqlite3`.
- Local gateway exposes `gpt-5.5`.
- WSL warehouse data roots exist.
- WSL checkout is exactly commit `f384884`.

## Acceptance Analysis

Postrun must report:

- wrapper exit and per-cell exit codes;
- requested rounds, effective rounds, counted Protocol rows, validation rows,
  frozen rows, promotions, and final champion version;
- champion quality/gap against the production reference where available;
- whether each repeat shows continuous promotion, real plateau, or
  pre-Protocol/framework failure;
- branch depth, same-mechanism continuation, clean-fork behavior, and branch
  lesson semantic satisfaction;
- prompt/context composition and whether compact research signals were still
  truncated or drowned by general/tool-selection payload;
- verification failures, patch-edit failures, stale-source/old-string failures,
  and no-effect fresh-runtime replay drain.

Interpretation guard: if a repeat produces `0` Protocol rows or substantial
pre-Protocol verification loops, classify it as framework/agentic-path failure,
not as evidence that warehouse has no remaining research opportunity.
