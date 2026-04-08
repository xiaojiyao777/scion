# Scion Operator Quality Analysis Report

**Date**: 2026-04-08  
**Scope**: Campaign B (10 rounds), with cross-reference to full codebase  
**Author**: Automated analysis (Cris)

---

## Executive Summary

LLM-generated operators consistently fail to beat the champion solver (clustering at ~0.50 win rate) due to a **confluence of three root causes**, ranked by severity:

1. **🔴 CRITICAL — Attribute Name Bug**: Nearly all generated "subcategory-aware" operators reference `order.subcategory` which **does not exist** on the `Order` dataclass. The actual field is `order.vehicle_subcategory`. The `getattr(order, 'subcategory', None)` pattern silently returns `None`/fallback, causing the entire subcategory-targeting logic to be effectively dead code.

2. **🟠 HIGH — Hypothesis Homogeneity**: 5 of 7 generated operators (SubcategorySplitRepair, SubcategoryAwareMove, SubcategoryConsolidate, CategoryAwareDestroyRebuild, SubcategoryGatherMove) all target the same mechanism — consolidating subcategory splits via order relocation. They are algorithmically near-identical, differing only in traversal order. The LLM generates superficially different hypotheses that collapse to the same strategy.

3. **🟡 MEDIUM — Missing Structural Understanding**: The LLM doesn't understand *why* splits exist in the greedy init (subcategory grouping + capacity bin-packing creates splits at bin boundaries), nor does it understand the VNS dynamics (pool of 40 solutions, 200 iterations, acceptance = strict dominance). This leads to operators that don't exploit the actual improvement opportunities.

---

## A. Hypothesis Quality Assessment

### A.1 Hypotheses Are Repetitive, Not Novel

| Round | Operator | Core Mechanism |
|---|---|---|
| 1 | SubcategorySplitRepair | Move minority-category orders out of mixed-category vehicles |
| 2 | RegionAwareMerge | Merge same-region, same-category vehicle pairs |
| 3 | SubcategoryAwareMove | Move subcategory misfits to matching vehicles |
| 4 | SubcategoryConsolidate | Gather orphan subcategory orders to majority vehicle |
| 5 | CategoryAwareDestroyRebuild | Destroy-rebuild with subcategory-aware greedy reinsertion |
| 6 | SubcategoryGatherMove | Same as #4 — gather scattered subcategory orders |
| 7 | SmartCostMerge | Merge vehicle pairs maximizing cost savings |

**Pattern**: Rounds 1, 3, 4, 5, 6 are all variants of "find subcategory-split orders → move to matching vehicle." The LLM is stuck in a single conceptual basin.

### A.2 Objective Function Understanding

The LLM correctly identifies the lexicographic ordering (splits > cost > time) and consistently targets the first objective. However:

- It does not understand that `subcategory_splits = Σ(|vehicles_per_subcategory| - 1)`, so reducing splits requires consolidating **subcategories into fewer vehicles**, not categories.
- **Round 1 (SubcategorySplitRepair)** actually targets `vehicle_category` (大类), not `vehicle_subcategory` (小类). This is a misunderstanding of the objective — category isolation is a *feasibility constraint* (H4), not an objective. The greedy init already satisfies H4 by design.
- Several operators conflate "subcategory" with "category" in their logic.

### A.3 Missing Innovation Directions

The LLM never proposes:
- **Pickup-point consolidation** (H3 constraint exploitation: fewer vehicles visiting the same pickup points)
- **Amount-limit-aware rebalancing** (H6 constraint: moving orders between vehicles to free up declaration amount headroom)
- **Multi-order swap/chain moves** (2-opt, 3-opt style order chain relocations)
- **Vehicle type downgrade chains** (merge 2 T5s into 1 T10 + cascading downgrades)
- **Urgency-aware grouping** (consolidating urgent orders to minimize split impact)
- **Adaptive weight adjustment operators** (operators that modify their own selection probability)

---

## B. Code Quality Assessment

### B.1 The Fatal `subcategory` vs `vehicle_subcategory` Bug

**Affected operators**: SubcategoryAwareMove, SubcategoryConsolidate, SubcategoryGatherMove, CategoryAwareDestroyRebuild

