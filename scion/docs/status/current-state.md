# Scion v0.4 Current State

*Last updated: 2026-08-14*

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
- The postrun analysis handoff is now a thin read-only V3 guide over ordinary
  DB events, H/C traces, source/workspaces, Verification, raw metrics, Protocol,
  Safe Features and the recorded Decision. Prepared/readiness bundles,
  receipts, digest/identity reconciliation and a formal-candidate index are no
  longer analysis prerequisites; missing exact source composition is reported
  as `UNIDENTIFIABLE` rather than repaired with new framework machinery.
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
It was not retried or resumed and is now sealed after the host reboot at
`2026-08-10 05:44 UTC`; the terminal classification is
`RUN_INVALID_INFRA / VALID_PARTIAL_SCIENCE`. Candidate
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
recomputations matched.

The same exact source's 12x8 expansion then completed 96/96 valid unique pairs
with zero candidate/champion/total failure, zero fleet regression and no
protected-objective regression. Pair evidence was 37W/16L/43T and case evidence
7W/0L/5T; manifest-order case medians were
`[7.5,25.5,3,14,5,0,0,0,4,4.5,0,0]`, with overall `+3.5 [0,6.25]`, net score
`0.583` and loss rate `0`. Two independent raw recomputations matched the raw
comparison on all 96 pairs. All five declared quality components passed; the
exact actual and expected route was `SCREENING_PASS -> queue_validate`. This is
R3's first exact candidate to advance beyond quality screening. Its validation
canary completed, then the host reboot interrupted same-source formal
validation at 52 attempted and 51 completed/valid pairs. The partial checkpoint
reported zero candidate, champion or total execution failures, but its W/L/T,
deltas and gate are excluded from adjudication and are not reported here. The
durable record therefore remains
10 screening, zero completed validation and zero frozen stages, with champion
B0/v1. There is no Protocol promotion or eligible clean-recovery candidate.
The full interruption boundary is recorded in the
[`R3 reboot postrun`](../experiments/v0.4/v0.4-cvrp-v3-quality-screen-16stage-r3-reboot-postrun-20260810.md).
The completed quality evidence remains valid; the reboot is not an algorithm
negative.

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

The experiment-owned input bundle at
`campaign_out/v04-cvrp-c-expression-ab-20260811-input` froze the four
historical H/C traces, each trace's ordinary 11-file source, both complete
terminal tool definitions and per-fixture outcome-blind checklists. The
203-line runner, 123-line strict diff parser and 139-line input loader add zero
production lines. Fifteen focused fake/parser tests, frozen-input validation
and `bash -n` pass. One control-only acquisition attempt failed before the
driver, made zero scientific/model-generation or solver calls and is archived
unchanged at
`campaign_out/v04-cvrp-c-expression-ab-20260811-control-pre-driver-acquisition-failure-20260812T084111Z`,
outside the scientific run. The corrected ordinary-user launcher then acquired
the driver and the authorized run completed exit `0`: 8/8 provider cells were
terminal, with no provider failure, retry or solver call. All four exact cells
normalized, applied and passed Contract. All four strict-diff cells failed
strict application because context or removal did not match the frozen source;
each therefore received its preregistered fixed `0/0` score and no blind
packet. Two independent blind reviewers agreed on exact-arm fixture scores
`2/2`, `1/1`, `1/1`, `1/1`, totaling H=`5` and source-anchor=`5` versus diff
`0/0`. The generated hunks had positional/context mismatches while the frozen
no-offset/no-fuzzy parser behaved as designed. All four adoption conditions
fail. R51 is therefore `VALID_COMPLETE_C_EXPRESSION_DIAGNOSTIC / STRICT_DIFF_NOT_ADOPTED / EXACT_RETAINED`,
without production change, retry or gate.
The complete boundary is recorded in the
[C-expression postrun](../experiments/v0.4/v0.4-cvrp-c-expression-ab-postrun-20260812.md).
The existing real
CVRP direct-v3 outer smoke also passes `1 passed in 32.55s`, but its MockLLM
multi-file no-op and real 12-case/one-seed/one-second screening establish only
local short-chain stability, not provider or algorithm evidence.

A separate result-blind provider-surface audit reaches the same priority. The
seven H calls do not justify more H tools or history compression: all received
the complete source, named the correct owner/symbol and stayed focused on
solver mechanisms. C is the observed fidelity bottleneck despite seeing the
same complete 11-file union, but the completed strict-diff treatment failed
exact source application in all four fixtures. R51 closes that direction
instead of adding a shell, tool loop or repair gate. The subsequent R52
research-hot-path subtraction is complete across nine production files at
`+273/-551`, net `-278`. `proposal_source_ledger` and its owner, provenance,
view and self-proof machinery are deleted. One ordinary
`editable_source_context` holds the approved target, unique canonical
path/content values and consolidated positive Warehouse/CVRP API, object-model
and legal-surface guidance. Branch-current history/workspace source takes
precedence over champion;
a touched-missing helper does not fall back to champion; `None` remains distinct
from an existing empty file; and create/modify behavior stays strict. The exact
selector digest remains only as runtime content binding.

H provider input now excludes recursive host/control metadata while retaining
the complete research science, source and evidence. C provider input is exactly
the approved hypothesis plus `editable_source_context`. The complete raw
structured context remains durable in trace, and Contract continues to own
negative path/import/edit constraints. No gate, Trust/Hash authority, ledger or
provider tool loop was added. Main focused regression passed 169 tests and an
independent expanded run passed 207. The real CVRP direct outer smoke passed
once in 32.70 seconds. The Warehouse outer smoke traversed the complete V3
chain, then failed only at an unrelated dirty V8 `typed_telemetry_summary`
assertion; it is therefore not recorded as passing. Potential objective,
headroom or case-structure additions remain separate scientific questions.

The bounded CVRP minute diagnostic has now completed and is sealed in its
[postrun report](../experiments/v0.4/v0.4-cvrp-minute-one-step-postrun-20260812.md)
as `VALID_COMPLETED_ONE_STEP_SCREEN / SCREENING_FAIL_CASE_QUALITY /
NO_PROMOTION`. It ran once from the clean ordinary-user `e4b6b98d` archive with
exit `0`, exactly one Terra H, one approved-H-bound C, one canary, one
`CampaignManager.run_one_step()` and one fresh four-case cache-off
`AB/BA/AB/BA` SCREENING call. It executed no validation or frozen stage.

Terra proposed the active embedded-VNS runtime-share mechanism and C made one
minimal solver change: `EMBEDDED_VNS_MAX_RUNTIME_SHARE = 0.0 -> 0.35`, while
retaining repair-improvement rescue. Contract, Verification and the typed
candidate canary passed. The canary artifact records one attempted candidate
and no raw or champion-side result, so it is not claimed as independently
auditable paired canary evidence.

All four formal pairs were successful, feasible and fresh. Independent
recomputation is `0W/1L/3T`, effects `[-16,0,0,0]`, median `0` with 95% CI
`[-16,0]`, and zero fleet regression. Aggregate telemetry is consistent with
the proposed allocation shift: ALNS iterations increased `44 -> 151`, ALNS-core
share increased `0.195208 -> 0.382246`, and embedded-VNS share fell
`0.419914 -> 0.287778`. Useful conversion did not improve: best updates fell
`7 -> 4`, VNS improvements fell `192 -> 90`, and `P-n65-k10` became 16
distance units worse. The mechanism artifact itself remains `association_only`
and does not enter Decision.

Decision correctly recorded `continue_explore` with
`SCREENING_FAIL_CASE_QUALITY`; B0/v1 remains the only champion and the verified
candidate is only a provisional branch head. The wrapper classification
`COMPLETED_ONE_STEP_WRAPPER` and campaign-summary `run_complete=true` describe
the bounded one-step lifecycle only, not validation, frozen holdout or campaign
completion. The run demonstrates one stable analyzable algorithm-research step,
not retained CVRP improvement, continuous optimization or task completion.

