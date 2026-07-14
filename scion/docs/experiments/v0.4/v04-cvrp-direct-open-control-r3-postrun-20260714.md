# CVRP Direct Open Control R3 Postrun Audit

Date: 2026-07-14

Status: terminal framework-interface failure; do not resume or retry

## Run Identity

- root:
  `/home/clawd/research/scion-experiments/v04-cvrp-direct-open-control-r3-2r-gpt56sol-20260714T163231Z-claw`;
- clean runtime:
  `/home/clawd/research/or-autoresearch-agent-v04-direct-runtime-1978b426`;
- prepared/runtime commit: `1978b426`;
- campaign: `affe082b-8d54-49c2-bc0b-2011de024fed`;
- model: `gpt-5.6-sol`;
- requested rounds: `2`;
- started/ended: `2026-07-14T23:03:51Z` /
  `2026-07-14T23:04:32Z`;
- completion preflight: authenticated, HTTP 200, non-empty response;
- durable calls: H=`1`, C=`0`, total=`1`;
- retries or continuation attempts: `0`;
- solver evaluations/pairs: `0`.

The outer wrapper completed normally. Campaign accounting recorded
`invalid_research_rejected_only` and stopped on `execution_research_rejected`.
That vocabulary describes where the stop occurred, but not its actual cause.

## Sole Hypothesis

The model targeted `policies/baseline_modules/local_search.py` with action
`modify`. It proposed a capacity-feasible SWAP* neighborhood:

- remove one customer from each of two routes;
- find the best reinsertion position in the opposite route;
- use edge-delta evaluation and time polling;
- accept only strictly improving moves;
- preserve load, coverage, route-count, reserve-time, and return contracts.

This is materially different from the existing fixed-position `_swap`,
relocate, Or-opt, and 2-opt-star neighborhoods. It is an algorithmic solver
proposal, not a helper, telemetry, or boundary-satisfaction edit. R3 therefore
provides positive evidence that the simplified H context can elicit substantive
VRP search ideas. It provides no evidence about whether SWAP* improves the
formal benchmark because code generation and evaluation never occurred.

## Rejection Cause

The response used:

`change_locus = "solver_design local-search/VNS neighborhood set"`

The provider-visible tool schema declared only `type=string` and
`minLength=1`, so this value satisfied the producer contract. The generic
Pydantic parser also accepted it unchanged. Outer Contract C2 then required
exact membership in `['solver_design']` and rejected it.

Contract results:

- C0 governance constraints: pass;
- C1 schema: pass;
- C2 change locus: fail;
- C3 action/target: pass;
- K5 governance-envelope audit: pass.

The resulting chain was:

```text
generic provider schema accepts an arbitrary non-empty locus string
-> provider appends a useful mechanism description
-> generic parser accepts the value unchanged
-> outer C2 requires the exact problem-owned identifier
-> campaign terminates before C or solver evaluation
```

This is a framework producer/consumer interface mismatch. It must not be
interpreted as a failed algorithm, weak agent behavior, provider outage, or
formal research rejection.

## Integrity and Postrun Evidence

- provider attempts: one `initial` H attempt, no continuation ID;
- trace count: one hypothesis trace, no code trace;
- output policy: provider-managed; no output token parameter, ceiling,
  truncation retry, or semantic budget;
- prompt: 3 system blocks, 87,338 visible text characters;
- prepared, pre-campaign, and post-campaign data identity: 81 files, digest
  `ca7e470ec8d1f3569a690d10df5a170c4994108c71fecf5aa1a7a76b42630743`;
- missing cases, companions, unsafe paths: all zero;
- postrun readiness: 28 `ok`, 3 `skipped`, no required or optional failure;
- lineage: single attempt, branch, hypothesis, trace, prompt hash, and C2 event
  are reconcilable;
- scheduler and promotion mutation: none;
- secret hygiene: no persisted API-key value, authorization header, account ID,
  or email.

`current_run_analysis_ready=true` and `delegation_ready=true` mean the failure
is auditable. `quality_judgment=false` and `report_only=true` correctly prevent
an algorithm-quality or promotion conclusion.

## Repair Decision

The minimal repair is generic and call-local:

1. derive exact allowed values from authoritative provider-visible
   `research_surfaces[].name`;
2. deep-copy the base hypothesis tool and compile those values into the
   `change_locus` enum before an attempt starts;
3. retain the same allowed tuple in the immutable prompt turn snapshot;
4. validate the raw provider response against that exact tuple before creating
   `HypothesisProposal`;
5. preserve outer C2 as an independent problem-spec backstop.

Do not normalize descriptive values, relax C2, add a retry, or hard-code CVRP
surface names into generic core. The trace and provider cache key must continue
to receive the call-local schema.

A separate audit found a forced-diagnostic governance wiring mismatch:
`ContextManager` emits `forced_research_target`, while part of the governance/C0
path still looks for legacy forced-surface keys. R3 had no forced target, so the
finding did not affect this result and remains a separate repair item.

The repair passes the standard Scion suite at `1886 passed, 1 skipped` in
`499.32s`; compileall and `git diff --check` pass. Independent latest-diff
review reports P0/P1/P2 = 0 and separately passes `103` tests. After the repair
is committed and pushed, create a distinct clean R4 prepared root. Do not
resume, reuse, or relaunch R3, and do not launch R4 without a fresh explicit
authorization after prelaunch checks.
