# v0.4 CVRP Baseline-Strength Phase B Launch

*Date: 2026-06-14*
*Status: launched; sequential matrix running*
*Run commit: `8311879`*

## Summary

Phase B has been launched as a matched CVRP baseline-strength research-surface
contrast. The matrix is running sequentially, not concurrently, to avoid mixing
CPU contention and wall-clock runtime interference into the budget-exhausting
CVRP evidence.

Group root:

`/home/clawd/research/scion-experiments/v04-cvrp-baseline-strength-phaseB-matched-20260614T024206Z-claw`

Matrix runner:

- PID: `2060750`
- Started: `2026-06-14T02:46:13Z`
- Status file:
  `/home/clawd/research/scion-experiments/v04-cvrp-baseline-strength-phaseB-matched-20260614T024206Z-claw/matrix_status.tsv`
- Log:
  `/home/clawd/research/scion-experiments/v04-cvrp-baseline-strength-phaseB-matched-20260614T024206Z-claw/matrix.log`

The first active cell at launch check was `rep01/alns_vns`.

## Cells

Prepared cells:

- `rep01/alns_vns`:
  `/home/clawd/research/scion-experiments/v04-cvrp-baseline-strength-phaseB-matched-20260614T024206Z-claw/cells/v04-cvrp-phaseB-rep01-alns-vns-8r-gpt55-20260614T024540Z-claw`
- `rep01/alns_only`:
  `/home/clawd/research/scion-experiments/v04-cvrp-baseline-strength-phaseB-matched-20260614T024206Z-claw/cells/v04-cvrp-phaseB-rep01-alns-only-8r-gpt55-20260614T024540Z-claw`
- `rep02/alns_vns`:
  `/home/clawd/research/scion-experiments/v04-cvrp-baseline-strength-phaseB-matched-20260614T024206Z-claw/cells/v04-cvrp-phaseB-rep02-alns-vns-8r-gpt55-20260614T024540Z-claw`
- `rep02/alns_only`:
  `/home/clawd/research/scion-experiments/v04-cvrp-baseline-strength-phaseB-matched-20260614T024206Z-claw/cells/v04-cvrp-phaseB-rep02-alns-only-8r-gpt55-20260614T024540Z-claw`
- `rep03/alns_vns`:
  `/home/clawd/research/scion-experiments/v04-cvrp-baseline-strength-phaseB-matched-20260614T024206Z-claw/cells/v04-cvrp-phaseB-rep03-alns-vns-8r-gpt55-20260614T024541Z-claw`
- `rep03/alns_only`:
  `/home/clawd/research/scion-experiments/v04-cvrp-baseline-strength-phaseB-matched-20260614T024206Z-claw/cells/v04-cvrp-phaseB-rep03-alns-only-8r-gpt55-20260614T024541Z-claw`

## Matched Controls

All cells were prepared with:

- `GIT_COMMIT=8311879`
- `SCION_MODEL=gpt-5.5`
- `SCION_BASE_URL=http://127.0.0.1:8080`
- `SCION_PROBLEM_DATA_ROOT=/home/clawd/research/or-autoresearch-agent/vrp`
- `ROUNDS=8`
- `TIME_LIMIT_SEC=30`
- `MEASUREMENT_GOVERNANCE=on`
- `PROPOSAL_CONTEXT_ABLATION=compact-measurement-diagnostics`
- `--disable-early-stop`
- `--agentic-proposal`
- `--agentic-session-timeout-sec 900`

All cells use Phase A calibration inputs:

- Protocol:
  `/home/clawd/research/scion-experiments/v04-cvrp-baseline-strength-phaseA-20260613T171611Z-claw/config/protocol.yaml`
- Split:
  `/home/clawd/research/scion-experiments/v04-cvrp-baseline-strength-phaseA-20260613T171611Z-claw/config/split_manifest.yaml`
- Seeds:
  `/home/clawd/research/scion-experiments/v04-cvrp-baseline-strength-phaseA-20260613T171611Z-claw/config/seed_ledger.yaml`

Baseline roots:

- ALNS+VNS:
  `/home/clawd/research/scion-experiments/v04-cvrp-baseline-strength-phaseA-20260613T171611Z-claw/baselines/alns_vns/problem.yaml`
- ALNS-only:
  `/home/clawd/research/scion-experiments/v04-cvrp-baseline-strength-phaseA-20260613T171611Z-claw/baselines/alns_only/problem.yaml`

Matched report-only control keys:

- `rep01`: `cvrp.baseline-strength.phaseB:rep01`
- `rep02`: `cvrp.baseline-strength.phaseB:rep02`
- `rep03`: `cvrp.baseline-strength.phaseB:rep03`

## Launch Validation

Before starting the sequential runner:

- `bash -n` passed for all 6 generated `run.sh` files.
- Each `launch.env` recorded the expected problem root, protocol, split, seed
  ledger, context arm, governance arm, control-pair key, and commit.
- No other Scion campaign process was running.
- The local `gpt-5.5` proxy at `http://127.0.0.1:8080` responded to `/v1/models`.

The first live command observed after launch was:

```bash
/home/clawd/miniconda3/envs/claw/bin/python -m scion.cli.main run \
  --problem /home/clawd/research/scion-experiments/v04-cvrp-baseline-strength-phaseA-20260613T171611Z-claw/baselines/alns_vns/problem.yaml \
  --protocol /home/clawd/research/scion-experiments/v04-cvrp-baseline-strength-phaseA-20260613T171611Z-claw/config/protocol.yaml \
  --split /home/clawd/research/scion-experiments/v04-cvrp-baseline-strength-phaseA-20260613T171611Z-claw/config/split_manifest.yaml \
  --seeds /home/clawd/research/scion-experiments/v04-cvrp-baseline-strength-phaseA-20260613T171611Z-claw/config/seed_ledger.yaml \
  --rounds 8 \
  --time-limit-sec 30 \
  --agentic-session-timeout-sec 900 \
  --measurement-governance on \
  --proposal-context-ablation compact-measurement-diagnostics \
  --disable-early-stop \
  --agentic-proposal
```

## Postrun Gate

Do not interpret Phase B until every completed cell has:

- wrapper and campaign status resolved;
- `scion report summary`;
- `scion report failures`;
- `scion report research-efficiency`;
- proposal trajectory manifests using the pre-registered `control_pair_key`;
- repeat-level proposal trajectory compares;
- branch-depth and same-mechanism follow-up SQL analysis.

Formal outcomes must be interpreted through the v3 Decision boundary only.
MDE, BKS gap, VNS activity, baseline strength, and trajectory comparison remain
postrun research-analysis facts.
