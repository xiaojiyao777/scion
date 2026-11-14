# CVRP VNS Variant Matrix WSL Postrun

Date: 2026-06-17

## Run

Commit: `6d742c6` on `codex/v04-evidence-repair-plan`

WSL runner:
`/home/xjy-ubuntu/research/or-autoresearch-agent`

WSL tmux session:
`scion_cvrp_vns_variants_6d742c6_20260617T150928Z`

WSL output:
`/home/xjy-ubuntu/research/scion-experiments/cvrp-vns-variants-6d742c6-20260617T150928Z`

Server-synced output:
`/home/clawd/research/scion-experiments/cvrp-vns-variants-6d742c6-20260617T150928Z`

## Validity

This WSL run is complete and valid as a no-LLM diagnostic matrix:

- `80/80` jobs completed;
- `results.json`, `summary.csv`, and `80` raw solver JSON files are present;
- no solver subprocess failed;
- artifacts were rsynced back to the server-side experiment directory;
- objective probes are present in result telemetry.

## Results

Candidate-vs-canonical deltas use total distance; negative is better than
canonical ALNS+VNS for the same case and seed.

Overall:

| mechanism | W/L/T vs canonical | median delta | mean delta |
| --- | ---: | ---: | ---: |
| `initial_vns_disabled` | `7/9/0` | `2.0` | `-7.62` |
| `embedded_vns_disabled` | `4/5/7` | `0.0` | `7.38` |
| `size70_two_opt_candidate` | `3/12/1` | `7.0` | `31.25` |
| `pure_alns_no_polish` | `3/13/0` | `8.0` | `29.19` |

By exact case:

| case | `initial_vns_disabled` W/L/T, median | `embedded_vns_disabled` W/L/T, median | `size70_two_opt_candidate` W/L/T, median | `pure_alns_no_polish` W/L/T, median |
| --- | ---: | ---: | ---: | ---: |
| `P-n76-k4` | `3/1/0`, `-8.0` | `2/2/0`, `6.5` | `3/1/0`, `-4.0` | `3/1/0`, `-3.5` |
| `CMT2` | `3/1/0`, `-54.5` | `1/3/0`, `30.0` | `0/4/0`, `104.0` | `0/4/0`, `110.5` |
| `CMT4` | `0/4/0`, `2.0` | `1/0/3`, `0.0` | `0/3/1`, `1.0` | `0/4/0`, `2.0` |
| `M-n151-k12` | `1/3/0`, `6.0` | `0/0/4`, `0.0` | `0/4/0`, `7.0` | `0/4/0`, `8.0` |

## Interpretation

The matrix again rejects broad removal of VNS and pure ALNS/no-polish. The
first useful mechanism clue is narrower:

- disabling only initial VNS is strongly positive on `CMT2` and positive on
  `P-n76-k4` under these seeds;
- disabling embedded VNS is neutral on `CMT4` and `M-n151-k12` but worse on
  `CMT2` and mixed on `P-n76-k4`;
- size70/two-opt fallback and pure ALNS remain poor on high-gap cases.

This points to a conditional initial-VNS scheduling issue, not a VNS deletion
or ALNS-only replacement. Under short budgets, initial VNS appears to consume
time before ALNS has enough opportunity on some cases, while embedded VNS still
matters for `CMT2` quality and canonical VNS behavior remains important on
`CMT4` / `M-n151-k12`.

The result is promising enough for one more no-LLM proof step, but not enough
for a CVRP LLM campaign or a solver-design change:

- run a deeper seed matrix comparing only canonical and
  `initial_vns_disabled` on `P-n76-k4`, `CMT2`, `CMT4`, and `M-n151-k12`;
- inspect objective probes to derive a case-general trigger, such as skipping
  initial VNS when construction is already route-feasible and the short budget
  would otherwise starve ALNS, rather than keying on case ids or families;
- only after that should an agentic CVRP campaign be given a conditional
  initial-VNS scheduling target.

No generic `DecisionFeatures`, Protocol threshold, or validation/frozen gate
change is supported by this matrix.
