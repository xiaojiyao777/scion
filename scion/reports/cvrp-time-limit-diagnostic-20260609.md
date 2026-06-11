# CVRP Champion Baseline Time-Limit Diagnostic

Date: 2026-06-09

Scope: problem/protocol-layer diagnosis for CVRP/VRP ALNS/VNS runtime. No generic Scion core changes were made.

## Question

Assess whether the current Scion CVRP experiment launcher budget, `--time-limit-sec 10`, is enough for champion/baseline ALNS/VNS screening runs.

## Relevant Paths

- Repo root: `/home/clawd/research/or-autoresearch-agent`
- VRP data root used by launched experiment: `/home/clawd/research/or-autoresearch-agent/vrp`
- Original VRP benchmark runner: `/home/clawd/research/or-autoresearch-agent/vrp/benchmark.py`
- Original VRP ALNS/VNS implementation: `/home/clawd/research/or-autoresearch-agent/vrp/src/solver.py`
- Scion CVRP solver facade: `/home/clawd/research/or-autoresearch-agent/scion/scion/problems/cvrp/solver.py`
- Scion active baseline/champion algorithm: `/home/clawd/research/or-autoresearch-agent/scion/scion/problems/cvrp/policies/baseline_algorithm.py`
- Active ALNS/VNS scheduler/config: `/home/clawd/research/or-autoresearch-agent/scion/scion/problems/cvrp/policies/baseline_modules/scheduler.py`, `/home/clawd/research/or-autoresearch-agent/scion/scion/problems/cvrp/policies/baseline_modules/config.py`
- Experiment root: `/home/clawd/research/scion-experiments/v04-p2-auditability-verify-cvrp-40r-gpt55-20260609T114757Z-claw`
- Copied champion workspace used for direct supplemental runs: `/home/clawd/research/scion-experiments/v04-p2-auditability-verify-cvrp-40r-gpt55-20260609T114757Z-claw/campaign/champions/champion_v1`
- Supplemental analysis artifacts: `/home/clawd/research/scion-experiments/v04-p2-auditability-verify-cvrp-40r-gpt55-20260609T114757Z-claw/analysis/cvrp_time_budget_20260609T170000Z`

## Config Boundaries

Three configuration surfaces are distinct:

1. Current repo source under `scion/scion/problems/cvrp/formal/*`.
2. Launch-time command/config in the experiment root.
3. Copied campaign/champion config under `campaign/champions/champion_v1/formal/*` and copied workspaces.

The launched wrapper recorded:

```bash
/home/clawd/miniconda3/envs/claw/bin/python -m scion.cli.main run \
  --problem scion/problems/cvrp/problem.yaml \
  --protocol scion/problems/cvrp/formal/protocol.yaml \
  --split scion/problems/cvrp/formal/split_manifest.yaml \
  --seeds scion/problems/cvrp/formal/seed_ledger.yaml \
  --campaign-dir /home/clawd/research/scion-experiments/v04-p2-auditability-verify-cvrp-40r-gpt55-20260609T114757Z-claw/campaign \
  --rounds 40 \
  --time-limit-sec 10 \
  --agentic-session-timeout-sec 900 \
  --disable-early-stop \
  --agentic-proposal
```

The launch env set:

```bash
SCION_PROBLEM_DATA_ROOT=/home/clawd/research/or-autoresearch-agent/vrp
TIME_LIMIT_SEC=10
```

The copied champion formal config observed during this diagnosis has:

- screening seeds: `11, 29`
- validation seeds: `47, 53`
- frozen seeds: `61, 67`
- copied screening cases include `A-n32-k5`, `A-n80-k10`, `E-n101-k8`, `P-n101-k4`
- copied frozen cases include `X-n401-k29`, `X-n1001-k43`
- copied formal stage budgets still say screening `3s`, validation `5s`, frozen `8s`, final `10s`

For this active experiment, the effective solver budget passed by the launcher is the global `--time-limit-sec 10`, not those copied per-stage values. The baseline algorithm then applies `BASELINE_TIME_FRACTION = 0.80`, so a 10s launcher budget normally gives the ALNS/VNS algorithm about 8s of internal search before JSON output/teardown.

