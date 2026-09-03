# Scion v0.4 Current State

*Current as of: 2026-09-02*

Read [`../../TASK.md`](../../TASK.md) first. The sole architecture authority is
[`../../design/scion-architecture-v3.md`](../../design/scion-architecture-v3.md)
and its direct-runtime addendum. Historical experiment reports preserve
evidence; they do not define current runtime authority.

## Outcome

Warehouse has demonstrated real retained improvement:

- synthetic Scion promoted and independently retained `v1 -> v2 -> v3`;
- production-style Scion promoted and independently retained `v1 -> v2`.

CVRP remains open. R3f completed its full 20-stage horizon through a stable
local tmux carrier with 19 screening stages, one prospective validation and no
frozen stage. One cumulative candidate passed initial and expanded screening,
but its validation obtained 94/96 valid pairs and two candidate-only timeouts;
Decision correctly abandoned it for incomplete runtime evidence. Champion
B0/v1 remains unchanged, and R4 retained-B0 evaluation is correctly blocked.

The final R3f cumulative candidate completed a safe `32/32` exact-relocate
initial screen and requested expansion, but this was evaluated stage 20. It has
no expanded result and is a formal-horizon censor, not a pass, failure,
interruption or promotion. R3f is therefore valid negative research evidence
classified `VALID_20_STAGE_HORIZON_CENSORED`.

## Runtime boundary

Scion is a problem-neutral engine. A problem enters Campaign, Contract,
Verification and Protocol only through its adapter.

```text
adapter + safe source/history
  -> agent H research -> tainted H -> Hypothesis Contract
  -> agent C research -> tainted C -> Patch Contract
  -> isolated candidate workspace -> Verification
  -> problem Protocol -> Safe Features -> deterministic Decision
  -> exact candidate stage drain / branch continuation / promotion
```

The normal scheduler supports up to three continuous branches. K=2 remains an
optional bounded H drafting strategy inside the same campaign, not a separate
qualification mode. Exact candidates progress through ordinary screening,
validation and frozen states; there is no qualification parking or candidate
reconstruction path.

History remains complete, ordered H-only proposal evidence. The agent may
search/read any ordinary record and chooses whether it is scientifically used.
The host does not rank a nearest record or select a mechanism. A small control
now requires an agent-authored disposition only for explicit failures at the
latest ordinary round of the `current` and `sibling` relations independently:
use a record after reading/citing it, or reject it with a reason. A later pass
closes an older failure only in the same relation. External and older history
stays fully optional. Held-out validation/frozen evidence never enters H
context.

Candidate workspaces use ordinary fresh temporary directories and local
cleanup. The retained integrity mechanism is one final exact-content equality
around Verification and Protocol handoff; object identity, leases, owner
registries, signing, receipts and repeated manifest closure are absent from the
reachable runtime.

## Completed evidence

R1 closed the problem boundary and deleted the post-M32 S2c authority island,
qualification-only runtime, parking/carrier/audit paths and the obsolete
effectiveness scorer. The ordinary trajectory evaluator, K1/K2 continuous
campaign and direct adapter boundary remain.

R2 ran a five-block, ten-arm matched CVRP history study. All 20 requested
screening stages completed. The additional 45 heterogeneous external records
were prompt-visible in the ON arm but no selected H read or cited them, so the
study found no attributable external uptake or demonstrated benefit and that
corpus remains disabled. This is an availability/index-exposure ITT, not proof
of zero indirect content effect. Ordinary within-campaign history was read and
cited, and selected bases attributed later direction changes to it; because
both arms had local history, R2 does not estimate its benefit. The next adaptive
campaign therefore loads only the narrower, same-problem R3 history while
retaining local current/sibling history.

R3 ran one preregistered K1 `gpt-5.6-sol` campaign through the local proxy:

- terminal `completed`, `requested_rounds_completed`, validity `valid`;
- 21 scheduled research steps, 16 formal screenings and five typed research
  rejections;
