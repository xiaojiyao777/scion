"""
Warm-start value translator for MILP solver.

Translates a champion Solution into a dict[str, float] mapping PuLP
variable names → warm-start values, consistent with build_milp()'s
variable layout.

PuLP variable name convention (from LpVariable.dicts with tuple keys):
  x[(i, j)]   → "x_(i,_j)"           ← spaces → _, parens kept
  y[j]         → "y_j"
  z[(j, t)]    → "z_(j,_'type')"      ← string index gets quoted
  a[(s, j)]    → "a_(s,_j)"           (prefix "a", not "alpha")
  w[(j, r)]    → "w_(j,_'region')"
  u[(j, p)]    → "u_(j,_'pickup')"
  v[(j, c)]    → "v_(j,_'cat')"

PuLP's LpVariable.dicts() calls `str(key)` for tuple keys, producing
"(i, j)" with spaces, then replaces spaces with underscores in the final
variable name. String components in the tuple keep their single quotes.
"""

from __future__ import annotations

import logging
import sys
from collections import defaultdict
from pathlib import Path

_surrogate_dir = Path(__file__).parent
if str(_surrogate_dir) not in sys.path:
    sys.path.insert(0, str(_surrogate_dir))

from milp_model import VEHICLE_TYPE_LIST
from models import Instance, Solution, get_region

logger = logging.getLogger(__name__)


def _vname(prefix: str, key: tuple) -> str:
    """Return the PuLP variable name for LpVariable.dicts with a tuple key.

    PuLP does: name = f"{prefix}_{str(key)}".replace(" ", "_")
    e.g. ("x", (2, 3)) → "x_(2,_3)"
         ("z", (1, "HQ40")) → "z_(1,_'HQ40')"
    """
    return f"{prefix}_{str(key)}".replace(" ", "_")


