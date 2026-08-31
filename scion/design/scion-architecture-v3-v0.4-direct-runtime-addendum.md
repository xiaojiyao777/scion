# Scion Architecture V3 — v0.4 Direct-Runtime Addendum

*Status: implementation note for v0.4; it cannot override
`scion-architecture-v3.md`*
*Updated: 2026-08-21*

## Purpose and precedence

V3 is the sole architecture authority for component ownership and control
boundaries. This addendum records the smaller v0.4 runtime selected after the
warehouse/CVRP experiment audit. It prevents old implementation examples from
being mistaken for requirements to restore adaptive provider retry loops,
algorithm-quality budgets, steering or context loss. Finite resource/action
bounds remain operational only; this addendum introduces no independent
normative layer.

For v0.4, use this order:

1. `scion-architecture-v3.md` for every architecture or boundary question;
2. `scion/TASK.md` and `scion/docs/status/current-state.md` for current work and
   validation status;
3. this addendum and the runbook only as descriptions of the current lightweight
   implementation. If either conflicts with V3, V3 wins.

## V3 invariants retained

- LLM output is tainted and may propose only a structured hypothesis and code.
- A bounded Creative session may use finite deliberate provider turns, but one
  branch attempt exports at most one tainted Hypothesis and, only after that H
  is approved, at most one tainted Code proposal.
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
| §8.7 | automatic infra retry | Provider SDK retries are zero. An ordinary resource envelope may explicitly allow at most one immediate `ProviderCaller` redispatch of the same frozen request for a typed timeout, transport fault or provider fault. Each physical dispatch consumes the shared provider cap and writes its own terminal trace; 429, authentication, balance, format, schema, response-size, generic and interruption faults are never redispatched. A successful redispatch remains one H/C turn and exposes only its successful response. Exhaustion or a second transient fault follows the existing typed terminal path. Statistical expand remains a Protocol action and is not a provider redispatch. |
| §10.4, §13 | LLM repair after light Contract/Verification failure | While a bounded Creative session is open, an invalid draft/action may receive enumerated feedback and a later deliberate revision; no H/C has yet been exported. A direct one-shot terminal response, or a bounded session closed without a valid export, becomes `RESEARCH_REJECTED`: it ends that H/C attempt, does not count as a formal round, and scheduler-forward schedules a fresh H on the exact clean base. Contract/Verification rejection follows the same attempt-terminal rule. Missing provider terminal response, transport/auth/timeout/resource failure, missing or invalid local proposal context, missing typed outcome, and interruption remain invocation-terminal. |
| §11.5, §12.2 | candidate fix budgets and campaign budget termination | v0.4 has no algorithm-quality, novelty or adaptive retry budget. An enabled Creative session has explicit finite provider-turn, read, search, public-test, output, transcript and shared provider-call limits. An ordinary resource envelope may additionally choose zero or one typed transient redispatch per frozen provider request; it neither adds logical turns nor expands the shared physical-dispatch cap. These are resource/action bounds only: they cannot select research content, alter Protocol or enter Safe Features/Decision. An operator-selected formal-round target and scientific subprocess/solver limits remain explicit experiment boundaries. |
| §11.1, §11.5 | one branch is one iterative direction; `max_active_branches = 3` is configurable | The v0.4 production default admits at most three active branches. State priority and FIFO choose runnable work; each branch deepens its own natural research direction without a host-authored diversity or mechanism gate. |
| §15.1–15.3 | recent-N context, compression, blacklist | H receives complete safe current context plus one canonical record per visible screening attempt. C receives the approved H and a complete ordinary path/content source mapping. There is no compact-to-fit, top-N, blacklist steering, or summary substitution. |
| §18 | `continue` after proposal/verification failure, possibly returning to Code | Open-session enumerated feedback is internal deliberation, not repair of an exported H/C. Once the direct response/session finalizes, abstains, abandons or closes without a valid export, proposal or Contract/Verification `RESEARCH_REJECTED` is attempt-terminal but scheduler-forward: no exported-H/C repair, no formal-round count, then a new H on the exact clean base. Provider turns without a terminal response and local/infrastructure outcomes stop/hold the invocation. |

## Direct v0.4 control flow

