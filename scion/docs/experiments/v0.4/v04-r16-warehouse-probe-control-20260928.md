# R16 independent Warehouse research-support control

State: terminal `stopped` / `execution_resource_exhausted`, **valid_incomplete**
at `2026-09-28T15:43:16.084971+00:00`; pane dead, exit 21.
Only **one of two requested evaluated stages** completed. Not a completed
two-stage control, not quality improvement. Launched once at
`2026-09-28T15:32:15Z`, tmux PID 331073.
Implementation and inputs were committed as `d67f9800` before launch;
checkout was clean, all tests/diagnostics finished, and output/session absent.
Only status documentation may change during measurement. Same frozen runtime as
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

## Invocation (executed once)

Read-only preflight passes: 406 non-cache source files, all five case inputs
parsed, two public suites and complete support closure disjoint from formal
cases, strict expansion/resource/production/Verification setup, sandbox
availability and absent output. No provider/solver/output was created.
Shared focused/input tests pass; full suite **2514 passed, 1 skipped in
426.78 s**. Runtime/input changes were committed before this control.
Provider credential/model-catalog checks passed without exposing credentials.

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

## Terminal audit and limited inference

[Status](/home/clawd/research/scion-experiments/v04-r16-warehouse-probe-control-20260928/status.json)
and [summary](/home/clawd/research/scion-experiments/v04-r16-warehouse-probe-control-20260928/campaign_summary.json)
record five scheduled attempts, five H exports, one C ready export, three
research rejections and a final provider-cap stop. All 80 physical calls
succeed at attempt index zero: H26, C-turn51, C-finalization3. No hidden retry,
unknown outcome, infrastructure exception or budget widening. Champion v1 /
weight revision zero; validation/frozen unopened. Never resume this root.

| Attempt | Result |
|---|---|
| MergeVehicles | Self-test fails; revised draft remains untested at turn limit; invalid finalization correctly rejected |
| DestroyRebuild | Contract/Verification/canary pass; one complete valid screening pair ties; continue_explore |
| new subcategory ejection chain | Draft first staged at last turn; untested finalization rejected |
| MoveOrder | Explicit C abandonment; no formal evidence |
| continuation of DestroyRebuild branch | Global 80-call cap correctly stops C; accepted source preserved |

The sole [metric](/home/clawd/research/scion-experiments/v04-r16-warehouse-probe-control-20260928/metrics/8ba2db4d-e24a-42a1-8537-581b25eed9db.json)
is small_6 / 170003, two-second limits, 1/1 valid pairs, no failures or protected
subcategory-split regression. Both objective deltas are zero, case/CI zero;
SCREENING_FAIL_WIN_RATE / CONTINUE_EXPLORE is preserved. Runtime ratio is
1.4627 (candidate +217 ms), not a speedup. No expansion or second formal pair.

All 406 champion files equal the declared source. All 52 visible C source
values match the correct base: champion for attempts 1–4, the accepted
DestroyRebuild head for attempt 5. The retained complete 406-file candidate
`candidate_workspaces/candidate-v20rqg4w` differs only in the exact history
DestroyRebuild source plus registry formatting/default empty-category fields;
typed registry values are equal via the ordinary registry reader. No sibling
mixing, fabricated stage snapshot, candidate execution rerun or SQLite access.

The failed MergeVehicles falsifier actually reaches C as
`failed / call / assertion_error / probe_line=68`, locating its self-authored
identity assertion; no raw exception/path is returned. Its host D1–D4 checks
pass, but the failed exact draft remains rejected. DestroyRebuild's self-test
passes and immediate ready exports the exact candidate. Guidance is present
in all applicable actual H/C calls. This establishes delivery and boundaries,
not that the model used the hint well or that the self-test claim is sufficient.

Research efficiency remains poor: 16 source_not_visible and 19
command_field_invalid tool results consume C turns. The model repeatedly
requests unavailable frozen sources or invalid search fields, often stages
its implementation too late, and cannot complete two stages within 80 calls.
This is an observed limitation, not evidence that larger budgets repair it.
The control is not a controlled estimate of the prompt change's effect.

Operator launch decision: the planned two-stage target was not reached and is
not retrospectively marked complete. The runbook's shared-runtime check has
nevertheless exercised actual H/C, safe failure feedback, exact source
continuation, Contract/Verification/canary and a complete Protocol/Decision
path, with no framework blocker found; the full suite also passes. Proceed
with the already preregistered CVRP trial under this explicitly limited control
coverage. No control rerun, larger cap, algorithm change, new scientific gate,
or control-result injection into CVRP H/C is introduced.
