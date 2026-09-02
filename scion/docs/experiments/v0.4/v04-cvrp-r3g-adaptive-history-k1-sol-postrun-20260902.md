# CVRP R3g adaptive-history K1 postrun

Date: 2026-09-02 UTC

Preregistration:
[`v04-cvrp-r3g-adaptive-history-k1-sol-preregistration-20260901.md`](v04-cvrp-r3g-adaptive-history-k1-sol-preregistration-20260901.md)

Experiment root:
`/home/clawd/research/scion-experiments/v04-cvrp-r3g-normal-k1-sol-20260901-r1`

## Outcome

R3g stopped cleanly at its typed infrastructure boundary and is classified
`valid_incomplete / execution_blocked_infra`. It is not a completed 20-stage
campaign, a scientific rejection of its entire frontier, or promotion evidence.

- requested/evaluated stages: `20/1`;
- scheduled calls: two, comprising one evaluated screening and one
  proposal-hypothesis infrastructure outcome;
- Protocol stages: one screening, zero validation and zero frozen;
- execution outcomes: one `EVALUATED`, one `BLOCKED_INFRA`, and zero
  research-rejected, not-evaluated, resource-exhausted, interrupted or unknown;
- provider dispatches: `10/340`, with `330` remaining;
- terminal reason: `execution_blocked_infra`;
- terminal champion: unchanged `v1`; no promotion occurred.

Both proposal attempts are durably `closed`. The retained tmux pane is dead and
its capture reports the same incomplete-infrastructure stop. That is operational
corroboration only; the ordinary status, summary, trace, metric and history
artifacts establish the result.

R3g is terminal and consumed. It will not be resumed, extended, reconstructed
or rewritten. R3h, if launched after its independent gates pass, starts from a
fresh B0 and a fresh provider/session boundary.

## Completed screening evidence

The first H independently proposed a bounded, capacity-feasible three-route
cyclic-exchange neighborhood in
`policies/baseline_modules/local_search.py`. It rotates one customer across
three distinct routes in both cyclic directions, uses deterministic bounded
nearest-neighbor candidates, screens exact load and edge changes, and exactly
recomputes the three affected route costs before accepting a strict
improvement.

The candidate passed Hypothesis Contract, Patch Contract, Verification and
canary. Its screening completed without an execution failure:

- attempted/valid/failed pairs: `32/32/0`;
- candidate, champion, shared and bilateral failed pairs: all zero;
- candidate-only timeout, invalid-output and attributable-infeasibility pairs:
  all zero;
- case W/L/T: `1/2/5`, case win rate `0.125`;
- pair W/L/T: `4/6/22`, pair win rate `0.125`;
- total-distance median delta: `0`, bootstrap CI `[-2,0]`;
- Protocol: `fail / SCREENING_FAIL_CASE_QUALITY`;
- Decision: `continue_explore`.

The accepted branch head has code digest
`14c4939469990ae99e038292955eea5eaa45ff0e9ab30e9534f6d124e73aaea9`.
The digest identifies the exact completed candidate for reporting; it grants no
authority and does not make that candidate an R3h input.

This is safe but negative adaptive-development evidence. The proposed
three-route transition did not earn expanded screening, validation, frozen
testing or promotion. Mechanism telemetry remains association-only and cannot
override Protocol or Decision.

## History uptake and selected basis

The first H used three hypothesis turns in exact action order:
`read_source(source-0006)`, `read_history(history-0056)`, then
`finalize_hypothesis`. Its selected basis records both refs, cites
`history-0056` as the nearest prior, and explains a material delta from that
R3f exact-relocate observation: the new proposal sought a coordinated
three-route state transition rather than another acceleration of the existing
two-route relocate evaluator.

This is attributable uptake of one R3f history row. It does not identify a
causal benefit of history, prove the mechanism, or make the R3f candidate
executable. The completed R3g screen itself remains the controlling scientific
result.

The second H turn read only current source `source-0005` before the provider
failure. It exported no hypothesis and therefore has no selected research
basis, citation, Protocol result or Decision. Its partial transcript is not an
algorithm proposal.

