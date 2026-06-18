# v0.4 CVRP Handoff Coverage Repair

Date: 2026-06-18

## Purpose

TASK Phase 4 requires CVRP follow-up runs to judge solver research against A/A
MDE, low-SNR trajectory-divergent semantics, default-avoid mechanisms, and
direct objective-effect attribution for route-merge or construction-seed
directions. The CVRP launcher already writes this problem-owned handoff into
the prepared manifest, but artifact inventories and analysis briefs did not
surface it as CVRP-specific Phase 4 coverage.

## Change

- Prepared CVRP contracts now require:
  - MDE/practical-delta and low-SNR reason-code handoff;
  - measurable opportunity classes for construction seed portfolios,
    destroy/repair selection, bounded local-search variants, and
    acceptance/adaptive weighting;
  - default-avoid coverage for the currently rejected CVRP directions;
  - direct-effect rules for route-merge and construction-seed mechanisms;
  - an explicit decision-boundary note keeping the handoff out of
    `DecisionFeatures`, Protocol gates, promotion input, and scheduler state.
- Phase 4 artifact inventories and analysis briefs now include CVRP
  `problem_specific_requirements` for the same handoff coverage.
- The generic Phase 4 table remains problem-neutral; CVRP-only requirements are
  separated from warehouse-only requirements.

## Boundary Check

- CVRP semantics stay in prepared manifests and report-only delegated analysis
  surfaces.
- This does not change CVRP solver behavior, Decision, `DecisionFeatures`,
  Protocol gates, lifecycle, scheduling, promotion, or proposal selection.
- Raw BKS, case gaps, case hardness, mechanism rankings, and LLM text remain
  outside deterministic Decision input.

## Verification

```bash
PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion pytest -q \
  scion/scion/tests/test_postrun_artifact_inventory.py \
  scion/scion/tests/test_cvrp_agentic_launcher.py \
  scion/scion/tests/test_postrun_analysis_brief.py
# 29 passed

PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion pytest -q \
  scion/scion/tests/test_postrun_artifact_inventory.py \
  scion/scion/tests/test_postrun_analysis_brief.py \
  scion/scion/tests/test_launch_readiness.py \
  scion/scion/tests/test_cvrp_agentic_launcher.py \
  scion/scion/tests/test_warehouse_agentic_launcher.py \
  scion/scion/tests/test_rebuild_postrun_acceptance.py \
  scion/scion/tests/test_proposal_trajectory_artifacts.py
# 66 passed

ssh -i /home/clawd/.ssh/id_ed25519_codex_wsl -p 2222 \
  xjy-ubuntu@127.0.0.1 'cd /home/xjy-ubuntu/research/or-autoresearch-agent && \
  PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion \
  /home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m pytest -q \
  scion/scion/tests/test_postrun_artifact_inventory.py \
  scion/scion/tests/test_postrun_analysis_brief.py \
  scion/scion/tests/test_launch_readiness.py \
  scion/scion/tests/test_cvrp_agentic_launcher.py \
  scion/scion/tests/test_warehouse_agentic_launcher.py \
  scion/scion/tests/test_rebuild_postrun_acceptance.py \
  scion/scion/tests/test_proposal_trajectory_artifacts.py'
# 66 passed

PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion python -m py_compile \
  scion/tools/postrun_artifact_inventory.py \
  scion/scion/tests/test_postrun_artifact_inventory.py \
  scion/scion/tests/test_cvrp_agentic_launcher.py \
  scion/scion/tests/test_launch_readiness.py
```

WSL launch-readiness and inventory checks under this repair:

- Current CVRP prepared root remains `ready=true`, `static_ready=true`,
  `launch_ready=false`, and `prepared_contract_complete=ok` for static
  readiness.
- All `cvrp_*` prepared-contract checks passed.
- All CVRP `problem_specific_requirements` are available.

## Acceptance

Accepted as a Phase 4 CVRP auditability repair. Once `gpt-5.5` launch auth is
restored, CVRP prepared roots can be checked for the problem-specific handoff
needed to judge whether the next branch is materially different, measurable,
and interpreted against A/A MDE rather than generic win-rate evidence alone.
