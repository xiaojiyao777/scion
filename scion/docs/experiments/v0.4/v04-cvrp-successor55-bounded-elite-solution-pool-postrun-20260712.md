# CVRP Successor55 Bounded Elite Solution-Pool Postrun

*Date: 2026-07-12*
*Run status: valid / complete / postrun-ready*
*Model: `gpt-5.6-sol`*

## Run Identity

- Run root:
  `/home/clawd/research/scion-experiments/v04-cvrp-successor55-bounded-elite-solution-pool-search-server-claw-gpt56sol-2r-gpt56sol-20260712T141031Z-claw`
- Campaign commit: `ff184608`
- Prepared design commit: `b56a2a32`
- Requested/effective rounds: `2 / 2`
- Proposal attempts: `3`
- Proposal quality blocks: `1`
- Formal screened candidates: `2`
- Wrapper exit: `0`
- Last stop reason: `max_rounds_exhausted`
- Champion promotions: `0`
- Postrun reports/readiness: complete and ready

## Decision

Successor55 is framework-informative but solver-negative.

Do not long-run, statistically expand, threshold-tune, or launch a same-line
solution-pool repair as the next v0.4 action. The second row contains useful
A/B-family subgroup gains, but both aggregate medians are zero, both CI highs
are below the 9.9 A/A MDE, no row is positive at or above MDE, and CMT2 is
negative in both implementations.

The more important result is architectural: the run gives a complete fixture
for prompt overloading, proposal-gate dialect repair, typed telemetry debt,
and downstream VNS dilution. Freeze new successors and use this run as the
baseline for the runtime-simplification plan.

## Proposal and LLM Accounting

All model calls were successful, but the input volume was excessive:

| Call kind | Calls | Input tokens | Output tokens |
| --- | ---: | ---: | ---: |
| target intent | 3 | 226,645 | 642 |
| hypothesis | 3 | 528,492 | 3,756 |
| tool selection | 4 | 72,789 | 360 |
| code | 2 | 154,959 | 5,673 |
| total | 12 | 982,885 | 10,431 |

Observed cache-read input tokens were zero.

The failed quality attempt consumed approximately 252,998 additional input
tokens across its retry path. This was a proposal-dialect repair, not a
research iteration.

The first target-intent correctly selected
`policies/baseline_modules/solution_pool.py` and
`bounded_elite_solution_pool_search`. The first formal hypothesis also
described the intended persistent whole-solution pool, but was rejected before
code generation only because it omitted
`branch_lesson_usage.clean_fork_diversity_claim`. The retry then supplied the
exact nested contract.

This quality block did not count as an effective protocol round, but it caused
another target-intent/hypothesis pass over a very large prompt. In the measured
formal hypothesis prompt:

- latest input was `176,653` tokens;
- `Compact Research Signals` was about `401,011` chars;
- embedded `launch_research_focus` was about `360,599` chars;
- `Prepared Research Obligations` was about `148,243` chars;
- `Prepared Successor Focus` was about `37,064` chars.

This is direct evidence that host-known audit metadata and successor history
must leave the default provider-visible prompt.

## Candidate 1

Implementation shape:

- created `policies/baseline_modules/solution_pool.py`;
- added narrow scheduler wiring;
- bounded pool size, diversity admission, route/feasibility guard, anchor
  selection, and runtime guard;
- kept global `best` semantics outside the pool.

Formal screening:

| Metric | Value |
| --- | ---: |
| valid pairs | 48/48 |
| pair W/L/T | 10 / 11 / 27 |
| case W/L/T | 1 / 3 / 8 |
| median delta | 0.0 |
| CI | [-1.5, 0.0] |
| decision | abandon |

Selected case medians:

- A-n64: `+18.0`;
- A-n80: `+1.5`;
- B-n67: `-3.0`;
- CMT2: `-2.5` with pair W/L/T `0/3/1`;
- CMT4: `0.0`, all ties;
- P-n76: `-8.5`.

The formal reason family was loss-heavy/non-positive-CI screening failure.

## Candidate 2

Implementation shape:

- remained on the same mechanism and owner file;
- split the bounded pool into quality and novelty lanes;
- added usage/credit-biased anchor selection;
- kept scheduler wiring narrow.

Formal screening:

| Metric | Value |
| --- | ---: |
| valid pairs | 48/48 |
| pair W/L/T | 10 / 9 / 29 |
| case W/L/T | 3 / 3 / 6 |
| median delta | 0.0 |
| CI | [-0.75, 3.0] |
| lifecycle decision | expand_screening |

Selected case medians:

- A-n64: `+6.0`;
- A-n80: `+13.0`;
- B-n67: `+8.5`;
- CMT2: `-1.5` with pair W/L/T `0/3/1`;
- CMT4: `0.0`, all ties;
- E-n101-k14: `-3.0`;
- P-n76: `-4.0`.

