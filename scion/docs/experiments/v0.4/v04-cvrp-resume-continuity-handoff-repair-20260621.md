# v0.4 CVRP Resume-Continuity Handoff Repair

Date: 2026-06-21

Scope: launch-before-auth repair for the current CVRP sparse-resume prepared
root. This is proposal/control-plane guidance only; it is not current-run
research evidence and not a Decision input.

## Boundary

The v3 boundary is preserved. The new
`resume_continuity_requirements` payload is problem-owned CVRP prepared-handoff
material with `proposal_visibility_only=true` and
`decision_features_excluded=true`. It is projected into hypothesis prompt
context through the existing prepared `research_focus` bridge and is checked by
readiness as boolean/count/path evidence. It does not enter
`DecisionFeatures`, Protocol gates, promotion input, scheduler state, or solver
semantics.

## Repair

The previous CVRP prepared root copied a sparse resume campaign with no branch
cards. Static readiness was technically clean, but the first live prompt could
fall back to prepared research focus plus target-intent traces without an
explicit continuity contract.

The repair adds a CVRP prepared-handoff requirement that a sparse resume with
zero branch cards must not be treated as an empty campaign. The first live
proposal must use the prepared focus plus copied target-intent or hypothesis
trace evidence, and must either continue the bounded large-instance intra-route
two-opt/CMT2/CMT4 path or name a materially different problem-owned causal
mechanism.

Code commits:

- Local: `b14eb332` (`Require CVRP resume continuity handoff`)
- WSL: `c7b06d9a` (`Require CVRP resume continuity handoff`)

## Verification

Local:

```bash
PYTHONPATH=scion pytest -q \
  scion/scion/tests/test_launch_readiness.py \
  scion/scion/tests/test_cvrp_agentic_launcher.py \
  scion/scion/tests/test_rebuild_prepared_handoff.py \
  scion/scion/tests/test_postrun_artifact_inventory.py \
  scion/scion/tests/test_postrun_analysis_brief.py \
  scion/scion/tests/test_check_postrun_acceptance.py
```

Result: `268 passed in 95.12s`.

WSL focused check:

```bash
PYTHONPATH=scion /home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m pytest -q \
  scion/scion/tests/test_rebuild_prepared_handoff.py \
  scion/scion/tests/test_launch_readiness.py::test_launch_readiness_accepts_clean_prepared_root \
  scion/scion/tests/test_launch_readiness.py::test_launch_readiness_rejects_missing_cvrp_resume_continuity \
  scion/scion/tests/test_cvrp_agentic_launcher.py::test_cvrp_agentic_launcher_prepare_writes_run_files
```

Result: `6 passed in 1.93s`.

## Refreshed Prepared Roots

Warehouse:

`/home/xjy-ubuntu/research/scion-experiments/v04-wh-v2-c7b06d9-resumecont-6r-gpt55-20260621T023211Z-claw`

Local mirror:

`/home/clawd/research/scion-experiments/v04-wh-v2-c7b06d9-resumecont-6r-gpt55-20260621T023211Z-claw`

CVRP:

`/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-twoopt-c7b06d9-resumecont-4r-gpt55-20260621T023211Z-claw`

Local mirror:

`/home/clawd/research/scion-experiments/v04-cvrp-twoopt-c7b06d9-resumecont-4r-gpt55-20260621T023211Z-claw`

Strict launch readiness for both refreshed roots reports:

- `static_ready=true`
- `launch_ready=false`
- `failed_static_required_checks=[]`
- only required failure: `completion_preflight`
- completion preflight: HTTP `401`, `classification=not_authenticated`,
  `code=invalid_api_key`
- `runtime_guard_status=ok`
- `prepared_runtime_commit=c7b06d9a`
- `actual_runtime_commit=c7b06d9a`
- `campaign_execution_marker_status=ok`
- `launch_env_secret_permissions=ok`

The refreshed CVRP prepared prompt-context report has:

- `signals.cvrp_resume_continuity_requirements.available=true`
- `fallback_source_count=3`
- `rule_count=3`
- `required_evidence_count=3`
- `prompt_summary.cvrp_resume_continuity_present=true`
- `prompt_summary.cvrp_resume_continuity_required_evidence_all_present=true`
- `prompt_summary.missing_rendered_paths=[]`

## Remaining Blocker

The only launch blocker remains external WSL `gpt-5.5` completion auth. Do not
launch either refreshed root until strict readiness reports `launch_ready=true`.
Warehouse should still launch first as the simpler continuous-improvement proof,
then CVRP should launch from the refreshed sparse-resume root.
