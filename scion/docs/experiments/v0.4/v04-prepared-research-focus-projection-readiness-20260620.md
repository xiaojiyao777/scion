# v0.4 Prepared Research-Focus Projection Readiness

Date: 2026-06-20

## Summary

Prepared prompt-context readiness now checks that prepared
`research_focus` fields are not only present in the manifest, but also survive
the deterministic `launch_research_focus` projection used by hypothesis
prompts. This closes the launch-before-auth gap where a problem-owned handoff
field could pass report checks while being absent from the proposal focus.

The check is report-only and prompt-safe:

- no raw provider prompt is rendered;
- `quality_judgment=false`;
- `decision_features_excluded=true`;
- campaign, scheduler, and promotion state are not mutated.

## Roots

Prepared from synchronized WSL commit `76a3bccd` after the local code commit
`0b2ef126`.

Warehouse:

- WSL:
  `/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-v2-followup-projguard-76a3bccd-preflight-6r-gpt55-20260620T032757Z-claw`
- Local mirror:
  `/home/clawd/research/scion-experiments/v04-warehouse-v2-followup-projguard-76a3bccd-preflight-6r-gpt55-20260620T032757Z-claw`

CVRP:

- WSL:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-large-twoopt-phase4-projguard-76a3bccd-preflight-4r-gpt55-20260620T032757Z-claw`
- Local mirror:
  `/home/clawd/research/scion-experiments/v04-cvrp-large-twoopt-phase4-projguard-76a3bccd-preflight-4r-gpt55-20260620T032757Z-claw`

Strict readiness for both roots:

- `static_ready=true`
- `launch_ready=false`
- `failed_static_required_checks=[]`
- `failed_required_checks=["completion_preflight"]`
- completion auth: HTTP `401`, `classification=not_authenticated`,
  `code=invalid_api_key`, auth pool `active=0`, `refreshing=1`, `total=1`

Projection readiness:

- Warehouse projected required fields include `accepted_checkpoint`,
  `current_question`, measurement diagnostics, required evidence, default
  avoid directions, and the decision boundary.
- CVRP projected required fields include `case_protection_requirements`,
  bounded large two-opt constraints, measurement diagnostics, direct-effect
  rules, measurable opportunity classes, default avoid directions, and the
  decision boundary.
- Both roots report `missing_projected_keys=[]`.

## Verification

Local:

```bash
python -m py_compile scion/tools/prepared_prompt_context.py scion/tools/rebuild_prepared_handoff.py scion/tools/check_launch_readiness.py
pytest -q scion/scion/tests/test_rebuild_prepared_handoff.py
pytest -q scion/scion/tests/test_launch_readiness.py -k 'clean_prepared_root or prompt_context or missing_cvrp_measurement or missing_cvrp_cmt_case_protection'
```

WSL:

```bash
PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion \
/home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m py_compile \
  scion/tools/prepared_prompt_context.py \
  scion/tools/rebuild_prepared_handoff.py \
  scion/tools/check_launch_readiness.py

PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion \
/home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m pytest -q \
  scion/scion/tests/test_rebuild_prepared_handoff.py

PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion \
/home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m pytest -q \
  scion/scion/tests/test_launch_readiness.py \
  -k 'clean_prepared_root or prompt_context or missing_cvrp_measurement or missing_cvrp_cmt_case_protection'
```

## Boundary Check

The projection summary audits only prepared prompt guidance. It does not feed
Decision, `DecisionFeatures`, Protocol gates, promotion input, scheduler state,
or solver semantics. CVRP/warehouse semantics remain problem-owned and
proposal-visible only.

## Next Step

Refresh the local proxy login, rerun strict launch readiness until
`launch_ready=true`, then launch the warehouse root first.