```text
ProblemRuntime + one validated ordinary source/history corpus
  -> one immutable provider-visible projection per deliberate turn
  -> optional finite Hypothesis research actions, or direct one-shot
  -> at most one tainted structured H
  -> Hypothesis Contract
  -> approved H + complete ordinary path/content source mapping
  -> optional finite Code research actions, or direct one-shot
  -> at most one tainted structured C
  -> Patch Contract
  -> transactional Workspace
  -> Verification
  -> Protocol
  -> Safe Features
  -> deterministic Decision
```

There is no general agent/tool loop and no Protocol, Decision, unrestricted
filesystem, shell, held-out or host-mechanism tool. The only multi-turn path is
the finite Creative research session over declared ordinary source/history and
public development checks. Multi-file algorithm changes remain supported by
the typed patch and exact per-file source binding.

An invalid bounded action may return enumerated feedback while the Creative
session is still open. A later deliberate revision is internal deliberation,
not repair or retry of an exported H/C. Once the session finalizes, abstains,
abandons, is rejected or loses a provider terminal response, that H/C cannot be
repaired, replayed, resumed or regenerated.

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

Scheduler-forward rejection includes a direct one-shot terminal response or a
bounded Creative session that closes without a valid H/C export. Open-session
invalid actions may receive enumerated feedback, but no exported proposal is
being repaired. Rejection also includes a structured H Contract, Patch
Contract or Verification rejection. Each `RESEARCH_REJECTED` records its phase
and typed diagnostic, ends the rejected attempt, and schedules a fresh H on the
clean base. It cannot repair, replay or regenerate an exported H/C, and it never
counts as a formal Protocol round.

A deliberate provider turn with no terminal response is different: transport, auth,
provider timeout, or upstream termination cannot establish a tainted H/C to
reject. Resource exhaustion, missing or invalid local proposal context, a
missing typed execution outcome, and interruption are likewise
invocation-terminal. They remain `NOT_EVALUATED`, `BLOCKED_INFRA`,
`RESOURCE_EXHAUSTED`, or `INTERRUPTED` as applicable and never authorize a new
provider turn inside that session or invocation.

There is no algorithm-quality, novelty or content-similarity gate. Explicit
Creative action/resource limits, provider transport limits and scientific
solver limits are operational boundaries, not research-quality gates; an
operator may stop explicitly at an attempt boundary.

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
fails Contract or Verification remains evidence only and cannot enter the
current executable source mapping, promotion ancestry, or the next executable
base.

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

Explicit prior `research_history` is ordered H-only evidence, not restored
campaign state. Problem-owned mechanism-family association is non-causal
proposal evidence: it is not exact activation, a Protocol gate, a Safe Feature,
Decision input or host mechanism selection. Creative drafts and
`research_basis` are tainted. Source/history/public-development values and
family association are non-authoritative proposal-only context. Only an
exported H/C proceeds through the unchanged Contract -> Verification ->
Protocol -> Safe Features -> Decision chain.

### Post-R3 bounded research responsibilities

The completed CVRP R3 campaign supplied the experiment evidence required by
the reintroduction rule below. Five consecutive late H attempts did not read
the latest live runtime/code failure records, and the final C attempt advanced
after its own falsifier reported a counterexample. These observations justify
exactly two finite Creative-session responsibilities:

- A self-authored falsifier result of `failed` is a negative counterexample to
  the exact executable patch value in that open C session. The same materialized
  path/action/before-source/after-source changes cannot become ready by omitting
  or weakening a later probe. A genuinely different executable value may be
  tested normally. This uses ordinary value equality, resets with the C
  session, and is not a cross-session blacklist, digest, identity, registry or
  substitute for Contract/Verification.
- Before a bounded H finalizes, or before each K=2 slot is staged, the agent
  must dispose of every explicit failure at the latest ordinary live round of
  each `current` and `sibling` relation. A later pass closes an older failure
  only within the same relation; activity in one relation cannot hide a live
  failure in the other.
  `used` means the agent read the record and cites it in the selected H basis;
  `rejected` needs an agent-authored bounded reason and does not force a read.
  External and older history remain optional. The host applies only this
  chronological failure frontier: it does not rank history, choose a nearest
  reference, choose a mechanism, assess the scientific merit of the reason or
  inject the disposition into Safe Features or Decision. K=2 retains only the
  selected slot's independently authored disposition.

