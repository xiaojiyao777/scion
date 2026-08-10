# Scion v0.4 Current State

*Last updated: 2026-08-09*

Read `TASK.md` first. `design/scion-architecture-v3.md` is the sole architecture
authority. `design/scion-architecture-v3-v0.4-direct-runtime-addendum.md` only
describes the current lightweight implementation and cannot override V3.

## Current objective

The active branch is `v0.4-dev`. The prior
`codex/v04-solver-improvement-research` stage was committed through
`30726a52` and fast-forwarded into `v0.4-dev`; this branch continues from that
accepted research checkpoint.

The active completion target is retained solver improvement on both Warehouse
and CVRP/VRP. Warehouse now has both retained synthetic continuity and retained
production transfer. CVRP must still produce a real algorithmic promotion;
valid negative observations alone do not close `TASK.md`.

Distribution, deployment, installation, packaging, builds, root/systemd and
source-acceptance machinery are out of scope. Object identity, signing,
registration, leases, capability graphs, hash chains and repeated self-proof
closures are also out of scope. No root command is required for the current
work. Historical W3/root artifacts remain historical evidence only and are not
part of this branch's acceptance.

## Active V3 path

```text
complete problem facts + complete current source + prior safe evidence
  -> one Hypothesis provider call
  -> structural Hypothesis Contract
  -> one Code provider call bound to the approved H
  -> structural Patch Contract
  -> isolated Workspace
  -> executable Verification
  -> problem-owned case-level Protocol
  -> Safe Features
  -> deterministic Decision
  -> exact stage reuse, verified provisional head, or promotion
```

Per V3 §11.2, Contract and Verification success followed by completed
screening retains the evaluated code as the branch's provisional head even
when screening fails to promote it. Verification failure alone returns to the
last clean branch source, or champion when the branch has never verified code.
The Scheduler admits at most three active branches by default, using state
priority/FIFO without forced diversity or mechanism classification.

The production import boundary no longer imports the dormant authority,
capability, lease, signing, proposal-attempt-owner, root, systemd, packaging, or
W3 installation stacks.

## Completed simplification

- Removed the dormant Campaign/proposal/lineage authority graph from the active
  path and deleted its production-facing modules and tests.
- Replaced the attempt-transition closure with one small append-only H/C call
  journal. Normal evaluated work performs one H call and one approved-H-bound C
  call; provider retry remains zero.
- Replaced rejection owner/intent/completion layers with a small rejection
  finalizer that records the typed rejection and returns to the clean source.
- Replaced VerifiedCandidate/DecisionCompletion owner, intent, digest, CAS, and
  recovery layers with one plain branch-local candidate-evaluation marker and a
  synchronous Decision finalizer. Verification leaves code in isolated staging;
  Protocol Decision alone accepts it, retains it provisionally, or restores the
  clean parent.
- Deleted the now-unused promotion journal/crash-recovery façade and the
  Decision/research-rejection receipt/archive APIs and their dedicated tests.
  The active path keeps staging create/apply/accept/reject, scientific
  source equality, champion snapshots, ordinary branch lineage and
  problem-owned Protocol evidence; it does not build a second artifact,
  recovery or replay authority around an in-process candidate.
- Wired typed candidate disposition into production. Completed screening keeps
  the verified candidate as an explicit provisional branch head, including on
  Protocol `fail`; Verification rejection restores the clean code parent, and
  screening/validation expansion reuses the exact candidate without another
  provider call.
- Removed forced surface/action/target controls from CLI, composition, context,
  prompts, and proposal execution. H sees all problem-declared safe surfaces
  and their complete current source.
- Reduced Contract to V3 structure and capability boundaries. It retains schema,
  concrete editable/frozen paths, approved-H binding, syntax, public interface,
  import resolution, dangerous API checks, `context.baseline` prohibition, and
  injected-RNG discipline. It no longer grades novelty, telemetry naming,
  internal scheduler shape, helper reachability, case names, or host-preferred
  mechanisms.
- Split H target context into concrete `existing_target_files` and declared
  `create_path_patterns`. Literal globs cannot be submitted as targets;
  modify/remove require a real existing file and create requires a real new
  path. Warehouse no longer advertises unsupported remove behavior.
- Removed model-facing source digest/provenance echo requirements. The host
  applies an edit only to the complete source value the provider actually saw;
  ordinary source/content inequality still fails.
- Replaced telemetry/mechanism keyword redaction with problem-owned structured
  visibility. Safe attribution and activation facts remain visible while raw
  validation/frozen/holdout and private pair/calibration structures remain
  excluded.
- Added minimal pre-Protocol rejection history for fresh H calls: phase, typed
  reason/check codes, surface, action, and targets only. Provider prose, patch
  source, check details, and raw evaluation data are excluded.
- Collapsed CLI/Campaign/Verification dependency checks into one typed research
  environment preflight before H. It materializes runtime dependencies, declared
  surface source, problem guidance, and Verification availability without hashes
  or exact-class parity checks.
- Simplified screening/validation/frozen gates to problem-declared case-level
  win rate, practical delta, and confidence rules. Pair and runtime signals are
  diagnostic only unless a problem explicitly declares runtime as an objective
  or hard constraint.
- Added transparent Warehouse pool/iteration/stagnation/operator-wiring mechanics
  and safe headroom/noise facts to H context, and added the accepted concise
  CVRP cross-campaign prior. Neither enters DecisionFeatures or selects a
  mechanism.
- Removed the dormant problem-specific algorithm-shape Contract dispatchers and
  preview/static-quality stack. The active Contract remains structural; solver
  behavior remains Verification/Protocol-owned.
- Removed the active formal-candidate artifact recorder and its composition
  wiring. Active lineage now keeps ordinary campaign/branch/H references, one
  exact branch-source equality value, declared stage inputs, public raw-metrics
  reference, verification checks and Protocol/Decision facts. It does not echo
  problem/split/seed hashes, patch digests, replay-identity payloads or
  complete/degraded identity states.
- Historical fixed-candidate evaluation has a read-only local safe-path
  compatibility reader for the old full-file replacement artifacts. It does
  not write current campaign evidence, call H/C, decide promotion or confer
  authority.
- Reduced provider context to one frozen validated value plus ordinary
  context/prompt equality. No prompt/context identity or receipt layer sits on
  H/C; trace and call-journal persistence are best-effort diagnostics, while
  the approved-H-to-C binding remains.
- Removed active promotion dossier generation, registry hashing, automatic
  summary closure and formal-readiness projection. Optional reporting cannot
  turn a persisted scientific promotion into a recovery failure. Validation
  and frozen reuse keep the substantive present/equal source and clean-state
  checks without generating another proof object over those same facts.
