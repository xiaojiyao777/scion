# CVRP R3h postrun: local research capacity stopped a healthy campaign

R3h is a valid but incomplete run. It must not be resumed or promoted from.

## Terminal facts

- Root: `/home/clawd/research/scion-experiments/v04-cvrp-r3h-normal-k1-sol-20260902-r1`.
- Terminal time: `2026-09-03T05:13:17Z`.
- Result: `stopped / execution_resource_exhausted / valid_incomplete`.
- Work completed: 11 evaluated stages from 16 scheduled calls: 10 screening,
  one validation, four research rejections, and one terminal resource outcome.
- Provider use: 113/340 physical dispatches. All 113 traces succeeded on attempt
  zero; no provider timeout, retry, authentication, balance, or transport fault
  caused the stop.
- Champion remained v1; no frozen stage or promotion occurred.

The exact terminal reason was
`HYPOTHESIS_RESEARCH_TRANSCRIPT_EXHAUSTED`. The active H session had already
completed five provider turns. Its next prompt would have taken that session's
accumulated rendered transcript beyond the configured 1,500,000-character
limit. This was local proposal working context, not disk storage, provider
budget, campaign time, or solver capacity. Treating it as global resource
exhaustion was therefore the defect.

## Prospective correction

The successor keeps ordinary per-action/read/test bounds but no longer imposes
a total H/C transcript character ceiling. If an explicitly configured local
turn/result limit is reached after research has begun, only that proposal is
rejected and the scheduler continues. A fixed prompt that cannot fit before
the first provider dispatch remains terminal so it cannot create a zero-cost
loop.

Typed timeout, transport, provider-overload, and 429 failures exhaust their
bounded frozen-request redispatches as an operational proposal rejection, not
as a campaign stop. Authentication, balance, an explicitly selected provider
cap, operator signal, and hardwall remain invocation-level boundaries.

Research-history output policy limits now preserve the valid prefix and stop
that optional projection without stopping StepRecord/SQLite research. Input
history validation remains bounded. Inherited `SIGHUP=SIG_IGN` is respected,
K2 no longer requires global cap/hardwall configuration, and a cleaned stale
explore attempt schedules forward.

Contract, Verification, canary, feasibility, screening, validation, and frozen
rules are unchanged. They reject unsafe or weak candidates/branches; they do
not end a healthy campaign. The one Verification-to-Protocol content equality
check remains, but no identity, lease, signing, registration, receipt, or
additional hash lifecycle was added.

R3h contributes 15 ordinary `cvrp` history rows. Its terminal row is retained
as evidence of the operational stop. Partial private validation/frozen facts
remain excluded by the existing held-out projection.
