# Launch Readiness Login Actionability Repair

Date: 2026-06-18

## Purpose

Make the current `gpt-5.5` launch blocker directly actionable from the
prepared-root readiness report. The previous readiness check correctly refused
launch on a real completion-preflight failure, but it did not request the proxy
login URL and therefore could leave the operator with only a `401`
classification.

## Change

`scion/tools/check_launch_readiness.py` now invokes
`check_gpt55_proxy.py --login-url-on-failure --json` for the optional real
completion preflight.

When the proxy returns a failure classification, readiness JSON preserves the
raw proxy detail and adds an `operator_action` object with:

- failure classification,
- model and base URL,
- next-step guidance for auth, account-pool, rate-limit, or transport failures,
- login URL when the proxy provides one,
- the rerun command that must pass before launch.

Markdown rendering adds a concise `Completion Preflight Action` section when
that action is available.

## Boundary Check

This is a report-only launch-readiness repair. It does not mutate campaign
state, scheduler state, promotion state, `DecisionFeatures`, Protocol evidence,
budgets, gates, lifecycle policy, or problem semantics.

## Verification

Focused local verification:

```bash
python -m py_compile \
  scion/tools/check_launch_readiness.py \
  scion/tools/check_gpt55_proxy.py

PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion pytest -q \
  scion/scion/tests/test_launch_readiness.py \
  scion/scion/tests/test_gpt55_proxy_check.py
```

Result: `12 passed`.

Prepared-root related suite:

```bash
PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion pytest -q \
  scion/scion/tests/test_cvrp_agentic_launcher.py \
  scion/scion/tests/test_warehouse_agentic_launcher.py \
  scion/scion/tests/test_postrun_artifact_inventory.py \
  scion/scion/tests/test_rebuild_postrun_acceptance.py \
  scion/scion/tests/test_launch_readiness.py
```

Result: `38 passed`.

Live local-mirror readiness check:

```bash
PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion \
python scion/tools/check_launch_readiness.py \
  /home/clawd/research/scion-experiments/v04-cvrp-postpivot-resume-ready-focushandoff-1r-gpt55-20260618T141926Z-claw \
  --completion-preflight \
  --timeout-sec 20 \
  --format json
```

Result: exit `64`, `static_ready=true`, `launch_ready=false`,
`classification=auth_token_invalidated`, and `operator_action.login_url`
present. The route remains blocked until re-login/token refresh and a passing
real completion preflight.

WSL target-root readiness check after syncing commit `dd50175`:

```bash
ssh -i /home/clawd/.ssh/id_ed25519_codex_wsl -p 2222 \
  xjy-ubuntu@127.0.0.1 \
  'cd /home/xjy-ubuntu/research/or-autoresearch-agent && \
   PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion \
   /home/xjy-ubuntu/miniconda3/envs/scion/bin/python \
   scion/tools/check_launch_readiness.py \
   /home/xjy-ubuntu/research/scion-experiments/v04-cvrp-postpivot-resume-ready-focushandoff-1r-gpt55-20260618T141926Z-claw \
   --completion-preflight --timeout-sec 20 --format json'
```

Result: exit `64`, `static_ready=true`, `launch_ready=false`,
`classification=not_authenticated`, and `operator_action.login_url` present.

## Operator Rule

Before launching a prepared root, rerun:

```bash
scion/tools/check_launch_readiness.py <prepared-root> \
  --completion-preflight \
  --format json
```

Launch only when `launch_ready=true`. If completion preflight fails, follow the
report's `operator_action` and rerun readiness after the proxy login or account
pool is healthy.
