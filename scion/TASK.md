# Scion v0.4 Solver-Improvement Research Task

*Working branch: `codex/v04-solver-improvement-research`*

*Accepted runtime baseline: `4d637959`*

*Last updated: 2026-08-08*

This is the active task source. `design/scion-architecture-v3.md` is the
sole architecture authority. The direct-runtime addendum may explain an
implementation choice, but it may not reverse a V3 research boundary.
`docs/status/current-state.md` records accepted evidence; detailed chronology
belongs in experiment reports.

## Objective

The previous stage proved that the lightweight direct-V3 runtime can produce
valid Warehouse and CVRP research observations. It did **not** prove solver
improvement: both champions remained at v1. This stage is complete only when
Scion demonstrates retained algorithmic improvement, not merely valid negative
research.

The required end state is:

1. **Warehouse continuity:** one fresh, uninterrupted campaign produces at
   least two Protocol-complete structural promotions (`v1 -> v2 -> v3` or
   later), and the final champion independently beats both v1 and its immediate
   predecessor on the declared held-out evidence.
2. **Warehouse transfer:** production-style Warehouse obtains at least one
   independently supported promotion, or a pre-registered matched experiment
   establishes that the remaining limitation is production headroom/noise
   rather than framework continuity. Multi-promotion is not required on
   production because v0.3 never established it there.
3. **CVRP improvement:** one exact candidate passes screening, validation and
   complete frozen holdout, receives deterministic `PROMOTE`, and independently
   improves the original B0 champion without feasibility or fleet regression.

If a finite experimental rung is negative, record the conclusion and redesign
the next rung. Do not relabel a scientifically valid negative result as task
completion.

## V3 non-negotiable boundary

The active path remains:

```text
complete safe problem facts + complete current branch source + prior safe evidence
  -> one structured Hypothesis call
  -> structural Hypothesis Contract
  -> one approved-H-bound Code call
  -> structural Patch Contract
  -> isolated Workspace
  -> executable Verification
  -> problem-owned paired Protocol
  -> Safe Features
  -> deterministic Decision
  -> exact stage reuse, branch iteration, or promotion
```

- LLM output is tainted proposal material. It never selects Protocol outcomes,
  Decision actions, cases, seeds, or promotion.
- Contract protects schema, approved-H binding, editable/frozen paths, public
  interface, import resolution, injected randomness, and dangerous host
  capabilities. It must not grade algorithm taste, patch style, novelty,
  activation, or expected performance.
- Verification owns import, execution, feasibility, objective semantics,
  determinism, state isolation, and declared behavioral invariants.
- Protocol owns paired comparisons and statistical gates. Decision consumes
  only typed Safe Features.
- Exact source, case/seed pairing, and stage reuse provide scientific
  determinism. Digests may compare content but confer no authority and create
  no lifecycle.
- A branch is one iterative research direction. Per V3 §11.2, a candidate that
  passes Verification and completes screening remains the branch's current
  code for the next same-branch H, even when screening does not promote it.
  Verification failure returns to the last clean branch source; a branch that
  has never verified code starts from champion.
- Promotion still requires the unchanged screening -> validation -> frozen
  Protocol. A provisional branch head is never a champion.

## Explicitly out of scope

Do not spend implementation, review, experiment, or root time on:

- distribution, deployment, installation, packaging, wheels, reproducible
  builds, release artifacts, systemd, D-Bus, cgroups, or `StartUnit`;
- root-owned source acceptance, Git mirrors, source signing, review closures,
  loaded-manager acceptance, or `/var/lib/scion` receipts;
- object identities, capabilities, leases, issuance/claim/spend flows,
  registration, nonce ledgers, owner authorities, or repeated
  intent/commit/closure self-proof;
- duplicate hashes, hash chains, or reopen proofs for facts already present in
  ordinary branch/source/evidence state;
- provider retry, Scion token/file/session budgets, truncation, top-k context,
  summary substitution, forced mechanisms, forced surfaces/actions/targets,
  novelty gates, or host-authored algorithm-quality gates;
- tuning Protocol thresholds, cases, seeds, or time limits after observing a
  candidate result.

Historical deployment and authority prototypes remain historical evidence.
They do not block this task and cannot satisfy it.

## Evidence already accepted

### Previous lightweight V3 stage

- Baseline commit `4d637959` passed the complete suite:
  `1946 passed, 1 skipped, 0 failed`, plus compileall, focused Ruff/format and
  diff checks.