## Existing Runtime Fields

Metrics already contain reusable runtime evidence:

- `campaign/metrics/champion_result_cache/*/*.json`
- `run_result.elapsed_ms`: subprocess wall time from the runner.
- `run_result.output.runtime.elapsed_s`: solver-reported elapsed time.
- `run_result.output.runtime.solver_algorithm_elapsed_ms`: active algorithm elapsed time.
- `run_result.output.runtime.solver_algorithm_stop_reason`: `completed`, `time_limit`, etc.
- `run_result.output.objective.total_distance`, `routes`: objective and route count.

The existing champion cache covered 6 relevant 10s rows for the selected old-screening sample. Supplemental direct runs filled the rest.

## Reproducible Commands

Inspect launch-time command and env:

```bash
sed -n '1,220p' /home/clawd/research/scion-experiments/v04-p2-auditability-verify-cvrp-40r-gpt55-20260609T114757Z-claw/run.sh
sed -n '1,220p' /home/clawd/research/scion-experiments/v04-p2-auditability-verify-cvrp-40r-gpt55-20260609T114757Z-claw/launch.env
```

Inspect copied config:

```bash
sed -n '1,220p' /home/clawd/research/scion-experiments/v04-p2-auditability-verify-cvrp-40r-gpt55-20260609T114757Z-claw/campaign/champions/champion_v1/formal/budgets.json
sed -n '1,120p' /home/clawd/research/scion-experiments/v04-p2-auditability-verify-cvrp-40r-gpt55-20260609T114757Z-claw/campaign/champions/champion_v1/formal/seed_ledger.yaml
sed -n '1,120p' /home/clawd/research/scion-experiments/v04-p2-auditability-verify-cvrp-40r-gpt55-20260609T114757Z-claw/campaign/champions/champion_v1/formal/split_manifest.yaml
```

Run a single direct champion solver case:

```bash
cd /home/clawd/research/scion-experiments/v04-p2-auditability-verify-cvrp-40r-gpt55-20260609T114757Z-claw/campaign/champions/champion_v1
PYTHONPATH="$PWD:/home/clawd/research/or-autoresearch-agent/scion" \
SCION_PROBLEM_DATA_ROOT=/home/clawd/research/or-autoresearch-agent/vrp \
SCION_SELECTED_SURFACE=solver_design \
/home/clawd/miniconda3/envs/claw/bin/python solver.py \
  /home/clawd/research/or-autoresearch-agent/vrp/cvrplib/E/E-n101-k8.vrp \
  --seed 11 \
  --time-limit 30 \
  --registry "" \
  --output /tmp/e-n101-k8-seed11-tl30.json
```

Aggregated supplemental outputs:

- CSV: `/home/clawd/research/scion-experiments/v04-p2-auditability-verify-cvrp-40r-gpt55-20260609T114757Z-claw/analysis/cvrp_time_budget_20260609T170000Z/cvrp_time_budget_runs.csv`
- JSON: `/home/clawd/research/scion-experiments/v04-p2-auditability-verify-cvrp-40r-gpt55-20260609T114757Z-claw/analysis/cvrp_time_budget_20260609T170000Z/cvrp_time_budget_runs.json`
- Individual supplemental solver outputs: same directory, named `{case}_seed{seed}_tl{time_limit}.json`

## Case/Seed Results

Median values are by case and time limit. For old-screening cases, `10s` rows came from existing champion cache when available; `20s` and `30s` rows are supplemental direct champion runs.