All use patterns like:
```python
subcat = getattr(order, "subcategory", None) or ""
# or
subcat = getattr(order, 'subcategory', None) or getattr(order, 'vehicle_category', '')
```

The `Order` dataclass has `vehicle_subcategory: int` (an integer), not `subcategory`. So:
- `getattr(order, "subcategory", None)` → **always returns `None`**
- The fallback `or ""` or `or getattr(order, 'vehicle_category', '')` means the operator either groups everything into one bucket (empty string) or uses category (大类) as proxy

**Impact**: The operators' subcategory-aware logic is **completely inoperative**. They degenerate into random order moves, explaining the ~0.50 WR (equivalent to random perturbation).

### B.2 SmartCostMerge Uses `order.subcategory` Too

```python
subcategories = set(o.subcategory for o in orders if hasattr(o, 'subcategory'))
```
Since `Order` has no `subcategory` attribute, `hasattr` returns False, so `subcategories` is always an empty set. The operator still functions for cost optimization because its merge logic doesn't depend on subcategories, which is why it achieved the highest WR (0.625).

### B.3 SubcategorySplitRepair Targets the Wrong Thing

This operator looks for vehicles with multiple `vehicle_category` values. But the greedy init already groups by `(vehicle_category, vehicle_subcategory, pickup_city)` — vehicles almost never have mixed categories. The operator fires rarely and when it does, it's fixing a non-existent problem.

### B.4 RegionAwareMerge — Actually Functional

This is the only generated operator that works approximately as intended. It merges same-region, same-category vehicle pairs by utilization rate. It achieved WR 0.609 because:
- It doesn't depend on the broken `subcategory` attribute
- It genuinely reduces vehicle count (improving cost)
- But it can *increase* subcategory splits when merging vehicles from different subcategories, which limits its win rate

### B.5 General Code Quality Issues

1. **Redundant `_select_vehicle_type`**: Every generated operator reimplements this static method identically. The champion already has `select_minimum_vehicle_type()` in `models.py`.

2. **Incomplete feasibility checks**: Some operators check capacity and region but skip:
   - H3 pickup point limits (max 2 in Dongguan, 3 in Shenzhen)
   - H6 amount limits (declaration amount per destination×shipping combination)
   - This means they may produce moves that pass the operator's internal check but fail the oracle's `check_feasibility`, causing the VNS to discard the move.

3. **Inefficient deep_copy placement**: SubcategoryAwareMoveOrder calls `solution.deep_copy()` inside a loop (per candidate), wasting time when most candidates fail.

4. **`getattr` with fallback is an anti-pattern**: The LLM uses `getattr(order, 'subcategory', None)` suggesting it's *uncertain* about the field name. A well-informed LLM would use `order.vehicle_subcategory` directly.

---

## C. Context Gaps Analysis

### C.1 Missing: Data Model Field Names

**This is the root cause of the attribute bug.** The LLM sees:
- Champion operator code (which uses `order.vehicle_category` and `order.vehicle_subcategory`)
- The Operator Interface Spec (which mentions `Solution`, `Vehicle`, `Order` but only describes them at a high level)

The interface spec says:
```
- `Order`: `order_id`, `locked_vehicle_id` (None = freely assignable), `hazard_flag`, `spu_list`, etc.
```

The **`etc.`** hides critical fields: `vehicle_category`, `vehicle_subcategory`, `pickup_name`, `pickup_city`, `declaration_amount`, `ship_method`, `destination_country`. The LLM has to *infer* field names from champion code examples. It sees `order.vehicle_category` in champion code but never sees `order.vehicle_subcategory` used explicitly (the oracle uses it via `instance.orders[oid].vehicle_subcategory` but the oracle is frozen and not shown).

**Fix**: Add complete `Order` field listing to the operator interface spec.

### C.2 Missing: Objective Function Formula

The problem description says "minimise subcategory splits" but never shows the formula:
```python
subcategory_splits = sum(len(vehicles) - 1 for vehicles in subcategory_to_vehicles.values())
```

The LLM doesn't know that splits are counted per **subcategory across all vehicles**, not per vehicle. This would fundamentally change operator design — the goal is to consolidate orders of the same `vehicle_subcategory` into the fewest possible vehicles.

