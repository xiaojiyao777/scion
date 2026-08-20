# CVRP M10 continuous-research continuation preregistration

*Date: 2026-08-20*

*State: `PREPARED_NOT_STARTED / AWAITING_EXPLICIT_ONE_SHOT_AUTHORIZATION`*

## Scientific question

Can the current problem-neutral Scion framework continue a failed CVRP research
line across campaign boundaries: ingest the ordinary M9 hypotheses, patches,
Verification rejection, screening Protocol and Decision; form a new hypothesis
without host-specified repair instructions; inspect the relevant source graph;
revise and publicly test a patch in a bounded sandbox; and produce up to two
formal development-screen observations?

Scion is the research system. CVRP and its solver policy package are the
research object. The host does not choose an action, research surface, target
file, mechanism, patch, test result or next repair. It fixes only the current
question, historical observations, source boundary, development population,
resource limits, stopping rules and claim boundary.

This experiment is named:

`v04-cvrp-m10-continuous-research-m9-history-development-20260820`

It is a longitudinal continuation, not a formal unseen-population confirmation
and not a causal A/B study. M9 is the descriptive historical reference because
it used the same algorithm source and development population. Provider
stochasticity and intervening framework changes prohibit attributing any result
solely to one new module.

## Source and carrier boundary

The exact prepared production baseline is clean commit
`41d2635b742d2f6d0040efbea8f578b3b5a31e7d`. Relative to the terminal M9
carrier, the CVRP policy bytes under `scion/scion/problems/cvrp/policies/` are
unchanged. The intervening source changes are problem-neutral framework changes:

- pair-local Protocol runtime-failure attribution;
- safe current-campaign Contract/Verification rejection observations for H;
- bounded code research and sandboxed public development tests;
- explicit H-only cross-campaign research history;
- target/dependency/caller/test source-graph context selection.

The execution carrier must be a clean descendant containing this document and
its two new ordinary inputs. Before launch, its exact commit replaces
`AUTHORIZED_M10_CARRIER`. The production subtree must have no changes relative
to `41d2635b742d2f6d0040efbea8f578b3b5a31e7d`. Commit hashes here are ordinary
source labels, not authorization receipts or a mutable registry.

## Ordinary inputs

The normal `scion run` entry loads:

- problem: `scion/scion/problems/cvrp/problem.yaml` and its sibling
  `problem-v1.yaml`;
- current research input:
  `docs/experiments/v0.4/inputs/v04-cvrp-m9-m7-fc1-research-input.json`;
- explicit prior history:
  `docs/experiments/v0.4/inputs/v04-cvrp-m10-m9-research-history.jsonl`;
- code-research limits:
  `docs/experiments/v0.4/inputs/v04-cvrp-m10-code-research-limits.json`;
- Protocol, split and seeds: the unchanged M9 development files
  `v04-cvrp-m9-development-{protocol,split,seeds}.yaml`.

The M9 history has exactly two append-ordered records and passes the current
`scion.research_history.step.v1` loader for problem `cvrp`:

1. the route-cap-aware destroy/repair hypothesis, its two-file patch and the
   safe Verification rejection (`V3_unit_tests` failed);
2. the augmenting construction hypothesis, its one-file patch, the screening
   aggregate with two candidate-only runtime failures, and Decision `abandon /
   CANDIDATE_RUNTIME_FAILURE`.

M9 predates the research-history writer. This backfill is therefore a
mechanical projection from the preserved terminal summary, provider responses,
baseline source and raw screening aggregate. It contains full ordinary H and
materialized patch source, safe check names/statuses and the canonical core
screening aggregate. It excludes raw paths, case identities, seeds, stderr,
tracebacks, elapsed check detail, IDs, validation/frozen facts and the large
problem-specific mechanism telemetry. That exclusion is a transport/privacy
policy, not a host-authored repair suggestion.

The current M7 input and the M9 history reach H only. C receives the same
Contract-approved current H plus current source selected by the generic graph.
Historical patch source is explicitly non-authoritative; current B0 source is
the only patch base.

Input SHA-256 values at preparation are:

- M9 history: `3de8368e2be33ce778baf74f13938171ce47770bbb3af06a4253e558339323a0`;
- code-research limits:
  `6470a1113f344ea8ce78442facdb3d60f7b353d59891a81fb885b3babb47f302`.

## Development population and measurement

M10 intentionally reuses the outcome-known M9 development population. This is
the correct population for a repair-continuation question: it can show whether
the next research chain eliminates the previously observed candidate failures,
but it cannot support an unseen-population or generalization claim.

