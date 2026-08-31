# Scion v0.4 Current State

*Current as of: 2026-08-31*

Read [`../../TASK.md`](../../TASK.md) first. The sole architecture authority is
[`../../design/scion-architecture-v3.md`](../../design/scion-architecture-v3.md)
and its direct-runtime addendum. Historical experiment reports preserve
evidence; they do not define current runtime authority.

## Outcome

Warehouse has demonstrated real retained improvement:

- synthetic Scion promoted and independently retained `v1 -> v2 -> v3`;
- production-style Scion promoted and independently retained `v1 -> v2`.

CVRP remains open. The normal R3 campaign completed 16/16 formal stages and
made sustained algorithm changes across three research branches, but no exact
candidate reached validation or frozen testing. Champion B0/v1 therefore
remains unchanged, and R4 retained-B0 evaluation is correctly blocked.

R3's closest candidate passed expanded-screen quality with case W/L/T `7/2/3`
and median distance delta `+3.75`, but produced five repeatable candidate-only
hard timeouts on the largest case. Decision correctly abandoned it rather than
turning a quality result with incomplete runtime safety into a promotion.

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

[`R3f`](../experiments/v0.4/v04-cvrp-r3f-adaptive-history-k1-sol-preregistration-20260831.md)
is frozen as a fresh B0 campaign with exactly 26 complete history rows in
R3 -> R3b -> R3c -> R3d -> R3e order. Only R3e's completed initial-screen row
is eligible; its status, SQLite state, candidate, workspace and `58/96` partial
expansion remain excluded. All scientific inputs, thresholds and resources are
unchanged. The production loader observes `[21,1,2,1,1]` strict `cvrp` records,
formal readiness remains 37 cases and 73 files with no missing or unsafe input,
and the fresh root is absent. The fresh exact-tree provider-free,
non-campaign regression collected `2296` tests and completed `2295 passed, 1
skipped, 0 failed` in 437.80 seconds (438.83 seconds outer elapsed); focused
Ruff `E9,F,I` and `git diff --check` pass.

## Next scientific rung

1. Run the exact frozen R3f wrapper once. It creates the one named local tmux
   session with a lazy pane, sets `remain-on-exit`, and replaces that pane once
   with the preregistered foreground `exec env` command. Do not respawn a
   second time under this preregistration if a gate fails.
2. Start from B0 in the absent fresh R3f root. This is not a resume/retry of
   R3e, and the result is established only by durable campaign artifacts.
3. Run one 20-stage normal CVRP campaign with 21 complete R3 records, one R3b
   record, two R3c records, one R3d record and the one complete R3e
   initial-screen record available for voluntary uptake. Keep the R2 45-record
   corpus OFF and require used/rejected disposition only for each relation's
   latest live failure.
4. Keep the common research input and ordinary local history/frontier review
   ON. Screening is adaptive development evidence; validation and frozen remain
   prospective for an independently generated exact R3f candidate. The R3e
   beam patch and `58/96` partial expansion receive no replay or host priority.
5. Let any successful exact candidate drain screening -> validation -> frozen
   -> deterministic promotion without reconstruction.
6. Only after promotion, compare that exact snapshot with original B0 on a
   newly frozen independent retained population with no LLM calls.

The tmux session is a single local process carrier, not a service, deployment,
distribution, scheduler or build. Additional authority objects,
identity/lease/receipt/hash lifecycles and repeated closure remain out of
scope. Scientific truth remains in ordinary durable campaign artifacts.
