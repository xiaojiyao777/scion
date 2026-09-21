# Scion Architecture V3 — v0.4 Direct-Runtime Addendum

*Status: implementation note for v0.4; it cannot override
`scion-architecture-v3.md`*
*Updated: 2026-09-20*

## Purpose and precedence

V3 is the sole architecture authority for component ownership and control
boundaries. This addendum records the smaller v0.4 runtime selected after the
warehouse/CVRP experiment audit. It prevents old implementation examples from
being mistaken for requirements to restore adaptive provider loops,
algorithm-quality budgets, steering, context loss, or self-attesting object
lifecycles. Bounded transport redispatch and proposal-local actions remain
operational only; there is no default transcript-lifetime cap. This addendum
introduces no independent normative layer.

Repository sessions enter through [`../../AGENTS.md`](../../AGENTS.md) and the
current handoff it names. That entry determines what is current and what work is
authorized; it does not replace V3 as architecture authority.

For v0.4, after the repository entry, use this precedence:

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
| §8.7 | automatic infra retry | Provider SDK retries are zero. An ordinary resource envelope may explicitly allow at most two `ProviderCaller` redispatches of the same frozen request for a typed timeout, transport fault, provider fault, or rate limit. Each physical dispatch consumes the shared cap and writes its own best-effort terminal trace. Backoff lower bounds are 5 seconds and 20 seconds; a provider `Retry-After` may extend them. The local proxy's exact synthetic no-usable-account 401 is temporary provider unavailability, while real authentication and balance failures remain distinct and terminal. A successful redispatch remains one H/C turn. Exhausted typed transient/rate-limit dispatches reject only the current proposal attempt and scheduler-forward; they never enter H, history, Protocol, or Decision. Statistical expansion is a Protocol action, not provider redispatch. Historical artifacts retain their actual behavior. |
| §10.4, §13 | LLM repair after light Contract/Verification failure | While a bounded Creative session is open, an invalid draft, action, or malformed wrapper may receive bounded enumerated feedback and a later deliberate revision; no H/C has yet been exported. A successful Code `ready` after the latest exact draft passes its host development check returns that patch immediately, without a redundant final confirmation turn. A closed attempt without valid export, Contract/Verification rejection, a started proposal-local limit, or exhausted typed transient/rate-limit provider dispatches becomes attempt-local `RESEARCH_REJECTED`, counts no formal round, and scheduler-forward schedules a fresh H. Exported H/C values are never repaired or replayed. Real auth/balance, explicit shared call-cap exhaustion, interruption, and unclassified infrastructure failures keep their separate typed stop/hold lanes. |
| §11.5, §12.2 | candidate fix budgets and campaign budget termination | v0.4 has no algorithm-quality, novelty, adaptive-retry, or transcript-lifetime budget. `max_transcript_chars` defaults to absent. Optional proposal-local turn/read/search/public-test/output limits constrain one H/C attempt and cannot select research content, silently truncate source/history, alter Protocol, or enter Safe Features/Decision. The shared physical-dispatch cap, an explicitly selected formal-round target, and scientific subprocess/solver limits remain experiment boundaries; none is a hidden lifetime limit on a branch algorithm object. |
| §11.1, §11.5 | one branch is one iterative direction; `max_active_branches = 3` is configurable | The v0.4 production default admits at most three active branches. State priority and FIFO choose runnable work; each branch deepens its own natural research direction without a host-authored diversity or mechanism gate. |
| §15.1–15.3 | recent-N context, compression, blacklist | H receives complete safe current context plus one canonical record per visible screening attempt. C receives the approved H and a complete ordinary path/content source mapping. There is no compact-to-fit, top-N, blacklist steering, or summary substitution. |
| §18 | `continue` after proposal/verification failure, possibly returning to Code | Open-session enumerated feedback is internal deliberation, not repair of an exported H/C. A closed-invalid proposal, started local-limit stop, exhausted typed transient/rate-limit dispatches, Contract rejection, or Verification rejection is attempt-terminal `RESEARCH_REJECTED`: no exported-H/C repair, no formal-round count, then a new H on the exact clean base. Real authentication/balance, explicit global cap, interruption, and other infrastructure outcomes retain their typed stop/hold lanes. |

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
not repair or retry of an exported H/C. A Code session's successful `ready`
returns the latest exact draft only after its current host development check
passes; it does not trigger a second confirmation/closure turn. Once an H/C is
exported, abstained, abandoned, or rejected, that value cannot be repaired,
replayed, resumed, or regenerated.

## Pre-Protocol research rejection

The user-selected round target counts formal Protocol observations, not H/C
attempts. A completed research rejection must not silently reduce that target.
The typed boundary is:

| Execution outcome | Attempt | Invocation | Formal count |
|---|---|---|---:|
| `EVALUATED` | complete | continue or finish target | 1 |
| attempt-local `RESEARCH_REJECTED` | rejected and immutable | schedule a new H | 0 |
| `NOT_EVALUATED` | no trusted research conclusion | stop/hold | 0 |
| `BLOCKED_INFRA` | unavailable | stop/hold | 0 |
| `RESOURCE_EXHAUSTED` | unavailable | stop/hold | 0 |
| `INTERRUPTED` | incomplete | stop/hold | 0 |

Scheduler-forward rejection includes a direct one-shot terminal response or a
bounded Creative session that closes without a valid H/C export. Open-session
invalid actions may receive enumerated feedback, but no exported proposal is
being repaired. Rejection also includes a structured H Contract, Patch
Contract or Verification rejection, a started proposal-local limit, and an
exhausted typed timeout/transport/provider/rate-limit dispatch sequence. Each
`RESEARCH_REJECTED` records its phase and typed diagnostic, ends the rejected
attempt, and schedules a fresh H on the clean base. It cannot repair, replay or
regenerate an exported H/C, and it never counts as a formal Protocol round.

