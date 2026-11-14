# R13 read-only postrun: broader positive screening, still unconfirmed

## Scope and terminal evidence

Profile: Experiment Analysis, plus the experiment runbook and postrun handoff.
Read the frozen R13 preregistration, ordinary input/terminal JSON, its single
linked metric and the relevant complete source values; no SQLite, rerun,
post-outcome solver patch or private unopened population access.

R13 launched September 26 at 01:13:23 UTC. Its terminal file was written by
`2026-09-26T02:22:17.944813+00:00`: `completed` / `NOT_CONFIRMED` at expanded
screening. The pane is now dead (no exit-status value), and the old driver is
defunct; neither fact substitutes for the terminal and metric. No competing
maintenance/tests/solver was initiated during measurement; no known performance
contamination is recorded. This does not establish absence of all host noise.

Exact evidence:

- [Frozen design](v04-cvrp-r13-constructor-fixed-b0-preregistration-20260926.md).
- [Input](/home/clawd/research/scion-experiments/v04-cvrp-r13-constructor-fixed-b0-20260926/input.json).
- [Terminal](/home/clawd/research/scion-experiments/v04-cvrp-r13-constructor-fixed-b0-20260926/terminal.json).
- [Expanded-screen metric](/home/clawd/research/scion-experiments/v04-cvrp-r13-constructor-fixed-b0-20260926/metrics/361aae52-87e4-4628-84ca-fd921a6efa77.json).

Runtime launch state was `841de42b` plus the recorded changes, subsequently
committed and pushed as `964a9622` without changing algorithm/input bytes.
Each 100-file snapshot still equals its declared complete source (cache files
excluded). Between arms only destroy_repair.py, local_search.py and scheduler.py
differ. Both contain the same independently engineered construction repair.
Candidate is **FULL_SOURCE_IDENTIFIED**. H/C exports and provider calls are zero.

## Complete paired result

Estimand: R12-A-fixed versus B0-fixed, not unchanged B0, on six known development
cases and four fresh seeds. Positive delta means B0-fixed distance minus candidate.
Seed order below: 120011,120017,120041,120047.

| Case | Four paired deltas | Case median |
|---|---|---:|
| B-n34-k5 | 0, 0, 0, 0 | 0 |
| tai100a | 163, 301, 200, 156 | 181.5 |
| X-n351-k40 | 648, 368, 367, 328 | 367.5 |
| A-n54-k7 | 0, 3, 2, 1 | 1.5 |
| X-n190-k8 | 0, -274, -144, 134 | -72 |
| X-n513-k21 | 226, 226, 226, 226 | 226 |

All 24 planned pairs are valid; all 48 formal arms succeed, are feasible,
fleet-protected, intended-algorithm active/loaded, and free of runtime errors.
Raw objective differences equal every recorded delta and fleet delta is zero.
All actual orders equal scheduled parity order: 12 AB / 12 BA. Both arms have
the declared equal 60/90/180-second limits on this screening roster; tai100a's
dimension 101 correctly gets 90 seconds. The paired canary passes.

Case W/L/T **4/1/1**, median **+91.5**, bootstrap CI **[-36,296.75]**.
Win rate 4/6, net case score 3/6 and loss rate 1/6 satisfy their existing
screening thresholds; effect is above the practical threshold. The CI lower
bound is negative. The recorded gate is `unclear`, Decision `continue_explore`,
reason **SCREENING_EXPAND_EXHAUSTED_CASE_LEVEL_UNCERTAIN**. Do not change the
gate or add seeds after observing it. Runtime ratio median 1.0002172 and median
elapsed difference +15.5 ms show essentially equal wall-clock exposure, not a
speedup claim. The budget-exhausting model judges distance under equal limits.

The driver used 50 subprocesses including canary, 5300 nominal / 6800 guarded
subject-seconds. It stopped for scientific uncertainty, not exhausted provider
budget, construction failure or an operational timeout. No validation, frozen,
retained or promotion artifact was produced.

## Source-grounded interpretation

- tai100a wins all four seeds; candidate ALNS iterations 70/66/77/71 versus
  B0-fixed 25/26/30/37. This supports a bundle-level screening signal, not
  isolated causal credit for a particular operator or throughput increase.
- X-n351 has zero ALNS in both arms. Candidate initial VNS takes 138.476–138.556
  seconds after 1.121–1.201 seconds of construction. Despite positive deltas,
  later ALNS mechanisms cannot explain those gains.
- X-n513 candidate likewise has zero ALNS: construction 2.665–2.829 seconds,
  initial VNS 136.846–137.011. B0-fixed spends 93.960–96.333 seconds in initial
  VNS then runs one ALNS iteration. Both arms' post-initial objectives equal
  final objectives (26990 and 26764). The +226 is not an ALNS improvement.
- X-n190 starts post-initial search at 17876 in both arms. Candidate subsequent
  gains are 0/0/31/134, comparator gains 0/274/175/0. Candidate runs 2/4/3/2
  ALNS iterations, comparator 4/5/3/2. Candidate embedded VNS takes
  57.786–64.337 seconds of about 69.84 seconds of algorithm-local allowance.
  Two negative seeds and one positive seed imply instability, not universal harm.
- Source has 15 joint destroy-repair pairs. Selection samples a random
  without-replacement first-trial permutation before learned priorities; updates
  occur every 100 iterations. Thus X-n190 never leaves first trials or reaches
  an in-loop weight update. Whole-pair selection and polishing costs are research
  hypotheses, not proven causes of the observed loss.
- Source still guards its special initial handoff above `alns_threshold=2000`,
  while this population has at most 512 customers. It cannot be credited for
  these timings. Best-improvement SWAP* limits the final scan to ten route pairs
  and 24 customer links, but first ranks all eligible pairs and sorts their
  cross-customer links. Bounded downstream count is not bounded ranking work.

Source locators in the exact candidate snapshot:
`policies/baseline_modules/scheduler.py` (pair selection, embedded/initial VNS),
`local_search.py` (VNS and best-improvement SWAP*), `config.py` and
`policies/baseline_algorithm.py` (actual thresholds/segment length).
No ablation here isolates these components. R12 local effects, R13 B0-fixed
effects and older original-B0 effects must not be pooled or interpreted as a
causal time/bundle dose-response curve.

## Verdicts and next rung

Framework: complete fixed-funnel evidence is consistent with the frozen design
and unchanged safety/scientific boundaries; no new defect was found. H/C fidelity
is not applicable to this provider-free run. Research: useful, broader positive
development evidence with an unresolved loss and uncertainty, **not confirmed**.

The constructor repair passed the separate engineering checks, but R13 never
reached the formerly failing validation case. It adds no formal proof that the
full validation matrix now completes. Exposed validation remains a development
gate; frozen and independent retained remain unopened. Neither B0-fixed nor
unchanged-B0 retained superiority is established; CVRP remains open.

Under the September 27 analysis/optimization/launch request, prepare fresh
[R14](v04-cvrp-r14-post-r13-autonomous-preregistration-20260927.md) autonomous
research from this entire repaired candidate. Preserve all ordered prior H-only
history, add the complete safe R13 screening contrast and source facts, and let
H/C choose the algorithm. Do not prescribe a phase handoff or operator deletion,
merge siblings, widen budgets again, weaken gates or expose private regression
details. Select new seeds prospectively. R13 remains terminal and untouched.
