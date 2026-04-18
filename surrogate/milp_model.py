"""
MILP 模型构建器（纯函数）

按 scion/docs/milp-model.md §2-§4 实现变量/约束/目标函数。
"""

from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import Optional

import pulp

# Ensure surrogate/ directory is in sys.path so sibling modules resolve
_surrogate_dir = Path(__file__).parent
if str(_surrogate_dir) not in sys.path:
    sys.path.insert(0, str(_surrogate_dir))

from models import (
    Instance,
    Solution,
    Vehicle,
    VEHICLE_TYPES,
    calc_pallets,
    get_region,
    get_max_pickups,
)

# Ordered list of vehicle type codes (must be consistent everywhere)
VEHICLE_TYPE_LIST: list[str] = ["HQ40_DG", "HQ40", "T10", "T5", "T3"]

# Hazmat threshold (pcs) above which HQ40_DG is mandatory
H_MAX: int = 1800


# ---------------------------------------------------------------------------
# K and locked-slot computation
# ---------------------------------------------------------------------------

def compute_K(instance: Instance) -> int:
    """Compute vehicle-slot upper bound K per §6.3.

    K = ceil(sum(p_i) / min_cap) + locked_count, capped at n.
    min_cap = 3 (T3).
    """
    total_pallets = sum(
        calc_pallets(o.spu_list) for o in instance.orders.values()
    )
    locked_ids = {
        o.locked_vehicle_id
        for o in instance.orders.values()
        if o.locked_vehicle_id is not None
    }
    L = len(locked_ids)
    K = math.ceil(total_pallets / 3) + L
    K = min(K, len(instance.orders))
    return max(K, max(L + 1, 1))


def build_locked_slot_map(instance: Instance) -> dict[str, int]:
    """Map each unique locked_vehicle_id → slot index (0-based).

    Locked groups occupy the first L slots (0, 1, …, L-1).
    The order of group assignment follows insertion order of orders.
    """
    locked_groups: dict[str, int] = {}
    slot = 0
    for o in instance.orders.values():
        if o.locked_vehicle_id is not None and o.locked_vehicle_id not in locked_groups:
            locked_groups[o.locked_vehicle_id] = slot
            slot += 1
    return locked_groups


# ---------------------------------------------------------------------------
# MILP builder
# ---------------------------------------------------------------------------