- Removed `attempt_disposition` as a CampaignLoop scheduling authority. A
  typed pre-Protocol research rejection now schedules forward directly; the
  old marker is optional diagnostics only. A patchless stale branch retires as
  non-research lifecycle work, while missing outcomes, infrastructure,
  interruption and resource failures still stop rather than being retried.
- Corrected the proposal-content failure route exposed by Warehouse R6. A
  terminal provider response that is malformed/schema-invalid, or a typed edit
  that cannot apply to the complete provider-visible source, remains rejected
  and never reaches Protocol, but it no longer stops the campaign. That H/C is
  marked `RESEARCH_REJECTED`, its in-process binding is released, and the
  scheduler starts a fresh H on the clean base. The failed H/C is never
  retried; local context/binding, missing outcome, provider-without-terminal-
  response, infrastructure, resource and interruption outcomes still stop.
- Removed the runtime path that derived expanded-evaluation case ids from the
  current branch's wins and losses. Initial and expanded populations now come
  only from the problem Protocol's pre-experiment configuration and
  deterministic selection; fixed problem-owned priorities such as the CVRP
  CMT cases remain valid when declared there before results.
- Routed the existing neutral CVRP cross-campaign research prior through the
  actual provider-visible H payload. The H prompt now asks for one
  evidence-grounded mechanism-level change or refinement instead of forcing a
  materially different mechanism, and CVRP guidance explains that the default
  VNS registry is shared by initial and embedded phases. These changes add no
  host mechanism choice, assay gate, owner, manifest, identity or Decision
  input.

The latest focused integration regression for the Protocol-case and CVRP-H
changes passed `112` tests; the broader core/protocol regression for the case
subtraction passed `440` tests. The combined hot-path regression set passed 180
tests. After all three
subtractions were integrated and the tree was frozen, the complete suite passed
`1949 passed, 1 skipped` in 628.19 seconds. This validates the pre-experiment
runtime checkpoint; it does not satisfy the Warehouse or CVRP solver-evidence
acceptance criteria.

## Historical lightweight research controls

Both fresh controls used `gpt-5.6-terra` through the local Codex proxy and the
same non-root direct-v3 composition.  All H/C traces report the Terra model and
the OpenAI-compatible transport.  The proxy does not expose its resolved
upstream alias, so the record makes only the transport/model claim it directly
observed. These controls predate the current provisional-head and active
artifact simplifications; their recorded outcomes remain historical facts.

### Warehouse

Campaign:
`/home/clawd/research/scion-experiments/v04-warehouse-v3-light-generative-3r-gpt56terra-20260808T034724Z-claw/campaign`

- wrapper exit 0; validity `valid`; completeness `complete`; stop reason
  `requested_rounds_completed`;
- 3 H, 3 C, 3 formal screening observations;
- 44/44 valid pairs and no candidate, champion, or framework failures;
- R1 split-aware `DestroyRebuild`: case 1W/2L/3T, median cost -1300,
  screening fail;
- R2 new `ConsolidateSubcategory`: case 0W/3L/7T, median cost +25,
  screening fail;
- R3 guarded best-pair `MergeVehicles`: case 3W/0L/3T, median cost +950,
  screening expand, not validation or promotion.

Every `subcategory_splits` delta was zero, so all observed effects were on the
secondary cost objective.  R2 visibly narrowed the broad R1 idea after seeing
its negative evidence; R3 pivoted to vehicle elimination.  Operator files were
present in the pool and eligible, but there are no direct per-operator
invocation counters, so attribution remains candidate/pool-level.

The pre-registered exact R3 eval-only completion is now final. Expanded
screening passed on 14 cases (8W/0L/6T, median `+950`, CI `[400,4900]`), but
validation failed: the exact candidate timed out on 11/15 pairs while champion
failed on 0/15, with candidate median runtime ratio `1.4750`. Frozen was skipped
by the declared conditional policy. This is a `SCIENTIFIC_NEGATIVE` at
validation, not a framework/queue failure, and closes the old truncated-candidate
question without a promotion.

The first authenticated long-horizon synthetic continuity campaign is also
final:
`/home/clawd/research/scion-experiments/v04-warehouse-v3-continuity-synth-36r-r3-gpt56terra-20260808T163049Z-claw/campaign`.
It generated three H/C pairs and completed four screening, one validation and
one frozen stage with 106/106 valid pairs and no provider, candidate, champion
or pair failure. The third candidate changed `operators/move_order.py`, won
18/18 validation pairs and 12/12 frozen pairs, reported median primary
improvement `+11` in both stages, and became champion v2. This restores one
real agent-generated Warehouse promotion.

R3 nevertheless stopped at 6/36 after promotion. Scheduler correctly selected
an older stale branch, but the old runtime treated its absent patch as a
markerless research rejection and stopped on
`research_rejection_disposition_missing`. Commit `88c1bc2b` now retires that
branch as non-research housekeeping and makes typed research rejection
sufficient to continue without a second disposition authority. It does not
change Protocol, Decision, Scheduler priority, cases, seeds, thresholds or
time limits. Therefore R3 proves one promotion, not same-campaign continuity,
v3, production transfer or independent replay.

The first post-fix launch, R4, has no scientific result. An operator-side shell
expression assigned jq's `<stdin>` input filename instead of the local proxy
client key, so the first H request received 401 and the run stopped
`invalid_infra_only` with zero evaluated stages and zero experiments. The proxy
itself remained authenticated with one active account. R4 is sealed; R5 uses a
fresh root, the same scientific inputs and executable code, and one exact key
extraction followed by a silent authenticated `/v1/models` check.

R5 passed those credential/model checks and completed H, but its first C call
ended upstream without a terminal event after 2,022 partial stream events. The
proxy deliberately failed fast with HTTP 504; it remained healthy,
authenticated and active after the stop. No valid C/source can be reconstructed
from a terminal-less stream, and R5 has zero evaluated stages and zero
experiments. It is sealed with no scientific conclusion. R6 keeps the same
science/code inputs in a fresh matched root and starts new H/C calls rather
than replaying R5 C; one intermittent upstream close does not justify changing
Scion or proxy configuration.

R6 then ran once in its declared fresh root:
`/home/clawd/research/scion-experiments/v04-warehouse-v3-continuity-synth-36r-r6-gpt56terra-20260808T173413Z-claw/campaign`.
It completed 17/36 formal stages: 15 screening, one validation and one frozen.
Its first candidate passed the complete funnel and became champion v2. After
promotion, three v2-based branches completed fourteen additional formal
screenings, all negative; there was no second promotion. All 16 H and 16 C
provider calls completed. The final C proposed an `exact_replace` selector
absent from the current source, and the old runtime misclassified that
candidate-local rejection as invocation-terminal `NOT_EVALUATED`. R6 is valid
partial science showing one improvement plus post-promotion research
continuity, not a completed 36-stage run or evidence of repeated optimization.

