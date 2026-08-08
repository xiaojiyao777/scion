# Scion Architecture V3 — v0.4 Direct-Runtime Addendum

*Status: implementation note for v0.4; it cannot override
`scion-architecture-v3.md`*
*Updated: 2026-08-08*

## Purpose and precedence

V3 is the sole architecture authority for component ownership and control
boundaries. This addendum records the smaller v0.4 runtime selected after the
warehouse/CVRP experiment audit. It prevents old implementation examples from
being mistaken for requirements to restore retry loops, budgets, steering, or
context loss; it introduces no independent normative layer.

For v0.4, use this order:

1. `scion-architecture-v3.md` for every architecture or boundary question;
2. `scion/TASK.md` and `scion/docs/status/current-state.md` for current work and
   validation status;
3. this addendum and the runbook only as descriptions of the current lightweight
   implementation. If either conflicts with V3, V3 wins.

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
- Workspace isolation, minimal append-only research lineage, promotion after
  complete declared Protocol evidence, and human review remain boundaries.
- Problem semantics and algorithm guidance remain problem-owned.

## Minimal ownership and equality interpretation

The V3 terms “owner”, “lineage”, and “exact source” do not require a local PKI.
For v0.4:

- branch, H, C, and experiment identifiers are ordinary references between
  human-readable records, not capabilities or authority objects;
- one transition function owns each mutable branch-state change, without an
  issuer/claim/spend protocol or nested intent/commit/closure graph;
- exact candidate content, case/seed selection, exact stage reuse and
  independent evaluation are retained where scientific equivalence requires
  them;
- a digest may compact an equality comparison, but it cannot sign, authorize,
  lease, register, accept, or attest the object it describes;
- nonce ledgers, source-acceptance receipts, review-closure ingestion, object
  identity graphs, and repeated reopen proofs are outside the research runtime.

## Operational examples superseded for v0.4

| V3 location | Earlier example | v0.4 direct-runtime rule |
|---|---|---|
| §4.2 | `recent_retry_count` and `budget_remaining_ratio` in the example `DecisionFeatures` | They are not Decision inputs. Decision consumes hard-safety facts and the typed Protocol gate outcome. |
| §5.1 | Contract `novelty check` | Contract checks schema, locus, path, source, interface, import/API and approved-H binding. Novelty/material difference is not a hard gate. |
| §8.7 | automatic infra retry | Provider SDK retries are zero. Infra failure terminalizes the durable attempt; a later invocation requires an explicit operator action. Statistical expand remains a Protocol action and is not a provider retry. |
| §10.4, §13 | LLM repair after light Contract/Verification failure | No automatic repair or second call for the same H/C. Every valid Contract/Verification `RESEARCH_REJECTED` is an independent typed event: it ends that H/C, does not count as a formal round, and scheduler-forward schedules a fresh H on the exact clean base. Invalid provider response, infra/resource failure, and interruption remain invocation-terminal. |
| §11.5, §12.2 | candidate fix budgets and campaign budget termination | v0.4 does not impose Scion-semantic prompt/session/tool/file/item/token/retry budgets. An operator-selected formal-round target and scientific subprocess/solver timeouts remain explicit experiment boundaries. A provider-required `max_tokens` parameter is an explicit transport ceiling, not a Scion stopping or research policy. |
| §11.1, §11.5 | one branch is one iterative direction; `max_active_branches = 3` is configurable | The v0.4 production default admits at most three active branches. State priority and FIFO choose runnable work; each branch deepens its own natural research direction without a host-authored diversity or mechanism gate. |
| §15.1–15.3 | recent-N context, compression, blacklist | H receives complete safe current context plus one canonical record per visible screening attempt. C receives the approved H and complete `SourceLedger`. There is no compact-to-fit, top-N, blacklist steering, or summary substitution. |
| §18 | `continue` after proposal/verification failure, possibly returning to Code | A finalized Contract/Verification `RESEARCH_REJECTED` is attempt-terminal but scheduler-forward: no same-H/C repair, no formal-round count, then a new H on the exact clean base. Other non-`EVALUATED` outcomes stop/hold the invocation fail-closed. |

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
per-file source binding; the direct runtime is small, not single-file.

## Pre-Protocol research rejection

The user-selected round target counts formal Protocol observations, not H/C
attempts. A completed research rejection must not silently reduce that target.
The typed boundary is:

| Execution outcome | Attempt | Invocation | Formal count |
|---|---|---|---:|
| `EVALUATED` | complete | continue or finish target | 1 |
| finalized `RESEARCH_REJECTED` | rejected and immutable | schedule a new H | 0 |
| `NOT_EVALUATED` | no trusted research conclusion | stop/hold | 0 |
| `BLOCKED_INFRA` | unavailable | stop/hold | 0 |
| `RESOURCE_EXHAUSTED` | unavailable | stop/hold | 0 |
| `INTERRUPTED` | incomplete | stop/hold | 0 |

