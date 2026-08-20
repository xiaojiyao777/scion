# CVRP M13 history-safe continuous research preregistration

**State:** `PREPARED_NOT_STARTED`

## Research question

Can Scion start again from the exact B0 source, use the ordered M9-M12 ordinary
research history, and autonomously propose, implement, development-test,
formally verify and screen up to two new CVRP candidates after the M12 terminal
history bug is corrected, without host-selected patch, file, mechanism or
repair direction?

## Label and one-shot boundary

The only run described here is
`v04-cvrp-m13-history-safe-continuation-20260820`. It uses the fresh output root
`/home/clawd/research/scion-experiments/v04-cvrp-m13-history-safe-continuation-20260820`.
That root must be absent before launch. The invocation is one-shot: no reuse,
resume, deletion, retry, replacement, case/seed substitution or automatic M14.

The user's 2026-08-20 instruction to continue trying and full authorization to
run experiments delegates this bounded follow-up after its clean carrier and
provider-/solver-free preparation gates pass.

## Carrier and framework condition

The production baseline is `7737bb0a`. Relative to M12 it makes two generic
changes only:

1. canonical screening `case_feedback[].seed_pattern` and
   `seed_consistency` are accepted only at the strict history projection
   location; open problem evidence still cannot carry seed values; and
2. the latest unchanged draft is eligible for the independent finalize or
   abandon decision immediately after its bounded public development checks
   pass. A later revision clears eligibility. The explicit `ready` action
   remains an optional early-stop action.

No CVRP algorithm, population, Protocol threshold, Safe Feature or Decision
rule changes. The exact clean descendant commit is bound at launch as
`AUTHORIZED_M13_CARRIER`, and its `scion/scion` production subtree must equal
`7737bb0a`.

## Ordinary prior research

H receives, in this exact file and line order:

1. the M7 structured research input used since M9;
2. the two-record M9 history;
3. the five-record M10 history;
4. the three-record M11 history; and
5. `inputs/v04-cvrp-m13-m12-research-history.jsonl`, three records, SHA256
   `c17dc4523a0d34632324022a17833387a5c08c083e29e3b4625b831b16c0a857`.

The M12 file copies its two durable rejection records byte-for-byte. Its third
record is mechanically recovered and normalized once from four preserved
ordinary sources: the H provider response, final candidate source, complete
Protocol metrics and SQLite experiment event. It contains the H, one current
step patch, evaluated screening aggregate and durable `continue_explore`
Decision. It excludes raw paths, case IDs, seeds, stderr, branch/campaign IDs
and held-out observations. Production `load_research_histories` must accept all
three records before launch. Runtime Scion reads only this committed JSONL; it
does not query the old M12 database, metrics, summary or workspace.

Current source remains authoritative. Historical patch source is an ordinary
research observation, not a patch to apply and not an accepted candidate.
History is exposed to H only; C receives the Contract-approved current H and
the current source graph.

## Agent and code-research condition

- model: `gpt-5.6-terra`, reasoning `high`, local proxy only;
- provider SDK retry: zero;
- H timeout: 120 seconds; C/research/finalize timeout: 240 seconds;
- shared H+C provider-call cap: 30, consumed immediately before dispatch;
- unchanged bounded code-research limits from M11;
- public development tests run only in the isolated problem-declared sandbox;
- development results are ordinary repair observations and never substitute
  for formal Patch Contract or Verification;
- formal Contract and Verification run again after finalize;
- the host specifies no target, patch, file, algorithm mechanism or repair.

## Development population and Protocol

M13 intentionally reuses the outcome-known M9 development population for
continuous learning. It is not a new formal population and cannot support a
generalization claim.

- screening cases: `B-n39-k5`, `P-n22-k2`, `A-n46-k7`, `F-n45-k4`,
  `X-n195-k51`, `X-n256-k16`;
- screening seeds: `3001`, `3011`;
- canary: problem-owned `data/tiny_canary.json`, seed `3049`;
- paired effect: case-median `total_distance`, protected lexicographic
  `fleet_violation`, equivalence band zero;
- unchanged M9 time limits, R3 numerical gates and
  `require_expanded_for_pass=true`;
- `--rounds 2`: stop after at most two evaluated screening stages. Any expand
  or queue recommendation is descriptive and does not run validation/frozen
  in this invocation.