def build_milp(
    instance: Instance,
    K: int,
    locked_slot_map: dict[str, int],
    symmetry_breaking: bool = True,
    phase2_sum_alpha_star: Optional[int] = None,
) -> tuple[pulp.LpProblem, dict]:
    """Build and return the MILP problem.

    Parameters
    ----------
    instance : Instance
        Problem data.
    K : int
        Number of vehicle slots.
    locked_slot_map : dict[str, int]
        Maps locked_vehicle_id → slot index.
    symmetry_breaking : bool
        If True, add y_j ≥ y_{j+1} for free (unlocked) slots.
    phase2_sum_alpha_star : int or None
        None  → Phase 1 (minimise subcategory spread).
        value → Phase 2 (fix α-sum = value, minimise cost).

    Returns
    -------
    (prob, vars_dict)  prob is the PuLP LpProblem; vars_dict contains all
    decision-variable dicts plus derived index structures needed for
    solution extraction.
    """
    is_phase2 = phase2_sum_alpha_star is not None
    prob_name = "phase2" if is_phase2 else "phase1"
    prob = pulp.LpProblem(f"vehicle_alloc_{prob_name}", pulp.LpMinimize)

    # -----------------------------------------------------------------------
    # Index structures
    # -----------------------------------------------------------------------
    orders: list = list(instance.orders.values())
    I: list[int] = list(range(len(orders)))   # order indices
    J: list[int] = list(range(K))             # slot indices
    T: list[str] = VEHICLE_TYPE_LIST          # vehicle type codes

    S: list[int] = sorted({o.vehicle_subcategory for o in orders})
    C: list[int] = sorted({o.vehicle_category for o in orders})
    R: list[str] = sorted({get_region(o.pickup_city) for o in orders})
    P: list[str] = sorted({o.pickup_name for o in orders})
    G: list[str] = sorted({
        f"{o.destination_country},{o.ship_method}" for o in orders
    })

    # Lookup: pickup_name → region
    pickup_to_region: dict[str, str] = {
        o.pickup_name: get_region(o.pickup_city) for o in orders
    }

    # Per-region pickup lists
    pickups_by_region: dict[str, list[str]] = {r: [] for r in R}
    for p in P:
        r = pickup_to_region.get(p)
        if r is not None:
            pickups_by_region[r].append(p)

    # Pre-compute order parameters (avoid repeated function calls inside loops)
    pallets: dict[int, int] = {i: calc_pallets(orders[i].spu_list) for i in I}
    order_region: dict[int, str] = {i: get_region(orders[i].pickup_city) for i in I}
    order_subcat: dict[int, int] = {i: orders[i].vehicle_subcategory for i in I}
    order_cat: dict[int, int] = {i: orders[i].vehicle_category for i in I}
    order_pickup: dict[int, str] = {i: orders[i].pickup_name for i in I}

    # Indices grouped by subcat / category
    orders_by_subcat: dict[int, list[int]] = {s: [] for s in S}
    for i in I:
        orders_by_subcat[order_subcat[i]].append(i)

    orders_by_cat: dict[int, list[int]] = {c: [] for c in C}
    for i in I:
        orders_by_cat[order_cat[i]].append(i)

    orders_by_pickup: dict[str, list[int]] = {p: [] for p in P}
    for i in I:
        orders_by_pickup[order_pickup[i]].append(i)

    orders_by_region: dict[str, list[int]] = {r: [] for r in R}
    for i in I:
        orders_by_region[order_region[i]].append(i)

    # Hazmat
    total_hazard_sum: int = sum(
        orders[i].hazard_quantity for i in I if orders[i].hazard_flag
    )
    M_H: int = total_hazard_sum + 1  # big-M for hazmat constraint (§4.5)

    # -----------------------------------------------------------------------
    # Preprocessing: compute infeasible (i, t) and (i, j) combinations
    # -----------------------------------------------------------------------
    # Optimization B: fix variables known to be infeasible a priori, shrinking
    # the MILP and tightening LP relaxation without adding constraints.

    # (i, t) infeasibility:
    #   - single-order pallets exceed vehicle type capacity → cannot fit even
    #     as sole occupant of that slot type
    #   - hazmat orders (hazard_flag=True) require HQ40_DG; all other types
    #     are infeasible when hazard_quantity > H_MAX (enforced exactly by H8;
    #     we tighten via preprocessing for single-order-only cases)
    order_infeasible_types: dict[int, set[str]] = {i: set() for i in I}
    for i in I:
        p_i = pallets[i]
        h_i = orders[i].hazard_quantity if orders[i].hazard_flag else 0
        for t in T:
            cap_t = VEHICLE_TYPES[t].capacity
            # single-order capacity check
            if p_i > cap_t:
                order_infeasible_types[i].add(t)
                continue
            # hazmat check: single order with h_i > H_MAX can only go on HQ40_DG
            if h_i > H_MAX and t != "HQ40_DG":
                order_infeasible_types[i].add(t)

    # (i, j) hard constraints from locked assignment:
    #   - locked order i MUST be on slot locked_slot_map[lock_id]
    #   - so x[i, j] = 0 for all other j
    # This is redundant with H7 (x[i, slot]=1 forces others=0 via C0a) but
    # fixing variables upfront shrinks the MILP dramatically.
    forced_x_one: list[tuple[int, int]] = []
    forced_x_zero: list[tuple[int, int]] = []
    locked_slots_set: set[int] = set(locked_slot_map.values())
    order_locked_slot: dict[int, int] = {}
    for i in I:
        o = orders[i]
        if o.locked_vehicle_id is not None:
            j_locked = locked_slot_map[o.locked_vehicle_id]
            order_locked_slot[i] = j_locked
            forced_x_one.append((i, j_locked))
            for j in J:
                if j != j_locked:
                    forced_x_zero.append((i, j))
        else:
            # non-locked orders cannot go on locked slots (those are reserved)
            for j in locked_slots_set:
                forced_x_zero.append((i, j))

    # -----------------------------------------------------------------------
    # Decision Variables
    # -----------------------------------------------------------------------

    # x[i,j] ∈ {0,1}: order i → slot j
    x = pulp.LpVariable.dicts(
        "x", [(i, j) for i in I for j in J], cat="Binary"
    )

    # y[j] ∈ {0,1}: slot j is used
    y = pulp.LpVariable.dicts("y", J, cat="Binary")

    # z[j,t] ∈ {0,1}: slot j uses vehicle type t
    z = pulp.LpVariable.dicts(
        "z", [(j, t) for j in J for t in T], cat="Binary"
    )

    # w[j,r] ∈ {0,1}: slot j serves region r  (H2 auxiliary)
    w = pulp.LpVariable.dicts(
        "w", [(j, r) for j in J for r in R], cat="Binary"
    )

    # u[j,p] ∈ {0,1}: slot j contains pickup p  (H3 auxiliary)
    u = pulp.LpVariable.dicts(
        "u", [(j, p) for j in J for p in P], cat="Binary"
    )

    # v[j,c] ∈ {0,1}: slot j contains category c  (H4 auxiliary, Phase 1 only)
    if instance.phase == 1:
        v = pulp.LpVariable.dicts(
            "v", [(j, c) for j in J for c in C], cat="Binary"
        )
    else:
        v = {}

    # alpha[s,j] ∈ {0,1}: subcat s appears in slot j  (objective auxiliary)
    alpha = pulp.LpVariable.dicts(
        "a", [(s, j) for s in S for j in J], cat="Binary"
    )

    # -----------------------------------------------------------------------
    # Apply preprocessing fixes (Optimization B)
    # -----------------------------------------------------------------------
    # Fix x[i,j] = 0 for locked-order conflicts (forces direct assignment)
    for (i, j) in forced_x_zero:
        x[i, j].setInitialValue(0)
        x[i, j].fixValue()
    for (i, j) in forced_x_one:
        x[i, j].setInitialValue(1)
        x[i, j].fixValue()
    # Fix z[j,t] = 0 when all orders assignable to j are infeasible on type t.
    # For locked slots, use the locked group's orders; for free slots, if every
    # order pool contains at least one order that cannot fit type t, we still
    # keep z[j,t] flexible (another order may be excluded from slot via x).
    # So we only fix z[j,t] when j is a locked slot and the locked orders
    # collectively cannot fit type t.
    if locked_slot_map:
        # Map slot → list of locked orders on that slot
        locked_slot_orders: dict[int, list[int]] = {j: [] for j in locked_slots_set}
        for i, j_locked in order_locked_slot.items():
            locked_slot_orders[j_locked].append(i)
        for j_locked, locked_is in locked_slot_orders.items():
            if not locked_is:
                continue
            total_p = sum(pallets[i] for i in locked_is)
            total_h = sum(
                orders[i].hazard_quantity for i in locked_is
                if orders[i].hazard_flag
            )
            for t in T:
                cap_t = VEHICLE_TYPES[t].capacity
                # type infeasible if capacity or hazmat cannot cover locked group
                if total_p > cap_t or (total_h > H_MAX and t != "HQ40_DG"):
                    z[j_locked, t].setInitialValue(0)
                    z[j_locked, t].fixValue()

    # -----------------------------------------------------------------------
    # Objective
    # -----------------------------------------------------------------------

    if not is_phase2:
        # Phase 1: minimise Σ_{s,j} α_{sj}  (≡ minimise Σ_s φ_s)
        prob += pulp.lpSum(alpha[s, j] for s in S for j in J), "obj_phase1"
    else:
        # Phase 2: minimise total cost
        prob += pulp.lpSum(
            VEHICLE_TYPES[t].cost * z[j, t] for j in J for t in T
        ), "obj_phase2"

    # -----------------------------------------------------------------------
    # Structural Constraints
    # -----------------------------------------------------------------------

    # C0a: each order assigned to exactly one slot
    for i in I:
        prob += (
            pulp.lpSum(x[i, j] for j in J) == 1,
            f"c0a_{i}",
        )

    # C0b: x_{ij}=1 ⇒ y_j=1
    for i in I:
        for j in J:
            prob += (x[i, j] <= y[j], f"c0b_{i}_{j}")

    # C0b': y_j=1 ⇒ ≥1 order in slot j
    for j in J:
        prob += (
            y[j] <= pulp.lpSum(x[i, j] for i in I),
            f"c0b2_{j}",
        )

    # C0c: exactly one vehicle type per used slot
    for j in J:
        prob += (
            pulp.lpSum(z[j, t] for t in T) == y[j],
            f"c0c_{j}",
        )

    # C0d: α_{sj} ≥ x_{ij} for all i with s_i = s
    for s in S:
        for i in orders_by_subcat[s]:
            for j in J:
                prob += (alpha[s, j] >= x[i, j], f"c0d_{s}_{i}_{j}")

    # C0d': α_{sj} ≤ Σ_{i: s_i=s} x_{ij}
    for s in S:
        idx_s = orders_by_subcat[s]
        for j in J:
            prob += (
                alpha[s, j] <= pulp.lpSum(x[i, j] for i in idx_s),
                f"c0d2_{s}_{j}",
            )

    # -----------------------------------------------------------------------
    # Hard Constraints
    # -----------------------------------------------------------------------

    # H1: pallet capacity
    for j in J:
        prob += (
            pulp.lpSum(pallets[i] * x[i, j] for i in I)
            <= pulp.lpSum(VEHICLE_TYPES[t].capacity * z[j, t] for t in T),
            f"h1_{j}",
        )

    # H2a: region indicator
    for r in R:
        for i in orders_by_region[r]:
            for j in J:
                prob += (w[j, r] >= x[i, j], f"h2a_{r}_{i}_{j}")

    # H2b: at most one region per slot
    for j in J:
        prob += (
            pulp.lpSum(w[j, r] for r in R) <= 1,
            f"h2b_{j}",
        )

    # H3a: pickup indicator
    for p in P:
        for i in orders_by_pickup[p]:
            for j in J:
                prob += (u[j, p] >= x[i, j], f"h3a_{p}_{i}_{j}")

    # H3b: pickup count ≤ region limit (compact form, no big-M needed per §4.3)
    for j in J:
        for r in R:
            p_list = pickups_by_region[r]
            if p_list:
                prob += (
                    pulp.lpSum(u[j, p] for p in p_list) <= get_max_pickups(r),
                    f"h3b_{j}_{r}",
                )

    # H4: category consistency — Phase 1 only (oracle skips H4 in Phase 2)
    if instance.phase == 1:
        # H4a: category indicator
        for c in C:
            for i in orders_by_cat[c]:
                for j in J:
                    prob += (v[j, c] >= x[i, j], f"h4a_{c}_{i}_{j}")

        # H4b: at most one category per slot
        for j in J:
            prob += (
                pulp.lpSum(v[j, c] for c in C) <= 1,
                f"h4b_{j}",
            )

    # H5/H8: hazmat constraint (§4.5)
    # Σ h_i x_{ij} ≤ H_max + (M_H - H_max) * z_{j,DG}
    # When z_{j,DG}=0: Σ h_i x_{ij} ≤ 1800
    # When z_{j,DG}=1: Σ h_i x_{ij} ≤ M_H (no real limit)
    hazard_orders = [i for i in I if orders[i].hazard_flag]
    if hazard_orders or total_hazard_sum > 0:
        for j in J:
            prob += (
                pulp.lpSum(
                    orders[i].hazard_quantity * x[i, j] for i in hazard_orders
                )
                <= H_MAX + (M_H - H_MAX) * z[j, "HQ40_DG"],
                f"h5h8_{j}",
            )

    # H6: declaration amount limits per (country, ship_method) group
    for j in J:
        for g in G:
            if g not in instance.amount_limits:
                continue
            country, method = g.split(",", 1)
            orders_in_g = [
                i for i in I
                if orders[i].destination_country == country
                and orders[i].ship_method == method
            ]
            if not orders_in_g:
                continue
            prob += (
                pulp.lpSum(
                    orders[i].declaration_amount * x[i, j] for i in orders_in_g
                )
                <= instance.amount_limits[g],
                f"h6_{j}_{g.replace(',', '_')}",
            )

    # H7: locked order assignments (fix x_{i, l_i} = 1)
    # Note: redundant with preprocessing (forced_x_one), but kept for auditability
    # against milp-model.md §4.7. PuLP handles constant constraints gracefully.
    for i in I:
        o = orders[i]
        if o.locked_vehicle_id is not None:
            j_locked = locked_slot_map[o.locked_vehicle_id]
            prob += (x[i, j_locked] == 1, f"h7_{i}")

    # Symmetry breaking: y_j ≥ y_{j+1} for free (unlocked) slots
    if symmetry_breaking:
        locked_slots = set(locked_slot_map.values())
        L = len(locked_slot_map)
        for j in range(L, K - 1):
            if j not in locked_slots and (j + 1) not in locked_slots:
                prob += (y[j] >= y[j + 1], f"sym_{j}")

    # Phase 2 epsilon-constraint: fix α-sum = Phase-1 optimal
    if is_phase2:
        prob += (
            pulp.lpSum(alpha[s, j] for s in S for j in J)
            == phase2_sum_alpha_star,
            "eps_constraint",
        )

    # Package variables for solution extraction
    vars_dict = {
        "x": x,
        "y": y,
        "z": z,
        "w": w,
        "u": u,
        "v": v,
        "alpha": alpha,
        # Index structures
        "I": I,
        "J": J,
        "T": T,
        "S": S,
        "orders": orders,
    }

    return prob, vars_dict


