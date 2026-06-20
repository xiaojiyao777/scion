# v0.4 Launch Readiness Runtime Guard Contract Consistency

Date: 2026-06-20

## Purpose

Close a launch-readiness gap between the prepared manifest and the wrapper that
actually starts a campaign. Before this repair, readiness checked that `run.sh`
contained executable runtime-guard commands and separately recomputed committed
drift for the manifest `runtime_guard_paths`, but it did not prove that the
effective `GIT_COMMIT` and `GIT_RUNTIME_GUARD_PATHS` consumed by `run.sh`
matched the prepared manifest.

## Change

- `scion/tools/check_launch_readiness.py`
  - Adds required check
    `run_script_runtime_guard_contract_consistency`.
  - Compares manifest `git.commit` and `git.runtime_guard_paths` against
    `launch.env`.
  - Detects executable pre-guard `run.sh` overrides and compares the effective
    wrapper values against the manifest.
  - Reports precise failures for launch-env mismatch, run-script mismatch, and
    effective-wrapper mismatch.
- `scion/scion/tests/test_launch_readiness.py`
  - Covers run-script `GIT_COMMIT` mismatch.
  - Covers run-script `GIT_RUNTIME_GUARD_PATHS` mismatch.
  - Covers launch-env `GIT_RUNTIME_GUARD_PATHS` mismatch.
  - Updates the fixture launch contract so `launch.env` mirrors real prepared
    roots for git guard fields.

## Verification

Local commit: `4cc9bc57`.

```text
python -m py_compile \
  scion/tools/check_launch_readiness.py \
  scion/scion/tests/test_launch_readiness.py
# passed
```

```text
PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion pytest -q \
  scion/scion/tests/test_launch_readiness.py
# 88 passed in 6.68s
```

```text
PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion pytest -q \
  scion/scion/tests/test_rebuild_prepared_handoff.py \
  scion/scion/tests/test_launch_readiness.py \
  scion/scion/tests/test_postrun_analysis_brief.py \
  scion/scion/tests/test_check_postrun_acceptance.py \
  scion/scion/tests/test_cli_report_research_efficiency.py
# 173 passed in 43.32s
```

WSL commit: `45cbec3a`.

```text
cd /home/xjy-ubuntu/research/or-autoresearch-agent
/home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m py_compile \
  scion/tools/check_launch_readiness.py \
  scion/scion/tests/test_launch_readiness.py
# passed
```

```text
PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion \
  /home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m pytest -q \
  scion/scion/tests/test_rebuild_prepared_handoff.py \
  scion/scion/tests/test_launch_readiness.py \
  scion/scion/tests/test_postrun_analysis_brief.py \
  scion/scion/tests/test_check_postrun_acceptance.py \
  scion/scion/tests/test_cli_report_research_efficiency.py
# 173 passed in 29.52s
```

## Current Prepared Roots

WSL runtime commit: `45cbec3a`.

Warehouse:

`/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-v2-followup-runguardcontract-45cbec3a-preflight-6r-gpt55-20260620T002429Z-claw`

Local mirror:

`/home/clawd/research/scion-experiments/v04-warehouse-v2-followup-runguardcontract-45cbec3a-preflight-6r-gpt55-20260620T002429Z-claw`

CVRP:

`/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-large-twoopt-phase4-runguardcontract-45cbec3a-preflight-4r-gpt55-20260620T002429Z-claw`

Local mirror:

`/home/clawd/research/scion-experiments/v04-cvrp-large-twoopt-phase4-runguardcontract-45cbec3a-preflight-4r-gpt55-20260620T002429Z-claw`

Strict launch readiness for both roots:

```text
static_ready=True
launch_ready=False
failed_required_checks=[completion_preflight]
failed_static_required_checks=[]
run_script_runtime_guard_contract_consistency=ok
git_runtime_guard_commit_consistent=ok
completion_preflight=failed
http_status=401
classification=not_authenticated
code=invalid_api_key
```

The readiness JSON is saved as `readiness.strict.json` in each prepared root.

## Boundary Check

- This is launch/readiness control-plane logic only.
- It does not change Decision, `DecisionFeatures`, Protocol gates, promotion,
  scheduler state, or solver semantics.
- The new check reads prepared manifest and wrapper files, and remains
  report-only/operator-facing.

## Acceptance

Accepted as a v0.4 launch-readiness repair. Active prepared roots were
refreshed from WSL runtime commit `45cbec3a`; launch remains blocked only by
external `gpt-5.5` completion auth.
