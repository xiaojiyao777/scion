# Prompt Improvement Plan

**Date**: 2026-04-08  
**Companion document**: `operator-quality-analysis.md`

---

## Overview

This document contains specific, implementable prompt changes for the Scion framework's LLM proposal pipeline. Changes target `context_manager.py` and `engine.py`.

---

## Change 1: Complete Order Field Listing in Interface Spec

**File**: `scion/scion/proposal/context_manager.py`  
**Function**: `_build_operator_interface_spec()`  
**Priority**: P0 (eliminates the attribute name bug)

**Current** (truncated Key Data Structures section):
```
- `Order`: `order_id`, `locked_vehicle_id` (None = freely assignable), `hazard_flag`, `spu_list`, etc.
```

**Proposed replacement** — expand the Order description:
```python
### Key Data Structures (from models.py)
- `Solution`: contains `vehicles: dict[str, Vehicle]` and `assignment: dict[str, str]` (order_id → vehicle_id)
  - Call `solution.deep_copy()` to get a deep copy before modifying
  - `solution.remove_empty_vehicles()` to clean up empty vehicles in-place
- `Vehicle`: `vehicle_id`, `vehicle_type` (HQ40_DG|HQ40|T10|T5|T3), `region`, `order_ids: list[str]`
- `Order` (complete field list — use these exact names):
  - `order_id: str` — unique identifier
  - `vehicle_category: int` — 分车大类序号 (feasibility constraint H4: same vehicle must have same category)
  - `vehicle_subcategory: int` — 分车小类序号 (**PRIMARY optimization target**: minimize the number of vehicles each subcategory is spread across)
  - `urgent: bool` — urgency flag
  - `hazard_flag: bool` — True if order contains hazardous goods
  - `hazard_quantity: int` — hazardous goods quantity in pcs (>1800 requires HQ40_DG vehicle)
  - `pickup_name: str` — pickup point name (constraint H3: max pickups per vehicle)
  - `pickup_city: str` — "Dongguan" or "Shenzhen" (constraint H2: all orders in a vehicle must be same region)
  - `declaration_amount: float` — customs declaration amount (constraint H6)
  - `lsp: str` — logistics service provider
  - `ship_method: str` — shipping method (H6 key)
  - `destination_country: str` — destination country (H6 key)
  - `spu_list: list[SPU]` — packing units; use `calc_pallets(order.spu_list)` to compute pallet count
  - `locked_vehicle_id: Optional[str]` — None means freely assignable; non-None means order MUST stay in that vehicle
- `Instance`: accessed via `self.instance` (set in `__init__`); contains `orders: dict[str, Order]`, `amount_limits: dict[str, float]`
```

---

## Change 2: Add Objective Function Formula to Problem Summary

**File**: `scion/scion/proposal/context_manager.py`  
**Function**: `_build_problem_summary()`  
**Priority**: P0

**Add after the description line**:
```python
def _build_problem_summary(spec: ProblemSpec) -> str:
    lines = [
        f"Name: {spec.name}",
    ]
    if spec.description:
        lines.append(f"Description: {spec.description}")
    lines += [
        "",
        "### Objective Function (lexicographic — minimize all three in order):",
        "1. subcategory_splits: For each unique `vehicle_subcategory` value across all orders,",
        "   count how many distinct vehicles contain orders of that subcategory, subtract 1,",
        "   then sum over all subcategories.",
        "   Code: sum(len(set(assignment[oid] for oid if orders[oid].vehicle_subcategory == sc)) - 1 for sc in all_subcategories)",
        "2. total_cost: sum(VEHICLE_TYPES[v.vehicle_type].cost for all non-empty vehicles)",
        "   Vehicle costs: T3=800, T5=1200, T10=1800, HQ40=3300, HQ40_DG=6600",
        "3. solve_time_ms: wall-clock time (external, not operator-controlled)",
        "",
        "Key implication: ANY increase in subcategory_splits makes the solution strictly worse,",
        "regardless of cost improvement. Cost only matters when splits are equal.",
        "",
        f"Operator categories: {', '.join(spec.operator_categories)}",
        f"Editable files: {', '.join(spec.search_space.editable)}",
        f"Frozen files (do not modify): {', '.join(spec.search_space.frozen)}",
    ]
    return "\n".join(lines)
```

---

## Change 3: Add Greedy Init Summary to Hypothesis Context

**File**: `scion/scion/proposal/context_manager.py`  
**Function**: `_split_hypothesis_context()` in `engine.py`  
**Priority**: P1

**Add to the system block** (after champion stats):
```
### How the Initial Solution is Built
The greedy initializer groups orders by (vehicle_category, vehicle_subcategory, pickup_city).
Within each group, orders are packed sequentially into vehicles using first-fit.
When a vehicle reaches capacity (pallet limit), a new vehicle is opened for the same group.

Subcategory splits occur when a subcategory group's total pallets exceed one vehicle's capacity.
Example: if subcategory 3 has 50 pallets and HQ40 capacity is 40, it needs 2 vehicles → 1 split.

To reduce splits, an operator must consolidate orders so a subcategory fits in fewer vehicles.
This typically means: merging two partially-filled vehicles of the SAME subcategory,
or moving orders between vehicles to free up space for same-subcategory consolidation.
Random order moves between arbitrary vehicles are unlikely to improve splits.
```

