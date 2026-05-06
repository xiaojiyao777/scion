# Causality and Design Review

Date: 2026-05-05 UTC

Question:

```text
Why did CVRP produce no promotions? Is this a Scion architecture problem, or
was the LLM's optimization space too small? Did warehouse promotions comply
with the v3/v0.4 framework design?
```

## Reference Frame

The controlling design source is `scion/design/scion-architecture-v3.md`.
The relevant v3 invariants are:

- LLM proposes; deterministic code decides.
- Contract, Verification, Protocol, and Decision are separate control surfaces.
- Decision reads only structured features, not free-text LLM rationale.
- Promotion requires screening -> validation -> frozen evidence.
- Champion is a pool-level immutable snapshot.
- Runtime and wall-clock failures are gateable evidence, not skipped noise.
- Branches are hypothesis directions, not just Git diffs.

The relevant v0.4 additions are:

- runtime/algorithm efficiency is a first-class promotion constraint;
- CVRP uses adapter-defined objective comparison:
  `fleet_violation -> total_distance`;
- BKS/gap is final evidence, not promotion evidence;
- CVRP is exposed through problem-owned research surfaces;
- the Scion core must remain problem-agnostic.

## Verdict

CVRP's zero-promotion result is **not primarily a failure of the v3 Scion
architecture**. The v3 governance loop did what it was supposed to do:
generated candidates went through contract, verification, protocol evaluation,
runtime accounting, and deterministic screening decisions.

The primary cause is that **this CVRP research object exposed too small and too
late an optimization surface to the LLM through its problem package**:

```text
strong ALNS+VNS baseline
-> generated operators run only after that baseline
-> most generated moves have no remaining improving move
-> evidence becomes tie-dominated
-> screening never advances to validation
```

This is an issue at the **problem research-surface boundary**, not a core
Decision/Protocol architecture issue and not a reason to put VRP algorithm
knowledge into Scion. Scion is the framework; warehouse and CVRP are research
objects. Each problem package must expose the heuristic algorithm surfaces that
Scion may govern. For warehouse, operators are close to the research object's
algorithm. For CVRP, the currently exposed post-baseline operators are only a
small tail-end polish layer.

## CVRP Evidence

CVRP completed 50 rounds and 40 protocol experiments:

| Signal | Value |
| --- | ---: |
| Protocol pairs | 952 |
| Valid pairs | 951 |
| Failed pairs | 1 |
| Wins | 53 |
| Losses | 42 |
| Ties/no metric delta | 857 |
| Candidate operator attempts | 956 |
| Accepted candidate operator moves | 21 |
| Pairs with accepted candidate move | 21 |
| Candidate operator errors | 0 |
| Candidate invalid outputs | 0 |
| Candidate runtime timeout pairs | 1 |

The dominant pattern is not crash or invalid code. It is lack of useful
post-baseline movement:

```text
935 operator-loaded pairs stopped at operator_stop_reason=no_improvement_round
914 pairs attempted operators but accepted no move
21 pairs accepted a move; all 21 were wins, but this is only 21/952 pairs
```

The accepted-move signal proves the operator boundary can affect objective
values. The problem is that the effect is sparse and too small to clear
screening.

## Why "LLM Quality" Is Secondary

The LLM did make some weak proposals:

- 4 patch/hypothesis contract failures;
- 2 heavy verification failures;
- repeated conventional local-search families;
- several policy ideas blocked by novelty.

But these are not the main explanation. Most evaluated candidates were valid:

- contract and verification passed for 40 evaluated experiments;
- generated operators loaded;
- runtime metrics were complete;
- operator errors and invalid outputs were zero in referenced screening
  metrics.

The LLM mostly produced standard bounded VRP neighborhoods: relocate, 2-opt,
2-opt*, Or-opt, swaps, ruin/recreate, depot-distance reinsertion, etc. These
are not irrational. They are simply weak when applied after a strong ALNS+VNS
baseline has already spent about 8 seconds of a 10-second solve budget.

## Why the Search Space Was Too Small

The current CVRP surfaces were:

```text
route_local      -> post-baseline operator file
route_pair       -> post-baseline operator file
ruin_recreate    -> post-baseline operator file
search_policy    -> baseline/operator budget and post-baseline enablement
```

This gives the LLM no direct control over the main algorithmic levers of the
CVRP research object:

- no destroy/repair portfolio selection;
- no adaptive neighborhood weighting;
- no acceptance policy;
- no restart/perturbation policy;
- no construction heuristic;
- no internal local-search schedule;
- no instance-size-specific component portfolio;
- no safe way to edit `solver.py`, by design.

The one evaluated `search_policy` branch changed budget allocation to
`baseline_time_fraction=0.92` and `operator_round_limit=8`. It reached
screening, but failed with:

```text
win_rate = 0.125
median_delta = 0.0
runtime_ratio_median = 1.145
runtime_regression_rate = 1.0
```

Four later `search_policy` attempts were stopped by `C10_novelty` because the
novelty key collapsed every singleton policy edit to:

```text
(search_policy, modify, policies/search_policy.py)
```

That is a real framework limitation for singleton policy surfaces. It
prematurely reduced the already-small research-object search space.

## Why This Is Not a Core Protocol Failure

The Decision Layer behaved conservatively:

