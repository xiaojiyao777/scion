# CVRP R3d adaptive-history K1 preregistration

Date: 2026-08-30 UTC

## Question

After the bounded provider-transient repair, can a fresh ordinary Scion
campaign start from CVRP B0, voluntarily use the complete R3, R3b and R3c
ordinary histories, maintain current/sibling failure-frontier continuity, and
produce an exact candidate that drains screening, validation and frozen
testing into deterministic promotion?

R3d is a new experiment after an infrastructure repair, not a resume or
campaign-level retry of R3c. It has a fresh output root, B0 workspace, branch
state and provider session. It loads no prior candidate source, SQLite file,
status file, workspace, process state, partial provider response or expanded
counter. A similar proposal must be independently selected and generated in
the new campaign.

The terminal R3c root remains untouched.

## Frozen history policy

Three external H-only files are loaded in this exact order:

1. R3 `research_history.jsonl`: 21 complete ordinary records;
2. R3b `research_history.jsonl`: one complete initial-screen record;
3. R3c `research_history.jsonl`: two complete typed records, one evaluated
   initial screen followed by one proposal-hypothesis infrastructure block.

The concatenation is exactly 24 strict `cvrp` records. Validation, frozen and
retained-B0 evidence is absent. The older R2 45-record heterogeneous corpus
remains OFF.

External history remains agent-optional. The host exposes the complete ordered
index but does not rank a reference, choose a mechanism, copy a patch or require
an external read. Mandatory used/rejected disposition applies only to explicit
failures at the latest ordinary live `current` and `sibling` relation rounds,
independently. Used evidence must be read and cited; rejected evidence needs a
bounded agent-authored reason.

Search, read, citation, selected-basis explanation and frontier disposition are
reported separately. Uptake requires an actual read and citation. This single
adaptive campaign cannot identify the causal benefit of history.

## Scientific inputs and interpretation

The formal problem and science inputs are unchanged from R3c:

- adapter: `scion/problems/cvrp/problem-v1.yaml`;
- Protocol: `scion/problems/cvrp/formal/protocol.yaml`;
- split: `scion/problems/cvrp/formal/split_manifest.yaml`;
- seeds: `scion/problems/cvrp/formal/seed_ledger.yaml`;
- research input:
  `experiments/cvrp_history_matched_study/research_input.json`;
- code-research limits:
  `docs/experiments/v0.4/inputs/v04-cvrp-m11-code-research-limits.json`;
- problem data root: `/home/clawd/research/or-autoresearch-agent/vrp`.

The split remains 12 screening, 12 validation and 12 frozen cases plus one
canary. Screening is the same outcome-known adaptive development population
used by R3, R3b and R3c; it is not independent generalization evidence.
Validation and frozen inputs have not been exposed by those campaigns and
remain prospective for an exact R3d candidate. Retained-B0 evaluation remains
blocked until promotion.

The existing activation falsifier and public synthetic large-shape deadline
checks remain tainted development diagnostics outside Safe Features and
Decision. Missing activation evidence cannot reverse Protocol or promotion;
it is reported as an audit gap.

## Frozen transient-dispatch boundary

Provider SDK retries remain zero. R3d explicitly sets
`--provider-transient-retries 1`. ProviderCaller may therefore redispatch the
same frozen request once, and only once, when the first dispatch raises one of
these typed faults:

- `LLMTimeoutError`;
- `LLMTransportError`;
- `LLMProviderError`.

Rate limit/429, authentication, authorization, balance, response-format,
schema, response-size, generic and interruption failures are not eligible. The
allowlist is type-based; no message/status regular-expression search, recursive
cause walk or object-identity mechanism expands it.

Every physical dispatch is charged against the same 340-call cap immediately
before it is sent and receives one terminal trace. A redispatch uses the same
request policy and remains within the same H/C logical turn. Retry eligibility,
attempt ordinals and prior transient failure details are operational evidence
only: they are not supplied to H and do not enter research history, Protocol or
Decision. The cap is not enlarged to compensate for a redispatch.

If the cap cannot admit the second dispatch, the existing resource-exhausted
outcome applies. If the second eligible dispatch also fails, the existing
blocked-infrastructure outcome applies. A returned response that fails format
or schema validation is terminal and is not redispatched.

No exactly-once property is claimed. A timed-out first request may remain in
flight upstream, but Scion never observes or uses a later response from it.
This boundary introduces no request identity, lease, issuance, registration,
signature, receipt, request hash or repeated finalization lifecycle.

## Frozen runtime and resources

- model: `gpt-5.6-sol` through the local Codex proxy;
- reasoning effort: `high`;
- H candidate count: K=1;
- H maximum turns per attempt: eight;
- C research maximum turns per attempt: eight, plus one final decision;
- formal evaluated-stage horizon: 20;
- ordinary maximum active branches: three;
- physical provider dispatch cap: 340;
- outer hardwall: 345600 seconds (96 hours);
- provider SDK retries: zero;
- explicit Scion transient redispatches per frozen request: one;
- output root:
  `/home/clawd/research/scion-experiments/v04-cvrp-r3d-normal-k1-sol-20260830-r1`.