- 114/272 provider dispatches, all attempts closed;
- 16 distinct formal H episodes, 12 observed distinct H+patch pairs and five
  exact-candidate expanded screens;
- 832 attempted pairs, 827 valid and five candidate-only timeout failures;
- no invalid output, infeasibility, protected regression, validation, frozen
  test or promotion.

The full R3 analysis is
[`../experiments/v0.4/v04-cvrp-r3-normal-k1-sol-postrun-20260829.md`](../experiments/v0.4/v04-cvrp-r3-normal-k1-sol-postrun-20260829.md).
It is valid negative research evidence, not a failed launch.

## Post-R3 controls

The framework defects exposed by R3 have been corrected without adding a
Trust/Hash authority layer:

- a failed self-authored code falsifier permanently vetoes that exact patch
  value for the current C session; omitting or weakening a later probe cannot
  reopen it, while a genuinely different patch may be tested normally;
- explicit failures at each relation's latest ordinary live round must receive
  one agent-authored used/rejected disposition before H finalizes, while search
  is case-insensitive token-OR and returns at most one discovery hit per ordered
  history record;
- the selected H basis, including the frontier review when present, and the
  typed evaluated outcome now flow through the original StepRecord, SQLite
  lineage, summary and research-history JSONL write points. Old R3 rows remain
  untouched and truthfully null;
- candidate/workspace disposition failure becomes one typed `BLOCKED_INFRA`
  fact that preserves either the interrupted outcome or completed Protocol plus
  unapplied Decision. It is not counted as an evaluated/applied-Decision
  closure, and nested validation/frozen facts remain excluded from H history;
- a stale branch with no accepted change closes as null-H/null-basis
  non-attempt housekeeping. Accepted-chain replay preserves its exact head
  basis, and cleanup failure cannot replace an already applied Decision or
  delete a durable accepted workspace.

Problem-owned CVRP guidance also requires a self-authored activation falsifier
for performance mechanisms and a public synthetic large-shape deadline check.
These are development diagnostics only; mechanism telemetry and history never
enter Safe Features or Decision.

The post-SIGHUP frozen provider-free, non-campaign regression is green: `2260
passed, 1 skipped` in 439.42 seconds. The exact signal, resource, history and
CVRP formal-readiness slice is also green at `107 passed`. This includes the
public 719-customer deadline case, frontier/falsifier adversarial tests,
exact-candidate stage continuity, adapter boundaries and candidate-disposition
fault injection.

R3b then launched once and produced one complete initial-screen result. Its
route-distinct regret candidate completed 32/32 valid pairs, case W/L/T `6/0/2`,
median `+6.5`, CI `[0,18]`, and received `expand_screening`. It used no external
R3 record. During expanded screening the interactive process disappeared after
33/96 completed/valid pairs. No expanded metric, event or Decision exists.
The stale `running` root is therefore preserved as
`INTERRUPTED_UNFINALIZED_EXTERNAL_PROCESS_LOSS`, not resumed or rewritten.

SIGHUP now uses the existing typed interruption path, closing the specific
stale-status gap without adding a Trust/Hash authority. R3c used one foreground
PTY attached to this Codex task's terminal panel; it was not backgrounded,
installed no service and created no identity, lease, signature, registry or
receipt.

R3c then started once from fresh B0 with the 22 complete R3/R3b records. Its
first scheduler candidate passed Contract, Verification and canary and
completed 32/32 screening pairs safely, but every case median tied: case W/L/T
`0/0/8`, pair W/L/T `3/2/27`, total-distance median `0`, CI `[0,0]`.
Protocol returned `SCREENING_FAIL_CASE_QUALITY` and Decision continued research.
The next H session read the new sibling failure, then its following provider
request hit the explicit 120-second `LLMTimeoutError`. With SDK retries disabled
and no Scion redispatch boundary, R3c stopped `valid_incomplete` with typed
`PROVIDER_CALL_BLOCKED_INFRA`; it reached no validation, frozen test or
promotion. Its terminal root remains untouched and is not resumable.

