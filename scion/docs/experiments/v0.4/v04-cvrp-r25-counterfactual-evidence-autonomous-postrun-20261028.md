# CVRP R25 terminal analysis: stronger diagnostics, no stable net benefit

Date: 2026-10-28. Profile: Experiment Analysis. Read the canonical entry pack,
R25 preregistration, operations runbook and postrun handoff before the bounded
read-only audit. User authorizes analysis, optimization and a fresh experiment,
not Git commit/push. Entry checkout is clean1d9845db=local origin/v0.4-dev.

## Scope and terminal

Root: `/home/clawd/research/scion-experiments/v04-cvrp-r25-counterfactual-evidence-autonomous-20261026`.
[Status](/home/clawd/research/scion-experiments/v04-cvrp-r25-counterfactual-evidence-autonomous-20261026/status.json),
[summary](/home/clawd/research/scion-experiments/v04-cvrp-r25-counterfactual-evidence-autonomous-20261026/campaign_summary.json).
The [frozen design](v04-cvrp-r25-counterfactual-evidence-autonomous-preregistration-20261026.md)
retains its original uncommitted-at-launch provenance; later publication as
1d9845db does not rewrite that fact.

Completed/valid at2026-10-27 08:25:49.072811 UTC /16:25:49 Beijing, about16h22m24s
after launch. Twelve requested/evaluated screening stages, ten distinct candidates,
no rejection or held-out stage; championv1 unchanged, no promotion.
The12 formal-screened counter counts stages, not distinct algorithms.
Carrier dead exit0 agrees but does not establish the scientific outcome.

137/600 physical calls:73 H and64 C, all successful attempt0. No recorded quota,
transport, resource, solver or feasibility failure.463 calls remain; the48-hour
guard did not exhaust. All296 pair rows/592 sides valid, fleet violation0 and
empty solver errors. Formal elapsed sums53,832.251 seconds, not campaign duration.
No competing campaign/test/solver was found at this audit. Launch discipline
records no operator overlap; there is no continuous host-load record proving
absence of every external interference.

## Comparative science

Every stage compares its complete cumulative branch against unchanged R22 C3,
not its preceding branch head, R23 A, or original B0. Positive delta means
C3 final distance minus candidate final distance. Effect is the median of case
medians; the brackets are its recorded95% bootstrap interval.

|Round|Candidate/stage|Pairs|Case W/L/T|Pair W/L/T|Effect [CI]|Recorded result|
|---|---|---:|---|---|---|---|
|1|A1 initial|20|0/1/4|2/3/15|0 [-20.5,0]|fail case quality|
|2|B1 initial|20|0/1/4|2/5/13|0 [-22.5,0]|fail case quality|
|3|C1 initial|20|1/1/3|3/4/13|0 [-5,7.5]|fail case quality|
|4|A2 initial|20|0/2/3|3/4/13|0 [-12,0]|fail case quality|
|5|B2 initial|20|0/1/4|1/3/16|0 [-9,0]|fail case quality|
|6|C2 initial|20|1/0/4|2/1/17|0 [0,16]|expand|
|7|C2 expanded|48|1/1/4|9/7/32|0 [-2.75,0.25]|fail case quality|
|8|A3 initial|20|0/1/4|1/5/14|0 [-29.5,0]|fail case quality|
|9|B3 initial|20|0/1/4|3/2/15|0 [-15,0]|fail case quality|
|10|C3 initial|20|1/1/3|5/4/11|0 [-15,39]|fail case quality|
|11|A4 initial|20|1/0/4|4/2/14|0 [0,18.5]|expand|
|12|A4 expanded|48|0/1/5|6/9/33|0 [-0.75,0]|fail case quality|

All raw grids, objective differences, pair signs, case medians, aggregate medians,
bootstrap intervals, time limits and gate reason codes reproduce. Gate recomputation
binds problem-owned practical deltas2/1; it does not use unbound configuration
defaults or overwrite Decisions. All initial Contract/Verification checks pass;
canary results pass, and expansion reuses the same candidate.

Across executed rows:41 wins,49 losses,206 ties. This is descriptive, not one
pooled independent experiment. Expanded6×8 screens rerun the initial5×4 cells;
3/20 and7/20 repeated champion outcomes differ for rounds6→7 and11→12. The
champion-first ordinary order remains unbalanced. Fresh seeds do not turn the
known adaptive cases into a new case population; no matched noise/power estimate
was collected.

Notable patterns:

- C2 initial tai100a median+16 becomes−5.5 over eight seeds; A54 median+.5 yields
  expanded case1/1/4 and0[-2.75,.25]. Other case medians are0.
- A4 initial tai100a+18.5 becomes−1.5 expanded; every other case median0,
  expanded0/1/5 and0[-.75,0]. Neither initial signal passes full screening.
- C3 tai100a improves at all four seeds:20,12,93,58, median39. But X513 loses15
  at every seed; case1/1/3 fails. Selecting only tai100a would erase an actual loss.