R54 has now run once and is sealed in the
[minute feedback one-step postrun](../experiments/v0.4/v0.4-cvrp-minute-feedback-one-step-postrun-20260812.md)
as `VALID_TERMINAL_CANDIDATE_RUNTIME_FAILURE / DECISION_ABANDON /
FRAMEWORK_POST_DECISION_CONTEXT_PERSISTENCE_ERROR / NO_PROMOTION`. It started
again from B0/v1 on the clean `e4b6b98d` archive and preserved seed `11`, the
P65/E101/X120/X233 roster, `8/12/12/15`-second limits, `AB/BA/AB/BA`, cache-off
subjects, Terra H/C limits `1/1`, one canary and one formal SCREENING call.

H incorporated R53's negative feedback directly and selected a source-grounded
elapsed-budget simulated-annealing mechanism. C implemented the central
elapsed-fraction design but deleted `_SimulatedAnnealing.cool` while leaving
three calls in repair-error, infeasible and route-limit branches. Contract and
all nine recorded Verification checks reported pass, but V3/V4 were skipped
and the controlled smoke did not traverse those branches. Formal evidence is
three valid ties on E101/X120/X233 plus one P65 candidate runtime-audit failure.
The P candidate's emitted objective is excluded from delta and W/L/T.

Decision durably recorded `abandon / CANDIDATE_RUNTIME_FAILURE`, and B0/v1
remains the only champion. A separate post-Decision context projection then
raised a feedback-cardinality `ValueError`, causing wrapper exit `1` after the
scientific Decision was already stored. Candidate failure, Decision, and the
framework persistence exception are kept as separate facts. The root is not
resumed or retried; this closeout preregisters no next experiment.

R55 closes the two narrow prospective defects without reopening R54. Commit
`3221416c` allows canonical screening-context feedback cardinality to range
from the exact valid-pair count through valid plus candidate-failed pairs while
preserving exact observed W/L/T accounting. Commit `9aedfb64` makes CVRP V3/V4
execute subsecond problem-owned operator-recovery and public-entrypoint tests
instead of skipping. The recovery fixtures assert feasible-incumbent/runtime
consistency without naming simulated annealing or `cool()`, so they do not
freeze a solver mechanism or add a quality or novelty gate. A provider-free
materialization of the exact R54 patch fails all three repair-error, infeasible
and route-limit fixtures; B0 passes the ordinary focused/adjacent 25-test set.
No provider call or Protocol/formal experiment was rerun; only provider-free
unit/smoke verification ran. No next H/C is preregistered, launched or
authorized by this correction.

R56 was frozen in its
[corrected-runtime minute one-step preregistration](../experiments/v0.4/v0.4-cvrp-r56-minute-corrected-one-step-preregistration-20260812.md)
from clean `acdc80ba`, fresh B0/v1, Terra H/C maxima `1/1` and retry zero. It
has now terminalized and is sealed in the
[postrun](../experiments/v0.4/v0.4-cvrp-r56-minute-corrected-one-step-postrun-20260812.md)
as `VALID_TERMINAL_RESEARCH_PROCESS_OBSERVATION /
VERIFICATION_LIGHT_REJECTED / ZERO_PROTOCOL_EVIDENCE / NO_DECISION /
NO_PROMOTION`.

R55 persistence and test mechanics remain host-side preregistration/runtime
rationale and are absent from the provider-visible research context. The
R56-specific provider additions are only the neutral algorithm question and
R53–R54 algorithm evidence alongside the ordinary complete problem-owned
context; R54 mechanism quality remains unidentifiable because its failed P row
has no admissible delta.

The user subsequently supplied the exact authorization for the `acdc80ba`
fresh-B0 problem-owned source-derived context, the neutral R53–R54 algorithm
prior, the R56 question, at most one Terra H and conditional C, and this one
minute screen. The frozen ordinary-user launcher was invoked exactly once and
its control marker records inner-process acquisition at
`2026-08-12T15:05:33Z`, with startup-observation PID `277510`. The PID is not a
durable identity or continued-liveness claim. The wrapper exited `0` normally
about 51 seconds later with `COMPLETED_ONE_STEP_WRAPPER`, one H/C and a passing
Contract.

H strongly followed the neutral evidence and explicitly required
elapsed-budget updates after every ordinary or recovery-path iteration, with
no calls to a removed cooling API. C preserved the algorithm intent but its
20-space `replace_all` matched only one of the five original calls. Four calls
remained after `_SimulatedAnnealing.cool()` was removed: three recovery paths
and one ordinary loop-tail path. V3 ran the problem-owned fixtures in 519 ms
and rejected all three recovery cases with `AttributeError`; the fourth call
is a source-proven latent defect. V4 and all later Verification checks, canary,
formal Protocol and Decision were not reached. There are no raw metrics,
admissible pairs, W/L/T or solver-quality conclusions. B0/v1 remains champion.
The root is not repaired or retried. This is evidence for minimal provider-free
C expression/tool redesign; no successor H/C experiment is preregistered,
authorized or launched.

R57 records that provider-free expression correction, not a successor
algorithm experiment. Commit `f537fed5` adds optional source-bound
`exact_line_replace`, which matches an exact complete logical line across
outer indentation levels and replays each replacement under the indentation of
its matched source line. It adds no provider source-search/tool loop, retry,
quality gate or Decision input. A counterfactual re-expression of the frozen
R56 C response matched all five `annealing.cool()` callsites through the
production parse -> Contract -> materialize path; non-skipped V3 and V4 then
passed. The combined regression passed 183 tests, while independent review
passed focused 38 plus adjacent 92 tests. No provider, canary, formal Protocol
or Decision call ran. Therefore this is expression-fidelity and regression
evidence only, not a repair or retry of R56, a new R56 result, or solver-quality
evidence.

R58 was frozen in its
[expression-corrected seed-29 minute one-step preregistration](../experiments/v0.4/v0.4-cvrp-r58-minute-expression-corrected-one-step-preregistration-20260812.md)
from clean `42535efc`, B0/v1, with at most one Terra H and
conditional C with retry zero. If Contract, non-skipped Verification and the
veto-only canary permit, the sole formal call uses seed `29` on the same
P65/E101/X120/X233 cases with `8/12/12/15`-second limits, fresh cache-off
subjects and `AB/BA/AB/BA` order. Expanded screening, validation, frozen and
promotion are unreachable; maximum declared formal solver time is 94
subject-seconds.

Seed `29` differs from the immediate R53–R56 minute-series seed `11`, but it is
not globally unseen, independent or held out: R3 already used it on these exact
four cases. Only the R58 subject executions are fresh. A complete result is
therefore one new-H/C exploratory screen on an already exposed case/seed
coordinate, not exact-candidate replication, seed robustness, case
generalization, validation, retained improvement or long-campaign readiness.
R57's `exact_line_replace` is an optional C tool fact and is absent from the H
algorithm prior; it adds no required-use gate, repair loop or algorithm claim.

After the earlier generic preparation assent, the user supplied exact
authorization for the clean `42535efc` fresh-B0 problem-owned source-derived
context, R53–R56 neutral algorithm prior, R58 question, local Codex proxy send
to Terra, at most one H and conditional C, and one minute screen. The frozen
launcher was invoked exactly once. Its control marker records successful
inner-process acquisition at `2026-08-12T23:38:22Z`, PID `316499`. The PID is a
startup observation only. The wrapper terminalized normally about 44 seconds
later with exit `0`, `COMPLETED_ONE_STEP_WRAPPER`, one terminal valid Terra H/C,
zero retry/repair calls and a passing Contract. Research eligibility is
`invalid_research_rejected_only / ineligible_zero_evaluated`, not an
infrastructure-invalid wrapper.

