# CVRP R3i long-run adaptive-history postrun

**State:** terminal, `stopped / valid_incomplete / execution_blocked_infra`

**Campaign:** `v04-cvrp-r3i-normal-k1-sol-20260903-r1`

**Frozen design:**
[`v04-cvrp-r3i-long-run-adaptive-history-preregistration-20260903.md`](v04-cvrp-r3i-long-run-adaptive-history-preregistration-20260903.md)

## Terminal diagnosis

R3i produced 16 of the requested 40 evaluated stages in 25 scheduled calls,
then stopped cleanly at `proposal_hypothesis` with
`PROVIDER_CALL_BLOCKED_INFRA`. The run remains valid but incomplete; its root
is terminal and must not be resumed or reconstructed.

The stopping request received two failed physical dispatches:

1. at `2026-09-04T10:19:20Z`, the local proxy returned provider 429, “all
   accounts exhausted / usage limit reached”;
2. about 61 seconds later, it returned its exact synthetic 401 body,
   `Not authenticated. Please login first at /`.

The transport classified the second response as a real authentication error.
Real auth errors are deliberately invocation-terminal, so the request did not
reach the remaining transient redispatch/attempt-local path. The actual chain
was therefore temporary provider exhaustion followed by the local proxy's
no-usable-account sentinel being misclassified as credential failure. It was
not provider-cap exhaustion (`170/2000` calls), an H/C timeout, solver timeout,
disk exhaustion, Protocol gate, balance failure or malformed solver output.
The retained tmux pane exited with status 20, consistent with the durable run
result.

The 170 traces comprise 168 successful calls and the two failures above. The
final null-H infrastructure row contains no algorithm proposal or evaluation
and is not scientific evidence.

## Completed scientific evidence

All 16 metric artifacts are complete: 14 screening, one validation and one
frozen evaluation. Across them, all `896/896` attempted pairs were valid, with
zero candidate, champion, shared or bilateral failures; zero candidate-only
timeouts or invalid outputs; zero attributable infeasibility; and zero
protected `fleet_violation` regressions.

R3i promoted champion v2. The promoted source is a cumulative bundle, not an
isolated 2-for-1 result:

1. a dynamic perturbation frontier;
2. post-repair admissibility plus smallest-route consolidation;
3. orientation-changing inter-route 2-opt-star;
4. inter-route 2-for-1 exchange.

Its three promotion stages were:

| Stage | Valid pairs | Case W/L/T | Median distance delta | Interval | Result |
|---|---:|---:|---:|---:|---|
| expanded screening | 96/96 | 6/1/5 | +2.5 | [0, 10.5] | pass |
| validation | 96/96 | 7/0/5 | +1.0 | [0, 14.5] | pass |
| frozen | 96/96 | 6/1/5 | +1.25 | [0, 6.5] | pass / promote |

The preceding initial screen was weaker but legitimately expanded: 32/32,
case W/L/T `3/2/3`, median `0`, interval `[-1.5,18]`. The three promotion-stage
results are consistent and safe, but every lower interval bound is exactly
zero, there is no matched A/A calibration or MDE, and generic VNS telemetry
does not observe direct `_exchange_2_for_1` activation. The supported claim is
therefore retention of the exact cumulative v2 bundle on the three R3i
populations, not isolated mechanism causality or retained superiority to the
original B0. R3i performed no final retained-B0 comparison.

## Mechanism conclusions

- Retain exact v2 pending direct ablation and independent B0 confirmation.
- Stop the current depth-2 ejection-chain direction: screening median `-2.5`,
  interval `[-9.5,0]`, case W/L/T `0/4/4`; it also displaced useful VNS/ALNS
  work.
- Stop always-on SWAP* in its current form: expanded median `+0.75`, interval
  `[-6,62.5]`, case W/L/T `6/3/3`; a few large wins did not offset systematic
  losses and a 19.4-point shift into initial VNS.
- Stop pure local-optimality-certificate/throughput work: despite more VNS and
  ALNS activity, its expanded result was median `0`, interval `[0,0.5]`, case
  W/L/T `3/0/9`, hence no useful terminal-quality result.
- Dynamic-frontier-only, terminal elite intensification, Shaw route-string
  destroy and further admissibility/consolidation-only variants also failed to
  establish standalone value. Do not deepen these mechanisms merely because
  they increase activity counters.

The highest-information next algorithm study is a paired `v2 minus
_exchange_2_for_1` ablation with direct, lightweight operator
scored/accepted/gain/runtime telemetry. If later large-case work is needed,
test a lower/adaptive initial-and-embedded VNS threshold rather than another
always-on expensive neighborhood.

## Prospective runtime repair status

The current working tree contains a prospective repair, but it is not yet a
completed release or frozen experiment carrier:

- recognize only the local proxy's exact synthetic 401 body as retryable
  provider unavailability, attach a 20-minute retry hint, and let provider
  faults as well as 429 honor that hint; real 401/403 authentication failures
  remain terminal;
- keep malformed C `revise` wrappers inside the bounded research session as
  corrective tool feedback, publish one canonical wrapper, and return the
  exact frozen patch immediately on successful `ready` instead of requesting a
  redundant final closure;
- keep operational provider/proposal/reconcile failures in their campaign
  audit trail but filter them from future H algorithm history, and widen only
  the ordinary history file/record input ceilings.

No hash, object identity, lease, owner registry, signing, receipt or repeated
closure was added. The stable provider-free full suite completed with `2383
passed`, `1 skipped` and `0 failed` in 478.87 seconds (480.61 seconds outer
wall). Targeted Ruff `E9,F,I` and diff check are green.

## R4 handoff

The provider-free R4 fixed-candidate comparison is preregistered and prepared,
but not launched. See the
[`R4 preregistration`](v04-cvrp-r4-r3i-v2-retained-b0-confirmation-preregistration-20260904.md).
It compares ordinary read-only copies of the exact R3i starting B0 and
`champion_v2`; direct comparison has exactly the three changed modules named
above. Its 36 CVRPLIB effect cases have zero case overlap and zero case-seed
overlap with the 68 R3-R3i metrics, while retained uses the pre-R3 reserved
12-case final block with the fixed two-seed prefix `157,163`. The controlled
canary is reused only as a non-estimand smoke check and uses a fresh seed.

`run_fixed_candidate_funnel.py --check` returned `PREPARED` with zero provider
calls, 85 maximum pairs, 170 serial solver subprocesses, 10,160 nominal and
15,260 guarded subject-seconds, and a 21,600-second outer hardwall. The reserved
output directory does not exist, so no live solver evidence has been produced.
