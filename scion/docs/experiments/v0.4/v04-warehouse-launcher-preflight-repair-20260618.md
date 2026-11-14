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
- `--resume-from-campaign` support that copies an existing campaign into the
  new run root before launch, so a follow-up can continue from a promoted
  champion such as warehouse `v2` instead of starting from the baseline;
- default postrun acceptance report generation under `postrun_acceptance/`
  after Scion exits, covering summary, failures, research-efficiency, and
  proposal-trajectory manifest artifacts while preserving the campaign's true
  wrapper exit code;
- `--skip-postrun-reports` for unusual smoke cases that should not generate
  postrun report artifacts;
- run-time git guard paths for warehouse-relevant source, warehouse data-root
  directory checks, and copied top-level `run_status.json` / `exit.txt`
  wrapper behavior. Runtime-path dirty changes or runtime-path commit drift
  fail before campaign startup; later docs-only status commits are allowed and
  logged. The runtime pathspec excludes `scion/scion/tests`, so test-only
  commits do not invalidate prepared run roots.
- pre-campaign wrapper failures for missing API-key environment variables and
  missing warehouse data roots write valid `run_status.json` without relying on
  the configured campaign Python executable.

The default mode is prepare-only. Passing `--launch` starts `run.sh` with
`nohup setsid`.

## Boundary

This is launch/reproducibility infrastructure only. It does not change
Decision, `DecisionFeatures`, Protocol, scheduling, gates, budgets, lifecycle
policy, proposal context, problem semantics, or warehouse operator guidance.

The config rewrite is problem-owned launch preparation for the warehouse
production split. It keeps warehouse path semantics outside generic Scion core.

Campaign resume uses existing Scion reopen semantics: the copied campaign keeps
its champion database rows and local `champions/champion_v*` snapshots. When
the campaign manager starts, the current champion is restored from the champion
store and re-anchored to the copied local snapshot if the hash matches.

The postrun reports are report-only artifacts. They read existing campaign
outputs after `scion run` exits and are allowed to fail closed into `run.log`
without changing the campaign exit status or mutating campaign state.

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

- `8 passed`
- `py_compile` passed
- `git diff --check` passed

The focused tests verify help output, prepare-only run-root generation,
warehouse config rewriting, secret-safe `--api-key-env`, completion preflight
wiring, resume-campaign copying, postrun report wiring, runtime-path git guard
wiring, valid pre-campaign failure status JSON, wrapper checks, and generated
shell syntax.

Additional local real-artifact smoke:

```bash
python scion/tools/launch_warehouse_agentic_campaign.py \
  --rounds 2 \
  --label smoke-warehouse-v2-resume \
  --experiments-root /tmp/scion-warehouse-launcher-smoke \
  --warehouse-data-root /home/clawd/research/scion-data \
  --resume-from-campaign /home/clawd/research/scion-experiments/v04-warehouse-validation-transfer-contract-rerun6r-ce5d884-20260617T152944Z/rep01/full_context/campaign
```

Result: prepare-only succeeded, copied `scion.db` and `champions/champion_v2`,
rewrote production split paths to `/home/clawd/research/scion-data`, and
generated a `bash -n` clean `run.sh`. No campaign was launched.

## Next Use

After restoring a real `gpt-5.5` route, prepare the warehouse follow-on check
from a clean synchronized commit, for example:

```bash
python scion/tools/launch_warehouse_agentic_campaign.py \
  --rounds 6 \
  --label v04-warehouse-v2-followup \
  --warehouse-data-root /home/xjy-ubuntu/research/scion-data \
  --resume-from-campaign /home/xjy-ubuntu/research/scion-experiments/v04-warehouse-validation-transfer-contract-rerun6r-ce5d884-20260617T152944Z/rep01/full_context/campaign \
  --completion-preflight
```

On WSL, run the tool from the synchronized checkout and keep
`PYTHONPATH` pointing at that checkout's `scion` package.
