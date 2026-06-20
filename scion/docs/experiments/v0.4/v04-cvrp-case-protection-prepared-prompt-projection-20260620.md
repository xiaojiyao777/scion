# v0.4 CVRP Case-Protection Prepared Prompt Projection

Date: 2026-06-20

## Summary

CVRP `case_protection_requirements` were present in the prepared manifest and
postrun handoff reports, but the proposal-context projection omitted them from
`launch_research_focus`. That meant the CMT2/CMT4 protection requirement could
pass prepared handoff checks while failing to reach the next hypothesis prompt.

This repair projects the prepared CVRP case-protection payload into the
proposal-only launch research focus and adds a required prepared prompt-context
readiness signal:

- `cvrp_case_protection_requirements.available=true`
- `cvrp_case_protection_requirements.required=true`
- protected cases: `CMT2`, `CMT4`

## Roots

Warehouse:

- WSL:
  `/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-v2-followup-cmtprompt-7f06d4c4-preflight-6r-gpt55-20260620T031230Z-claw`
- Local mirror:
  `/home/clawd/research/scion-experiments/v04-warehouse-v2-followup-cmtprompt-7f06d4c4-preflight-6r-gpt55-20260620T031230Z-claw`
- Runtime guard commit: `7f06d4c4`

CVRP:

- WSL:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-large-twoopt-phase4-cmtprompt-7f06d4c4-preflight-4r-gpt55-20260620T031242Z-claw`
- Local mirror:
  `/home/clawd/research/scion-experiments/v04-cvrp-large-twoopt-phase4-cmtprompt-7f06d4c4-preflight-4r-gpt55-20260620T031242Z-claw`
- Runtime guard commit: `7f06d4c4`

Strict readiness for both roots:

- `static_ready=true`
- `launch_ready=false`
- `failed_static_required_checks=[]`
- `failed_required_checks=["completion_preflight"]`
- completion auth: HTTP `401`, `classification=not_authenticated`,
  `code=invalid_api_key`, auth pool `active=0`, `expired=1`, `total=1`

## Verification

Local:

```bash
pytest -q scion/scion/tests/unit/test_research_surfaces_cvrp_context.py scion/scion/tests/test_rebuild_prepared_handoff.py scion/scion/tests/test_cvrp_agentic_launcher.py
pytest -q scion/scion/tests/test_launch_readiness.py -k 'cmt_case_protection or prompt_context or prepared_handoff'
pytest -q scion/scion/tests/unit/test_hypothesis_context_profiles.py scion/scion/tests/unit/test_research_surfaces_cvrp_context.py
pytest -q scion/scion/tests/test_postrun_artifact_inventory.py -k 'cvrp or prepared' scion/scion/tests/test_postrun_analysis_brief.py -k 'cvrp or prepared'
python -m py_compile scion/scion/proposal/context_manager/manager.py scion/tools/rebuild_prepared_handoff.py scion/scion/tests/unit/test_research_surfaces_cvrp_context.py scion/scion/tests/test_rebuild_prepared_handoff.py scion/scion/tests/test_cvrp_agentic_launcher.py
git diff --check
```

WSL:

```bash
PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion \
/home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m pytest -q \
  scion/scion/tests/unit/test_research_surfaces_cvrp_context.py \
  scion/scion/tests/test_rebuild_prepared_handoff.py \
  scion/scion/tests/test_cvrp_agentic_launcher.py \
  scion/scion/tests/test_launch_readiness.py \
  -k 'cmt_case_protection or prompt_context or prepared_handoff'
```

## Boundary Check

The projected case-protection payload is tainted proposal guidance only. It is
marked `proposal_visibility_only=true` and `decision_features_excluded=true`,
and it does not enter Decision, `DecisionFeatures`, Protocol gates, promotion
input, scheduler state, or solver semantics.

## Next Step

Refresh the local proxy login, rerun strict launch readiness, and launch the
warehouse root first once `launch_ready=true`.
