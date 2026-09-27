# R15 repair: independent Warehouse research-path control

State: startup rejected at `2026-09-27T13:40:17Z`, exit 1; launched once at
`2026-09-27T13:40:16Z`, driver PID 288362. Preserve the dead tmux pane and
this original invocation/input; it is not a completed control or resumable run.
User authorizes the shared-core repair and
fresh experiment. This control precedes CVRP R15 on the same frozen runtime;
it is engineering regression evidence, not a new Warehouse improvement claim.

## Design

Two formal evaluated stages through the ordinary autonomous CLI. H chooses
the problem-owned surface, target and mechanism; C implements its approved H.
No forced target, injected patch, research-input/history or restored state.
Current complete source: `/home/clawd/research/or-autoresearch-agent/surrogate`.
Problem spec: `scion/problems/warehouse_delivery/problem-v1.yaml`.
Existing problem-owned editable/frozen, public development, Contract and
Verification boundaries remain unchanged. Parameter search is disabled.

Population is the already known feasible second
[Warehouse A/A control](v04-p1b-warehouse-aa-control-postrun-20260921.md).
Preserve the first control's small_2 shared-infeasible result; it is not repaired.
No private data is added to H/C. [Split](inputs/v04-r15-warehouse-feedback-control-split.yaml)
contains two screening/public fixtures; initial selection is
instance_development, then strict expansion adds small_1.
[Protocol](inputs/v04-r15-warehouse-feedback-control-protocol.yaml): initial
1 case × 1 seed, expanded 2 × 2, pass requires expansion. A negative first
screen may instead lead to a second fresh candidate; same-branch continuation
and covering both cases are therefore conditional, not guaranteed.
The two-stage target cannot reach validation/frozen after a required screen
expansion. Retain all normal gates, measurement and deterministic Decision.

[Seeds](inputs/v04-r15-warehouse-feedback-control-seeds.yaml) are the first five
primes above 150000: screening 150001/150011, validation 150041,
frozen 150053, canary 150061. Solver limit 2 seconds, ordinary 17-second
subprocess guard, 4096 MiB. Up to five screening pairs and two stage-canary
pairs (14 Protocol subprocesses), plus candidate Verification and public
development checks. Failed attempts have separate cost, bounded by 80 charged
physical calls and 7200-second outer guard. H 180 s, C 300 s; SDK retry zero,
two charged typed-transient redispatches. Existing R3i Code session limits.

Warehouse calibration is degraded/calibration_stale (108 days versus existing
90-day policy on September 27). Do not modify calibration dates/policy or
claim improvement from this control. The small cases are outcome-informed.

## Acceptance and timing

Run only after all source edits and focused/full tests finish. Runtime and
all scientific inputs remain frozen for this control and CVRP R15. No
concurrent tests, other solvers or cleanup.

Inspect actual exported H/C, source implementation, Contract/Verification,
typed stages, complete paired metrics and deterministic Decision. A valid
negative is acceptable. Framework failure must be repaired before CVRP, with
tests and a fresh control root. Provider success or stage count alone is
insufficient. Security-feedback examples are directly tested by focused
redteams; autonomous control need not naturally make an unsafe draft.

Checkout `v0.4-dev`, HEAD `964a9622`, uncommitted repairs/tests/docs/inputs.
Output `/home/clawd/research/scion-experiments/v04-r15-warehouse-feedback-control-20260927`.
Tmux `scion-r15-warehouse-feedback-control-20260927`.

Full shared suite: 2471 passed, 1 skipped in 430.51 s. Focused feedback tests
144 passed; prompt/context tests 195 passed; prospective input tests 6 passed
(overlapping sets, not additive). Independent review has no blocking finding.
All five data inputs, CLI parsing, expansion, source/fresh output and public
test limits pass read-only checks. Provider catalog/credential checks pass
without secret output. No other solver/test/cleanup overlaps this run.
Runtime and scientific inputs are now frozen; only status docs may change.

## Invocation (executed once)

```bash
set -Eeuo pipefail
cd /home/clawd/research/or-autoresearch-agent
test ! -e /home/clawd/research/scion-experiments/v04-r15-warehouse-feedback-control-20260927
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
    --protocol /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-r15-warehouse-feedback-control-protocol.yaml \
    --split /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-r15-warehouse-feedback-control-split.yaml \
    --seeds /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-r15-warehouse-feedback-control-seeds.yaml \
    --time-limit-sec 2 --rounds 2 --provider-call-cap 80 \
    --provider-transient-retries 2 --outer-hardwall-sec 7200 \
    --campaign-dir /home/clawd/research/scion-experiments/v04-r15-warehouse-feedback-control-20260927
```

## Result

`validate_development_closure_boundary` rejects
`surrogate/data/instance_development.json`: this is explicitly a Code public
development support file and cannot also be a formal Protocol case. This
boundary was not applicable to the old provider-free A/A control but applies
to the new autonomous Code session. The prelaunch check omitted this one
composition validator; production/data/expansion checks alone were insufficient.

No output directory, status, H/C, provider dispatch or solver execution was
created. The tmux pane retains the exit-1 traceback. This is a configuration
failure with the intended isolation working, not a solver/scientific result.
Do not weaken the boundary or rename/copy the development case to bypass it.
The separately preregistered r2 uses an existing non-development case, checks
the full public closure boundary, and starts in a new root on unchanged runtime.