R7 used the corrected revision in a fresh matched root and completed four
formal stages with 62/62 valid pairs. Its first candidate expanded screening
and then failed; its second passed screening but regressed in validation
(median primary delta `-15`, confidence interval `[-24, -0.5]`) and was
abandoned. The third H completed, but its C ended upstream without a terminal
response after about 29.8 seconds. Scion correctly recorded `BLOCKED_INFRA`
and stopped at 4/36. Proxy authentication and the single active account
remained healthy after exit. R7 is useful partial negative science, not a
promotion or continuity result; the failed C is sealed and will not be
retried.

R8 then completed the matched continuity question in its declared fresh root:
`/home/clawd/research/scion-experiments/v04-warehouse-v3-continuity-synth-36r-r8-gpt56terra-20260808T201033Z-claw/campaign`.
The wrapper exited 0 with `valid / complete` and
`requested_rounds_completed`. It completed all 36 formal stages (29 screening,
five validation and two frozen), with 534/534 valid pairs and zero candidate or
champion failed pairs. The run made 29 H and 28 C calls. One Verification
undefined-name rejection and one schema-invalid H were typed
`RESEARCH_REJECTED`; the scheduler moved to fresh H calls without retrying or
stopping the campaign.

Two exact candidates completed the whole promotion funnel. Candidate
`89f3edbb...` created a bounded fragmented-subcategory repack operator and
promoted v1 to v2: validation was 18/18 pair wins with median primary delta
`+21`, CI `[7.5, 43]`; frozen was 12/12 pair wins with median `+22`, CI
`[4, 38]`. Candidate `3f204b01...` then improved the v2-based rebuild path and
promoted v2 to v3: validation was 18/18 pair wins with median `+4.5`, CI
`[1, 34.5]`; frozen was 12/12 pair wins with median `+15`, CI `[1, 42]`.
After reaching v3, R8 completed sixteen more formal screenings.

R8 therefore proves same-campaign continuous Warehouse research through
`v1 -> v2 -> v3`. Its separately preregistered no-LLM replay then completed all
three comparisons on 12 R8-unseen frozen cases and seeds 11/73/509. Every
comparison had 36/36 valid pairs, both candidate and champion canaries passed,
and there were zero candidate/champion failures and zero cached champion
runtimes.

- v2-v1: case 11/1/0, pair 32/4/0, median `subcategory_splits` improvement `+8`, CI
  `[4, 23.5]`;
- v3-v2: case 12/0/0, pair 35/1/0, median `+39`, CI `[15, 48]`;
- v3-v1: case 12/0/0, pair 36/0/0, median `+48.5`, CI `[40, 65]`.

These primary deltas do not establish `total_cost` improvement. Runtime remains
diagnostic only.

All three returned `FROZEN_PASS_HIERARCHICAL` and meet the preregistered
`RETAINED_IMPROVEMENT` rule. Warehouse synthetic continuity is therefore
`CONTINUOUS_OPTIMIZATION_CONFIRMED`. The campaign audit, fixed design and
held-out result are recorded respectively in
`docs/experiments/v0.4/v0.4-warehouse-v3-continuity-synthetic-36stage-r8-postrun-20260808.md`,
`docs/experiments/v0.4/v0.4-warehouse-v3-continuity-r8-heldout-replay-preregistration-20260808.md`
and
`docs/experiments/v0.4/v0.4-warehouse-v3-continuity-r8-heldout-replay-postrun-20260809.md`.
This does not establish production-style Warehouse transfer or CVRP
improvement.

### Warehouse production transfer

The preregistered prod-1.1 12-stage shakedown completed in its fresh root:
`/home/clawd/research/scion-experiments/v04-warehouse-v3-production-transfer-prod11-12stage-r1-gpt56terra-20260809T021245Z-claw/campaign`.
The wrapper exited 0 with `valid / complete`, all 12 requested formal stages
completed, and 211/211 formal pairs valid. There were 11 screening stages, one
validation stage, zero frozen stages, zero solver/infra failures, and no
promotion.

The final exact candidate passed screening at 4/0/2 cases and 9/0/3 pairs. Its
validation completed all five declared cases and all 15 pairs: case 5/0/0,
pair 14/1/0, primary `subcategory_splits` deltas `[1,0,0,0,0]`, primary CI
`[0,1]`, and median `total_cost` improvement `+13200`. Protocol returned
`VALIDATION_EXPAND_HIERARCHICAL_UNCERTAIN`; the requested horizon then ended
with champion v1. The exact classification is
`VALID_FUNNEL_FOR_24STAGE_PREREGISTRATION`, not promotion, retained transfer,
validation failure or framework failure. The root is sealed and must not be
resumed. The validation candidate was also slower on all 15 pairs, with median
runtime ratio `1.473`; runtime remained diagnostic under the declared policy.

The run exposed prospective research-design defects without changing its
recorded result:

- prod-1.1 had `validation.n_cases=5` and `expand_to=5`, so its queued
  expansion would repeat identical cases and seeds rather than add evidence;
- the execution path used the statistics default of 1000 bootstrap samples
  despite the Protocol declaration of 10000;
- first-nonexact hierarchical statistics were non-monotone: adding a sparse
  positive higher-priority improvement could hide the already predeclared
  `total_cost` effect metric and make a better candidate harder to pass;
- initial and expanded evenly-spaced populations were selected independently;
  the same defect drops initial CVRP cases during a nominal expansion;
- real H history grew without a V3 semantic projection, while Warehouse
  surface-level hypothesis guidance did not reach H and C carried source
  owner/hash/provenance self-proof metadata.

The no-new-evidence expansion, declared-bootstrap execution and shared
measurement/population/context defects are corrected prospectively. The
measurement path now uses the problem's declared effect metric while retaining
lexicographic direction evidence and every objective row; only an explicitly
declared protected objective can veto a regression. Expanded populations
strictly contain their initial cases. Durable raw history remains complete,
while H receives the fixed V3 research view and C receives plain approved path
and source content plus phase-correct guidance. Fresh Warehouse H additionally
receives one neutral aggregate prod-1.1 scientific prior; it does not import a
candidate or select a surface, action, target or mechanism. These corrections
do not reinterpret R1.
The prod-1.2 population design fixes five new candidate-independent validation
instances and keeps the old five as the initial set, all ten as the expanded
set, with unchanged seeds and thresholds. The fixed cases have passed
constructive phase-1 and phase-2 feasibility checks; no candidate, champion,
objective difference or runtime was used to choose them. See the
[population design](../experiments/v0.4/v0.4-warehouse-production-prod12-validation-population-design-20260809.md)
and [R1 postrun](../experiments/v0.4/v0.4-warehouse-v3-production-transfer-prod11-12stage-r1-postrun-20260809.md).