The original cap remains `20 x (8 H + 8 C + 1 C-finalize) = 340`. A transient
redispatch consumes that fixed allowance and can therefore censor the logical
horizon earlier. Research rejections also consume provider dispatches but not
the evaluated-stage horizon. Exact candidates move only through new live
branch state; no history summary can reconstruct one.

## Launch gate and freeze

Launch is authorized only after all of the following are true:

1. the full provider-free, non-campaign regression passes after the bounded
   transient-dispatch change;
2. focused ResourceEnvelope, ProviderCaller, transport classification,
   history and CVRP formal-readiness tests pass;
3. the three history files load as exactly 24 ordered strict `cvrp` records in
   the order R3, R3b, R3c;
4. all 37 declared split cases and all 73 required files resolve under the
   frozen data root;
5. the claw Python environment imports the runtime dependencies;
6. the fresh R3d output root is absent;
7. one local proxy/model check confirms `gpt-5.6-sol` without printing the
   proxy key.

Items 1-6 are provider-free and freeze source, public tests, Protocol, split,
seeds, limits, ordered histories and this preregistration. Their concrete pass
evidence must be recorded before execution. Item 7 is intentionally neither
run during preparation nor repeated: it is the only network precondition in
the one frozen launch block below. If that check fails, no campaign root is
created and the block is not retried.

Prelaunch evidence recorded on 2026-08-30 UTC satisfies items 1-6. The full
provider-free, non-campaign suite passed `2293` tests with one declared skip in
452.12 seconds (`2294` collected, zero failures). The focused ProviderCaller,
ResourceEnvelope, CLI, transport, proposal-transition and research-history
slice passed `213` tests; the adjacent trace/campaign/resource slice passed
`85`. Focused Ruff `E9,F,I` and `git diff --check` pass, and an independent
minimal-boundary review found no P0/P1. The production history loader observes
exactly 24 ordered strict `cvrp` records (`21 + 1 + 2`), all 37 declared split
cases and 73 required files resolve under the unchanged data root, the claw
Python runtime imports successfully, the frozen launch block passes shell
syntax checking, and the R3d output root is absent. Item 7 has not been run
separately; it remains the only network check before the foreground launch.

Launch uses one ordinary foreground PTY and immediately attaches that session
to the current Codex terminal panel. If attachment is unavailable, the
campaign is not started. There is no shell backgrounding, service, scheduler,
distribution, deployment or build work, and no process registry or lifecycle
authority.

## Frozen launch

```bash
set -euo pipefail

SOURCE=/home/clawd/research/or-autoresearch-agent/scion
DATA_ROOT=/home/clawd/research/or-autoresearch-agent/vrp
R3_HISTORY=/home/clawd/research/scion-experiments/v04-cvrp-r3-normal-k1-sol-20260828-r1/research_history.jsonl
R3B_HISTORY=/home/clawd/research/scion-experiments/v04-cvrp-r3b-normal-k1-sol-20260829-r1/research_history.jsonl
R3C_HISTORY=/home/clawd/research/scion-experiments/v04-cvrp-r3c-normal-k1-sol-20260830-r1/research_history.jsonl
CAMPAIGN_ROOT=/home/clawd/research/scion-experiments/v04-cvrp-r3d-normal-k1-sol-20260830-r1
PYTHON=/home/clawd/miniconda3/envs/claw/bin/python

test ! -e "$CAMPAIGN_ROOT"
test -f "$R3_HISTORY"
test -f "$R3B_HISTORY"
test -f "$R3C_HISTORY"
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
  --research-history "$R3_HISTORY" \
  --research-history "$R3B_HISTORY" \
  --research-history "$R3C_HISTORY" \
  --code-research-limits "$SOURCE/docs/experiments/v0.4/inputs/v04-cvrp-m11-code-research-limits.json" \
  --protocol "$SOURCE/scion/problems/cvrp/formal/protocol.yaml" \
  --split "$SOURCE/scion/problems/cvrp/formal/split_manifest.yaml" \
  --seeds "$SOURCE/scion/problems/cvrp/formal/seed_ledger.yaml" \
  --time-limit-sec 30 \
  --provider-call-cap 340 \
  --provider-transient-retries 1 \
  --outer-hardwall-sec 345600 \
  --rounds 20 \
  --campaign-dir "$CAMPAIGN_ROOT"
```

The command runs in the foreground with a PTY. Its returned session is attached
immediately to this task's terminal panel before control is yielded. The
terminal is not a scientific authority: campaign status, ordinary metrics and
Decision remain the runtime/scientific records.

## Outcome classification

- `PROMOTION_OBSERVED_RETAINED_PENDING`
- `PROMOTION_WITH_ACTIVATION_AUDIT_GAP`
- `VALID_20_STAGE_HORIZON_CENSORED`
- `VALID_20_STAGE_NO_PROMOTION`
- `PROVIDER_CAP_CENSORED`
- `OUTER_HARDWALL_EXCEEDED`
- `RUN_INVALID_INFRA`
- `INTERRUPTED`

Candidate-attributable timeout, invalid output, infeasibility or fleet
regression in a complete Protocol result remains negative algorithm evidence,
not root-level infrastructure. A partial stage has no scientific Decision. A
positive screen is not promotion, postrun analysis cannot override Decision,
and retained-B0 is unauthorized before promotion.
