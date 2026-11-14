# v0.4 Warehouse Follow-Up Handoff Coverage Repair

Date: 2026-06-18

## Purpose

TASK Phase 4 requires warehouse follow-up runs to distinguish additional
continuous-improvement potential from a real post-v2 plateau, while explaining
fast completion through the warehouse runtime/problem model. The warehouse
launcher already writes this intent into the prepared manifest, but the generic
Phase 4 coverage table did not expose warehouse-specific handoff coverage.

## Change

- Prepared warehouse contracts now require the report-only research focus to
  carry:
  - champion-v2 checkpoint and plateau follow-up framing;
  - required evidence for promotion preservation, branch transfer,
    quality-blocked-vs-protocol-evaluated distinction, cost-vs-split telemetry,
    and fast-completion runtime explanation;
  - default-avoid directions for baseline restart, proposal-quality plateau
    misuse, fast-completion noise, split-only effect-zero interpretation, and
    broad matrix launch before focused follow-up analysis.
- Phase 4 artifact inventories and analysis briefs now include
  `problem_specific_requirements` for warehouse follow-up handoff coverage.
- The new coverage is report-only and does not change Decision,
  `DecisionFeatures`, Protocol gates, lifecycle, scheduler, promotion, proposal
  selection, or warehouse solver semantics.

## Boundary Check

- Warehouse follow-up semantics remain in the warehouse launcher/prepared
  manifest and delegated analysis surfaces.
- The generic Phase 4 coverage table remains problem-neutral.
- Warehouse-specific coverage is separated under
  `problem_specific_requirements` so CVRP roots are not judged against
  warehouse-only criteria.

## Verification

```bash
PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion pytest -q \
  scion/scion/tests/test_postrun_artifact_inventory.py \
  scion/scion/tests/test_postrun_analysis_brief.py \
  scion/scion/tests/test_warehouse_agentic_launcher.py
# 22 passed

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
  scion/tools/postrun_analysis_brief.py \
  scion/scion/tests/test_postrun_artifact_inventory.py \
  scion/scion/tests/test_warehouse_agentic_launcher.py
```

WSL launch-readiness and inventory checks under this repair:

- CVRP prepared root: `ready=true`, `static_ready=true`, `launch_ready=false`,
  `prepared_contract_complete=ok`; completion preflight skipped for this static
  check.
- Warehouse prepared root: `ready=true`, `static_ready=true`,
  `launch_ready=false`, `prepared_contract_complete=ok`; all
  `warehouse_followup_*` prepared-contract checks passed, and all warehouse
  `problem_specific_requirements` are available.

Later root status:

- The earlier warehouse identityguard root was superseded after runtime guard
  path changes.
- Current warehouse root:
  `/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-v2-followup-ready-35dd723-6r-gpt55-20260619T001002Z-claw`.
- Current root report:
  `scion/docs/experiments/v0.4/v04-warehouse-v2-followup-root-refresh-20260619.md`.

## Acceptance

Accepted as a Phase 4 warehouse auditability repair. Once `gpt-5.5` launch
auth is restored, the prepared warehouse v2 follow-up can be reviewed against a
problem-specific handoff checklist instead of inferring plateau readiness from
generic promotion or runtime counters alone.