The repair is deliberately smaller than an adaptive retry system. An explicit
ordinary ResourceEnvelope value may allow `ProviderCaller` to redispatch the
same frozen request once after a typed timeout, transport fault or provider
fault. The SDK remains at zero retries; 429, auth, balance, format, schema,
response-size, generic and interruption faults are excluded. Each physical
dispatch consumes the unchanged shared cap and writes one terminal trace. The
redispatch remains one logical H/C turn and exposes no retry fact to H, research
history, Protocol, Safe Features or Decision. It adds no request identity,
lease, registration, receipt, request hash or repeated closure.

The bounded provider-retry repair gate was green at `2293 passed, 1 skipped` in
452.12 seconds, with zero failures. Focused provider/CLI/history gates and an
independent minimal-boundary review were also green. That evidence froze R3d as
a fresh-B0 experiment loading exactly 24 complete records in R3 -> R3b -> R3c
order with unchanged formal inputs.

R3d then launched once. Its first H read and cited R3b's complete
route-distinct-regret record and proposed a one-step capacity-scarcity
look-ahead. The exact candidate changed only `destroy_repair.py`, passed
Contract, Verification and canary, and completed all `32/32` initial-screen
pairs without subject or protected-objective failure. Case W/L/T was `4/0/4`,
pair W/L/T `15/7/10`, total-distance median `+2.25`, CI `[0,18]`; Protocol and
Decision required expanded screening. This is attributable history uptake and
weak positive adaptive-development evidence, not history-benefit, mechanism or
promotion evidence.

During the same candidate's expansion, the foreground process disappeared
after `35` attempted and `34` completed/valid pairs of `96`. No expanded
metric, event or Decision exists. The original shell, Python and solver child
are gone, while the root remains stale `running / pending`. With no OOM,
recorded signal or typed provider/solver failure, the root is classified
`INTERRUPTED_UNFINALIZED_EXTERNAL_PROCESS_LOSS` and will not be resumed or
rewritten. Its single history row contains only the complete initial screen;
the partial expanded counters are excluded from future H context. Full details
are in the
[`R3d interruption report`](../experiments/v0.4/v04-cvrp-r3d-adaptive-history-k1-sol-interruption-20260830.md).

The operational diagnosis found that R3d ran in a unified tool PTY that never
became the visible app terminal; its exposure request remained `queued`, and
the unattached session later disappeared. R3b and R3d's PTY-backed invocations
failed after `4957.185` and `5039.302` seconds. By comparison, R3's ordinary
non-TTY unified-exec foreground invocation completed exit `0` after
`77359.3004` seconds. This comparison is operational evidence, not a lifetime
guarantee or scientific result. A separate typed-finalization race was also
corrected: the CLI now keeps SIGTERM, SIGINT and SIGHUP handlers installed until
`finalize_requested_stop` is durable and suppresses repeated handler re-entry.
This cannot catch `SIGKILL`.

R3e then launched once through that non-TTY carrier from fresh B0 with the 25
complete R3 -> R3b -> R3c -> R3d records available. Its H read only current
source `source-0005`, not external history, and independently proposed a
bounded beam regret repair. The exact candidate passed Contract, Verification,
self-authored checks and canary and completed a safe `32/32` initial screen.
Case W/L/T was `3/1/4`, pair W/L/T `12/7/13`, total-distance median was `0`,
CI `[0,7]`, and Protocol required expanded screening. This is uncertain
adaptive-development evidence, not attributable history uptake, an expanded
screen pass, validation or promotion.

During the same candidate's expanded screen, R3e's non-TTY unified-exec
carrier also disappeared. It returned `failed/-1` after `7704.372878714`
seconds with empty stderr. The last heartbeat recorded `59` attempted and `58`
completed/valid pairs of `96`, zero observed failures, and no expanded metric,
event or Decision. No Scion process remains, while the root is stale `running /
pending`; journals contain no OOM, segfault or recorded process kill. The
low-level reaper or signal is unknown. R3e is therefore preserved as
`INTERRUPTED_UNFINALIZED_EXTERNAL_PROCESS_LOSS`, not resumed, rewritten or
backfilled. Full details are in the
[`R3e interruption report`](../experiments/v0.4/v04-cvrp-r3e-adaptive-history-k1-sol-interruption-20260831.md).

