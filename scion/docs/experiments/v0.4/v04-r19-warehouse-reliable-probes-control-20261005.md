# R19 Warehouse control for reliable research feedback

State: **stopped / invalid_no_evaluated_outcome**, zero of two evaluated stages.
Started once October5 at14:21:18 Beijing /06:21:18 UTC, PID530783; stopped at
14:37:22 Beijing /06:37:22 UTC, pane exit21. This fresh two-stage control checks the
shared no-tests feedback and draft-base guidance used by
[CVRP R19](v04-cvrp-r19-reliable-probes-autonomous-preregistration-20261005.md).
It is an engineering/research-interface check, not a retained improvement claim.
No Warehouse outcome enters CVRP H/C.

## Frozen design

Complete initial source is repository `surrogate`, with no host algorithm edit.
[Protocol](inputs/v04-r19-warehouse-reliable-probes-control-protocol.yaml),
[split](inputs/v04-r19-warehouse-reliable-probes-control-split.yaml) and
[seeds](inputs/v04-r19-warehouse-reliable-probes-control-seeds.yaml) preserve the
R18 population and gates. Initial small_6×one seed; required expansion
small_6/small_1×two seeds. Validation small_3, frozen small_4, canary small_5;
public development small_2 excluded from all formal cases.

First five primes above230000: screening230003/230017, validation230047,
frozen230059, canary230063. Two evaluated stages, two-second solver limits,
K=1/max three branches, gpt-5.6-sol high, H180/C300, SDK retry0/two charged typed
redispatches,80 physical calls,7200-second outer guard and unchanged R3i C limits.
No threshold relaxation, extra stage, case substitution, calibration relabeling
or extension/resume. Population is inherited outcome-informed engineering
selection, not independent algorithm-quality evidence.

## Checks and interpretation

After focused/full regression and preflight, freeze the ordinary checkout at
`484433ea` plus scoped uncommitted P15 changes. No new commit/push is authorized.
Use the same runtime for this control and CVRP. No tests, competing solvers,
maintenance or runtime/input changes during measurement.

Inspect all actual H/C source values, safe query/probe feedback and any draft
corrections. Do not force the model to issue an empty test or bad selector:
unexercised live paths stay unexercised, with regression coverage distinguished.
Readonly dependencies must remain noneditable; no private source/data read.
Candidate failure or valid tie is acceptable. An execution/boundary defect blocks
CVRP; incomplete coverage must be recorded honestly rather than silently resumed.
No control outcome, algorithm or import-repair recipe is copied into CVRP.

R18 Warehouse's repeated new-target reads, readonly edit attempts and forbidden
imports remain known research-support limits; this scoped work does not claim to
solve them. Interpret actual coverage, not the existence of new prompt text.

Output: `/home/clawd/research/scion-experiments/v04-r19-warehouse-reliable-probes-control-20261005`.
Tmux: `scion-r19-warehouse-reliable-probes-control-20261005`.

## Planned direct invocation

```bash
set -Eeuo pipefail
cd /home/clawd/research/or-autoresearch-agent
test ! -e /home/clawd/research/scion-experiments/v04-r19-warehouse-reliable-probes-control-20261005
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
    --protocol /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-r19-warehouse-reliable-probes-control-protocol.yaml \
    --split /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-r19-warehouse-reliable-probes-control-split.yaml \
    --seeds /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-r19-warehouse-reliable-probes-control-seeds.yaml \
    --time-limit-sec 2 --rounds 2 --provider-call-cap 80 \
    --provider-transient-retries 2 --outer-hardwall-sec 7200 \
    --campaign-dir /home/clawd/research/scion-experiments/v04-r19-warehouse-reliable-probes-control-20261005
```

## Verification and actual execution

Full regression passes2659 tests / one skip in453.27 seconds; focused groups and
changed-file Ruff/diff checks pass. Complete source/public-formal closure and all
five case inputs pass read-only preflight. H has17 source entries and C9 readonly
bodies, with models.py not editable. Initial source has406 non-cache files (and
five pre-existing pytest cache files). No output or provider/solver call is created.
Runtime and inputs are frozen at484433ea plus scoped uncommitted P15 changes;
full tests have finished before measurement. One bounded inference succeeds
at14:20:52 Beijing, then the command above starts once at14:21:18. Early H
requests encounter upstream overloaded-server502 errors with a successful bounded
retry. No additional calls beyond the80 cap or retry enlargement is authorized.

The frozen protocol/split YAML version labels retain the R18 spelling; the seed
label has an04 prefix. These descriptive values are not runtime controls; actual
fresh seeds, paths and effective Protocol are checked. Preserve executed input
files rather than relabeling them during the run. Record this cosmetic limit.

## Terminal audit and blocked launch decision

[Terminal status](/home/clawd/research/scion-experiments/v04-r19-warehouse-reliable-probes-control-20261005/status.json)
at `2026-10-05T06:37:22.191075+00:00` and the
[summary](/home/clawd/research/scion-experiments/v04-r19-warehouse-reliable-probes-control-20261005/campaign_summary.json)
establish `stopped / execution_resource_exhausted`, reason
`PROVIDER_CALL_CAP_EXHAUSTED`, validity `invalid_no_evaluated_outcome`.
This is neither a valid negative scientific result nor a completed control.
There are zero formal candidates, pairs, metric files, validation/frozen stages
or promotions. No research_history.jsonl is produced. Champion v1 remains exact.

All80 admitted physical calls are accounted for: H64 (35 successful,29 failed),
C16 (two successful,14 failed). All43 failures explicitly report upstream
overloaded-server502 errors, not quota429, authentication failure or a local
test failure. All34 bounded redispatches preserve the exact original context,
system blocks, user prompt and schema. Eight scheduled attempts end as
`research_rejected / PROVIDER_TRANSIENT_RETRIES_EXHAUSTED`; these are operational
proposal failures, not adverse algorithm evidence. The ninth ends at the call cap.
The7200-second outer guard is not exhausted; no limit is widened.

Four H values reach finalization. Successful C actions are one read of the
existing destroy-rebuild source and one revise in the final attempt. That draft
never completes test_patch or ready: the next request fails and its retry cannot
be admitted after call80. There is no exercised live no-tests feedback or completed
draft correction, Contract/Verification/canary or paired Protocol. Regression
coverage cannot be substituted for this missing live control evidence.

Source audit checks all recorded request contexts, including failed dispatches:
1088 H source-index entries (64 contain models.py),137 visible H bodies,
16 editable C bodies,144 readonly C bodies and32 public-test bodies are exact.
The new draft-base guidance is present in all16 C requests. A recorded failed
request is not proof that the model consumed that context. The complete406-file
non-cache champion equals the initial source; no accepted branch head exists.
No original SQLite is opened or changed. Runtime and scientific inputs remain
byte-for-byte frozen through terminal; only status/analysis docs changed.

Decision: **do not launch CVRP R19** from this control. Shared support passes
2659 regressions and all preflight checks, but service availability and complete
control execution have not been demonstrated. Wait for service recovery, then
preregister a fresh control with a new output path/seed ledger; never resume this
terminal campaign or silently raise its80-call cap. Audit a complete control
before deciding on CVRP. No Warehouse failure or result is fed into CVRP H/C.