H received the exact question and R53–R56 prior once and again selected a
source-grounded, falsifiable elapsed-budget-SA mechanism. C received that exact
approved H, all 11 editable files and a tool surface containing optional
`exact_line_replace`. It nevertheless emitted six `exact_replace` edits and no
line-oriented edit. Every selector matched uniquely and Contract passed, but
the applied source removed only the 20-space and 12-space calls while deleting
`_SimulatedAnnealing.cool()`. Three 16-space calls remained on repair-error,
candidate-infeasible and route-limit recovery paths. V1, V1b and V2 passed;
V3 rejected all three fixtures with `AttributeError` in 568 ms. V4 and later
checks, canary, formal Protocol and Decision were not reached. Candidate
cleanup succeeded and B0/v1 remains the only champion.

The independent
[postrun](../experiments/v0.4/v0.4-cvrp-r58-minute-expression-corrected-one-step-postrun-20260812.md)
seals `VALID_TERMINAL_RESEARCH_PROCESS_OBSERVATION /
VERIFICATION_LIGHT_REJECTED / ZERO_PROTOCOL_EVIDENCE / NO_DECISION /
NO_PROMOTION`. Seed-29 W/L/T, delta, CI and fleet comparison are undefined, so
there is no algorithm-quality, replication or generalization result. The
provider-free R57 replay proved the optional line form expressive; R58 shows
that making it available did not make C select it. Pause provider CVRP
algorithm experiments and redesign/test the C expression-selection surface
provider-free. Add no source-navigation loop, repair/retry call, patch grader,
algorithm-direction rule, candidate-quality gate or Decision input. Do not
launch an R59 provider experiment, a long campaign or a WSL run.

R59 is a provider-free tool-presentation correction, not a successor algorithm
experiment. Commit `47fe81ee` builds the root and nested change objects from
one shared flat schema factory. An explicit `edit_intent` selects among four
singleton-intent branches for localized replacement, line replacement,
complete-file create/modify and typed deletion; the legacy missing-intent shape
and default `replace_all=false` remain compatible. Exact-span and
indentation-neutral exact-line intents now have neutral parallel descriptions,
and the latter has one explicitly shape-only example that does not require its
selection. A mocked OpenAI transport call proves its actual `tools[0]` equals
the version-controlled payload snapshot.

Frozen provider-free R56/R58 counterfactual replay keeps the R58 original
result distinct: the original exact edits leave three residual `cool()` calls,
whereas the line re-expression matches all five callsites and passes non-skipped
V3/V4. The scoped suite passed 170 tests and independent review passed 68. No
provider, canary, formal Protocol or Decision call ran, so R59 provides no
algorithm-quality evidence and does not repair or retry R58. Provider
algorithm experiments remain paused.

R60 has now completed as one C-only tool-presentation matched pair, not an
algorithm experiment. Its
[postrun](../experiments/v0.4/v0.4-cvrp-r60-c-tool-presentation-pair-postrun-20260813.md)
seals `TERMINAL_MATCHED_PAIR_OBSERVATION / BOTH / BOTH_LINE_SELECTION /
NO_IDENTIFIED_PRESENTATION_ADVANTAGE / ZERO_ALGORITHM_QUALITY_EVIDENCE`.
The frozen wrapper held the complete R58 approved-H C turn, prompt, two system
blocks and all 11 problem-owned source files constant. It called Terra once
with the complete OLD `42535efc` tool and then once with the complete NEW
`47fe81ee` tool, with zero H calls and retries. Both responses were terminal
before provider-free scoring; both opaque primary records preceded the reveal.
The wrapper exited `0` after about `69.043` seconds.

Both arms passed production parse, source binding, Contract, materialization
and independently executed non-skipped V3/V4. OLD V3/V4 took 555/854 ms and
NEW took 508/844 ms; these are local consistency-test timings, not provider or
algorithm performance. After reveal, both responses contained exactly one
unindented `exact_line_replace` for `annealing.cool()` with
`replace_all=true`, each matched all five sites and left zero residual calls.
OLD used six other exact edits; NEW used three and had one no-op exact edit
dropped by normalization. Thus both primary and descriptive patterns are
`BOTH`; the new presentation has no identified advantage on this pair.

Independent post-hoc source inspection is outside the preregistered endpoints.
OLD's normalized scheduler repeats `destroy_weights.record(d_idx, score)`
consecutively; the average ratio often cancels but the accounting is
semantically unclean. NEW defines `set_deadline_progress` but never calls it,
leaving temperature at `start_temp` and the approved mechanism inactive.
Neither implementation enters canary, formal solver testing, branch retention
or promotion. Canary, formal Protocol, algorithm-quality and Decision calls
are all zero.

The single fixed OLD-then-NEW pair confounds presentation with order, time and
model stochasticity. Historical R58 is not another cell. R58-to-R60 shows only
that both presentations could and in this pair did select the five-site line
expression; it does not prove an R59 causal improvement, provider population
rate or reproducibility. Provider algorithm experiments remain paused, and no
R61 was preregistered, authorized or launched at R60 closeout.

R61 was later executed as an independent provider-free semantic audit over
the sealed R60 materialized workspaces. Its
[postrun](../experiments/v0.4/v0.4-cvrp-r61-provider-free-semantic-audit-postrun-20260813.md)
seals `TERMINAL_DIAGNOSTIC / SEPARATE_ENDPOINT_TRADEOFF /
ZERO_ALGORITHM_QUALITY_EVIDENCE`. Each cell and each progress coordinate used
a fresh temporary copy and subprocess. A fake solution, fake instance,
controlled elapsed clock and patched operators drove exactly one ordinary
worsening-candidate scheduler iteration at progress `0.1` and `0.9`.

OLD called its candidate `set_progress` once before accept at both coordinates.
Acceptance temperature fell from `2.6857958838184386` early to
`0.018616455666360693` late, so deadline wiring passes. The same ordinary path
dynamically recorded the destroy weight twice and repair weight once at each
coordinate, so accounting fails `2/1`. NEW defines
`set_deadline_progress` but the candidate scheduler called no setter; early and
late acceptance both observed start temperature `5.0`, so deadline wiring
fails. Its destroy/repair recording was exactly `1/1`, so accounting passes.

The two endpoint booleans remain separate and
`aggregate_algorithm_success=null`. Static callsite counts are corroboration
only; the decisions come from the isolated dynamic probes. The synthetic state
is not a CVRP model, feasibility check, objective-quality comparison or
benchmark. Provider, canary, formal Protocol solver, quality solver and
benchmark/BKS inputs are all zero. R61 does not rewrite R60, enter Protocol or
Decision, rank the candidates or establish generalization. Provider algorithm
experiments remain paused; no R62 is preregistered, authorized or launched.

R62 later completed as an independent provider-free static C semantic-risk
sidecar over frozen fresh-B0, the sealed R60 workspaces and ephemeral in-memory
controls. Its
[postrun](../experiments/v0.4/v0.4-cvrp-r62-provider-free-c-semantic-risk-sidecar-postrun-20260814.md)
seals `TERMINAL_CALIBRATION / SEPARATE_SYNTAX_RISK_SIGNALS /
ZERO_ALGORITHM_QUALITY_EVIDENCE`. The two independent T/F/UNKNOWN signals are a
same-name direct Attribute Call signal for introduced internal method names and
a changed-span adjacent AST-identical `Expr(Call)` risk-absence signal. Alpha
is `TRUE / FALSE`, beta is `FALSE / TRUE`, B0 is `UNKNOWN / UNKNOWN`, both
cleaned controls are `TRUE / TRUE`, the branch control is `UNKNOWN / TRUE`, and
the callback control is `UNKNOWN / FALSE`.

