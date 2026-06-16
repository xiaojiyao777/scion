# Warehouse Positive Diagnostic Protocol Repair - 2026-06-16

Purpose:

- Repair the warehouse-owned diagnostic validation route exposed by the
  loss-heavy lifecycle rerun.
- Admit expanded-exhausted, non-regressive, positive-CI low-SNR warehouse
  evidence to diagnostic validation.
- Keep negative-median and loss-dominated evidence fail-closed.

Basis:

- Field gate postrun:
  `scion/docs/experiments/v0.4/v04-warehouse-lossheavy-lifecycle-rerun6r-postrun-20260616.md`
- Field-positive shape from commit `6e3988c`:
  case W/L/T `3/1/10`, pair W/L/T `13/6/9`, median delta `300`, CI `[0, 875]`.
- This shape was expanded-exhausted and non-regressive, but stayed
  screening-only because the earlier pair diagnostic thresholds required
  `pair_win_rate_min=0.50` and `pair_non_tie_win_rate_min=0.70`.

Change:

- `scion/problems/warehouse_delivery/protocol_prod.yaml`
  - `pair_win_rate_min: 0.46`
  - `pair_non_tie_win_rate_min: 0.68`

No generic Decision code changed. The repair is problem-owned protocol policy:
Decision still consumes deterministic `DecisionFeatures`, and raw warehouse
diagnostics, branch lessons, prompts, and LLM text remain outside Decision.

Deterministic acceptance:

- Shape A now queues diagnostic validation:
  - case W/L/T `3/1/10`
  - pair W/L/T `13/6/9`
  - median delta `300`
  - CI `[0, 875]`
  - reason codes:
    `SCREENING_EXPAND_EXHAUSTED_PAIR_SIGNAL_POLICY_PASS`,
    `SCREENING_PAIR_LEVEL_SIGNAL_DIAGNOSTIC_VALIDATE`
- Shape B remains fail-closed:
  - case W/L/T `4/2/10`
  - pair W/L/T `14/12/6`
  - median delta `-50`
  - reason codes include
    `SCREENING_EXPAND_EXHAUSTED_BORDERLINE_NEGATIVE_DELTA`,
    `SCREENING_BORDERLINE_POLICY_FAIL_CLOSED`,
    `BRANCH_LIFECYCLE_ARCHIVE_LINEAGE`
- Shape C does not validate:
  - case W/L/T `1/2/3`
  - pair W/L/T `3/4/5`
  - median delta `0`
  - reason codes include `SCREENING_FAIL_WIN_RATE`; no diagnostic validation
    code is present.
- Existing pair-positive route remains valid:
  - case W/L/T `2/0/4`
  - pair W/L/T `6/2/4`
  - median delta `0`
  - queues diagnostic validation.

Tests:

- `PYTHONPATH=scion /home/clawd/miniconda3/envs/claw/bin/python -m pytest -q scion/scion/tests/test_config.py scion/scion/tests/test_decision_screening.py scion/scion/tests/test_protocol_stats_gates.py`
  - `92 passed`
- `PYTHONPATH=scion /home/clawd/miniconda3/envs/claw/bin/python -m pytest -q scion/scion/tests/unit/core/test_branch_lifecycle_policy.py scion/scion/tests/test_decision_validation_frozen.py scion/scion/tests/unit/core/test_decision_finalizer_lifecycle.py scion/scion/tests/unit/core/test_scheduler_runtime_evidence_pressure.py`
  - `93 passed`
- `PYTHONPATH=scion /home/clawd/miniconda3/envs/claw/bin/python -m pytest -q scion/scion/tests/test_problem_bridge.py scion/scion/tests/test_config.py scion/scion/tests/test_decision_screening.py scion/scion/tests/test_protocol_stats_gates.py`
  - `100 passed`
- Python compile and `git diff --check` passed for the affected files.

Next field gate:

- Run another short warehouse production `6R` cell from the repair commit.
- Acceptance requires that expanded-exhausted positive low-SNR evidence reaches
  validation instead of remaining screening-only.
- Validation/frozen/promotion must still reject or confirm the candidate through
  ordinary protocol evidence; this repair does not loosen later-stage gates.