The `expand_screening` lifecycle result means low-SNR/mixed evidence, not a
positive solver result. Its CI high `3.0` is still below the `9.9` MDE, the
aggregate median remains zero, and the predeclared CMT2 risk remains negative.
The campaign ended at the requested round budget. Independent postrun review
therefore overrides the generic lifecycle suggestion for planning purposes:
park/default-avoid this mechanism rather than spend the next action on an
expansion.

## MDE and Full-Solver Judgment

The stored postrun research-efficiency report concludes:

- `max_median_delta=0.0`;
- `max_effect_to_mde_ratio=0.0`;
- `positive_rows=0`;
- `rows_at_or_above_mde=0`;
- `rows_with_ci_high_below_mde=2`;
- interpretation: `all_available_ci_high_below_mde`.

Successor55 therefore does not justify validation, frozen, long-run, or
promotion work.

## Telemetry Audit

Both candidates passed the current telemetry guard and were reported as having
observed activation and positive mechanism effect. That label is not causally
trustworthy under the generated implementations.

Candidate 1:

- solution-pool phase accepted-move sum: `940` across 48 runs;
- mechanism best-delta positive in 17/48 runs;
- mechanism runtime: `162 ms` total, nonzero in 39/48 runs.

Candidate 2:

- solution-pool phase accepted-move sum: `943` across 48 runs;
- mechanism best-delta positive in 18/48 runs;
- mechanism runtime: `450 ms` total, nonzero in 41/48 runs.

Those accepted counts merge at least three different facts:

1. admission into an internal container;
2. selection/switch to a stored anchor;
3. a later downstream new-best credited while an anchor is active.

They are not 940/943 accepted route-improvement moves. A later ALNS best after
an anchor switch is associated with the pool trajectory but is not a direct
counterfactual effect. The telemetry contract should split attempt, state
transition, direct objective effect, and associated downstream outcome before
another solver campaign.

The mismatch is visible in the paired results: 7 of the internally
positive-effect runs for each candidate were final pair losses. On CMT2, the
internal effect sums were positive (`21` and `130`) while final paired delta
sums were negative (`-10` and `-12`). Candidate 2 also retained active credit
across state changes rather than clearing it. The second-row champion side was
fully cache-hit, so its runtime evidence was classified
`insufficient/low_cached_champion`.

## Artifact Integrity Gap

The run completed and the full-file `code_content` in each
`candidate.patch.json` is replayable, but both exported `candidate.diff`
artifacts fail an independent `git apply --check`:

- candidate 1: `corrupt patch at line 241`;
- candidate 2: `corrupt patch at line 357`.

The historical postrun readiness and evidence-integrity checks did not detect
this. The current working tree now generates parseable diffs and includes a
required `formal_candidate_diff_integrity` check. Rechecking this unchanged run
correctly reports it as not current-run-analysis-ready, while retaining the
full-file patch payload as the canonical replay content.

## Runtime-Dilution Audit

Candidate phase totals show the full-solver result is dominated by downstream
VNS:

| Candidate | ALNS core | Embedded VNS | Solution pool |
| --- | ---: | ---: | ---: |
| 1 | 154,722 ms | 1,148,289 ms | 162 ms |
| 2 | 153,460 ms | 1,157,147 ms | 450 ms |

The promotion protocol should remain full-solver. For research feedback, add a
problem-owned diagnostic assay that can measure the changed state boundary
before downstream VNS absorbs or reverses the effect. Diagnostic results must
remain outside `DecisionFeatures` and promotion input.

## Accepted Lessons

Framework-positive:

- exact target binding and full target source visibility worked;
- both generated candidates respected the new module owner and narrow wiring;
- verification, 48-pair screening, priority-case selection, wrapper status,
  artifact persistence, and postrun readiness completed normally;
- the quality block was accounted separately from effective protocol rounds.

Solver-negative:

- neither row was positive at MDE;
- candidate 1 was loss-heavy and abandoned;
- candidate 2 was mixed/low-SNR with CMT2 still unsafe;
- no promotion occurred.

Audit-negative:

- 982,885 input tokens for two screened candidates is not a viable research
  loop;
- the first block repaired a gate-specific metadata shape, not the algorithm;
- current telemetry overstates accepted moves and causal effect;
- postrun readiness can report ready while exported candidate diffs are
  syntactically corrupt;
- exact target binding proves implementation compliance, not open research.

## Next Action

1. Freeze successor56 and all same-line solution-pool work.
2. Use this run as the R0 prompt/gate/telemetry characterization fixture.
3. Land a single immutable prompt snapshot without content change.
4. Replace duplicate guidance with one authoritative full-context projection;
   do not add a `ResearchBrief` budget, summary substitution, or truncation.
5. Reset proposal gate ownership and host-fill audit metadata.
6. Implement typed telemetry semantics.
7. Only after those slices pass replay and regression tests, run one short,
   non-target-bound formal CVRP campaign.

Related documents:

- `scion/reports/v04-v3-runtime-and-research-effectiveness-audit-20260712.md`
- `scion/docs/planning/v0.4/v0.4-runtime-simplification-and-research-reset-plan-20260712.md`