Receiver type and callee effects are deliberately unresolved. Same-name-call
`TRUE` does not prove the introduced method is used; adjacent-risk `FALSE` does
not prove a side effect or defect. `UNKNOWN` is not coerced, the diagnostics
remain separate, and both `aggregate_semantic_completeness` and
`aggregate_algorithm_success` are null. Provider, Contract, V3/V4, Protocol,
Decision, quality and benchmark calls are zero. No production source, gate,
R60 or R61 artifact changed. R62 implements no prompt/tool change or feedback,
retry or repair loop. Provider algorithm experiments remained paused; at R62
closeout no R63 was preregistered, authorized or launched.

R63 later completed as the separately
[preregistered](../experiments/v0.4/v0.4-cvrp-r63-c-message-whole-patch-review-pair-preregistration-20260814.md)
and authorized C-message pair. Its
[postrun](../experiments/v0.4/v0.4-cvrp-r63-c-message-whole-patch-review-pair-postrun-20260814.md)
seals `TERMINAL_MATCHED_PAIR_OBSERVATION / BOTH /
NO_IDENTIFIED_MESSAGE_REVIEW_ADVANTAGE /
ZERO_ALGORITHM_QUALITY_EVIDENCE`. The fixed
CONTROL→REVIEW wrapper completed exit `0` in about 55 seconds with H/retry
zero, two terminal provider outcomes, two opaque primary records, two opaque
sidecars and two evaluated arms.

All 13 primary mechanical fields are true for both arms. CONTROL V3/V4 passed
in `615/934` ms and REVIEW in `569/838` ms. Both sidecars are
`UNKNOWN/TRUE`, with aggregate semantic completeness null. Both raw proposals
changed only `local_search.py` and used `exact_replace` on `_two_opt_star` for
nearly the same boundary-delta strategy; REVIEW differs only in depot-assignment
placement/format and used 51 more input tokens. These are descriptive facts.
V3/V4 do not enter `_two_opt_star`: V3 disables embedded VNS. V4 passes `0.01`
seconds, but `_algorithm_time_limit` clamps the scheduler time limit to `0.05`
seconds, equal to its minimum `0.05`-second reserve, so the strict
`remaining_time() > reserve` guard is not met. They therefore do not establish
every cut-pair equivalence, directed-arc correctness or near-EPS behavior. No
canary, formal Protocol, quality solver or Decision ran, and
B0/v1 remains champion. One fixed ordered pair proves neither review benefit
nor ineffectiveness; the seal does not mean the suffix was ineffective or the
model did not review. Provider algorithm experiments remain paused. At R63
closeout, no R64 was preregistered, authorized or launched.

R64 subsequently completed its unique
[provider-free semantic diagnostic](../experiments/v0.4/v0.4-cvrp-r64-provider-free-two-opt-star-semantic-diagnostic-postrun-20260814.md).
The mode-`0700` formal root was created at `2026-08-14T09:41:56Z` and contains
only mode-`0600` `result.json` and `status.json`. Its terminal record is
`TERMINAL_DIAGNOSTIC` with `complete=true` and
`semantic_endpoints_claimed=true`.

Both sealed R63 arms report `cut_delta_equivalence=TRUE`,
`near_eps_decision_equivalence=TRUE`,
`first_improvement_state_equivalence=TRUE`, and
`candidate_route_distance_evaluation_calls=0`. All 27 cut cases and three
near-EPS cases equal their references without exception. The three state
fixtures have candidate/reference accepted-move counts `0/0`, `1/1`, and
`5/5`; complete traces and final partition/load/cost state are equal, every
frozen invariant holds, and no candidate exception occurred. Classification,
`aggregate_semantic_correctness`, and `aggregate_algorithm_success` remain
null, with no cross-arm ranking.

The formal role is
`DURABLE_REPRODUCTION_OF_EXACT_CANDIDATE_CALIBRATED_PROVIDER_FREE_DIAGNOSTIC`,
with `outcome_blind=false`, `independent_confirmation=false`, and claim boundary
`preformal_exact_candidate_outcomes_seen_no_independent_confirmation`. Exact
candidate endpoint values had already been observed in pytest temporary roots.
The nested `preparation_calibration.formal_output_created=false` therefore
describes only that earlier calibration snapshot; it does not mean the current
formal root is absent.

All provider, H/C, canary, Contract, V3/V4, formal solver/Protocol,
algorithm-quality, Decision, benchmark/BKS, production-change, and R63-mutation
counters are zero. R64 is finite-fixture, non-gating, not an independent
confirmation, and supplies no quality or generalization claim. Provider
algorithm experiments remain paused. At R64 closeout, no R65 was
preregistered, authorized or launched.

R65 is now
[preregistered](../experiments/v0.4/v0.4-cvrp-r65-provider-free-r63-alpha-minute-quality-calibration-preregistration-20260814.md)
as an exact-alpha, provider-free minute quality calibration. At final
preparation it remained
`PREPARED_NOT_STARTED / AWAITING_EXPLICIT_SOLVER_EXECUTION_AUTHORIZATION`.
Only sealed R63 `cell_alpha/control_original_message` is selected, by neutral
ordinal-0 tie-break rather than quality. The exact action is one fresh,
cache-disabled B0/alpha seed-101 two-second veto canary followed conditionally
by four P65/E101/X120/X233 seed-73 pairs at per-subject limits
8/12/12/15 seconds and AB/BA/AB/BA order. It permits at most ten solver
subprocesses, 98 subject-seconds, one concurrent subject and a 300-second hard
wall.

Historical R1 already evaluated the same boundary-edge-delta mechanism more
strongly at 8 cases by 4 seeds, with pair `3W/0L/29T`, case `0W/0L/8T` and
median `0 [0,0]`; later R1 B0 observations were mostly cached. R65 does not
pool with or reinterpret R1. It is only an implementation-specific, exposed-
coordinate, lower-bound-style minute calibration, where lower-bound-style is
not a mathematical bound because deadline trajectories are nonmonotone. It is
not held-out, independent or effect evidence. The generic continuation
instruction and consumed R64 authorization did not authorize a solver.
Provider/H/C, Contract, V3/V4,
retry/repair, validation/frozen, Decision, promotion, beta and R66 remain zero.
Any terminal outcome stops R65.

The frozen R65 input contains nine regular non-symlink files and binds the
unchanged preregistration SHA-256
`4905fdfca6b91d6c24d5e8be3eb736060671dad9d468976122e9ee953323f8ac`.
Its directory and launcher are mode `0700`; `run_r65.py` and
`test_run_r65.py` are mode `0600`, as are the other non-launcher files.
Env-injected `launch.sh --preflight-tests` passed 42 tests in 0.87 seconds; an
independent run passed the same 42 in 0.80 seconds.
Outer pytest uses an `env -i` allowlist, with API/proxy/auth sentinels proven
absent. Ruff check and format, `bash -n`, `jq`, and `launch.sh --check` pass.
Fake acquisition proves the pid/acquired marker, `LAUNCHED` return and exit-code
precedence without waiting for formal output. Atomic-rename coverage requires
durable `raw_metrics_ref` and fresh-workspace paths only under the final output,
never a partial staging path. Five manifest science-surface mutation negatives
exact-bind the formal role, research question, estimand, endpoints and claim
boundary that can enter the durable result. Direct fake coverage excludes an
authorized timeout-wrapper ancestor from host self-conflict, binds the exact
predelegated 10-subprocess/98-second ledger and rejects call 11, directly binds
the sealed R63 cell to its score, and captures the actual child Python and six
thread-variable environment. It also persists and re-requires the sealed
production runtime-audit validity endpoint. Direct B0/alpha canary and
SCREENING audit-only failure negatives preserve comparator/candidate precedence
and null aggregates. At preparation close, cache/pyc and the exact formal
output, process-control and socket roots were absent, and no exact candidate or
solver had run. These are preparation facts, not solver or quality evidence.

