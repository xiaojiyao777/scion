# CVRP Size70 Tier 1 Large-X Launch - 2026-06-15

## Purpose

Launch the first pre-registered no-LLM replay tier for the size70 two-opt
candidate: Large-X completion diagnostic. This tier fills the missing `m=2`
budget multiplier and accounts all `36` large-X keys before formal validation.

This is not a Scion campaign, not LLM evidence, and not promotion evidence. It
is problem-owned mechanism-validity evidence for the human-approved size70
candidate. Runtime, BKS gap, timeout, activation, and best-update diagnostics
remain postrun/proposal material and must not enter `DecisionFeatures`.

## Inputs

- Source design:
  `scion/docs/planning/v0.4/v04-cvrp-size70-fixed-candidate-validation-design-20260615.md`
- Candidate prep report:
  `scion/docs/experiments/v0.4/v04-cvrp-size70-fixed-replay-prep-20260615.md`
- WSL repo:
  `/home/xjy-ubuntu/research/or-autoresearch-agent`
- WSL commit:
  `2548560`
- Candidate workspace:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-twoopt-polish-followup-smoke-20260615T1848Z/workspaces/candidate_twoopt_size70`
- Data root:
  `/home/xjy-ubuntu/research/or-autoresearch-agent/vrp`

## Run

- WSL run root:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-size70-tier1-largeX-20260615T211545Z`
- Server sync root:
  `/home/clawd/research/scion-experiments/v04-cvrp-size70-tier1-largeX-20260615T211545Z`
- Tmux session:
  `scion_cvrp_size70_tier1_211545`
- Started:
  `2026-06-15T21:17:11Z`
- Wrapper:
  `timeout 16h`
- Tool:
  `scion/tools/cvrp_runtime_curve.py`
- No LLM / no APS:
  yes
- Parallelism:
  `4`

Dry-run matrix completed first at the same WSL root:

- Planned jobs:
  `36`
- Statuses:
  `planned`
- First key:
  `X-n401-k29 seed=61 m=1 tl=90`
- Last key:
  `X-n1001-k43 seed=89 m=4 tl=480`

## Matrix

- Cases:
  - `cvrplib/X/X-n401-k29.vrp=90`
  - `cvrplib/X/X-n573-k30.vrp=120`
  - `cvrplib/X/X-n641-k35.vrp=120`
  - `cvrplib/X/X-n1001-k43.vrp=120`
- Seeds:
  `61`, `67`, `89`
- Multipliers:
  `1`, `2`, `4`
- Candidate keys:
  `4 cases x 3 seeds x 3 multipliers = 36`

## Command

```bash
timeout 16h /home/xjy-ubuntu/miniconda3/envs/scion/bin/python \
  /home/xjy-ubuntu/research/or-autoresearch-agent/scion/tools/cvrp_runtime_curve.py \
  --repo-root /home/xjy-ubuntu/research/or-autoresearch-agent \
  --workspace /home/xjy-ubuntu/research/scion-experiments/v04-cvrp-twoopt-polish-followup-smoke-20260615T1848Z/workspaces/candidate_twoopt_size70 \
  --data-root /home/xjy-ubuntu/research/or-autoresearch-agent/vrp \
  --python /home/xjy-ubuntu/miniconda3/envs/scion/bin/python \
  --selected-surface solver_design \
  --parallelism 4 \
  --timeout-padding-sec 900 \
  --resume \
  --case-budget cvrplib/X/X-n401-k29.vrp=90 \
  --case-budget cvrplib/X/X-n573-k30.vrp=120 \
  --case-budget cvrplib/X/X-n641-k35.vrp=120 \
  --case-budget cvrplib/X/X-n1001-k43.vrp=120 \
  --seed 61 --seed 67 --seed 89 \
  --multiplier 1 --multiplier 2 --multiplier 4 \
  --output-dir /home/xjy-ubuntu/research/scion-experiments/v04-cvrp-size70-tier1-largeX-20260615T211545Z/results/candidate_size70_largeX_full
```

## Acceptance

Postrun must check:

- all `36` planned keys accounted;
- completed versus timeout/failed/resumed counts;
- no candidate-only systematic timeout;
- feasible/recomputable output where completed;
- BKS gap and total-distance behavior versus the existing ALNS-only champion
  large-X curve;
- eligible rows show size70 two-opt activation or a clear reason activation did
  not occur;
- `m=2` closes the previous key-set ambiguity before formal validation.

If Tier 1 fails on completeness or broad large-X regression, do not launch
formal validation. If Tier 1 passes, launch the fixed-candidate validation
manifest prepared at:

`/home/clawd/research/scion-experiments/v04-cvrp-twoopt-polish-followup-smoke-20260615T1848Z/fixed_replay/validation_manifest.v1.json`
