# CVRP M15 customer-conservation continuation preregistration

**State:** `PREPARED_NOT_STARTED`

## Scientific object

Can Scion use the four native M14 H/patch/failure/Protocol/Decision records
and a new problem-owned public customer-conservation test to autonomously
repair, refine or abandon the failed local-search direction and evaluate up to
two new CVRP candidates, without a host-chosen patch, target file, mechanism or
repair?

The only run is
`v04-cvrp-m15-customer-conservation-continuation-20260820` in the fresh root
`/home/clawd/research/scion-experiments/v04-cvrp-m15-customer-conservation-continuation-20260820`.
The user's 2026-08-20 instruction to continue trying with full experimental
authorization delegates this independently frozen one-shot after its clean
carrier and provider-/solver-free gates pass. It does not authorize root reuse,
resume, retry, replacement, case/seed substitution or automatic M16.

## Carrier and ordinary research history

Production baseline `a3e32e2b` differs from the M14 baseline only by one
problem-owned public CVRP unit test. The test constructs a strictly improving
cross-route tail exchange and requires every customer to remain present
exactly once with capacity feasibility. It passes B0 and fails the exact M14
boundary-delta patch, which produces routes `((1, 4), (3, 4))` and loses
customer 2. The test specifies a CVRP solution invariant, not an algorithm
repair or preferred neighborhood implementation. Generic Scion core and the
CVRP algorithm source are unchanged.

Launch binds a clean descendant as `AUTHORIZED_M15_CARRIER` and requires its
`scion/scion` production subtree to equal `a3e32e2b`.

H receives the same M7 structured input and the M9, M10, M11, M12, M13 and M14
history files in order. The four native M14 lines are committed as
`inputs/v04-cvrp-m15-m14-research-history.jsonl`, an exact byte copy with SHA256
`741570ee543a5901cbb6aa1ea59f36f223f5993be2f2d29aab0e02f8af6476a5`.
The complete ordered history contains 19 records. Runtime Scion reads only
these committed ordinary files; it does not reopen an old campaign database,
summary, metrics, trace or workspace. History enters H only. C receives the
Contract-approved current H, current source graph and current public tests;
historical patch source is observation, not code to apply.

## Agent, population and resources

M15 keeps the exact M14/M13 development condition:

- `gpt-5.6-terra`, reasoning high, local proxy, SDK retry zero;
- H timeout 120 seconds; C/research/finalize timeout 240 seconds;
- one shared pre-dispatch H+C provider cap of 30;
- unchanged M11 bounded code-research limits and isolated public sandbox;
- the new customer-conservation test is visible to C and runs in D1-D4; it
  never substitutes for formal Patch Contract or Verification;
- current Patch Contract and Verification always rerun after finalize;
- the host supplies no patch, target, mechanism or repair instruction;
- unchanged outcome-known six-case/two-seed development screen, canary 3049,
  case-median total distance, protected fleet violation, R3 numerical gates
  and `require_expanded_for_pass=true`;
- `--rounds 2`, so at most two evaluated stages. A positive initial screen may
  spend the second stage on expansion; otherwise Decision may create one more
  candidate. Validation/frozen and future formal data remain unused.

| Resource | Hard maximum |
|---|---:|
| provider calls, H+C combined | 30 |
| autonomous H / Hypothesis Contract calls | 30 |
| complete C sessions / formal candidates | 7 |
| Patch Contract / Verification calls | 7 each |
| Protocol / Safe Feature / Decision calls | 2 each |
| Verification solver subprocesses | 14 |
| Verification pytest subprocesses | 7 at 60 seconds |
| Protocol canary solver subprocesses | 4 |
| formal screening solver subprocesses | 48 |
| all solver subprocesses | 66 |
| nominal / guarded solver seconds | 2,260 / 3,250 |
| worst provider timeout seconds | 6,840 |
| cumulative development-test / Verification pytest seconds | 540 / 420 |
| known guarded total / outer hardwall | 11,050 / 13,500 seconds |

Seven formal candidates follows from the minimum four provider calls per
candidate (H, revise, test, finalize). H-only rejection can consume all 30
calls but creates no solver work. Solver and timeout arithmetic is unchanged
from M14.

## Stops and claim boundary