A direct one-shot H interface cannot express the second responsibility. When
the frontier is nonempty it therefore exports no H and records one typed local
context outcome; a later explicit invocation must enable the bounded H session.
This is a mode-feasibility check, not a hypothesis-quality gate. The ordinary
formal runtime already declares a bounded H session, so a valid agent can
always continue by reading/citing a frontier record or rejecting it with a
reason. The selected basis and disposition remain tainted H-only evidence and
are persisted through the existing StepRecord, research-history, summary and
SQLite lineage write points without any new authority lifecycle.

Campaign reopen is not part of the fresh v0.4 research-effectiveness acceptance
path, so no active implementation work is allocated to reopen proofs or a
separate identity, signing, lease, or closure lifecycle. Current experiments
either continue their live branch state or start a fresh campaign explicitly.

This setting changes only scheduling topology; the Scheduler itself does not
cap provider calls, hypotheses, files, tokens, formal rounds or campaign
duration. A declared Creative session and global resource envelope may impose
finite action/resource limits without becoming research-quality policy.
Scheduler-forward `RESEARCH_REJECTED` continuation is a new attempt, not retry
authorization.
Provider calls without a terminal response and local/infrastructure/resource/
interruption outcomes remain invocation-terminal. The three-slot
maximum enables V3 breadth while preserving depth and evidence continuity
within every branch; it does not force the provider to invent distinct
mechanisms.

## Research-run interpretation

An autonomous v0.4 H/C control uses a fresh campaign on the selected current
source and must:

- parse its concrete command with the current `scion.cli.main run` CLI;
- optionally perform a provider/proxy health check before launch; this is an
  operator diagnostic, not a scientific gate or completion preflight;
- contain no forced surface, action, or target-file binding;
- start from a fresh campaign without restored mutable branch, champion or
  provider-session state; explicitly listed ordered H-only research history is
  ordinary evidence, not campaign reopen;
- retain ordinary run status, H/C traces, Protocol evidence, and Decision state;
- preserve provider SDK retry zero; if an ordinary resource envelope explicitly
  allows one typed transient `ProviderCaller` redispatch, charge and trace each
  physical dispatch while keeping the transport fact out of H/C, research
  history, Protocol, Safe Features and Decision;
- record every declared Creative/global resource limit and provider-required
  transport ceiling explicitly; never use a limit to rank mechanisms or
  silently truncate source/history;
- use the production default maximum of three active scientific-iteration
  branches rather than a formal-only scheduling override.

The narrow provider-free exact-candidate estimand instead uses
`run_fixed_candidate_funnel.py`, a fresh output directory and zero H/C/provider
calls. It enters complete-pair canary and the same Protocol -> Safe Features ->
Decision scientific chain where applicable; it is not an alternate autonomous
proposal runtime.

Postrun analysis and human-readable reports are useful diagnostics, not launch
gates. Framework correctness is necessary but not sufficient for v0.4
completion. Research effectiveness is proven only by the declared controls'
hypotheses, multi-file code when warranted, attributable solver behavior,
Protocol results, and full-solver outcomes. A valid, independently reviewed
negative mechanism result is scientific evidence, but it does not satisfy the
active Warehouse/CVRP solver-improvement task; that task requires the promotion
and independent replay outcomes stated in `TASK.md`.

None of these direct-runtime changes authorizes distribution, packaging,
build, deployment, root/systemd, Trust/Hash authority, object identity, lease,
signing, registration, receipt or duplicate-closure work.

## Reintroduction rule

Retry, algorithm-quality budget, compaction, blacklist, novelty gate or
host-steering mechanisms may not be reintroduced as compatibility fixes.
Finite resource/action bounds and problem-owned association telemetry remain
non-authoritative proposal support. A future version
must provide new experiment evidence, identify one implementation
responsibility and prove that the mechanism cannot alter Decision or suppress
valid algorithm research, then update the foundation/addendum explicitly before
implementation. “Responsibility” here never means an identity, capability,
lease, issuer, registry or receipt authority.