The separately preregistered prod-1.2 24-stage campaign then completed in
`/home/clawd/research/scion-experiments/v04-warehouse-v3-production-transfer-prod12-24stage-r1-gpt56terra-20260809T044055Z-claw/campaign`.
It is `valid / complete`, exited 0, and completed all 24 requested formal
stages: 22 screening, one validation and one frozen. There were 23 H/C pairs,
24 evaluated outcomes, one candidate-local research rejection, 297/299 valid
formal pairs, two failures belonging to one abandoned candidate, and no
champion or infrastructure failure.

The first H produced a subcategory-aware best-fit DestroyRebuild refinement.
Its exact source passed screening at 4/0/2 cases and 9/1/2 pairs, validation at
5/0/0 and 15/0/0, and frozen at 4/0/0 and 12/0/0. The problem-owned
`total_cost` effect progressed from `+500 [-50,3300]` to
`+11500 [4200,18900]` and `+17000 [6500,29600]`, producing champion v2.
The v2/v1 snapshots differ only in `operators/destroy_rebuild.py`.

The fixed independent replay completed in
`/home/clawd/research/scion-experiments/v04-warehouse-prod12-independent-heldout-v1-20260809T072000Z-claw/run`.
Both sides passed canaries; all 12 executions on four campaign-unseen cases
were fresh and valid; the result was 4/0/0 cases, 12/0/0 pairs and
`total_cost +15150 [8400,22000]`, with `FROZEN_PASS`. Classification:
`RETAINED_PRODUCTION_IMPROVEMENT`. Warehouse production transfer and the
complete Warehouse acceptance block are therefore satisfied. See the campaign
[postrun](../experiments/v0.4/v0.4-warehouse-v3-production-transfer-prod12-24stage-r1-postrun-20260809.md)
and independent replay
[postrun](../experiments/v0.4/v0.4-warehouse-prod12-independent-heldout-v1-postrun-20260809.md).

The 21 screenings after v2 did not establish a second production promotion.
They did expose three experiment-organization limits: creation-time EXPLORE
selection starved two schedulable sibling branches; 14 later candidates were
cumulative and not incrementally isolated; and two independent 2/0/4-case,
6/0/6-pair Merge signals were denied the declared expanded population. Commit
`8909f635` prospectively rotates EXPLORE siblings by persisted
least-recently-served time, grants one expansion (not a pass) to a practical
sparse no-loss initial signal, and exposes one typed Python Verification root
cause to the next H. It adds no rollback, novelty or algorithm-quality gate
and does not reinterpret prod-1.2.

### CVRP

Campaign:
`/home/clawd/research/scion-experiments/v04-cvrp-v3-light-generative-4r-gpt56terra-20260808T050545Z-claw/campaign`

- wrapper exit 0; validity `valid`; completeness `complete`; stop reason
  `requested_rounds_completed`;
- 4 H, 4 C, 4 formal screening observations;
- 128/128 valid pairs and no candidate, champion, or framework failures;
- R1 cross-exchange composite: case 2W/5L/1T, median distance -12.25,
  screening fail;
- R2 adaptive credit: 8 case ties, 31 pair ties/1 loss, median 0,
  screening fail;
- R3 bounded ejection-chain repair: case 0W/4L/4T, median -11.5,
  screening fail;
- R4 symmetric 2-opt delta: 8 case ties, 31 pair ties/1 loss, median 0,
  screening fail.

The agent used structured solver evidence to pivot from neighborhood expansion
to credit allocation, repair, and then a cheap evaluator.  R1 also exposed a
provider-authoring defect: a broad full-file rewrite removed an unrelated
terminal return, so its negative result cannot isolate cross-exchange.  R2 was
under-exposed in the operator schedule.  R3 exposed the related route-limit
condition in 31/32 runs but completed only 74 ALNS iterations versus 1631 for
champion, roughly 22x lower throughput.  There is no direct ejection-chain
invocation counter, so the chain itself is not isolated.  Two independent R4
reviews found only about 0.4%-0.9% weak throughput association, no direct
fast-path mediator, and no objective benefit.

All four rejected CVRP candidates returned to champion v1 before the next H;
rejected source did not enter later executable ancestry.  Both problem
champions remained version 1.  No improvement, validation, frozen-holdout, or
promotion claim is made.

Independent scientific review marks Warehouse M5 and CVRP M6 **YES, with
caveats**.  The milestones are satisfied by substantive evidence-driven pivots
and useful negative or constraint findings, not benchmark improvement.
Warehouse R3 omitted an `amount_limits` / `declaration_amount` check in its
local merge guard; all 12 formal pairs still passed the problem oracle, so the
recorded screen remains valid but is not a universal feasibility or validation
claim.  Per-round mechanism attribution remains candidate/pool-level or
association-only where direct counters are absent, and neither campaign
authorizes validation, frozen holdout, promotion, or an improvement claim.

The detailed evidence and claim boundary are in
`docs/experiments/v0.4/v0.4-v3-lightweight-research-effectiveness-gpt56terra-20260808.md`.

The matched CVRP open-research R1 was launched once from executable commit
`51f9bbd7` in:
`/home/clawd/research/scion-experiments/v04-cvrp-v3-open-research-8stage-r1-gpt56terra-20260809T081630Z-claw/campaign`.
It is terminal and sealed. The wrapper recorded
`valid_but_incomplete / incomplete_infra_stop` at 5/8 requested formal stages
after a hypothesis stream closed upstream without a terminal event. The local
proxy remained authenticated with one active account. The pre-registered root
classification is `RUN_INVALID_INFRA`; its five completed screening stages are
retained separately as `VALID_PARTIAL_SCIENCE_5_OF_8`. It must not be resumed
or retried.

R1 completed 176/176 formal pairs with zero candidate/champion failed pair,
zero feasibility failure and zero protected fleet regression. Three branches
tested exact 2-opt* evaluation, initial-VNS allocation and ejection repair. The
scheduler performed least-recently-served exploration; one queued expansion
reused the exact branch-C source with no H/C; later H calls used current-branch
source plus sibling evidence. Thus R1 demonstrates real branch iteration and
algorithm research behavior, but no validation, frozen stage or promotion.

The strongest observation was bounded depth-one ejection repair. Initial
screening produced 4W/0L/4T gate cases and expansion reproduced direction at
6W/1L/5T, median distance improvement `+3.75`, CI `[0,11]`. The operator was
selected 557 times, accepted 311 times and generated 27 best updates; ALNS
iterations increased by 202 and route-limit events fell by 17. It also
recorded 186 discarded repair errors, about 9% of ALNS iterations. This is a
mixed sparse-positive signal that merits a fresh prospective confirmation,
not a promotion. A cumulative fast-2-opt* plus depth-two fallback was negative
and does not isolate depth two.