Real authentication or balance failure, explicit shared provider-cap
exhaustion, interruption, missing typed execution outcome, and unclassified
local/infrastructure failure are different. They remain `NOT_EVALUATED`,
`BLOCKED_INFRA`, `RESOURCE_EXHAUSTED`, or `INTERRUPTED` as applicable and do not
become algorithm history. The exact local-proxy synthetic 401 exception remains
narrowly classified as temporary provider unavailability; it does not weaken
real authentication handling.

There is no algorithm-quality, novelty, content-similarity, or default total
transcript gate. Optional proposal-local action limits, provider transport
limits, explicit shared caps, and scientific solver limits are operational
boundaries, not research-quality gates or hidden campaign lifetime limits.

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
Each branch's research object is its complete runnable source tree, not an
object ID, patch receipt, or hash chain. Evidence continuity and code
inheritance are separate:

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
Verification-to-Protocol boundary retains one local exact-content equality
check for the same executable candidate (the implementation may compact that
single comparison with a digest); it creates no artifact identity, digest
lineage, owner, receipt, or self-proof lifecycle. Expansion and queued
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

### Post-R3 development safeguards

The completed CVRP R3 campaign supplied the experiment evidence required by
the reintroduction rule below. Five consecutive late H attempts did not read
the latest live runtime/code failure records, and the final C attempt advanced
after its own falsifier reported a counterexample. These observations justify
one narrow executable safeguard and better ordinary context; they do not
justify a failure-reading proof or history authority layer:

- A self-authored falsifier result of `failed` is a negative counterexample to
  the exact executable patch value in that open C session. The same materialized
  path/action/before-source/after-source changes cannot become ready by omitting
  or weakening a later probe. A genuinely different executable value may be
  tested normally. This uses ordinary value equality, resets with the C
  session, and is not a cross-session blacklist, digest, identity, registry or
  substitute for Contract/Verification.
- Recent current/sibling failures remain complete ordinary H-visible evidence.
  The agent may read, use, or ignore them; the host must not choose a nearest
  record or mechanism, require an exact `used/rejected/cited` closure, grade an
  agent-authored reason, or inject history use into Safe Features or Decision.
  Any reachable compatibility check that still requires exact failure-frontier
  disposition is implementation debt, not a V3 invariant. It must not be
  expanded or made a precondition for multi-day algorithm research.

Campaign reopen is not part of the fresh v0.4 research-effectiveness acceptance
path, so no active implementation work is allocated to reopen proofs or a
separate identity, signing, lease, or closure lifecycle. Current experiments
either continue their live branch state or start a fresh campaign explicitly.

Stale reconciliation now copies the already materialized branch tree into
isolated staging, repeats Verification and screens it against the new champion.
Its prior Contract acceptance still applies: no new H/C is exported and no
archived patch is reapplied or re-contracted. Champion edits are not merged into
the branch. A missing verified tree is a typed operational failure, never a
request to reconstruct it from history. Decision reanchors the comparison and
resets its sample-expansion counts; subsequent stages reuse the exact candidate.

The normal CLI accepts `--source-tree` for an explicitly selected complete
algorithm directory, defaulting to the problem root. Campaign composition copies
the initial source into its own read-only champion snapshot. CLI baseline version,
branches, stages and provider counters start fresh; optional `--research-history`
remains ordered H-only evidence. Status exposes ordinary source paths for the
initial tree, current champion and live branch heads. No manifest or restoration
of old campaign state is involved.

This setting changes only scheduling topology; the Scheduler itself does not
cap provider calls, hypotheses, files, tokens, formal rounds or campaign
duration. Optional proposal-local limits and an explicit global resource
envelope may impose finite operational boundaries without becoming
research-quality policy or a default transcript lifetime.
Scheduler-forward `RESEARCH_REJECTED` continuation is a new attempt, not retry
authorization.
Exhausted typed transient/rate-limit calls are attempt-local; real auth,
balance, explicit global caps, interruption, and other infrastructure outcomes
retain their typed stop/hold lanes. The three-slot
maximum enables V3 breadth while preserving depth and evidence continuity
within every branch; it does not force the provider to invent distinct
mechanisms.

## Research-run interpretation

An autonomous v0.4 H/C control uses a fresh campaign on the selected current
source and must:

- begin from the repository entry and current authorization named in
  `AGENTS.md`; this addendum does not authorize a launch;
- parse its concrete command with the current `scion.cli.main run` CLI;
- optionally perform a provider/proxy health check before launch; this is an
  operator diagnostic, not a scientific gate or completion preflight;
- contain no forced surface, action, or target-file binding;
- start from a fresh campaign without restored mutable branch, champion or
  provider-session state; explicitly listed ordered H-only research history is
  ordinary evidence, not campaign reopen;
- retain ordinary run status, H/C traces, Protocol evidence, and Decision state;
- preserve provider SDK retry zero; if an ordinary resource envelope explicitly
  allows up to two typed timeout/transport/provider/rate-limit `ProviderCaller`
  redispatches, use the 5-second then 20-second lower bounds plus a longer
  provider `Retry-After` when supplied, charge and trace each physical dispatch,
  and keep the transport fact out of H/C, research history, Protocol, Safe
  Features and Decision; exhaustion rejects only that attempt;
- record every explicitly selected proposal-local/global resource limit and
  provider-required transport ceiling; the total transcript limit is absent by
  default, and no limit may rank mechanisms or silently truncate source/history;
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