| case | class | seeds | time limit | median solver s | median cost | median BKS gap | stop reason(s) |
|---|---|---:|---:|---:|---:|---:|---|
| A-n32-k5 | old screening easy | 11,29 | 10 | 8.02 | 784.0 | 0.00% | completed |
| A-n32-k5 | old screening easy | 11,29 | 20 | 16.03 | 784.0 | 0.00% | completed |
| A-n32-k5 | old screening easy | 11,29 | 30 | 24.03 | 784.0 | 0.00% | completed |
| A-n80-k10 | old screening medium | 11,29 | 10 | 8.61 | 1832.5 | 3.94% | completed |
| A-n80-k10 | old screening medium | 11,29 | 20 | 16.34 | 1832.5 | 3.94% | completed |
| A-n80-k10 | old screening medium | 11,29 | 30 | 24.30 | 1831.5 | 3.89% | completed |
| E-n101-k8 | old screening hard | 11,29 | 10 | 9.08 | 866.0 | 6.26% | completed |
| E-n101-k8 | old screening hard | 11,29 | 20 | 17.33 | 866.0 | 6.26% | completed |
| E-n101-k8 | old screening hard | 11,29 | 30 | 25.41 | 848.5 | 4.11% | completed |
| M-n200-k17 | formal screening larger | 11,29 | 10 | 10.13 | 1357.0 | 6.43% | time_limit |
| M-n200-k17 | formal screening larger | 11,29 | 20 | 18.66 | 1357.0 | 6.43% | completed, time_limit |
| M-n200-k17 | formal screening larger | 11,29 | 30 | 29.33 | 1357.0 | 6.43% | time_limit |
| X-n401-k29 | frozen large | 61 | 10 | 11.11 | 68439.0 | 3.45% | time_limit |
| X-n401-k29 | frozen large | 61 | 30 | 32.69 | 68387.0 | 3.38% | time_limit |
| X-n1001-k43 | frozen xlarge | 61 | 10 | NA | NA | NA | subprocess timeout |
| X-n1001-k43 | frozen xlarge | 61 | 30 | 29.52 | 76942.0 | 6.34% | time_limit |

Aggregate supplemental/cache sample:

- rows: 28
- successful solver outputs: 27
- failed solver outputs: 1 (`X-n1001-k43`, seed `61`, `10s`, subprocess timed out after 18s without a usable JSON objective)
- `10s` rows: 6 `completed`, 3 `time_limit`, 1 subprocess timeout
- `20s` rows: 7 `completed`, 1 `time_limit`
- `30s` rows: 6 `completed`, 4 `time_limit`

## Interpretation

`10s` is enough for very small/easy old-screening cases. `A-n32-k5` is already at BKS at 10s and does not improve at 20s or 30s.

`10s` is marginal for old screening as a general budget. `E-n101-k8` improves from median cost `866.0` / gap `6.26%` at 10s to median cost `848.5` / gap `4.11%` at 30s. That is a material quality difference for a screening comparison even though the stop reason says `completed`.

`10s` is not a reliable budget for larger validation/frozen-style cases. `M-n200-k17` and `X-n401-k29` report `time_limit`, and `X-n1001-k43` at 10s failed to produce a usable solver output under an 18s subprocess guard. The xlarge case did produce a valid result at 30s, but still ended with `time_limit`.

`completed` should not be read as convergence for the old small cases. Because the algorithm uses `BASELINE_TIME_FRACTION = 0.80`, `10s` launcher budget produces about `8s` internal algorithm time. The observed runtimes near `8s`, `16s`, and `24s` for 10/20/30s runs show the algorithm is budget-bound by design; it is not proving that no more search is useful.

## Recommendation

Use `10s` only as a cheap smoke/sanity screening budget for small old-screening cases where the goal is fast throughput and rough signal.

For regular screening on the copied old-screening set, use `30s` if quality sensitivity matters. `20s` did not improve the sampled `A-n80-k10` or `E-n101-k8`; `30s` did improve `E-n101-k8` materially.

For a staged protocol:

- Stage 0 smoke: `10s`, small copied screening cases only.
- Stage 1 screening: `30s`, at least for cases around 80-150 nodes or cases with prior gap above roughly 4-5%.
- Stage 2 validation/frozen: `60s` minimum for large X/M/tai cases, with explicit attention to subprocess guard and solver JSON emission.

For redesigned/frozen cases, do not rely on `10s`. Use at least `30s` for preliminary checks and prefer `60s` when the case dimension is above roughly 300 or when `solver_algorithm_stop_reason=time_limit` appears.

## Notes

- No source files were intentionally modified for this diagnosis.
- The repo already had unrelated modified/untracked Scion formal/report files before this report was added; they were not reverted or edited.
- This diagnosis did not move CVRP/VRP semantics into generic Scion core.
