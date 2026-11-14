# CVRP R3b adaptive-history K1 preregistration

Date: 2026-08-29 UTC

## Question and estimand

Can a fresh ordinary Scion campaign, starting from CVRP B0 and using only the
problem adapter, autonomously decide whether and how to use the complete
ordinary R3 research history, maintain continuous current/sibling research, and
produce one exact cumulative algorithm candidate that drains screening,
validation and frozen testing and is promoted by deterministic Decision?

The complete claim additionally requires the selected H/C path to have a
self-authored development falsifier that directly exercises the proposed
mechanism and to pass the separate public synthetic large-shape deadline check.
These development diagnostics remain tainted proposal evidence: they are not Safe
Features, Protocol gates or Decision inputs. A deterministic promotion with
missing activation evidence remains a real promotion but is classified
separately as an activation-audit gap.

R3b is a fresh campaign, not a resume, reopen or branch reconstruction of R3.
No R3 workspace, SQLite state, provider-session state, postrun report or
candidate snapshot is loaded.

## Frozen continuity policy

R3b loads exactly one external history file:

`/home/clawd/research/scion-experiments/v04-cvrp-r3-normal-k1-sol-20260828-r1/research_history.jsonl`

It contains 21 ordered ordinary H-only records: 16 screening evaluations and
five typed pre-Protocol research rejections. It contains no validation, frozen,
retained-B0 or BKS evidence. The old records' absent selected-H basis remains an
explicit legacy null; R3b never rewrites the R3 artifact.

The R2 45-record matched-study corpus is not loaded. Its prompt-visible ON
treatment produced no selected-H external read or citation, hence no
attributable uptake or demonstrated benefit. This remains an
availability/index-exposure ITT and does not prove zero indirect content effect.
R3 is the same-problem, same-baseline, same-Protocol direct predecessor and is
the narrower test of cross-campaign continuity.

External R3 history remains agent-optional. Search, read, citation and mechanism
choice belong to the agent; the host does not rank a nearest record. Only R3b's
latest explicit live failures carry the V3-addendum responsibility: for the
latest ordinary `current` and `sibling` relation rounds independently, each
failure must receive an agent-authored `used` or `rejected` disposition before
an H is exported. `used` requires an actual read and selected-H citation;
`rejected` requires a bounded reason but no read. K=2 is not enabled, but its
slot-local semantics remain part of the frozen runtime.

Secondary continuity endpoints are descriptive:

- external R3 search/read/citation counts;
- selected H bases citing R3 refs;
- whether a cited failure is followed by a materially different H/C;
- live-frontier used/rejected completeness;
- ordinary branch depth and exact H/H+patch replay counts.

Only an explicit read/citation with a corresponding research-basis explanation
is called history uptake. This single run cannot prove that history caused an
improvement; causal history benefit still requires a separate matched study.

## Development and held-out interpretation

The existing 12-case screening population is intentionally reused as an
outcome-known adaptive development population. R3 outcomes are known to the
developer and are present in the R3 history supplied to the agent. Screening
therefore provides adaptive training feedback and comparability with R3; it is
not outcome-blind confirmation or generalization evidence.

R3 never reached validation or frozen testing. Those Protocol populations and
their seed ledgers remain unavailable to H, C, Safe Features and scheduling and
provide prospective evidence for any exact R3b candidate. They are not claimed
to be globally unseen across all historical project work. The post-campaign
retained-B0 population remains hidden and cannot run until an exact candidate is
promoted.

The public CVRP development tests use only separate synthetic development
inputs. Their two fixed seeds, `1703` and `1709`, are disjoint from smoke,
controlled, formal and final ledgers; the large shape has 719 customers and does
not reproduce an R3 Protocol case. Problem-owned guidance states timeless
measurement and deadline rules and contains no R3 case, seed or outcome.

## Frozen runtime and resource policy

- model: `gpt-5.6-sol` through the local Codex proxy;
- reasoning effort: `high`;
- hypothesis candidate count: K=1;
- formal evaluated-stage horizon: 20;
- scheduler: ordinary evidence-blind maximum of three active branches;
- provider dispatch cap: 340 (`20 x (8 H + 8 C + 1 C-finalize)`);
- outer hardwall: 345600 seconds (96 hours);
- provider SDK retry: zero;
- common ordinary research input: enabled;
- external history: the single R3 JSONL above;
- within-campaign current/sibling history and failure-frontier review: enabled;
- R2 matched-study history: absent.

The provider cap includes attempts that end in research rejection and is a
censor, not a promise that 20 evaluated stages will complete. Research
rejections do not consume the evaluated-stage horizon. The 20th evaluated stage
is allowed to complete and persist its Decision; a queued next stage is not
drained after the horizon.

## Frozen problem and science inputs