# ---------------------------------------------------------------------------
# Solution extraction
# ---------------------------------------------------------------------------

def extract_solution(
    instance: Instance,
    vars_dict: dict,
) -> Solution:
    """Reconstruct a Solution object from solved MILP variable values.

    Uses a threshold of 0.5 for binary variable rounding.
    """
    x = vars_dict["x"]
    y = vars_dict["y"]
    z = vars_dict["z"]
    I = vars_dict["I"]
    J = vars_dict["J"]
    T = vars_dict["T"]
    orders = vars_dict["orders"]

    vehicles: dict[str, Vehicle] = {}
    assignment: dict[str, str] = {}

    for j in J:
        y_val = pulp.value(y[j])
        if y_val is None or y_val < 0.5:
            continue

        # Determine vehicle type
        vtype = None
        for t in T:
            z_val = pulp.value(z[j, t])
            if z_val is not None and z_val > 0.5:
                vtype = t
                break

        if vtype is None:
            continue

        # Collect assigned orders
        oids_in_j: list[str] = []
        for i in I:
            x_val = pulp.value(x[i, j])
            if x_val is not None and x_val > 0.5:
                oids_in_j.append(orders[i].order_id)

        if not oids_in_j:
            continue

        # Region from orders (should be consistent by H2)
        region = get_region(instance.orders[oids_in_j[0]].pickup_city)

        vid = f"MILP_V{j:04d}"
        vehicles[vid] = Vehicle(
            vehicle_id=vid,
            vehicle_type=vtype,
            region=region,
            order_ids=list(oids_in_j),
        )
        for oid in oids_in_j:
            assignment[oid] = vid

    return Solution(vehicles=vehicles, assignment=assignment)


