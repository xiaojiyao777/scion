# CVRP M12 corrected development-closure continuation preregistration

*Date: 2026-08-20*

*State: `PREPARED_NOT_STARTED / USER_DELEGATED_ONE_SHOT_AUTHORIZATION`*

## Scientific question

Can Scion use the ordinary M9, M10 and M11 research histories after correcting
the CVRP public-development package closure to produce at least one formal CVRP
development-screen observation without a host-specified target, mechanism,
patch or repair?

The experiment is:

`v04-cvrp-m12-corrected-development-closure-continuation-20260820`

It is a longitudinal, treatment-only continuation. It is not an independent
A/B comparison, unseen-population confirmation or causal estimate of one
framework change. M9 through M11 are descriptive historical references. The user
has delegated authority to continue bounded experiments; this document freezes
the exact one-shot M12 condition before any M12 provider or solver call.

## Source boundary

The exact production baseline is clean commit
`0860331b3e53993608db0da7ba9c677e980e588d`. Relative to M11 it changes only
the CVRP problem-owned public development manifest: the frozen, read-only
`policies/__init__.py` and `policies/baseline_modules/__init__.py` package
markers are copied into the development scratch. This corrects a tool-closure
failure where D4 observed `policies.__file__ is None`; it does not change any
CVRP algorithm source, generic core behavior, formal gate or population.

The M11 scheduler and 2-for-1 drafts were replayed after the correction and
both passed D1-D4 in the real bounded sandbox. These are non-evidentiary host
diagnostics, not formal Verification or algorithm-effect evidence. The
execution carrier must be a clean descendant containing this preregistration
and the copied M11 terminal history. Its exact commit is
bound as `AUTHORIZED_M12_CARRIER`. The `scion/scion` production subtree must be
identical to `0860331b3e53993608db0da7ba9c677e980e588d`.

## Ordinary research inputs

The normal CLI receives, in order:

1. the M7 structured research input;
2. the two-record M9 history used by M10;
3. the five-record M10 history prepared for M11;
4. the three-record terminal M11 history;
5. the unchanged M11 code-research limits;
6. unchanged M9 development Protocol, split and seed files.

The five M10 records are a mechanical projection of the immutable M10 terminal
history and provider traces:

- two draft patches rejected for duplicate file declarations;
- two complete `config.py` drafts whose D1 syntax, D1b names, D2 interface and
  D3 public unit checks passed while D4 public regression failed;
- one complete draft stopped by the global provider cap before development
  testing.

The projection contains ordinary H values, materialized draft source, safe
check names/status and typed outcomes. It excludes raw subprocess output,
tracebacks, child messages, host paths, IDs, seeds, case identities,
validation/frozen facts and any host-authored repair. Historical patch source
is non-authoritative; the current carrier source is the sole patch base.

The M11 history is copied byte-for-byte from the immutable M11 campaign
terminal and contains three H values and typed Proposal outcomes. It does not
reinterpret the false D4 failures as algorithm evidence and contains no host
repair instruction. All three history files and the M7 observation reach H
only. C receives the current
Contract-approved H plus the current generic source graph and public development
tests. Protocol, Safe Features and Decision do not consume the imported history.

Prepared input SHA-256 values are:

- M10 history: `edc6ea50db856b60216805497c63f713780142d0790bfa754877ca5050541cc1`;
- M11 terminal history:
  `440ce00c09ddb68dfce8a7570181f746426a9bf6c11cd2ff8d70baa5148cd40b`;
- M11 code-research limits:
  `da906dba9b1a6b4e20bcc3d98da32cb9a47216386085ac99e6b0a05923ec1342`.

## Development population and measurement

M12 intentionally reuses the outcome-known M9/M10/M11 development population to
test repair continuity:

- screening cases: `B-n39-k5`, `P-n22-k2`, `A-n46-k7`, `F-n45-k4`,
  `X-n195-k51`, `X-n256-k16`;
- screening seeds: `3001`, `3011`;
- per-subject time limits: `30, 30, 30, 30, 45, 60` seconds;
- canary: `data/tiny_canary.json`, seed `3049`, ten seconds.

Validation and frozen configuration remain reserved and are not executed.
Measurement remains lexicographic: preserve/minimize `fleet_violation`, then
minimize `total_distance` with practical delta `2.0`. Paired case-median
aggregation, quality gates and `require_expanded_for_pass: true` are unchanged.

## Agent and bounded C condition

Provider is `gpt-5.6-terra`, reasoning effort `high`, through the local Codex
proxy, with SDK retry zero. H timeout is 120 seconds; C turns and finalize each
have a 240-second timeout.