Reserved validation/frozen development data remains unavailable to H/C and is
not executed. A future formal population remains unselected.

## Resource envelope

| Resource | Hard maximum |
|---|---:|
| provider calls, H+C combined | 30 |
| autonomous H / Hypothesis Contract calls | 30 |
| complete C sessions / formal candidates | 7 |
| Patch Contract / Verification calls | 7 each |
| Protocol / Safe Feature / Decision calls | 2 each |
| Verification solver subprocesses | 14 |
| Verification pytest subprocesses | 7, each at most 60 seconds |
| Protocol canary solver subprocesses | 4 |
| formal screening solver subprocesses | 48 |
| all solver subprocesses | 66 |
| nominal solver subject-seconds | 2,260 |
| guarded solver seconds | 3,250 |
| worst provider timeout seconds | 6,840 |
| cumulative development-test seconds | 540 |
| Verification pytest hard-timeout seconds | 420 |
| known guarded total | 11,050 seconds |
| `mgr.run` outer hardwall | 13,500 seconds |

Seven is the maximum number of formal candidates because each needs at least
one H, one revise, one passing development test and one independent finalize
provider call. H-only rejections can consume all 30 calls but create no C,
Verification or solver work. Solver arithmetic is `Verification 14*30 + canary
4*10 + formal 2*900 = 2260` nominal seconds and `14*45 + 4*25 + 2*1260 =
3250` guarded seconds. Worst provider time is `3*120 + 27*240 = 6840`
seconds; allocating more calls to H reduces it. The maximum development-test
wall is 540 seconds under the same 30-call cap.

## Typed stops and claims

- Invalid H, correctable C exhaustion, abandon, Contract rejection or
  Verification rejection is `RESEARCH_REJECTED` and may schedule another H
  only below the shared provider cap.
- Provider cap exhaustion is terminal
  `RESOURCE_EXHAUSTED / PROVIDER_CALL_CAP_EXHAUSTED` before dispatch.
- Provider auth/rate/timeout/transport/service faults are terminal
  `BLOCKED_INFRA`; retry is zero.
- Other `NOT_EVALUATED`, `BLOCKED_INFRA`, `RESOURCE_EXHAUSTED` or
  `INTERRUPTED` outcomes stop immediately.
- Canary veto has no formal Protocol claim and stops fail-closed.
- Two evaluated screening stages stop as `requested_rounds_completed`.
- The 13,500-second watchdog terminates active children and records
  `INTERRUPTED / OUTER_HARDWALL_EXCEEDED`.

Framework claims are limited to observed current H/C/Contract/Verification/
Protocol/Safe Feature/Decision behavior. Research-effectiveness claims describe
whether ordered history helped form and revise candidates. Algorithm claims
are development-screen descriptive only. No M13 result establishes promotion,
general CVRP improvement, causal isolation, production readiness or v0.4
completion.

## Frozen command

```bash
set -euo pipefail
cd /home/clawd/research/or-autoresearch-agent/scion

test -n "${AUTHORIZED_M13_CARRIER:-}"
test "$(git rev-parse HEAD)" = "$AUTHORIZED_M13_CARRIER"
git diff --quiet
git diff --cached --quiet
REPO_ROOT="$(git rev-parse --show-toplevel)"
test "$REPO_ROOT" = /home/clawd/research/or-autoresearch-agent
git -C "$REPO_ROOT" diff --quiet \
  7737bb0a "$AUTHORIZED_M13_CARRIER" -- scion/scion
test ! -e /home/clawd/research/scion-experiments/v04-cvrp-m13-history-safe-continuation-20260820
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
  --code-research-limits /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m11-code-research-limits.json \
  --protocol /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m9-development-protocol.yaml \
  --split /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m9-development-split.yaml \
  --seeds /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m9-development-seeds.yaml \
  --time-limit-sec 30 \
  --provider-call-cap 30 \
  --outer-hardwall-sec 13500 \
  --rounds 2 \
  --campaign-dir /home/clawd/research/scion-experiments/v04-cvrp-m13-history-safe-continuation-20260820
```

Provider-/solver-free preparation must verify the exact clean carrier, module
origins, all loaders, thirteen ordered history records, the strict recovered
M12 screening projection, public development closure, sandbox, unchanged
population, resource arithmetic and absent output. Any failure leaves M13
`PREP_INVALID` and performs no live request.
