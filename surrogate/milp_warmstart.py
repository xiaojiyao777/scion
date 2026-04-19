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
    # Map locked-group champion vehicles to locked slots
    # (one locked_vehicle_id → one slot; find the champion vehicle for it)
    # -------------------------------------------------------------------------
    locked_champ_to_slot: dict[str, int] = {}  # champion vehicle_id → slot j
    for locked_instance_vid, slot_j in locked_slot_map.items():
        # Find the champion vehicle that covers this locked group
        for o in orders:
            if o.locked_vehicle_id == locked_instance_vid:
                champ_vid = solution.assignment.get(o.order_id)
                if champ_vid is not None and champ_vid not in locked_champ_to_slot:
                    locked_champ_to_slot[champ_vid] = slot_j
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
            continue  # handled via locked_champ_to_slot
        if free_slot >= K:
            logger.warning(
                "warm start: champion has more vehicles than K=%d; skipping warm start",
                K,
            )
            return {}
        free_vehicle_to_slot[champ_vid] = free_slot
        free_slot += 1

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

    # Free orders in locked vehicles → no warm start (skip)

    # -------------------------------------------------------------------------
    # Build slot → vehicle type
    # -------------------------------------------------------------------------
    slot_to_vtype: dict[int, str] = {}

    # Locked slots: use the vehicle type of the champion vehicle for that group
    for champ_vid, j in locked_champ_to_slot.items():
        slot_to_vtype[j] = solution.vehicles[champ_vid].vehicle_type

    # Free slots: use champion vehicle type
    for champ_vid, j in free_vehicle_to_slot.items():
        slot_to_vtype[j] = solution.vehicles[champ_vid].vehicle_type

    # -------------------------------------------------------------------------
    # Helper: PuLP's name for LpVariable.dicts tuple key
    # PuLP does: name = f"{prefix}_{str(key)}".replace(" ", "_")
    # For tuple (i, j): str((i, j)) == "(i, j)" → "(i,_j)"
    # For tuple (j, 'HQ40'): str((j, 'HQ40')) == "(j, 'HQ40')" → "(j,_'HQ40')"
    # (single quotes kept, spaces → underscore)
    # -------------------------------------------------------------------------
    def _vname(prefix: str, key: tuple) -> str:
        return f"{prefix}_{str(key)}".replace(" ", "_")

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