For every approved H, C may use at most:

- eight source-research actions and one independent finalize/abandon decision;
- four exact reads and four literal searches;
- three full-patch revisions tested in a fresh public `bwrap` sandbox;
- 90 cumulative development-test seconds;
- 1,500,000 actual provider-wire transcript characters.

A failed revise returns only a correction enum such as
`duplicate_file_path`, `selector_not_found`, `source_not_read` or
`invalid_patch_path`. A development subprocess returns only D1-D4 status, a
host-enumerated reason such as `pytest_test_failure`, and the already-public
canonical test path. It never returns child-controlled text. Development
checks are non-evidentiary and cannot satisfy or bypass formal Patch Contract,
Verification, canary or Protocol.

## Adaptive execution

`--rounds 2` permits no more than two evaluated Protocol stages:

- a failed initial candidate may be followed by a fresh H/C candidate;
- an initial candidate requesting expanded screening uses the second stage for
  that same candidate;
- pre-Protocol rejection may schedule another H only below the shared provider
  cap;
- validation, frozen, promotion, resume and an automatic follow-up campaign
  remain zero.

The host does not force a particular direction or require a second candidate.

## Preregistered endpoints

### Framework endpoint

Positive only if at least one current candidate completes bounded
revise/test/ready/finalize, reruns current Patch Contract and Verification, and
reaches a complete screening Protocol, Safe Features and Decision. Merely
generating H, passing development tests or consuming the provider budget is not
positive.

### Research-effectiveness endpoint

The M9 screened reference had two candidate-only failures in 12 attempts,
10 valid pairs, case `0/2/4` wins/losses/ties, pair `0/3/9`, gate
`SCREENING_FAIL_CASE_QUALITY`, and Decision
`abandon / CANDIDATE_RUNTIME_FAILURE`.

- strong positive: candidate-only failures are zero, no protected regression,
  and Decision is `EXPAND_SCREENING` or `QUEUE_VALIDATE`;
- partial positive: candidate-only failures fall to zero but the quality gate
  still fails;
- mixed: feasibility improves while quality worsens or a new failure appears;
- negative: no candidate reaches Protocol, candidate-only failures persist, or
  all screened candidates remain abandon without a better aggregate.

Any result remains development evidence only. It cannot establish unseen
generalization, causal attribution, validation/frozen success, promotion,
retained-B0 superiority, global CVRP improvement or production readiness.

## Resource envelope

All H/C/finalize calls share a pre-dispatch provider cap of 30.

| Resource | Maximum |
| --- | ---: |
| actual H + code provider requests | 30 |
| code-research turns per session | 8 plus 1 finalize |
| complete minimal H/C/finalize sequences | 6 |
| development `test_patch` calls | 18 |
| sandboxed development pytest subprocesses | 36 |
| formal Patch Contract / Verification calls | 6 each |
| Verification solver subprocesses | 12 |
| Verification pytest subprocesses | 12, each at most 60 seconds |
| Protocol / Safe Feature / Decision calls | 2 each |
| Protocol canary solver subprocesses | 4 |
| formal screening solver subprocesses | 48 |
| all solver subprocesses | 64 |
| nominal solver subject-seconds | 2,200 |
| guarded solver seconds | 3,160 |
| worst provider timeout seconds | 6,840 |
| cumulative development-test seconds | 540 |
| Verification pytest hard-timeout seconds | 720 |
| known guarded total | 11,260 seconds |
| `mgr.run` outer hardwall | 13,500 seconds |

Solver arithmetic is `Verification 12*30 + canary 4*10 + formal 2*900 =
2200` nominal seconds and `12*45 + 4*25 + 2*1260 = 3160` guarded seconds.
Provider arithmetic is the worst locally admissible mix of three H requests and
27 code/finalize requests: `3*120 + 27*240 = 6840` seconds.

## Typed stopping rules

- Invalid H, correctable patch exhaustion, explicit abandon, Contract rejection
  or Verification rejection is `RESEARCH_REJECTED` and may schedule another H
  only below the global cap.
- Provider cap exhaustion is terminal
  `RESOURCE_EXHAUSTED / PROVIDER_CALL_CAP_EXHAUSTED` before dispatch.
- Auth, rate, timeout, transport or service faults are terminal
  `BLOCKED_INFRA`; provider retry is zero.
- Other `NOT_EVALUATED`, `BLOCKED_INFRA`, `RESOURCE_EXHAUSTED` or
  `INTERRUPTED` outcomes stop immediately.
