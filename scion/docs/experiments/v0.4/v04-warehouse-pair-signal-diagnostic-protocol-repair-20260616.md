# Warehouse Pair-Signal Diagnostic Protocol Repair - 2026-06-16

## Verdict

Accepted as a deterministic measurement/protocol repair, not yet as warehouse
efficacy evidence.

The preceding `d666311` rerun removed framework blockers but still failed
research-quality acceptance: all six formal candidates remained screening-only.
Its deepest branch had a warehouse production shape that should be diagnosable
rather than silently flattened by case-level ties: case W/L/T `2/0/4`, pair
W/L/T `6/2/4`, median `0.0`, and CI crossing zero.

This repair lets that specific class of pair-positive, non-regressive
low-SNR warehouse production signal enter diagnostic validation after screening
expand is exhausted. It does not loosen validation, frozen, promotion, runtime,
or `DecisionFeatures` boundaries.

## Changes

- `scion/problems/warehouse_delivery/problem-v1.yaml` and package mirror:
  `measurement.pairing_validity` is now `trajectory_divergent`.
- `scion/problems/warehouse_delivery/protocol_prod.yaml`:
  `expanded_borderline_advance.allow_pair_level_signal=true` with conservative
  thresholds:
  - `pair_win_rate_min=0.50`
  - `min_pair_total=12`
  - `min_pair_wins=6`
  - `min_pair_win_loss_margin=4`
  - `pair_non_tie_win_rate_min=0.70`
  - `max_pair_loss_rate=0.25`
- `scion/scion/core/decision.py`:
  expanded-exhausted negative median evidence now reaches the existing
  fail-closed negative-delta reason path instead of being reported only as a
  generic win-rate failure.
- Focused tests cover config loading, problem bridge measurement parity, and
  deterministic decision behavior for the `2/0/4` case-level and `6/2/4`
  pair-level warehouse shape.

## Boundary

This is a problem-owned measurement/protocol declaration repair. It keeps the
v3 boundary intact:

- no raw prompt, LLM output, branch lessons, or audit text enters
  `DecisionFeatures`;
- diagnostic validation only queues more evidence;
- frozen and promotion gates remain strict;
- negative median and loss-heavy pair evidence fail closed.

## Verification

Main-session acceptance reran:

```bash
PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion \
pytest -q \
  scion/scion/tests/test_config.py \
  scion/scion/tests/test_problem_bridge.py \
  scion/scion/tests/test_decision_screening.py \
  scion/scion/tests/test_protocol_stats_gates.py
```

Result: `97 passed`.

The main session also replayed the deterministic decision shape from the
`d666311` warehouse rerun:

- `pairing_validity=trajectory_divergent`
- case W/L/T `2/0/4`
- pair W/L/T `6/2/4`
- `median_delta=0.0`
- `ci_low=-1.0`
- `screening_expand_count=1`

Outcome:

- `Decision.QUEUE_VALIDATE`
- `SCREENING_EXPAND_EXHAUSTED_PAIR_SIGNAL_POLICY_PASS`
- `SCREENING_PAIR_LEVEL_SIGNAL_DIAGNOSTIC_VALIDATE`

## Residual Risk

This does not prove that warehouse research quality is restored. It only fixes
one identified measurement/protocol sink where pair-positive low-SNR evidence
could not enter diagnostic validation. The next required step is a short
warehouse production rerun from this repair commit and a branch-level postrun
checking whether pair-positive branches reach validation and whether validation
rejects or confirms them.