The user subsequently recorded this exact R65 authorization verbatim:

> 我明确授权执行一次 v04-cvrp-r65-provider-free-r63-alpha-minute-quality-calibration-20260814：以 51f9bbd77f1e93777bbe9c401b8ba05c09a3e819 的 exact B0 为对照，只使用 sealed R63 cell_alpha/control_original_message 候选和 sealed 47fe81ee6e17c04bc805197e2b2ad34e0fff4d14 runtime；先串行运行 B0/alpha 的 seed-101、每个 2 秒 veto canary，通过后仅在 P65/E101/X120/X233、seed 73、每 subject 8/12/12/15 秒、AB/BA/AB/BA、fresh 且 cache disabled 下运行一次四对 SCREENING。最多 10 个 solver subprocess、98 subject-seconds、单并发、300 秒 hard wall；provider/H/C/Contract/V3/V4/retry/repair/validation/frozen/Decision/promotion/beta/R66 均为 0。失败不重试、恢复、替换或追加 seed；无论结果如何 R65 停止。此授权仅覆盖这一 R65。

Launch-only history: the launcher returned `R65_FORMAL_LAUNCHED` after
acquisition at `2026-08-14T12:53:36Z`, with `inner_pid=514140`. At that
launch-only update status was `IN_FLIGHT`, and no outcome was read. The
byte-bound R65
preregistration was not edited and remains SHA-256
`4905fdfca6b91d6c24d5e8be3eb736060671dad9d468976122e9ee953323f8ac`.

R65 is now terminal. The mode-`0700` formal root reached terminal mtime
`2026-08-14T12:54:59.619678635Z`; mode-`0600` `result.json` and `status.json`
have SHA-256 values
`336bbc89fa4bf3463122ae41a18d377a0bd8d372ff09fd2a30eb62fbae589f73`
and `d75d000d4a8dceb2a24b21ecf87aab35df61c001d1df09d69dbd56d6441e7a0c`,
respectively,
and process-control `exit.code` is `0`. All 10 fresh subprocesses and 98
declared subject-seconds completed. B0 then alpha both passed the seed-101
canary at distance 20, feasible, fleet-safe and runtime-audit valid. The
seed-73 AB/BA/AB/BA screen reports exact B0/alpha ties at P65=798, E101=1124,
X120=14250 and X233=20112. Every screen subject is successful, feasible,
fleet-safe and runtime-audit valid; routes also tie `10/10`, `14/14`, `6/6`
and `17/17`. Raw metrics are 4/4 valid with zero failures and zero cache
hits/misses/writes. All 11 durable references resolve under the final output,
with no temporary, partial, symlink or cache path; sealed R63/R64 remain
unchanged.

The complete result is `0W/0L/4T`, signed deltas `[0,0,0,0]`, median
`0 [0,0]`, and zero protected fleet regressions. Only the CI-lower-bound,
loss-rate and fleet criteria pass; win-rate, practical-median and net-score
criteria fail. R65 seals
`VALID_COMPLETE_EXPOSED_COORDINATE_MINUTE_CALIBRATION /
EXPLORATORY_SCREEN_NO_SIGNAL / ORDINARY_MINUTE_RULE_NOT_MET /
NO_GO_EFFECT_INFERENCE / NO_MORE_PROVIDER_FREE / NO_R66`. Decision and
promotion are null. Provider/H/C/Contract/V3/V4/validation/frozen/Decision/
promotion/beta/R66 remain zero. This is no effect inference, does not pool with
R1, and authorizes no extension or R66. Alpha-minus-B0 elapsed deltas are
`[-80,-24,-4,-427]` ms, median `-52` ms, with approximate median ratio
`0.992741`; these are association-only and support no causal speed claim.

R66 was
[preregistered](../experiments/v0.4/v0.4-cvrp-r66-h-only-mechanism-frontier-probe-preregistration-20260814.md)
as a single H-only mechanism-frontier probe with preparation status
`PREPARED_AUTHORIZED_NOT_STARTED`. This is a separate, narrowly authorized
provider observation, not an extension or reinterpretation of R65. It binds
the exact ordered eleven fresh-B0 CVRP source values at subject commit
`51f9bbd77f1e93777bbe9c401b8ba05c09a3e819` and the clean production H
carrier/tool at `47fe81ee6e17c04bc805197e2b2ad34e0fff4d14`. Production carries the
eleven values only under `champion_operators_code`; the typed question payload
has no `research_prior`, and the context has no experiment history, last
research rejection, branch-current code or ordinary outcome-rich
cross-campaign prior. It contains no historical raw H/C response, candidate or
result. It does contain a neutral E01–E10 mechanism-exclusion ledger derived
from prior evidence, so the observation is explicitly prior-informed,
non-blind and not independent.

The exact production H system blocks and base prompt remain unchanged. The
production context-bound H tool is frozen with the sole allowed
`change_locus=solver_design` and no experiment-owned schema change. The exact
discovery question is carried in
`research_question.current_question`; the frozen ledger block is appended in
E01→E10 order, one row per line, with no trailing prose and no explicit
`prompt_cache_key`. The request uses the local Codex proxy at
`http://127.0.0.1:8080`, `gpt-5.6-terra`, at most one H call, a 180-second
provider timeout, retry zero and a 300-second outer wall. Its only mechanical
fields are provider completion, exactly one expected named tool, argument
availability, valid argument JSON and typed hypothesis-schema validity.
Scientific classification, algorithm-quality evidence, Decision and promotion
remain null.

The user's final exact raw authorization is recorded verbatim:

> 我明确授权执行一次 v04-cvrp-r66-h-only-mechanism-frontier-probe-20260814：将 commit 51f9bbd77f1e93777bbe9c401b8ba05c09a3e819 的 fresh-B0 CVRP problem-owned 11-source 源码派生上下文（local_search.py、baseline_algorithm.py、acceptance.py、config.py、construction.py、destroy_repair.py、route_first_heuristic.py、route_first_improvement.py、route_first_seeding.py、scheduler.py、state.py），连同冻结的研究问题、E01–E10 机制排除表以及 clean 47fe81ee6e17c04bc805197e2b2ad34e0fff4d14 production H system/tool，通过本机 Codex proxy http://127.0.0.1:8080 发送给 gpt-5.6-terra。最多执行 1 次 H、180 秒、retry 0；不得发送历史 H/C response、候选或结果；C、patch、solver、canary、Protocol、Decision、promotion 和 R67 均为 0。此授权仅覆盖这一 R66 H-only 调用。

That statement is resolved only to provider-free preparation plus one
immediate H-only Terra call after preflight. C, patch, materialization,
Contract/ContractGate, V3/V4, solver, canary, Protocol, quality/formal
evaluation, Decision, promotion, repair, retry/resume/substitution and R67 are
all zero. The ledger is neither a novelty gate nor a permanent blacklist;
human overlap review is descriptive only. A terminal H cannot automatically
launch C or R67 or claim feasibility, correctness, executability, quality,
runtime improvement, generalization or S6 progress. No R66 provider call or
downstream action had started at that prepared-state update.

The authorized R66 action was then invoked once after the UTC date changed to
2026-08-15. The outer provider-free preflight stopped before inner-process
acquisition, proxy/model preflight or any provider request. Independent
reconstruction found one and only one canonical static-context difference:

```text
/problem_measurement_diagnostics/measurement_readiness/calibration_age_days
frozen: 64
production rebuild: 65
```

