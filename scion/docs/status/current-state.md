# Scion v0.4 Current State

*Last updated: 2026-08-09*

Read `TASK.md` first. `design/scion-architecture-v3.md` is the sole architecture
authority. `design/scion-architecture-v3-v0.4-direct-runtime-addendum.md` only
describes the current lightweight implementation and cannot override V3.

## Current objective

The active branch is `codex/v04-production-cvrp-research`. The prior
`codex/v04-solver-improvement-research` stage was committed through
`30726a52` and fast-forwarded into `v0.4-dev`; this branch continues from that
accepted research checkpoint.

The active completion target is retained solver improvement on both Warehouse
and CVRP/VRP. Warehouse has confirmed retained synthetic continuity and now
needs the separate production-transfer rung. CVRP must still produce a real
algorithmic promotion; valid negative observations alone do not close
`TASK.md`.

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
   current runtime admits at most three active branches; this must remain a
   lightweight V3 scheduler and must not reintroduce object authority, signed
   identity, lease, or closure machinery.

## Closure status

The prior lightweight-runtime milestone is accepted at `4d637959`; the active
`TASK.md` is not closed. Warehouse R8 completed 36/36 stages, reached synthetic
champion v3 through two exact promotions in one campaign, and retained both
promotion steps plus the cumulative v3-v1 gain on 108/108 independently
declared held-out pairs. Synthetic Warehouse continuity is
`CONTINUOUS_OPTIMIZATION_CONFIRMED`; the production-transfer rung remains.
The production 12-stage shakedown is a valid funnel with no promotion and,
after the completed prospective shared research-design corrections, authorizes
a fresh prod-1.2 24-stage rung. CVRP has no Protocol-complete promotion. Closure
still requires Warehouse production transfer, one CVRP screening -> validation
-> frozen promotion, and an independent B0 comparison.
Deployment, packaging, builds, root/systemd and self-proof infrastructure are
neither prerequisites nor completion claims.
