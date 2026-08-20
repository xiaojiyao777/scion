# CVRP M22 post-infra continuous research preregistration

**State:** `PREPARED_NOT_STARTED`

## Scientific object

Can a fresh normal Scion campaign continue the autonomous research frontier
after M21's typed provider-infrastructure stop and obtain two evaluated
development stages without host-selected algorithm content?  M21's exact
ordinary history tells H that removing the redundant relocation neighborhood
was a valid all-tie result and that deadline-fraction annealing was proposed but
not evaluated.  H is free to revisit that hypothesis with a concrete delta or
choose another target/mechanism.  The host supplies no patch, repair, target,
action or forced continuation of the failed provider request.

The one run is `v04-cvrp-m22-post-infra-continuation-20260820` in fresh root
`/home/clawd/research/scion-experiments/v04-cvrp-m22-post-infra-continuation-20260820`.
The user's full experimental authorization covers this independently prepared
bounded one-shot after clean-carrier and offline gates pass.  M21 is not
resumed or retried; M22 has a new process, label, root, population and provider
requests.  No root reuse, response retry, input substitution or automatic M23
is authorized by this record.

## Carrier and ordinary history

Production baseline remains `62142c80`, including pre-provider multi-round
shape validation.  Launch binds a clean descendant with an identical
`scion/scion` subtree.  H receives the unchanged problem-owned M7+M18 input;
the ordered history files through M20; and
`inputs/v04-cvrp-m22-m21-research-history.jsonl`, an exact three-line copy of
M21 native history with SHA256
`c6e18ad17cfd91cd42869698a295ac083303464754b87f7eb3b94c15c2c4561f`.
The complete ordered prior has 30 records.  C sees only the approved current H,
current source graph/on-demand peers and public development checks.  It does
not reopen any old campaign database, summary, raw metric, trace, workspace or
candidate source.

## Fresh population and stages

Initial screening is the exact priority subset `B-n57-k9`, `P-n19-k2`,
`X-n303-k21` with seeds `2079`, `5831`.  Expanded screening strictly contains
it and adds `A-n69-k9`, `X-n139-k10`, `X-n331-k15`, using the same seeds.
Normal nested selection is therefore 3 -> 6 cases and 6 -> 12 paired
comparisons.

Declared later-development data is validation `X-n162-k11`, `X-n204-k19`,
`X-n561-k42` with seeds `4741`, `3617`, and frozen `X-n181-k23`,
`X-n280-k17`, `X-n701-k44` with seeds `8830`, `2235`.  Canary is the public
tiny instance with seed `5947`.  Every instance and companion solution is a
regular non-symlink parsed by the production adapter.  All twelve paths and
seven seeds are absent from all earlier committed experiment records and
inputs.  Selection is outcome-blind.

Measurement, pairing, protected fleet objective, numerical gates and
`require_expanded_for_pass` are unchanged.  Two evaluated rounds allow either
initial -> expanded reuse of one verified branch or two initial candidates.
Validation, frozen and promotion are unavailable and unauthorized.  Passing
expanded screening would still be development evidence only.

## Resources, stops and claims

H/C share provider cap 30.  At most seven complete C/Contract/Verification
attempts and two Protocol/Safe Feature/Decision stages are possible.  Solver
cap is 54 subprocesses: Verification 14, canary 4 and formal screening 36.
Nominal/positive-hard-timeout solver seconds are 1,960/2,770; provider timeout
sum is 6,840, development pytest 540 and Verification pytest 420, for known
guarded total 10,570 below outer hardwall 14,000.  Model is
`gpt-5.6-terra`, reasoning high, local proxy, H timeout 120, C timeout 240 and
SDK retry zero.

Any provider/infrastructure, `NOT_EVALUATED`, resource, unknown or interrupt
outcome stops immediately; no provider response retry occurs.  Research
rejection may continue within cap.  Two evaluated rounds stop normally.  The
only allowed claims are framework continuity, ordinary-history use,
mechanism-level observations and development-screen descriptions.  No
independent discovery, isolated causal effect, validation/frozen, promotion,
global CVRP, production or v0.4-complete claim follows.

## Frozen command

```bash
set -euo pipefail
cd /home/clawd/research/or-autoresearch-agent/scion
test -n "${AUTHORIZED_M22_CARRIER:-}"
test "$(git rev-parse HEAD)" = "$AUTHORIZED_M22_CARRIER"
git diff --quiet
git diff --cached --quiet
REPO_ROOT="$(git rev-parse --show-toplevel)"
test "$REPO_ROOT" = /home/clawd/research/or-autoresearch-agent
git -C "$REPO_ROOT" diff --quiet \
  62142c80 "$AUTHORIZED_M22_CARRIER" -- scion/scion
test ! -e /home/clawd/research/scion-experiments/v04-cvrp-m22-post-infra-continuation-20260820
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
  --research-input /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m19-m7-m18-research-input.json \
  --research-history /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m10-m9-research-history.jsonl \
  --research-history /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m11-m10-research-history.jsonl \
  --research-history /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m12-m11-research-history.jsonl \
  --research-history /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m13-m12-research-history.jsonl \
  --research-history /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m14-m13-research-history.jsonl \
  --research-history /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m15-m14-research-history.jsonl \
  --research-history /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m16-m15-research-history.jsonl \
  --research-history /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m19-m16-research-history.jsonl \
  --research-history /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m20-m19-research-history.jsonl \
  --research-history /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m21-m20-research-history.jsonl \
  --research-history /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m22-m21-research-history.jsonl \
  --code-research-limits /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m11-code-research-limits.json \
  --protocol /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m22-provider-recovery-development-protocol.yaml \
  --split /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m22-provider-recovery-development-split.yaml \
  --seeds /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m22-provider-recovery-development-seeds.yaml \
  --time-limit-sec 30 \
  --provider-call-cap 30 \
  --outer-hardwall-sec 14000 \
  --rounds 2 \
  --campaign-dir /home/clawd/research/scion-experiments/v04-cvrp-m22-post-infra-continuation-20260820
```

Preparation verifies clean carrier/module origins, production config/history
loading, all instances/solutions, strict nested selection, zero prior overlap,
resource arithmetic, sandbox, proxy model metadata and absent output.  Failure
is `PREP_INVALID` with zero live provider or solver work.
