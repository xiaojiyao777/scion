# CVRP R3d adaptive-history K1 postrun interruption report

Date: 2026-08-30 UTC

Preregistration:
[`v04-cvrp-r3d-adaptive-history-k1-sol-preregistration-20260830.md`](v04-cvrp-r3d-adaptive-history-k1-sol-preregistration-20260830.md)

Experiment root:
`/home/clawd/research/scion-experiments/v04-cvrp-r3d-normal-k1-sol-20260830-r1`

## Classification

R3d is classified `INTERRUPTED_UNFINALIZED_EXTERNAL_PROCESS_LOSS`.

The foreground shell, Scion Python process and solver child no longer exist.
The last durable heartbeat is `2026-08-30T09:57:01.246651Z`, but
`status.json` still reports `running / pending`. There is no
`campaign_summary.json`, terminal run result, expanded-screen metric, typed
terminal event or promotion artifact. Kernel and user journals contain no OOM,
segfault or recorded kill for the relevant interval, and no provider or solver
failure was persisted at the interruption boundary.

The stale root is therefore neither live nor a completed campaign. It is not a
typed infrastructure failure and not negative evidence about the candidate.
The exact external loss mechanism was not recorded, so the classification does
not claim a particular signal or reaper implementation.

R3d will not be resumed, retried, extended, terminalized retrospectively or
rewritten. Its partial expanded counters will not be converted into a metric,
Decision or history row.

## Complete ordinary evidence

One ordinary proposal and one initial screening stage closed durably before the
process disappeared:

- provider dispatches: `7/340`, all successful on `attempt_index=0`;
- transient redispatches: zero, so R3d did not exercise the new retry path;
- H actions: `read_source(source-0005)`, `read_history(history-0030)`, then
  `finalize_hypothesis`;
- selected external basis: the complete R3b route-distinct-regret result;
- Contract, Verification and canary: passed;
- exact candidate workspace: `candidate-774o0q2l`;
- changed file: only `policies/baseline_modules/destroy_repair.py`;
- attempted/valid/failed pairs: `32/32/0`;
- case W/L/T: `4/0/4`; pair W/L/T: `15/7/10`;
- total-distance median delta: `+2.25`, bootstrap CI `[0,18]`;
- candidate, champion, shared and bilateral failures: all zero;
- candidate-only timeout, invalid output and attributable infeasibility: zero;
- protected fleet regressions: zero;
- gate/Decision: `expand / expand_screening`, reason
  `SCREENING_EXPAND_REQUIRED_FOR_PASS`.

The complete projections are the initial metric
`metrics/dc0aa71a-c862-41a4-bd2d-fca1f56de5e6.json`, its SQLite event and the
single `research_history.jsonl` row. They agree on the selected H basis, typed
evaluated outcome and Decision. This confirms the post-R3 selected-basis and
typed-outcome lineage repair at the ordinary write points.

The result is weak positive adaptive-development evidence, not an expanded
screen pass, validation result, frozen result or promotion. The case win rate
is `0.5`, the interval lower bound is zero and the pair effects are
heterogeneous. Champion B0/v1 remains unchanged.

## History and mechanism interpretation

R3d provides attributable external-history uptake: H read and cited R3b's
complete initial result, then proposed a one-step capacity-scarcity look-ahead
as a material extension of its route-distinct regret repair. This demonstrates
use of history, not causal benefit from history.

The extension also did not clearly outperform the simpler prior direction on
the shared initial population. R3b recorded case W/L/T `6/0/2` and median
`+6.5`; R3d recorded `4/0/4` and `+2.25`. This is a descriptive cross-campaign
comparison, not a randomized incremental-effect estimate.

The changed regret-2/regret-3 path was exercised in formal runs, but no direct
telemetry records how often the scarcity rule prevented stranding or singleton
creation. Problem-owned attribution remains `unavailable_legacy`,
`family_association`, with `exact_mechanism_activation=false`. One central
proxy also moved against the prediction: candidate/champion route-limit events
were `5/4`. The completed outcome can therefore support candidate association,
not an exact look-ahead mechanism claim.

## Incomplete expanded work

The same exact candidate had entered required expanded screening. The final
status reports:

- total planned pairs: `96`;
- attempted pairs: `35`;
- completed/valid pairs: `34/34`;
- observed failure counters: zero;
- last reported case/seed: `X-n120-k6`, seed `43`.

There is no expanded metric, event, aggregate, W/L/T, interval, gate or
Decision. These counters are operational progress only. In particular, the
single R3d history row contains only the complete `32/32` initial screen; it was
written at `09:22:53Z`, before the later expanded heartbeats through
`09:57:01Z`.

## Interruption analysis and repair boundary

R3d was launched through a unified tool PTY as a shell with a Python child. The
attempt to expose that terminal in the Codex panel returned `queued`, and the
task terminal reader confirmed that no app terminal was attached. The unified
session later disappeared after about 5039 seconds, taking the foreground
process tree with it. This unattached-session lifetime is the strongest
operational explanation for the loss; the exact low-level reaping event remains
unrecorded.

A separate CLI robustness gap was also found. After the first handled terminal
signal raised the typed stop exception, the old control flow restored default
signal handlers before `finalize_requested_stop` made the interruption durable.
A second signal in that interval could therefore terminate Python without a
typed terminal artifact. The repair keeps the existing handlers installed
through typed finalization and suppresses repeated handler re-entry. It does
not claim that Python can catch `SIGKILL` or prevent an external terminal owner
from disappearing.

The run-lifetime correction is operational and smaller: a future campaign must
first attach an otherwise empty foreground PTY to the visible Codex terminal,
prove that attachment with one ephemeral marker roundtrip, and only then run
the frozen launch block in the same session. The final command uses `exec env`
so the attached shell is replaced by the Scion Python process instead of
retaining a shell-to-child layer.

This adds no background process, service, scheduler, distribution, deployment,
build, PID registry, object identity, lease, registration, signature, receipt,
request hash or repeated closure.

## Continuity boundary

Exactly one complete R3d `research_history.jsonl` record may be supplied after
the complete R3, R3b and R3c files to a future fresh campaign. The production
loader accepts that ordered prefix as `21 + 1 + 2 + 1 = 25` strict `cvrp`
records. Together with the eight common prior observations it is exposed as the
last external entry, `history-0033`.

No R3d status file, metric file, SQLite state, candidate source, workspace,
provider session, process state or partial expanded counter may be loaded or
reconstructed. The interruption itself is an operational preregistration fact,
not a fabricated H-history row.
