# CVRP R3b adaptive-history K1 interruption report

Date: 2026-08-30 UTC

## Classification

The R3b root
`/home/clawd/research/scion-experiments/v04-cvrp-r3b-normal-k1-sol-20260829-r1`
is classified `INTERRUPTED_UNFINALIZED_EXTERNAL_PROCESS_LOSS`.

The original shell, Scion process and solver child no longer exist. The last
status heartbeat is `2026-08-30T00:09:08.503714Z`, while `status.json` still
says `running`. There is no campaign summary, terminal status, expanded metric
or typed terminal outcome. The root is therefore partial evidence, not a live
campaign, completed campaign, infrastructure result or algorithm result.

The frozen R3b rule forbids resume, retry or reconstruction inside this root.
No terminal row or summary will be written retrospectively.

## Complete ordinary evidence

Exactly one proposal and one initial screening stage closed before the
interruption:

- provider dispatches: `6/340` (two H turns, three C turns, one C finalize), all
  successful;
- H actions: `read_source(source-0005) -> finalize_hypothesis`;
- external R3 search/read/citation: `0/0/0`;
- selected basis: current `destroy_repair.py` only, with no history review
  because the first-round live failure frontier was empty;
- Contract, Verification and canary: passed;
- exact candidate: `candidate-g5m8w9qm`, modifying only
  `policies/baseline_modules/destroy_repair.py`;
- attempted/valid/failed pairs: `32/32/0`;
- case W/L/T: `6/0/2`; pair W/L/T: `18/5/9`;
- total-distance median delta: `+6.5`, bootstrap CI `[0,18]`;
- candidate/champion/shared/bilateral failures: all zero;
- candidate-only timeout, invalid output and attributable infeasibility: zero;
- protected fleet regressions: zero;
- gate/Decision: `expand / expand_screening`, reason
  `SCREENING_EXPAND_REQUIRED_FOR_PASS`.

The complete ordinary evidence is
`metrics/05946d23-1da7-429f-a622-7d6021a752ad.json`, the single SQLite event and
the single `research_history.jsonl` record. Those three projections agree on
the selected H basis, typed evaluated outcome and Decision. This demonstrates
that the post-R3 lineage repair works at its original write points without a
new identity, receipt or hash authority.

The initial result is promising adaptive development evidence only. It is not
an expanded-screen pass, validation result, frozen result, promotion or
history-benefit result.

## Incomplete expanded work

The same exact candidate had begun its required expanded screening. The last
heartbeat reports `34/96` attempted, `33` completed/valid and zero observed
failure counters; pair 34 was in flight on `X-n120-k6`, seed 29.

No expanded metric, event, W/L/T, median, CI, gate or Decision exists. The 33
completed counters cannot be converted into a scientific result or ordinary H
history. They establish only where the external process disappeared.

## Candidate interpretation

The patch changes regret-2/regret-3 repair so the regret score uses the cheapest
position per existing route instead of several positions in the same route.
The final insertion remains the globally cheapest feasible position, and no
capacity or fleet acceptance rule is relaxed.

Its self-authored regret-2 falsifier was discriminating and passed, but formal
telemetry cannot prove that route de-duplication changed a customer ranking in
the live runs. The evidence remains family association, not exact mechanism
activation. The falsifier also omitted regret-3, full scheduler integration and
the worst-case repair deadline. New-route padding does not know the route cap,
and a repair call has no internal deadline poll. These are proposal caveats,
not retrospective reasons to alter the completed Decision.

## Process lesson and bounded repair

No kernel OOM or typed Scion infrastructure failure is recorded. The original
interactive execution session is unavailable, so the exact external signal is
unknowable. The strongest local explanation is loss of the PTY-backed process
session; Scion handled SIGTERM/SIGINT but not SIGHUP, which explains the stale
`running` state without a terminal artifact. This is an inference, not a fact
stored by the run.

Future CLI runs handle SIGHUP through the same existing typed interruption path
as SIGTERM/SIGINT. The next campaign uses one ordinary foreground PTY session
attached to this Codex task's terminal panel, so the UI rather than an
unattached tool cell owns the process lifetime. This is run robustness only: it
installs no service, performs no distribution, deployment or build, and
introduces no PID registry, identity, lease, signature, receipt or repeated
closure.

## Continuity boundary

Only the one complete R3b `research_history.jsonl` record may be supplied to a
future campaign. It retains initial-screening scope and `expand_screening`
Decision semantics. The partial expanded counters and this interruption report
are not H history.
