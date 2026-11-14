# v0.4 Trajectory-Divergent Open Low-Signal Lifecycle

Date: 2026-06-19

## Purpose

Keep declared trajectory-divergent, non-regressive low-SNR screening research
alive inside the requested campaign rounds instead of parking it through fixed
no-effect, repeated-signature, rollback-budget, or zero-win lifecycle counters.

This is a lifecycle-depth repair, not a promotion-gate relaxation. It preserves
the v3 boundary: Decision still reads deterministic `DecisionFeatures` and
problem-owned protocol config only. Raw calibration diagnostics, LLM text, BKS,
case gaps, and problem free text remain excluded from `DecisionFeatures`.

## Change

- `BranchLifecyclePolicy` now has `open_ended_low_signal_followup`.
- `DecisionEngine` enables that policy only when
  `ProtocolConfig.pairing_validity == "trajectory_divergent"`.
- Default and trajectory-stable lifecycle behavior remains unchanged.
- Negative median delta, loss-heavy evidence, candidate runtime failure,
  verification failure, canary failure, timeout, and true runtime regression
  still fail closed.

## Verification

Local:

```bash
python -m py_compile scion/scion/core/branch_lifecycle_policy.py scion/scion/core/decision.py scion/scion/tests/unit/core/test_branch_lifecycle_policy.py scion/scion/tests/test_decision_screening.py
PYTHONPATH=scion pytest -q scion/scion/tests/test_decision_screening.py scion/scion/tests/unit/core/test_branch_lifecycle_policy.py
PYTHONPATH=scion pytest -q scion/scion/tests/test_decision.py scion/scion/tests/test_decision_validation_frozen.py scion/scion/tests/unit/core/test_decision_finalizer_park_lifecycle.py
PYTHONPATH=scion pytest -q scion/scion/tests/test_scheduler.py scion/scion/tests/unit/core/test_branch_step_runner_scheduler_metadata.py
PYTHONPATH=scion pytest -q scion/scion/tests/test_config.py scion/scion/tests/test_problem_bridge.py scion/scion/tests/unit/test_problem_measurement_artifacts.py scion/scion/tests/unit/test_measurement_readiness.py
PYTHONPATH=scion pytest -q scion/scion/tests/test_protocol_stats_gates.py scion/scion/tests/unit/core/test_runtime_budget_diagnostics.py scion/scion/tests/unit/test_agentic_feedback_screening.py scion/scion/tests/unit/test_screening_feedback_tiers_memory.py
PYTHONPATH=scion pytest -q scion/scion/tests/unit/core/test_campaign_control_lifecycle_budget_runtime.py scion/scion/tests/unit/core/test_retry_round_accounting.py scion/scion/tests/unit/core/test_proposal_pipeline_hypothesis.py
PYTHONPATH=scion pytest -q scion/scion/tests/unit/core/test_decision_finalizer_lifecycle.py scion/scion/tests/unit/core/test_evaluation_orchestrator_telemetry.py
PYTHONPATH=scion pytest -q scion/scion/tests/unit/core/test_scheduler_runtime_evidence_pressure.py scion/scion/tests/unit/test_branch_followup_policy.py scion/scion/tests/unit/test_branch_prompt_projection.py
git diff --check
```

Observed local results:

- `84 passed`
- `28 passed`
- `66 passed`
- `35 passed`
- `60 passed`
- `61 passed`
- `33 passed`
- `40 passed`
- `git diff --check` passed

WSL:

```bash
PYTHONPATH=scion /home/xjy-ubuntu/miniconda3/envs/scion/bin/pytest -q scion/scion/tests/test_decision_screening.py scion/scion/tests/unit/core/test_branch_lifecycle_policy.py
PYTHONPATH=scion /home/xjy-ubuntu/miniconda3/envs/scion/bin/pytest -q scion/scion/tests/test_decision.py scion/scion/tests/test_decision_validation_frozen.py scion/scion/tests/unit/core/test_decision_finalizer_park_lifecycle.py
PYTHONPATH=scion /home/xjy-ubuntu/miniconda3/envs/scion/bin/pytest -q scion/scion/tests/test_scheduler.py scion/scion/tests/unit/core/test_branch_step_runner_scheduler_metadata.py
PYTHONPATH=scion /home/xjy-ubuntu/miniconda3/envs/scion/bin/pytest -q scion/scion/tests/test_config.py scion/scion/tests/test_problem_bridge.py scion/scion/tests/unit/test_problem_measurement_artifacts.py scion/scion/tests/unit/test_measurement_readiness.py
PYTHONPATH=scion /home/xjy-ubuntu/miniconda3/envs/scion/bin/pytest -q scion/scion/tests/test_protocol_stats_gates.py scion/scion/tests/unit/core/test_runtime_budget_diagnostics.py scion/scion/tests/unit/test_agentic_feedback_screening.py scion/scion/tests/unit/test_screening_feedback_tiers_memory.py
PYTHONPATH=scion /home/xjy-ubuntu/miniconda3/envs/scion/bin/pytest -q scion/scion/tests/unit/core/test_campaign_control_lifecycle_budget_runtime.py scion/scion/tests/unit/core/test_retry_round_accounting.py scion/scion/tests/unit/core/test_proposal_pipeline_hypothesis.py
PYTHONPATH=scion /home/xjy-ubuntu/miniconda3/envs/scion/bin/pytest -q scion/scion/tests/unit/core/test_decision_finalizer_lifecycle.py scion/scion/tests/unit/core/test_evaluation_orchestrator_telemetry.py scion/scion/tests/unit/core/test_scheduler_runtime_evidence_pressure.py scion/scion/tests/unit/test_branch_followup_policy.py scion/scion/tests/unit/test_branch_prompt_projection.py
git diff --check
```

Observed WSL results:

- `84 passed`
- `28 passed`
- `66 passed`
- `35 passed`
- `60 passed`
- `61 passed`
- `73 passed`
- `git diff --check` passed

## Prepared Roots

New WSL runtime commit: `8f1994ea`.

- Warehouse:
  `/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-v2-followup-openlowsnr-8f1994ea-6r-gpt55-20260619T173441Z-claw`
- CVRP:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-large-twoopt-openlowsnr-8f1994ea-1r-gpt55-20260619T173442Z-claw`

Strict launch readiness for both roots:

- `static_ready=true`
- `launch_ready=false`
- exit `64`
- `git_runtime_consistent=ok`, detail `checkout matches manifest commit`
- completion preflight failed with HTTP `401`,
  `classification=not_authenticated`, `code=invalid_api_key`
- auth pool: `active=0`, `expired=1`, `total=1`

No campaign was launched.

## Residual Risk

This repair removes fixed low-signal lifecycle truncation only for declared
trajectory-divergent problems. It relies on the requested campaign round budget,
hard negative evidence, runtime/verification/canary failures, and postrun review
to stop unproductive research. The empirical proof is still pending until auth
is refreshed and the warehouse/CVRP prepared roots can run.