- 39 CVRP decisions abandoned on `SCREENING_FAIL_WIN_RATE`;
- 1 abandoned on `CANDIDATE_RUNTIME_FAILURE` in DB lineage;
- no candidate reached validation;
- no candidate consumed frozen holdout budget;
- no incomplete evidence promoted.

This matches v3/v0.4 governance. The promotion gates did not falsely promote a
weak or incomplete CVRP candidate. The cost of this correctness is visible:
when the exposed search space is too weak, the campaign will produce no
promotions.

## What Would Be an Architecture Problem

It would be a core Scion architecture defect if any of these happened:

- LLM free text directly caused promotion;
- validation/frozen case details leaked into proposal context;
- runtime timeout pairs were skipped as ties;
- candidate code bypassed adapter feasibility/objective recomputation;
- screening evidence promoted without frozen holdout;
- warehouse-specific fallback made CVRP appear to work.

The analyzed artifacts do not show those failures in this run.

There are still framework defects, but they are evidence/observability and
surface-model defects:

- singleton policy novelty is too coarse;
- CVRP final state leaves one residual `explore` branch after max-round stop;
- summary reason codes should expose candidate runtime failure directly;
- final evidence refs are missing, so the run is not formal-ready;
- unreferenced scratch metrics need separation from evidence metrics.

## Warehouse Promotion Validity

Warehouse promotions were valid under the implemented protocol and consistent
with the v3/v0.4 governance model.

Warehouse protocol:

```text
screening win_rate_min = 0.60
validation win_rate_min = 0.66 and bootstrap_ci_low >= 0
frozen requires bootstrap_ci_low >= 0 and canary_required = true
statistical unit = case
frozen max uses per campaign = 3
```

### Promotion 1: `subcategory_cross_move.py`

| Stage | Decision | Win rate | Median delta | CI | Failed pairs |
| --- | --- | ---: | ---: | --- | ---: |
| screening | `queue_validate` | 0.600 | 1.75 | `[0.0, 6.0]` | 0 |
| validation | `queue_frozen` | 1.000 | 12.0 | `[4.0, 21.5]` | 0 |
| frozen | `promote` | 1.000 | 15.0 | `[7.0, 42.0]` | 0 |

Frozen raw metrics were complete: 12/12 valid pairs, 12 wins.

### Promotion 2: `subcategory_intra_repack.py`

| Stage | Decision | Win rate | Median delta | CI | Failed pairs |
| --- | --- | ---: | ---: | --- | ---: |
| screening | `queue_validate` | 0.600 | 1.0 | `[0.0, 4.0]` | 0 |
| validation | `queue_frozen` | 0.833 | 7.0 | `[1.0, 19.0]` | 0 |
| frozen | `promote` | 1.000 | 11.5 | `[1.0, 23.0]` | 0 |

Frozen raw pairs were 11 wins and 1 loss, but the protocol's statistical unit
is case, not pair. The case-level frozen result passed.

### Promotion 3: `subcategory_rightsize_offload.py`

| Stage | Decision | Win rate | Median delta | CI | Failed pairs |
| --- | --- | ---: | ---: | --- | ---: |
| screening expanded | `queue_validate` | 0.563 | 0.5 | `[0.0, 2.0]` | 0 |
| validation expanded | `queue_frozen` | 0.900 | 4.0 | `[1.0, 8.5]` | 0 |
| frozen | `promote` | 1.000 | 2.5 | `[1.0, 10.0]` | 0 |

The screening value is below `0.60`, but this is not an unregistered leak. The
DecisionEngine has an explicit rule:

```text
if wr in [threshold - 0.05, threshold)
and screening_expand_count >= 1
and median_delta >= 0
then queue_validate with SCREENING_EXPAND_EXHAUSTED_BORDERLINE
```

For this candidate:

```text
threshold = 0.60
threshold - 0.05 = 0.55
wr = 0.5625
median_delta = 0.5
```

So validation was a valid adjudication step, and frozen ultimately confirmed
the candidate.

## Warehouse Caveats

The promotion trajectory is valid, but auditability still has gaps:

- promoted champion rows have `promotion_experiment_id=NULL`;
- code-generation timeouts are not as queryable as protocol events;
- final evidence refs are absent, so the campaign is not final formal quality
  evidence;
- async weight optimization discard/commit is correct but should be summarized
  more directly.

These caveats do not invalidate the three warehouse promotions. They are
evidence-lineage and closeout issues.

## Design Implication

The next design step should be described generically as:

```text
operator design optimization
is a subset of
heuristic algorithm research-surface optimization
```

Do not discard the existing operator work. Keep operator surfaces for local
polishing, controlled fixtures, and algorithm components. But for research
objects where operator files are not the full algorithm, add problem-owned
surfaces that expose the main search mechanism safely. In the CVRP package,
candidate examples are:

- `neighborhood_portfolio.py`;
- `destroy_repair_policy.py`;
- `acceptance_restart_policy.py`;
- `construction_policy.py`;
- richer instance-size-aware `search_policy.py`;
- possibly a bounded ALNS component scheduler.

The Scion core should remain unchanged in spirit: it should govern research
surfaces, not contain VRP or warehouse logic. The problem package should expose
richer surfaces with contracts and verification hooks.