The R3 precedent did not establish a non-TTY lifetime guarantee. A minimal
provider/solver-free carrier probe has now verified one local tmux session:
create a lazy pane, set window-local `remain-on-exit`, replace it once with a
foreground command, and observe it from a later independent exec call. The
tmux server reparented to PID 1, the session survived the creating tool call,
and the dead pane retained process exit status or signal. This is operational
evidence only. The pane, console and tmux state never enter H, Protocol, Safe
Features or Decision and cannot authorize promotion or relaunch.

R3f then launched once through the preregistered tmux carrier and finished
normally: terminal `completed / requested_rounds_completed / valid`, 20/20
evaluated stages, 23 scheduled calls, three research rejections, 145/340
provider dispatches, three active branches and champion v1 unchanged. The
retained dead pane has exit status zero and agrees operationally with the
ordinary terminal artifacts; it is not scientific authority.

The one candidate to reach stage-held-out validation was cumulative across
`destroy_repair.py` and `scheduler.py`. It completed initial screening at
32/32 valid, case W/L/T `5/1/2`, median `+5.25`, CI `[0,14.5]`, then expanded
screening at 96/96 valid, case W/L/T `6/1/5`, median `+3`, CI `[0,9.5]`.
Validation attempted all 96 pairs but produced two candidate-only timeouts on
`X-n401-k29`, seeds 53 and 71. The champion had no failures. Protocol returned
`INCOMPLETE_EVIDENCE` and `CANDIDATE_RUNTIME_FAILURE`; Decision abandoned the
candidate. The observed case win rate was also only `0.50` against a `0.66`
threshold, and optimistic recovery of the two missing pairs cannot create a
seventh case win. This is negative candidate algorithm/runtime evidence, not
root infrastructure, a validation pass or promotion. The validation row is
excluded from H-only history.

R3f's final exact-relocate initial screen completed 32/32 valid pairs, case
W/L/T `2/1/5`, median `0`, CI `[0,25]`, and requested expansion at the formal
horizon. No expanded-stage metric or Decision artifact exists. V3
cumulative-depth semantics remain in force: this is association evidence for
a cumulative `scheduler.py` + `local_search.py` candidate, not an isolated
current-step effect and not an executable candidate to reconstruct in R3g.
Full evidence is in the
[`R3f postrun`](../experiments/v0.4/v04-cvrp-r3f-adaptive-history-k1-sol-postrun-20260901.md).

The R3f terminal history is frozen at 22 strict `cvrp` rows: 19 evaluated
screening rows and three research rejections, with no validation/frozen row.
The prospective R3g loader reads
`[21,1,2,1,1,22] = 48` ordered rows across R3 -> R3b -> R3c -> R3d -> R3e ->
R3f. No R3f candidate source, workspace, status, metric, SQLite state or tmux
state is an R3g input.

Three bounded prospective corrections address the R3f evidence without
rewriting it:

- nested destroy/repair loops poll the existing monotonic deadline and exit
  reserve; a typed internal expiry causes the partially mutated local candidate
  to be discarded before the scheduler exits its ALNS loop;
- ordinary before-source text captured at candidate materialization follows
  the current-step patch into exact-stage proposal evidence, so workspace
  cleanup cannot erase bounded before/after attribution;
- every Protocol stage and subprocess launch clears stale completion, phase,
  child-exit and child-elapsed progress fields before new work begins.

These changes add no mechanism selector, held-out exposure, identity, lease,
issuance, registration, signature, receipt, hash or repeated closure. The
adaptive embedded-VNS direction is a strong negative; pre-polish tournament
and initial-VNS budget directions receive no more host-directed investment.
Exact inter-route evaluation remains only promising cumulative association
evidence, not a fixed replay.