- Warehouse 3R produced 44/44 valid pairs; CVRP 4R produced 128/128 valid
  pairs. Every candidate crossed Contract, Verification and real Protocol.
- Both experiments remained at champion v1. They establish runtime validity,
  not retained improvement.

### Warehouse historical control

- v0.3 synthetic Warehouse really did promote: 6/6 campaigns promoted, with
  10 structural promotions. The strongest campaign promoted at rounds
  8/19/24/41 and reached v5; independent frozen replay beat v1 on all 12/12
  pairs for each final champion.
- v0.3 production was much weaker: corrected Sonnet runs produced one
  promotion per campaign; GPT-mini produced none. Therefore synthetic
  multi-promotion and production single-promotion are separate claims.
- Current 3R production evidence is not a regression comparison. Its third
  candidate reached 3W/0L/3T, median cost improvement +950 and CI [0, 10025],
  then stopped in `EXPLORE_EXPAND` with exact candidate reuse queued. The later
  1R run was a fresh root and did not continue that candidate.

### CVRP historical control

- Repeated successor work has already rejected or failed to resolve segment
  exchange, broad cross-exchange, destroy-size, lookahead repair, seed
  selection, route-pair overlap, double bridge, generic VNS allocation, and
  several pool/recombination variants. A new campaign currently sees little of
  this cross-campaign scientific history and can repeat an old weak direction.
- The strongest unresolved line is bounded SWAP*: historical screening and
  validation were positive, and frozen observations were descriptively
  positive, but frozen evidence was incomplete because champion runs timed
  out. The cumulative implementation also starved ALNS on Tai cases, so it is
  not promotable as-is.
- The current B0 solver spends most search time in embedded VNS. Pure ALNS and
  globally disabling embedded VNS are both known regressions. The useful
  question is mechanism-level allocation, not a global VNS switch.

## Root-cause register

| ID | Status | Finding | Consequence |
|---|---|---|---|
| R1 | resolved scientific negative | Warehouse 3R ended with an exact candidate queued for screening expansion. Exact eval-only replay passed expanded screening but timed out on 11/15 validation pairs. | Do not promote or tune around this candidate; proceed to a fresh long-horizon synthetic campaign. |
| R2 | proven | v0.3 synthetic campaigns ran 25-66 rounds; first promotion appeared at rounds 4-19. | A 3R campaign cannot test continuous promotion. |
| R3 | proven | Current production Warehouse has near-saturated split objective and noisy cost effects; v0.3 multi-promotion used high-headroom synthetic cases. | Use synthetic recovery and production transfer as different controls. |
| R4 | proven baseline deviation; corrected on current branch; causal effect unproven | The accepted baseline mapped screening `fail` to clean-parent rejection, contrary to V3 §11.2. | Keep the lightweight provisional branch head and test it without changing promotion gates. |
| R5 | proven context gap | Warehouse H context omits solver mechanics such as pool size, iteration/stagnation limits, weights and registration semantics. | Add transparent problem-owned mechanics, not a gate. |
| R6 | observed attribution limit | Create-new Warehouse operators alter both mechanism and pool allocation; direct invocation/adoption is not visible. | Use minimal problem-owned counters only for analysis; never Decision. |
| R7 | proven | CVRP candidates often combine an algorithm idea with broad rewrites or large runtime cost. | Test one mechanism and preserve unrelated source before formal scale-up. |
| R8 | proven | Several CVRP changes were inactive or activated too late; others consumed ALNS opportunity. | Run a small mechanism assay before expensive formal screening. |
| R9 | proven | CVRP campaigns repeat known failures because accepted cross-campaign conclusions are absent from H context. | Add a short problem-owned research prior, with no target prescription. |
| R10 | proven | Repeated pair trees make later prompts grow sharply while adding little new information. | Use fresh one-candidate lines now; later allow only reversible lossless factoring. |

## Modular execution plan

### S0 - Preserve and pre-register

- [x] Commit the completed lightweight V3 runtime as `4d637959`.
- [x] Fast-forward `v0.4-dev` to that commit while preserving unrelated user
  worktree changes and the named overlap stash.
- [x] Create `codex/v04-solver-improvement-research`.
- [x] Independently review v0.3 Warehouse promotions, current Warehouse
  blockers, and historical/current CVRP evidence.
- [ ] Record exact experiment inputs, campaign root, model
  (`gpt-5.6-terra`), local Codex proxy, case/seed manifests, time limits and
  stop conditions before every new run.

### S1 - Finish the truncated Warehouse candidate

- [x] Materialize the exact Warehouse 3R round-3 MergeVehicles candidate and
  its exact v1 champion without another provider call.
