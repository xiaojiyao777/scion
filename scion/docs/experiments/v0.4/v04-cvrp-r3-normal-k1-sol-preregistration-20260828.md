# CVRP R3 normal K1 continuous-research preregistration

Date: 2026-08-28 UTC

## Question and fixed interpretation

Can the ordinary Scion campaign, using only the CVRP adapter and its declared
formal protocol, autonomously produce and preserve an exact algorithm change
that passes screening, expanded screening, validation and frozen testing and is
then promoted by the deterministic Decision layer?

This is a fresh normal campaign. It is not a continuation or reconstruction of
an r5 branch. The r5 matched study remains development evidence only. No r5
workspace, SQLite state or external 45-record history corpus is an input.

## Frozen research policy

- model: `gpt-5.6-sol` through the local Codex proxy;
- reasoning effort: `high`;
- hypothesis candidate count: K=1;
- formal evaluated-stage horizon: 16;
- scheduler: the ordinary evidence-blind maximum of three active branches;
- provider dispatch cap: 272, the K1 mechanical maximum of 17 calls for each
  of 16 newly researched formal opportunities;
- outer hardwall: 216000 seconds (60 hours);
- automatic provider retry: zero;
- common ordinary observations: enabled through the fixed research input;
- within-campaign current/sibling history: enabled and agent-optional;
- external `--research-history`: absent.

K1 is selected because r5 produced a formal H at every opportunity not consumed
by exact-candidate expansion. Candidate quality, not formal-proposal yield, was
the observed bottleneck. There is no matched evidence that K2's extra provider
cost improves quality.

## Frozen problem and science inputs

- adapter: `scion/problems/cvrp/problem-v1.yaml`;
- protocol: `scion/problems/cvrp/formal/protocol.yaml`;
- split: `scion/problems/cvrp/formal/split_manifest.yaml`;
- seeds: `scion/problems/cvrp/formal/seed_ledger.yaml`;
- research input: `experiments/cvrp_history_matched_study/research_input.json`;
- code-research limits:
  `docs/experiments/v0.4/inputs/v04-cvrp-m11-code-research-limits.json`;
- problem data root: `/home/clawd/research/or-autoresearch-agent/vrp`;
- output: `/home/clawd/research/scion-experiments/v04-cvrp-r3-normal-k1-sol-20260828-r1`.

The protocol owns its dimension-based solver limits; `--time-limit-sec 30` is
only the declared default. Validation and frozen cases remain unavailable to H,
C, Safe Features and scheduling. Exact candidates advance through ordinary
branch state; no summary-based candidate reconstruction is allowed.

The correct runtime is
`/home/clawd/miniconda3/envs/claw/bin/python`. The base conda interpreter is
invalid because it lacks the declared NumPy dependency.

## Prelaunch correction and final source freeze

The full default suite found one framework exception before launch: when every
solver pair failed, no declared objective row existed and the stats layer raised
on the absent effect metric instead of returning typed negative Protocol
evidence. The correction permits an unobserved statistical metric only when
`valid_pairs == 0`, case-level results exist and every metric row is empty. It
does not synthesize `total_distance`; any valid pair, any observed metric row or
any declared-metric mismatch remains strict and raises.

The corrected CVRP integration returns `fail`, two static case losses, four
candidate failures and no statistical metric. Focused Protocol/stats tests
passed, unit tests passed `1106`, readiness tests passed `16`, and the final
default suite passed `2203` with one expected skip. No provider request or
formal R3 solver run occurred during correction. Cases, seeds, gates, model,
history policy, candidate policy and resource limits are unchanged. This record
is the final prelaunch source freeze; no source or formal input is edited after
it while the campaign is live.

## Frozen launch

