# Prepared Root Runtime Guard Refresh

Date: 2026-06-18
Branch: `codex/v04-evidence-repair-plan`

## Purpose

Refresh the launch-prepared CVRP and warehouse roots after runtime-guard code
changed in commit `ec1e88f5`. The previous prepared roots were still
prepare-only, but `check_launch_readiness.py` correctly rejected them because
their manifests were bound to commit `35de1b5` and runtime guard paths changed.

## Previous Roots

- CVRP:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-postpivot-resume-ready-actionpreflight-1r-gpt55-1r-gpt55-20260618T145045Z-claw`
- Warehouse:
  `/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-v2-followup-ready-actionpreflight-6r-gpt55-6r-gpt55-20260618T145046Z-claw`

Readiness result for both previous roots:

- `static_ready=false`
- `git_runtime_consistent=failed`
- detail: `checkout differs and runtime guard paths changed`
- `prepared_contract_complete=failed`

Those roots must not be launched.

## Refreshed Roots

- CVRP:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-postpivot-resume-ready-ec1e88f-1r-gpt55-1r-gpt55-20260618T153718Z-claw`
- Warehouse:
  `/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-v2-followup-ready-ec1e88f-6r-gpt55-6r-gpt55-20260618T153719Z-claw`

Both refreshed roots are prepare-only and preserve the current resume sources:

- CVRP resumes from
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-postpivot-guidance-agentic-1r-acc21ba-20260618T064210Z/campaign`.
- Warehouse resumes from
  `/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-validation-transfer-contract-rerun6r-ce5d884-20260617T152944Z/rep01/full_context/campaign`.

## Verification

WSL readiness checks with real completion preflight:

```bash
PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion \
  /home/xjy-ubuntu/miniconda3/envs/scion/bin/python \
  scion/tools/check_launch_readiness.py <run-root> \
  --completion-preflight --format json
```

For both refreshed roots:

- `static_ready=true`
- `git_runtime_consistent=ok`
- `prepared_contract_complete=ok`
- `prepared_only_not_started=ok`
- `zero_current_run_counters=ok`
- `launch_ready=false`

The remaining launch blocker is still infrastructure, not the prepared roots:
the real chat completion returns HTTP `401` with
`classification=not_authenticated`; the latest auth pool snapshot reports
`authenticated=false`, `active=0`, `refreshing=1`.

## Launch Rule

Do not launch either refreshed root until:

```bash
scion/tools/check_launch_readiness.py <run-root> \
  --completion-preflight --format json
```

reports `launch_ready=true` with a non-empty `gpt-5.5` completion.