- All56 X513 pair rows have zero ALNS iterations on both sides. B's destroy/repair
  optimizations cannot receive causal credit for that case's timed differences.
  Final A4 X351 has eight ties; C2 X351 has seven ties and one+3.
- B34 ties at every seed, despite substantial throughput losses in the A branch.
  A1 iterations medians653 versus1317.5, A2 917 versus1288, A3 838.5 versus1314.5,
  A4 expanded718.5 versus1267.5. C3 is1011 versus1363.5. These complete-bundle
  observations support considering total overhead, not identifying one helper's
  isolated cost or imposing a host-chosen phase policy.

All592 progress rows return no worse than their own initial post-local-search
checkpoint. All815 recorded best updates are retained at final return. There
is no observed positive initial relative lead turning into a final loss in R25,
and no evidence for a production best-return repair. Metrics do not preserve
every transient route/changed-kernel event, so these facts are not complete
mechanism attribution or an independent route-level recomputation.

## Actual algorithm research and source fidelity

Branch labels are local to R25:

|Branch|Stages and actual cumulative changes|Surviving full head|
|---|---|---|
|A c9a76241|A1 whole-pair Held–Karp fallback after completed no-winner singleton search; A2 solve-local no-winner reuse and caller plumbing; A3 advance past certified pairs; A4 omit overloaded DP states without pruning feasible prefixes|candidate_workspaces/candidate-ei6fy2a4|
|B 62500594|B1 exact incremental Shaw relatedness minima; B2 separable two-hop ejection pricing with rounded-sum tie handling; B3 solve-local immutable nearest-distance normalization|candidate_workspaces/candidate-j4ebuswp|
|C a998343b|C1 three-route cyclic free reinsertion; C2 capacity-conditioned rotation completion; C3 exact Or-opt insertion-cost vectors and identity-preserving VNS dispatch|candidate_workspaces/candidate-t3fmjut5|

All three surviving heads contain the100 ordinary source files plus ten existing
generated bytecode files; they differ from C3 only in A:local_search/scheduler,
B:destroy_repair/scheduler, C:local_search. No bytecode or original evidence
was deleted. All100 source values match ordinary final patches.
A4/B3/C3 are FULL_SOURCE_IDENTIFIED. The seven superseded heads are absent:
ordinary patch fallback identifies their source values in memory, with48 Python
files parsing in each; they are PATCH_FALLBACK_IDENTIFIED, not newly preserved
historical complete workspaces. No reconstructed executable candidate was run.

317 visible editable C values match the actual session base,128 public-test and
1088 read-only values match their frozen host support. All ten approved H values
match the corresponding C context and evaluated step. Actual changes implement
the stated mechanisms and retain sibling separation. H explicitly distinguishes
exact evaluator savings from added capability and cumulative contrasts from
incremental causality. No delivered-source, Contract or Decision defect is
observed in these exercised paths; that is not a proof of all runtime correctness.

## Tests: real progress and remaining claim gaps

Sixteen submitted probes:12 passed, two assertion failures, one collection syntax
error, one timeout. Every candidate ends with a passing probe. All16 host public
check sets pass5/5; a passing host set does not convert its failed/timeout optional
probe into a pass. Two B2 invalid empty-query actions receive bounded correction.
No raw private evidence is used as a falsifier.

Stronger actual evidence includes:

- A1 independently exhausts six-customer partitions with a26→8 anchor and all
  fixed-state poll cutoffs. Its real VNS check only asserts non-worsening.
- B1 compares removal order, partial routes and RNG state; counts exact reduced
  relatedness work and asserts nonempty completed Shaw transitions through the
  ordinary solver. This is stronger than mere entry telemetry.
- C1 independently establishes no improving feasible singleton exchange and a
  three-route630→603 transition, then reaches603 through the real full-registry
  VNS with full and active-frontier scopes.
- A2 checks cold/warm no-winner behavior and solve-local lifetime through actual
  entry; A3 checks all15 pairs advancing one per real VNS invocation.
- B2's final probe checks directed/fractional/rounded-tie cases, real repair callers
  and atomic cutoffs. Its earlier oversized probe times out; the final bounded
  scope is not the same full coverage claim.
- B3 asserts at least two actual frequency calls, a cold first map, warm later
  maps and distinct maps across solves, with independent removal/RNG references.
- A4 checks feasible DP rows, zero-demand cases, overloaded complements and
  interrupted no-winner publication, but the large0.2-second entry is a deadline/
  feasibility check, not completed fallback gain at that scale.

Two specific remaining issues motivate the next support/input changes:

1. C2's first multi-route reference fails at line143
   (`20261026T220141218636_code_research_turn_c5bfe58a.json`).
   Its reference nominates triples without the candidate's active-frontier filter,
   while execution supplies only route0 as active. Thus it does not model the
   same eligible population; the recorded line alone does not isolate every
   cause of disagreement. The final passing probe restricts to three routes,
   where that exclusion disappears, and keeps `best <= inherited_best`, not a
   strict extra-win witness. It does not repair full multi-route scoped coverage.