## Provider incident and exact accounting

The first closed proposal attempt admitted seven physical calls:

- three `hypothesis_research_turn` calls;
- three `code_research_turn` calls;
- one `code_research_finalize` call.

All seven returned successful terminal traces and produced the evaluated
candidate. The second closed attempt admitted three
`hypothesis_research_turn` calls. Its first call successfully returned
`read_source(source-0005)`. The next frozen logical request then received two
typed `LLMProviderError` responses:

1. `attempt_index=0`: HTTP 502, provider servers overloaded;
2. `attempt_index=1`: the one preregistered Scion redispatch, the same HTTP 502.

Both physical dispatches were charged and each has one terminal failure trace.
Provider SDK retries remained zero. The exhausted logical turn became
`BLOCKED_INFRA / PROVIDER_CALL_BLOCKED_INFRA / proposal_hypothesis`; its new
branch is held `blocked_infra`, while the completed first branch remains
`explore`. The campaign loop's existing invocation-terminal policy then stopped
R3g after one evaluated stage.

The incident is provider infrastructure evidence, not candidate-attributable
solver failure, `RESEARCH_REJECTED`, provider-cap exhaustion or balance
exhaustion. It does not revise the completed first screening Decision.

## Frozen R3h history boundary

R3g contributes exactly two complete strict `cvrp` history rows:

1. the evaluated cyclic-exchange screening row with its selected basis and
   `continue_explore` Decision;
2. the null-H/null-basis `blocked_infra` proposal-hypothesis row with no
   Protocol result or Decision.

Both typed rows may be loaded, in order, as ordinary H-only evidence by one
fresh R3h campaign. R3g candidate source, accepted workspace, status, metrics,
SQLite state, provider response/session, trace bodies, tmux state and mutable
branch state are not R3h inputs. In particular, R3h does not continue either
R3g branch or reconstruct the cyclic-exchange patch.

The exact prospective external concatenation is
`[21,1,2,1,1,22,2] = 50` rows in R3 -> R3b -> R3c -> R3d -> R3e -> R3f -> R3g
order. The two R3g records occupy provider-visible refs
`history-0057..0058` after the common eight ordinary observations.

## Prospective operational repair

R3g's already completed facts retain their preregistered zero-SDK-retry and
one-immediate-redispatch boundary. They are not retrospectively reclassified.

For a future fresh R3h only, the same ordinary `ProviderCaller` boundary may
perform at most two redispatches of one frozen request after typed timeout,
transport or provider faults. The physical sequence is therefore bounded at
three dispatches, with deterministic ordinary backoff constants of 5 seconds
before the first redispatch and 20 seconds before the second. Every physical
dispatch is still admitted against the unchanged shared cap before sending and
receives its own terminal trace. SDK retries remain zero; 429, authentication,
authorization, balance, format, schema, response-size, generic and interruption
faults remain ineligible.

This is not an exactly-once claim and adds no logical H/C turn, provider
identity, owner, lease, issuance, registration, signature, receipt, request
hash, history field, Protocol input, Decision feature or repeated closure. If
all three eligible dispatches fail, the existing typed invocation-terminal path
still applies.

R3h also prospectively raises only provider transport ceilings: default and H
research turns to 180 seconds, C research turns to 300 seconds, and C finalize
to 240 seconds. Formal solver budgets, cases, seeds, splits, statistical gates,
K1 policy, branch count, evaluated-stage horizon and provider cap remain
unchanged.

## Next rung

The fresh R3h preregistration is
[`v04-cvrp-r3h-adaptive-history-k1-sol-preregistration-20260902.md`](v04-cvrp-r3h-adaptive-history-k1-sol-preregistration-20260902.md).
Its exact prospective tree completed `2301 passed, 1 skipped, 0 failed`; all
focused static, history, formal-readiness and wrapper gates are green. It is
ready for the separately frozen one-shot background launch from clean code
commit `44fff1356e253927e820fff88ad13ca701e87dbc`.
