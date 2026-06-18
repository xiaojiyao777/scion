# Prepared Root Runtime Guard Refresh After Scheduler Slot Repair

Date: 2026-06-18
Branch: `codex/v04-evidence-repair-plan`
Commit: `7e12c62`

## Purpose

Refresh the launch-prepared CVRP and warehouse roots after
`scion/scion/core/scheduler.py` changed for the low-signal same-branch slot
repair. The previous `ec1e88f` roots were still prepare-only, but
`check_launch_readiness.py` correctly rejected at least the CVRP root because
runtime guard paths changed.

## Superseded Roots

- CVRP:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-postpivot-resume-ready-ec1e88f-1r-gpt55-1r-gpt55-20260618T153718Z-claw`
- Warehouse:
  `/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-v2-followup-ready-ec1e88f-6r-gpt55-6r-gpt55-20260618T153719Z-claw`

The old CVRP root reported:

- `static_ready=false`
- `git_runtime_consistent=failed`
- detail: `checkout differs and runtime guard paths changed`
- `prepared_contract_complete=failed`

Do not launch the superseded roots.

## Current Prepared Roots

- CVRP:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-postpivot-resume-ready-7e12c62-1r-gpt55-1r-gpt55-20260618T155025Z-claw`
- Warehouse:
  `/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-v2-followup-ready-7e12c62-6r-gpt55-6r-gpt55-20260618T155038Z-claw`

Both roots are prepare-only and preserve the same resume sources:

- CVRP resumes from
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-postpivot-guidance-agentic-1r-acc21ba-20260618T064210Z/campaign`.
- Warehouse resumes from
  `/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-validation-transfer-contract-rerun6r-ce5d884-20260617T152944Z/rep01/full_context/campaign`.

## Verification

WSL focused tests at commit `7e12c62`:

```bash
PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion \
  /home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m pytest -q \
  scion/scion/tests/unit/core/test_scheduler_runtime_evidence_pressure.py \
  scion/scion/tests/unit/core/test_branch_step_runner_scheduler_metadata.py \
  scion/scion/tests/test_scheduler.py \
  scion/scion/tests/unit/core/test_branch_lifecycle_policy.py \
  scion/scion/tests/unit/core/test_branch_hygiene_status.py \
  scion/scion/tests/unit/core/test_proposal_pipeline_hypothesis.py \
  scion/scion/tests/unit/test_branch_prompt_projection.py
```

Result: `171 passed`.

WSL launch-readiness checks with real completion preflight:

```bash
PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion \
  /home/xjy-ubuntu/miniconda3/envs/scion/bin/python \
  scion/tools/check_launch_readiness.py <run-root> \
  --completion-preflight --format json
```

For both current roots:

- `static_ready=true`
- `git_runtime_consistent=ok`
- `prepared_contract_complete=ok`
- `prepared_only_not_started=ok`
- `zero_current_run_counters=ok`
- `launch_ready=false`

The remaining blocker is still LLM infrastructure, not Scion code or prepared
contracts: `/v1/chat/completions` returns HTTP `401` with
`classification=not_authenticated`; the auth pool reports
`authenticated=false`, `active=0`, and `refreshing=1`. Readiness includes an
`operator_action.login_url`.

## Launch Rule

Do not launch either current root until:

```bash
scion/tools/check_launch_readiness.py <run-root> \
  --completion-preflight --format json
```

reports `launch_ready=true` with a non-empty `gpt-5.5` completion.