- A canary veto supplies no formal Protocol claim and stops fail-closed.
- Two evaluated stages stop as `requested_rounds_completed`.
- The 13,500-second watchdog kills active children and records
  `INTERRUPTED / OUTER_HARDWALL_EXCEEDED`.

There is no output-root reuse, retry, resume, repair by the host, case/seed
substitution, extra provider call, third evaluated stage or automatic M13.

## Frozen command

```bash
set -euo pipefail
cd /home/clawd/research/or-autoresearch-agent/scion

test -n "${AUTHORIZED_M12_CARRIER:-}"
test "$(git rev-parse HEAD)" = "$AUTHORIZED_M12_CARRIER"
git diff --quiet
git diff --cached --quiet
REPO_ROOT="$(git rev-parse --show-toplevel)"
test "$REPO_ROOT" = /home/clawd/research/or-autoresearch-agent
git -C "$REPO_ROOT" diff --quiet \
  0860331b3e53993608db0da7ba9c677e980e588d \
  "$AUTHORIZED_M12_CARRIER" -- scion/scion
test ! -e /home/clawd/research/scion-experiments/v04-cvrp-m12-corrected-development-closure-continuation-20260820
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
  --code-research-limits /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m11-code-research-limits.json \
  --protocol /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m9-development-protocol.yaml \
  --split /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m9-development-split.yaml \
  --seeds /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m9-development-seeds.yaml \
  --time-limit-sec 30 \
  --provider-call-cap 30 \
  --outer-hardwall-sec 13500 \
  --rounds 2 \
  --campaign-dir /home/clawd/research/scion-experiments/v04-cvrp-m12-corrected-development-closure-continuation-20260820
```

Before launch, provider-/solver-free preflight must verify the exact clean
carrier, module origins, loaders, ten ordered history records, public
development closure, sandbox, unchanged population, resource arithmetic and
absent output. Failure leaves M12 `PREP_INVALID` and performs no live request.
The user's delegated authorization applies only to this frozen one-shot after
those gates pass; it does not authorize retry or automatic follow-up.

## Terminal record

M12 was launched once from clean carrier
`342a43d2d91e615cb05f7bca0a1c2322b0804a76`. It is terminal and will not be
retried. The campaign used 25 provider calls: three H calls, nineteen bounded C
research turns and three independent finalize/abandon calls.

The first attempt proposed regret-4 repair and abandoned after invalid
duplicate-file edit payloads. The second proposed elapsed-budget annealing;
its latest draft passed public D1-D4, but the then-current session required an
additional `ready` provider turn before independent finalize and rejected the
otherwise unchanged draft as `PATCH_PROPOSAL_INVALID`. The third proposed a
deterministic bounded packing fallback, passed bounded development checks,
formal Patch Contract, Verification and canary, and completed the full
six-case/two-seed screening stage.

The durable raw Protocol result is complete: 12 attempted pairs, 10 valid and
2 invalid. The invalid pairs are the two `X-n256-k16` seeds and are attributed
bilaterally because champion and candidate reported the same solver-algorithm
packing failure. Candidate-only failures are therefore zero after bilateral
attribution. Across the five valid case aggregates, the candidate has two wins
(`A-n46-k7`, `X-n195-k51`), one loss (`F-n45-k4`) and two ties (`B-n39-k5`,
`P-n22-k2`). The gate is `fail / SCREENING_FAIL_CASE_QUALITY` with
`SCREENING_PARTIAL_CHAMPION_EVIDENCE`; no validation, frozen, promotion or
retention stage ran.

After Protocol completion, ordinary history projection rejected the canonical
safe aggregate field `case_feedback[].seed_pattern`. The CLI caught the
`ValueError` and wrote `stopped / unhandled_exception`; the durable status has
two research-rejected steps, one unknown outcome, zero evaluated rounds and an
invalid run-validity projection. It does not contain the third StepRecord,
Safe Features or Decision, so M12 is not described as a valid completed
campaign even though its raw screening metrics are durable. The exact output
root is preserved at
`/home/clawd/research/scion-experiments/v04-cvrp-m12-corrected-development-closure-continuation-20260820`.

The generic correction is commit
`7737bb0a`: canonical case-level `seed_pattern` and `seed_consistency` are
accepted only at the strict screening projection location, while arbitrary
open problem evidence still cannot carry seed values. The same commit makes a
latest unchanged draft eligible for independent finalize immediately after
its public development checks pass; any later revision clears eligibility.
These fixes do not alter CVRP algorithms, the M12 population, Protocol gates
or its terminal evidence.
