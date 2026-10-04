# R18 independent Warehouse public-research-context control

State: preregistered, not launched. October 4 user authorizes repair, verification,
commit/push and fresh experiments. This checks shared read-only dependency and
query-feedback changes on the same frozen runtime as
[CVRP R18](v04-cvrp-r18-research-context-autonomous-preregistration-20261004.md).
It is an engineering/research-interface control, not a new retained-improvement
claim. No control result is supplied to CVRP proposals.

## Design and interpretation

Complete ordinary initial source is repository `surrogate`, no host algorithm
repair. Same population and scientific gates as R17, with fresh seeds.
Public development instance remains excluded from all formal cases.
[Protocol](inputs/v04-r18-warehouse-research-context-control-protocol.yaml),
[split](inputs/v04-r18-warehouse-research-context-control-split.yaml),
[seeds](inputs/v04-r18-warehouse-research-context-control-seeds.yaml).
Initial small_6 × one seed; expansion adds small_1 × two seeds. Validation
small_3, frozen small_4, canary small_5. Mandatory expansion prevents held-out
stages within the two-stage target. The inherited population is outcome-informed
engineering selection, not independent algorithm-quality evidence.

First five primes above210000: screening210011/210019; validation210031;
frozen210037; canary210053. Two evaluated stages, two-second paired solver
limits, K=1/max three branches, gpt-5.6-sol high, H180/C300, SDK retry0/two
charged typed transient redispatches, 80 physical calls, 7200-second outer
guard, unchanged R3i C limits. No increase, statistical-threshold change,
calibration relabeling or run extension/resume. Negative science is acceptable.

Inspect all actual C contexts/actions for public dependency visibility and exact
source values, malformed query feedback and whether the next action corrects
it. Record failed queries separately from patch-edit errors and provider faults;
compare descriptively with R17's 28 query errors and two edit errors /43 C turns,
not as a controlled causal estimate of model quality. A model that does not
issue a malformed request does not exercise live correction feedback; regression
tests must cover that path. No forced target, read action or algorithm mechanism.

The source-read repair must not allow frozen dependency edits or private-suite/
formal-data reads. Contract/Verification/canary and paired Protocol/Decision
remain unchanged. Verify source continuation if naturally exercised; do not
force a branch to manufacture coverage.

## Prelaunch and terminal conditions

Base runtime `7e1fd7dc` plus P14 repairs, committed/pushed after focused/full
tests and input/source/public-formal closure checks. Record actual revision and
counts below. No live tests, other solvers, maintenance or runtime edits overlap
measurement. Credentials remain outside logs/artifacts.

After terminal inspect ordinary status/summary/traces/history/metrics/source
without opening original SQLite. A discovered framework defect blocks CVRP;
preserve an incomplete control rather than calling it completed or extending it.
Record actual coverage before any subsequent launch decision.

Output: `/home/clawd/research/scion-experiments/v04-r18-warehouse-research-context-control-20261004`.
Tmux: `scion-r18-warehouse-research-context-control-20261004`.

## Planned direct CLI invocation

Not executed at preregistration.

```bash
set -Eeuo pipefail
cd /home/clawd/research/or-autoresearch-agent
test ! -e /home/clawd/research/scion-experiments/v04-r18-warehouse-research-context-control-20261004
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
    --protocol /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-r18-warehouse-research-context-control-protocol.yaml \
    --split /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-r18-warehouse-research-context-control-split.yaml \
    --seeds /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-r18-warehouse-research-context-control-seeds.yaml \
    --time-limit-sec 2 --rounds 2 --provider-call-cap 80 \
    --provider-transient-retries 2 --outer-hardwall-sec 7200 \
    --campaign-dir /home/clawd/research/scion-experiments/v04-r18-warehouse-research-context-control-20261004
```

## Actual verification and terminal audit

Implementation/independent review and focused tests pass; see the CVRP design
for overlapping group counts. Read-only preflight loads all five formal/canary
instances, checks public/formal closure and both actual H/C context builders.
H has 17 source-index entries; C has nine explicitly declared readonly
dependencies. `models.py` is readable but not an editable file. No campaign
directory, solver or provider call is created. Full suite passes 2622 tests /
one skip in 446.02 s; exact prompt-fixture alignment and the first run are
disclosed in the CVRP design. Ruff F/E9 and diff checks pass. Git push pending.