Scheduler-forward rejection is limited to a structured H Contract, Patch
Contract, or Verification rejection. Each valid `RESEARCH_REJECTED` is an
independent append-only typed event with its phase, diagnostic code, clean code
parent, and cleanup result. It ends the rejected H/C and schedules a fresh H;
it cannot repair or regenerate the rejected C. Provider parse/schema failure is
`NOT_EVALUATED`, not permission to call the model again.

There is no Scion-semantic rejection cap, attempt budget, or
content-similarity gate. Explicit provider-transport and scientific solver
timeouts remain operational boundaries, not research-quality gates; an operator
may stop explicitly at an attempt boundary.

## Gate interpretation

The hard gates exist to protect V3 control boundaries, not to grade research style:

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

The default direct runtime admits at most three active scheduling branches.
Evidence
continuity and code inheritance are separate:

```text
screening observation on branch A
  -> next H retains the complete safe canonical evidence
  -> typed Protocol/Decision outcome determines candidate disposition
  -> continuation-base planning selects exact stage reuse or the verified
     provisional branch head
  -> next C receives source only from that exact selected base
```

Verification leaves the candidate in isolated staging and does not itself
advance the branch research head. Once the verified candidate is exposed to
Protocol, the branch carries only a plain evaluation marker: `pending` or
`completed`, the hypothesis reference, and `explore` or `reconcile` kind. The
Verification-to-Protocol boundary retains one code-hash equality check for the
same executable candidate; it creates no artifact identity, snapshot digest,
owner, receipt, or self-proof lifecycle. Expansion and queued
validation/frozen stages reuse the exact candidate without another H/C call.
After Contract and Verification pass and screening completes,
`CONTINUE_EXPLORE` retains that verified candidate as the provisional branch
head, including for a typed Protocol `fail`; the next H sees its complete safe
screening evidence and the next C receives that branch-current source.
Verification failure restores the last clean branch source, or champion when
the branch has never produced verified code. A provisional head is not a
champion and cannot bypass validation, frozen holdout, or promotion. Code that
fails Contract or Verification remains evidence only and cannot enter current
SourceLedger, promotion ancestry, or the next executable base.

The completed Decision applies candidate disposition, branch state, hypothesis
status, evidence projection, and existing lineage synchronously. Workspace
cleanup remains diagnostic-only after that application: restore-parent,
finalize-candidate, or abandon cleanup cannot reopen or alter the scientific
Decision. Scheduler remains problem-neutral and reads only branch state,
priority/FIFO, execution hold, and active slots. Problem packages own
mechanism-owner classification; LLM free text cannot select a base.

The canonical screening history remains complete in ordinary campaign evidence.
The active runtime adds no candidate-identity manifest, digest chain, source
attribution closure, or normalization authority around it. Reversible
lossless factoring may be considered only after it becomes a measured research
obstacle; recent-N selection, summary substitution, top-k and truncation remain
outside this path.

Campaign reopen is not part of the fresh v0.4 research-effectiveness acceptance
path, so no active implementation work is allocated to reopen proofs or a
separate identity, signing, lease, or closure lifecycle. Current experiments
either continue their live branch state or start a fresh campaign explicitly.

This setting changes only scheduling topology. It does not cap provider calls,
hypotheses, files, tokens, formal rounds, or campaign duration. Scheduler-forward
`RESEARCH_REJECTED` continuation is a new attempt, not retry authorization;
every other non-`EVALUATED` outcome remains invocation-terminal. The three-slot
maximum enables V3 breadth while preserving depth and evidence continuity
within every branch; it does not force the provider to invent distinct
mechanisms.

## Research-run interpretation

A v0.4 declared control uses a fresh campaign on the selected current source and
must:

- parse its concrete command with the current `scion.cli.main run` CLI;
- optionally perform a provider/proxy health check before launch; this is an
  operator diagnostic, not a scientific gate or completion preflight;
- contain no forced surface, action, or target-file binding;
- start from a fresh campaign without restored branch, champion, or evidence
  state;
- retain ordinary run status, H/C traces, Protocol evidence, and Decision state;
- preserve provider SDK retry zero;
- keep all Scion-semantic budgets and truncation controls absent while recording
  any provider-required transport ceiling explicitly;
- use the production default maximum of three active scientific-iteration
  branches rather than a formal-only scheduling override.

Postrun analysis and human-readable reports are useful diagnostics, not launch
gates. Framework correctness is necessary but not sufficient for v0.4
completion. Research effectiveness is proven only by the declared controls'
hypotheses, multi-file code when warranted, attributable solver behavior,
Protocol results, and full-solver outcomes. A valid, independently reviewed
negative mechanism result is scientific evidence, but it does not satisfy the
active Warehouse/CVRP solver-improvement task; that task requires the promotion
and independent replay outcomes stated in `TASK.md`.

## Reintroduction rule

Retry, budget, compaction, blacklist, novelty, telemetry, or host-steering
mechanisms may not be reintroduced as compatibility fixes. A future version
must provide new experiment evidence, identify one authoritative owner, prove
that the mechanism cannot alter Decision or suppress valid algorithm research,
and update the foundation/addendum explicitly before implementation.