The date-sensitive calibration age advanced between preparation and launch.
The fail-closed check therefore produced terminal `PREP_INVALID` with error
type `OuterPreflightFailure`; no payload was sent and no H observation exists.
The sole mode-`0700` process-control root contains mode-`0600`
`outer_failure.json` and `exit.code=1`. It records H attempts/provider calls
zero, no provider terminal response, `mechanically_complete=false`, and every
downstream counter zero. The formal output root, socket/session, inner PID and
acquisition marker are absent. The full durable record is in the
[R66 postrun](../experiments/v0.4/v0.4-cvrp-r66-h-only-mechanism-frontier-probe-postrun-20260815.md).
Under the frozen terminal policy there is no repair, retry, resume,
substitution, same-label relaunch, C, solver action or R67. This is a
preparation-authority failure, not model, mechanism or algorithm-quality
evidence.

That original terminal history remains sealed. The user then gave this exact
instruction after reviewing the one-field diagnosis:

> 是的，那你直接去掉，做好修复，然后继续实验

The append-only recovery amendment resolves it narrowly to the separately
rooted R66 subtype
`v04-cvrp-r66-h-only-mechanism-frontier-probe-20260814-recovery1`, not R67.
Its manifest exact-binds three distinct fields: historical broad
`authorization_text`, full eleven-source `source_send_authorization_text`, and
the new `recovery_authorization_text`. The broad instruction does not replace
explicit disclosure authority, while the disclosure authority does not by
itself amend the original terminal stop.
It replaces only live-current-date canonical reconstruction with manifest
authority `static_context_as_of_date="2026-08-14"` and a typed date parsed from
the same exact string. That deterministic rebuild must reproduce frozen
`calibration_age_days=64`. Every other source,
runtime, prompt, tool, question, ledger, schema, request-envelope and fresh-
root check remains unchanged.

Recovery1 uses fresh input, output, process-control and socket roots recorded
in the preregistration amendment. The original consumed root is not reused or
overwritten. At launch freeze its status was
`RECOVERY1_PREPARED_AUTHORIZED_NOT_STARTED`. The historical provider-free
preparation input-tree/manifest SHA-256 values are
`89e7994a05a0663f3bc95a9c2453ca28328159608a2cfc3749222f6747138aaf` and
`ba196da15b7a2d64b8b8918e2a56e6143846aba35a289c5a7e760f525d3fd4f1`.
The tree has 4,191 files and 72,632,636 bytes. The 97,863-byte public-call
payload receipt over `{prompt, tool, system_blocks, model}` has SHA-256
`573d445126f41acab255d6f9bfa93d9aff43851fbc6458bca3cb0b9d9f5b470a`;
it is not SDK kwargs. The 97,866-byte canonical counterfactual OpenAI-create
kwargs receipt has SHA-256
`0dc1c5b4da1283915fcceb2b3b83e141cb70f1be87b589dcd7ff5d322947b0e0`
and exact keys `messages`, `model`, `timeout`, `tool_choice`, `tools`, with
float timeout `180.0` and `prompt_cache_key` absent. Recovery1 failed before
kwargs evaluation, so this is a reconstruction receipt, not an emitted
request.
All 36 provider-free tests pass in 11.91 seconds together with runner/style/
shell/JSON checks, with fresh output/control/socket roots absent. Because the
original H/provider count is zero, original plus recovery1 retain a combined
maximum of one H call.
Provider retry, C, patch,
materialization, Contract, V3/V4, solver, canary, Protocol, quality/formal
evaluation, Decision, promotion, resume, substitution and R67 remain zero.
The then-frozen policy authorized no recovery2 or automatic downstream action.

Recovery1 subsequently acquired at `2026-08-15T03:23:06Z`, inner PID
`591276`; at that launch-only boundary it was `IN_FLIGHT` and outcome-unread.
It later published a unique mode-`0700` output root and exited `3`. The durable
result/status emit `TERMINAL_HYPOTHESIS_PROVIDER_FAILURE`, logical
`h_attempts=1` and `hypothesis_provider_calls=1`, no provider terminal
response, `mechanically_complete=false`, exact error
`API error: No module named 'jiter'`, and latency 637 ms. There is no raw
response, response envelope, usage, tool argument or H observation. Every
downstream and R67 counter is zero.

Read-only causal audit preserves those emitted fields but classifies the event
as `RUN_INVALID_LOCAL_INFRA / MISSING_JITER_BEFORE_REQUEST`. The exact minimal
formal environment lacked `jiter`, and the OpenAI SDK's lazy `client.chat`
resource failed while importing it before the model request could reach HTTP.
Audited outbound model/H requests and provider-visible research-payload sends
are therefore both zero. Control-plane proxy liveness/model checks sent no
research payload. This is not provider, model-format, mechanism or algorithm
evidence.

The output result/status SHA-256 values are
`a781f1fb8444af8854536ff601416e0bef126c2d1020dff36b611b6fc0e75118`
and `af1608d8f0a530da153b359a99e2a7a8fbae19536643dd1a61b647fde6e7a5cb`.
The control root retains acquisition markers and `exit.code=3`; the inner PID
is gone. The recovery1 socket remains stale at mode `0600`. Full facts are in
the
[recovery1 postrun](../experiments/v0.4/v0.4-cvrp-r66-h-only-mechanism-frontier-probe-recovery1-postrun-20260815.md).

Recovery2 is provider-free prepared under a new R66 identity. Its only new
correction vendors exact `jiter==0.13.0` as nine files under
`vendor/python312`, retains `PYTHONNOUSERSITE=1`, and exercises the exact lazy
chat dependency seam without HTTP. Its status is
`RECOVERY2_PREPARED_AWAITING_EXPLICIT_AUTHORIZATION`. Recovery1's logical call
counter remains one even though its audited HTTP count is zero. The broad,
full source-send and exact recovery1 authorization fields remain preserved;
new `recovery2_source_send_authorization_text` is null. No earlier field
authorizes recovery2; it must not launch until the user explicitly authorizes
the new fresh roots and one-H envelope and overrides the prior no-recovery2
stop for this one action. C, solver, Decision, promotion and R67 remain zero.

The frozen recovery2 provider-free input-tree receipt covers 4,200 files and
73,523,973 bytes, using sorted
`relative_path\0file_sha256\0size\n` records, with SHA-256
`f8e82201700cbfebea9ba26f5bfeb0d30f5ee694824722ab3a9fcdf861a050d5`.
The 14,315-byte manifest SHA-256 is
`e056afcfe6e279bbc902c3b17b8e512eb466c9a28ae4e3e5ea4a4bf7e6fa8dc9`.
Forty-seven tests passed in 12.15 seconds, with runner check, Ruff check/format,
`bash -n` and `jq` green. The
formal preauthorization path exits `2`, and output, control and socket roots
remain absent; recursive cache/symlink exclusion passes. These are
provider-free preparation facts, not launch or H evidence.

The R3 run also exposed an operator-side validity problem: pytest
ran concurrently on the same two-vCPU/one-physical-core host while the
deadline-driven solver was evaluating several pairs. All CPU-heavy repository
validation was stopped immediately. Because every overlap boundary cannot be
reconstructed exactly, the root is conservatively
`OPERATOR_LOAD_CONTAMINATED_FOR_STRICT_PROMOTION_CLAIM`; no selected pair is
silently deleted or retried. The outcome-blind
[recovery preregistration](../experiments/v0.4/v0.4-cvrp-v3-r3-operator-load-recovery-preregistration-20260809.md)
was written before the quality expansion became terminal. R3 remains useful
for research behavior and candidate discovery. Its later reboot left no
Protocol promotion, so there is no eligible source or promoted snapshot pair
for that conditional clean recovery. The recovery preregistration is not
launched and the partial validation is not used to select a candidate.

