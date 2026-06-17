# CVRP Adaptive Trigger Compact WSL Postrun

Date: 2026-06-17

## Verdict

Accepted as a no-LLM mechanism diagnostic and as a proposal-context opportunity
source. Not accepted as a production default and not promotion evidence.

`adaptive_embedded_vns_cadence2` is the best current trigger candidate: it
reduces embedded-VNS runtime pressure, increases ALNS iterations, keeps median
paired delta at `0.0`, and has no route/fleet regressions. Its mean paired
delta is still slightly worse (`+1.8`), so the correct next action is to expose
the opportunity to CVRP proposal context as a refinement target, not to change
the canonical solver default.

`adaptive_embedded_vns_improve_only` saves more embedded-VNS time but loses too
much quality. `adaptive_embedded_vns_cadence4` remains rejected as too blunt.

## Run

- Commit: `eddaf8c`
- WSL root:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-adaptive-trigger-compact-eddaf8c-20260617T170200Z`
- Server sync root:
  `/home/clawd/research/scion-experiments/v04-cvrp-adaptive-trigger-compact-eddaf8c-20260617T170200Z`
- Shape: no-LLM mechanism matrix, `80` jobs
- Cases: `P-n76-k4`, `CMT2`, `CMT4`, `M-n151-k12`
- Seeds: `1..5`
- Mechanisms:
  - `canonical_alns_vns`
  - `adaptive_embedded_vns_cadence4`
  - `adaptive_embedded_vns_cadence2`
  - `adaptive_embedded_vns_improve_only`
- Time budget: `3s`
- Wrapper status: `finished`
- Exit code: `0`
- Raw result files: `80`

Command shape:

```bash
PYTHONPATH=$PWD/scion /home/xjy-ubuntu/miniconda3/envs/scion/bin/python \
  scion/tools/cvrp_mechanism_matrix.py \
  --case-id P-n76-k4 --case-id CMT2 --case-id CMT4 --case-id M-n151-k12 \
  --case-limit 4 \
  --seed 1 --seed 2 --seed 3 --seed 4 --seed 5 \
  --mechanism canonical_alns_vns \
  --mechanism adaptive_embedded_vns_cadence4 \
  --mechanism adaptive_embedded_vns_cadence2 \
  --mechanism adaptive_embedded_vns_improve_only \
  --time-budget-sec 3 \
  --output-dir /home/xjy-ubuntu/research/scion-experiments/v04-cvrp-adaptive-trigger-compact-eddaf8c-20260617T170200Z
```

## Artifact Checks

- `status.txt`: `status=finished`, `exit_code=0`.
- `summary.csv`: `80` data rows plus header.
- Raw JSON files: `80`.
- `results.json`: `80/80` jobs completed with return code `0`.
- No route-count or fleet-regression flags were raised.

## Overall Results

Comparison versus canonical:

| Mechanism | Rows | W/L/T | Median delta | Mean delta | Mean ALNS iterations | Embedded VNS fraction |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `canonical_alns_vns` | 20 | reference | `0.0` | `0.0` | `4.0` | `0.653` |
| `adaptive_embedded_vns_cadence4` | 20 | `3/7/10` | `0.0` | `+11.4` | `8.35` | `0.363` |
| `adaptive_embedded_vns_cadence2` | 20 | `5/7/8` | `0.0` | `+1.8` | `6.0` | `0.528` |
| `adaptive_embedded_vns_improve_only` | 20 | `4/8/8` | `0.0` | `+9.25` | `14.7` | `0.183` |

Embedded-VNS fraction treats rows with no embedded-VNS run as `0`, matching
whole-matrix runtime-pressure interpretation.

## Case Results

| Case | Cadence-4 W/L/T, mean | Cadence-2 W/L/T, mean | Improve-only W/L/T, mean |
| --- | --- | --- | --- |
| `CMT2` | `1/3/1`, `+40.4` | `3/2/0`, `-3.2` | `2/3/0`, `+31.2` |
| `CMT4` | `0/2/3`, `+6.4` | `1/2/2`, `+1.8` | `0/2/3`, `+6.4` |
| `M-n151-k12` | `0/0/5`, `0.0` | `1/0/4`, `-0.8` | `1/0/4`, `-1.8` |
| `P-n76-k4` | `2/2/1`, `-1.2` | `0/3/2`, `+9.4` | `1/3/1`, `+1.2` |

Cadence-2 is the only variant that materially fixes the `CMT2` volatility seen
with cadence-4 while staying near-neutral overall. Its main warning is
`P-n76-k4`, where cadence-2 loses `0/3/2` with mean delta `+9.4`.

## Interpretation

This matrix converts the adaptive-VNS idea from a vague solver-tuning hunch into
a concrete research signal:

- broad embedded-VNS removal is still rejected;
- improve-only triggering is too sparse for quality despite large runtime
  savings;
- cadence-4 remains too aggressive;
- cadence-2 is near-neutral and reduces embedded-VNS pressure enough to be a
  useful refinement target.

Because CVRP formal A/A MDE is about `9.9` raw `total_distance`, cadence-2's
overall mean delta `+1.8` and median `0.0` are small relative to measured noise.
That does not make cadence-2 a default. It makes it suitable as problem-owned
proposal context for an agent to refine, especially around the observed
case-level split:

- preserve the `CMT2` gains from cadence-2;
- avoid the `P-n76-k4` losses;
- use objective/budget/best-update triggers rather than case-id rules.

## Next Step

Add a CVRP proposal-visible opportunity summary that describes the accepted
problem-owned facts above without leaking raw BKS shortcuts or adding CVRP
semantics to generic `DecisionFeatures`. Then run a short agentic CVRP campaign
whose task is to refine adaptive embedded-VNS scheduling from the cadence-2
candidate, not to blindly tune destroy ratios or remove VNS.
