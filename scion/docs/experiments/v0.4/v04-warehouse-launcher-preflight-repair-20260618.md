# Warehouse Launcher Preflight Repair

Date: 2026-06-18

## Purpose

Prepare the next warehouse continuous-improvement check without launching a
campaign while the `gpt-5.5` route is unavailable. The previous accepted
warehouse WSL run depended on a hand-written `run_wsl.sh` that copied and
rewrote production config paths for WSL. That worked, but it was too easy to
lose or mis-copy when resuming from a clean commit.

## Change

Added `scion/tools/launch_warehouse_agentic_campaign.py`.

The launcher prepares a run root with:

- copied `problem.yaml`, `problem-v1.yaml`, `protocol_prod.yaml`,
  `split_manifest_prod.yaml`, and `seed_ledger.yaml`;
- production warehouse case paths and safe roots rewritten to
  `--warehouse-data-root`;
- `root_dir` and canary paths rewritten to the current repo checkout;
- `launch.env` written with mode `0600`;
- `--api-key-env` support so non-local credentials do not get written to disk;
- `--completion-preflight` support using a real chat completion before Scion
  starts;
- a run-time git commit check, warehouse data-root directory check, and copied
  top-level `run_status.json` / `exit.txt` wrapper behavior.

The default mode is prepare-only. Passing `--launch` starts `run.sh` with
`nohup setsid`.

## Boundary

This is launch/reproducibility infrastructure only. It does not change
Decision, `DecisionFeatures`, Protocol, scheduling, gates, budgets, lifecycle
policy, proposal context, problem semantics, or warehouse operator guidance.

The config rewrite is problem-owned launch preparation for the warehouse
production split. It keeps warehouse path semantics outside generic Scion core.

## Current LLM Route Probe

No warehouse campaign was launched. A local and WSL probe of
`http://127.0.0.1:8080/v1/chat/completions` with model `gpt-5.5` still returns
HTTP `401` because the upstream Codex OAuth token is invalidated.

## Acceptance

Commands:

```bash
PYTHONPATH=scion pytest -q scion/scion/tests/test_warehouse_agentic_launcher.py
python -m py_compile scion/tools/launch_warehouse_agentic_campaign.py scion/scion/tests/test_warehouse_agentic_launcher.py
git diff --check
```

Result:

- `4 passed`
- `py_compile` passed
- `git diff --check` passed

The focused tests verify help output, prepare-only run-root generation,
warehouse config rewriting, secret-safe `--api-key-env`, completion preflight
wiring, wrapper checks, and generated shell syntax.

## Next Use

After restoring a real `gpt-5.5` route, prepare the warehouse follow-on check
from a clean synchronized commit, for example:

```bash
python scion/tools/launch_warehouse_agentic_campaign.py \
  --rounds 6 \
  --label v04-warehouse-v2-followup \
  --warehouse-data-root /home/xjy-ubuntu/research/scion-data \
  --completion-preflight
```

On WSL, run the tool from the synchronized checkout and keep
`PYTHONPATH` pointing at that checkout's `scion` package.