def build_warmstart_values(
    solution: Solution,
    instance: Instance,
    K: int,
    locked_slot_map: dict[str, int],
) -> dict[str, float]:
    """Translate champion Solution into PuLP variable name → value mapping.

    Parameters
    ----------
    solution : Solution
        Champion solution to use as warm start.
    instance : Instance
        Problem instance.
    K : int
        Number of MILP slots.
    locked_slot_map : dict[str, int]
        Maps locked_vehicle_id (from instance) → MILP slot index.

    Returns
    -------
    dict[str, float]
        Maps PuLP variable names to 0/1 values. Empty dict on failure.
    """
    orders = list(instance.orders.values())
    I = list(range(len(orders)))
    J = list(range(K))
    T = VEHICLE_TYPE_LIST

    S = sorted({o.vehicle_subcategory for o in orders})
    C = sorted({o.vehicle_category for o in orders})
    R = sorted({get_region(o.pickup_city) for o in orders})
    P = sorted({o.pickup_name for o in orders})

    L = len(locked_slot_map)
    locked_slots: set[int] = set(locked_slot_map.values())

    # -------------------------------------------------------------------------
    # Identify champion vehicles that contain locked orders
    # -------------------------------------------------------------------------
    # A champion vehicle is "locked" if it contains at least one locked order.
    # Free orders in locked champion vehicles are skipped (MILP preprocessing
    # fixes x[free_order, locked_slot] = 0, so they can't go there).
    locked_champion_vids: set[str] = set()
    for o in orders:
        if o.locked_vehicle_id is not None:
            champ_vid = solution.assignment.get(o.order_id)
            if champ_vid:
                locked_champion_vids.add(champ_vid)

    # -------------------------------------------------------------------------
    # Map each locked slot to its champion vehicle's type.
    # One champion vehicle may cover multiple locked groups (e.g., if the VNS
    # merged two locked groups into one vehicle); each group still maps to a
    # separate MILP slot, and all such slots must have a vehicle type set.
    # -------------------------------------------------------------------------
    locked_slot_vtype: dict[int, str] = {}  # slot j → vehicle type
    for locked_instance_vid, slot_j in locked_slot_map.items():
        for o in orders:
            if o.locked_vehicle_id == locked_instance_vid:
                champ_vid = solution.assignment.get(o.order_id)
                if champ_vid is not None:
                    locked_slot_vtype[slot_j] = solution.vehicles[champ_vid].vehicle_type
                break

    # -------------------------------------------------------------------------
    # Assign pure-free champion vehicles to free MILP slots
    # -------------------------------------------------------------------------
    free_slot = L
    free_vehicle_to_slot: dict[str, int] = {}

    for champ_vid, vehicle in solution.vehicles.items():
        if not vehicle.order_ids:
            continue
        if champ_vid in locked_champion_vids:
            continue  # handled via locked_slot_vtype and spillover below
        if free_slot >= K:
            logger.warning(
                "warm start: champion has more vehicles than K=%d; skipping warm start",
                K,
            )
            return {}
        free_vehicle_to_slot[champ_vid] = free_slot
        free_slot += 1

    # -------------------------------------------------------------------------
    # Allocate spillover free slots for free orders stranded in locked vehicles.
    # In the MILP, free orders cannot go on locked slots (preprocessing fixes
    # x[free_order, locked_slot] = 0). Each mixed champion vehicle (one that has
    # both locked and free orders) gets one fresh free slot for its free orders.
    # -------------------------------------------------------------------------
    spillover_free_oids: dict[str, int] = {}  # order_id → spillover slot j
    spillover_slot_vtype: dict[int, str] = {}  # spillover slot j → vehicle type

    for champ_vid in sorted(locked_champion_vids):  # sorted for determinism
        vehicle = solution.vehicles.get(champ_vid)
        if vehicle is None:
            continue
        free_oids_in_mixed = [
            oid for oid in vehicle.order_ids
            if instance.orders[oid].locked_vehicle_id is None
        ]
        if not free_oids_in_mixed:
            continue  # purely locked vehicle; no spillover needed
        if free_slot >= K:
            logger.warning(
                "warm start: K=%d exhausted; skipping spillover for %s "
                "(%d free orders unassigned)",
                K, champ_vid, len(free_oids_in_mixed),
            )
            continue  # leave unassigned rather than aborting entirely
        j_spill = free_slot
        free_slot += 1
        spillover_slot_vtype[j_spill] = vehicle.vehicle_type
        for oid in free_oids_in_mixed:
            spillover_free_oids[oid] = j_spill

    # -------------------------------------------------------------------------
    # Build order → warm-start slot mapping
    # -------------------------------------------------------------------------
    order_to_slot: dict[str, int] = {}

    # Locked orders → their locked slot
    for o in orders:
        if o.locked_vehicle_id is not None:
            order_to_slot[o.order_id] = locked_slot_map[o.locked_vehicle_id]

    # Free orders in pure-free vehicles → their free slot
    for champ_vid, j in free_vehicle_to_slot.items():
        for oid in solution.vehicles[champ_vid].order_ids:
            order_to_slot[oid] = j

    # Free orders in mixed vehicles → their spillover slot
    order_to_slot.update(spillover_free_oids)

    # -------------------------------------------------------------------------
    # Build slot → vehicle type
    # -------------------------------------------------------------------------
    slot_to_vtype: dict[int, str] = {}

    # Locked slots: each locked group has its own MILP slot with its champion's type
    for slot_j, vtype in locked_slot_vtype.items():
        slot_to_vtype[slot_j] = vtype

    # Free slots: use champion vehicle type
    for champ_vid, j in free_vehicle_to_slot.items():
        slot_to_vtype[j] = solution.vehicles[champ_vid].vehicle_type

    # Spillover slots: same type as the mixed champion vehicle
    slot_to_vtype.update(spillover_slot_vtype)

    # -------------------------------------------------------------------------
    # Build variable value dict
    # -------------------------------------------------------------------------
    values: dict[str, float] = {}

    # x[i, j]
    for i in I:
        oid = orders[i].order_id
        j_assigned = order_to_slot.get(oid)
        if j_assigned is None:
            continue  # skip orders with no warm-start slot
        for j in J:
            values[_vname("x", (i, j))] = 1.0 if j == j_assigned else 0.0

    # y[j]
    used_slots: set[int] = set(order_to_slot.values())
    for j in J:
        values[f"y_{j}"] = 1.0 if j in used_slots else 0.0

    # z[j, t]
    for j in J:
        vtype_j = slot_to_vtype.get(j)
        for t in T:
            values[_vname("z", (j, t))] = 1.0 if t == vtype_j else 0.0

    # alpha[s, j] — prefix "a"
    slot_to_subcats: dict[int, set] = defaultdict(set)
    for i in I:
        j_assigned = order_to_slot.get(orders[i].order_id)
        if j_assigned is not None:
            slot_to_subcats[j_assigned].add(orders[i].vehicle_subcategory)

    for s in S:
        for j in J:
            values[_vname("a", (s, j))] = 1.0 if s in slot_to_subcats[j] else 0.0

    # w[j, r]
    slot_to_region: dict[int, str] = {}
    for i in I:
        j_assigned = order_to_slot.get(orders[i].order_id)
        if j_assigned is not None:
            slot_to_region[j_assigned] = get_region(orders[i].pickup_city)

    for j in J:
        region_j = slot_to_region.get(j)
        for r in R:
            values[_vname("w", (j, r))] = 1.0 if r == region_j else 0.0

    # u[j, p]
    slot_to_pickups: dict[int, set] = defaultdict(set)
    for i in I:
        j_assigned = order_to_slot.get(orders[i].order_id)
        if j_assigned is not None:
            slot_to_pickups[j_assigned].add(orders[i].pickup_name)

    for j in J:
        for p in P:
            values[_vname("u", (j, p))] = 1.0 if p in slot_to_pickups[j] else 0.0

    # v[j, c] — Phase 1 only
    if instance.phase == 1:
        slot_to_cats: dict[int, set] = defaultdict(set)
        for i in I:
            j_assigned = order_to_slot.get(orders[i].order_id)
            if j_assigned is not None:
                slot_to_cats[j_assigned].add(orders[i].vehicle_category)

        for j in J:
            for c in C:
                values[_vname("v", (j, c))] = 1.0 if c in slot_to_cats[j] else 0.0

    return values
