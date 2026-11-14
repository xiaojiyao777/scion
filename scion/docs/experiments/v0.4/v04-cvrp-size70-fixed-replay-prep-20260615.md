# CVRP Size70 Fixed Replay Input Prep - 2026-06-15

## Purpose

Prepare the external full-file candidate artifact needed for the pre-registered
CVRP size70 two-opt fixed-candidate validation replay. This is input
preparation only. No CVRP validation replay was launched in this step because
the repaired warehouse short debug was actively running solver evaluations on
WSL.

The v3 boundary remains unchanged: this artifact is replay material for a
human-approved external candidate. It is not Decision input, promotion
evidence, or a Scion campaign mutation.

## Source Evidence

- Source run root:
  `/home/clawd/research/scion-experiments/v04-cvrp-twoopt-polish-followup-smoke-20260615T1848Z`
- Baseline workspace:
  `workspaces/baseline_alns_only`
- Candidate workspace:
  `workspaces/candidate_twoopt_size70`
- Prior patch:
  `patches/twoopt_size70.patch`
- Changed source file retained in the external full-file artifact:
  `policies/baseline_modules/scheduler.py`

Runtime artifacts such as `.prepared` and `__pycache__` were excluded.

## Prepared Artifacts

- External candidate artifact:
  `/home/clawd/research/scion-experiments/v04-cvrp-twoopt-polish-followup-smoke-20260615T1848Z/external_candidates/size70_twoopt_candidate.patch.json`
- Validation manifest:
  `/home/clawd/research/scion-experiments/v04-cvrp-twoopt-polish-followup-smoke-20260615T1848Z/fixed_replay/validation_manifest.v1.json`
- Materialization check root:
  `/home/clawd/research/scion-experiments/v04-cvrp-twoopt-polish-followup-smoke-20260615T1848Z/fixed_replay/materialization_check`

## Manifest Command

```bash
PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion \
python -m scion.cli.main report fixed-candidate-replay-manifest \
  --source /home/clawd/research/scion-experiments/v04-cvrp-twoopt-polish-followup-smoke-20260615T1848Z \
  --source-arm external_control \
  --comparison-id cvrp-size70-twoopt-validation-20260615 \
  --stage validation \
  --external-candidate-artifact /home/clawd/research/scion-experiments/v04-cvrp-twoopt-polish-followup-smoke-20260615T1848Z/external_candidates/size70_twoopt_candidate.patch.json \
  --output /home/clawd/research/scion-experiments/v04-cvrp-twoopt-polish-followup-smoke-20260615T1848Z/fixed_replay/validation_manifest.v1.json
```

Output:

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

## Materialization Check

The prepared artifact was checked by `materialize_candidate_workspace`.

- Materialized workspace:
  `/home/clawd/research/scion-experiments/v04-cvrp-twoopt-polish-followup-smoke-20260615T1848Z/fixed_replay/materialization_check/materialized/external-size70-twoopt-polish-20260615/on`
- Recreated file:
  `policies/baseline_modules/scheduler.py`
- Recreated file sha256:
  `1cdc55672fd14f357605fbb253186fef621864c4972dd1ddf73bec31a9c826ac`
- Result: materialized file equals
  `workspaces/candidate_twoopt_size70/policies/baseline_modules/scheduler.py`
  and differs from
  `workspaces/baseline_alns_only/policies/baseline_modules/scheduler.py`.

## Next Step

After the active warehouse debug frees WSL solver load, run the pre-registered
validation fixed replay. The replay is still a no-LLM mechanism-validity gate,
not promotion evidence.
