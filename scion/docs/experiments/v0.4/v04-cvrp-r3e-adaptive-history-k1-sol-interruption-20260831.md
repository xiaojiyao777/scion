# CVRP R3e adaptive-history K1 postrun interruption report

Date: 2026-08-31 UTC

Preregistration:
[`v04-cvrp-r3e-adaptive-history-k1-sol-preregistration-20260830.md`](v04-cvrp-r3e-adaptive-history-k1-sol-preregistration-20260830.md)

Experiment root:
`/home/clawd/research/scion-experiments/v04-cvrp-r3e-normal-k1-sol-20260830-r1`

## Classification

R3e is classified `INTERRUPTED_UNFINALIZED_EXTERNAL_PROCESS_LOSS`.

The Scion Python process and its solver child no longer exist. The last durable
heartbeat is `2026-08-30T15:30:10.579855Z`, while `status.json` remains stale
at `running / pending`. There is no `campaign_summary.json`, terminal run
result, expanded-screen metric, typed terminal event or promotion artifact.
The non-TTY unified-exec carrier closed as `failed`, exit `-1`, after
`7704.372878714` seconds with empty stderr. Its completion event was recorded
at `2026-08-30T15:30:26.546Z`.

Kernel and user journals contain no OOM, segfault or recorded process kill for
the relevant interval. The outer 96-hour hardwall was not close to expiry, and
no provider or solver fault was durable at the loss boundary. The exact signal
or host reaper action was not recorded, so this report does not claim
`SIGKILL` or any other specific low-level cause.

The stale root is therefore neither live nor a completed campaign. It is not a
typed infrastructure result and is not negative evidence about the candidate.
R3e will not be resumed, retried, extended, terminalized retrospectively or
rewritten. Its partial expanded counters will not be converted into a metric,
Decision or history row.

## Complete ordinary evidence

One proposal and one initial screening stage closed durably before the process
disappeared:

- provider dispatches: `6/340`, all successful on `attempt_index=0`;
- transient redispatches: zero;
- H actions: `read_source(source-0005)` and `finalize_hypothesis`;
- external-history reads and citations: none;
- changed files: `policies/baseline_modules/destroy_repair.py` and the bounded
  scheduler call-site adjustment in `policies/baseline_modules/scheduler.py`;
- Contract, Verification, the self-authored checks and canary: passed;
- attempted/valid/failed pairs: `32/32/0`;
- case W/L/T: `3/1/4`;
- pair W/L/T: `12/7/13`;
- total-distance median delta: `0`, bootstrap CI `[0,7]`;
- candidate, champion, shared and bilateral failures: all zero;
- candidate-only timeout, invalid output and attributable infeasibility: zero;
- protected fleet regressions: zero;
- gate/Decision: `expand / expand_screening`, reason
  `SCREENING_EXPAND_INITIAL_QUALITY`.

Positive distance delta means the candidate was better. The complete case
results were:

| Case | pair W/L/T | case median delta | Case result |
|---|---:|---:|---|
| `P-n65-k10` | `1/2/1` | `-1.5` | loss |
| `A-n80-k10` | `3/1/0` | `+7.0` | win |
| `E-n101-k14` | `3/0/1` | `+6.5` | win |
| `M-n151-k12` | `1/1/2` | `0` | tie |
| `X-n120-k6` | `2/2/0` | `+39.0` | win, heterogeneous seeds |
| `X-n233-k16` | `0/0/4` | `0` | tie |
| `X-n439-k37` | `1/1/2` | `0` | tie |
| `X-n502-k39` | `1/0/3` | `0` | tie |

The initial result is statistically uncertain. Its net case score was `0.25`,
case loss rate `0.125`, and CI high `7`, so it satisfied the frozen initial
expansion rule. It did not satisfy the complete screening thresholds of case
win rate at least `0.6` and median delta at least `2`, and Protocol requires an
expanded screen before any pass. `expand_screening` is therefore only a
development decision to collect the frozen expansion, not a screen pass,
validation result, frozen result or promotion.

The ordinary metric
`metrics/8b78586b-703b-4f72-83f4-e8863ff87456.json`, its SQLite event and the
single `research_history.jsonl` row agree on this completed initial result.

## History and mechanism interpretation

