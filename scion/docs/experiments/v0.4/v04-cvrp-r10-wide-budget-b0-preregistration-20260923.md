# CVRP R10: equal wider-budget comparison of the complete R9 C candidate and B0

State: terminal `completed_incomplete` / `INCOMPLETE_COMPARATOR_EVIDENCE`
at validation by `2026-09-23T16:38:14.659955255Z`. Expanded screening passed
(24 valid pairs, 3/0/3, median 19.75, CI [0,179]); validation attempted 12 pairs
but two failed in both arms at shared construction. No promotion, frozen or
retained evidence. See the operator-only
[postrun](v04-cvrp-r10-wide-budget-b0-postrun-20260923.md). R10 is terminal and
must not resume. The prospective design below remains unchanged.

Launched once at `2026-09-23T15:02:15Z` (process start), tmux
`scion-r10-wide-budget-b0-20260923`, driver PID 154657, under the user's explicit
approval to widen solver budgets equally, analyze R9 and start the next experiment.
`input.json` was recorded at `15:02:15.963863784Z`; both 100-file snapshots
match their declared originals. At startup, a real screening solver was observed
on B-n34-k5 / seed 90001 with `--time-limit 60`, after the canary phase.
Startup observations are not formal results. R9 is terminal and will not resume. The
[R9 postrun](v04-cvrp-r9-post-b0-autonomous-postrun-20260923.md) records its
negative/uncertain evidence and implementation limitations.

## Question and source selection

Does the complete R9 branch-C candidate improve protected-fleet distance over
original B0 when **both** receive twice the previous external solver time?
Conditional on passing all preceding stages, does it retain the effect on the
still-unopened independent block? A positive result would concern this new
budget regime, not the original 30/45/60/90/120-second regime.

Candidate is R9's final branch C (`ff62ab13-24a4-4d42-ab81-9a8232d271be`),
created at step 8 and fully expanded at step 9: W/L/T 2/0/4, median 0,
CI [0,170.25], `SCREENING_EXPAND_EXHAUSTED_CASE_LEVEL_UNCERTAIN`, no promotion.
Its joint generation-cost selector and edge-frequency destroy are active on
tai100a, whose seed effects are mixed (187/-24/33/-20). The large-case +334
median occurred with zero ALNS iterations and cannot establish their benefit.
Selection is adaptive exploratory selection among the three surviving complete
R9 trees, not a claim that C is superior. A's last initial screen is 1/1/1 with
a large-case loss; B's last expanded screen is 1/2/3. No fresh R10 outcome is
used to choose or modify the candidate.

Exact ordinary inputs, without host-authored edits or merging:

- B0: `/home/clawd/research/scion-experiments/v04-cvrp-r6-minus-2for1-b0-20260921/input_snapshots/baseline`.
- Candidate: `/home/clawd/research/scion-experiments/v04-cvrp-r9-post-b0-autonomous-20260922/candidate_workspaces/candidate-sm2ft2v2`.

Each contains 100 ordinary files. Only `destroy_repair.py`, `local_search.py`
and `scheduler.py` under `policies/baseline_modules/` differ. The candidate
retains the complete R3i/R6/R7 bundle plus R9's C-branch changes, including unused
helpers. The driver copies ordinary read-only snapshots and serial disposable
arm workspaces; it restores no mutable campaign state and invents no H/C.

## Budget intervention and unchanged science

The [Protocol](inputs/v04-cvrp-r10-wide-budget-b0-protocol.yaml) doubles **all
formal** limits uniformly, with no case/outcome-specific exception. Both arms
receive the same limit for each case/seed; independent retained comparisons use
the same doubled frozen-stage rule.

| Instance DIMENSION | Previous limit | R10 limit |
|---|---:|---:|
| <=100 | 30 s | 60 s |
| 101–200 | 45 s | 90 s |
| 201–350 | 60 s | 120 s |
| 351–700 | 90 s | 180 s |
| 701–1001 | 120 s | 240 s |

The tai100a alias continues to resolve to DIMENSION 101's band (now 90 s).
Safety-only canary remains 10 s; it is not effect evidence. Subprocess guard
remains 30 s and memory 4096 MiB. Single-threaded, sequential arm execution.

The algorithm-owned 0.80 fraction, 3% exit reserve and internal scheduling are
**not** edited. A large-case arm therefore has about 139.68 s of search after
the reserve, versus 69.84 s previously. This isolates the configured budget
change from a new host algorithm patch, but does not guarantee initial VNS
finishes or ALNS starts. Record actual phase behavior after completion. The
candidate differs from R8's, seeds are new, and R9 used a different comparator:
cross-run deltas cannot be pooled or interpreted as a causal budget-dose effect.

Reuse the exact [R7 split](inputs/v04-cvrp-r7-autonomous-source-continuation-split.yaml):
six outcome-known adaptive screening cases, six unexecuted validation cases,
twelve unexecuted frozen cases. Reuse the separate pre-R3 reserved
[retained split](inputs/v04-cvrp-r6-minus-2for1-b0-retained-split.yaml), still
unexecuted. R9 executed no later stage. Held-out outcomes never inform this
source selection or another H/C prompt.

The first eleven primes above 90,000, chosen without results, supply new
[main seeds](inputs/v04-cvrp-r10-wide-budget-b0-seeds.yaml) and
[retained seeds](inputs/v04-cvrp-r10-wide-budget-b0-retained-seeds.yaml):

| Stage | Cases | Seeds | Pairs |
|---|---:|---|---:|
| expanded screening | 6 | 90001,90007,90011,90017 | 24 |
| validation | 6 | 90019,90023 | 12 |
| frozen | 12 | 90031,90053 | 24 |
| independent retained | 12 | 90059,90067 | 24 |
| safety canary | 1 | 90071 | 1 |