Research rejection may schedule another H only below the provider cap.
Provider cap exhaustion stops before dispatch as
`RESOURCE_EXHAUSTED / PROVIDER_CALL_CAP_EXHAUSTED`; provider faults are terminal
`BLOCKED_INFRA` with retry zero. Other non-evaluated, resource,
infrastructure or interrupt outcomes stop immediately. Canary veto carries no
formal Protocol claim. Two evaluated stages stop as
`requested_rounds_completed`; the watchdog terminates children as
`INTERRUPTED / OUTER_HARDWALL_EXCEEDED`.

Framework behavior and observed use of prior history/public tools may be
reported. Algorithm claims remain outcome-known development-screen
descriptions. No result establishes promotion, general CVRP improvement,
causal isolation, production readiness or v0.4 completion.

## Frozen command

```bash
set -euo pipefail
cd /home/clawd/research/or-autoresearch-agent/scion
test -n "${AUTHORIZED_M15_CARRIER:-}"
test "$(git rev-parse HEAD)" = "$AUTHORIZED_M15_CARRIER"
git diff --quiet
git diff --cached --quiet
REPO_ROOT="$(git rev-parse --show-toplevel)"
test "$REPO_ROOT" = /home/clawd/research/or-autoresearch-agent
git -C "$REPO_ROOT" diff --quiet \
  a3e32e2b "$AUTHORIZED_M15_CARRIER" -- scion/scion
test ! -e /home/clawd/research/scion-experiments/v04-cvrp-m15-customer-conservation-continuation-20260820
command -v bwrap >/dev/null

PROXY_KEY_VALUE="$(curl -fsS --connect-timeout 5 --max-time 15 \
  http://127.0.0.1:8080/auth/status | \
  jq -er '.proxy_api_key | select(type == "string" and length > 0)')"
trap 'unset PROXY_KEY_VALUE' EXIT
curl -fsS --connect-timeout 5 --max-time 15 \
  -H "Authorization: Bearer $PROXY_KEY_VALUE" \
  http://127.0.0.1:8080/v1/models | \
  jq -e --arg model gpt-5.6-terra \
    'any(.data[]?; .id == $model)' >/dev/null

PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion:/home/clawd/.local/lib/python3.12/site-packages:/home/clawd/miniconda3/envs/claw/lib/python3.12/site-packages \
PYTHONDONTWRITEBYTECODE=1 \
SCION_PROBLEM_DATA_ROOT=/home/clawd/research/or-autoresearch-agent/vrp \
SCION_MODEL=gpt-5.6-terra \
SCION_REASONING_EFFORT=high \
SCION_BASE_URL=http://127.0.0.1:8080 \
SCION_API_KEY="$PROXY_KEY_VALUE" \
SCION_LLM_TIMEOUT_SEC=120 \
SCION_LLM_HYPOTHESIS_TIMEOUT_SEC=120 \
SCION_LLM_CODE_TIMEOUT_SEC=240 \
/home/clawd/miniconda3/envs/claw/bin/python -S -B -m scion.cli.main run \
  --problem /home/clawd/research/or-autoresearch-agent/scion/scion/problems/cvrp/problem.yaml \
  --research-input /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m9-m7-fc1-research-input.json \
  --research-history /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m10-m9-research-history.jsonl \
  --research-history /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m11-m10-research-history.jsonl \
  --research-history /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m12-m11-research-history.jsonl \
  --research-history /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m13-m12-research-history.jsonl \
  --research-history /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m14-m13-research-history.jsonl \
  --research-history /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m15-m14-research-history.jsonl \
  --code-research-limits /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m11-code-research-limits.json \
  --protocol /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m9-development-protocol.yaml \
  --split /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m9-development-split.yaml \
  --seeds /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m9-development-seeds.yaml \
  --time-limit-sec 30 \
  --provider-call-cap 30 \
  --outer-hardwall-sec 13500 \
  --rounds 2 \
  --campaign-dir /home/clawd/research/scion-experiments/v04-cvrp-m15-customer-conservation-continuation-20260820
```

Preparation must verify the exact clean carrier and module origins, all
loaders, 19 ordered history records, the exact M14 copy, B0-pass/M14-fail
customer-conservation regression, public sandbox and closure, unchanged
population/resource arithmetic, proxy model metadata and absent output. Any
failure is `PREP_INVALID` with zero live provider or solver call.
