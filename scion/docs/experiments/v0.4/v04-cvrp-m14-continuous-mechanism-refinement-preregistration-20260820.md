# CVRP M14 continuous mechanism-refinement preregistration

**State:** `TERMINAL_VALID_NEGATIVE_MIXED`

## Scientific object

Can Scion use the two native M13 H/patch/Protocol/Decision observations to
autonomously choose and evaluate the next CVRP mechanism, without a host-chosen
target, patch, file or repair? The only run is
`v04-cvrp-m14-continuous-mechanism-refinement-20260820` in the fresh root
`/home/clawd/research/scion-experiments/v04-cvrp-m14-continuous-mechanism-refinement-20260820`.

M13 showed one uniformly negative operator-credit change and one mixed
route-removal change. Both also showed that X-n256-k16 is a shared baseline
failure rather than a candidate-only failure. M14 asks the Agent—not the
host—to decide whether to refine either mechanism, combine evidence into a new
mechanism, or pivot elsewhere in the current source graph.

The user's 2026-08-20 instruction to keep trying with full experimental
authorization delegates this independently frozen one-shot after all clean
carrier and provider-/solver-free gates pass. It does not authorize root reuse,
retry, resume, replacement, case/seed substitution or automatic M15.

## Carrier and ordinary inputs

Production baseline is unchanged commit `7737bb0a`; no CVRP algorithm or
framework change occurs after M13. Launch binds the clean docs-only descendant
as `AUTHORIZED_M14_CARRIER` and requires its `scion/scion` subtree to equal
`7737bb0a`.

H receives the same M7 research input and, in order, the M9, M10, M11, M12 and
M13 histories. The M13 history is committed as
`inputs/v04-cvrp-m14-m13-research-history.jsonl`, an exact byte copy of the two
native M13 lines, SHA256
`b73dd2a16504dde4df9866f8f62bc6ae0842d92fa1745870d2016736ab6bd62b`.
The full ordered input contains 15 records. Runtime Scion reads only committed
ordinary JSONL files; it does not reopen any campaign database, summary,
metrics, traces or workspace. History enters H only. Current source remains
authoritative for C.

## Agent, population and resources

M14 keeps the exact M13/M9 condition:

- `gpt-5.6-terra`, reasoning high, local proxy, SDK retry zero;
- H timeout 120 seconds, C/research/finalize timeout 240 seconds;
- shared pre-dispatch provider cap 30;
- unchanged M11 code-research limits and problem-declared public sandbox;
- current Patch Contract and Verification always rerun after finalize;
- unchanged six-case/two-seed outcome-known development screen, canary 3049,
  case-median total distance, protected fleet violation, R3 numerical gates
  and `require_expanded_for_pass=true`;
- `--rounds 2`, so at most two evaluated stages. A positive initial screen may
  spend the second stage on expansion; otherwise a Decision may create one
  further candidate. Validation/frozen and future formal data remain unused.

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

Seven formal candidates follows from the minimum four provider calls per
candidate (H, revise, test, finalize). H-only rejection can use all 30 calls but
creates no solver work. Solver and timeout arithmetic is identical to M13.

## Stops and claims

Research rejection may schedule another H only below the provider cap.
Provider cap exhaustion is terminal
`RESOURCE_EXHAUSTED / PROVIDER_CALL_CAP_EXHAUSTED` before dispatch. Provider
fault is terminal `BLOCKED_INFRA` with retry zero. Other non-evaluated,
resource, infrastructure or interrupt outcomes stop immediately. Canary veto
has no formal Protocol claim. Two evaluated stages stop as
`requested_rounds_completed`; the outer watchdog terminates children as
`INTERRUPTED / OUTER_HARDWALL_EXCEEDED`.

Framework behavior may be reported as observed. Research effectiveness may
describe autonomous use of M13 history. Algorithm claims remain
development-screen descriptive. No result is promotion, generalization,
causal isolation, production readiness or v0.4 completion.

## Frozen command

