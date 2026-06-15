# CVRP Size70 Fixed-Candidate Validation Launch - 2026-06-15

## Purpose

Launch the pre-registered Tier 2 fixed-candidate validation replay for the
size70 two-opt polish mechanism after Tier 1 Large-X completion diagnostic
passed.

This is no-LLM/no-APS mechanism-validity replay. It is not a Scion campaign,
not promotion evidence, and not `DecisionFeatures` input. Formal promotion
evidence still requires validation/frozen interpretation through the intended
Protocol path.

## Inputs

- Tier 1 postrun:
  `scion/docs/experiments/v0.4/v04-cvrp-size70-tier1-largeX-postrun-20260615.md`
- Validation design:
  `scion/docs/planning/v0.4/v04-cvrp-size70-fixed-candidate-validation-design-20260615.md`
- Original server manifest:
  `/home/clawd/research/scion-experiments/v04-cvrp-twoopt-polish-followup-smoke-20260615T1848Z/fixed_replay/validation_manifest.v1.json`
- WSL manifest:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-twoopt-polish-followup-smoke-20260615T1848Z/fixed_replay/validation_manifest.v1.json`
- WSL external candidate artifact:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-twoopt-polish-followup-smoke-20260615T1848Z/external_candidates/size70_twoopt_candidate.patch.json`

## WSL Prep

WSL repo was fast-forwarded to commit `2e0db05`.

The external candidate artifact was synced to WSL, then the validation manifest
was rebuilt on WSL so `artifact_ref` uses WSL-local absolute paths.

Manifest rebuild output:

```json
{
  "candidate_count": 1,
  "external_candidate_artifact_count": 1,
  "filtered_out_row_count": 0,
  "omitted_row_count": 0,
  "schema_version": "scion.fixed_candidate_replay_manifest.v1",
  "stage_filter": ["validation"]
}
```

Materialization check passed on WSL:

- materialized workspace:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-twoopt-polish-followup-smoke-20260615T1848Z/fixed_replay/materialization_check_wsl/materialized/external-size70-twoopt-polish-20260615/on`
- recreated file:
  `policies/baseline_modules/scheduler.py`
- sha256:
  `1cdc55672fd14f357605fbb253186fef621864c4972dd1ddf73bec31a9c826ac`
- result: materialized source matches `candidate_twoopt_size70` and differs
  from `baseline_alns_only`.

## Initial Run

- WSL root:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-size70-fixed-validation-20260615T223636Z`
- Server sync root:
  `/home/clawd/research/scion-experiments/v04-cvrp-size70-fixed-validation-20260615T223636Z`
- Tmux session:
  `scion_cvrp_size70_validation_223636`
- Started:
  `2026-06-15T22:36:36Z`
- Wrapper:
  `timeout 8h`
- Candidate count:
  `1`
- Replay arms:
  `on`, `record_only`
- Replay stage:
  `validation`
- LLM/APS:
  none

The run intentionally does not pass `--time-limit-sec`; validation uses the
formal CVRP protocol runtime policy:

- dimensions `<=100`: `30s`
- dimensions `101-149`: `45s`
- dimensions `150-250`: `60s`
- dimensions `>=251`: `90s`

## Command

```bash
cd /home/xjy-ubuntu/research/or-autoresearch-agent
export PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion
export SCION_PROBLEM_DATA_ROOT=/home/xjy-ubuntu/research/or-autoresearch-agent/vrp

/home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m scion.cli.main \
  report fixed-candidate-replay \
  --manifest /home/xjy-ubuntu/research/scion-experiments/v04-cvrp-twoopt-polish-followup-smoke-20260615T1848Z/fixed_replay/validation_manifest.v1.json \
  --problem /home/xjy-ubuntu/research/or-autoresearch-agent/scion/scion/problems/cvrp/problem-v1.yaml \
  --protocol /home/xjy-ubuntu/research/or-autoresearch-agent/scion/scion/problems/cvrp/formal/protocol.yaml \
  --split /home/xjy-ubuntu/research/or-autoresearch-agent/scion/scion/problems/cvrp/formal/split_manifest.yaml \
  --seeds /home/xjy-ubuntu/research/or-autoresearch-agent/scion/scion/problems/cvrp/formal/seed_ledger.yaml \
  --output-dir /home/xjy-ubuntu/research/scion-experiments/v04-cvrp-size70-fixed-validation-20260615T223636Z \
  --output /home/xjy-ubuntu/research/scion-experiments/v04-cvrp-size70-fixed-validation-20260615T223636Z/fixed_candidate_replay_comparison.v1.json
```

## Initial Health

Initial health check after launch:

- tmux session exists;
- `run_fixed_validation.sh`, `stdout.log`, and `stderr.log` exist;
- no stderr output yet;
- no comparison artifact yet.

## Immediate Pre-Protocol Failure

The initial run completed quickly with `error_count=2`. Both replay arms failed
before canary or validation metrics with the same strict case-path error:

`Unsafe case path in strict ExperimentProtocol: 'cvrplib/A/A-n60-k9.vrp' status=unresolved_relative reason=relative case path did not resolve under workspace or safe_data_roots`

This is configuration evidence, not mechanism evidence. Root cause: the fixed
replay CLI was passed the formal split manifest directly, whose
`safe_data_roots` did not include the WSL CVRP data root. The environment
variable `SCION_PROBLEM_DATA_ROOT` reaches solver subprocesses, but strict
`ExperimentProtocol` case-path resolution uses `SplitManifest.safe_data_roots`
before subprocess launch.

Initial comparison artifact:

`/home/clawd/research/scion-experiments/v04-cvrp-size70-fixed-validation-20260615T223636Z/fixed_candidate_replay_comparison.v1.json`

## Repaired Relaunch

An experiment-local split manifest was generated on WSL with the same formal
case sets plus:

```yaml
safe_data_roots:
  - /home/xjy-ubuntu/research/or-autoresearch-agent/vrp
```

Repaired WSL root:

`/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-size70-fixed-validation-rerun-20260615T224151Z`

Repaired server sync root:

`/home/clawd/research/scion-experiments/v04-cvrp-size70-fixed-validation-rerun-20260615T224151Z`

Repaired tmux session:

`scion_cvrp_size70_validation_rerun_224151`

Repaired command changes only `--split`:

```bash
--split /home/xjy-ubuntu/research/scion-experiments/v04-cvrp-size70-fixed-validation-rerun-20260615T224151Z/inputs/split_manifest.validation_wsl.yaml
```

Initial repaired health check:

- tmux session exists;
- materialized `on` workspace exists;
- `stdout.log` and `stderr.log` are empty so far;
- no immediate unsafe-case-path error.

## Postrun Requirements

Postrun must check:

- distinguish the invalid first attempt from the repaired replay;
- comparison schema and row status for both replay arms;
- canary status for each arm;
- raw validation metric rows, not only the top-level two-row comparison;
- candidate/champion completed pairs, W/L/T, median delta, bootstrap/gate
  outcome, route count, fleet violation, and runtime errors;
- eligible `customer_count >= 70` two-opt activation and ineligible tie/zero
  activation behavior;
- whether validation passes sufficiently to launch frozen fixed replay.

Any positive result remains fixed-candidate mechanism-validity material until
frozen and Scion Protocol interpretation are complete.
