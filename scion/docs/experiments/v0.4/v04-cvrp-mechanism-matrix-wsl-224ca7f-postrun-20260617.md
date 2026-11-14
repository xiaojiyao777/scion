# CVRP Mechanism Matrix WSL Postrun

Date: 2026-06-17
Commit: `224ca7f`
Branch: `codex/v04-evidence-repair-plan`

## Run

WSL root:
`/home/xjy-ubuntu/research/scion-experiments/cvrp-mechanism-matrix-224ca7f-20260617T140531Z`

Server sync root:
`/home/clawd/research/scion-experiments/cvrp-mechanism-matrix-224ca7f-20260617T140531Z-wsl`

Command shape:

```bash
/home/xjy-ubuntu/miniconda3/envs/scion/bin/python \
  scion/tools/cvrp_mechanism_matrix.py \
  --workspace scion/scion/problems/cvrp \
  --repo-root . \
  --data-root /home/xjy-ubuntu/research/or-autoresearch-agent/vrp \
  --case-manifest scion/scion/problems/cvrp/formal/manifests/screening.json \
  --output-dir /home/xjy-ubuntu/research/scion-experiments/cvrp-mechanism-matrix-224ca7f-20260617T140531Z \
  --case-limit 16 \
  --seed 11 \
  --seed 23 \
  --time-budget-sec 3 \
  --timeout-padding-sec 30
```

The WSL runner was fast-forwarded by git to `224ca7f` before launch. The run
completed with `exit_code=0`, `96/96` raw solver JSON files, `results.json`,
and `summary.csv`.

## Matrix Shape

- Cases: all 16 CVRP formal screening manifest entries.
- Seeds: `11`, `23`.
- Mechanisms:
  - `canonical_alns_vns`
  - `alns_only`
  - `size70_two_opt_candidate`
- Time budget: `3s` per solver job.

This is a no-LLM diagnostic matrix. It is not Protocol promotion evidence and
does not write any generic `DecisionFeatures`.

## Result Summary

All `96` result rows completed.

| Mechanism | Rows | Mean BKS gap | Median BKS gap | Mean accepted moves | Mean best updates |
| --- | ---: | ---: | ---: | ---: | ---: |
| `canonical_alns_vns` | `32` | `6.688%` | `6.281%` | `34.0` | `0.8` |
| `alns_only` | `32` | `8.655%` | `7.000%` | `26.0` | `2.9` |
| `size70_two_opt_candidate` | `32` | `8.644%` | `6.751%` | `35.4` | `2.9` |

Delta versus canonical ALNS+VNS:

| Mechanism | W/T/L | Median delta | Mean delta | Best delta | Worst delta |
| --- | ---: | ---: | ---: | ---: | ---: |
| `alns_only` | `4/0/28` | `12.0` | `39.531` | `-24.0` | `327.0` |
| `size70_two_opt_candidate` | `4/0/28` | `12.0` | `39.969` | `-24.0` | `327.0` |

Local wins were narrow and concentrated:

- `alns_only`: wins on `P-n76-k4` seed `23`, `B-n63-k10` seed `23`,
  `P-n101-k4` seed `11`, and `P-n76-k4` seed `11`.
- `size70_two_opt_candidate`: wins on `P-n76-k4` seed `23`,
  `P-n101-k4` seed `11`, `P-n76-k4` seed `11`, and `P-n65-k10` seed `11`.

Largest canonical gaps in this short-budget matrix:

- `M-n151-k12`: mean `13.300%`
- `CMT2`: mean `13.258%`
- `CMT4`: mean `11.725%`
- `P-n76-k4`: mean `8.179%`
- `E-n101-k8`: mean `8.037%`

## Interpretation

The matrix confirms that the tool and WSL execution path are usable, and that
the overlays are behaviorally active. It does not support replacing canonical
ALNS+VNS with ALNS-only or size70/two-opt: both candidate mechanisms are worse
on average and lose `28/32` paired comparisons against canonical.

The useful research signal is narrower:

- `P` family has local candidate wins and should be a first target for
  mechanism-specific follow-up.
- High-gap canonical cases such as `M-n151-k12`, `CMT2`, `CMT4`, and `P-n76-k4`
  expose headroom, but ALNS-only/two-opt alone is not the right broad fix.
- A longer LLM campaign should not be launched from this matrix alone. The
  next CVRP step should be a focused no-LLM or fixed-candidate diagnostic on
  selected family/slice targets, then a short agent campaign only after the
  target mechanism and measurable objective are explicit.