R1 also establishes that the matched measurement is not adequate for the next
rung. The case estimator maps `2W/0L/2T` seeds to a case tie because wins must
strictly exceed ties; calibration MDE@80% is `9.9` while the observed depth-one
median is `3.75` and the practical threshold is `2`. Any estimator, seed or
population change must therefore be fixed in a new preregistration and cannot
reinterpret R1. Under a prospective paired-median-sign estimator, the expanded
result would be 7W/2L/3T, win rate `0.583`, and would still miss the R1 `0.60`
threshold. Screening advancement remains distinct from validation/frozen
promotion.

Two prospective research-path defects are also concrete. One complete branch-C
code response was rejected before Contract because its selector differed from
source only by the number of blank lines between functions. Terminal status
also projected one of two typed research rejections out of run validity. The
corrected R2 prerequisite is limited to deterministic unique blank-line-run
selector repair, consistent rejection accounting and one concise neutral
ejection evidence update. None is a deployment, Trust/Hash, mechanism or
algorithm-quality gate.

The next rung does not claim calibrated power. Its prospective estimator is a
paired per-case median with a zero equivalence band; an 8-case x 4-seed
mechanism screen may only request the exact 12-case x 8-seed quality screen.
The retained MDE `9.9` calibration and later 8-seed MDE `9.6` diagnostic both
used incompatible pair-level estimators or populations, so R2 measurement
readiness is explicitly uncalibrated. They establish only that effects near
the practical delta `2` remain difficult to exclude. Validation stays 12x4,
frozen stays 12x3, and promotion thresholds remain unchanged.

The integrated pre-R2 implementation passes the complete suite at
`2047 passed, 1 skipped` in 624.56 seconds. A campaign-level wiring regression
also proves that the initial screen queues exact expansion on the same
candidate with no new provider call or workspace, uses all 12 cases and eight
ordered seeds, and only then enters 12x4 validation. Critical Ruff syntax/error
rules and `git diff --check` pass; the repository's broad historical Ruff
baseline remains out of scope.

R2 also treats experiment design as an input rather than an invisible host
assumption. Its preregistration must inventory the provider-visible H/C
sections, complete solver/mechanics material and available edit/research tools,
then preserve input size, tool/edit outcomes and typed rejection causes for
postrun analysis. Those observations cannot enter Decision or become novelty,
mechanism, activation, style or algorithm-quality gates. A no-promotion result
must separately report agent research behavior, measurement reach and
pre-Protocol framework friction; any causal context/measurement comparison is
a later fresh matched ablation, never an in-place change to R2.

A final independent V3 exposure audit found that the prospective H prior still
contained current validation case `tai150a`, seed-level deltas and
validation/frozen summaries. It also found duplicated C rules, contradictory
route-count wording and an instruction to use an incompatible MDE. Executable
commit `41956f36` removes those validation/frozen details, retains only neutral
screening-level mechanism evidence, exposes each current source file once,
corrects excess routes to the separate `fleet_violation` objective and reduces
C to one object/API fact packet plus target-specific guidance. This is a net
context reduction, not a new gate. The complete suite and 46 actual H/C render
regressions pass after the change.

Corrected R2 is frozen in
[`v0.4-cvrp-v3-quality-screen-12stage-r2-preregistration-20260809.md`](../experiments/v0.4/v0.4-cvrp-v3-quality-screen-12stage-r2-preregistration-20260809.md)
at executable commit `41956f36` and was launched once in the declared fresh
root. It is now terminal and sealed. The wrapper stopped
`incomplete_infra_stop / valid_but_incomplete` after the final C stream ended
upstream without a terminal event. The pre-registered classification is
`RUN_INVALID_INFRA`; the completed record is retained separately as
`VALID_PARTIAL_SCIENCE_10_OF_12`. The root must not be resumed and the failed C
must not be retried.

R2 completed 10 formal screening stages and 448/448 valid pairs with zero
candidate/champion failure, feasibility failure or protected fleet regression.
It exercised three branches, two exact 12x8 quality expansions, two
candidate-local schema rejections that correctly scheduled forward, and no
Contract/Verification rejection. Champion remains original B0/v1; no candidate
reached validation, frozen holdout or promotion.

The strongest result is elapsed-budget simulated-annealing cooling. Its exact
quality screen returned 6W/1L/5T cases, 49/20/27 pairs and median distance
`+2.75 [0,11]`. This is broadly non-inferior and mechanism-consistent, but it is
not a hidden pass: the fixed rule used wins/all cases and 6/12 is below 0.60.
SWAP* reached 6W/5L/1T and `+1 [-7.5,9.75]`; a transactional route-cap ejection
was a valid mixed negative. One time-aware-credit C added only unused constants,
so its result is proposal-fidelity evidence rather than an algorithm negative.

The full postrun and claim boundary are in
[`v0.4-cvrp-v3-quality-screen-12stage-r2-postrun-20260809.md`](../experiments/v0.4/v0.4-cvrp-v3-quality-screen-12stage-r2-postrun-20260809.md).
R3 is the next fresh promotion-seeking rung. Its prerequisites are limited to
lossless compact context framing, mechanical provider completion facts,
intended-H versus executed-patch context, and a prospectively specified and
null-checked tie-aware case rule with a loss veto. They are not new
proposal-quality gates,
and R1/R2 are not reinterpreted. The existing local Codex-proxy development
process is again listening on `127.0.0.1:8080`, reports one authenticated active
account, and exposes `gpt-5.6-terra`; no proxy build, upgrade or Scion deployment
work was performed.

The structural R3 hot-path changes and outcome-blind populations were fixed at
`6d5be022`. A final launch-readiness review found that a fresh campaign would
not inherit the R2 database and therefore would miss the strongest R2 SA result
and its deadline-model residuals. Exact executable commit
`76f3e9765128dcc6e0e9234ee6fc21cc4570d59f` adds only that neutral aggregate
problem prior, the limited non-power A/A interpretation, synchronized formal
documentation and tests. The independent clean worktree passes `2081 passed,
1 skipped` in 639.39 seconds. The changes remain deliberately small in
authority:

- canonical provider JSON is compact but lossless; the R2 final H rendering
  would fall by 63,094 chars (28.8%) without selecting or deleting evidence;
- provider finish/tool/argument facts are trace-only, and next-H history now
  separates proposal intent from whether a patch existed and which files ran;
- `expected_effect` remains optional tainted lineage text, avoiding two R2
  description-only rejections that consumed 45,528 tokens;
- quality/validation/frozen use a prospective case net-score plus loss-veto,
  median and CI rule; initial evidence may request exact expansion but cannot
  promote;
- quality, validation and frozen are mutually exclusive outcome-blind 12-case
  blocks with 4->8, 8 and 8 disjoint seeds; one dimension-only time policy is
  used throughout; a fourth 12x8 block is reserved for final B0 replay and is
  absent from proposal/search splits.
