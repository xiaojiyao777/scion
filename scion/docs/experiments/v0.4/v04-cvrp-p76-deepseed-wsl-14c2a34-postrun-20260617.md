# CVRP P-n76 Deep-Seed Mechanism Matrix WSL Postrun

Date: 2026-06-17

## Run

Commit: `14c2a34` on `codex/v04-evidence-repair-plan`

WSL runner:
`/home/xjy-ubuntu/research/or-autoresearch-agent`

WSL tmux session:
`scion_cvrp_p76_deep_14c2a34_20260617T145519Z`

WSL output:
`/home/xjy-ubuntu/research/scion-experiments/cvrp-p76-deep-mechanism-14c2a34-20260617T145519Z`

Server-synced output:
`/home/clawd/research/scion-experiments/cvrp-p76-deep-mechanism-14c2a34-20260617T145519Z`

Command shape:

```bash
PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion \
/home/xjy-ubuntu/miniconda3/envs/scion/bin/python \
  scion/tools/cvrp_mechanism_matrix.py \
  --workspace scion/scion/problems/cvrp \
  --repo-root . \
  --data-root /home/xjy-ubuntu/research/or-autoresearch-agent/vrp \
  --case-manifest scion/scion/problems/cvrp/formal/manifests/screening.json \
  --output-dir /home/xjy-ubuntu/research/scion-experiments/cvrp-p76-deep-mechanism-14c2a34-20260617T145519Z \
  --case-id P-n76-k4 \
  --case-limit 1 \
  --seed 1 --seed 2 --seed 3 --seed 4 --seed 5 \
  --seed 6 --seed 7 --seed 8 --seed 9 --seed 10 \
  --seed 11 --seed 12 --seed 13 --seed 14 --seed 15 \
  --seed 16 --seed 17 --seed 18 --seed 19 --seed 20 \
  --time-budget-sec 3 \
  --timeout-padding-sec 60
```

## Validity

This WSL run is complete and valid as a no-LLM diagnostic:

- `60/60` jobs completed;
- `results.json`, `summary.csv`, and `60` raw solver JSON files are present;
- no solver subprocess failed;
- artifacts were rsynced back to the server-side experiment directory.

## Results

The earlier focused 5-case matrix showed `P-n76-k4` candidate wins on `3/4`
seeds. This deeper seed check rejects that as a stable local improvement.

Candidate-vs-canonical deltas use total distance; negative is better than
canonical ALNS+VNS for the same seed.

| mechanism | W/L/T vs canonical | median delta | mean delta |
| --- | ---: | ---: | ---: |
| `alns_only` | `6/14/0` | `8.0` | `7.05` |
| `size70_two_opt_candidate` | `6/14/0` | `8.0` | `7.05` |

Observed deltas for both candidates were identical:

`[2, 4, 26, 10, 6, 3, 10, 24, 22, -8, -2, -4, -7, 10, 14, -4, 21, -32, 22, 24]`

Canonical total-distance median was `636.0`, with range `622.0..650.0`.

## Interpretation

`P-n76-k4` is not a reliable enough win pocket to justify an agentic CVRP
campaign or a solver-design change. The `3/4` seed result from the focused
matrix was a seed pocket; at `20` seeds the same candidate mechanisms are worse
than canonical by median `8.0`.

The phase telemetry from the focused matrix still contains a useful diagnostic
hypothesis: canonical often spends most of the short `3s` budget in VNS and
runs fewer ALNS iterations, while the candidate mechanisms run more ALNS with a
cheap size70/two-opt polish. But this timing difference does not yet translate
into a stable objective improvement.

The next CVRP step should therefore be diagnostic instrumentation and variant
separation, not a research campaign:

- separate initial-VNS from embedded-VNS effects;
- separate pure ALNS from the current no-VNS plus size70/two-opt fallback;
- record initial objective before/after VNS and VNS before/after objective
  changes so VNS improvements can be tied to final global-best progress;
- run the variant matrix on `P-n76-k4`, `CMT2`, `CMT4`, and `M-n151-k12`
  before launching any CVRP LLM campaign.

No generic `DecisionFeatures`, Protocol threshold, or validation/frozen gate
change is supported by this run.
