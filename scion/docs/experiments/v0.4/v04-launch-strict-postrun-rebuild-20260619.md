# Launch Strict Postrun Rebuild

Date: 2026-06-19

## Purpose

Warehouse and CVRP launch scripts now call
`rebuild_postrun_acceptance.py --strict` inside
`write_postrun_acceptance_reports`. Launch readiness also requires
`run_script_strict_postrun_rebuild=ok`, and verifies that the strict rebuild
command executes before the postrun readiness command.

Without `--strict`, an incomplete rebuild could record an incomplete rebuild
manifest while the wrapper still logged `POSTRUN_REPORTS_EXIT_STATUS:0`. If the
rebuild ran after readiness, the wrapper could also check stale postrun
artifacts before rebuilding the bundle. This repair keeps postrun bundle rebuild
status aligned with the rebuild manifest and makes the run script ordering
auditable.

This is launcher/reporting hygiene only. It does not change Decision,
`DecisionFeatures`, Protocol gates, promotion, scheduler state, or solver
behavior.

## Acceptance Evidence

- Both launchers add `--strict` to the executable
  `rebuild_postrun_acceptance.py` command.
- Launch readiness rejects missing, prefixed, or comment-only strict postrun
  rebuild paths and still requires `POSTRUN_REPORTS_EXIT_STATUS`.
- Launch readiness rejects run scripts where the strict rebuild command appears
  after the postrun readiness command, or where
  `POSTRUN_REPORTS_EXIT_STATUS` is emitted before the rebuild command.
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
the active prepared roots were regenerated from WSL runtime commit `7fd806e`:

- Warehouse:
  `/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-v2-followup-rebuildorder-7fd806e-6r-gpt55-6r-gpt55-20260619T152101Z-claw`
- CVRP:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-large-twoopt-rebuildorder-7fd806e-1r-gpt55-1r-gpt55-20260619T152101Z-claw`

Strict WSL launch readiness for both regenerated roots reports
`static_ready=true`, `run_script_strict_postrun_rebuild=ok`,
`run_script_strict_postrun_readiness=ok`, and `launch_ready=false`.
The strict rebuild order evidence is:

- Warehouse:
  `postrun_rebuild_command_position=1155`,
  `POSTRUN_REPORTS_EXIT_STATUS` position `1291`, and
  `postrun_acceptance_command_position=1443`.
- CVRP:
  `postrun_rebuild_command_position=1159`,
  `POSTRUN_REPORTS_EXIT_STATUS` position `1295`, and
  `postrun_acceptance_command_position=1447`.

The remaining blocker is the external `gpt-5.5` provider auth preflight
returning HTTP `401` / `classification=not_authenticated` /
`code=invalid_api_key`, with auth pool `active=0`, `expired=1`,
`refreshing=0`, `total=1`.