R3e exposed the eight common observations followed by the 25 complete R3,
R3b, R3c and R3d records. H read only current source `source-0005`; it did not
read or cite an external history record. External-history availability is
therefore confirmed, but R3e provides no attributable history uptake or
history-benefit evidence.

The candidate replaced the single irreversible regret-2/regret-3 insertion
trajectory with a width-six bounded beam over partial repairs and passed a
deadline context through the scheduler only to marked built-in repair
operators. Complete initial-screen telemetry shows a quality-throughput trade:

- route-limit rejections: candidate `1`, champion `5`;
- controlled repair errors: candidate `10`, champion `0`;
- ALNS iterations: `616` versus `724`;
- accepted ALNS steps: `527` versus `597`;
- best updates: `43` versus `46`;
- completed regret repairs: `404` versus `462`;
- completed-regret acceptance rate: about `90.8%` versus `82.0%`;
- completed-regret best-update rate: about `7.9%` versus `6.5%`.

The metric marks mechanism attribution `unbound`, interpretation
`association_only` and exact activation `false`. The observed route-limit
shift may also have moved some late route-limit rejections into earlier
controlled repair failures. These diagnostics may inform later agent research,
but they do not establish a causal beam-repair mechanism claim and do not
authorize a host-selected replay or patch.

## Incomplete expanded work

The same exact candidate entered required expanded screening. The final
heartbeat reports:

- total planned pairs: `96`;
- attempted pairs: `59`;
- completed/valid pairs: `58/58`;
- observed failure counters: zero;
- last pair: `X-n502-k39`, seed `43`, time limit `90` seconds;
- last persisted child: exit `0`, elapsed `70.195` seconds, not yet credited as
  a completed pair.

There is no expanded metric, event, aggregate W/L/T, interval, gate or
Decision. These counters are operational progress only. Stale merged fields
such as `phase=canary` and `complete=true` cannot override the simultaneously
durable `protocol_state=running`, `58/96` progress and absence of a terminal
metric.

The single R3e history row was written at `2026-08-30T14:12:03Z`, before the
later expanded heartbeats. It contains only the complete `32/32` initial
screen. No part of the `58/96` partial expansion is present in that row.

## Interruption analysis and carrier repair

R3e deliberately replaced the earlier unattached PTYs with one non-TTY
unified-exec foreground process because R3 had once completed through that
carrier after `77359.3004` seconds. R3e demonstrates that the R3 observation
was not a lifetime guarantee: its tool-owned non-TTY process tree was removed
after about two hours even though provider research had closed, the current
solver child had exited `0`, and all durable failure counters were zero.

The previously repaired CLI signal path remains valid for a signal delivered
to Python: SIGTERM, SIGINT and SIGHUP handlers stay installed through typed
finalization, and repeated handler re-entry is suppressed. The missing typed
artifact here means only that Python did not complete that path; it does not
identify whether no catchable signal was delivered, the process tree was
removed externally, or finalization itself was prevented.

The next operational carrier is one local user-owned tmux session. A
provider/solver-free probe demonstrated that a detached tmux session survives
the unified-exec call that creates it, the tmux server is reparented to PID 1,
and its pane runs in an independent user-manager scope. The probe also
demonstrated a lazy pane followed by `remain-on-exit` and `respawn-pane` with a
foreground command. `remain-on-exit` preserves only the pane's exit status or
terminal signal for operational diagnosis; it is not scientific evidence.

This is a process-carrier correction, not distribution, deployment, a service,
installation, packaging or build work. It adds no Scion owner registry, object
identity, lease, issuance, registration, signature, receipt, request hash or
repeated closure. Machine reboot, OOM, administrator kill or loss of tmux/the
user manager remain possible and are not hidden by the carrier.

## Continuity boundary

Exactly one complete R3e `research_history.jsonl` record may be supplied after
the complete R3, R3b, R3c and R3d files to a future fresh campaign. The
production loader accepts that ordered prefix as `21 + 1 + 2 + 1 + 1 = 26`
strict `cvrp` records. Together with the eight common observations, R3e is
exposed last as `history-0034`.

No R3e status file, SQLite state, candidate source, workspace, provider
session, process state or partial expanded counter may be loaded or
reconstructed. The interruption classification is an operational
preregistration fact, not a fabricated H-history row.
