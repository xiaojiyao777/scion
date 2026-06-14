# v0.4 CVRP Baseline-Strength Phase A

*Date: 2026-06-14*
*Branch: `codex/v04-evidence-repair-plan`*
*Run commit: `0a58e1115a8ceac3672d7dde75c82c46319896bf`*
*Status: accepted no-LLM characterization; Phase B requires explicit matched-campaign design*

## Summary

The no-LLM CVRP baseline-strength characterization completed with wrapper exit
status `0` for all three stages: ALNS+VNS A/A, ALNS-only A/A, and paired
baseline characterization.

The result supports treating baseline strength and research-surface headroom as
an explicit v0.4 experimental variable. Disabling VNS makes the A/A measurement
instrument less noisy (`MDE=4.65` versus `9.6` raw `total_distance`) and reduces
the recommended seed count from `16` to `8`. It does not make the current
screening protocol sensitive to the declared `practical_delta_screen=2.0`, and
it materially weakens raw solver quality. In direct paired comparison,
ALNS-only won only `7/64` pairs, lost `56/64`, tied `1/64`, and had median
signed delta `-20.0` raw `total_distance` versus the ALNS+VNS control.

This is not a solver-quality win and not a Scion core feature. ALNS-only is a
CVRP problem-owned copied snapshot used to characterize research-surface
headroom before any LLM campaign. The canonical ALNS+VNS baseline remains
unchanged, and no VNS, BKS, baseline-strength, or raw calibration diagnostic
enters `DecisionFeatures`.

## Run

Run root:

`/home/clawd/research/scion-experiments/v04-cvrp-baseline-strength-phaseA-20260613T171611Z-claw`

Full status:

- Started: `2026-06-13T19:46:11Z`
- Ended: `2026-06-14T02:24:47Z`
- Runtime policy: `protocol_time_limits`
- Cases: `8`
- Seeds: `8`
- A/A replicates: `3`
- Exit status: `aa_alns_vns=0`, `aa_alns_only=0`, `pair_characterization=0`

The first full attempt in the same run root failed on `M/M-n200-k17.vrp` with a
solver timeout before the runner timeout grace repair. The accepted rerun is
from commit `0a58e11`, which increased the solver wall-clock grace to `15s`.
The accepted A/A artifacts record `runner_timeout_sec=60` and
`runner_timeout_grace_sec=15`; `M-n200-k17` completed under the `45s`
protocol-resolved screening budget.

## Provenance

Source champion:

`/home/clawd/research/scion-experiments/v04-phase4-focused-cvrp-measreadiness-20260611-4r-gpt55-20260611T224916Z-claw/campaign/champions/champion_v1`

Control snapshot:

`/home/clawd/research/scion-experiments/v04-cvrp-baseline-strength-phaseA-20260613T171611Z-claw/baselines/alns_vns`

Contrast snapshot:

`/home/clawd/research/scion-experiments/v04-cvrp-baseline-strength-phaseA-20260613T171611Z-claw/baselines/alns_only`

Only intentional solver diff:

```diff
-USE_VNS = True
+USE_VNS = False
```

Manifest hashes:

- Control config SHA256:
  `7b6e0c78ae35c25b31e872e8eeaefc0edfbd812068f3bce8418081818ca0bc88`
- Contrast config SHA256:
  `f80f25b495ec1be106e34999e0d0be4bb74d121686e16298643b29bef5e876fc`
- Entrypoint SHA256 for both:
  `616412d1d9f65f810412c0c2bb52b81b3056bba73f0a9fb444152692047a0c6e`
- Baseline manifest SHA256:
  `594ddf6757545b5cfa27a08e198d4084e054b9478f28d9d56f4f6568a331702f`
- Phase A input manifest SHA256:
  `0d3751a915d0dc495bb72428516e8ed44d1ab76be0bdaa521af143916ba4047d`

Output artifact hashes:

- ALNS+VNS A/A:
  `0bf563688e71d5b5247ad2f1b1186dfe9d89be6c473c05313419f41c5a1e7e73`
- ALNS-only A/A:
  `002fc705f3f70e05bd71de0f76ea38a8ef6af170de791ad9fcd154d57ce8bc09`