An independent outcome-blind experiment-design audit also found a prospective
measurement gap that does not reinterpret Warehouse acceptance or incomplete
R3. The generic formal loop runs champion before candidate, enables champion
result caching by default and reruns the cumulative matrix on expansion. Raw
pairs retain deltas and runtime/cache facts but not both absolute objective
vectors, subject order or feasibility. Consequently
objective headroom, order/load effects and case-versus-seed attribution are
partly `UNIDENTIFIABLE`. The minimal correction landed default-off at
`c32f5b8a`: fresh cache-off subjects, deterministic AB/BA counterbalancing and
bounded block/case/seed/order/objective/feasibility/timing/failure raw facts in
the existing Protocol. The four production files grew by net 100 lines and 46
focused/adjacent tests plus independent review passed; the default Protocol,
raw schema and Decision path remain unchanged. The now-frozen
[R45 diagnosis R1](../experiments/v0.4/v0.4-cvrp-r3-ordinary-lineage-r45-diagnosis-preregistration-20260810.md)
used the frozen 37-block design over six exact candidates, including an
independent B0 A/A matched-MDE block and fixed `0.5x/1x/2x` budgets. Its process
disappeared during the first block. Terminal structure is `complete=false`,
zero of 37 accepted blocks, `last=null`, one incomplete 46/96 raw file with
zero recorded subject failures, no analysis, and no remaining driver or solver.
No W/L/T, effect, gate or objective was read. R1 is sealed
`RUN_INVALID_INFRA / ZERO_ACCEPTED_BLOCKS / NO_ADMISSIBLE_ANALYSIS`; its cause
is `PROCESS_DISAPPEARANCE_CAUSE_UNIDENTIFIABLE` and no partial pair is reused.
The [R2 replacement](../experiments/v0.4/v0.4-cvrp-r3-ordinary-lineage-r45-diagnosis-r2-replacement-preregistration-20260810.md)
terminated at `2026-08-10 12:15:10 UTC` with exit `2`. Its first MDE raw was
complete at 96/96 attempted and valid pairs with zero subject failures, but the
one-off driver rejected the legitimate auxiliary `routes` field before atomic
acceptance. All 192 A/B objective mappings contained the two declared finite
numeric metrics plus only `routes`; every other structural predicate passed.
Status therefore remained zero of 37 accepted blocks with `last_block=null`,
and no analysis exists. No W/L/T, effect, gate, ranking or objective value was
read. R2 is sealed
`RUN_INVALID_EXPERIMENT_DRIVER / ZERO_ACCEPTED_BLOCKS /
NO_ADMISSIBLE_ANALYSIS` and is not an algorithm negative.
The [R3 replacement](../experiments/v0.4/v0.4-cvrp-r3-ordinary-lineage-r45-diagnosis-r3-driver-replacement-preregistration-20260810.md)
launched once after explicit confirmation at `2026-08-10 15:21:30 UTC` and
completed with ordinary-user launcher exit `0`. Terminal status is
`complete=true`, 37/37 accepted atomic blocks and 1,056 unique fresh AB/BA pair
rows, with `last_block={label: 2x, ordinal: 5}`. The terminal analysis is
complete, and no R1 or R2 pair was copied, combined or reused.

The independent B0 A/A block gives `MDE@80%=2.0` only for the frozen `12x8`,
`1x`, case-median homogeneous-additive estimand. Across the six exact complete
`12x8` immediate-base comparisons, candidate median signs are 0 positive, 5
zero and 1 negative. Added-case and joint contrasts improve no candidate
median; seed and budget responses are mixed. Candidate five is a clear exact
algorithm negative, while the elapsed-budget-SA-related sources retain only
descriptive scoped/`2x` opportunity. Case-by-seed interaction and
whole-budget-arm machine drift remain `UNIDENTIFIABLE`. The
[postrun](../experiments/v0.4/v0.4-cvrp-r3-ordinary-lineage-r45-diagnosis-r3-postrun-20260811.md)
therefore seals R50
`VALID_COMPLETE_PROVIDER_FREE_DIAGNOSIS / DESCRIPTIVE_COHORT_ONLY /
NO_BROAD_IMMEDIATE_BASE_ADVANCE`. It selects, recovers and promotes no candidate
and changes no Scion core gate, Protocol, Safe Feature or Decision.

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

After the production research-design corrections were integrated, a historical
complete-suite checkpoint passed `2011 passed, 1 skipped` in 639.18 seconds.
The later exact clean-source `2081 passed, 1 skipped` result recorded above is
the latest completed full-suite checkpoint before the currently active
experiment work; the 1949, 1964, 1965, 1988 and 2011 results remain historical
checkpoints.

## Known residuals

