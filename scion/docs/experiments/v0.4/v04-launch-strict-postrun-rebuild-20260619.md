# Launch Strict Postrun Rebuild

Date: 2026-06-19

## Purpose

Warehouse and CVRP launch scripts now call
`rebuild_postrun_acceptance.py --strict` inside
`write_postrun_acceptance_reports`. Launch readiness also requires
`run_script_strict_postrun_rebuild=ok`.

Without `--strict`, an incomplete rebuild could record an incomplete rebuild
manifest while the wrapper still logged `POSTRUN_REPORTS_EXIT_STATUS:0`. The
later delegated-readiness check would fail, but the rebuild status marker would
be misleading. This repair keeps postrun bundle rebuild status aligned with the
rebuild manifest.

This is launcher/reporting hygiene only. It does not change Decision,
`DecisionFeatures`, Protocol gates, promotion, scheduler state, or solver
behavior.

## Acceptance Evidence

- Both launchers add `--strict` to the executable
  `rebuild_postrun_acceptance.py` command.
- Launch readiness rejects missing, prefixed, or comment-only strict postrun
  rebuild paths and still requires `POSTRUN_REPORTS_EXIT_STATUS`.
- Local:
  - `python -m py_compile scion/tools/launch_cvrp_agentic_campaign.py scion/tools/launch_warehouse_agentic_campaign.py scion/tools/check_launch_readiness.py scion/scion/tests/test_launch_readiness.py scion/scion/tests/test_warehouse_agentic_launcher.py scion/scion/tests/test_cvrp_agentic_launcher.py`
  - `PYTHONPATH=scion pytest -q scion/scion/tests/test_launch_readiness.py scion/scion/tests/test_warehouse_agentic_launcher.py scion/scion/tests/test_cvrp_agentic_launcher.py`
  - `PYTHONPATH=scion pytest -q scion/scion/tests/test_launch_readiness.py scion/scion/tests/test_warehouse_agentic_launcher.py scion/scion/tests/test_cvrp_agentic_launcher.py scion/scion/tests/test_rebuild_postrun_acceptance.py scion/scion/tests/test_check_postrun_acceptance.py`
  - `git diff --check`
- WSL:
  - `/home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m py_compile scion/tools/launch_cvrp_agentic_campaign.py scion/tools/launch_warehouse_agentic_campaign.py scion/tools/check_launch_readiness.py scion/scion/tests/test_launch_readiness.py scion/scion/tests/test_warehouse_agentic_launcher.py scion/scion/tests/test_cvrp_agentic_launcher.py`
  - `PYTHONPATH=scion /home/xjy-ubuntu/miniconda3/envs/scion/bin/pytest -q scion/scion/tests/test_launch_readiness.py scion/scion/tests/test_warehouse_agentic_launcher.py scion/scion/tests/test_cvrp_agentic_launcher.py`
  - `PYTHONPATH=scion /home/xjy-ubuntu/miniconda3/envs/scion/bin/pytest -q scion/scion/tests/test_launch_readiness.py scion/scion/tests/test_warehouse_agentic_launcher.py scion/scion/tests/test_cvrp_agentic_launcher.py scion/scion/tests/test_rebuild_postrun_acceptance.py scion/scion/tests/test_check_postrun_acceptance.py`
  - `git diff --check`

## Result

Accepted as launch/postrun audit hardening. Because this touches `scion/tools`,
the active prepared roots were regenerated from WSL runtime commit `4c6edac`:

- Warehouse:
  `/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-v2-followup-strictrebuild-4c6edac-6r-gpt55-6r-gpt55-20260619T151356Z-claw`
- CVRP:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-large-twoopt-strictrebuild-4c6edac-1r-gpt55-1r-gpt55-20260619T151356Z-claw`

Strict WSL launch readiness for both regenerated roots reports
`static_ready=true`, `run_script_strict_postrun_rebuild=ok`,
`run_script_strict_postrun_readiness=ok`, and `launch_ready=false`.
The remaining blocker is the external `gpt-5.5` provider auth preflight
returning HTTP `401` / `classification=not_authenticated` /
`code=invalid_api_key`, with auth pool `active=0`, `expired=0`,
`refreshing=1`, `total=1`.