- Paired characterization:
  `f17c7a3b71a5c9ccbc6047ded5296164cb6336a59b8393aa3e0e478ecc86563b`

The recorded repo status at launch contained only unrelated untracked files:

- `scion/docs/engineering/module-debt/agentic-runtime-refactor-plan-20260613.md`
- `scion/scion/tests/unit/test_agentic_runtime_refactor_guards.py`

## Selected Inputs

Selected cases:

- `cvrplib/A/A-n64-k9.vrp`
- `cvrplib/B/B-n63-k10.vrp`
- `cvrplib/E/E-n101-k14.vrp`
- `cvrplib/P/P-n65-k10.vrp`
- `cvrplib/CMT/CMT2.vrp`
- `cvrplib/CMT/CMT4.vrp`
- `cvrplib/M/M-n200-k17.vrp`
- `cvrplib/X/X-n110-k13.vrp`

Selected seeds:

`11, 29, 43, 59, 73, 79, 97, 103`

Runtime policy:

- Selected policy: `protocol_time_limits`
- Resolved unique solver budgets: `30s`, `45s`
- Runner timeout: `60s`
- Runner timeout grace: `15s`

`M-n200-k17` used `45s`. `CMT4` used `30s` under the current resolver, even
though the file dimension is `151`; exact CMT dimension fidelity remains a
known caveat unless repaired or explicitly pre-registered.

## A/A Results

| Baseline | Pairs | MDE raw distance | False-pass | Recommended seeds | Outcome W/L/T | Time limits |
| --- | ---: | ---: | ---: | ---: | --- | --- |
| ALNS+VNS | 192 | 9.6 | 0.0 | 16 | 75/86/31 | 168 at 30s, 24 at 45s |
| ALNS-only | 192 | 4.65 | 0.0 | 8 | 58/53/81 | 168 at 30s, 24 at 45s |

Both A/A artifacts record `decision_features_excluded=true`. They are
problem-owned measurement diagnostics, not promotion evidence.

Per-case A/A absolute delta summaries:

| Baseline | Case | P50 abs | P90 abs | Max abs | Tie rate |
| --- | --- | ---: | ---: | ---: | ---: |
| ALNS+VNS | `A-n64-k9` | 10.0 | 18.4 | 26.0 | 0.0833 |
| ALNS+VNS | `B-n63-k10` | 14.0 | 44.5 | 54.0 | 0.0833 |
| ALNS+VNS | `CMT2` | 17.0 | 30.4 | 41.0 | 0.0000 |
| ALNS+VNS | `CMT4` | 15.0 | 39.4 | 60.0 | 0.0000 |
| ALNS+VNS | `E-n101-k14` | 8.0 | 16.0 | 23.0 | 0.0417 |
| ALNS+VNS | `M-n200-k17` | 0.0 | 8.0 | 13.0 | 0.7500 |
| ALNS+VNS | `P-n65-k10` | 8.0 | 17.0 | 23.0 | 0.0000 |
| ALNS+VNS | `X-n110-k13` | 13.0 | 76.8 | 90.0 | 0.3333 |
| ALNS-only | `A-n64-k9` | 16.5 | 36.8 | 41.0 | 0.0000 |
| ALNS-only | `B-n63-k10` | 21.5 | 47.9 | 69.0 | 0.0000 |
| ALNS-only | `CMT2` | 21.0 | 70.0 | 103.0 | 0.0833 |
| ALNS-only | `CMT4` | 0.0 | 3.7 | 26.0 | 0.8333 |
| ALNS-only | `E-n101-k14` | 0.0 | 0.0 | 1.0 | 0.9167 |
| ALNS-only | `M-n200-k17` | 0.0 | 5.4 | 6.0 | 0.6667 |
| ALNS-only | `P-n65-k10` | 9.0 | 20.0 | 28.0 | 0.0000 |
| ALNS-only | `X-n110-k13` | 0.0 | 6.3 | 94.0 | 0.8750 |

Interpretation:

- ALNS-only has a lower aggregate MDE and lower seed recommendation.
- The lower MDE comes with many ties on several cases, especially `CMT4`,
  `E-n101-k14`, `M-n200-k17`, and `X-n110-k13`.