def extract_solution_strict(
    instance: Instance,
    vars_dict: dict,
    tol: float = 1e-4,
) -> tuple[Solution, list[str]]:
    """Extract solution with integrality + C0a completeness verification.

    Returns (solution, issues). `issues` is empty iff solution is verified
    as an integer-feasible, complete assignment (every order placed exactly
    once). Otherwise the solution may still be useful for diagnostics.
    """
    issues: list[str] = []
    x = vars_dict["x"]
    y = vars_dict["y"]
    I = vars_dict["I"]
    J = vars_dict["J"]
    orders = vars_dict["orders"]

    # Integrality check
    for i in I:
        for j in J:
            val = pulp.value(x[i, j])
            if val is None:
                issues.append(f"x[{i},{j}] is None")
                continue
            if min(abs(val), abs(1 - val)) > tol:
                issues.append(f"x[{i},{j}]={val:.6f} non-integer")

    # C0a: every order assigned exactly once
    for i in I:
        row_sum = 0.0
        for j in J:
            val = pulp.value(x[i, j])
            if val is not None and val > 0.5:
                row_sum += 1
        if row_sum != 1:
            issues.append(
                f"C0a violation: order {orders[i].order_id} (i={i}) "
                f"assigned to {int(row_sum)} slots"
            )

    solution = extract_solution(instance, vars_dict)
    n_placed = len(solution.assignment)
    if n_placed != len(I):
        issues.append(
            f"assignment incomplete: {n_placed}/{len(I)} orders placed"
        )

    return solution, issues