Initial and expanded screening each use the same six cases and two seeds:

- `B-n39-k5`, `P-n22-k2`, `A-n46-k7`, `F-n45-k4`, `X-n195-k51`,
  `X-n256-k16`;
- seeds `3001`, `3011`;
- per-subject limits `30, 30, 30, 30, 45, 60` seconds.

Canary remains `data/tiny_canary.json`, seed `3049`, ten seconds. Reserved M9
validation and frozen values remain valid configuration but are not executed.
No new formal population is selected or exposed.

Measurement remains lexicographic:

1. preserve/minimize protected `fleet_violation`;
2. then minimize `total_distance` with screening practical delta `2.0`.

The Protocol continues to use paired case-median aggregation, the unchanged M9
quality gates, and `require_expanded_for_pass: true`. An initial positive result
therefore requests expanded screening rather than passing directly.

## Agent and code-research condition

The only provider model is `gpt-5.6-terra`, reasoning effort `high`, through
the local Codex proxy. SDK retry remains zero. H timeout is 120 seconds and
every code-research/finalize call has a 240-second timeout.

For each Contract-approved H, C receives a bounded session:

```text
target + transitive local dependencies + callers + public tests
  -> optional read/search of inventoried peer/public source
  -> revise complete typed patch
  -> sandboxed public development tests
  -> optional revise and second test
  -> ready (latest tested revision only)
  -> independent finalize or abandon
  -> formal Patch Contract -> isolated candidate -> Verification
```

The session has at most six research turns plus one final decision, three reads,
three searches and two test calls. It cannot choose a shell command, arbitrary
test path, environment or hidden dataset. Public tests execute in a fresh
network-disabled `bwrap` sandbox with bounded files, bytes, process resources
and time. Raw stdout/stderr and host paths do not return to the provider.
Development checks never satisfy or replace formal Contract or Verification.

## Adaptive two-stage execution

The invocation sets `--rounds 2`. A round is a complete evaluated Protocol
stage, not a provider call.

- If candidate one fails initial screening, Decision may abandon it and the
  second evaluated round may belong to a fresh H/C candidate that sees the
  current-campaign failure in addition to imported M9 history.
- If candidate one requests expanded screening, the second evaluated round is
  its fresh expanded screen; no new H is forced.
- Contract, code-research or Verification rejection may schedule another H
  while the shared provider cap remains.
- After two evaluated stages the campaign stops. Validation, frozen,
  promotion, retained comparison, resume and a second campaign are zero.

This adaptive fork is part of the scientific object. The host does not force a
second candidate when the first candidate earns more evidence.

## Outcomes fixed before execution

### Framework-continuity endpoint

The framework endpoint is positive only if at least one current candidate:

- is generated from an H context containing both imported M9 records;
- obtains a patch through the bounded revise/test/ready/finalize session;
- reruns current Patch Contract and Verification after development checks; and
- reaches a complete screening Protocol, Safe Features and Decision.

The terminal record will also report whether a later H was created and, if so,
whether it received the preceding current-campaign rejection/screening value.
No wording, target or mechanism is required from the provider.

### Research-effectiveness endpoint

M9 candidate two is the descriptive reference:

- candidate-only runtime failures: `2/12`;
- valid pairs: `10/12`;
- case wins/losses/ties: `0/2/4`;
- pair wins/losses/ties: `0/3/9`;
- gate: `fail / SCREENING_FAIL_CASE_QUALITY`;
- Decision: `abandon / CANDIDATE_RUNTIME_FAILURE`.

M10 is a strong positive research result if a screened candidate has no
candidate-only runtime failure or protected-objective regression and reaches
`EXPAND_SCREENING` or `QUEUE_VALIDATE`. It is a partial positive if the two
candidate failures fall to zero but the quality gate still fails. It is mixed
if feasibility improves while case/pair quality worsens or new failure classes
appear. It is negative if no candidate reaches Protocol, candidate-only
failures persist, or every Decision remains `abandon` without a better
development aggregate.

Post-run qualitative analysis may ask whether H used the prior scientific
facts and whether its patch matches its own H, but that analysis cannot change
the preregistered quantitative classification.

### Algorithm claim boundary

Even a strong M10 result is development evidence only. It does not establish:

- independent or unseen-population improvement;
- causal effect of one framework feature;
- validation/frozen success, promotion or retained-B0 superiority;
- global CVRP effectiveness or production readiness.

Any later new-population full funnel requires outcome-blind selection, a new
preregistration, a new resource envelope and separate explicit authorization.