- ALNS-only remains above the declared `practical_delta_screen=2.0`.
- ALNS+VNS remains a low-power measurement setting for small solver-design
  effects.

## Paired Baseline Characterization

Paired comparison directly ran ALNS-only as contrast versus ALNS+VNS as
control on the same 8 cases and 8 seeds.

Summary:

- Pairs: `64`
- Valid pairs: `64`
- Failed pairs: `0`
- ALNS-only wins/losses/ties: `7/56/1`
- ALNS-only win rate: `0.109375`
- Median signed delta: `-20.0`
- Mean signed delta: `-65.25`
- Median runtime ratio, ALNS-only over ALNS+VNS: `0.9883`
- Mean total distance: `3033.203125` for ALNS-only versus `2967.953125`
  for ALNS+VNS
- Mean BKS gap: `6.50%` for ALNS-only versus `4.20%` for ALNS+VNS
- Runtime budget-hit count: `0` for ALNS-only versus `6` for ALNS+VNS
- VNS observed: `0/64` contrast pairs, `64/64` control pairs

Per-case paired result:

| Case | Pairs | Contrast W/L/T | Median signed delta | Mean signed delta | Median runtime ratio | Time limit | Control BKS gap | Contrast BKS gap |
| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `A-n64-k9` | 8 | 1/6/1 | -7.0 | -9.75 | 0.9920 | 30 | 3.50% | 4.19% |
| `B-n63-k10` | 8 | 2/6/0 | -17.0 | -25.25 | 0.9944 | 30 | 3.08% | 4.77% |
| `CMT2` | 8 | 2/6/0 | -45.0 | -33.75 | 0.9898 | 30 | 3.96% | 8.01% |
| `CMT4` | 8 | 0/8/0 | -53.0 | -58.125 | 0.9106 | 30 | 6.27% | 11.92% |
| `E-n101-k14` | 8 | 0/8/0 | -14.0 | -15.125 | 0.9891 | 30 | 5.22% | 6.64% |
| `M-n200-k17` | 8 | 0/8/0 | -19.0 | -19.0 | 0.8832 | 45 | 6.35% | 7.84% |
| `P-n65-k10` | 8 | 2/6/0 | -2.0 | -8.25 | 0.9945 | 30 | 1.67% | 2.71% |
| `X-n110-k13` | 8 | 0/8/0 | -336.0 | -352.75 | 0.9830 | 30 | 3.58% | 5.93% |

Interpretation:

- ALNS-only is slightly faster in median runtime ratio, but not enough to
  compensate for quality loss under the current objective.
- ALNS-only creates a noisier/easier research surface in the sense that its A/A
  MDE is smaller and its quality headroom against BKS is larger.
- The headroom is bought by weaker starting quality, especially on `CMT4` and
  `X-n110-k13`.
- A later matched Scion campaign may use ALNS-only as a research-surface
  ablation, but it must not claim a production CVRP solver improvement unless
  final evidence is interpreted against the stronger ALNS+VNS baseline.

## Boundary Check

The v3 boundary held for this no-LLM characterization:

- The canonical CVRP baseline was not mutated.
- The only solver change lived in a copied run-root snapshot.
- ALNS/VNS telemetry stayed in problem-owned report artifacts.
- A/A artifacts explicitly set `decision_features_excluded=true`.
- BKS/gap/headroom evidence is report and proposal-readiness evidence only.
- Decision, Protocol gates, scheduler state, lifecycle state, and promotion
  semantics were not changed by this run.

## Decision

Accepted as Phase A no-LLM characterization.

Phase B is allowed only as a pre-registered matched Scion campaign comparing two
starting research surfaces, not as a production-baseline replacement:

- ALNS+VNS arm: keep interpreting solver-design evidence against MDE `9.6` and
  recommended seed pressure `16`.
- ALNS-only arm: interpret evidence against MDE `4.65`, but state clearly that
  the starting solver is lower quality.
- Both arms must match model, rounds, protocol/split/seed inputs, prompt context
  mode, measurement governance, runtime policy, and postrun analysis.
- Primary interpretation should ask whether Scion can do deeper and more useful
  CVRP research when the research surface has more measurable headroom.

Do not treat a possible ALNS-only promotion as proof that Scion solved CVRP
under the current ALNS+VNS champion.