**Fix**: Show the exact objective computation from `oracle.py:recompute_objective()`.

### C.3 Missing: Greedy Init Logic

The LLM doesn't see how the initial solution is constructed:
- Groups by `(vehicle_category, vehicle_subcategory, pickup_city)`
- Greedy bin-packing within each group
- Splits occur when a subcategory group overflows a single vehicle's capacity

Understanding this reveals that:
- Splits are **structural** — caused by capacity overflow at subcategory boundaries
- To reduce splits, you need to either: (a) fit more orders per vehicle (merge within subcategory), or (b) rebalance across subcategory groups
- Random order moves are unlikely to improve splits because they don't target the structural cause

**Fix**: Include a summary of greedy_init logic and where splits originate.

### C.4 Missing: VNS Acceptance Mechanics

The prompt doesn't explain:
- Pool of 40 solutions, updated each iteration
- **Strict lexicographic dominance** for pool entry — a new solution must beat existing pool members on `(splits, cost, time)` tuple to survive
- 200 iterations × 40 solutions = 8,000 operator invocations per solve
- `check_feasibility` rejects infeasible candidates, reverting to the original

This means:
- An operator that produces slightly *worse* solutions 60% of the time but dramatically *better* solutions 5% of the time is valuable (the pool filters)
- An operator that always produces marginal changes is useless (overwhelmed by noise)
- The LLM doesn't know it needs to produce **high-variance, occasionally excellent** moves

**Fix**: Add VNS dynamics summary to hypothesis context.

### C.5 Missing: Concrete Solution Example

The LLM never sees what a solution actually looks like. A small example showing:
```
Instance: 8 orders, 3 subcategories
Greedy solution: 4 vehicles, 2 splits
After optimal moves: 3 vehicles, 0 splits, cost reduced by 1200
```
...would dramatically improve the LLM's ability to reason about operator design.

**Fix**: Include a worked example in the problem summary.

### C.6 Missing: Instance Statistics Context

The LLM doesn't know:
- How many orders are in each screening instance (16-80)
- How many subcategories exist (affects split reduction opportunity)
- What fraction of orders are locked (limits operator applicability)
- Typical vehicle counts and utilization rates

---

## D. Prompt Improvement Recommendations

### D.1 — Add Complete Order Dataclass to Interface Spec

**Before** (current):
```
- `Order`: `order_id`, `locked_vehicle_id` (None = freely assignable), `hazard_flag`, `spu_list`, etc.
```

**After**:
```
- `Order` fields (complete):
  - `order_id: str` — unique identifier
  - `vehicle_category: int` — 分车大类 (H4 constraint: same vehicle must have same category)
  - `vehicle_subcategory: int` — 分车小类 (objective: minimize splits of this across vehicles)
  - `urgent: bool`
  - `hazard_flag: bool` — if True, requires HQ40_DG vehicle when hazard_quantity > 1800
  - `hazard_quantity: int` — hazardous goods quantity (pcs)
  - `pickup_name: str` — pickup point name (H3 constraint: max per vehicle)
  - `pickup_city: str` — "Dongguan" or "Shenzhen" (H2 constraint: same region per vehicle)
  - `declaration_amount: float` — customs declaration amount (H6 constraint)
  - `lsp: str` — logistics service provider
  - `ship_method: str` — shipping method (H6 grouping key with destination_country)
  - `destination_country: str` — destination country (H6 grouping key with ship_method)
  - `spu_list: list[SPU]` — packing units, use calc_pallets() to compute pallet count
  - `locked_vehicle_id: Optional[str]` — None = freely assignable, otherwise must stay in this vehicle
```

### D.2 — Add Objective Function Formula

Add to the problem summary:
```
### Objective Function (lexicographic, minimize all)
1. subcategory_splits: For each unique vehicle_subcategory value, count how many 
   vehicles contain orders of that subcategory, subtract 1, sum over all subcategories.
   Formula: sum(len(set(assignment[oid] for oid in orders if orders[oid].vehicle_subcategory == sc)) - 1 for sc in all_subcategories)
2. total_cost: sum of VEHICLE_TYPES[v.vehicle_type].cost for all non-empty vehicles
3. solve_time_ms: wall-clock solve time
```

### D.3 — Add Greedy Init Summary

