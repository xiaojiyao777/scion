# CVRP M21 strict-expansion continuous research preregistration

**State:** `PREPARED_NOT_STARTED`

## Scientific object

Can Scion continue autonomously from M20's positive `_swap` evidence and
complete a genuinely deeper research step under the normal V3 chain?  M21
allows two evaluated stages.  If the first candidate earns expansion, stage
two is the same verified branch on a strictly larger screening population.  If
the first candidate terminates at initial screening, stage two may instead be
a new autonomous H informed by the first ordinary result.  The host chooses no
mechanism, target file, patch, repair or branch action.

This is a development experiment, not a formal acceptance rung.  Validation
and frozen inputs are declared for a complete problem configuration but are
unavailable to H/C and are not authorized for this run.  Promotion is zero.

The one run is
`v04-cvrp-m21-strict-expansion-continuation-20260820` in the fresh root
`/home/clawd/research/scion-experiments/v04-cvrp-m21-strict-expansion-continuation-20260820`.
The user's 2026-08-20 instruction fully authorizes continued experiments after
safe preparation.  It authorizes this bounded one-shot once its clean-carrier,
input, proxy and provider-/solver-free gates pass; it does not authorize root
reuse, resume, input substitution or an automatic retry.

## Carrier and research context

Production baseline is `62142c80`, which adds a problem-neutral normal-run
preflight: when more than one evaluated round is requested, initial screening
must be a strict case subset of expanded screening and the declared split must
contain the expanded population.  The check runs before LLM construction,
provider dispatch or solver work.  The launch binds a clean descendant with an
identical `scion/scion` subtree.

H receives the same problem-owned M7+M18 external input; the prior history
files through M16 and M19; and
`inputs/v04-cvrp-m21-m20-research-history.jsonl`, an exact two-line copy of M20
native ordinary history with SHA256
`cbaa0952fb1a7333fb200cef69d566aa679143b0b150df984d0718b4173e69a8`.
The complete ordered prior contains 27 records.  It includes M20's evaluated
positive `_swap` initial screen and its typed non-evaluated configuration stop.
C receives only the approved current H, current source graph, on-demand peer
source and public development checks.  No campaign database, summary, raw
metric, trace, workspace or old candidate source is reopened.

## Fresh development population

The screening split is new and outcome-blind relative to all earlier committed
experiment inputs.  Initial screening is the exact priority subset
`B-n38-k6`, `P-n50-k7`, `X-n251-k28` with seeds `1135`, `8396`.  Expanded
screening strictly contains it and adds `A-n37-k6`, `P-n22-k8`,
`X-n359-k29`, using the same two seeds.  Thus the normal nested selection is
3 -> 6 cases and 6 -> 12 paired comparisons.

Declared later-development data is validation `A-n39-k5`, `P-n23-k8`,
`X-n439-k37` with seeds `6858`, `9488`, and frozen `A-n63-k10`,
`P-n70-k10`, `X-n502-k39` with seeds `8155`, `5774`.  Canary is the public
tiny case with seed `6419`.  Every instance and companion solution is a regular
non-symlink parsed by the production CVRP loader.  All twelve case paths and
seven seeds are disjoint from earlier committed inputs and from each other as
required.

Measurement, paired arm order, protected fleet objective, practical deltas and
quality gates are unchanged from M20.  `require_expanded_for_pass` remains
true.  Development-screen results are descriptive even if expanded screening
passes; no validation, frozen, promotion, global improvement or production
claim follows.

## Resource and stop boundary

The provider cap is 30, shared by H and C.  At most seven C/Contract/
Verification attempts are possible; Protocol/Safe Feature/Decision has at most
two evaluated stages.  The conservative solver cap is 54 subprocesses:
Verification 14, canary 4 and formal screening 36.  The formal maximum covers
one 3-case initial plus its 6-case expanded screen; two separate initial
screens use fewer subjects.  Nominal/positive-hard-timeout solver seconds are
2,020/2,830.  Provider timeout sum is 6,840 seconds, development pytest 540,
formal Verification pytest 420, and the known guarded sum is 10,630 under a
14,000-second outer hardwall.  Model is `gpt-5.6-terra`, reasoning high, local
proxy, H timeout 120, C timeout 240 and SDK retry zero.

Provider/resource exhaustion, provider or infrastructure failure,
`NOT_EVALUATED`, unknown outcome or interruption stops immediately.  Research
rejection may continue only within the shared cap.  Two evaluated stages stop
as `requested_rounds_completed`.  The run may establish framework continuity,
an incremental mechanism observation and development-screen evidence only; it
cannot claim independent discovery, isolated causality, validation/frozen
success, promotion, global CVRP generalization or v0.4 completion.

## Frozen command

```bash
set -euo pipefail
cd /home/clawd/research/or-autoresearch-agent/scion
test -n "${AUTHORIZED_M21_CARRIER:-}"
test "$(git rev-parse HEAD)" = "$AUTHORIZED_M21_CARRIER"
git diff --quiet
git diff --cached --quiet
REPO_ROOT="$(git rev-parse --show-toplevel)"
test "$REPO_ROOT" = /home/clawd/research/or-autoresearch-agent
git -C "$REPO_ROOT" diff --quiet \
  62142c80 "$AUTHORIZED_M21_CARRIER" -- scion/scion
test ! -e /home/clawd/research/scion-experiments/v04-cvrp-m21-strict-expansion-continuation-20260820
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
  --code-research-limits /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m11-code-research-limits.json \
  --protocol /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m21-strict-expansion-development-protocol.yaml \
  --split /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m21-strict-expansion-development-split.yaml \
  --seeds /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m21-strict-expansion-development-seeds.yaml \
  --time-limit-sec 30 \
  --provider-call-cap 30 \
  --outer-hardwall-sec 14000 \
  --rounds 2 \
  --campaign-dir /home/clawd/research/scion-experiments/v04-cvrp-m21-strict-expansion-continuation-20260820
```

Preparation verifies the exact clean carrier and module origins, all config
loaders, all 27 histories, both external observations, production parsing for
all declared cases/solutions, strict 3 -> 6 nested selection, zero earlier
input overlap, budget arithmetic, sandbox, proxy model metadata and absent
output.  Any failure is `PREP_INVALID` with zero live provider or solver work.
