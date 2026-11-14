# v0.4 Proposal Headroom Launcher Repair

Date: 2026-06-19

## Purpose

Focused warehouse and CVRP prepared roots were still relying on the core
proposal-quality fallback `rounds + max(6, rounds * 2)`. For the current
1-round CVRP follow-up, that meant only seven user-visible quality-blocked
proposal attempts before campaign termination, which could stop the research
loop before a useful protocol-evaluated solver hypothesis existed.

This repair keeps the core safety fallback intact but makes the focused v0.4
warehouse/CVRP launchers pass explicit proposal headroom into `scion run`.
Launch readiness now also enforces that prepared roots carry this headroom all
the way through `launch.env`, manifest execution, manifest command, and
`run.sh`, and that guarded runtime paths are clean before launch.

## Repair

- `scion/tools/launch_warehouse_agentic_campaign.py`
- `scion/tools/launch_cvrp_agentic_campaign.py`

Both launchers now default to:

- `--proposal-attempt-limit 64`
- `--proposal-quality-loop-limit 64`

The values are written into `launch.env`, `command.txt`, generated `run.sh`,
`run_status.json`, and `prepared_run_manifest.v1.json`. They can still be
overridden per prepared root with launcher CLI flags.

## Verification

Local:

```bash
python -m py_compile scion/tools/launch_cvrp_agentic_campaign.py scion/tools/launch_warehouse_agentic_campaign.py scion/scion/tests/test_cvrp_agentic_launcher.py scion/scion/tests/test_warehouse_agentic_launcher.py
PYTHONPATH=scion pytest -q scion/scion/tests/test_cvrp_agentic_launcher.py scion/scion/tests/test_warehouse_agentic_launcher.py
PYTHONPATH=scion pytest -q scion/scion/tests/test_cli_run_options.py scion/scion/tests/unit/core/test_retry_round_accounting_campaign_loop.py
```

Result: launcher tests `23 passed`; core CLI/retry tests `58 passed`.

WSL:

```bash
PYTHONPATH=scion /home/xjy-ubuntu/miniconda3/envs/scion/bin/pytest -q scion/scion/tests/test_cvrp_agentic_launcher.py scion/scion/tests/test_warehouse_agentic_launcher.py scion/scion/tests/test_cli_run_options.py scion/scion/tests/unit/core/test_retry_round_accounting_campaign_loop.py
```

Result: `81 passed`.

Follow-up readiness-contract verification:

```bash
python -m py_compile scion/tools/check_launch_readiness.py scion/scion/tests/test_launch_readiness.py
PYTHONPATH=scion pytest -q scion/scion/tests/test_launch_readiness.py scion/scion/tests/test_cvrp_agentic_launcher.py scion/scion/tests/test_warehouse_agentic_launcher.py
PYTHONPATH=scion /home/xjy-ubuntu/miniconda3/envs/scion/bin/pytest -q scion/scion/tests/test_launch_readiness.py scion/scion/tests/test_cvrp_agentic_launcher.py scion/scion/tests/test_warehouse_agentic_launcher.py
```

Result: local `97 passed`; WSL `97 passed`.

## Current Prepared Roots

Generated from WSL runtime commit `12fa3626`:

- Warehouse:
  `/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-v2-followup-headroomguard-12fa3626-6r-gpt55-20260619T180233Z-claw`
- CVRP:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-large-twoopt-headroomguard-12fa3626-1r-gpt55-20260619T180233Z-claw`

Both prepared manifests record `proposal_attempt_limit=64` and
`proposal_quality_loop_limit=64`.

Strict WSL launch readiness with real completion preflight reports
`static_ready=true`, `launch_ready=false`, exit `64` for both roots. The
static contract includes `git_runtime_worktree_clean=ok` and
`run_script_proposal_headroom_enforced=ok`. The remaining blocker is external
`gpt-5.5` provider auth, not Scion static readiness: chat completion preflight
returns HTTP `401`,
`classification=not_authenticated`, `code=invalid_api_key`, with auth pool
`active=0`, `expired=1`, `total=1`.