Add to hypothesis context:
```
### How the Initial Solution is Built (greedy_init)
Orders are grouped by (vehicle_category, vehicle_subcategory, pickup_city).
Within each group, orders are packed greedily into vehicles (first-fit decreasing).
When a vehicle reaches capacity, a new vehicle is opened.
Subcategory splits occur when a subcategory group requires more than one vehicle.

Key insight: to reduce splits, you must either:
- Move orders so an entire subcategory fits in fewer vehicles
- Merge partially-filled vehicles that share a subcategory
- Split a large vehicle's load across subcategory boundaries more efficiently
```

### D.4 — Add VNS Solver Dynamics

Add to hypothesis context:
```
### How the VNS Solver Uses Operators
- Maintains a pool of 40 candidate solutions (sorted by objective)
- Each iteration: for each solution in pool, randomly select one operator (weighted), apply it
- Feasibility check: if the new solution violates any constraint, it is DISCARDED (reverts to original)
- Pool update: new 40 + old 40 merged, top 40 by lexicographic objective kept
- Runs for 200 iterations or until 30 consecutive iterations with no improvement
- Total: ~8000 operator applications per solve

Implications for operator design:
- Operators should produce FEASIBLE solutions (infeasible = wasted computation)
- High variance is good: the pool filters bad outcomes, keeping rare good ones
- Operators should be complementary to existing ones, not duplicate their function
- An operator that improves splits even 5% of the time is valuable if the improvement is large
```

### D.5 — Add Concrete Worked Example

Add to problem summary:
```
### Example: Small Instance
Instance: 6 orders across 2 subcategories (A: 4 orders, B: 2 orders)
Vehicle capacity: 3 orders each

Greedy init result:
  Vehicle 1: [A1, A2, A3]  → subcategory A
  Vehicle 2: [A4, B1, B2]  → mixed! subcategory A split across V1+V2, B in V2
  Splits: subcat_A uses 2 vehicles (split=1), subcat_B uses 1 vehicle (split=0) → total=1

Better solution:
  Vehicle 1: [A1, A2, A3]  → subcategory A
  Vehicle 3: [A4]          → subcategory A (new smaller vehicle)
  Vehicle 2: [B1, B2]      → subcategory B
  Splits: 1 (A still split), but cost may be lower with smaller vehicle type for A4

Optimal solution (if capacity allows):
  Vehicle 1: [A1, A2, A3, A4]  → subcategory A (upgrade to HQ40)
  Vehicle 2: [B1, B2]          → subcategory B
  Splits: 0, cost = HQ40 + T5
```

### D.6 — Improve Experiment History Feedback

Current feedback shows win/loss/tie per case but doesn't show **what objective component was decisive**. The `dominant_decisive_objective` field exists but the LLM doesn't know how to interpret it in context.

Add to experiment history rendering:
```
Case medium_2: LOSS (splits increased by 1, cost decreased by 200)
  → The operator improved cost but hurt the PRIMARY objective (splits).
  → Lesson: any operator that increases splits will lose, even if cost improves dramatically.
```

### D.7 — Guide Toward "Modify" Actions

The current prompt defaults to `create_new` for every round. After 3+ failed create_new attempts targeting the same mechanism, the prompt should steer toward:
- `modify` an existing champion operator (e.g., make MoveOrder subcategory-aware)
- `remove` a poorly-performing operator to increase weight of good ones
- Combine two existing operators into a compound move

---

## E. Experiment History Feedback Quality

### E.1 Case-Level Feedback

The feedback system provides rich per-case data:
```
medium_2: loss (W/L/T=0/2/0, consistency=1.00)
  decisive=business_aggregation  deltas: splits=+1.0, cost=-200.0  size=medium
```

**Issues**:
1. `decisive=business_aggregation` is confusing — this appears to be an internal label for the splits objective. Should be renamed to `subcategory_splits` for clarity.
2. The delta signs are unintuitive: `splits=+1.0` means splits *increased* (bad), but the LLM may not realize positive=bad for a minimization objective.
3. **The LLM doesn't know absolute values** — if champion has 0 splits, any operator that touches subcategory grouping will likely increase splits. This context is missing.

### E.2 Pattern Summary

