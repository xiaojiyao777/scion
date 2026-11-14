# Scion v0.4 Warehouse/VRP Process Synthesis - 2026-06-16

## Boundary

This is a main-session synthesis of four subagent reports:

- `v04-warehouse-longrun-rep01-branch-analysis-20260616.md`
- `v04-warehouse-longrun-rep02-branch-analysis-20260616.md`
- `v04-warehouse-longrun-rep03-branch-analysis-20260616.md`
- `v04-vrp-independent-research-process-audit-20260616.md`

It preserves the v3 boundary from `design/scion-architecture-v3.md`.
Prompt/context/trace/branch-lesson and independent-agent research logs are
diagnostic material only. Promotion evidence remains deterministic Contract,
Verification, Protocol, safe feature extraction, and Decision output.

## Accepted Inputs

Warehouse longrun root:

`/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z`

The three accepted warehouse cells were valid production-style runs:

| Cell | Champion | Promotions | Protocol rows | Stage counts | Proposal attempts | Quality blocks | Heavy verification | Code edit failures | Fresh replay executed |
| --- | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: | ---: |
| `rep01` | `v2` | 1 | 25 | screening 22, validation 2, frozen 1 | 47 | 21 | 1 | 1 | 0 |
| `rep02` | `v1` | 0 | 24 | screening 21, validation 2, frozen 1 | 38 | 14 | 0 | 2 | 0 |
| `rep03` | `v2` | 1 | 22 | screening 19, validation 2, frozen 1 | 39 | 15 | 2 | 0 | 0 |

All three cells had branch-lesson usage present in every inspected session and
semantic projection present in every inspected session:

| Cell | Sessions | Traces | Branch-lesson truncated traces | Research-signal token share | General token share |
| --- | ---: | ---: | ---: | ---: | ---: |
| `rep01` | 60 | 130 | 44 | 0.301 | 0.382 |
| `rep02` | 55 | 120 | 51 | 0.340 | 0.357 |
| `rep03` | 55 | 107 | 52 | 0.357 | 0.355 |

VRP independent control inputs:

- Phase K `Helmholtz`: retained `regret4_repair` from a small 5-case x 3-seed
  smoke grid.
- Broader `regret4_repair` validation:
  `/home/clawd/research/scion-experiments/v04-vrp-regret4-broader-validation-20260616`
- Phase L `Newton`: rejected intra-route Or-opt VNS after primary and outside
  sanity matrices.

The broader `regret4_repair` validation completed `80/80` rows with no
failures, no feasibility regressions, and no route-count regressions, but W/T/L
was `21/31/28`, W-L `-7`, median delta `0.0`, and repeated regression families
were `E`, `M`, and `P`.

## Main Judgement

The surprising result is real but not ambiguous:

1. v0.4 warehouse can still execute the full production path and can still
   promote.
2. It does not recover the v0.3-style cadence or continuous branch-improvement
   behavior.
3. The limiting factor is not a catastrophic launch/preflight framework break.
   It is research-loop efficiency: branch-level lesson usability, proposal
   quality, fragile code-edit protocol, cheap verification gaps, no-effect
   continuation policy, and unschedulable fresh-runtime replay closure.
4. CVRP/VRP failure is not explained by "there is no BKS gap." There is gap,
   but current agents, with or without Scion, mostly try nearby operator or
   parameter edits and do not yet diagnose which slice/phase creates the gap.

Therefore the next v0.4 work should not be another blind longrun. The next
rung should repair the observed research-loop drains and add problem-owned VRP
mechanism diagnostics before spending more long-run budget.

## Warehouse: What The Branch Replay Shows

### Rep01

`rep01` produced one valid promotion on branch `98676170...` with
`compatible_pair_cost_guard`. That branch is the best positive example of
cross-branch semantic transfer: it avoided and contrasted prior failed lessons
and changed mechanism rather than repeating the same weak path.

However, most of the cell did not convert visible lessons into executable
research:

- `21/47` proposal attempts were quality blocks.
- Branch lessons were visible in all sessions, but `44/130` traces had
  truncated branch-lesson context.
