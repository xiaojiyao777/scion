# v0.4 Postrun Acceptance Readiness Checker

Date: 2026-06-19

## Purpose

Postrun delegated review now has an explicit report-only readiness artifact.
After a campaign exits, the launcher rebuilds the postrun acceptance bundle and
then writes:

- `postrun_acceptance/readiness/<stem>.postrun_acceptance_readiness.v1.json`
- `postrun_acceptance/readiness/<stem>.postrun_acceptance_readiness.md`

The readiness artifact answers whether delegated current-run analysis is ready.
It does not judge solver quality or mutate campaign, scheduler, promotion,
Protocol, Decision, `DecisionFeatures`, or problem solver behavior.

## Change

- Added `scion/tools/check_postrun_acceptance.py`.
- CVRP and warehouse launchers now generate the readiness JSON/Markdown after
  `rebuild_postrun_acceptance.py`.
- Launchers log both `POSTRUN_REPORTS_EXIT_STATUS` and
  `POSTRUN_READINESS_EXIT_STATUS`.
- `postrun_artifact_inventory.py` now counts the `readiness` report family and
  captures the readiness exit-status marker.
- Prepared-run manifests now declare `readiness` in
  `postrun_acceptance_families`, so static launch readiness can confirm the
  postrun report family contract before launch.

## Boundary

This is a reporting and delegated-analysis closure repair only.

- No broad budgets, truncation, prompt compression, or generic gate tightening
  were added.
- No `DecisionFeatures`, promotion, scheduler, Protocol gate, or solver
  semantics were changed.
- Warehouse and CVRP semantics remain in problem-owned handoff/report layers.

## Verification

Local checkout `69fe9b28`:

```bash
python -m py_compile \
  scion/tools/check_postrun_acceptance.py \
  scion/tools/launch_cvrp_agentic_campaign.py \
  scion/tools/launch_warehouse_agentic_campaign.py \
  scion/tools/postrun_artifact_inventory.py

PYTHONPATH=scion pytest -q \
  scion/scion/tests/test_check_postrun_acceptance.py \
  scion/scion/tests/test_postrun_analysis_brief.py \
  scion/scion/tests/test_postrun_artifact_inventory.py \
  scion/scion/tests/test_rebuild_postrun_acceptance.py \
  scion/scion/tests/test_rebuild_prepared_handoff.py \
  scion/scion/tests/test_launch_readiness.py \
  scion/scion/tests/test_cvrp_agentic_launcher.py \
  scion/scion/tests/test_warehouse_agentic_launcher.py
```

Result: `78 passed`.

WSL checkout `9a5d00c`:

```bash
PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion \
  /home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m pytest -q \
  scion/scion/tests/test_check_postrun_acceptance.py \
  scion/scion/tests/test_postrun_analysis_brief.py \
  scion/scion/tests/test_postrun_artifact_inventory.py \
  scion/scion/tests/test_rebuild_postrun_acceptance.py \
  scion/scion/tests/test_rebuild_prepared_handoff.py \
  scion/scion/tests/test_launch_readiness.py \
  scion/scion/tests/test_cvrp_agentic_launcher.py \
  scion/scion/tests/test_warehouse_agentic_launcher.py
```

Result: `78 passed`.

## Current Prepared Roots

New prepare-only roots were generated from WSL checkout `9a5d00c` because the
launcher `run.sh` template changed.

Warehouse:

`/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-v2-followup-ready-9a5d00c-6r-gpt55-20260619T023301Z-claw`

CVRP:

`/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-large-twoopt-bounded-ready-9a5d00c-1r-gpt55-20260619T023302Z-claw`

Strict launch readiness for both roots reports:

- `static_ready=true`
- `launch_ready=false`
- `postrun_families_complete=ok`
- `prepared_analysis_brief_current=ok`
- `prompt_context_readiness_complete=ok`
- `problem_specific_prepared_handoff=ok`
- `git_runtime_consistent=ok`
- `run.sh` contains `tools/check_postrun_acceptance.py`
- `run.sh` contains `POSTRUN_READINESS_EXIT_STATUS`

The remaining blocker is external `gpt-5.5` auth, not Scion static readiness:
completion preflight returns HTTP `401`, `classification=not_authenticated`,
`code=invalid_api_key`, with auth pool `active=0`, `total=1`.

Do not launch either prepared root until:

```bash
python scion/tools/check_launch_readiness.py <prepared-root> \
  --require-launch-ready --format json
```

reports `launch_ready=true`.
