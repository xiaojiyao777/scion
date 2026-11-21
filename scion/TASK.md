# Scion v0.5 Continuous Algorithm Research Design

*Working branch: `codex/v0.5-dev` · Current as of: 2026-11-21*

Follow [`../AGENTS.md`](../AGENTS.md) and
[`current-state.md`](docs/status/current-state.md) before acting.
[Architecture V3](design/scion-architecture-v3.md) is the sole architecture
source; the [direct-runtime addendum](design/scion-architecture-v3-v0.4-direct-runtime-addendum.md)
describes current implementation. The
[stage review](docs/planning/v0.4/v04-stage-review-and-v05-research-mechanism-proposal-20261114.md)
records the accepted v0.4 stage closeout and its evidence. The
[v0.5 design](design/v0.5/README.md) specifies the mechanism and acceptance
contracts; implementation progress is below, and it is not a second authority.

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
earlier publication request explicitly authorized committing the documentation, tagging
`v0.4`, integrating into the default branch and pushing, then entering v0.5.
The closeout commit `eb339d32`, annotated tag `v0.4` and `master` merge `6befa390`
are now published to origin. The remote default is `master` (there is no `main`
or `mian`). Active development has moved to `codex/v0.5-dev`, created from that
merge. v0.5 is formally the active design/development stage; its specific new
interfaces are being implemented module by module. The preceding November 15 request
explicitly authorizes P5b: freeze actual source/model/formal data/run configuration,
check the declared budgets/stops, then launch the fixed eight-slot real-provider
matrix and retain all failures, no-candidate and no-benefit outcomes. This supersedes
the preceding engineering-only launch restriction for this P5b matrix; it does not
authorize R27, extra repeats or E3/E4 confirmation.
The subsequent “继续推进吧” led to [P5c](design/v0.5/v0.5-p5c-question-session-and-materials.md).
A/B implemented test-material readback and actual test-source retention with their
failed regression records preserved. The preceding November 21 request explicitly
authorized P5c C: first specify continuing-question context, stop semantics,
interfaces/permissions/failure routes and adopt the necessary V3 lifecycle extension;
then implement and validate Q11–Q15 without changing veto, ready or scientific
boundaries. That extension was written into V3 before implementation. A later
request froze P5d, followed by explicit authorization to run the eight slots
under the registered stop rules. The terminal record appears below.

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
No further R27 is required for closure. v0.5 is in staged implementation, without
empirical research-effect acceptance. The annotated `v0.4` tag records the mechanism-stage
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

The latest request requires design-first progression, module-by-module
implementation/validation, and an explicit check against the original V3 blueprint.
The [V3 alignment and module plan](design/v0.5/v0.5-v3-alignment-and-module-plan.md)
finds the research goal and decision boundaries aligned, but identified gaps in
execution/exposure contracts, failure routing and evaluation specifications.
P0/P1 now detail the first two; later empirical specifications remain open. The
original D/O/M/E outline has been expanded into concrete module contracts.

Active module progress (definitions and dependencies are in that design; this is
the sole execution checklist):

- [x] Review V3/addendum and v0.5 design completeness; map boundary changes and
  strengthen acceptance, including the actual bundled B−A estimand.
- [x] P0 design: specify concrete schemas, permissions, H→C export timing,
  resource/error routing, C01–C12 cases and exact proposed V3 extension text in
  the [interface contract](design/v0.5/v0.5-p0-interface-and-boundary-contract.md).
- [x] P1 design: specify optional provider and isolated runner/checker protocols,
  CVRP/Warehouse input/argument schemas, actual-source/config binding and
  P1-01–14 cases in the [problem execution contract](design/v0.5/v0.5-p1-public-problem-execution.md).
- [x] P0 boundary adoption: synchronize the explicitly requested extension in V3
  and clarify the v0.4-only scope of the addendum. No scientific gate changes.
- [x] P1a: implement pure provider/descriptor contracts, optional adapter factories,
  bounded strict JSON and problem-owned CVRP/Warehouse validators. The resolver is
  not connected to campaign execution at that stage; real closure and observe-envelope
  checks were deferred to P1b/P2/P3 below. Stage focused checks: 93 passed; non-slow regression:
  2805 passed / 1 skipped (collection preceded final descriptor refinements,
  which the focused checks cover).
- [x] P1b: real CVRP/Warehouse runner/checker entrypoints, selected source/config
  binding, independent frozen recomputation and no fallback substitution, tested
  through P2 isolation. H/C dispatch integration is implemented in P3 below.