## Resource envelope

H and all code-research/finalize calls share a pre-dispatch provider cap of 18.
The structural maxima are conservative and include rejected attempts:

| Resource | Maximum |
| --- | ---: |
| actual H + code provider requests | 18 |
| H requests / H Contract calls | 18 |
| code requests after the first H | 17 |
| complete H + tested/finalized C sequences | 3 |
| code-research turns per sequence | 6 plus 1 finalize |
| development `test_patch` calls | 6 |
| sandboxed development pytest subprocesses | 12 |
| C Contract / executable Verification calls | 3 |
| Verification solver subprocesses | 6 |
| Verification pytest subprocesses | 6, each at most 60 seconds |
| Protocol / Safe Feature / Decision calls | 2 each |
| Protocol canary solver subprocesses | 4 |
| formal screening solver subprocesses | 48 |
| all solver subprocesses | 58 |
| nominal solver subject-seconds | 2,020 |
| guarded solver seconds, including 15-second guards | 2,890 |
| worst provider timeout seconds (`18 * 240`) | 4,320 |
| development test total wall seconds | 180 |
| Verification pytest hard-timeout seconds | 360 |
| known guarded total | 7,750 seconds |
| `mgr.run` outer hardwall | 9,000 seconds |

The 48 formal subjects are two possible six-case/two-seed/two-arm screens. The
same bound covers two separate initial candidates or initial plus expanded
screening of one candidate. Solver arithmetic is
`Verification 6*30 + canary 4*10 + formal 2*900 = 2020` nominal seconds and
`6*45 + 4*25 + 2*1260 = 2890` guarded seconds.

## Typed stopping rules

- Invalid H/C output, Contract rejection, code-research abandon or
  Verification rejection is `RESEARCH_REJECTED`; it may schedule a fresh H
  only below the shared provider cap.
- Provider cap exhaustion is terminal
  `RESOURCE_EXHAUSTED / PROVIDER_CALL_CAP_EXHAUSTED` before another dispatch.
- Provider auth, rate, timeout, transport or service failure is terminal
  `BLOCKED_INFRA`; SDK/provider retry is zero.
- `NOT_EVALUATED`, other `BLOCKED_INFRA`, `RESOURCE_EXHAUSTED` and
  `INTERRUPTED` stop immediately.
- A canary veto supplies no formal Protocol claim and stops fail-closed.
- Two evaluated Protocol stages stop as `requested_rounds_completed`.
- The 9,000-second watchdog terminates active children and records
  `INTERRUPTED / OUTER_HARDWALL_EXCEEDED`.

There is no repair, resume, deletion/reuse of the output root, case/seed
substitution, extra provider call, third evaluated stage or automatic follow-up
campaign under this authorization envelope.

## Frozen command shape

This command is a prepared shape, not execution authorization:

```bash
set -euo pipefail
cd /home/clawd/research/or-autoresearch-agent/scion

test -n "${AUTHORIZED_M10_CARRIER:-}"
test "$(git rev-parse HEAD)" = "$AUTHORIZED_M10_CARRIER"
git diff --quiet
git diff --cached --quiet
REPO_ROOT="$(git rev-parse --show-toplevel)"
test "$REPO_ROOT" = /home/clawd/research/or-autoresearch-agent
git -C "$REPO_ROOT" diff --quiet \
  41d2635b742d2f6d0040efbea8f578b3b5a31e7d \
  "$AUTHORIZED_M10_CARRIER" -- scion/scion
test ! -e /home/clawd/research/scion-experiments/v04-cvrp-m10-continuous-research-m9-history-development-20260820
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
  --code-research-limits /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m10-code-research-limits.json \
  --protocol /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m9-development-protocol.yaml \
  --split /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m9-development-split.yaml \
  --seeds /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m9-development-seeds.yaml \
  --time-limit-sec 30 \
  --provider-call-cap 18 \
  --outer-hardwall-sec 9000 \
  --rounds 2 \
  --campaign-dir /home/clawd/research/scion-experiments/v04-cvrp-m10-continuous-research-m9-history-development-20260820
```

Before any live request, provider-/solver-free preflight must verify the exact
carrier, clean tracked/index state, module origins, absent output root, all
input loaders, both history records, code limits, development manifests,
sandbox availability, CLI options and the resource arithmetic. Any failure
leaves the experiment `PREP_INVALID` and consumes no launch authorization.

After a clean carrier and independent preflight pass, live execution still
requires one new user instruction naming this experiment, the exact carrier and
the complete one-shot envelope. Preparation alone does not authorize launch.