```bash
set -euo pipefail

SOURCE=/home/clawd/research/or-autoresearch-agent/scion
DATA_ROOT=/home/clawd/research/or-autoresearch-agent/vrp
CAMPAIGN_ROOT=/home/clawd/research/scion-experiments/v04-cvrp-r3-normal-k1-sol-20260828-r1
PYTHON=/home/clawd/miniconda3/envs/claw/bin/python

test ! -e "$CAMPAIGN_ROOT"
test -x "$PYTHON"

proxy_key_value=$(curl -fsS --connect-timeout 5 --max-time 15 \
  http://127.0.0.1:8080/auth/status | \
  jq -er '.proxy_api_key | select(type == "string" and length > 0)')
trap 'unset proxy_key_value' EXIT

curl -fsS --connect-timeout 5 --max-time 15 \
  -H "Authorization: Bearer $proxy_key_value" \
  http://127.0.0.1:8080/v1/models | \
  jq -e --arg model gpt-5.6-sol \
    'any(.data[]?; .id == $model)' >/dev/null

cd "$SOURCE"
PYTHONDONTWRITEBYTECODE=1 \
PYTHONPATH="$SOURCE" \
SCION_PROBLEM_DATA_ROOT="$DATA_ROOT" \
SCION_MODEL=gpt-5.6-sol \
SCION_REASONING_EFFORT=high \
SCION_BASE_URL=http://127.0.0.1:8080 \
SCION_API_KEY="$proxy_key_value" \
SCION_LLM_TIMEOUT_SEC=120 \
SCION_LLM_HYPOTHESIS_RESEARCH_TURN_TIMEOUT_SEC=120 \
SCION_LLM_CODE_RESEARCH_TURN_TIMEOUT_SEC=240 \
SCION_LLM_CODE_RESEARCH_FINALIZE_TIMEOUT_SEC=240 \
"$PYTHON" -B -m scion.cli.main run \
  --problem "$SOURCE/scion/problems/cvrp/problem-v1.yaml" \
  --research-input "$SOURCE/experiments/cvrp_history_matched_study/research_input.json" \
  --code-research-limits "$SOURCE/docs/experiments/v0.4/inputs/v04-cvrp-m11-code-research-limits.json" \
  --protocol "$SOURCE/scion/problems/cvrp/formal/protocol.yaml" \
  --split "$SOURCE/scion/problems/cvrp/formal/split_manifest.yaml" \
  --seeds "$SOURCE/scion/problems/cvrp/formal/seed_ledger.yaml" \
  --time-limit-sec 30 \
  --provider-call-cap 272 \
  --outer-hardwall-sec 216000 \
  --rounds 16 \
  --campaign-dir "$CAMPAIGN_ROOT"
```

Launch once into the absent root. Do not edit the source tree while the campaign
is live, resume an interrupted root, retry a failed provider call, extend the
horizon after seeing results or substitute a fixed candidate.

## Outcomes

- `PROMOTION_OBSERVED_RETAINED_PENDING`: an exact candidate passes the full
  automatic funnel and is promoted; independent retained-B0 evidence remains
  R4.
- `VALID_16_STAGE_HORIZON_CENSORED`: 16 evaluated stages complete with an exact
  candidate queued for its next declared stage.
- `VALID_16_STAGE_NO_PROMOTION`: 16 evaluated stages complete without a queued
  candidate or promotion.
- `RUN_INVALID_INFRA`: a typed provider, environment or framework failure
  truncates the horizon. The root is retained as evidence and is never resumed.
- `OUTER_HARDWALL_EXCEEDED`: the 60-hour censor fires. The CLI records the
  actual typed interruption reason `OUTER_HARDWALL_EXCEEDED` and exits 124; the
  partial root is not a valid 16-stage result and is never resumed.
- `INTERRUPTED`: another explicit external interruption ends the campaign.

Candidate-attributable timeout, invalid output or infeasibility that produces a
complete Protocol result is algorithm evidence, not root-level infrastructure.
No positive screen is a promotion, and no postrun score may override Decision.

## Postrun disposition

The one frozen launch completed normally on 2026-08-29 and is classified
`VALID_16_STAGE_NO_PROMOTION`: 16/16 evaluated screening stages, five typed
research rejections, no validation/frozen stage and no promotion. Champion v1
is unchanged. The complete evidence audit is recorded in
[`v04-cvrp-r3-normal-k1-sol-postrun-20260829.md`](v04-cvrp-r3-normal-k1-sol-postrun-20260829.md).
