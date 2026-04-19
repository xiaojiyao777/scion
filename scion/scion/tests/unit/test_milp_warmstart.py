"""Unit tests for MILP warm-start translator and warm-start solve path.

Tests:
1. test_warmstart_values_sum_to_n_orders   — sum of x[i,j] over all j per order == 1
2. test_warmstart_locked_slots_respected   — locked orders at correct slot
3. test_warmstart_vehicle_type_matches     — z[j, t] = 1 for correct vehicle type
4. test_warmstart_feasibility              — values correspond to oracle-feasible solution
5. test_solve_exact_with_warmstart         — warm-start solve gives same or better f1/f2
"""
from __future__ import annotations

import sys
from pathlib import Path

# Add surrogate/ to sys.path so we can import surrogate modules directly
_repo_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(_repo_root / "surrogate"))

import pytest

from models import Instance, Order, Solution, SPU, Vehicle
from oracle import check_feasibility, recompute_objective
from milp_model import compute_K, build_locked_slot_map
from milp_warmstart import build_warmstart_values, _vname
from milp_solver import solve_exact, _load_instance


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

DATA_DIR = _repo_root / "surrogate" / "data"


def _load(name: str) -> Instance:
    return _load_instance(str(DATA_DIR / f"instance_v4_scr_{name}.json"))


def _make_order(
    order_id: str,
    vehicle_category: int = 0,
    vehicle_subcategory: int = 0,
    pickup_name: str = "WH_A",
    pickup_city: str = "Dongguan",
    ship_method: str = "ROAD",
    destination_country: str = "Germany",
    locked_vehicle_id: str | None = None,
    spu_list: list[SPU] | None = None,
) -> Order:
    return Order(
        order_id=order_id,
        vehicle_category=vehicle_category,
        vehicle_subcategory=vehicle_subcategory,
        urgent=False,
        hazard_flag=False,
        hazard_quantity=0,
        pickup_name=pickup_name,
        pickup_province="Guangdong",
        pickup_city=pickup_city,
        declaration_amount=100_000.0,
        lsp="DHL",
        ship_method=ship_method,
        destination_country=destination_country,
        spu_list=spu_list or [SPU("FULL_PLT", 2)],
        locked_vehicle_id=locked_vehicle_id,
    )


def _small_instance_with_locked() -> tuple[Instance, Solution]:
    """Instance with 4 orders (2 locked, 2 free) and a compatible champion solution."""
    orders = [
        _make_order("O1", locked_vehicle_id="LOCK_A", spu_list=[SPU("FULL_PLT", 2)]),
        _make_order("O2", locked_vehicle_id="LOCK_A", spu_list=[SPU("FULL_PLT", 1)]),
        _make_order("O3", spu_list=[SPU("FULL_PLT", 2)]),
        _make_order("O4", spu_list=[SPU("FULL_PLT", 3)]),
    ]
    inst = Instance(
        orders={o.order_id: o for o in orders},
        amount_limits={"Germany,ROAD": 5_000_000.0},
        phase=1,
    )
    # Champion: V_LOCK covers O1+O2 (locked), V_FREE1 covers O3, V_FREE2 covers O4
    champion = Solution(
        vehicles={
            "V_LOCK": Vehicle("V_LOCK", "T5", "Dongguan", ["O1", "O2"]),
            "V_FREE1": Vehicle("V_FREE1", "T3", "Dongguan", ["O3"]),
            "V_FREE2": Vehicle("V_FREE2", "T10", "Dongguan", ["O4"]),
        },
        assignment={"O1": "V_LOCK", "O2": "V_LOCK", "O3": "V_FREE1", "O4": "V_FREE2"},
    )
    return inst, champion


# ---------------------------------------------------------------------------
# T1: sum of x[i,j] over all j == 1 for each order that has a warm-start slot
# ---------------------------------------------------------------------------

def test_warmstart_values_sum_to_n_orders():
    inst, champion = _small_instance_with_locked()
    K = compute_K(inst)
    locked_slot_map = build_locked_slot_map(inst)
    values = build_warmstart_values(champion, inst, K, locked_slot_map)

    orders = list(inst.orders.values())
    I = list(range(len(orders)))
    J = list(range(K))

    # For each order i, sum x[i,j] over all j
    for i in I:
        row_sum = sum(
            values.get(_vname("x", (i, j)), 0.0) for j in J
        )
        # Each order should have exactly 1 assignment (or 0 if no warm-start slot)
        assert row_sum in (0.0, 1.0), (
            f"order i={i} has x-row sum={row_sum}, expected 0 or 1"
        )

    # Total x=1 entries should equal number of orders with warm-start slots
    total = sum(
        values.get(_vname("x", (i, j)), 0.0) for i in I for j in J
    )
    n_orders = len(orders)
    assert total == n_orders, (
        f"Expected {n_orders} total x=1 entries (all orders have warm-start slots), got {total}"
    )


# ---------------------------------------------------------------------------
# T2: locked orders land on the slot specified by locked_slot_map
# ---------------------------------------------------------------------------