- fresh H receives R2 elapsed-budget SA aggregate evidence and its incomplete
  deadline-model facts exactly once, without mechanism selection or holdout
  exposure; the A/A summary says explicitly that no matched MDE/power estimate
  exists, and `calibration_ref` remains empty.

The R2 C tool itself is not broadened: 8/8 completed C responses parsed and
entered evaluation, 4/8 changed two files, and all ten formal evaluations
passed Contract and Verification. There is no evidence that shell or more
provider tools would improve R3. The separately pre-registered provider-free
same-seed A/A/null diagnostic is now complete in
`/home/clawd/research/scion-experiments/v04-cvrp-v3-r3-aa-null-20260809T183131Z-claw`.
Quality, validation and frozen each completed 24/24 pairs with zero pair errors
or runtime-budget hits; every observed combined rule was false, and every
2,000-swap null had 0 passes with a one-sided 95% Wilson upper bound of
`0.001351`. All three artifacts exclude DecisionFeatures. This satisfies only
the diagnostic's pre-registered acceptance condition. The complete record is
in
[`v0.4-cvrp-v3-r3-aa-null-postrun-20260809.md`](../experiments/v0.4/v0.4-cvrp-v3-r3-aa-null-postrun-20260809.md).
The fresh 16-stage R3 campaign is now fixed in
[`v0.4-cvrp-v3-quality-screen-16stage-r3-preregistration-20260809.md`](../experiments/v0.4/v0.4-cvrp-v3-quality-screen-16stage-r3-preregistration-20260809.md).
The frozen proxy/model preflight passed and the one allowed `gpt-5.6-terra`
campaign was launched from exact runtime `76f3e976` at
`/home/clawd/research/scion-experiments/v04-cvrp-v3-quality-screen-16stage-r3-gpt56terra-20260809T194031Z-claw/campaign`.
It is still active and has not been retried, resumed or modified. Candidate
three's completed 96-pair quality expansion was independently reproduced twice:
34W/11L/51T pairs, 6W/0L/6T cases, net score `0.5`, loss rate `0`, and distance
median `+1 [0,2.25]`, with 96/96 valid pairs, zero feasibility/fleet failure and
zero candidate/champion failure. Net, loss and CI-low checks passed, but the
practical median was below `2`, so the actual
`SCREENING_EXPAND_EXHAUSTED_CASE_LEVEL_UNCERTAIN -> continue_explore` route was
correct for an already expanded candidate.

That expansion was nevertheless an off-protocol descendant. Its initial
32-pair result was 3W/0L/5T cases and median `0 [0,1.5]`; CI high was below the
practical delta, so none of the frozen initial expansion routes applied. The
old generic uncertainty fallback expanded it anyway. This is a Protocol
implementation routing deviation, not a candidate or runner failure. The
first prospective patch at `67405777` correctly blocked the generic expansion
but overclassified that evidence as a hard fail. The narrowed current-branch
route is `unclear -> continue_explore`: it neither expands nor promotes, while
also avoiding a new candidate veto. R3 is not reinterpreted and the extra stage
is retained as exploratory evidence.

Candidate four then provided a stronger but scoped signal. Its initial
elapsed-deadline SA refinement completed 32/32 pairs at 10W/5L/17T and
4W/0L/4T cases, with case effects `[9.5,2,4.5,6,0,0,0,0]` and median
`+1 [0,6]`; the frozen initial-quality route correctly requested exact
expansion. The 12x8 expansion completed 96/96 at 32W/12L/52T pairs and
5W/0L/7T cases, median `0 [0,3.25]`, zero fleet regression and zero execution
failure. Net, loss and CI-low passed, but broad practical median failed, so the
actual route was again `unclear -> continue_explore` with no validation or
frozen event. Two independent raw recomputations matched exactly.

The completed expansion is nevertheless useful algorithm evidence: the six
non-X cases were 5W/0L/1T with subgroup median `+3.25`, while all six X cases
tied. Every case above dimension 200 was X, so family and size cannot be
separated. The honest label is therefore
`SCOPED_SIGNAL_ONLY / UNIDENTIFIABLE_FAMILY_VS_SIZE`, not promotion or broad
null.

The next H/C completed normally with no schema, binding, Contract or
Verification failure, but its time-normalized operator-credit implementation
was only an unused `segment_outcomes` scaffold. This repeats an R2
implementation-fidelity gap and is not evidence against the intended algorithm
mechanism. Its initial formal screening then completed 32/32 pairs at
6W/1L/25T and 2W/0L/6T cases, effects `[1,0,0,0,0,0,1,0]`, median
`0 [0,1]`, with zero execution or fleet failure. Two independent raw
recomputations matched. None of the three pre-registered expansion predicates
held because both median and CI high were below practical delta `2`, but exact
runtime `76f3e976` again reached the old generic
`SCREENING_EXPAND_CASE_LEVEL_UNCERTAIN` fallback. Formal screening seven then
completed its off-protocol exploratory expansion at 3W/13L/80T pairs and
0W/1L/11T cases, median `0 [0,0]`, with zero execution or fleet failure. The
expanded gate correctly returned `SCREENING_FAIL_CASE_QUALITY ->
continue_explore`; two independent raw recomputations matched. Because the
exact source added only the unused scaffold, this result characterizes that
source snapshot, not the unimplemented time-aware-credit mechanism.

The next H was again source-grounded: it proposed replacing full route
recalculation inside two intra-route 2-opt paths with a running directed
reversal delta. C was provider-complete, source-bound and structurally closed,
and the candidate passed Contract and Verification. A separate result-blind
formula audit nevertheless found that for reversals longer than two customers
the boundary term uses the rolling `customers[j-1]` rather than the fixed
`customers[i]`. This makes implementation fidelity partial and can accept an
actual distance increase, but it is analysis rather than a host candidate gate;
the fixed Protocol remains authoritative. Formal screening eight subsequently
completed 32/32 valid pairs with 0W/32L/0T pairs and 0W/8L/0T cases. In the
pre-registered manifest order its case effects were
`[-45,-55.5,-19.5,-50.5,-1171,-261,-481,-343]`, with median `-158.25` and
bootstrap interval `[-412,-45]`; candidate/champion solver failures, fleet
regressions and required-runtime-field failures were all zero. Two independent
raw recomputations matched. The exact actual and expected route was
`SCREENING_FAIL_WIN_RATE -> continue_explore`. Runtime evidence is consistent
with the audited loop defect, but does not isolate it causally; the supported
classification is a failed exact source with partial H/C implementation
fidelity, not a provider, schema, binding, runner or V3-control failure.

