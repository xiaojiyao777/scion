# R16 independent Warehouse research-support control

State: preregistered, not launched. Same frozen shared runtime as
[R16](v04-cvrp-r16-probe-diagnostics-autonomous-preregistration-20260928.md).
This cross-problem control follows the runbook because generic development
feedback and H/C interpretation guidance changed. It does not qualify CVRP
algorithm quality, and its outcomes never enter the CVRP research input.

Source: complete ordinary `surrogate` tree (406 non-cache files).
Problem: `scion/problems/warehouse_delivery/problem-v1.yaml`.
Same source/population/protocol as the corrected R15 control; no source repair.
Population selection inherits that control's outcome-informed engineering
choice. Public instance_development stays out of every formal stage.

[Protocol](inputs/v04-r16-warehouse-probe-control-protocol.yaml),
[split](inputs/v04-r16-warehouse-probe-control-split.yaml),
[seeds](inputs/v04-r16-warehouse-probe-control-seeds.yaml).
Initial small_6 × one seed; expansion adds small_1 × two seeds.
Validation small_3, frozen small_4, canary small_5; no public/formal overlap.
Two evaluated stages, K=1/max three branches, 2-second solver limits.
First five primes above 170000: screening 170003/170021, validation 170029,
frozen 170047, canary 170057. No seed reselection after outcomes.
All existing objective, feasibility, confidence and Decision gates unchanged.

gpt-5.6-sol high; H180/C300; SDK retries zero/two charged typed redispatches.
80 physical calls, 7200-second outer guard, unchanged R3i C limits.
Existing stale calibration diagnostic is retained, not weakened or relabeled.
Validation/frozen cannot execute within two stages when expanded screening is
required. A valid negative is acceptable; a shared framework error blocks CVRP.

Before launch: full regressions, closure/source/expansion checks, fresh absent
output/session, healthy provider without exposing credentials, no competing
solver/test/maintenance. Inspect actual H/C contexts, development hints if
emitted, candidate source, typed steps, metrics and Decisions after terminal.
Do not infer hint usefulness from a run that never emits a failed self-test.

Output: `/home/clawd/research/scion-experiments/v04-r16-warehouse-probe-control-20260928`.
Tmux: `scion-r16-warehouse-probe-control-20260928`.

## Invocation (not yet executed)

Read-only preflight passes: 406 non-cache source files, all five case inputs
parsed, two public suites and complete support closure disjoint from formal
cases, strict expansion/resource/production/Verification setup, sandbox
availability and absent output. No provider/solver/output was created.
Shared focused/input tests pass; full suite **2514 passed, 1 skipped in
426.78 s**. Runtime/input changes are complete and will be committed before
this control. No formal execution has occurred yet.

```bash
set -Eeuo pipefail
cd /home/clawd/research/or-autoresearch-agent
test ! -e /home/clawd/research/scion-experiments/v04-r16-warehouse-probe-control-20260928
proxy_key_value=$(curl -fsS --connect-timeout 5 --max-time 15 http://127.0.0.1:8080/auth/status | jq -er '.proxy_api_key | select(type == "string" and length > 0)')
curl -fsS --connect-timeout 5 --max-time 15 -H "Authorization: Bearer $proxy_key_value" http://127.0.0.1:8080/v1/models | jq -e 'any(.data[]?; .id == "gpt-5.6-sol")' >/dev/null
exec env \
  PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
  PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion \
  OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 \
  SCION_PROBLEM_DATA_ROOT=/home/clawd/research/or-autoresearch-agent/surrogate \
  SCION_MODEL=gpt-5.6-sol SCION_REASONING_EFFORT=high \
  SCION_BASE_URL=http://127.0.0.1:8080 SCION_API_KEY="$proxy_key_value" \
  SCION_LLM_TIMEOUT_SEC=180 SCION_LLM_HYPOTHESIS_RESEARCH_TURN_TIMEOUT_SEC=180 \
  SCION_LLM_CODE_RESEARCH_TURN_TIMEOUT_SEC=300 SCION_LLM_CODE_RESEARCH_FINALIZE_TIMEOUT_SEC=300 \
  /home/clawd/miniconda3/envs/claw/bin/python -B -m scion.cli.main run \
    --problem /home/clawd/research/or-autoresearch-agent/scion/problems/warehouse_delivery/problem-v1.yaml \
    --source-tree /home/clawd/research/or-autoresearch-agent/surrogate \
    --code-research-limits /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-r3i-long-run-code-research-limits.json \
    --protocol /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-r16-warehouse-probe-control-protocol.yaml \
    --split /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-r16-warehouse-probe-control-split.yaml \
    --seeds /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-r16-warehouse-probe-control-seeds.yaml \
    --time-limit-sec 2 --rounds 2 --provider-call-cap 80 \
    --provider-transient-retries 2 --outer-hardwall-sec 7200 \
    --campaign-dir /home/clawd/research/scion-experiments/v04-r16-warehouse-probe-control-20260928
```
