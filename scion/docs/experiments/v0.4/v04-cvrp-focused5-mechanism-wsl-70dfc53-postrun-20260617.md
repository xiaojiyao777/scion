# CVRP Focused Exact-Case Mechanism Matrix WSL Postrun

Date: 2026-06-17

## Run

Commit: `70dfc53` on `codex/v04-evidence-repair-plan`

WSL runner:
`/home/xjy-ubuntu/research/or-autoresearch-agent`

WSL tmux session:
`scion_cvrp_focused5_70dfc53_20260617T144526Z`

WSL output:
`/home/xjy-ubuntu/research/scion-experiments/cvrp-focused5-mechanism-70dfc53-20260617T144526Z`

Server-synced output:
`/home/clawd/research/scion-experiments/cvrp-focused5-mechanism-70dfc53-20260617T144526Z`

Command shape:

```bash
PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion \
/home/xjy-ubuntu/miniconda3/envs/scion/bin/python \
  scion/tools/cvrp_mechanism_matrix.py \
  --workspace scion/scion/problems/cvrp \
  --repo-root . \
  --data-root /home/xjy-ubuntu/research/or-autoresearch-agent/vrp \
  --case-manifest scion/scion/problems/cvrp/formal/manifests/screening.json \
  --output-dir /home/xjy-ubuntu/research/scion-experiments/cvrp-focused5-mechanism-70dfc53-20260617T144526Z \
  --case-id P-n76-k4 \
  --case-id P-n101-k4 \
  --case-id M-n151-k12 \
  --case-id CMT2 \
  --case-id CMT4 \
  --case-limit 5 \
  --seed 11 --seed 23 --seed 37 --seed 47 \
  --time-budget-sec 3 \
  --timeout-padding-sec 60
```

An earlier shakedown at
`/home/xjy-ubuntu/research/scion-experiments/cvrp-focused-mechanism-70dfc53-20260617T144341Z`
completed `12/12` rows for `P-n76-k4` only because the tool's conservative
default `--case-limit=1` was left in effect. It is not used as acceptance
evidence except to correct the documented command shape.

## Validity

This WSL run is complete and valid as a no-LLM diagnostic matrix:

- `60/60` jobs completed;
- `results.json`, `summary.csv`, and `60` raw solver JSON files are present;
- no solver subprocess failed;
- artifacts were rsynced back to the server-side experiment directory.

## Results

Overall candidate-vs-canonical deltas use total distance; negative is better
than canonical ALNS+VNS for the same case and seed.

| mechanism | W/L/T vs canonical | median delta | mean delta | route regressions | fleet positives |
| --- | ---: | ---: | ---: | ---: | ---: |
| `alns_only` | `4/15/1` | `7.0` | `24.8` | `0` | `0` |
| `size70_two_opt_candidate` | `4/15/1` | `7.0` | `26.0` | `0` | `0` |

By exact case:

| case | canonical median gap | `alns_only` W/L/T | `alns_only` median delta | `size70_two_opt_candidate` W/L/T | `size70_two_opt_candidate` median delta |
| --- | ---: | ---: | ---: | ---: | ---: |
| `P-n76-k4` | `7.93%` | `3/1/0` | `-4.0` | `3/1/0` | `-4.0` |
| `P-n101-k4` | `6.17%` | `1/3/0` | `7.0` | `1/3/0` | `7.0` |
| `CMT2` | `12.96%` | `0/4/0` | `104.0` | `0/4/0` | `105.5` |
| `CMT4` | `11.72%` | `0/3/1` | `1.0` | `0/3/1` | `1.0` |
| `M-n151-k12` | `13.30%` | `0/4/0` | `7.0` | `0/4/0` | `7.0` |

## Interpretation

The matrix rejects `alns_only` and `size70_two_opt_candidate` as broad
replacements for canonical ALNS+VNS on these focused cases. The high-gap
canonical cases do not become easier by removing VNS or using the size70/two-opt
probe; `CMT2` especially gets much worse.

The useful positive signal is narrower: `P-n76-k4` remains a local-win case for
both candidate mechanisms across `3/4` seeds, with median delta `-4.0`, no route
regression, and no fleet violation. `P-n101-k4` is not a replicated P-family
win under these seeds.

This points away from a broad LLM CVRP campaign and toward one of two narrower
diagnostics:

- run a deeper fixed-candidate/no-LLM seed matrix on `P-n76-k4` to decide
  whether the small median improvement clears the CVRP A/A noise floor;
- inspect phase telemetry on `P-n76-k4` win/loss seeds versus `CMT2` and
  `M-n151-k12` loss seeds to identify whether the actionable mechanism is VNS
  timing, best-update starvation, accepted-move starvation, or local-search
  mismatch.

No generic `DecisionFeatures`, Protocol threshold, or validation/frozen gate
change is supported by this matrix.
