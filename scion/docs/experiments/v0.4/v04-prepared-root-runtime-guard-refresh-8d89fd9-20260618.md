# v0.4 Prepared Root Runtime Guard Refresh 8d89fd9

Date: 2026-06-18

## Purpose

The prompt signal-density coverage repair changed `scion/tools`, which is a
runtime guard path for prepared launch roots. The previous `7308544` prepared
roots remained unstarted, but they were no longer aligned to the current guarded
tooling. New prepare-only roots were generated from checkout `8d89fd9` without
launching a campaign.

## Current Launch Targets

CVRP:

`/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-postpivot-resume-ready-signaldensity-8d89fd9-1r-gpt55-20260618T194900Z-claw`

Warehouse:

`/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-v2-followup-ready-signaldensity-8d89fd9-6r-gpt55-20260618T194900Z-claw`

Both roots are prepare-only and remain unstarted.

Two same-commit roots were briefly generated with shorter labels lacking the
`v04-cvrp` / `v04-warehouse` prefix. They are not the current launch targets;
use only the two `v04-*signaldensity*` roots above.

## Verification

WSL checkout:

```text
8d89fd9
```

WSL postrun-acceptance regression sweep:

```bash
PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion \
  /home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m pytest -q \
  scion/scion/tests/test_postrun_artifact_inventory.py \
  scion/scion/tests/test_postrun_analysis_brief.py \
  scion/scion/tests/test_rebuild_postrun_acceptance.py
```

Result: `17 passed in 1.29s`.

Prepared handoff checks for both current roots:

- `prepared_run_manifest.git.commit=8d89fd9`
- `prepared_run_contract.contract_complete=true`
- `phase4_evidence_coverage.current_run_evidence=false`
- `phase4_evidence_coverage.requirements.prompt_signal_density` is present and
  unavailable with the expected `not current-run evidence` reason.

Static launch readiness for both current roots:

- `static_ready=true`
- `ready=true`
- `launch_ready=false`
- `git_runtime_consistent=ok`
- `prepared_contract_complete=ok`
- `not_already_started=ok`

Strict launch readiness for both current roots:

- exit `64`
- `static_ready=true`
- `launch_ready=false`
- completion preflight `failed`
- classification `not_authenticated`
- HTTP `401`

Launch remains blocked until the strict command returns `launch_ready=true`:

```bash
scion/tools/check_launch_readiness.py <prepared-root> \
  --require-launch-ready \
  --format json
```

## Acceptance

Accepted as the current prepared-root refresh after the R4 prompt
signal-density coverage repair. The current roots are aligned to guarded source
`8d89fd9`; the only current launch blocker is external `gpt-5.5` auth.
