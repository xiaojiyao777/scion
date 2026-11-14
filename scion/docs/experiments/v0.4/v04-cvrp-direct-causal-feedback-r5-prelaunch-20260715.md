# CVRP Direct Causal-Feedback R5 Prelaunch Audit

*Prepared: 2026-07-15*

## Status

R5 is prepared only. It has not been launched and has made no live completion,
Hypothesis, or Code provider call. Launch remains a separate explicit operator
decision.

- root:
  `/home/clawd/research/scion-experiments/v04-cvrp-direct-causal-feedback-r5-2r-gpt56sol-20260715T141236Z-claw`;
- clean detached runtime:
  `/home/clawd/research/or-autoresearch-agent-v04-direct-runtime-3fb2f9a7`;
- prepared/runtime commit:
  `3fb2f9a72c914dd2fd98b1a3488ff7de06fdfa15`;
- model/rounds/solver limit: `gpt-5.6-sol`, `2`, `30` seconds per solver
  subprocess;
- workflow: `direct_v3`;
- forced surface/action/target: all empty;
- resume state: empty;
- provider calls: `0`.

## Repair Boundary

This root confirms the narrow R4 feedback/attribution repair. CVRP owns the
proposal-only causal packet; generic runtime code only transports its validated
envelope. The packet is excluded from DecisionFeatures and gates. Second-round
source is semantically deduplicated without losing complete current source,
patch guidance consistently requests one change object per file, typed proposal
trajectory fields are durable, and statistical branch evidence retains its
status and metric.

The repair adds no prompt/session/tool/file/item/token budget, size cutoff,
top-k selection, truncation, retry, target mandate, scheduler steering, or gate.
The 30-second solver limit remains a scientific subprocess fact.

Verification at the prepared commit is green:

- standard suite: `1900 passed, 1 skipped` in `497.39s`;
- compileall, `git diff --check`, focused proposal/trajectory/context tests,
  Protocol/CVRP tests, and R4 raw-metrics replay: passed;
- independent final review: P0/P1/P2=`0/0/0`.

## Static Launch Evidence

Guarded readiness was run against the prepared root without a live completion
probe or provider call.

- static ready: `true`;
- guarded-wrapper launch ready: `true`;
- guarded blockers: empty;
- selected-workflow blockers: empty;
- failed required checks: empty;
- external live-probe ready: `false`, as expected before launch;
- prepared/runtime commit and clean-tree identity: exact;
- generated `run.sh` SHA-256:
  `f3f98a8783650df8eeef614e3d883cd8862756dbaf7afb8bfaa767ada6ae2d2c`;
- formal CVRP data identity: 81 files, digest
  `ca7e470ec8d1f3569a690d10df5a170c4994108c71fecf5aa1a7a76b42630743`;
- missing cases, missing companions, and unsafe files: empty;
- `launch.env`: mode `0600`, containing only the key variable name
  `SCION_SHARED_PROXY_KEY`, never its value;
- live artifacts: no `pid`, `exit.txt`, completion receipt, or campaign output.

The prepared script bytes, detached runtime, manifest, and data identity must
remain unchanged between this audit and launch.

## Operator Launch Discipline

Only after explicit operator authorization:

1. export `SCION_SHARED_PROXY_KEY` in the launch process environment;
2. execute this prepared root's existing `run.sh` exactly once;
3. do not send a separate completion request, edit the root, add a forced
   target, resume another root, or reuse either R4 candidate;
4. poll observationally at low frequency;
5. after terminal completion, verify that H2 received the round-1 compact causal
   packet and one semantically deduplicated complete current-source view before
   drawing an algorithm or framework conclusion.
