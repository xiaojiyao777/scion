# Scion v0.5 Continuous Algorithm Research Design

*Working branch: `codex/v0.5-dev` · Current as of: 2026-11-15*

Follow [`../AGENTS.md`](../AGENTS.md) and
[`current-state.md`](docs/status/current-state.md) before acting.
[Architecture V3](design/scion-architecture-v3.md) is the sole architecture
source; the [direct-runtime addendum](design/scion-architecture-v3-v0.4-direct-runtime-addendum.md)
describes current implementation. The
[stage review](docs/planning/v0.4/v04-stage-review-and-v05-research-mechanism-proposal-20261114.md)
records the accepted v0.4 stage closeout and its evidence. The
[v0.5 design](design/v0.5/README.md) specifies the next mechanism and acceptance
draft; it is not an implemented runtime or second architecture authority.

## Objective and priority

Scion should enable its own agent to conduct sustained combinatorial algorithm
research and produce independently retained complete-solver improvements.
This includes acquiring evidence, testing explanations, revising conclusions and
continuing research; formal acceptance remains deterministic and independent.

The November 14 user request prioritizes a stage retrospective and deep mechanism
review over continuing the support-patch / experiment / analysis cycle. On
November 15 the user explicitly accepts this direction:

> 让 agent 围绕一个持续的算法问题，自主观察、实验、修正解释，再提交正式 H/C。

The November 15 requests accept the stage-closeout standard, retain the CVRP
scientific objective and begin detailed v0.5 mechanism/acceptance design. The
latest request explicitly authorizes committing the documentation, tagging
`v0.4`, integrating into the default branch and pushing, then entering v0.5.
The closeout commit `eb339d32`, annotated tag `v0.4` and `master` merge `6befa390`
are now published to origin. The remote default is `master` (there is no `main`
or `mian`). Active development has moved to `codex/v0.5-dev`, created from that
merge. v0.5 is formally the active design/development stage; its specific new
interfaces remain a design draft. This handoff does not launch R27 or change
runtime/scientific inputs.

Keep two statuses separate:

- **Scientific objective:** Warehouse retained improvement is accepted; CVRP
  retained improvement remains unconfirmed. Original v0.4 scientific acceptance
  is not complete or relabeled as passed.
- **Framework evolution:** assess the current mechanism and design the next
  version without waiting indefinitely for a positive CVRP result. v0.5 must
  represent a reviewable capability change and evaluation, not a claim that
  the old unmet target has been satisfied.

## Accepted v0.4 stage closeout

The milestone accepted from section 8 of the
[stage review](docs/planning/v0.4/v04-stage-review-and-v05-research-mechanism-proposal-20261114.md)
is a cross-problem research foundation demonstrated through substantive algorithm
work, continuous verified source, trustworthy scientific decisions and an explicit
account of its effectiveness and limits. It has five evidence conditions:
generic trusted execution; real sustained algorithm work; resolved scientific
outcome reporting; usable source/input/evidence handoff; and a distinct testable
next-version question. The evidence mapping is kept in that report.

**v0.4 mechanism stage is closed; original scientific success acceptance is
partially met.** Warehouse retained improvement is accepted; CVRP retained
improvement is unconfirmed and carried forward. The user explicitly accepted
this stage decision; the original scientific criterion has not been rewritten.
No further R27 is required for closure. v0.5 is in detailed design, not implemented
or empirically accepted. The annotated `v0.4` tag records the mechanism-stage
closeout and the unmet CVRP goal. Integration and the new development branch do
not themselves change the existing v0.4 direct-v3 runtime.

## Completed stage review

- [x] Read canonical entry, V3/addendum and relevant design/source evidence;
  verify live checkout and carrier state.
- [x] Audit [R26 terminal evidence](docs/experiments/v0.4/v04-cvrp-r26-scope-and-net-benefit-autonomous-postrun-20261114.md):
  completed October 29 14:30:25 Beijing, 12 screening stages, nine evaluated
  candidates, 324 valid pairs, 162 successful calls, no held-out/promotion.
  All aggregate stage medians are zero; preserve one additional Code abandonment.
