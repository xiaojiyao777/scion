# Scion v0.4 Phase 1 A/A Calibration

*Date: 2026-06-11*
*Status: in progress*
*Branch: `codex/v04-evidence-repair-plan`*
*Base commit at launch: `fab66da`*

This note records the Phase 1 measurement-power gate from `TASK.md`.
The goal is to test whether the current instruments can detect useful effects
before starting additional framework repair. These A/A artifacts are
problem-owned diagnostics only. They must not be treated as promotion evidence
and must not enter `DecisionFeatures`.

## Runs

| Problem | Action | Run root | Status |
|---|---|---|---|
| CVRP | `modify` | `/home/clawd/research/scion-experiments/v04-phase1-aa-cvrp-screening-modify-r3-tl30-saferoot-20260611T164539Z-claw` | failed, exit 1 |
| CVRP | `modify` | `/home/clawd/research/scion-experiments/v04-phase1-aa-cvrp-screening-modify-r3-tl60-saferoot-20260611T175414Z-claw` | running |
| Warehouse | `create_new` | `/home/clawd/research/scion-experiments/v04-phase1-aa-warehouse-screening-create-r3-defaultbudget-20260611T164426Z-claw` | finished, exit 0 |
| Warehouse | `modify` | `/home/clawd/research/scion-experiments/v04-phase1-aa-warehouse-screening-modify-r3-defaultbudget-20260611T164426Z-claw` | finished, exit 0 |

The warehouse runs completed with wrapper exit status 0:

- `create_new`: started `2026-06-11T16:44:26Z`, ended
  `2026-06-11T16:51:15Z`.
- `modify`: started `2026-06-11T16:44:26Z`, ended
  `2026-06-11T16:47:25Z`.

The first CVRP run started at `2026-06-11T16:45:39Z` and failed at
`2026-06-11T17:50:33Z` before producing an `aa_noise_floor.json`. The failure
was a timeout on `/home/clawd/research/or-autoresearch-agent/vrp/cvrplib/M/M-n200-k17.vrp`
with candidate seed `2000035` under uniform `--time-limit-sec 30`.

A corrected CVRP run started at `2026-06-11T17:54:50Z` with the same safe-root
split and `--time-limit-sec 60`. This is still a uniform-budget calibration
run, not a perfect reproduction of the formal per-case runtime time-limit rules.

## Expected Workload

The current calibration CLI runs champion vs champion with independent RNG
streams. Each A/A pair runs the champion once with the ledger seed and once
with `seed + seed_offset * (replicate + 1)`.

| Problem | Action | Cases | Seeds | Replicates | Pairs | Solver runs |
|---|---:|---:|---:|---:|---:|---:|
| CVRP | modify | 8 | 4 | 3 | 96 | 192 |
| Warehouse | create_new | 10 | 2 | 3 | 60 | 120 |
| Warehouse | modify | 6 | 2 | 3 | 36 | 72 |

The first CVRP launch used uniform `--time-limit-sec 30` and failed on
`M/M-n200-k17.vrp`. This confirms that the current calibration CLI cannot yet
be treated as a faithful formal screening runner for CVRP: the formal protocol
uses screening defaults of 30s plus 45s rules for dimensions 150-250 and 60s
rules above 250. The active corrected launch uses uniform 60s to produce a
complete first CVRP noise-floor artifact. The final report must label the CVRP
number as a uniform-60s calibration until Worker F adds per-case runtime-rule
support.

## Warehouse Results

### Create

Artifact:
`/home/clawd/research/scion-experiments/v04-phase1-aa-warehouse-screening-create-r3-defaultbudget-20260611T164426Z-claw/aa_noise_floor.json`

SHA-256:
`e15a8c69c2fd85ef7ae490971370abdca4b89a4b4e78e574d6d7c594e6e9506a`

Summary:

- `n_pairs`: 60
- `mde_at_power_80`: 1725.0 raw `total_cost`
- `false_pass_rate_at_current_gate`: 0.0
- `recommended_min_seeds`: 4
- Maximum per-case `delta_max_abs`: 15600.0
- Maximum per-case `delta_p90_abs`: 9900.0
- Average per-case tie rate: about 0.20

### Modify

Artifact:
`/home/clawd/research/scion-experiments/v04-phase1-aa-warehouse-screening-modify-r3-defaultbudget-20260611T164426Z-claw/aa_noise_floor.json`

SHA-256:
`5e34c863356bc74a9d2254dbde1d0a0945c88d56ca7201a4e033344b9718146f`

Summary:

- `n_pairs`: 36
- `mde_at_power_80`: 577.5 raw `total_cost`
- `false_pass_rate_at_current_gate`: 0.0
- `recommended_min_seeds`: 4
- Maximum per-case `delta_max_abs`: 9100.0
- Maximum per-case `delta_p90_abs`: 8500.0
- Average per-case tie rate: about 0.42

## Interpretation So Far

The warehouse protocol's current gate does not show an A/A false-pass problem
in these two screening calibrations. However, the measured MDE values are much
larger than the current warehouse `practical_delta_screen: 0.001` raw
`total_cost` declaration. That means practical delta is not yet calibrated to
the problem's actual effect/noise scale, even on the healthy warehouse control.

This does not contradict the Phase 0 warehouse promotion. It says the promotion
should be interpreted against a measured raw-cost noise floor rather than an
effectively dead practical-delta value.

CVRP remains the gating item for Phase 1 completion.

## CVRP Results

The `tl30` CVRP run produced no calibration JSON and must not be interpreted as
an MDE estimate. Its value is diagnostic: it shows that the A/A tool must either
consume protocol runtime time-limit rules or expose a sufficiently conservative
calibration budget. The `tl60` CVRP run is the active run for the first complete
CVRP MDE estimate.

## Tooling Gaps Found During Phase 1

- The first CVRP launch failed before solver execution because the formal CVRP
  split uses paths such as `cvrplib/A/A-n64-k9.vrp` while
  `formal/split_manifest.yaml` does not include `safe_data_roots`.
- The campaign path can resolve those cases through the CVRP problem data root,
  but `tools/calibrate_aa_noise.py` currently passes only
  `split.safe_data_roots` into `resolve_case_path_details`.
- The active CVRP run uses a local copied split with:
  `/home/clawd/research/or-autoresearch-agent/vrp` added as a safe data root.
  That split copy has SHA-256
  `395a05d172d44c27e462f5030ff22b88730b4c1df21af368f8e0315aaee660d1`.
- The first safe-root CVRP run still failed because uniform 30s was below the
  formal screening runtime rule needed by `M/M-n200-k17.vrp`. The corrected
  `tl60` run uses the same split hash and should be treated as a conservative
  calibration workaround until the CLI supports protocol runtime rules.
- The A/A payload records MDE, false pass rate, and per-case summaries, but it
  does not persist raw pair rows, candidate seeds, elapsed runtime, budget-hit
  or saturation details, selected cases/seeds, replicate count, seed offset, or
  case-resolution evidence.

These gaps should become Phase 2 repair items after the full A/A calibration
gate is complete. They are tooling/diagnostic limitations, not Decision-layer
inputs.
