# CVRP M16 positive-mechanism continuation preregistration

**State:** `PREPARED_NOT_STARTED`

## Scientific object and one-shot

Can Scion use the two native M15 H/patch/Protocol/Decision records to
autonomously preserve or improve the first candidate's positive mechanism,
avoid the second candidate's X195 regression, address the repeated shared
baseline failure, or pivot—without a host-selected target, patch, mechanism or
repair?

The only run is
`v04-cvrp-m16-positive-mechanism-continuation-20260820` in the absent root
`/home/clawd/research/scion-experiments/v04-cvrp-m16-positive-mechanism-continuation-20260820`.
The user's 2026-08-20 full experimental authorization delegates this bounded
fresh continuation after clean-carrier and provider-/solver-free gates pass.
It does not authorize root reuse, resume, retry, replacement, case/seed
substitution or automatic M17.

## Carrier and ordinary inputs

Production baseline remains `a3e32e2b`: relative to M14 it adds only the
problem-owned CVRP customer-conservation development test. Generic framework
code and CVRP algorithm source are unchanged. Launch binds a clean descendant
as `AUTHORIZED_M16_CARRIER` and requires its `scion/scion` subtree to equal
that baseline.

H receives the same M7 research input and the M9-M15 history files in exact
order. `inputs/v04-cvrp-m16-m15-research-history.jsonl` is an exact two-line
copy of native M15 history, SHA256
`3a3a1eae63a10fa61dc928ad417d09b4d343ff3a970695e461422deba8aacb75`.
The full ordered history has 21 records. Only committed ordinary inputs are
read; old campaign databases, summaries, metrics, traces and workspaces are not
reopened. History enters H only. C uses the approved current H, current source
graph and current public tests. Historical patch source is not applied.

## Agent, development science and resources

- `gpt-5.6-terra`, reasoning high, local proxy, SDK retry zero;
- H timeout 120 seconds; C/research/finalize timeout 240 seconds;
- one shared pre-dispatch provider cap of 30;
- unchanged bounded code-research limits and isolated public sandbox;
- current development checks, formal Patch Contract and Verification rerun for
  every finalized candidate;
- the host specifies no patch, target, mechanism or repair;
- unchanged outcome-known six-case/two-seed development screen, canary 3049,
  total-distance case median, protected fleet violation, R3 numerical gates
  and `require_expanded_for_pass=true`;
- `--rounds 2`, at most two evaluated stages. Validation/frozen and future
  formal data remain unavailable and unused.

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

The arithmetic and typed stops are unchanged from M15. Research rejection may
continue only below the provider cap. Provider exhaustion stops before
dispatch; provider fault, other infrastructure/resource/non-evaluated or
interrupt outcomes stop immediately. Canary veto carries no Protocol claim.
Two evaluated stages stop as `requested_rounds_completed`; the watchdog kills
children and records `INTERRUPTED / OUTER_HARDWALL_EXCEEDED`.

Framework and observed continuous-research behavior may be reported.
Algorithm claims remain outcome-known development descriptions. No result is
promotion, general CVRP improvement, causal isolation, production readiness or
v0.4 completion.

## Frozen command

```bash
set -euo pipefail
cd /home/clawd/research/or-autoresearch-agent/scion
test -n "${AUTHORIZED_M16_CARRIER:-}"
test "$(git rev-parse HEAD)" = "$AUTHORIZED_M16_CARRIER"
git diff --quiet
git diff --cached --quiet
REPO_ROOT="$(git rev-parse --show-toplevel)"
test "$REPO_ROOT" = /home/clawd/research/or-autoresearch-agent
git -C "$REPO_ROOT" diff --quiet \
  a3e32e2b "$AUTHORIZED_M16_CARRIER" -- scion/scion
test ! -e /home/clawd/research/scion-experiments/v04-cvrp-m16-positive-mechanism-continuation-20260820
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
  --research-history /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m16-m15-research-history.jsonl \
  --code-research-limits /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m11-code-research-limits.json \
  --protocol /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m9-development-protocol.yaml \
  --split /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m9-development-split.yaml \
  --seeds /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m9-development-seeds.yaml \
  --time-limit-sec 30 \
  --provider-call-cap 30 \
  --outer-hardwall-sec 13500 \
  --rounds 2 \
  --campaign-dir /home/clawd/research/scion-experiments/v04-cvrp-m16-positive-mechanism-continuation-20260820
```

Preparation verifies clean carrier and origins, all loaders, 21 ordered
history records, exact M15 copy, public tests and sandbox, unchanged
population/resource arithmetic, proxy model metadata and absent output. Any
failure is `PREP_INVALID` with zero live provider or solver call.
