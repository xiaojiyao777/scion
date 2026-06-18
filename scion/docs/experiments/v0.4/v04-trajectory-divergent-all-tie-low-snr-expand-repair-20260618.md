# Trajectory-Divergent All-Tie Low-SNR Expand Repair

Date: 2026-06-18
Branch: `codex/v04-evidence-repair-plan`

## Summary

The low-SNR screening policy for `pairing_validity=trajectory_divergent`
handled tie-heavy weak evidence, but pure all-tie screening fell through to
`SCREENING_FAIL_WIN_RATE`. For CVRP-style budget-exhausting solver work, an
all-tie result with zero median delta, non-negative CI, no candidate/runtime
failure, and no runtime veto is measurement-noise evidence, not mechanism
disproof.

This repair lets tie-dominant non-regressive evidence enter the existing
low-SNR expand/continue path even when there are no non-tie pairs. It does not
change stable-pairing behavior and does not admit loss-heavy, negative-delta,
candidate-failed, or runtime-vetoed candidates.

## Boundary Check

- Decision still reads only `DecisionFeatures`.
- The behavior is selected by deterministic problem-owned
  `pairing_validity=trajectory_divergent`.
- No raw calibration rows, BKS, free text, or proposal guidance enter
  `DecisionFeatures`.
- Protocol and Decision predicates remain aligned.

## Changed Files

- `scion/scion/protocol/gates.py`
- `scion/scion/core/decision.py`
- `scion/scion/tests/test_protocol_stats_gates.py`
- `scion/scion/tests/test_decision_screening.py`

## Verification

Local:

```bash
python -m py_compile scion/scion/protocol/gates.py scion/scion/core/decision.py
PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion pytest -q \
  scion/scion/tests/test_protocol_stats_gates.py \
  scion/scion/tests/test_decision_screening.py \
  scion/scion/tests/unit/core/test_branch_lifecycle_policy.py \
  scion/scion/tests/unit/core/test_scheduler_runtime_evidence_pressure.py \
  scion/scion/tests/unit/core/test_branch_step_runner_scheduler_metadata.py
```

Result: `164 passed`.

WSL:

```bash
PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion \
  /home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m pytest -q \
  scion/scion/tests/test_protocol_stats_gates.py \
  scion/scion/tests/test_decision_screening.py \
  scion/scion/tests/unit/core/test_branch_lifecycle_policy.py \
  scion/scion/tests/unit/core/test_scheduler_runtime_evidence_pressure.py \
  scion/scion/tests/unit/core/test_branch_step_runner_scheduler_metadata.py
```

Result: `164 passed`.

## Acceptance

Accepted as a narrow v0.4 measurement-semantics repair. It prevents pure
all-tie trajectory-divergent screening from becoming a false negative while
preserving fail-closed behavior for genuine negative or unsafe evidence.
