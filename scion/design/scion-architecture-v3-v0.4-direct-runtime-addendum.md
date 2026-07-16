# Scion Architecture V3 — v0.4 Direct-Runtime Addendum

*Status: normative for v0.4 where it conflicts with operational examples in
`scion-architecture-v3.md`*
*Updated: 2026-07-16*

## Purpose and precedence

V3 remains the architecture authority for component ownership and trust
boundaries. This addendum records the smaller v0.4 runtime selected after the
warehouse/CVRP experiment audit. It prevents old implementation examples from
being mistaken for requirements to restore retry loops, budgets, steering, or
context loss.

For v0.4, use this order:

1. V3 invariants below;
2. this addendum for conflicting operational details;
3. `scion/TASK.md` and `scion/docs/status/current-state.md` for current work and
   validation status.

## V3 invariants retained

- LLM output is tainted and may propose only a structured hypothesis and code.
- The creative path makes at most one Hypothesis call and, only after that H is
  approved, at most one Code call.
- Contract owns structural and source-boundary validity.
- Verification owns executable correctness.
- Protocol owns comparative scientific judgment and split/seed isolation.
- Safe features are the only Decision input; free text cannot drive Decision.
- Decision is deterministic and branch transitions cannot be authored by the
  provider.
- Scheduler allocates runnable branch state; it cannot decide scientific truth.
- Workspace isolation, append-only lineage, atomic promotion, and human review
  remain trust boundaries.
- Problem semantics and algorithm guidance remain problem-owned.

## Operational examples superseded for v0.4

| V3 location | Earlier example | v0.4 direct-runtime rule |
|---|---|---|
| §4.2 | `recent_retry_count` and `budget_remaining_ratio` in the example `DecisionFeatures` | They are not Decision inputs. Decision consumes hard-safety facts and the typed Protocol gate outcome. |
| §5.1 | Contract `novelty check` | Contract checks schema, locus, path, source, interface, import/API and approved-H binding. Novelty/material difference is not a hard gate. |
| §8.7 | automatic infra retry | Provider SDK retries are zero. Infra failure terminalizes the durable attempt; a later invocation requires an explicit operator action. Statistical expand remains a Protocol action and is not a provider retry. |
| §10.4, §13 | LLM repair after light Contract/Verification failure | No automatic H/C repair call. Invalid response, Contract rejection, Verification failure, infra failure, and interruption remain distinct terminal outcomes. |
| §11.5, §12.2 | candidate fix budgets and campaign budget termination | v0.4 does not impose Scion-semantic prompt/session/tool/file/item/token/retry budgets. An operator-selected formal-round target and scientific subprocess/solver timeouts remain explicit experiment boundaries. A provider-required `max_tokens` parameter is an explicit transport ceiling, not a Scion stopping or research policy. |
| §11.1, §11.5 | one branch is one iterative direction; `max_active_branches = 3` is configurable | The v0.4 production default is one active branch so a screening continuation consumes that branch's preceding evidence on the next invocation. Explicit wider `Scheduler(max_active_branches=...)` configurations remain available for breadth ablation; they are not the formal-control default. |
| §15.1–15.3 | recent-N context, compression, blacklist | H receives complete safe current context plus one canonical record per visible screening attempt. C receives the approved H and complete `SourceLedger`. There is no compact-to-fit, top-N, blacklist steering, or summary substitution. |
| §18 | `continue` after proposal/verification failure, possibly returning to Code | Any non-`EVALUATED` execution outcome stops the current campaign invocation. The loop continues only after a formal candidate has reached a typed Protocol result. |

## Direct v0.4 control flow

```text
ProblemRuntime + complete safe source
  -> immutable ProposalContextSnapshot
  -> one durable Hypothesis provider call
  -> Hypothesis Contract
  -> approved H + complete SourceLedger
  -> one durable Code provider call
  -> Patch Contract
  -> transactional Workspace
  -> Verification
  -> Protocol
  -> Safe Features
  -> deterministic Decision
```

There is no target-intent call, model tool-selection loop, preview/grounding
repair, partial provider resume, or successor-specific host steering on this
path. Multi-file algorithm changes are supported by the typed patch and exact
per-file source ownership; the direct runtime is small, not single-file.