def test_warmstart_locked_slots_respected():
    inst, champion = _small_instance_with_locked()
    K = compute_K(inst)
    locked_slot_map = build_locked_slot_map(inst)
    values = build_warmstart_values(champion, inst, K, locked_slot_map)

    orders = list(inst.orders.values())
    order_id_to_i = {o.order_id: i for i, o in enumerate(orders)}

    locked_slot = locked_slot_map["LOCK_A"]

    # O1 and O2 have locked_vehicle_id=LOCK_A → must be on locked_slot
    for oid in ("O1", "O2"):
        i = order_id_to_i[oid]
        assert values.get(_vname("x", (i, locked_slot)), 0.0) == 1.0, (
            f"Order {oid} (i={i}) should be at locked slot {locked_slot}"
        )
        # Must be 0 on all other slots
        for j in range(K):
            if j == locked_slot:
                continue
            assert values.get(_vname("x", (i, j)), 0.0) == 0.0, (
                f"Order {oid} (i={i}) should not be at slot {j}"
            )


# ---------------------------------------------------------------------------
# T3: z[j, t] = 1 for the vehicle type of the champion vehicle at slot j
# ---------------------------------------------------------------------------

def test_warmstart_vehicle_type_matches():
    inst, champion = _small_instance_with_locked()
    K = compute_K(inst)
    locked_slot_map = build_locked_slot_map(inst)
    values = build_warmstart_values(champion, inst, K, locked_slot_map)

    # Locked slot: V_LOCK has type T5
    locked_slot = locked_slot_map["LOCK_A"]
    assert values.get(_vname("z", (locked_slot, "T5")), 0.0) == 1.0, "Locked slot should have z[j, T5]=1"
    for t in ("HQ40_DG", "HQ40", "T10", "T3"):
        assert values.get(_vname("z", (locked_slot, t)), 0.0) == 0.0, (
            f"Locked slot should have z[j, {t}]=0"
        )

    # Verify each used free slot has exactly one z=1
    J = list(range(K))
    for j in J:
        z_vals = [values.get(_vname("z", (j, t)), 0.0) for t in ("HQ40_DG", "HQ40", "T10", "T5", "T3")]
        z_sum = sum(z_vals)
        # Either slot is used (z_sum=1) or unused (z_sum=0)
        assert z_sum in (0.0, 1.0), f"Slot {j}: z sum = {z_sum}, expected 0 or 1"


# ---------------------------------------------------------------------------
# T4: warm-start values correspond to an oracle-feasible solution
# ---------------------------------------------------------------------------

def test_warmstart_feasibility():
    """The champion used to build warm-start values must pass oracle feasibility."""
    inst, champion = _small_instance_with_locked()
    K = compute_K(inst)
    locked_slot_map = build_locked_slot_map(inst)

    # Warm start builds from champion — verify champion itself is feasible
    feas = check_feasibility(champion, inst, 1)
    assert feas.is_feasible, f"Champion is not oracle-feasible: {feas.violations}"

    # Warm start values should be non-empty
    values = build_warmstart_values(champion, inst, K, locked_slot_map)
    assert len(values) > 0, "build_warmstart_values returned empty dict for valid champion"


# ---------------------------------------------------------------------------
# T5: solve_exact with warm_start returns same or better f1/f2 on s01
# ---------------------------------------------------------------------------

@pytest.mark.slow
def test_solve_exact_with_warmstart():
    """solve_exact(warm_start=champion) should produce f1/f2 <= baseline on s01."""
    inst = _load("s01")

    # Generate champion via greedy_init + short VNS
    from config import Config
    from greedy_init import greedy_init
    from operators import (
        ChangeVehicleType, MergeVehicles, MoveOrder, SwapOrders,
    )
    from vns import run_vns
    from random import Random

    cfg = Config()
    cfg.max_iterations = 100
    rng = Random(42)
    init_sol = greedy_init(inst, rng)
    init_sol.objective = recompute_objective(init_sol, inst)
    ops = [cls(inst, 1) for cls in [SwapOrders, MoveOrder, MergeVehicles, ChangeVehicleType]]
    weights = [3, 3, 2, 2]
    champion = run_vns(inst, [init_sol], ops, weights, cfg)
    champion.objective = recompute_objective(champion, inst)

    # Baseline solve without warm start
    baseline = solve_exact(inst, time_limit_seconds=60, verbose=False, solver_name="HiGHS")

    # Warm-start solve
    result_ws = solve_exact(
        inst,
        time_limit_seconds=60,
        verbose=False,
        solver_name="HiGHS",
        warm_start=champion,
    )

    # Both should return without error
    assert baseline.status in ("optimal", "feasible", "timeout", "no_feasible")
    assert result_ws.status in ("optimal", "feasible", "timeout", "no_feasible")

    # Warm-start result should be at least as good as baseline (or no solution found)
    if baseline.solution is not None and result_ws.solution is not None:
        assert (result_ws.objective_f1, result_ws.objective_f2) <= (
            baseline.objective_f1, baseline.objective_f2
        ), (
            f"Warm start result ({result_ws.objective_f1}, {result_ws.objective_f2}) "
            f"worse than baseline ({baseline.objective_f1}, {baseline.objective_f2})"
        )