[`R3g`](../experiments/v0.4/v04-cvrp-r3g-adaptive-history-k1-sol-postrun-20260902.md)
launched from that isolated tree and stopped cleanly as
`valid_incomplete / execution_blocked_infra` after one evaluated screening and
one proposal-infrastructure step. Its three-route cyclic-exchange candidate
completed 32/32 valid pairs with no runtime or protected-objective failure,
case W/L/T `1/2/5`, pair W/L/T `4/6/22`, median `0`, CI `[-2,0]`, and
`SCREENING_FAIL_CASE_QUALITY`. The next H read current source but exported no
hypothesis: one frozen request received two charged/traced 502 overload
responses only milliseconds apart. R3g stopped at 10/340 provider dispatches;
champion v1 and all held-out stages remained unchanged. Its two strict history
rows preserve exactly those facts.

The first provider repair was ordinary and bounded: SDK retries remained zero;
a frozen request could receive at most two charged and traced Scion
redispatches after typed timeout/transport/provider faults. R3h then showed the
larger issue was a local transcript classification, not provider reliability.
The successor also treats exhausted transient/429 dispatches as an operational
proposal rejection so research schedules forward. Authentication, balance and
explicit global cost boundaries remain terminal.

[`R3h`](../experiments/v0.4/v04-cvrp-r3h-adaptive-history-k1-sol-postrun-20260903.md)
stopped cleanly as `valid_incomplete` after 11 evaluated stages. All 113
provider calls succeeded; the stop was an H session's configured 1.5M-character
transcript limit being misclassified as global resource exhaustion. It was not
a provider, solver, disk, or scientific-gate failure. Champion v1 remained
unchanged and R3h contributes 15 ordinary history rows.

The prospective long-run repair makes started proposal-local caps and exhausted
typed transient/429 calls reject only the current attempt; removes the default
total transcript cap; widens default H/C timeouts; auto-enables bounded H tools
when a live frontier needs them; makes output-history policy limits nonfatal;
and removes incidental K2/SIGHUP/stale-run blockers. Authentication, balance,
explicit operator cost/time boundaries, correctness checks, held-out isolation,
and promotion rules remain. No identity, lease, registration, receipt, or hash
lifecycle was added. The final repair suite is `2351 passed, 1 skipped, 0
failed` in 467.79 seconds; focused tests are `438 passed`, Ruff and diff checks
pass.

R3i is now live from commit `738d741e` in the isolated
`or-autoresearch-agent-r3i-dev` worktree and fresh
`v04-cvrp-r3i-normal-k1-sol-20260903-r1` root. Its first H/C closed with 11
successful first-attempt provider calls out of the 2,000-call envelope; the
unbounded transcript setting and widened 12-turn/8-read limits were loaded.
Proposal Verification and the formal canary passed, and initial screening
recorded its first valid pair with zero candidate, champion, shared, or
bilateral failures. The 40-stage campaign remains healthy in its local tmux
carrier and continues in background.

## Next scientific rung

1. Let the already launched R3i campaign continue in its one named local tmux
   carrier. Do not respawn it; only durable ordinary artifacts establish
   result validity.
2. R3i started from B0 in a fresh root. It is not a resume/retry of R3h.
3. Complete the 40-stage normal CVRP campaign with the exact 65 eligible R3 through
   R3h H-only records available for voluntary uptake. Keep validation and all
   prior candidate/process state excluded. Use the explicit no-transcript-cap
   limits and a generous 2,000-call / 14-day operator envelope.
4. Treat screening as adaptive development. Validation remains stage-held-out
   from H/C and prospective for each independent exact R3i candidate, but is
   not called globally never-observed because R3f already reached it. Let a
   successful exact candidate drain validation -> frozen -> deterministic
   promotion without reconstruction.
5. Only after promotion, compare that exact snapshot with original B0 on a
   newly frozen independent retained population with no LLM calls.

The tmux session is a single local process carrier, not a service, deployment,
distribution, scheduler or build. Additional authority objects,
identity/lease/receipt/hash lifecycles and repeated closure remain out of
scope. Scientific truth remains in ordinary durable campaign artifacts.
