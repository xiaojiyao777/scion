# CVRP R3c adaptive-history K1 preregistration

Date: 2026-08-30 UTC

## Question

Can a fresh ordinary Scion campaign start from CVRP B0, voluntarily use the
complete R3 history plus the one complete R3b initial-screen record, maintain
current/sibling failure-frontier continuity, and produce an exact candidate
that drains screening, validation and frozen testing into deterministic
promotion?

R3c is not a resume or retry of R3b. It has a fresh output root, provider
session, branch state and B0 workspace. No R3b candidate source, SQLite state,
partial expanded counter or process state is loaded. An independently proposed
similar patch remains an ordinary new proposal; the host does not reconstruct
one from history.

## Frozen history policy

Two external H-only files are loaded in this exact order:

1. R3 `research_history.jsonl`: 21 complete ordinary records;
2. R3b `research_history.jsonl`: one complete initial-screen record.

The R3b record says only that its route-distinct regret candidate completed
initial screening and received `expand_screening`. It does not contain the
interrupted expanded work. The R2 45-record heterogeneous corpus remains OFF.

Both external histories remain agent-optional. The host exposes the complete
ordered index but does not rank a reference, choose a mechanism or require an
external read. Mandatory used/rejected disposition applies only to explicit
failures at the latest ordinary live `current` and `sibling` relation rounds,
independently. Used evidence must be read and cited; rejected evidence needs a
bounded agent-authored reason.

Search/read/citation, selected-basis explanation and live-frontier disposition
are reported separately. Uptake is not benefit; this single adaptive run cannot
estimate the causal effect of history.

## Scientific interpretation

Screening is the same outcome-known adaptive development population used by R3
and R3b. It trains and compares research behavior; it is not independent
generalization evidence.

R3 and R3b never reached validation or frozen testing. Those formal inputs
remain unavailable to H, C and scheduling and are prospective for an exact R3c
candidate. Retained-B0 evidence remains blocked until promotion.

The existing activation falsifier and public large-shape deadline checks remain
tainted development diagnostics outside Safe Features and Decision. Missing
exact activation evidence does not reverse a Protocol result or promotion; it
is reported as an audit gap.

## Frozen runtime and inputs

- model: `gpt-5.6-sol` through the local Codex proxy;
- reasoning effort: `high`;
- H candidate count: K=1;
- formal evaluated-stage horizon: 20;
- maximum active branches: three;
- provider dispatch cap: 340;
- outer hardwall: 345600 seconds (96 hours);
- provider SDK retry: zero;
- problem: `scion/problems/cvrp/problem-v1.yaml`;
- protocol: `scion/problems/cvrp/formal/protocol.yaml`;
- split: `scion/problems/cvrp/formal/split_manifest.yaml`;
- seeds: `scion/problems/cvrp/formal/seed_ledger.yaml`;
- research input: `experiments/cvrp_history_matched_study/research_input.json`;
- code-research limits:
  `docs/experiments/v0.4/inputs/v04-cvrp-m11-code-research-limits.json`;
- problem data root: `/home/clawd/research/or-autoresearch-agent/vrp`;
- output root:
  `/home/clawd/research/scion-experiments/v04-cvrp-r3c-normal-k1-sol-20260830-r1`.

Exact candidates progress only through live branch state. A positive screen is
not promotion, and no summary or interrupted partial state can reconstruct a
candidate.

## Launch gate and freeze

Before launch:

1. the full provider-free, non-campaign regression passes after the SIGHUP
   terminalization change;
2. focused signal, history, CVRP deadline and formal-readiness tests pass;
3. the two history files load as exactly 22 ordered `cvrp` records;
4. all declared Protocol cases resolve in the data root;
5. the claw Python environment is available;
6. the output root is absent;
7. one local proxy/model check confirms `gpt-5.6-sol` without printing the key.

Items 1-6 freeze source, public tests, Protocol, split, seeds, limits, histories
and this preregistration. Item 7 runs once immediately before the attached
local launch. Failure creates no campaign root and is not retried.

Prelaunch evidence recorded on 2026-08-30 UTC satisfies items 1-6. The full
provider-free, non-campaign regression passed `2260` tests with one declared
skip in 439.42 seconds after the SIGHUP change. The exact signal, resource,
history and CVRP formal-readiness slice passed `107` tests. The production
loader observed exactly 22 ordered `cvrp` records (21 R3 followed by one R3b),
all 37 declared Protocol cases and 73 required files resolve under the frozen
data root, the claw Python environment imports the runtime dependencies, the
launch block passes shell syntax checking, focused Ruff and `git diff --check`
pass, and the output root is absent. Item 7 has intentionally not been run
separately; it remains the first operation of the one frozen launch block.

Launch uses one ordinary foreground PTY and immediately attaches that session
to this task's Codex terminal panel. If the terminal cannot be attached, the run
is not started. No shell backgrounding, service, scheduler, distribution,
deployment, build, PID registry or identity/hash/receipt lifecycle is allowed.

## Frozen launch

```bash
set -euo pipefail

SOURCE=/home/clawd/research/or-autoresearch-agent/scion
DATA_ROOT=/home/clawd/research/or-autoresearch-agent/vrp
R3_HISTORY=/home/clawd/research/scion-experiments/v04-cvrp-r3-normal-k1-sol-20260828-r1/research_history.jsonl
R3B_HISTORY=/home/clawd/research/scion-experiments/v04-cvrp-r3b-normal-k1-sol-20260829-r1/research_history.jsonl
CAMPAIGN_ROOT=/home/clawd/research/scion-experiments/v04-cvrp-r3c-normal-k1-sol-20260830-r1
PYTHON=/home/clawd/miniconda3/envs/claw/bin/python

test ! -e "$CAMPAIGN_ROOT"
test -f "$R3_HISTORY"
test -f "$R3B_HISTORY"
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
  --code-research-limits "$SOURCE/docs/experiments/v0.4/inputs/v04-cvrp-m11-code-research-limits.json" \
  --protocol "$SOURCE/scion/problems/cvrp/formal/protocol.yaml" \
  --split "$SOURCE/scion/problems/cvrp/formal/split_manifest.yaml" \
  --seeds "$SOURCE/scion/problems/cvrp/formal/seed_ledger.yaml" \
  --time-limit-sec 30 \
  --provider-call-cap 340 \
  --outer-hardwall-sec 345600 \
  --rounds 20 \
  --campaign-dir "$CAMPAIGN_ROOT"
```

The command is run with a PTY. Its returned session is attached immediately to
the current Codex terminal panel before control is yielded. The terminal is not
a scientific authority: campaign status, ordinary metrics and Decision remain
the runtime/scientific records.

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
not root-level infrastructure. A partial stage has no scientific Decision.