2. C3 first fails its handwritten repeated-descent reference anchor at line78
   (`20261027T035140068676_code_research_turn_09b310a1.json`).
   Final revision supplies a new independent valid anchor and substantial local
   transition/cache checks. However its final `test_real_vns_cache_dispatch`
   appends `published` records and never asserts that list is nonempty or that
   a hit occurs. Its final assertion is merely registry length7. A passing
   conditional callback can be vacuous. Earlier real-solve `published and hits`
   assertions occur in the probe already failed at the earlier anchor and cannot
   be claimed as passing evidence. Final trace:
   `20261027T035501823055_code_research_turn_b79403e5.json`, lines164–182.

Do not infer that cache integration is broken: source shows the actual plumbing;
the evidence gap is what this test establishes. Counting fewer helper calls
likewise excludes key construction, miss builds, eviction and extra polling,
and does not establish net speed or final quality.

## Bounded optimization and next rung

Keep original evidence, production solver, generic core/adapter/prompts and all
Contract/Verification/Protocol/Decision rules unchanged. Optional public support
adds a synthetic same-frontier reference worksheet (full, empty, active and inactive
controls), plus three regressions including two wrong-scope mutations. Existing
target-bypass retention regressions remain. Guidance distinguishes nonempty
target observations, publication versus actual reuse, and whole-call overhead;
no mandatory positive fixture or new quality gate.35 focused support tests pass
in23.43s; full prelaunch verification is recorded in the next design.

[R26 prospective design](v04-cvrp-r26-scope-and-net-benefit-autonomous-preregistration-20261028.md)
uses the same complete C3 and all23 whole histories. Supply every R25 screening
cell, including losses, and the safe public diagnostic limitations above. H/C
choose mechanisms/tests; do not import a sibling, force a path, relax a gate,
resume R25, or call local signals retained original-B0 superiority.

## Exact raw stage refs

- Round1 A1: [metric](/home/clawd/research/scion-experiments/v04-cvrp-r25-counterfactual-evidence-autonomous-20261026/metrics/26cf6e05-c8b1-4c41-8851-7afd34a97d00.json).
- Round2 B1: [metric](/home/clawd/research/scion-experiments/v04-cvrp-r25-counterfactual-evidence-autonomous-20261026/metrics/a927d67c-c8ec-49f6-86e2-d51692759ef2.json).
- Round3 C1: [metric](/home/clawd/research/scion-experiments/v04-cvrp-r25-counterfactual-evidence-autonomous-20261026/metrics/83c63fa9-d164-4e2a-a22d-19f7c06af5de.json).
- Round4 A2: [metric](/home/clawd/research/scion-experiments/v04-cvrp-r25-counterfactual-evidence-autonomous-20261026/metrics/ab513cca-1fa3-4d72-94f9-436fc5e00cde.json).
- Round5 B2: [metric](/home/clawd/research/scion-experiments/v04-cvrp-r25-counterfactual-evidence-autonomous-20261026/metrics/6487cfea-87ab-40c8-8af1-b827ac2866af.json).
- Round6 C2: [metric](/home/clawd/research/scion-experiments/v04-cvrp-r25-counterfactual-evidence-autonomous-20261026/metrics/0877fc91-5532-4bd2-b8a5-9694937fb302.json).
- Round7 C2: [metric](/home/clawd/research/scion-experiments/v04-cvrp-r25-counterfactual-evidence-autonomous-20261026/metrics/1470330f-7b21-4956-9988-bec53656978b.json).
- Round8 A3: [metric](/home/clawd/research/scion-experiments/v04-cvrp-r25-counterfactual-evidence-autonomous-20261026/metrics/cbc45474-c523-456d-ac11-0ba5f4946005.json).
- Round9 B3: [metric](/home/clawd/research/scion-experiments/v04-cvrp-r25-counterfactual-evidence-autonomous-20261026/metrics/ef3ee48b-ea87-43c6-a1c3-b899f3ed9d36.json).
- Round10 C3: [metric](/home/clawd/research/scion-experiments/v04-cvrp-r25-counterfactual-evidence-autonomous-20261026/metrics/47631d66-350d-4cef-8254-aa74234a5a49.json).
- Round11 A4: [metric](/home/clawd/research/scion-experiments/v04-cvrp-r25-counterfactual-evidence-autonomous-20261026/metrics/9d2f94ef-8f9e-4013-96ac-8b31f4a219c6.json).
- Round12 A4: [metric](/home/clawd/research/scion-experiments/v04-cvrp-r25-counterfactual-evidence-autonomous-20261026/metrics/013056c7-e655-499c-9505-bfef211508a5.json).

Additional ordinary evidence: `research_history.jsonl` (12 safe screening rows),
`llm_traces/` (137 terminal records), and the three source directories above,
all beneath the exact R25 root. Original SQLite was not opened.