- [x] P2 backend: concrete isolation design, exact public closure, single-process
  execution, aggregate reservation/actual accounting, captured materials and byte
  paging/search; S01–S12 execution cases and 100 final focused checks pass. Full regression
  result is tracked in current-state. This does not mark the whole O slice complete.
- [x] P3: write the [session/permission contract](design/v0.5/v0.5-p3-session-permissions-and-handoff.md),
  integrate optional H/C observation, actual Protocol file exclusions, safe material
  projections, explicit immutable H handoff after Contract, C draft preflight/config
  binding and typed outer failures. Both problem packages pass scripted-provider
  real outer-chain tests, including H Contract rejection and unchanged falsifier
  veto. O is engineering-integrated behind explicit opt-in; empirical E2–E4 remain open.
  Focused/full verification scope is recorded in current-state.
- [x] P4: [design contract](design/v0.5/v0.5-p4-material-continuity.md) and V3 extension
  written before implementation. Independent O/M switches, H-only closed-session
  corpus, atomic public export/import, complete private source retention and safe
  projections are implemented. Cleanup faults preserve Decision and old bytes.
  Non-slow regression: 2941 passed / 1 skipped; final focused checks: 253 passed,
  including a final imported-script encoding refinement after full-suite collection.
  M engineering acceptance does not satisfy E2 material-use or E3/E4 effect/algorithm acceptance.
- [x] P5a: write the [process-assessment contract](design/v0.5/v0.5-p5-process-assessment.md)
  before implementation; six problem-owned public diagnoses and separate evaluator
  answers, two open-solver slots, explicit resources/stops, two-reviewer rubric,
  complete-run reporting and V3 alignment. Implement public-only export and offline
  citation/coverage review; real isolated checkers verify all 12 reference solutions,
  and both actual solvers execute diagnostic inputs. Focused checks: 74 passed
  (61 P5 cases plus 13 existing research-input cases). No production assessment gate.
- [x] P5b execution/report: freeze the actual source/model/data/configuration in
  the [preregistration](docs/experiments/v0.5/v05-p5b-process-study-preregistration-20261115.md)
  and dispose of all eight authorized slots: seven completed their formal targets;
  warehouse-02 stopped at 48 calls before evaluation. Total 298 calls, 214 valid
  pair rows / no failed pairs, all champions v1. CVRP open failed screening;
  Warehouse open passed validation but failed frozen with unclear evidence.
  The [process/results report](docs/experiments/v0.5/v05-p5b-process-study-postrun-20261115.md)
  retains failures, costs, original byte citations and one non-blinded review per slot.
- [ ] P5b/E2 capability acceptance: this batch does not satisfy E2. No observe
  calls and no cross-attempt material reads occurred. Legacy formal-history use
  supports one bounded revision trajectory; it is not a new O/M witness. Independent
  second reviews are pending. P5c specifies the observed material/session gaps;
  it does not supply a second independent review or new E2 evidence.
- [x] P5c design: specify automatic C test-material readback, exact safe feedback,
  draft versus actual test-source capture, phase/import permissions, persistence
  failures, resource accounting and Q01–Q15. Keep the current falsifier veto;
  separately draft a typed investigation conclusion with explicit V3 differences.
- [x] P5c A: implement request/script/draft/bounded-result readback; Q01–Q07 and
  related focused checks pass (203 tests), as do 128 development/diagnostic/material
  regressions. Veto/ready order is preserved; historical A capture remains request_only.
  Full non-slow result is 3036 passed / 1 skipped / 1 failed: an unchanged timed
  CVRP public-example assertion, passing alone and in the 128-test follow-up.
  Preserve that qualification; full regression was not all green. Details are in
  [current state](docs/status/current-state.md), not an implicit exemption or E2 pass.
- [x] P5c B implementation: retain the actual prepared scratch before probe and
  host-check stages; separate private copies from safe public projections and
  publish through existing P4 continuity. Q08–Q10: 17 cases pass; Q15 both real
  problem outer chains pass. Failed-falsifier veto and ready remain unchanged.
  Full non-slow regression: 3054 passed / 1 skipped (641.30 s). Prior failures
  and fixture corrections remain documented in current-state; E2 stays open.
- [x] P5c C design/adoption: freeze the explicit investigation intent, H-only
  conclusion, zero-formal mode, shared limits, material permissions and terminal
  fault precedence in P5c §5–7 and V3 before implementation.