Use the existing fixed driver's explicit parity AB/BA order, with A=B0 and
B=candidate: 12 AB and 12 BA screening pairs. Both arms execute independently.
No solver/test/cleanup overlaps measurement. Counterbalancing does not prove
absence of external load variation.

All gates are unchanged: complete pairs, feasibility, fleet protection,
case-paired median effects, screening practical delta 2.0, validation 1.0,
nonnegative CI lower bound, net case score >=0.25 and case loss rate <=0.20.
No weaker `SCREENING_FAIL_CASE_QUALITY`, new telemetry gate, adaptive extension
or repeated attempt after observing results. Validation/frozen/retained open
only after the preceding necessary pass. Comparator/shared/bilateral failure
is incomplete evidence, not a candidate defeat. Preserve every negative result.

This is provider-free: H/C exports and provider calls are zero. The candidate
already passed ordinary Contract/Verification in R9. The fixed path retains
source/scope checks, strict paired canary, Protocol, Safe Features and
deterministic Decision. Only `PROMOTED_RETAINED` supports retained superiority
of this exact bundle in the declared wider-budget regime. It cannot establish
component causality, low-budget superiority or global CVRP improvement.

## Runtime, resources and prelaunch checks

Main branch `v0.4-dev`, HEAD `39b03166`; runtime unchanged from `e405bfd2`.
Existing uncommitted R8 analysis/R9 preparation is preserved. This slice adds
R9 analysis, R10 docs, three prospective inputs and one input test; no runtime
or algorithm implementation changes. Freeze these sources and scientific inputs
before launch; a clean commit is not an authority gate. Do not commit/push
without a new user request.

Maximum conditional work is 85 pairs / 170 subprocesses, 20,300 nominal and
25,400 guarded subject-seconds. Screening plus canary is 50 subprocesses,
5,300 nominal and 6,800 guarded seconds. Explicit outer guard is 43,200 seconds
(12 hours), exceeding the complete conditional matrix; no hidden lifetime cap.

Before launch: run prospective-input and existing fixed-funnel/source/session
tests; perform the existing read-only `--check`; verify exact source difference,
all case inputs, seed disjointness, fresh output/session and no active competing
job. No core/adapter/Protocol implementation changes require a new full suite
or another Warehouse solver control. Preserve all R9 original evidence.

Prelaunch validation: 106 fixed-funnel, source-continuation, source-CLI,
Code-session and R7/R8/R9/R10 input tests passed in 1.83 s. Targeted Ruff F/E9
and formatting checks passed. Read-only `--check` returned `PREPARED`, parsed
all 37 case inputs including canary, validated the exact three-file source
difference and the 170-subprocess resource maximum, without creating output
or executing a solver. Final checks found only dead older experiment panes,
no active competing solver/test, fresh output/session and 63 GiB disk available.
R3/R4/R5 seed checks also found no overlap. Runtime, scientific inputs and
algorithm sources are frozen for measurement; only this launch-status handoff
is updated after startup.

Output: `/home/clawd/research/scion-experiments/v04-cvrp-r10-wide-budget-b0-20260923`.
tmux: `scion-r10-wide-budget-b0-20260923`. Launch once; do not resume or restart
terminal output. Read `terminal.json` and its exact metric refs after completion.

## Frozen invocation

From the main checkout, without credentials or provider configuration:

```bash
/usr/bin/env -i \
  PATH=/home/clawd/miniconda3/envs/claw/bin:/usr/bin:/bin \
  LANG=C.UTF-8 LC_ALL=C.UTF-8 PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
  PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion:/home/clawd/.local/lib/python3.12/site-packages:/home/clawd/miniconda3/envs/claw/lib/python3.12/site-packages \
  OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 \
  SCION_PROBLEM_DATA_ROOT=/home/clawd/research/scion-experiment-inputs/v04-cvrp-r6-minus-2for1-b0-20260921/data \
  /home/clawd/miniconda3/envs/claw/bin/python -S -B \
  /home/clawd/research/or-autoresearch-agent/scion/run_fixed_candidate_funnel.py \
  --label v04-cvrp-r10-wide-budget-b0-20260923 \
  --baseline-source /home/clawd/research/scion-experiments/v04-cvrp-r6-minus-2for1-b0-20260921/input_snapshots/baseline \
  --candidate-source /home/clawd/research/scion-experiments/v04-cvrp-r9-post-b0-autonomous-20260922/candidate_workspaces/candidate-sm2ft2v2 \
  --problem-spec /home/clawd/research/scion-experiments/v04-cvrp-r6-minus-2for1-b0-20260921/input_snapshots/baseline/problem-v1.yaml \
  --protocol /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-r10-wide-budget-b0-protocol.yaml \
  --split /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-r7-autonomous-source-continuation-split.yaml \
  --seeds /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-r10-wide-budget-b0-seeds.yaml \
  --retained-split /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-r6-minus-2for1-b0-retained-split.yaml \
  --retained-seeds /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-r10-wide-budget-b0-retained-seeds.yaml \
  --changed-file policies/baseline_modules/destroy_repair.py \
  --changed-file policies/baseline_modules/local_search.py \
  --changed-file policies/baseline_modules/scheduler.py \
  --selected-surface solver_design --time-limit-sec 60 --timeout-guard-sec 30 \
  --outer-hardwall-sec 43200 --memory-mb 4096 \
  --output-dir /home/clawd/research/scion-experiments/v04-cvrp-r10-wide-budget-b0-20260923
```

Appending `--check` parses and validates without running a solver/provider or
creating output. R10 does not repair R9's missing yield controller, implement a
host-selected phase allocation, or restart autonomous H/C. Those remain separate
future research questions after the equal-budget comparison.