- [x] Run the queued expanded screening population. If Protocol passes, drain
  validation and frozen with the same source; otherwise stop that candidate.
- [x] Classify the result as `TRUNCATED_QUEUE_CONFIRMED` or
  `SCIENTIFIC_NEGATIVE`. This diagnostic does not by itself prove continuous
  agent research. Result: `SCIENTIFIC_NEGATIVE`; screening passed 8W/0L/6T,
  but validation had 11/15 candidate timeouts, 0 champion failures and stopped
  before frozen.

### S2 - Restore the small V3 research semantics

- [x] Change screening-fail disposition from clean-parent rejection to a
  provisional verified branch head, while leaving champion, Protocol and
  promotion state unchanged.
- [x] Restore V3 branch depth/breadth semantics without forced diversity: up
  to three active branches, FIFO/state priority, one natural direction per
  branch, complete branch evidence, and exact branch-current source.
- [x] Set branch direction from its first retained verified H and expose it as
  context; do not add a mechanism classifier or same-mechanism gate.
- [x] Add concise Warehouse solver mechanics and safe aggregate objective
  headroom/noise facts to proposal-only problem context.
- [x] Add a concise CVRP cross-campaign research prior and explicit request for
  the smallest causal implementation that preserves unrelated code. The prior
  informs but does not select surface, action, target or Decision.
- [x] Add no framework mechanism counter or gate in this stage. If a later
  measured attribution question justifies a minimal counter, keep it
  problem-owned, observational and absent from Contract, Safe Features and
  Decision.
- [x] Delete or quarantine the remaining dead problem-specific algorithm-shape
  Contract checks encountered on this path; behavior belongs in Verification
  or Protocol.
- [x] Remove formal-candidate identity manifests, source-owner attribution,
  duplicate digests and replay-closure recording from the active campaign.
  The active lineage now records ordinary campaign/branch/H references, one
  exact branch-source equality value, stage inputs, metrics, verification and
  Protocol/Decision facts. Historical candidate evaluation may use only a
  local safe-path compatibility reader for cumulative full-file replacements;
  that reader is not an active writer or authority.
- [x] Reduce provider context to one frozen, validated value boundary with
  ordinary value/prompt equality. Remove active prompt manifests, context and
  snapshot identities, prompt hashes and receipt authority; trace and H/C call
  journal persistence are best-effort diagnostics and cannot discard a valid
  provider result. Keep the H-to-C approved-hypothesis binding.
- [x] Remove active promotion dossiers, registry hashes, summary closure and
  formal-readiness projection. Champion persistence and ordinary promotion
  lineage remain, but observer/report writes no longer form a second promotion
  gate. Remove the validation/frozen verification audit hash while retaining
  required branch code equality and clean-state checks.

### S3 - Focused implementation verification

- [x] Test the disposition truth table, branch source reuse, clean fallback
  after Verification failure, exact stage reuse and three-branch scheduling.
- [x] Test that Warehouse mechanics/headroom and CVRP prior are visible to H
  but absent from DecisionFeatures.
- [x] Test that no removed host algorithm-shape check blocks a valid
  executable candidate.
- [x] Run focused Contract, proposal, workspace, Verification, Protocol,
  Decision and campaign tests; run focused lint and diff-check changed files.
  The focused V3 integration set passed 270 tests; after the active lineage
  simplification, the evidence/proposal/composition set passed 58 tests and
  the campaign/preflight integration set passed 43 tests. Critical
  Ruff `E9/F63/F7/F82` and changed-file diff checks passed. These focused
  results do not replace the S6 full-suite run. The combined prompt, Decision,
  promotion, summary, Warehouse/CVRP smoke and fixed-replay regression set then
  passed 180 tests after the final hot-path subtraction. The stable pre-S1
  checkpoint then passed the complete suite: `1949 passed, 1 skipped` in
  628.19 seconds. S6 remains open because the final solver-evidence state still
  requires its own post-experiment regression run.

### S4 - Warehouse recovery ladder

- [ ] Run a fresh uninterrupted Terra synthetic Warehouse campaign with a
  pre-registered 36 formal-stage horizon. Do not split it into fresh roots when
  a candidate is queued for expansion/validation/frozen. This horizon covers
  the historical round-19 second-promotion tail; a 12-stage run is diagnostic
  only and cannot establish continuous promotion.
- [ ] If the first campaign does not reach v3, run at most two matched repeats
  before changing framework or problem context. Report first-promotion round,
  promotion funnel, branch depth and exact failure class.