The following H/C pair is also source-grounded and provider-complete. It changes
only `_route_removal`: shuffled routes are removed whole while they fit the
requested destroy size, and the first overshooting route contributes one
injected-RNG seed plus its nearest route-local customers to reach the exact
count. An independent result-blind source audit found the reachable scheduler
path deterministic, capacity-safe, rollback-safe and faithful to H, with no
candidate-introduced correctness blocker. The added partial-route sort can
change runtime/search quality and remains an empirical hypothesis rather than
a framework guarantee. Formal screening nine's initial block then completed
32/32 valid pairs at 13W/8L/11T and 4W/1L/3T cases. Manifest-order case effects
were `[8.5,6.5,6.5,28,0,0,0,-5]`, with median `+3.25 [0,8.5]`, zero fleet
regression and zero candidate/champion failure. All four non-X cases won; the
four X cases were 0W/1L/3T. Net score, loss rate, practical median and CI-low
all passed, and the exact required route was
`SCREENING_EXPAND_REQUIRED_FOR_PASS -> expand_screening`, because initial
evidence cannot pass before the frozen expansion. Two independent raw
recomputations matched. The exact 12x8 expansion is active; no incomplete
expansion W/L/T or deltas are read or used here.

The chronological result-blind H/C audit now covers all seven provider pairs
through that H/C pair. Every H was schema-valid, saw the same complete
11-file source union exactly once across champion/current sections, named the
correct owner and symbol, and proposed a solver mechanism rather than framework
or measurement work. H context grew from about 93k to 136k characters as exact
branch source and history accumulated, but even the largest context remained
source-grounded; size alone therefore does not trigger an H-context A/B. All C
calls were likewise provider-complete and schema-valid, with three `faithful`,
three `partial` and one `scaffolding_only` observational fidelity labels. The
partial cases separate a missed exact-replace use site, an elapsed-budget
denominator mismatch and the directed-delta endpoint error; the scaffold is the
zero-use `segment_outcomes` declaration. A deterministic multi-site closure
failure plus the independent R2/R3 scaffolding omissions satisfy the frozen C
expression A/B trigger, but do not prove that the typed schema caused them.
That post-terminal A/B remains a proposal-surface diagnosis, never a candidate
gate or solver-outcome comparison; H remains unchanged.

The active expansion later exposed an operator-side validity problem: pytest
ran concurrently on the same two-vCPU/one-physical-core host while the
deadline-driven solver was evaluating several pairs. All CPU-heavy repository
validation was stopped immediately. Because every overlap boundary cannot be
reconstructed exactly, the root is conservatively
`OPERATOR_LOAD_CONTAMINATED_FOR_STRICT_PROMOTION_CLAIM`; no selected pair is
silently deleted or retried. The outcome-blind
[recovery preregistration](../experiments/v0.4/v0.4-cvrp-v3-r3-operator-load-recovery-preregistration-20260809.md)
was written before the quality expansion became terminal. R3 remains useful
for research behavior and candidate discovery, but only an exact candidate
promoted by its existing Protocol is eligible for the fixed provider-free
clean quality -> validation -> frozen -> final replay.

An independent outcome-blind experiment-design audit also found a prospective
measurement gap that does not reinterpret Warehouse acceptance or incomplete
R3. The generic formal loop runs champion before candidate, enables champion
result caching by default and reruns the cumulative matrix on expansion. Raw
pairs retain deltas and runtime/cache facts but not both absolute objective
vectors, subject order, feasibility and subject time intervals. Consequently
objective headroom, order/load effects and case-versus-seed attribution are
partly `UNIDENTIFIABLE`. Before another promotion campaign, the smallest
correction is fresh cache-off subjects, deterministic AB/BA counterbalancing,
immutable atomic case×seed blocks and the corresponding minimal raw fields in
the existing runner. Exact non-futility routes, seed-first versus case-first,
matched power and Warehouse size budgets remain contingent on the already
frozen provider-free diagnoses; they are not new gates or post-hoc R3 changes.

The fixed R1 design is in its
[preregistration](../experiments/v0.4/v0.4-cvrp-v3-open-research-8stage-r1-preregistration-20260809.md),
and the complete claim boundary and mechanism analysis are in its
[postrun](../experiments/v0.4/v0.4-cvrp-v3-open-research-8stage-r1-postrun-20260809.md).

## Research-path corrections after the controls

- Local existing-file authoring now consistently prefers ordered
  `exact_replace` edits and preserves source outside the selector.  A regression
  reproduces the CVRP R1 terminal-return hazard without adding a style gate.
- H-visible `observation_count` now comes from the same complete
  `experiment_history` that H receives; the old zero in optional diagnostics
  was accounting-only, not context loss.
- A clean current-step candidate based on the declared champion is now marked
  `incremental_effect_isolated=true`; cumulative/provisional ancestry remains
  false.
- Warehouse operator-pool configuration synchronization preserves original
  bytes when operator semantics are unchanged, and one lifecycle writer owns
  real create/remove changes. Rejected created operators leave the clean pool
  configuration untouched.
- Raw/status Protocol snapshots now distinguish `in_progress`, `complete`, and
  `partial_champion_evidence`; raw and canonical candidate runtime-pair counts
  agree and remain outside `DecisionFeatures`.
- A focused routing test proves explicit `SCION_MODEL=gpt-5.6-terra` plus
  `SCION_BASE_URL=http://127.0.0.1:8080` selects the local OpenAI-compatible
  path even when conflicting Anthropic fallback variables exist.
- At the time of these controls, the then-active formal-candidate evidence
  writer read pending staging before disposition, and Decision lineage captured
  the evaluated candidate before clean-parent restoration. This preserves how
  the historical campaigns were interpreted. The writer and its identity/hash
  closure have since been removed from the active campaign; ordinary branch,
  step and Protocol evidence now carry the current scientific record.
- If an asynchronous champion update makes a branch stale after Verification
  but before Protocol, Scion now rejects staging and terminalizes that H as
  `not_evaluated`. The branch becomes `ABANDONED`; a fresh invocation starts
  from the new champion instead of inventing a durable patch-recovery owner.

These are authoring, attribution, and diagnostic corrections.  They do not
change the completed controls' recorded Protocol thresholds or Decision
outcomes, so the campaigns need no scientific reinterpretation.

## Post-correction runtime regressions

Fresh one-round runs exercised the final corrected hot path.  They are runtime
regressions, not substitutes for the multi-round M5/M6 direction-change
evidence.

Warehouse:
`/home/clawd/research/scion-experiments/v04-warehouse-v3-minimal-terra-1r-20260808T132138Z-claw/campaign`

- valid and complete, wrapper exit 0, one H and one C, both model traces
  `gpt-5.6-terra`;
- new subcategory-consolidation operator; Contract and Verification passed;
- 20/20 valid screening pairs, zero failures, median delta 0 on both declared
  objectives, then `SCREENING_FAIL_WIN_RATE` / `continue_explore`;
- the then-active recorder wrote one replayable historical candidate artifact;
  zero candidate workspace paths remained after Decision. Current campaigns do
  not write that artifact type.

