# CVRP Successor24 Lookahead Insertion Repair Postrun - 2026-06-30

## Run Identity

- Run root:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-successor24-lookahead-insertion-repair-2r-gpt55-20260630T073830Z-claw`
- WSL runner repo:
  `/home/xjy-ubuntu/research/or-autoresearch-agent-v04dev-runner-20260629`
- Runner commit: `462d6e0a`
- Model route: `gpt-5.5` via `http://127.0.0.1:8080`
- Start/end: `2026-06-30T07:38:34Z` / `2026-06-30T08:34:15Z`
- Wrapper exit status: `0`
- Campaign stop reason: `max_rounds_exhausted`
- Postrun acceptance: ready for analysis

The first prepared root,
`/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-successor24-lookahead-insertion-repair-2r-gpt55-20260630T073154Z-claw`,
failed before campaign start because the runtime git guard found a dirty WSL
runner tree. It is launch hygiene evidence, not CVRP solver evidence.

## Validity

The active run is valid and complete:

- requested rounds: `2`;
- effective protocol rounds: `2`;
- screening protocol rows: `2`;
- validation/frozen rows: `0`;
- formal candidates: `2`;
- proposal quality blocks: `0`;
- verification failure consumed candidates: `0`;
- postrun readiness: `current_run_analysis_ready=true`,
  `delegation_ready=true`, `failed_required_checks=[]`;
- latest champion version: `1`;
- active branches after completion: none.

Proposal trajectory accounting is usable for postrun interpretation:

- `formal_candidate_count=2`;
- `formal_candidate_joined_session_count=2`;
- `formal_candidate_replayable_count=2`;
- proposal distributions: `lookahead_insertion_cost_repair=2`,
  `lookahead_insertion_cost_repair_v2=2`;
- all proposal sessions used `solver_design` and primary target
  `policies/baseline_modules/destroy_repair.py`;
- raw prompt, raw response, and patch bodies remained excluded from
  `DecisionFeatures`.

## Mechanisms

Round 1 targeted the intended prepared mechanism:

- branch: `17896b8e-6ce7-4ec5-9ff8-e894fdac9301`;
- mechanism: `lookahead_insertion_cost_repair`;
- file scope: `policies/baseline_modules/destroy_repair.py` plus minimal
  scheduler registration and telemetry;
- implementation: a bounded repair operator scored immediate insertion cost,
  sampled future insertion cost for remaining customers, and selected the
  lowest combined score.

The mechanism activated and runtime was observed in all 32 candidate pairs.
Its phase bucket recorded `weighted_sum_ms=71139.0` and `max_ms=7649.0`.

Round 2 targeted a same-family follow-up:

- branch: `fa3d8083-897d-4bbf-9c9d-93abed7b7b40`;
- mechanism: `lookahead_insertion_cost_repair_v2`;
- file scope: `policies/baseline_modules/destroy_repair.py` plus minimal
  scheduler registration;
- implementation: a paired lookahead repair that considered top customer,
  partner, and insertion-position choices.

The v2 mechanism activated and runtime was observed, but direct effect
telemetry was zero: `candidate_present=60`, `candidate_positive=0`,
`candidate_zero=60` for
`solver_algorithm_phase_improvement_counts.lookahead_insertion_cost_repair_v2`.
The patch recorded `record_move(..., delta=None, best_improved=0)`, so the
diagnostic is not a missing-activation failure; it is a direct-effect
attribution failure alongside negative objective evidence.

## Objective Evidence

The solver evidence is negative for v0.4 closeout:

- rows at or above MDE: `0`;
- positive rows: `0`;
- rows with CI high below MDE: `2`;
- max median delta: `-0.75`;
- max effect/MDE ratio: `-0.075758`;
- MDE at 80% power: `9.9`;
- interpretation: `all_available_ci_high_below_mde`.

Protocol rows:

| Row | Branch | Mechanism | Pairs | Median delta | CI | Decision | Interpretation |
|---|---|---|---:|---:|---|---|---|
| 1 | `17896b8e` | `lookahead_insertion_cost_repair` | 32 | `-0.75` | `[-5.5, 0.5]` | `abandon` | activation observed, below MDE |
| 2 | `fa3d8083` | `lookahead_insertion_cost_repair_v2` | 32 | `-2.0` | `[-12.0, 1.5]` | `abandon` | direct-effect zero, below MDE |

Case-level medians:

| Case | Row 1 | Row 2 |
|---|---:|---:|
| `A-n64-k9` | `-1.5` | `1.5` |
| `B-n63-k10` | `0.5` | `1.0` |
| `CMT2` | `8.5` | `-4.0` |
| `CMT4` | `-5.5` | `-15.5` |
| `E-n101-k14` | `0.5` | `7.5` |
| `M-n200-k17` | `0.0` | `0.0` |
| `P-n65-k10` | `-2.0` | `-12.0` |
| `X-n110-k13` | `-6.0` | `-6.0` |

CMT4, P, and X regressions are material caveats. Row 1 had a positive CMT2
median, but row 2 lost CMT2 and worsened CMT4/P/X, so there is no protected-case
basis for continuing this path as solver research.

## Interpretation

Successor24 is valid framework evidence and negative solver evidence.

It demonstrates that the repaired guidance can drive the campaign toward the
intended clean-fork target, keep proposals replayable, complete formal
screening, and surface mechanism-level telemetry. It does not support a solver
improvement claim because both rows are below MDE with CI highs below MDE, both
branches are abandoned, and the same-family v2 follow-up still produces no
direct effect telemetry.

Classification:

- `lookahead_insertion_cost_repair`: `activation-observed-below-MDE`;
- `lookahead_insertion_cost_repair_v2`: `direct-effect-zero-and-below-MDE`;
- overall successor24: `quality-regression/default-avoid` for unchanged
  destroy/repair insertion-cost lookahead repair.

## Next Action

Do not continue unchanged successor24-style insertion-cost lookahead repair.
Treat both `lookahead_insertion_cost_repair` and
`lookahead_insertion_cost_repair_v2` as reviewed/default-avoid evidence in the
CVRP problem-owned catalog.

The next CVRP solver slot should clean-fork away from repair-side
insertion-cost lookahead. A better successor25 focus is a construction-side
seed selector that can report direct same-run seed-baseline attribution before
ALNS/VNS blurs causality, for example
`cw_sweep_seed_baseline_selector` in the construction seed portfolio family.
Scheduler q work should remain limited to explicit telemetry-only q-audit
repair unless a materially different scheduler-policy causal path is designed.