- [ ] Independently replay every promoted champion against its immediate parent
  and replay the final champion against v1 on declared held-out evidence.
- [ ] After synthetic continuity is demonstrated, run the pre-registered
  production transfer rung. Start with one uninterrupted 12-stage shakedown;
  use a 24-stage matched matrix only if the shakedown shows a valid funnel or a
  clearly powered negative question.
- [ ] Do not enable parameter/weight search until two structural promotions are
  demonstrated. If later tested, keep it as a separate off/on ablation so it
  cannot masquerade as structural research ability.

Warehouse acceptance:

- one fresh campaign reaches at least v3 through two exact
  screening->validation->frozen promotions;
- no promotion depends on incomplete pairs, cached-only runtime, threshold
  changes, seed shopping or framework failure;
- final replay supports retained improvement over v1 and the immediate parent;
- production transfer is either positively promoted or negatively resolved by
  the pre-registered matched experiment.

### S5 - CVRP single-mechanism research ladder

- [ ] Freeze the current B0 ALNS+VNS champion and declared ProblemSpec,
  Protocol, split and seed inputs. Do not
  globally disable VNS or weaken the canonical baseline.
- [ ] Give the agent the accepted research prior, then use a fresh
  one-candidate line. The leading evidence-backed direction is an isolated,
  bounded, embedded-only SWAP* that is excluded from initial VNS and has a
  strict time/attempt allowance; the provider remains free to choose another
  source-grounded direction.
- [ ] Before formal screening, run a problem-owned public development assay on
  unseen development cases. Inspect feasibility, direct mechanism effect,
  elapsed share and ALNS opportunity. These facts decide whether to spend the
  formal run; they are not Contract or promotion gates.
- [ ] If the implementation is inactive, incorrect or starves search, stop that
  exact candidate. Permit at most one new-H/new-C implementation refinement of
  the same mechanism; never retry the same provider call.
- [ ] Run existing formal screening only for a mechanism-supported candidate.
  Queue validation/expanded validation and complete frozen using exact source
  reuse and no further provider call.
- [ ] If SWAP* is negative, test the next pre-registered line: deterministic
  route-cap-aware regret repair with existing-route insertion and at most one
  bounded ejection. Do not combine the two mechanisms before each is isolated.
- [ ] Only after a direct mechanism win may a separate allocation experiment
  bound its cadence/time share while retaining all canonical VNS components.

CVRP acceptance:

- one exact candidate completes all declared pairs with no feasibility, fleet,
  candidate-runtime or champion-runtime failure;
- existing Protocol passes screening, validation and frozen without threshold,
  manifest or budget changes made after results;
- deterministic Decision promotes to champion v2 or later;
- independent final comparison against original B0 confirms retained distance
  improvement and states the exact case-family scope.

### S6 - Close only on solver evidence

- [ ] Run the full relevant suite plus focused formatter/linter and diff check.
- [ ] Update `docs/status/current-state.md` with exact campaign roots and honest
  claim boundaries.
- [ ] Write one cross-problem report separating framework behavior,
  mechanism-level evidence, formal promotion and independent replay.
- [ ] Mark this task complete only when both Warehouse and CVRP acceptance
  blocks are satisfied.

## Experiment discipline

- Main Python: `/home/clawd/miniconda3/envs/claw/bin/python`.
- Model: `gpt-5.6-terra` through the local Codex proxy at
  `http://127.0.0.1:8080`.
- Use a fresh campaign root for each pre-registered arm. A queued stage within
  one arm must drain on the same exact candidate and campaign state.
- No provider call is retried. A new implementation correction is a new H/C
  candidate with its own evidence.
- Do not change framework source while an experiment is running.
- Poll long runs observationally at low frequency. Polling must not launch,
  retry or mutate a campaign.
- Preserve terminal roots, user documents, unrelated worktree changes and the
  overlap stash.
- The main session owns V3 architecture, TASK/current-state, experimental
  ordering and final claims. Subagents receive bounded review, implementation
  or analysis tasks.

## Status

**Active: S4 Warehouse continuous-optimization experiment, then S5 CVRP.** S1
is closed as a scientific negative; S2/S3 are complete and the stable pre-S1
suite passed 1949 tests with one skip. S6 final closure remains pending. The
prior lightweight runtime is closed and merged locally. Solver-improvement
acceptance is not yet satisfied: Warehouse is v1 in the current fresh controls,
the prior MergeVehicles candidate failed validation runtime, and CVRP has no
Protocol-complete promotion.