```bash
set -euo pipefail
cd /home/clawd/research/or-autoresearch-agent/scion
test -n "${AUTHORIZED_M14_CARRIER:-}"
test "$(git rev-parse HEAD)" = "$AUTHORIZED_M14_CARRIER"
git diff --quiet
git diff --cached --quiet
git -C /home/clawd/research/or-autoresearch-agent diff --quiet \
  7737bb0a "$AUTHORIZED_M14_CARRIER" -- scion/scion
test ! -e /home/clawd/research/scion-experiments/v04-cvrp-m14-continuous-mechanism-refinement-20260820
command -v bwrap >/dev/null

PROXY_KEY_VALUE="$(curl -fsS --connect-timeout 5 --max-time 15 \
  http://127.0.0.1:8080/auth/status | \
  jq -er '.proxy_api_key | select(type == "string" and length > 0)')"
trap 'unset PROXY_KEY_VALUE' EXIT
curl -fsS --connect-timeout 5 --max-time 15 \
  -H "Authorization: Bearer $PROXY_KEY_VALUE" \
  http://127.0.0.1:8080/v1/models | \
  jq -e --arg model gpt-5.6-terra 'any(.data[]?; .id == $model)' >/dev/null

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
  --code-research-limits /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m11-code-research-limits.json \
  --protocol /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m9-development-protocol.yaml \
  --split /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m9-development-split.yaml \
  --seeds /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m9-development-seeds.yaml \
  --time-limit-sec 30 \
  --provider-call-cap 30 \
  --outer-hardwall-sec 13500 \
  --rounds 2 \
  --campaign-dir /home/clawd/research/scion-experiments/v04-cvrp-m14-continuous-mechanism-refinement-20260820
```

Preparation must verify exact clean carrier and module origins, all loaders,
15 ordered history records, exact M13 copy, sandbox and public closure,
unchanged population/resource arithmetic, proxy model metadata and absent
output. Any failure is `PREP_INVALID` with zero live provider or solver call.

## Terminal record

M14 ran once from clean carrier
`ed307edde1cf844094c7b75e5fad9581d1ed401e` and exited zero as
`completed / valid / requested_rounds_completed`. It scheduled four research
attempts, used 17 provider calls, recorded two code-research rejections and two
evaluated screening stages, and wrote four native ordinary history records.
There were no infrastructure, resource, interrupt, not-evaluated or unknown
outcomes, and no live child remained. Champion is still v1; validation,
frozen, promotion and retention counts are zero.

Attempts one and three independently proposed elapsed-budget simulated
annealing in `acceptance.py`, but their C revise responses violated the typed
action schema. Both stopped safely as
`RESEARCH_REJECTED / PATCH_PROPOSAL_INVALID`; neither reached a candidate
workspace, Verification or Protocol.

The first evaluated candidate extended `_two_opt_star` with reversal-aware
tail variants. Contract, Verification and canary passed. Screening completed
12 attempted pairs, ten valid pairs and two shared X-n256-k16 failures. The
five case aggregates were one win, two losses and two ties: A-n46-k7 was +1.5,
F-n45-k4 was -2.1025439344, X-n195-k51 was -761.5, and B/P tied. The
case-median effect was zero with CI `[-761.5, 1.5]`. Protocol failed case
quality and Decision returned `continue_explore` because champion evidence was
partial.

The second evaluated candidate replaced repeated route-distance evaluation in
the forward `_two_opt_star` exchange with a boundary-edge delta. The idea did
not preserve behavior in its implementation: it assigned the new left route
before using the original left tail to build the new right route. On both
X-n195-k51 seeds this duplicated customers and omitted others; the runtime
solution audit classified both pairs as candidate-only solver-algorithm
failures. X-n256-k16 remained two independent shared failures. Only eight
pairs were valid; the case aggregate had zero wins, five losses and median
-2.1025439344 with CI `[-12, -1]`. Decision correctly returned
`abandon / CANDIDATE_RUNTIME_FAILURE`.

This is valid continuous-research evidence: M13 history influenced new H/C
work, current gates rejected a defective candidate, and pair-local attribution
separated its X195 failure from the shared X256 baseline failure. It is not
algorithm improvement, promotion, generalization or v0.4 completion. The
immutable root is
`/home/clawd/research/scion-experiments/v04-cvrp-m14-continuous-mechanism-refinement-20260820`;
it is not retried or resumed.
