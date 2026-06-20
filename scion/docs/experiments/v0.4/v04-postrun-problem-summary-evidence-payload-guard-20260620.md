# v0.4 Postrun Problem Summary Evidence Payload Guard

Date: 2026-06-20

## Purpose

Current-run warehouse/CVRP delegated review must not accept a
protocol-evaluated, plateau, positive-effect, or bounded two-opt conclusion
from summary text alone. If a problem summary claims current-run evidence, it
must carry an explicit `evidence` payload that can be checked against the
review inputs.

This is a framework/readiness guard only. It does not add problem semantics to
`DecisionFeatures`, promotion, scheduler state, or solver logic.

## Change

- `scion/tools/check_postrun_acceptance.py` now reports
  `problem_summary_evidence_missing` when a current-run problem summary has no
  `evidence` payload.
- `scion/scion/tests/test_check_postrun_acceptance.py` covers the missing
  payload rejection and verifies that actionability and input-consistency both
  fail for that case.

Accepted commits:

- Local code commit: `15ff63e0`
- WSL runtime commit: `29b65698`

## Verification

Local:

```bash
python -m py_compile scion/tools/check_postrun_acceptance.py scion/scion/tests/test_check_postrun_acceptance.py
PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion pytest -q scion/scion/tests/test_check_postrun_acceptance.py
PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion pytest -q scion/scion/tests/test_launch_readiness.py scion/scion/tests/test_check_postrun_acceptance.py scion/scion/tests/test_rebuild_prepared_handoff.py
```

Observed: `49 passed` for postrun acceptance and `140 passed` for the related
readiness/postrun/rebuild suite.

WSL:

```bash
PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion /home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m pytest -q scion/scion/tests/test_check_postrun_acceptance.py
PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion /home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m pytest -q scion/scion/tests/test_launch_readiness.py scion/scion/tests/test_check_postrun_acceptance.py scion/scion/tests/test_rebuild_prepared_handoff.py
```

Observed: `49 passed` for postrun acceptance and `140 passed` for the related
readiness/postrun/rebuild suite.

## Prepared Roots

The prior `2d0db1b6` roots are superseded because runtime-guarded `scion/tools`
changed. New WSL prepared roots from runtime commit `29b65698`:

- Warehouse:
  `/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-v2-followup-evidenceguard-29b65698-preflight-6r-gpt55-20260620T011035Z-claw`
- CVRP:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-large-twoopt-phase4-evidenceguard-29b65698-preflight-4r-gpt55-20260620T011050Z-claw`

Local mirrors:

- Warehouse:
  `/home/clawd/research/scion-experiments/v04-warehouse-v2-followup-evidenceguard-29b65698-preflight-6r-gpt55-20260620T011035Z-claw`
- CVRP:
  `/home/clawd/research/scion-experiments/v04-cvrp-large-twoopt-phase4-evidenceguard-29b65698-preflight-4r-gpt55-20260620T011050Z-claw`

Strict launch readiness was saved as `readiness.strict.json` in each root.
Both roots report:

- `static_ready=true`
- `launch_ready=false`
- `failed_static_required_checks=[]`
- `failed_required_checks=["completion_preflight"]`
- `git_runtime_guard_commit_consistent=ok` at `29b65698`
- `run_script_runtime_guard_contract_consistency=ok`

The only launch blocker is external completion auth:

- HTTP `401`
- `classification=not_authenticated`
- `code=invalid_api_key`
- auth pool `active=0`, `expired=1`, `total=1`

## Next Step

Refresh the WSL/local proxy login, rerun strict launch readiness until
`launch_ready=true`, then launch warehouse first as the simpler continuous
research proof before the CVRP bounded two-opt follow-up.
