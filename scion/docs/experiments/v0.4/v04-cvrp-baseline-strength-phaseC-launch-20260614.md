# CVRP Baseline-Strength Phase C Launch

Status: launched, not complete.

This launch executes the pre-registered Phase C long-run follow-up:
[`../../planning/v0.4/v0.4-cvrp-baseline-strength-phaseC-longrun-20260614.md`](../../planning/v0.4/v0.4-cvrp-baseline-strength-phaseC-longrun-20260614.md).

## Launch Inputs

- Accepted launcher commit: `354a941b9b5c4b86e0370d8a932f311a5c01311c`
- Experiment root:
  `/home/clawd/research/scion-experiments/v04-cvrp-baseline-strength-phaseC-longrun-20260614T174532Z`
- WSL root:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-baseline-strength-phaseC-longrun-20260614T174532Z`
- External handoff/status:
  `/home/clawd/research/scion-experiments/v04-cvrp-baseline-strength-phaseC-longrun-20260614T174532Z/status/phaseC_status.md`
- Protocol snapshot:
  `/home/clawd/research/scion-experiments/v04-cvrp-baseline-strength-phaseC-longrun-20260614T174532Z/config/protocol.yaml`
- Split snapshot:
  `/home/clawd/research/scion-experiments/v04-cvrp-baseline-strength-phaseC-longrun-20260614T174532Z/config/split_manifest.yaml`
- Seed snapshot:
  `/home/clawd/research/scion-experiments/v04-cvrp-baseline-strength-phaseC-longrun-20260614T174532Z/config/seed_ledger.yaml`

Config checksums:

```text
63369af827da84c3657515537334517e36d914e163758f5e22dba4c3542f4c64  config/protocol.yaml
13d941ad06d6483c88dfa26370aec1e90300ac6b892c9f74e3353a1159094c3c  config/split_manifest.yaml
3e0625ff18ba53ba6aa267ee5a69325341d4f9eec6a5874f1ac6355c2ce78923  config/seed_ledger.yaml
```

The protocol snapshot preserves the accepted Phase A 8-case/8-seed sampling
and adds the repaired CVRP staged-gate block from the current formal protocol.

## Matrix

- Server runner PID: `2121897`
- WSL runner PID: `64429`
- Server first accepted cell:
  `/home/clawd/research/scion-experiments/v04-cvrp-baseline-strength-phaseC-longrun-20260614T174532Z/cells/v04-cvrp-phaseC-rep01-alns-vns-16r-16r-gpt55-20260614T175545Z-claw`
- WSL first accepted cell:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-baseline-strength-phaseC-longrun-20260614T174532Z/cells/v04-cvrp-phaseC-wsl-rep02-alns-vns-16r-16r-gpt55-20260614T175551Z-claw`

Planned order:

1. Server: `rep01/alns_vns`, then `rep01/alns_only`.
2. WSL: `rep02/alns_vns`, `rep02/alns_only`, `rep03/alns_vns`, then
   `rep03/alns_only`.

Both runners launch one cell at a time and wait for `run_status.json` to report
`status=finished` before launching the next cell.

## Launch Evidence

Accepted cells launch with:

- `GIT_COMMIT=354a941`
- `ROUNDS=16`
- `MEASUREMENT_GOVERNANCE=on`
- `PROPOSAL_CONTEXT_ABLATION=compact-measurement-diagnostics`
- `SCION_STAGE_TRANSITION_DRAIN_LIMIT=4`
- `CONTROL_PAIR_KEY=cvrp.baseline-strength.phaseC:<repeat>`

Python paths:

- Server: `PY=/home/clawd/miniconda3/envs/claw/bin/python`
- WSL: `PY=/home/xjy-ubuntu/miniconda3/envs/scion/bin/python`

## Launch Repairs And Exclusions

Two launch-wrapper attempts are excluded from accepted Phase C cells:

- Initial WSL attempt exited immediately with wrapper exit `127` because the
  launcher defaulted to the server Python path on WSL. It is archived under the
  WSL root's `failed_launch_archive/`.
- A short-lived server `cf2e9ae` cell was terminated and moved to
  `superseded_launch_archive/` so accepted cells use one launcher commit.

The portable launcher fix is commit `354a941`. It adds `--python` to
`launch_cvrp_agentic_campaign.py` and focused launcher tests passed with
`7 passed`; `py_compile` and `git diff --check` passed.

## Monitoring

Server:

```bash
ROOT=/home/clawd/research/scion-experiments/v04-cvrp-baseline-strength-phaseC-longrun-20260614T174532Z
cat "$ROOT/status/server_rep01_runner.log"
find "$ROOT/cells" -maxdepth 2 -name run_status.json -print -exec cat {} \;
```

WSL through reverse SSH:

```bash
ssh -i /home/clawd/.ssh/id_ed25519_codex_wsl -p 2222 xjy-ubuntu@127.0.0.1 \
  'ROOT=/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-baseline-strength-phaseC-longrun-20260614T174532Z; cat "$ROOT/status/wsl_rep02_rep03_runner.log"; find "$ROOT/cells" -maxdepth 2 -name run_status.json -print -exec cat {} \;'
```

Postrun analysis must wait until all accepted cells are complete and WSL results
are synced back to the server root.

## Postrun Tooling

Prepared external scripts:

- `/home/clawd/research/scion-experiments/v04-cvrp-baseline-strength-phaseC-longrun-20260614T174532Z/scripts/sync_wsl_back.sh`
- `/home/clawd/research/scion-experiments/v04-cvrp-baseline-strength-phaseC-longrun-20260614T174532Z/scripts/run_phaseC_postrun_reports.sh`

Completion sequence:

1. Wait for all accepted cells to finish.
2. Run `scripts/sync_wsl_back.sh` from the server root.
3. Run `scripts/run_phaseC_postrun_reports.sh` from the server root.
4. Inspect `postrun_acceptance/accepted_cells.tsv`,
   `postrun_acceptance/sql/reach_drain.csv`,
   `postrun_acceptance/sql/wlt_mde_rows.csv`,
   `postrun_acceptance/sql/branch_depth.csv`, and
   `postrun_acceptance/sql/prompt_context.csv`.

The postrun script gates on exactly six accepted cells, records excluded
wrapper/superseded archives, emits standard Scion reports, artifact inventory,
per-repeat trajectory compares, and keeps MDE/BKS/gap, prompt/context,
branch-depth, same-mechanism-chain, and cross-arm comparisons as postrun-only
diagnostics.
