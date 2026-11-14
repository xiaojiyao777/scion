# CVRP R3c adaptive-history K1 postrun

Date: 2026-08-30 UTC

Preregistration:
[`v04-cvrp-r3c-adaptive-history-k1-sol-preregistration-20260830.md`](v04-cvrp-r3c-adaptive-history-k1-sol-preregistration-20260830.md)

Experiment root:
`/home/clawd/research/scion-experiments/v04-cvrp-r3c-normal-k1-sol-20260830-r1`

## Terminal outcome

R3c stopped with the typed root-level classification `RUN_INVALID_INFRA`.
The runtime record says `stopped / execution_blocked_infra`, with validity
`valid / valid_incomplete` and final outcome
`blocked_infra / PROVIDER_CALL_BLOCKED_INFRA / proposal_hypothesis`.

- requested evaluated-stage horizon: 20;
- scheduled ordinary steps: two;
- completed formal evaluations: one, at screening;
- validation, frozen and promotion: `0/0/0`;
- provider dispatches charged: `13/340`;
- terminal provider traces: 12 successful and one failed;
- unknown execution outcomes: zero.

The completed first stage remains ordinary adaptive-development evidence. The
declared campaign as a whole is truncated infrastructure evidence, not a valid
20-stage result and not evidence for or against promotion. The R3c root is
terminal and will not be resumed, retried, extended or retrospectively
rewritten.

## Completed candidate evidence

The first proposal modified only `policies/baseline_modules/scheduler.py`. It
added a bounded quality-and-edge-diversity elite archive and sparse
stagnation-triggered archive restarts. The exact candidate digest recorded by
the branch is
`320e62d088fa15930156db41fc5ddd207e7a18419a72ff7ded2ecde26a47dcd9`.

Contract, Verification and the canary passed. Initial screening completed all
32 pairs without a failure:

- attempted/valid/failed pairs: `32/32/0`;
- case W/L/T: `0/0/8`;
- pair W/L/T: `3/2/27`;
- total-distance median delta: `0`, bootstrap CI `[0,0]`;
- candidate, champion, shared and bilateral failed pairs: all zero;
- candidate-only timeout, invalid output and attributable infeasibility: zero;
- protected fleet regressions: zero;
- gate: `fail`, reason `SCREENING_FAIL_CASE_QUALITY`;
- Decision: `continue_explore`.

This is a safe but tied quality result. It did not request expanded screening
and did not reach validation or frozen testing. Association-level search
telemetry does not turn the tie into mechanism or promotion evidence.

## Research-history behavior

The first H session read current source `source-0010` and cited no external
history. None of the 22 external R3/R3b records was read or cited, so external
history uptake is zero. Availability of those records therefore cannot be
called beneficial use.

The next H session did establish live within-campaign continuity. It read
`source-0005`, read the completed sibling result as `history-0031`, and marked
that frontier reference `used`. Its following provider request was the failed
request, so it exported no hypothesis or selected research basis. The partial
H transcript is not an algorithm proposal and supplies no Protocol or Decision
result.

## Infrastructure failure

The final trace is a `hypothesis_research_turn` with no response. It records
`LLMTimeoutError` after the explicit 120.0-second hard timeout, with elapsed
time exactly 120.0 seconds. At the terminal boundary the local proxy reported a
synthesized HTTP 504 after its upstream SSE stream closed prematurely. Scion
did not receive a usable terminal HTTP response before its own timeout, so the
durable fact is the typed timeout rather than a provider response body.

R3c used provider SDK retries of zero and had no Scion redispatch boundary. A
single transient transport episode therefore terminalized the second ordinary
step as blocked infrastructure. There is no candidate-attributable solver
failure in that step and no basis for reclassifying the completed first-screen
tie.

## Bounded repair disposition

Future campaigns retain provider SDK retries at zero. The only repair is an
explicit ResourceEnvelope option allowing ProviderCaller to redispatch the
same frozen request at most once after one of three typed transient failures:
`LLMTimeoutError`, `LLMTransportError` or `LLMProviderError`.

The boundary excludes rate limit/429, authentication, authorization, balance,
response-format, schema, response-size, generic and interruption failures.
Every physical dispatch consumes the existing shared provider cap before the
call and writes one terminal trace. The second dispatch remains part of the
same H/C logical turn; it creates no extra research turn and contributes no
retry metadata to H, research history, Protocol or Decision. If the shared cap
cannot admit it, the existing resource-exhausted path applies. If both
dispatches fail with eligible typed faults, the existing blocked-infrastructure
path applies.

This is not an exactly-once claim. A timed-out first request could still be in
flight upstream, but a later response from it is never observed or used by
Scion. The repair adds no object identity, lease, issuance, registration,
signature, receipt, request hash or repeated finalization mechanism.

## Continuity boundary

R3c contains exactly two complete typed `cvrp` research-history records:

1. the evaluated initial-screen record with `continue_explore`;
2. the proposal-hypothesis `blocked_infra` record with no Decision.

Both records may be supplied, in order and without alteration, to a future
fresh campaign. No candidate source, workspace, SQLite state, status state,
provider session or partial H response from R3c may be loaded or reconstructed.
