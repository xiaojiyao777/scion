# Warehouse 1-Candidate Lifecycle Debug Design - 2026-06-15

## Purpose

The aborted warehouse 3x24R longrun produced no Protocol rows, so it cannot be
used to judge warehouse research quality. This design defines the next minimal
empirical gate: one warehouse candidate must pass through proposal/code,
Contract, Verification, and Protocol far enough to produce
`protocol_metric_results > 0`.

This is a lifecycle/debug gate, not a promotion run and not a governance on/off
experiment.

## V3 Boundary

Warehouse objective semantics, runtime configuration, problem paths, split
manifests, seeds, and case ownership remain problem-owned through
`problem.yaml`, sibling `problem-v1.yaml`, `protocol_prod.yaml`, and
`split_manifest_prod.yaml`.

Raw diagnostics from preflight, verification, patch protocol, and Protocol row
counts are postrun/debug evidence only. They must not enter generic
`DecisionFeatures`. LLM hypothesis/code/fix output remains tainted proposal
material until it passes Contract, Verification, Protocol, and safe feature
extraction.

## Launch Decision

Do not launch while the WSL CVRP `size70` large-X replay is still running. That
replay is no-LLM, but it runs up to four concurrent solver processes with
120/480s time limits and can distort a warehouse `time_limit_sec=30` lifecycle
debug. Start this warehouse gate only after the solver load is clear.

## Recommended Spec

- Problem: warehouse production problem package.
- Cells: `1` cell only, `rep01/on_compact`.
- Rounds: `1`.
- Model: local/WSL `gpt-5.5`.
- Base URL/API key: WSL codex proxy, same shape as prior WSL campaigns.
- Measurement governance: `on`.
- Proposal context: `compact-measurement-diagnostics`.
- Time limit: `30s`.
- Agentic session timeout: `900s`.
- Early stop: disabled.
- Stage-transition drain: `0` if exposed in the invoked runner path; this gate
  should not mix validation/frozen drain into the lifecycle judgment.
- Execution shape: foreground `timeout 2h bash run.sh`, or tmux wrapping a
  foreground timeout for recoverable terminal access.
- Parallelism/stagger: none.

## WSL Config Strategy

Do not use repository warehouse config files directly on WSL because the
checked-in files still contain server absolute paths.

Use an experiment-local config directory containing WSL-rewritten copies of:

- `problem.yaml`
- sibling `problem-v1.yaml`
- `split_manifest_prod.yaml`

Required path rewrites:

- `/home/clawd/research/or-autoresearch-agent` ->
  `/home/xjy-ubuntu/research/or-autoresearch-agent`
- `/home/clawd/research/scion-data` ->
  `/home/xjy-ubuntu/research/scion-data`

The sibling `problem-v1.yaml` is required. A previous WSL attempt without that
sibling fell back to legacy objective behavior instead of the adapter-backed
metric-spec path.

## Preflight Status

WSL environment repair performed before this design was recorded:

- Installed `pytest` into `/home/xjy-ubuntu/miniconda3/envs/scion`.
- Verified `pytest` imports as version `9.1.0`.
- Fast-forwarded the WSL repo
  `/home/xjy-ubuntu/research/or-autoresearch-agent` to commit `9204315` on
  `codex/v04-evidence-repair-plan`.
- Ran focused preflight/fix-stage acceptance on WSL:
  `PYTHONPATH=$PWD/scion /home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m pytest -q scion/scion/tests/test_verification_runner_checks.py scion/scion/tests/unit/core/test_campaign_control_preflight_contract.py scion/scion/tests/unit/test_agentic_session_core_flow.py -q`
  with `39 passed`.

Remaining launch-time checks:

```bash
test -x /home/xjy-ubuntu/miniconda3/envs/scion/bin/python
/home/xjy-ubuntu/miniconda3/envs/scion/bin/python - <<'PY'
import importlib.util
for name in ["pytest", "yaml", "sqlite3"]:
    print(name, "OK" if importlib.util.find_spec(name) else "MISSING")
PY

curl -fsS --max-time 2 http://127.0.0.1:8080/v1/models | grep -q 'gpt-5.5'

test -d /home/xjy-ubuntu/research/or-autoresearch-agent/surrogate
test -d /home/xjy-ubuntu/research/scion-data/production/generated
test -d /home/xjy-ubuntu/research/scion-data/production/converted
```

## Command Draft

The old 3x24R `run_wsl.sh` should not be reused directly. Keep its
WSL-config-copy helper and postrun report commands, but reduce it to one
foreground cell.

Core run command:

```bash
timeout 2h /home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m scion.cli.main run \
  --campaign-dir "$OUT/rep01/on_compact/campaign" \
  --problem "$OUT/config/problem.yaml" \
  --protocol /home/xjy-ubuntu/research/or-autoresearch-agent/scion/problems/warehouse_delivery/protocol_prod.yaml \
  --split "$OUT/config/split_manifest_prod.yaml" \
  --seeds /home/xjy-ubuntu/research/or-autoresearch-agent/scion/problems/warehouse_delivery/seed_ledger.yaml \
  --rounds 1 \
  --time-limit-sec 30 \
  --measurement-governance on \
  --proposal-context-ablation compact-measurement-diagnostics \
  --disable-early-stop \
  --agentic-proposal \
  --agentic-session-timeout-sec 900
```

## Acceptance

Accept the lifecycle gate only if all of the following are true:

- `$CAMPAIGN/status.json` exists.
- `protocol_metric_results > 0`.
- `protocol_metric_stage_counts.screening > 0`.
- `scion.db` contains Protocol-stage experiment events, at least screening.
- `agentic_sessions > 0`.
- `llm_traces/` and `agentic_sessions/agentic_session_index.json` exist.
- `campaign_summary.json`, `run.log`, and `run_status.json` exist.

Suggested checks:

```bash
CAMPAIGN="$ROOT/rep01/on_compact/campaign"

jq '.run_validity, .protocol_metric_results, .protocol_metric_stage_counts,
    .research_accounting_breakdown.protocol_rows,
    .agentic_sessions, .llm_request_kind_counts,
    .verification_failure_breakdown' "$CAMPAIGN/status.json"

sqlite3 "$CAMPAIGN/scion.db" \
  "select event_kind, stage, count(*) from experiment_events
   group by event_kind, stage order by event_kind, stage;"
```

Only after this gate passes should the artifact be used to judge warehouse
hypothesis quality, code quality, branch lessons, or promotion potential.

## Failure Classification

- `protocol_metric_results=0`: framework/env/lifecycle failure, not warehouse
  research-quality evidence.
- `V3_unit_tests` / `No module named pytest`: verifier preflight regression.
- `wrong_owner` followed by empty or whole-file `exact_replace`: fix-stage
  no-patch repair regression.
- `verification_light` loop with clean environment: patch lifecycle failure;
  inspect whether wrong-owner/no-patch exits are legal and whether APS patch
  fidelity is failing.
- Legacy objective fallback, missing sibling `problem-v1.yaml`, or
  `absolute_outside_roots`: launch/problem-package path failure.
- Protocol row exists but metrics tie or regress: valid research-quality
  evidence, not a lifecycle gate failure.