## Gate interpretation

The hard gates exist to protect trust boundaries, not to grade research style:

- Contract may reject malformed or unsafe structure, but not weak novelty,
  missing telemetry prose, or a host-preferred algorithm mechanism.
- Verification may reject incorrect execution evidence, but missing or
  incomplete diagnostic telemetry alone cannot invalidate a correct solver
  result.
- Protocol may expand a preregistered sample or reject weak evidence; it cannot
  request another provider call.
- Decision maps Protocol plus hard safety. It does not reinterpret telemetry,
  recompute statistics, or rank mechanisms.
- Scheduler uses branch state, priority/FIFO, execution hold, and active slots.
  It does not use branch lessons, stagnation prose, or mechanism similarity.

## v0.4 scientific-iteration scheduling and candidate ancestry

The default direct runtime admits one active scheduling branch. Evidence
continuity and code inheritance are separate:

```text
screening observation on branch A
  -> next H retains the complete safe canonical evidence
  -> typed Protocol/Decision outcome determines candidate disposition
  -> continuation-base planning selects exact reuse, provisional repair,
     clean code parent, or champion pivot
  -> next C receives source only from that exact selected base
```

Verification produces an immutable candidate snapshot but does not by itself
advance the branch research head. Expansion and queued validation/frozen stages
reuse the exact candidate without another H/C call. `CONTINUE_EXPLORE` after a
typed Protocol `fail` archives the negative candidate and returns code ownership
to its clean parent; `unclear/continue` may retain a provisional same-mechanism
head. A different problem-owned mechanism owner pivots from the current
champion. Rejected code remains evidence but cannot enter current SourceLedger,
promotion ancestry, or the next executable base.

Candidate disposition and research-head ownership commit with the completed
Decision transaction. Scheduler remains problem-neutral and reads only branch
state, priority/FIFO, execution hold, and active slots. Problem packages own
mechanism-owner classification; LLM free text cannot select a base.

The canonical screening history remains complete. It may be transported as a
normalized, reversible ledger that declares repeated schemas, cases, metrics,
and candidate identities once while retaining every observation and pair row.
This is lossless normalization, not recent-N selection, summary substitution,
token-aware compaction, top-k, or truncation.

A campaign reopen must restore canonical evidence, exact candidate snapshots,
disposition, and research-head ownership without duplication. If a referenced
snapshot is unavailable or its hash does not match, continuation fails closed
instead of silently reconstructing from another base.

This setting changes only scheduling topology. It does not cap provider calls,
hypotheses, files, tokens, formal rounds, or campaign duration, and it does not
authorize retry after a non-`EVALUATED` outcome. A wider explicit portfolio is
a separate breadth experiment and must not be silently substituted for the
v0.4 warehouse/CVRP completion controls.

## Formal-launch interpretation

A v0.4 formal control must be prepared from the exact clean commit and must:

- parse its concrete command with the current `scion.cli.main run` CLI;
- pass a real, non-empty completion preflight for the configured manifest model;
- contain no forced surface, action, or target-file binding;
- start from a fresh campaign without restored branch, champion, or evidence
  state;
- retain strict postrun reconstruction and readiness reports;
- preserve provider SDK retry zero;
- keep all Scion-semantic budgets and truncation controls absent while recording
  any provider-required transport ceiling explicitly;
- use the production default one-branch scientific-iteration scheduler rather
  than a formal-only portfolio override;
- run warehouse first, then an open CVRP control from the same runtime.

Framework correctness is necessary but not sufficient for v0.4 completion.
Research effectiveness is proven only by the formal controls' hypotheses,
multi-file code when warranted, attributable solver behavior, Protocol results,
and full-solver outcomes.

## Reintroduction rule

Retry, budget, compaction, blacklist, novelty, telemetry, or host-steering
mechanisms may not be reintroduced as compatibility fixes. A future version
must provide new experiment evidence, identify one authoritative owner, prove
that the mechanism cannot alter Decision or suppress valid algorithm research,
and update the foundation/addendum explicitly before implementation.
