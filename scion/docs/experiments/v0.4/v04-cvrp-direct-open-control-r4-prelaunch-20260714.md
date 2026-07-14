# CVRP Direct Open Control R4 Prelaunch Audit

Date: 2026-07-14

Status: prepared-only; explicit launch authorization required

## Identity

- run root:
  `/home/clawd/research/scion-experiments/v04-cvrp-direct-open-control-r4-2r-gpt56sol-20260714T234816Z-claw`;
- runtime:
  `/home/clawd/research/or-autoresearch-agent-v04-direct-runtime-ff14318c`;
- prepared/runtime commit: clean detached `ff14318c`;
- model: `gpt-5.6-sol`;
- rounds: `2`;
- solver subprocess limit: `30` seconds;
- force surface/action/target: all empty;
- completion preflight: enabled inside `run.sh`;
- provider/live-probe/campaign calls so far: `0`.

R3 is terminal interface evidence and must not be resumed, retried, or reused.
R4 is a distinct root prepared after the call-local surface-enum repair.

## Formal Data and Wrapper

The external data root resolves 41 declared cases into 81 identity files. The
ordered identity is:

`ca7e470ec8d1f3569a690d10df5a170c4994108c71fecf5aa1a7a76b42630743`

Missing cases, missing companions, and unsafe files are all zero. The generated
wrapper SHA256 is
`6b7d557e59e00b32c8deb90d9e573a018b8d5c47f51cf75255ec31809d80c869`
and matches the prepared contract. `launch.env` is mode `0600`; the key value
is absent, credential-literal scans are clean, and no live artifacts exist.

## Readiness

The selected guarded-wrapper readiness is green:

- `ready=true`;
- `static_ready=true`;
- `guarded_wrapper_launch_ready=true`;
- guarded launch blockers: `[]`;
- required/static-required failures: `[]`;
- campaign, scheduler, and promotion mutation: all `false`.

The generic `launch_ready=false` is expected because a separate live completion
was not sent. `run.sh` owns the sole pre-campaign completion preflight. There is
no `exit.txt`, campaign status/summary, provider trace, or execution marker.

## Native First-H Audit

The independent no-provider audit used the production path:

`ContextManager.build_hypothesis_context` ->
`proposal_context_snapshot` -> `build_prompt_turn_snapshot`

The active surface is only `solver_design`. Targetable scope is 12 entries: 11
concrete CVRP algorithm files plus `policies/baseline_modules/*.py`. The prompt
contains three system blocks of 183, 85,234, and 1,401 characters plus a
520-character user prompt.

The repaired call-local snapshot has:

- `allowed_change_loci == ("solver_design",)`;
- provider `change_locus.enum == ["solver_design"]`;
- exact-name guidance in the tool description;
- a deep-copied provider tool, leaving global `HYPOTHESIS_TOOL` unchanged;
- parse-time exact membership validation against the same tuple.

Counts are zero for successor IDs, target-intent, forced targeting,
mechanism ranking/denylist, telemetry gates, candidate caps, retry/backoff,
truncation, and agent/semantic/token/context/output budgets. Ordinary `budget`
tokens in the included solver source refer only to the 30-second solver runtime
mechanism; they do not impose an agent budget or output cutoff. Open algorithm
guidance remains present. Independent review reports P0/P1/P2 = `0/0/0`.

## Launch Discipline

Keep R4 prepared-only until the operator explicitly authorizes launch. At
launch, provide `SCION_SHARED_PROXY_KEY` only in the process environment. Poll
about every three minutes. Never auto-retry, resume, replace, or silently repair
this root. After a terminal outcome, audit H/C receipts, solver pairs, lineage,
algorithmic materiality, runtime, and postrun readiness before any continuation
or promotion decision.
