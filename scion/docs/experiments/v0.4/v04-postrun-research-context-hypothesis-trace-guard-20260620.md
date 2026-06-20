# v0.4 Postrun Research Context Hypothesis Trace Guard

Date: 2026-06-20

## Purpose

R3/R4 readiness must prove that current-run research-context accounting covers
the next hypothesis/proposal prompt. Code-only prompt manifests can prove source
visibility for code generation, but they cannot prove that branch-depth,
same-mechanism, weak-positive transfer, or cross-branch lesson signals reached
the hypothesis-generation prompt.

This guard is report/readiness only. It does not add problem semantics to
`DecisionFeatures`, Protocol gates, lifecycle policy, scheduler state,
promotion, or solver logic.

## Change

- `scion/tools/check_postrun_acceptance.py` now requires a formal hypothesis
  generation prompt trace in `prompt_context_visibility_summary.aggregate
  .call_kind_counts` for warehouse/CVRP research-context readiness.
- `hypothesis`, `hypothesis_retry`, `hypothesis_preview_retry`,
  `hypothesis_semantic_retry`, and `hypothesis_grounding_retry` count as formal
  hypothesis-generation traces.
- `hypothesis_target_intent` and `code` prompts do not satisfy this guard.
- `scion/scion/tests/test_check_postrun_acceptance.py` now has a code-only
  prompt-manifest regression test.

Accepted commits:

- Local code commit: `96560d9f`
- WSL runtime commit: `3b7a116b`

## Verification

Local:

```bash
python -m py_compile scion/tools/check_postrun_acceptance.py scion/scion/tests/test_check_postrun_acceptance.py
PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion pytest -q scion/scion/tests/test_check_postrun_acceptance.py
PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion pytest -q scion/scion/tests/test_launch_readiness.py scion/scion/tests/test_check_postrun_acceptance.py scion/scion/tests/test_rebuild_prepared_handoff.py
```

Observed: `50 passed` for postrun acceptance and `141 passed` for the related
launch-readiness/postrun/rebuild suite.

WSL:

```bash
PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion /home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m pytest -q scion/scion/tests/test_check_postrun_acceptance.py
PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion /home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m pytest -q scion/scion/tests/test_launch_readiness.py scion/scion/tests/test_check_postrun_acceptance.py scion/scion/tests/test_rebuild_prepared_handoff.py
```

Observed: `50 passed` for postrun acceptance and `141 passed` for the related
launch-readiness/postrun/rebuild suite.

## Prepared Roots

The prior `29b65698` roots are superseded because runtime-guarded
`scion/tools` changed. New WSL prepared roots from runtime commit `3b7a116b`:

- Warehouse:
  `/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-v2-followup-hyptrace-3b7a116b-preflight-6r-gpt55-20260620T012745Z-claw`
- CVRP:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-large-twoopt-phase4-hyptrace-3b7a116b-preflight-4r-gpt55-20260620T012800Z-claw`

Local mirrors:

- Warehouse:
  `/home/clawd/research/scion-experiments/v04-warehouse-v2-followup-hyptrace-3b7a116b-preflight-6r-gpt55-20260620T012745Z-claw`
- CVRP:
  `/home/clawd/research/scion-experiments/v04-cvrp-large-twoopt-phase4-hyptrace-3b7a116b-preflight-4r-gpt55-20260620T012800Z-claw`

Strict launch readiness was saved as `readiness.strict.json` in each root.
Both roots report:

- `static_ready=true`
- `launch_ready=false`
- `failed_static_required_checks=[]`
- `failed_required_checks=["completion_preflight"]`
- `git_runtime_guard_commit_consistent=ok` at `3b7a116b`
- `run_script_runtime_guard_contract_consistency=ok`

The only launch blocker remains external completion auth:

- HTTP `401`
- `classification=not_authenticated`
- `code=invalid_api_key`
- auth pool `active=0`, `expired=1`, `total=1`

## Next Step

Refresh the WSL/local proxy login, rerun strict launch readiness until
`launch_ready=true`, then launch warehouse first as the simpler continuous
research proof before the CVRP bounded two-opt follow-up.
