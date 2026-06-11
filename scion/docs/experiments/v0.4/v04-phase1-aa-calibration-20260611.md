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
| CVRP | `modify` | `/home/clawd/research/scion-experiments/v04-phase1-aa-cvrp-screening-modify-r3-protocoltime-20260611T191356Z-claw` | prepared, not launched |
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
At `2026-06-11T20:06:50Z`, this run was still active with no
`aa_noise_floor.json` yet; the live solver had reached
`M/M-n200-k17.vrp`, confirming continued progress rather than a launch-time
stall.

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

## Phase 1 Acceptance Checklist

Phase 1 can close only when the final report can support these checks:

- CVRP `modify`, warehouse `create_new`, and warehouse `modify` all have a
  usable calibration conclusion, or a failed run is classified as a
  tooling/runtime diagnostic rather than an MDE estimate.
- Each run records run root, wrapper exit status, start/end time, launch
  command, branch/commit, champion version, copied problem/protocol/split/seed
  artifacts, and relevant hashes.
- Each successful artifact reports `n_pairs`, `protocol_power.mde_at_power_80`,
  `protocol_power.false_pass_rate_at_current_gate`,
  `protocol_power.recommended_min_seeds`, per-case delta quantiles, tie rate,
  false-win/loss rates, and practical-delta detectability.
- CVRP records selected cases/seeds, replicates, seed offset, independent RNG
  stream rule, case path resolution, and whether runtime used formal per-case
  policy or a conservative uniform cap.
- Runtime interpretation records timeout/failure evidence where present. Until
  Worker F extends the payload, elapsed runtime, budget-hit/saturation, raw
  pair rows, candidate seeds, and case-resolution details remain known caveats.
- The conclusion compares measured MDE against expected mechanism effects and
  against `practical_delta_screen` / `practical_delta_validate`.

If the active CVRP uniform-60s run succeeds, it is acceptable as the first CVRP
MDE estimate but not as a faithful formal screening reproduction. If it fails,
or if its payload is insufficient for the checks above, Worker F becomes a
Phase 1 prerequisite repair: calibration must learn declared data roots,
per-case runtime rules, and replayable pair/runtime evidence before Phase 1 can
be closed.

## Phase 1 Prerequisite Tooling Repair

Worker F implemented the calibration evidence-closure repair while the active
CVRP uniform-60s run was already running. The repair keeps calibration evidence
problem-owned and explicitly excluded from `DecisionFeatures`.

New capability:

- `aa_noise_floor.json` now records replayable `pair_evidence` with case,
  resolved case path, case resolution, ledger seed, candidate seed, replicate,
  outcome, delta/raw delta, candidate/champion values, elapsed runtime, and
  pair time limit.
- The top-level payload and `calibration_run` record selected cases/seeds,
  replicate count, seed offset, bootstrap samples, selected surface,
  runtime-policy metadata, safe data roots, and
  `decision_features_excluded=true`.
- `tools/calibrate_aa_noise.py` now wires declared problem data roots through
  the existing data-root helpers instead of requiring a hand-edited split.
- The CLI supports `--runtime-policy uniform_time_limit` for compatibility and
  `--runtime-policy protocol_time_limits` to resolve per-case protocol budgets.

Verification:

- `PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion pytest scion/scion/tests/unit/test_aa_calibration.py`
- `cd scion && python -m py_compile tools/calibrate_aa_noise.py scion/measurement/aa_calibration.py`
- `cd scion && python tools/calibrate_aa_noise.py --help`
- `cd scion && python tools/calibrate_aa_noise.py ... --max-cases 1 --max-seeds 1 --replicates 1 --time-limit-sec 5 --runtime-policy protocol_time_limits`
- `cd scion && unset SCION_PROBLEM_DATA_ROOT && python tools/calibrate_aa_noise.py ... formal ... --replicates 0 --runtime-policy protocol_time_limits`
- `PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion pytest scion/scion/tests/unit/test_cli_data_roots.py scion/scion/tests/test_cvrp_formal_readiness.py`
- `PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion pytest scion/scion/tests/test_protocol_split_runtime.py`

Important caveat: the active CVRP uniform-60s run was launched before this
repair and will not retroactively gain the new schema or protocol-time-limit
behavior. If that run succeeds, it remains a legacy uniform-60s first estimate.
The next formal CVRP calibration should use the repaired CLI with
`--runtime-policy protocol_time_limits`.

A repaired formal protocol-time run directory has been prepared but not
launched:

`/home/clawd/research/scion-experiments/v04-phase1-aa-cvrp-screening-modify-r3-protocoltime-20260611T191356Z-claw`

It uses commit `ba19e4fae57e4ccc3b7b2c70cf94d90a53c5d6f4`, the formal CVRP
split and seed ledger, declared data-root wiring through `formal/budgets.json`,
and `--runtime-policy protocol_time_limits`. Launch it after the legacy
uniform-60s run exits to avoid resource contention contaminating runtime
evidence.

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
- The A/A payload records MDE, false pass rate, and per-case summaries under
  `protocol_power` / `per_case`, but it does not persist raw pair rows,
  candidate seeds, elapsed runtime, budget-hit or saturation details, selected
  cases/seeds, replicate count, seed offset, or case-resolution evidence.

If CVRP cannot produce a usable calibration conclusion because of these gaps,
they become Phase 1 prerequisite repairs rather than Phase 2 framework repairs.
They are tooling/diagnostic limitations, not Decision-layer inputs.