- adapter: `scion/problems/cvrp/problem-v1.yaml`;
- protocol: `scion/problems/cvrp/formal/protocol.yaml`;
- split: `scion/problems/cvrp/formal/split_manifest.yaml`;
- seeds: `scion/problems/cvrp/formal/seed_ledger.yaml`;
- research input: `experiments/cvrp_history_matched_study/research_input.json`;
- code-research limits:
  `docs/experiments/v0.4/inputs/v04-cvrp-m11-code-research-limits.json`;
- problem data root: `/home/clawd/research/or-autoresearch-agent/vrp`;
- output:
  `/home/clawd/research/scion-experiments/v04-cvrp-r3b-normal-k1-sol-20260829-r1`.

`formal/budgets.json` and `formal/matrix.json` both declare 20 evaluated stages.
The Protocol owns dimension-based solver limits; `--time-limit-sec 30` remains
only the declared default. Exact candidates move only through ordinary live
branch state and cannot be reconstructed from summaries or prior roots.

## Launch gate and source freeze

Launch is authorized only after all of the following are true:

1. the full provider-free repository regression passes after the post-R3
   frontier, falsifier, lineage and public-development changes;
2. focused CVRP public deadline and formal-readiness tests pass;
3. the R3 history loads as exactly 21 ordinary `cvrp` records;
4. every declared Protocol case resolves under `SCION_PROBLEM_DATA_ROOT`;
5. the claw Python environment imports all declared runtime dependencies;
6. the output root is absent;
7. a one-time local proxy health/model check succeeds without printing its key.

Items 1-6 are the source-freeze gate. Once they pass, source, public development
tests, Protocol, split, seed ledger, limits, history input and this
preregistration are frozen until the campaign terminates. Item 7 is the first
operation of the frozen block and only authorizes continuing into the CLI; if
it fails, no campaign root is created. The frozen block is executed once, and
the root is never resumed, retried, extended or filled with a substituted fixed
candidate.

Prelaunch evidence recorded on 2026-08-29 UTC satisfies items 1-6: the full
provider-free repository regression passed `2259` tests with one declared skip
in 435.67 seconds; focused CVRP deadline/formal and frontier/CLI checks passed;
the loader observed exactly 21 ordered `cvrp` R3 records; all 37 declared
Protocol cases and 73 required files resolved without a missing, unsafe or
companion error; the claw Python environment loaded every runtime dependency;
and the output root was absent. Item 7 is intentionally evaluated exactly once
by the frozen block below, immediately before launch and before campaign-root
creation. No earlier or repeated proxy/model pre-probe is permitted.

## Frozen launch

```bash
set -euo pipefail

SOURCE=/home/clawd/research/or-autoresearch-agent/scion
DATA_ROOT=/home/clawd/research/or-autoresearch-agent/vrp
R3_HISTORY=/home/clawd/research/scion-experiments/v04-cvrp-r3-normal-k1-sol-20260828-r1/research_history.jsonl
CAMPAIGN_ROOT=/home/clawd/research/scion-experiments/v04-cvrp-r3b-normal-k1-sol-20260829-r1
PYTHON=/home/clawd/miniconda3/envs/claw/bin/python

test ! -e "$CAMPAIGN_ROOT"
test -f "$R3_HISTORY"
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

## Outcome classification

- `PROMOTION_OBSERVED_RETAINED_PENDING`: an exact candidate passes the ordinary
  automatic funnel, is promoted, and has direct self-authored activation
  evidence; independent retained-B0 remains R4.
- `PROMOTION_WITH_ACTIVATION_AUDIT_GAP`: deterministic promotion occurs, but
  exact activation evidence is absent or unavailable. Promotion is not
  retroactively overridden, but R3b's complete-research claim is unmet.
- `VALID_20_STAGE_HORIZON_CENSORED`: 20 evaluated stages complete with an exact
  candidate queued for the next declared stage.
- `VALID_20_STAGE_NO_PROMOTION`: 20 evaluated stages complete without a queued
  exact candidate or promotion.
- `PROVIDER_CAP_CENSORED`: the 340-call cap ends the run before 20 evaluated
  stages. The partial root is not resumed.
- `OUTER_HARDWALL_EXCEEDED`: the 96-hour censor exits 124. The partial root is
  retained and not resumed.
- `RUN_INVALID_INFRA`: a typed environment/provider/framework failure truncates
  the declared run.
- `INTERRUPTED`: another explicit external interruption ends the campaign.

Candidate-attributable timeout, invalid output, infeasibility or fleet
regression in a complete Protocol result is negative algorithm evidence, not
root-level infrastructure. A positive screen is never a promotion, postrun
analysis cannot override Decision, and no retained-B0 evaluation is authorized
before promotion.