- [x] P5c C implementation: continuing-question context, bounded conclusion notes,
  typed zero-formal outcome, CLI/API intent and formal ceiling, preserved heads/
  Decisions/pending work, no resume. Q11–Q15 focused checks cover both real problem
  runtimes; default formal mode, veto/ready and scientific boundaries are unchanged.
  Final non-slow regression: 3114 passed / 1 skipped (784.60 s), including all
  52 C cases. Development failures and deliberately interrupted earlier test runs
  remain recorded in current-state alongside the existing A/B failure evidence.
- [x] P5d E2 prospective design and offline freeze. Eight sets of CLI/closure checks,
  six verified diagnostic references and two disposable fresh-import readbacks.
- [x] P5d batch closed under the frozen authentication stop. One real H request reached the proxy. All eight slots have dispositions.
- [x] Two independent AI reviews cover all eight P5d slots. The five ratings on the
  started slot agree, and all 91 cited byte ranges match their originals.
- [ ] E2 empirical research capability remains unestablished. Neither open investigation started.
- [ ] P6: use public pilots to freeze and run the repeated mechanism comparison.
- [ ] P7: independently assess full-solver outcomes and report stage conclusions.

P5 task/rubric design and offline tooling are now concrete. The
[task/config package](experiments/v0.5/p5/README.md) freezes a bounded feasibility
matrix, not an E3 sample size; its actual P5b execution is separately recorded above.
The first authorized P5d invocation used the frozen source, model policy and inputs.
Its first H request received HTTP 401 before any agent action. The batch stopped
with one provider failure and seven unstarted slots, including both 01→03 imports
and both open questions. There is no autonomous O, M, revision or conclusion
trajectory to score positively. A fresh study would need a working credential
for the generation endpoint and a separate prospective batch decision. The next
scientific rung remains E2. [P5d postrun](docs/experiments/v0.5/v05-p5d-e2-postrun-20261121.md)

Scientific CVRP retained superiority remains open, and the P5 external confirmation
allowance is zero.
P3 uses one shared backend per fresh campaign. `--public-research` supplies the
strict opt-in/budget JSON alongside `--code-research-limits`; disabled behavior is
unchanged. M adds H-only material continuity and `--research-materials` fresh import;
M-only permits material actions but disables observe. The authorized P5b matrix is
now terminal; O tests do not count as retained solver improvement.
P0/P1 design examples were
checked against frozen models/oracle (CVRP distances 12/14; Warehouse cost 800),
without a solver/provider run; these reference checks do not validate execution.

**Does safe public measurement before submission improve the agent's ability to
diagnose an algorithm, reject incorrect explanations and choose useful research
actions under comparable resources?**

The research direction, v0.4 closeout and explicit V3 public-research extension
are accepted. P1b/P2/P3/P4/P5a engineering checks use public fixtures and existing outer-chain test inputs;
the subsequent explicit P5b request authorizes this fixed real-provider budget.
The P0–P7 sequence above replaces
the earlier coarse implementation list. O includes observation, current-attempt
materials and H→C handoff; B−A measures that bundle. C−B isolates the additional
cross-attempt material exposure. Neither contrast changes scientific gates,
chooses an executable head through notes or restores a terminal campaign.

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
The explicitly authorized P5b matrix is now terminal; no fixed confirmation
or additional autonomous matrix is authorized by this step.

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

Historical v0.4 shared-runtime full suite: P16 at `6380a59e`, 2678 passed /
1 skipped. R26 prelaunch: 142 focused regressions plus optional-example checks.
Current v0.5 focused/full results are recorded in [current state](docs/status/current-state.md).
For later tests use `env PYTHONPATH=scion:. /home/clawd/miniconda3/envs/claw/bin/python`
from the repository root. Shared-boundary changes need suitable focused/full
regression and a prospective independent problem control; ordinary CVRP-only
research does not make Warehouse a permanent prerequisite.

Evidence: [current state](docs/status/current-state.md),
[stage review](docs/planning/v0.4/v04-stage-review-and-v05-research-mechanism-proposal-20261114.md),
[v0.5 design and acceptance](design/v0.5/README.md),
[R26 audit](docs/experiments/v0.4/v04-cvrp-r26-scope-and-net-benefit-autonomous-postrun-20261114.md),
[experiment index](docs/experiments/v0.4/README.md).
