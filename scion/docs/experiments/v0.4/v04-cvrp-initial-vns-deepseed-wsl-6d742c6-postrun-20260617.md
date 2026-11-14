# CVRP Initial-VNS Deep-Seed Matrix WSL Postrun

Date: 2026-06-17

## Run

Commit: `6d742c6` on `codex/v04-evidence-repair-plan`

WSL runner:
`/home/xjy-ubuntu/research/or-autoresearch-agent`

WSL tmux session:
`scion_cvrp_initvns_deep_6d742c6_20260617T151531Z`

WSL output:
`/home/xjy-ubuntu/research/scion-experiments/cvrp-initial-vns-deep-6d742c6-20260617T151531Z`

Server-synced output:
`/home/clawd/research/scion-experiments/cvrp-initial-vns-deep-6d742c6-20260617T151531Z`

## Validity

This WSL run is complete and valid as a no-LLM diagnostic matrix:

- `160/160` jobs completed;
- `results.json`, `summary.csv`, and `160` raw solver JSON files are present;
- no solver subprocess failed;
- artifacts were rsynced back to the server-side experiment directory;
- objective probes are present, with probe counts ranging from `3` to `23`.

## Results

Candidate-vs-canonical deltas use total distance; negative is better than
canonical ALNS+VNS for the same case and seed.

Overall `initial_vns_disabled`: W/L/T `25/51/4`, median delta `+2.0`, mean
delta `+3.35`.

By exact case:

| case | W/L/T vs canonical | median delta | mean delta | min..max delta |
| --- | ---: | ---: | ---: | ---: |
| `P-n76-k4` | `9/8/3` | `0.0` | `-1.65` | `-33..23` |
| `CMT2` | `8/12/0` | `3.5` | `10.05` | `-61..111` |
| `CMT4` | `3/16/1` | `2.0` | `0.75` | `-30..17` |
| `M-n151-k12` | `5/15/0` | `8.0` | `4.25` | `-27..33` |

The earlier `4`-seed variant matrix overestimated the signal. With `20` seeds,
disabling initial VNS is not stable enough to accept as a CVRP mechanism or to
seed an agentic solver-design campaign.

## Objective-Probe Notes

Initial VNS objective improvement is deterministic within each case in this
matrix:

| case | canonical initial VNS gain |
| --- | ---: |
| `P-n76-k4` | `16.0` |
| `CMT2` | `642.0` |
| `CMT4` | `2.0` |
| `M-n151-k12` | `8.0` |

Within-case win/loss differences therefore come mainly from later ALNS random
paths, not from variation in the initial-VNS gain itself. For example,
`P-n76-k4` skip wins had median skip best-update count `3`, while skip losses
had median `2`; `CMT2` wins/losses both had the same initial-VNS gain `642`.

This makes a simple initial-VNS disable trigger too weak. A useful future CVRP
research target would need a richer condition, such as measuring early ALNS
starvation or budget pressure directly, not keying on case id, family, or the
static initial VNS improvement.

## Interpretation

The v0.4 CVRP evidence now supports the following conservative conclusion:

- broad VNS removal is rejected;
- pure ALNS/no-polish is rejected;
- current size70/two-opt fallback is rejected as a broad replacement;
- disabling initial VNS is also rejected as a stable standalone mechanism;
- VNS timing remains an important diagnosis, but it needs a more precise,
  instrumented scheduling hypothesis before any LLM campaign.

No generic `DecisionFeatures`, Protocol threshold, or validation/frozen gate
change is supported by this run.