1. CVRP H input historically grew about 20.7k -> 47.3k -> 73.7k -> 100.2k
   tokens across four rounds; Warehouse production similarly reached 83.8k by
   its final H. R52 now keeps complete raw lineage and research evidence while
   removing host/control wrappers from the provider projection. C receives one
   ordinary approved-target/path/content/API context, with no legacy source
   ledger, owner/provenance/view metadata or self-rehashing validation. This is
   semantic projection rather than token-triggered truncation, top-k selection,
   an opaque summary or a gate. Future prompt growth still needs observation,
   but no further compression is justified by size alone.
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
output roots remain unlaunched and lower-priority than the CVRP R45/cohort
diagnosis. One
small accounting correction remains before execution: current canary skips a
champion solver or blocking-audit failure without retaining that fact and can
return `champion_status=not_applicable`. Seven attempt/failure/completeness
fields plus a heldout execution-completeness check will distinguish incomplete
comparison evidence from the existing candidate safety veto without changing
canary pass/veto, Protocol or Decision semantics.
CVRP has no Protocol-complete promotion. R1 is sealed at 5/8 and R2 at 10/12;
both retain valid partial science but neither candidate path reached validation
or frozen holdout. R2's elapsed-budget SA is the current strongest lead. R3's
code, context, measurement rule and disjoint populations are fixed and fully
regressed and its provider-free null calibration completed acceptably. Its
fresh 16-stage campaign from exact runtime `76f3e976` is sealed
`RUN_INVALID_INFRA / VALID_PARTIAL_SCIENCE`: the host rebooted with formal
validation incomplete, durable stage counts 10/0/0 for
screening/validation/frozen, and champion B0/v1. Its terminal quality pass is
retained, but the unadjudicated partial validation is neither a pass nor an algorithm
negative. With no Protocol promotion, R3 supplies no clean-recovery candidate
and the promotion-recovery replay is not launched. Closure still requires a
fresh clean screening -> validation -> frozen promotion, an independent B0
comparison and the S6 cross-problem/full-regression record.
The terminal outcome-blind ordinary-lineage reconstruction is now frozen. Full
primary plus ordered `additional_changes` replay produced six chronological
unique Verification-passed candidates with their exact immediate bases. All
three reconstructed branch heads matched their durable workspaces byte-for-byte
across 53 ordinary Python files, one research rejection was omitted, and an
independent review passed. Earlier r1/r2 materializer differences came from
that offline analyzer omitting `additional_changes`, not from Scion runtime
drift. The cohort remains experiment evidence, not a restored candidate index,
identity or replay authority.
The preregistered 37-block R45 diagnosis R1 is now sealed after unexplained
process disappearance with zero accepted blocks and no admissible analysis.
Its output root is unchanged, it is not resumed, and its partial first-block
pairs are not copied or combined. R2 launched once through an ordinary-user
tmux seam, completed 96/96 valid MDE pairs, then its one-off driver rejected
the auxiliary `routes` field before accepting the block. R2 is sealed with zero
accepted blocks and no admissible analysis; no scientific outcome was read.
R3 was separately preregistered, launched once after explicit confirmation and
completed exit `0` with all 37 blocks, 1,056 unique pairs and terminal analysis.
Its exact-roster MDE is `2.0`; the six full immediate-base medians are five zero
and one negative. R50 is complete provider-free descriptive diagnosis, not a
promotion or recovery result. The complete one-off driver/test source remains
experiment-owned and is not committed into Scion. H-context A/B is not
triggered by the seven audited H calls. The C-expression A/B is terminal under
R51: retain exact and close strict diff. R52 then closes the provider/source
subtraction by net deletion while keeping raw trace completeness and runtime
source binding. R53 completes the clean minute one-step with a stable V3
research lifecycle but a negative exact screen: `0W/1L/3T`, median
`0 [-16,0]`, no fleet regression and no promotion. The remaining task boundary
is solver evidence: CVRP still needs a fresh clean screening -> validation ->
frozen promotion and independent B0 retention. R53 cannot itself close this
boundary. R54 is also terminal: its feedback-conditioned H was strong, but C
left three calls to a removed `cool()` method; formal evidence contains three
valid ties and one candidate runtime-audit failure. Decision abandoned the
candidate, and a separate post-Decision context-persistence `ValueError`
caused wrapper exit `1`. B0/v1 remains champion and no R54 objective from the
failed P row is used as delta/W/L/T evidence. R55 prospectively fixes the
feedback-cardinality persistence defect and makes CVRP V3/V4 execute real
subsecond problem-owned consistency tests; an exact provider-free R54 patch
replay fails all three newly covered recovery paths. This is corrective test
evidence only: it reruns no provider or Protocol/formal experiment, adds no
candidate gate, and by itself authorizes no next H/C. R56 then completed one
H/C and a passing Contract on clean `acdc80ba`, after which the new V3 fixtures
rejected three residual calls to the removed `cool()` API in 519 ms.
Independent source audit found a fourth latent residual call. The wrapper
exited `0`; V4, canary, formal Protocol and Decision were not reached, so there
is zero solver-quality evidence and B0/v1 remains champion. R56 is sealed
`VALID_TERMINAL_RESEARCH_PROCESS_OBSERVATION / VERIFICATION_LIGHT_REJECTED /
ZERO_PROTOCOL_EVIDENCE / NO_DECISION / NO_PROMOTION`. R57 is not an algorithm
experiment; its evidence label records only the provider-free expression
correction at `f537fed5`. R58 was separately preregistered from clean `42535efc`
as one seed-29 minute observation with fresh subject executions. Exact
authorization was later recorded and the one launcher invocation exited `0`.
R58 is sealed at Verification with zero canary, Protocol or Decision evidence;
B0/v1 remains champion and provider algorithm experiments pause for
provider-free C expression-selection work. R59 records the provider-free
typed-tool presentation correction at `47fe81ee`; its frozen replay and
transport/regression tests add no algorithm evidence. Provider experiments
remain paused. R60 then completed one C-only OLD-then-NEW matched pair over the
frozen R58 turn. Both arms were fully executable and both selected the five-site
line expression, so it is sealed `BOTH / BOTH_LINE_SELECTION /
NO_IDENTIFIED_PRESENTATION_ADVANTAGE / ZERO_ALGORITHM_QUALITY_EVIDENCE`.
Post-hoc source observations keep both proposals out of algorithm testing; no
R61 had been preregistered, authorized or launched at R60 closeout. R61 later
completed provider-free over those sealed workspaces: OLD passes deadline
wiring but fails `2/1` weight accounting; NEW fails deadline wiring at constant
temperature `5.0` but passes `1/1` accounting. The endpoints stay separate,
`aggregate_algorithm_success` is null, and there is zero provider, formal or
quality evidence. Provider pause remains; no R62 is preregistered, authorized
or launched.
R62 later completed provider-free as a static, post-hoc R60-informed sidecar
calibration. Alpha's two separate syntax signals are `TRUE/FALSE`, beta's are
`FALSE/TRUE`, and both aggregate fields are null. It adds no provider, solver,
quality, gate, prompt or repair-loop evidence. At R62 closeout, provider pause
remained and no R63 was preregistered, authorized or launched.

R63 later completed the fixed authorized CONTROL→REVIEW C-message pair. Both
arms passed all 13 mechanical fields, yielding `BOTH /
NO_IDENTIFIED_MESSAGE_REVIEW_ADVANTAGE`; both descriptive sidecars are
`UNKNOWN/TRUE` with null aggregate. V3/V4 do not enter `_two_opt_star`, and the
near-matching one-file boundary-delta proposals have no formal or
algorithm-quality evidence. The result neither supports nor refutes review
benefit and does not establish that the suffix was ineffective or the model
did not review. At R63 closeout, no R64 was preregistered, authorized or
launched.

R64 subsequently published one complete provider-free `TERMINAL_DIAGNOSTIC`.
Both exact sealed R63 candidates durably reproduce all three separate semantic
endpoints as `TRUE`, with distance-evaluation calls `0`; all 27 cut, three
near-EPS, and three state fixtures equal their references without exception.
Classification and both aggregate fields remain null. Because preparation had
already observed the exact candidate vectors, the formal record is durable
reproduction with `outcome_blind=false` and `independent_confirmation=false`,
not independent evidence. R64 is finite-fixture and non-gating, leaves R63
unchanged, and produces no provider, solver-quality, Decision or R65 evidence.

R65 subsequently completed the exact authorized provider-free alpha minute
calibration. All 10 fresh subprocesses and 98 declared subject-seconds
completed. B0 and alpha tied at distance 20 on the seed-101 canary and tied on
all seed-73 screen cases: P65=798, E101=1124, X120=14250 and X233=20112. Every
subject was successful, feasible, runtime-audit valid and fleet-safe. The
complete result is `0W/0L/4T`, deltas `[0,0,0,0]`, median `0 [0,0]`, and zero
protected regressions. It seals
`VALID_COMPLETE_EXPOSED_COORDINATE_MINUTE_CALIBRATION /
EXPLORATORY_SCREEN_NO_SIGNAL / ORDINARY_MINUTE_RULE_NOT_MET /
NO_GO_EFFECT_INFERENCE / NO_MORE_PROVIDER_FREE / NO_R66`. Decision and
promotion are null; provider/H/C/Contract/V3/V4/validation/frozen/Decision/
promotion/beta/R66 are zero. The result is neither effect evidence nor
independent confirmation, does not pool with R1, and authorizes no extension
or R66.

A new, separate authorization covered the original R66 H-only action. Its
fail-closed outer preflight found the single UTC-date-derived canonical drift
`calibration_age_days: 64 -> 65` before inner acquisition or provider
disclosure. The original remains terminal `PREP_INVALID /
OuterPreflightFailure / NO_PROVIDER_REQUEST / NO_H_OBSERVATION`; H/provider and
all downstream counters are zero, and no formal output exists. This is no
novelty, quality or algorithm evidence and cannot advance S6.

The user subsequently authorized removal of that erroneous date gate, repair
and continuation. R66 recovery1 used the sole fixed-`as_of` correction,
preserving frozen `calibration_age_days=64` and every other authority check.
It then acquired, but the formal environment lacked `jiter`. Durable artifacts
emit provider failure and logical H attempt/call `1/1`; causal audit seals
`RUN_INVALID_LOCAL_INFRA / MISSING_JITER_BEFORE_REQUEST` with zero actual
outbound model requests, research-payload sends and H observations. Provider retry, C,
solver, Protocol, Decision, promotion and R67 are zero.

A fresh R66 recovery2 is provider-free prepared with exact vendored
`jiter==0.13.0`, but is
`RECOVERY2_PREPARED_AWAITING_EXPLICIT_AUTHORIZATION`. The prior recovery1
instruction does not authorize it; no recovery2 provider call may start
without a new explicit user authorization.

All diagnosis results remain excluded from Decision and cannot reinterpret the
interrupted provider campaign's partial validation.
Deployment, packaging, builds, root/systemd and self-proof infrastructure are
neither prerequisites nor completion claims.