CVRP:
`/home/clawd/research/scion-experiments/v04-cvrp-v3-minimal-terra-1r-20260808T132654Z-claw/campaign`

- valid and complete, wrapper exit 0, one H and one C, both model traces
  `gpt-5.6-terra`;
- localized cross-exchange edit preserved the unrelated `_two_opt_star`
  terminal return; Contract and Verification passed;
- 32/32 valid screening pairs, zero failures, case win rate 0.375, median
  distance delta -0.25 with fleet violation unchanged, then
  `SCREENING_FAIL_WIN_RATE` / `continue_explore`;
- the then-active recorder wrote one replayable historical candidate artifact;
  zero candidate workspace paths remained after Decision. Current campaigns do
  not write that artifact type.

An earlier Warehouse launch ending in local-proxy HTTP 401 stopped before a
valid H/C attempt and remains excluded infrastructure evidence.  The completed
runs used the authenticated local proxy key only in their child-process
environment; the key was not printed or persisted.

These controls predate the current V3 §11.2 disposition correction. Their
recorded clean-parent outcomes remain historical facts and are not rewritten;
new campaigns must retain every Contract/Verification-passing, completed
screening candidate as the provisional branch head.

## Accepted baseline validation

Focused slices for the baseline's former staging/replay/runtime cleanup were
green (`75 passed` before its full suite and `65 passed` after final
formatting). Both real direct outer smokes passed. The two fresh Terra
regressions above each wrote one artifact under the historical recorder; that
is not a current acceptance requirement.

At baseline `4d637959`, using the required `claw` interpreter, the complete
default suite ran with
no file exclusion: `1946 passed, 1 skipped, 0 failed` in 619.61 seconds.  All
144 changed/new Python files pass critical Ruff syntax/name checks; the 14
final research-hot-path files pass formatter check; all of `scion/scion`
passes explicit `compileall`; and `git diff --check` is clean.  A repository-
wide formatter sweep would mechanically reformat 108 older changed files, so
it was intentionally not applied as unrelated churn. These baseline results do
not by themselves validate the active S2/S3 changes or satisfy the new solver-
improvement acceptance.

For the active S2/S3 implementation, the focused V3 integration set passed 270
tests. After removing the active lineage identity mirror, the
evidence/proposal/composition set passed 58 tests and the campaign/preflight
integration set passed 43 tests; critical Ruff `E9/F63/F7/F82` and changed-file
diff checks passed. These were focused results at that checkpoint; they do not
replace the later complete-suite result.

After the R3 lifecycle correction, the complete suite passed
`1964 passed, 1 skipped` in 620.83 seconds; focused adjacent regression passed
69 tests and critical Ruff/diff checks passed.

After the R6 proposal-rejection correction, the focused proposal, CampaignLoop
and fail-closed regressions passed 92 tests. The complete suite passed
`1965 passed, 1 skipped` in 629.99 seconds; critical Ruff and diff checks
passed. This is the frozen framework checkpoint for the next fresh Warehouse
run, not solver-evidence acceptance by itself.

After the production research-design corrections were integrated, the latest
complete suite passed `2011 passed, 1 skipped` in 639.18 seconds. This is the
current full-regression terminal count; the 1949, 1964, 1965 and 1988 results
above remain historical checkpoints.

## Known residuals

1. CVRP H input grew about 20.7k -> 47.3k -> 73.7k -> 100.2k tokens across
   four rounds because prior evidence and telemetry were repeated in full;
   Warehouse production similarly reached 83.8k by its final H. The correction
   keeps complete raw lineage but uses the fixed V3 semantic view:
   recent current attempts detailed, older current evidence structured, and
   sibling state brief. It is not token-triggered truncation, top-k selection,
   an opaque summary or a gate. C now sees plain path/content rather than
   owner, digest, provenance or view metadata. A legacy internal source ledger
   remains host-only; it is not provider-visible authority, a gate, or a
   research-path blocker, and no further phase investment is planned for it.
2. Warehouse lacks direct per-operator invocation counts, and CVRP R4 lacks
   fast/fallback/2-opt-probe counters.  Conclusions therefore keep the narrower
   candidate-level or association-only attribution.
3. Neither problem declares rename/permutation invariance.  No universal
   metamorphic gate is pending; a problem may add a probe later only when its
   semantics declare the transformation meaningful.
4. The prior one-active-branch controls are historical baseline evidence. The
   current runtime admits at most three active branches and now rotates
   same-tier EXPLORE work by persisted least-recently-served time. This remains
   a lightweight V3 scheduler and must not reintroduce evidence scoring, object
   authority, signed identity, lease, or closure machinery.

## Closure status

The prior lightweight-runtime milestone is accepted at `4d637959`; the active
`TASK.md` is not closed. Warehouse R8 completed 36/36 stages, reached synthetic
champion v3 through two exact promotions in one campaign, and retained both
promotion steps plus the cumulative v3-v1 gain on 108/108 independently
declared held-out pairs. Synthetic Warehouse continuity is
`CONTINUOUS_OPTIMIZATION_CONFIRMED`. Prod-1.2 then promoted a production-style
DestroyRebuild candidate and its separately preregistered 12/12 fresh replay
returned `FROZEN_PASS`, so Warehouse production transfer is
`RETAINED_PRODUCTION_IMPROVEMENT` and all Warehouse acceptance is complete.
The provider-free Warehouse measurement reanalysis now has a frozen tracked
input bundle at
[`warehouse-measurement-reanalysis-v1`](../experiments/v0.4/warehouse-measurement-reanalysis-v1/bundle_manifest.v1.json):
all 17 synthetic and 16 production screening cases, four ordered seeds, exact
step-local champions and historical/even/static-stratified selector arms. Its
output roots remain unlaunched until the host is CPU-exclusive after R3.
CVRP has no Protocol-complete promotion. R1 is sealed at 5/8 and R2 at 10/12;
both retain valid partial science but neither candidate path reached validation
or frozen holdout. R2's elapsed-budget SA is the current strongest lead. R3's
code, context, measurement rule and disjoint populations are fixed and fully
regressed, its provider-free null calibration completed acceptably, and its
fresh 16-stage campaign is active from exact runtime `76f3e976`. Closure still
requires a clean screening -> validation -> frozen promotion, an independent
B0 comparison and the S6 cross-problem/full-regression record. The active root
alone cannot supply that clean claim because of its recorded operator-load
contamination; a Protocol-promoted exact source must pass the pre-registered
provider-free recovery replay.
If R3 does not promote, the next step is a provider-free, frozen-cohort
case-by-seed and budget diagnosis before any fresh campaign; H-context or
C-expression A/B is conditional on observed friction rather than mandatory
framework work. Those diagnostics remain excluded from Decision and cannot
reinterpret R3.
Deployment, packaging, builds, root/systemd and self-proof infrastructure are
neither prerequisites nor completion claims.