The pattern summary provides:
```
pattern: cases=8 win=1 loss=4 mixed=3
  wins by objective: {subcategory_splits: 1}
  losses by objective: {subcategory_splits: 3, total_cost: 1}
```

This is useful but should be augmented with:
- Champion's current objective values per case (so LLM knows the baseline)
- Whether the champion already has 0 splits on some cases (meaning no improvement possible on that objective)

---

## F. Answers to Key Questions

### F.1 Why is medium_2 always tied?

`medium_2` has 30 orders across 8 subcategories. With the greedy init grouping by `(category, subcategory, city)`, each subcategory group likely fits neatly into 1-2 vehicles. The champion solver's VNS with 200 iterations is already converging to near-optimal for this instance size. Any operator perturbation either:
- Produces an equivalent solution (tie) because the solution is already at a local optimum
- Produces a worse solution that gets filtered by the pool

**Root cause**: medium_2 is already well-solved by the champion; the improvement ceiling is near zero.

**Recommendation**: Add larger instances (100+ orders) to screening where the champion has more room for improvement, or verify by running the champion with different seeds to measure objective variance.

### F.2 Why do operators cluster at 0.50 WR?

Three factors combine:
1. **The subcategory bug**: Most operators' targeting logic is dead code, making them equivalent to random perturbation
2. **The champion is already good**: On small/medium instances, 200 VNS iterations with 6 well-tuned operators find near-optimal solutions
3. **Adding an operator dilutes others**: Adding a 7th operator to the pool reduces the invocation frequency of the 6 champion operators. If the new operator is no better than random, the solver gets worse through dilution alone.

A WR of 0.50 means "adding this operator is neutral" — the new operator's occasional improvements exactly offset the dilution cost. This is consistent with a broken operator that produces random perturbations.

### F.3 Should the LLM also try "modify"?

**Yes, strongly.** Modifying an existing operator is lower risk and higher leverage:
- Making `MoveOrder` subcategory-aware (prefer moves that reduce splits) would directly improve the primary objective
- Making `DestroyRebuild` subcategory-aware in its reinsertion phase would be high-impact
- Removing `SplitVehicle` (weight 1.0, rarely useful post-init) would give more iterations to other operators

The prompt should actively suggest modification as the preferred action after 2+ failed create_new attempts.

### F.4 Should we give the LLM a concrete solution example?

**Yes.** See recommendation D.5 above. The LLM currently reasons abstractly about "reducing splits" without understanding the mechanical structure of solutions. A worked example would:
- Clarify the objective function calculation
- Show what "split" means concretely
- Demonstrate what an effective operator move looks like
- Prevent the attribute naming bug (the example would use real field names)

### F.5 Is the operator interface too restrictive?

**No.** The `execute(solution, rng) -> Solution` interface is standard for metaheuristic operators and doesn't limit the design space. The restriction is appropriate because:
- It enforces determinism (via `rng`)
- It enables pool-based VNS
- It supports feasibility checking
- All champion operators use the same interface effectively

The real limitation is **information access**: operators can only see the `Solution` object but not the `Instance` directly in `execute()`. However, the `__init__` receives the `Instance`, so this is not actually limiting — the LLM just doesn't fully exploit the instance data.

---

## G. Prioritized Action Plan

| Priority | Action | Expected Impact | Effort |
|---|---|---|---|
| P0 | Add complete `Order` field listing to interface spec (D.1) | Eliminates attribute bug | Low |
| P0 | Add objective function formula (D.2) | Correct targeting of optimization objective | Low |
| P1 | Add greedy init summary (D.3) | LLM understands where splits originate | Low |
| P1 | Add VNS dynamics to hypothesis context (D.4) | Better operator design for pool-based search | Low |
| P1 | Add worked example (D.5) | Concrete understanding of solution structure | Medium |
| P2 | Improve experiment feedback clarity (D.6, E.1-E.2) | Better learning from failures | Medium |
| P2 | Guide toward "modify" after failed create_new (D.7) | Reduce hypothesis homogeneity | Low |
| P3 | Add champion objective values per screening case | LLM knows improvement ceiling | Medium |

**Estimated timeline**: P0 fixes alone should lift WR from ~0.50 to ~0.60+. Combined P0+P1 should enable WR ≥ 0.667 (screening threshold).