- [x] Preserve positive research findings: nonempty real cache reuse and real
  changed-path gain/retention witnesses now exist; these do not prove net gain.
  No observed source-delivery/provider/best-return defect explains R26.
- [x] Publish the cross-problem stage review separating execution correctness,
  research capability/efficiency and retained algorithm improvement. Warehouse
  status is inherited from accepted reports, not reaudited historical raw runs.
- [x] Identify source-supported gaps: H cannot acquire new runtime observations;
  C execution mainly yields pass/fail; research materials have weaker continuity
  than source; cumulative formal comparisons do not isolate each patch's cause.
- [x] Define a minimal v0.5 proposal and falsifiable assessment without changing
  production code or scientific gates.
- [x] Replace accumulated status/task chronology with current facts and priorities.
  Historical P0–P23 work remains in Git at `c82b77ef` and dated experiment docs.
- [x] Record the November 15 accepted research direction and finite milestones,
  then the user's explicit v0.4 stage-closeout decision, preserving the unmet
  original scientific success criterion.
- [x] Write the [detailed mechanism](design/v0.5/v0.5-continuous-algorithm-research-design.md):
  question/branch/attempt/campaign roles, isolated subject/analysis observations,
  current-attempt H→C handoff, persistent ordinary materials, source retention,
  limits/failures and prospective architecture changes.
- [x] Write [acceptance and comparison design](design/v0.5/v0.5-research-mechanism-acceptance.md):
  engineering, real research process, mechanism effect and independent algorithm
  benefit; A/B/C contrasts and all parameters to freeze before launch.
- [x] Route active design to v0.5 and mark the June Evidence Uplift roadmap
  superseded; do not restore its old closeout prerequisites or governance plans.
- [x] Commit the stage review/R26 audit/v0.5 design, publish annotated `v0.4`,
  merge `v0.4-dev` into remote-default `master`, and establish `codex/v0.5-dev`.
  The tag marks stage closure with the original CVRP scientific goal still open.

## Next falsifiable framework question

**Does safe public measurement before submission improve the agent's ability to
diagnose an algorithm, reject incorrect explanations and choose useful research
actions under comparable resources?**

The research direction and v0.4 closeout are accepted. Detailed contracts are
now written for review; they are not yet accepted architecture changes or an
instruction to spend provider/solver budget. The next work is:

1. Review/adopt the concrete capability and exposure changes in the v0.5 design,
   then synchronize V3/addendum before implementation. The draft keeps one H/C,
   C's bounded handoff and the exact failed-falsifier rule; it adds no question
   controller, history authority or research-quality gate.
2. Implement the smallest observation slice O: fixed subject execution separated
   from agent analysis, public source/input boundaries, current-attempt materials,
   H→C handoff, actual source/input/script audit copies, charged resources and
   explicit incomplete/error outcomes.
3. Add slice M separately: cross-attempt ordinary materials, actual source copies
   for longer-lived verified parents before cleanup, correction without erasure
   and explicit fresh-campaign import.
   Materials never select an executable head or resume a terminal campaign.
4. Pass boundary checks and obtain real autonomous investigation/correction/reuse
   traces. These prove capability existence, not mechanism superiority.
5. Use public pilots and stated budgets to freeze the full preregistration:
   task population, repeats, effect/precision requirements, resource limits,
   candidate nomination, held-out use and stopping rules.
6. Compare A/B/C (existing capability / observation / observation + continuity),
   separately estimating B−A and C−B. Complete the declared matrix and independent
   algorithm assessment; report supported, unsupported and inconclusive results.

Slice E and scientific success are separate. A valid completed negative or
uncertain matrix can support stage closure; it cannot satisfy a positive
mechanism-effect or retained-improvement claim. Missing launch parameter values
are explicitly tracked in the acceptance design, not silently defaulted.

Do not bundle a new model, more branches, larger budgets, multiple agents and
new tools into one comparison and attribute success to a single mechanism.
Research-quality assessment is framework-development evaluation, not a new
production candidate gate. Useful negative research does not by itself satisfy
the retained-improvement objective.