---

## Change 4: Add VNS Dynamics to Hypothesis Context

**File**: `scion/scion/proposal/context_manager.py`  
**Function**: `_split_hypothesis_context()` in `engine.py`  
**Priority**: P1

**Add to the system block**:
```
### How the VNS Solver Uses Your Operator
- The solver maintains a pool of 40 candidate solutions, sorted by objective.
- Each iteration: for EACH solution in the pool, ONE operator is randomly selected 
  (weighted) and applied via `execute(solution, rng)`.
- If the result is INFEASIBLE (violates any hard constraint), it is DISCARDED and the 
  original solution is kept. Infeasible operators waste computation.
- Pool update: new solutions + old solutions merged, top 40 by lexicographic objective kept.
- Runs 200 iterations or until 30 consecutive no-improvement iterations.
- Total: ~8000 operator invocations per solve run.

Design implications:
- Your operator will be called ~1000 times per solve. It MUST produce feasible solutions.
- High variance is good: the pool filters bad outcomes and keeps rare great ones.
- A large improvement on 5% of calls is more valuable than a tiny improvement on 50%.
- Your operator competes with 6 existing operators for invocation share. It must provide 
  a capability the existing operators lack, not duplicate what they already do.
```

---

## Change 5: Add Worked Example to Problem Summary

**File**: `scion/scion/proposal/context_manager.py` or problem.yaml description  
**Priority**: P1

**Add to problem summary or as a separate context block**:
```
### Worked Example (Small Instance)
Instance: 6 orders, 2 regions (all Shenzhen), 2 subcategories
  Orders: A1(subcat=1, 8plt), A2(subcat=1, 6plt), A3(subcat=1, 10plt), 
          A4(subcat=1, 12plt), B1(subcat=2, 5plt), B2(subcat=2, 4plt)
  Vehicle types: T10(cap=14), HQ40(cap=40)

Greedy init (groups by subcategory, first-fit packing):
  V1[T10]: A1(8)+A2(6)=14plt → full
  V2[T10]: A3(10) → 10plt  (A4 won't fit: 10+12=22 > 14)
  V3[T10]: A4(12) → 12plt
  V4[T10]: B1(5)+B2(4)=9plt
  Objective: splits=2 (subcat 1 spans V1,V2,V3 → split=2; subcat 2 spans V4 → split=0)
             cost=4×1800=7200

Improved (merge subcat-1 vehicles into HQ40):
  V1[HQ40]: A1+A2+A3+A4 = 36plt
  V4[T10]: B1+B2 = 9plt
  Objective: splits=0, cost=3300+1800=5100 ✓ BETTER on both objectives

The key move: merging V2+V3 orders into V1 (upgrading V1 to HQ40). 
This is what a good subcategory-consolidation operator should do.
```

---

## Change 6: Steer Toward "Modify" After Repeated create_new Failures

**File**: `scion/scion/proposal/context_manager.py`  
**Function**: `_build_experiment_history()`  
**Priority**: P2

**Logic**: If the last 3+ rounds were all `create_new` with WR < 0.60, inject:
```
### ⚠️ Strategy Guidance
The last {N} rounds all used action="create_new" with limited success (best WR: {best}).
Consider a different approach:
- action="modify": Enhance an existing champion operator. For example, make MoveOrder 
  subcategory-aware (prefer moves that reduce subcategory splits).
- action="remove": Remove the weakest operator to increase invocation share of strong ones.
- Think about WHY existing operators are already good and what specific gap remains.
```

---

## Change 7: Improve Experiment Feedback Clarity

**File**: `scion/scion/proposal/context_manager.py`  
**Function**: `_render_case_feedback()`  
**Priority**: P2

**Current**:
```
medium_2: loss (W/L/T=0/2/0, consistency=1.00)
  decisive=business_aggregation  deltas: splits=+1.0, cost=-200.0
```

**Proposed**:
```
medium_2: LOSS (W/L/T=0/2/0, consistency=1.00)
  decisive_objective=subcategory_splits (splits increased by 1 → strictly worse)
  deltas: subcategory_splits=+1 (BAD: increased), total_cost=-200 (good but irrelevant since splits worse)
  lesson: improving cost at the expense of splits always loses in lexicographic comparison
```

---

## Change 8: Add Champion Baseline Values to Screening Cases

**File**: `scion/scion/proposal/context_manager.py`  
**Function**: `_build_experiment_history()` or new helper  
**Priority**: P2

**Add to case feedback**:
```
Champion baseline for this case: splits=0, cost=5100
  → splits are already optimal! Only cost improvements can win on this case.
```

This prevents the LLM from wasting effort on split reduction for already-optimal cases.

---

## Implementation Order

1. **Immediate (before next campaign)**: Changes 1 + 2 (P0 — fix the attribute bug + objective formula)
2. **Next iteration**: Changes 3 + 4 + 5 (P1 — structural understanding)
3. **Refinement**: Changes 6 + 7 + 8 (P2 — feedback quality)

## Expected Impact

- **P0 alone**: Fix the dead-code bug → generated operators actually target subcategory splits → WR improvement from ~0.50 to ~0.60
- **P0 + P1**: Structural understanding → operators designed for the VNS pool dynamics → WR ~0.65-0.70
- **Full stack**: Reduced hypothesis homogeneity + better learning → sustainable innovation across rounds