- Repeated same-target attempts failed the machine-readable
  `branch_lesson_usage` linkage even when the natural-language intent was
  plausible.
- One stale `old_string_not_found` edit consumed a code attempt before the
  eventual successful branch recovered.
- One formal-candidate replay path reached fresh-runtime pressure but had no
  schedulable replay candidate.

Interpretation: rep01 proves isolated continuity, not sustained continuity.
The agent can use branch history productively, but this happened once rather
than becoming a repeatable branch-to-branch research process.

### Rep02

`rep02` reached frozen but did not promote. Its strongest branch, `345a...`,
was not blocked by Contract, Verification, prompt absence, or runtime replay. It
failed because the objective signal was marginal and did not generalize:
screening passed, validation barely queued frozen, and frozen split `6/6` with
negative median delta.

The important process drains were:

- `14/38` proposal attempts blocked before Protocol.
- `51/120` traces had truncated branch-lesson context.
- Branch lessons were present and often semantically projected, but the model
  repeatedly failed exact target/action/mechanism linkage.
- A merge-family branch lost two code attempts to exact-replace serialization
  and stale `old_string` failures.
- Multiple all-tie same-mechanism refinements consumed rounds after marginal
  parents.

Interpretation: rep02 is not a framework-path failure. It is a real research
failure: the system spent too much of the campaign on guarded no-op or
all-tie refinements, and the only frozen candidate was correctly rejected.

### Rep03

`rep03` produced one valid promotion on branch `47ec47f1...` with
`cost_preserving_tail_refit`. The promotion is robust as an active-champion
improvement because it survived screening, validation expansion, and frozen
with high-confidence pair wins.

The rest of the branch replay again shows inefficient search:

- `15/39` proposal attempts were quality blocks.
- `52/107` traces had truncated branch-lesson context.
- Two heavy verification failures were cheap-invariant misses: a remove
  operation left import/registry inconsistency, and one operator returned
  `None` on a path that should return a `Solution`.
- The successful branch used historical lessons best as contrast/avoidance,
  not as a direct mechanism template.
- No follow-up `v3` champion chain emerged after the first promotion.

Interpretation: compact measurement diagnostics can carry enough historical
signal for one good clean fork, but current branch-lesson machinery does not
yet reliably drive sustained depth.

## Warehouse: Root Causes

The branch reports agree on the same root causes:

1. Lesson visibility is not lesson usability.
   The context usually contains branch lessons, and reports count semantic
   projection as present, but proposals still fail strict linkage. The system
   needs to measure `semantic_linkage_valid`, not only `usage_present`.

2. The `branch_lesson_usage` gate is useful but too brittle.
   It correctly prevents ungrounded branch claims from reaching code, but it
   also burns many attempts on schema/linkage details the system could
   canonicalize deterministically from the hypothesis, branch card, and target.

3. Same-branch weak-positive refinement and clean-fork contrast need different
   modes.
   Current prompts often mix obligations. A weak-positive refinement should
   preserve the branch lesson and state a concrete mechanism delta. A clean
   fork should contrast/avoid prior lessons. Forcing both shapes everywhere
   produces blocks and all-tie guarded no-ops.

4. Code-edit robustness is still too weak for repeated same-file research.
   The old-string and exact-replace failures are not research insight. They
   consume campaign attempts and should be handled by a deterministic patch
   path or full-file replacement validation when repeated same-file edits occur.

5. Cheap verification invariants should catch obvious operator errors before
   heavy verification.
   Remove-operation registry/import consistency and operator `execute` return
   type are low-cost checks that would convert heavy failures into targeted
   repair feedback.

6. Fresh-runtime replay pressure is not closed.
   Each warehouse repeat had a fresh-runtime replay drain attempt with
   `executed=0` and `pressure_no_schedulable_replay_candidate`. Runtime
   pressure should either materialize a replayable candidate or close with a
   machine-readable non-replayable reason.

7. Tie-heavy screening creates over-readable weak positives.
   Promotions were only trustworthy after validation/frozen. Many weak
   branches produced all-tie or mostly-tie rows and then consumed further
   attempts. This argues for earlier all-tie branch-local stop/diagnosis rules,
   not weaker promotion gates.