## Scientific work remaining open

- [ ] Establish CVRP complete-solver advantage under its declared Protocol,
  including independent retention against the explicitly named baseline.
  Distinguish unchanged B0, constructor-repaired B0-fixed and local C3 contrasts.
- [ ] Assess framework research effectiveness with repeated campaigns and
  resource/uncertainty reporting. One promotion, better self-tests or a long
  transcript does not prove a general mechanism's superiority.

R24–R26 compare against complete R22 C3. Known screening cases are adaptive;
expanded stages rerun initial cells; ordinary evaluation is champion-first.
Do not pool repeats, remove losses, extend after seeing outcomes or turn private
later-stage evidence into public input. All prior terminals stay terminal.
No fresh autonomous run or fixed confirmation is prepared by this task.

## Boundaries for subsequent work

- Core remains problem-neutral. Algorithms, objective/feasibility semantics,
  public development inputs, surfaces and telemetry stay problem-owned.
  Do not extend generic `OperatorConfig`/operator-pool schema debt.
- LLM observations, plans, notes, H/C remain tainted; they cannot write Protocol
  results, Safe Features, branch/champion state or promotion decisions.
- Preserve Contract, Verification, paired Protocol, held-out isolation,
  feasibility/objective checks and deterministic Decision. Novelty, preferred
  mechanisms, prose quality and telemetry completeness are not extra gates.
- Preserve complete verified source continuation and exact candidate reuse.
  Parent/ablation comparisons require actual saved complete source copies;
  no executable reconstruction from historical patches or automatic sibling merge.
- Public observations need safety preflight and isolation. Negative measurement
  does not affect Decision and cannot clear an exact-patch failed-falsifier veto.
  Exported H/C cannot be repaired, replayed or silently rebound.
- Ordinary completed materials can carry research across fresh attempts;
  they do not resume old mutable branch/provider/stage state. Complete safe
  evidence stays retrievable, without silent truncation, top-k or summary replacement.
- Explicit operational limits and charged typed transient redispatch remain
  separate from scientific quality. Usage-quota exhaustion remains terminal.
- No Trust/Hash authority, identity, leases, signing, registration, receipts,
  duplicate closure, distribution, deployment, packaging, build or service work.

## Verification and handoff

November 14 entry: clean `c82b77ef`, equal to local `origin/v0.4-dev`.
November 15 publication: `eb339d32` commits the preceding documentation plus
README/handoff updates and is the annotated `v0.4` target. `6befa390` merges it
into `master`; its tree exactly equals the tag tree. Both branches and the tag
were pushed atomically to origin. `codex/v0.5-dev` starts from this merge; its
initial changes only update the active development handoff. No history was rewritten.
November 14 artifact/source calculations, November 15 source/design reviews and
document-link/diff checks support the review and design (405 local links checked
before tagging). No new runtime suite,
provider call, solver run or scientific experiment is claimed. Git publication
is a subsequent handoff action, separate from the earlier read-only review.
R26 audit limits include no fresh bootstrap rerun or full public/private context
projection audit; consult its postrun before extending any claim.

Last recorded shared-runtime full suite: P16 at `6380a59e`, 2678 passed /
1 skipped. R26 prelaunch: 142 focused regressions plus optional-example checks.
For later tests use `env PYTHONPATH=scion:. /home/clawd/miniconda3/envs/claw/bin/python`
from the repository root. Shared-boundary changes need suitable focused/full
regression and a prospective independent problem control; ordinary CVRP-only
research does not make Warehouse a permanent prerequisite.

Evidence: [current state](docs/status/current-state.md),
[stage review](docs/planning/v0.4/v04-stage-review-and-v05-research-mechanism-proposal-20261114.md),
[v0.5 design and acceptance](design/v0.5/README.md),
[R26 audit](docs/experiments/v0.4/v04-cvrp-r26-scope-and-net-benefit-autonomous-postrun-20261114.md),
[experiment index](docs/experiments/v0.4/README.md).
