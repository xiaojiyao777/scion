# CVRP CMT Case-Protection Handoff

Date: 2026-06-19
Branch: `codex/v04-evidence-repair-plan`

## Summary

The CVRP prepared handoff already carried bounded large-instance two-opt
constraints, default-avoid directions, and direct-effect rules for route-merge
and construction-seed mechanisms. This repair adds a structured
`case_protection_requirements` payload for CMT2/CMT4 so a prepared CVRP root is
not static-ready unless the next construction, route-merge, demand-slack, VNS,
or share70-derived branch slot carries explicit protected-case guidance.

The payload is proposal/delegated-analysis guidance only. It is report-only,
`DecisionFeatures`-excluded, and does not change Protocol gates, promotion,
scheduler state, or solver behavior.

## Runtime Commits

- Local code/test commit: `025ff7d7`
- WSL runner code/test commit: `6db5b58`

## Prepared Roots

- Warehouse:
  `/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-v2-followup-cmtcase-6db5b58-6r-gpt55-6r-gpt55-20260619T140050Z-claw`
- CVRP:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-large-twoopt-cmtcase-6db5b58-1r-gpt55-1r-gpt55-20260619T140050Z-claw`

Both roots were prepared from a clean WSL runner worktree at `6db5b58`.

## Acceptance

Local checks:

```bash
PYTHONPATH=scion pytest -q scion/scion/tests/test_launch_readiness.py
PYTHONPATH=scion pytest -q scion/scion/tests/test_postrun_artifact_inventory.py scion/scion/tests/test_postrun_analysis_brief.py
PYTHONPATH=scion pytest -q scion/scion/tests/test_launch_readiness.py scion/scion/tests/test_postrun_artifact_inventory.py scion/scion/tests/test_postrun_analysis_brief.py scion/scion/tests/test_check_postrun_acceptance.py scion/scion/tests/test_rebuild_postrun_acceptance.py
python -m py_compile scion/tools/launch_cvrp_agentic_campaign.py scion/tools/postrun_artifact_inventory.py scion/scion/tests/test_launch_readiness.py scion/scion/tests/test_postrun_artifact_inventory.py
git diff --check
```

Results:

- Launch readiness tests: `57 passed`
- Inventory/analysis brief tests: `37 passed`
- Core readiness/postrun suite: `131 passed`
- Compile and whitespace checks: passed

WSL checks:

```bash
PYTHONPATH=scion /home/xjy-ubuntu/miniconda3/envs/scion/bin/pytest -q scion/scion/tests/test_launch_readiness.py scion/scion/tests/test_postrun_artifact_inventory.py
/home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m py_compile scion/tools/launch_cvrp_agentic_campaign.py scion/tools/postrun_artifact_inventory.py scion/scion/tests/test_launch_readiness.py scion/scion/tests/test_postrun_artifact_inventory.py
```

Results:

- WSL focused suite: `68 passed`
- WSL compile check: passed

## Launch Readiness

Static readiness from WSL:

- Warehouse: `static_ready=true`, `launch_ready=false`,
  `prepared_contract_complete=ok`, `problem_specific_prepared_handoff=ok`,
  `analysis_brief_prepared_contract_consistency=ok`,
  `prompt_context_readiness_complete=ok`, `git_runtime_consistent=ok`.
- CVRP: `static_ready=true`, `launch_ready=false`,
  `prepared_contract_complete=ok`, `problem_specific_prepared_handoff=ok`,
  `analysis_brief_prepared_contract_consistency=ok`,
  `prompt_context_readiness_complete=ok`, `git_runtime_consistent=ok`.
  The CVRP problem-specific detail includes
  `cvrp_cmt_case_protection_present=true`, protected cases `CMT2` and `CMT4`,
  four rules, three required evidence items, and no missing tokens.

Strict launch readiness with `SCION_API_KEY=pwd --require-launch-ready` still
exits `64` for both roots because the external `gpt-5.5` provider auth is not
launch-usable:

- HTTP status: `401`
- Classification: `not_authenticated`
- Code: `invalid_api_key`
- Auth pool: `active=0`, `expired=1`, `refreshing=0`, `total=1`

Do not launch either prepared root until strict launch readiness reports
`launch_ready=true`.

## Analysis Brief Surface

A follow-up audit-surface repair made the prepared analysis brief render
`case_protection_requirements` in the "Current research focus" section and added
`cvrp_cmt_case_protection_handoff` to the CVRP large-twoopt handoff
requirements table. This keeps delegated review usable when reviewers inspect
the analysis brief instead of the raw prepared manifest.

Additional checks:

```bash
PYTHONPATH=scion pytest -q scion/scion/tests/test_postrun_analysis_brief.py
PYTHONPATH=scion pytest -q scion/scion/tests/test_launch_readiness.py scion/scion/tests/test_postrun_artifact_inventory.py scion/scion/tests/test_postrun_analysis_brief.py scion/scion/tests/test_check_postrun_acceptance.py scion/scion/tests/test_rebuild_postrun_acceptance.py
PYTHONPATH=scion /home/xjy-ubuntu/miniconda3/envs/scion/bin/pytest -q scion/scion/tests/test_postrun_analysis_brief.py scion/scion/tests/test_postrun_artifact_inventory.py scion/scion/tests/test_check_postrun_acceptance.py scion/scion/tests/test_rebuild_postrun_acceptance.py
```

Results:

- Local analysis brief tests: `26 passed`
- Local core readiness/postrun suite: `131 passed`
- WSL analysis/inventory/postrun suite: `74 passed`
- WSL rendered brief for the current CVRP prepared root shows
  `Case-protection requirements`, protected cases `CMT2, CMT4`, the
  target-intent/hypothesis evidence requirement, and
  `cvrp_cmt_case_protection_handoff=true` in the handoff table.