## VRP: Why BKS Gap Did Not Become Improvement

The independent VRP audit answers the user's central question directly:

BKS gap is headroom, not a paired-improvement certificate.

The active protocol asks whether a candidate beats the current champion on the
same case/seed/budget while preserving feasibility, fleet/route semantics, and
validation/frozen robustness. A solver can be away from BKS and still reject a
small local candidate because the gap arises from a different phase: initial
construction, route-count pressure, destroy/repair scheduling, acceptance
temperature, VNS runtime allocation, or large-X budget saturation.

The independent-agent lane is useful but not yet strong:

- It produced auditable process records in phases G-L.
- Phase K's `regret4_repair` smoke signal was narrow and family-skewed.
- Broader validation showed `regret4_repair` was not a robust broad
  improvement, especially because `E`, `M`, and `P` regressed.
- Phase L's Or-opt VNS addition was rejected correctly; extra local search can
  consume short-budget ALNS opportunity.
- Prior phases mostly tested nearby knobs or small operator variants, not
  systematic mechanism diagnostics.

The conclusion is not "Scion is the only reason VRP fails." Plain independent
Codex research also struggled to turn BKS headroom into robust gains. The
shared bottleneck is problem-domain research quality and diagnostics.

## Accepted Next Rung

### Warehouse

Before another full `3 x 24R` warehouse longrun, implement a targeted
research-loop repair package:

1. Add a deterministic `branch_lesson_usage` canonicalizer before quality
   gating.
2. Add explicit proposal modes:
   `same_mechanism_refine`, `clean_fork`, `sibling_nearby`, and
   `weak_positive_transfer`.
3. Count and report `semantic_linkage_valid` separately from lesson visibility.
4. Harden code edit protocol for repeated same-file edits.
5. Add cheap warehouse operator invariants for remove-operation dependencies
   and `execute -> Solution` return behavior.
6. Make fresh-runtime replay candidates materializable or explicitly closed.
7. Stop or redirect all-tie same-mechanism refinements earlier.

Acceptance should be a short warehouse debug run first, not a blind longrun:
`4-6R`, early stop disabled, compact diagnostics, and postrun checks for fewer
proposal-quality blocks, no code-edit stale failures, no unschedulable fresh
runtime replay pressure, and at least one semantically valid branch transfer.

Only after that should a new longrun compare continuity against the current
`2/3` single-promotion warehouse result.

### VRP/CVRP

The next VRP task should be diagnostic, not candidate-first:

1. Split at least A/B/E/P/M/X and construction-only large/AGS surfaces.
2. Record construction cost, post-initial-local-search cost, ALNS iteration
   count, selected destroy/repair pairs, accepted moves, best-update count,
   route-count status, phase runtime, and final BKS gap.
3. Keep ALNS-only and ALNS+VNS as separate research surfaces. ALNS-only is
   weaker but more measurable; ALNS+VNS remains the canonical quality baseline.
4. Pre-register budget tiers before choosing candidates: 1s, 2s/3s, and one
   longer diagnostic tier.
5. For repair operators such as regret4, test destroy/repair interaction
   ablations before adding another global operator to the pool.
6. For local-search additions, measure opportunity cost explicitly.

Acceptance for the next independent or Scion-assisted VRP task should not be
"positive W/T/L on a smoke set." It should be either:

- a validated narrow mechanism claim for one pre-registered slice, or
- a diagnostic that explains why a slice has BKS gap but the current solver
  does not convert it into paired improvement.

## TASK Impact

This synthesis changes the active TASK interpretation:

- The warehouse longrun regression question is answered: v0.4 is not
  catastrophically regressed, but it has not recovered v0.3-style continuous
  promotion.
- The warehouse repair target is no longer broad observability. It is targeted
  research-loop repair around branch-lesson usability, code-edit robustness,
  cheap verification, replay closure, and tie-heavy branch lifecycle.
- The VRP independent lane remains useful as an external control and
  hypothesis generator, but it has not produced an adoptable broad candidate.
- The next VRP rung should be instrumentation and mechanism diagnosis, not a
  longer random search for another local operator.
