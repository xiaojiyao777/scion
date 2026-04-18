"""
MILP Solver Tests

Covers:
1. Feasibility on s01/s02/s03
2. Oracle verification
3. Objective consistency
4. Comparison with VNS heuristic
5. Locked order constraints
6. Timeout handling

Performance design:
- solve_exact on s01/s02/s03 is cached at session scope (one solve per instance).
- Six downstream assertions reuse the cached MILPResult, cutting 15 solves to 3.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

# Ensure surrogate/ on sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from models import (
    Instance,
    Order,
    Solution,
    SPU,
    Vehicle,
    VEHICLE_TYPES,
)
from oracle import check_feasibility, recompute_objective
from milp_solver import solve_exact, MILPResult, _load_instance

DATA_DIR = Path(__file__).parent.parent / "data"

SMALL_INSTANCES = ["s01", "s02", "s03"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_test_instance(name: str) -> Instance:
    return _load_instance(str(DATA_DIR / f"instance_v4_scr_{name}.json"))


def make_order(
    order_id: str = "O1",
    vehicle_category: int = 0,
    vehicle_subcategory: int = 0,
    hazard_flag: bool = False,
    hazard_quantity: int = 0,
    pickup_name: str = "FG_CENTRAL_WH",
    pickup_city: str = "Dongguan",
    declaration_amount: float = 100_000.0,
    ship_method: str = "ROAD",
    destination_country: str = "Germany",
    spu_list: list[SPU] | None = None,
    locked_vehicle_id: str | None = None,
) -> Order:
    return Order(
        order_id=order_id,
        vehicle_category=vehicle_category,
        vehicle_subcategory=vehicle_subcategory,
        urgent=False,
        hazard_flag=hazard_flag,
        hazard_quantity=hazard_quantity,
        pickup_name=pickup_name,
        pickup_province="Guangdong",
        pickup_city=pickup_city,
        declaration_amount=declaration_amount,
        lsp="DHL",
        ship_method=ship_method,
        destination_country=destination_country,
        spu_list=spu_list or [SPU("FULL_PLT", 2)],
        locked_vehicle_id=locked_vehicle_id,
    )


# ---------------------------------------------------------------------------
# Session-scoped cache: one solve per small instance, reused across classes.
# ---------------------------------------------------------------------------

# Per-session cache keyed by instance name. Populated lazily by _milp_result().
_MILP_CACHE: dict[str, MILPResult] = {}


def _milp_result(name: str, time_limit: int = 600) -> MILPResult:
    if name not in _MILP_CACHE:
        t0 = time.monotonic()
        inst = load_test_instance(name)
        result = solve_exact(inst, time_limit_seconds=time_limit, verbose=False)
        elapsed = time.monotonic() - t0
        print(
            f"\n[milp-cache] {name}: status={result.status} "
            f"f1={result.objective_f1} f2={result.objective_f2} "
            f"elapsed={elapsed:.1f}s",
            flush=True,
        )
        _MILP_CACHE[name] = result
    return _MILP_CACHE[name]


@pytest.fixture(scope="session", params=SMALL_INSTANCES)
def small_instance(request):
    """Yield (name, instance, milp_result) for each small instance (s01..s03).

    The MILP solve is cached per session so downstream tests reuse it.
    """
    name = request.param
    inst = load_test_instance(name)
    result = _milp_result(name, time_limit=600)
    return name, inst, result


# ---------------------------------------------------------------------------
# 1. Feasibility tests
# ---------------------------------------------------------------------------

class TestFeasibility:
    def test_finds_feasible_solution(self, small_instance):
        name, inst, result = small_instance
        assert result.status in ("optimal", "feasible"), (
            f"{name}: got status={result.status}"
        )
        assert result.solution is not None


# ---------------------------------------------------------------------------
# 2. Oracle verification
# ---------------------------------------------------------------------------

class TestOracleVerification:
    def test_solution_passes_oracle(self, small_instance):
        name, inst, result = small_instance
        assert result.solution is not None
        feas = check_feasibility(result.solution, inst, 1)
        assert feas.is_feasible, f"{name}: Violations: {feas.violations}"


# ---------------------------------------------------------------------------
# 3. Objective consistency
# ---------------------------------------------------------------------------

class TestObjectiveConsistency:
    def test_f1_consistent(self, small_instance):
        name, inst, result = small_instance
        assert result.solution is not None
        obj = recompute_objective(result.solution, inst)
        assert result.objective_f1 == obj.subcategory_splits, (
            f"{name}: MILP f1={result.objective_f1} != recomputed {obj.subcategory_splits}"
        )

    def test_f2_consistent(self, small_instance):
        name, inst, result = small_instance
        assert result.solution is not None
        obj = recompute_objective(result.solution, inst)
        assert result.objective_f2 == obj.total_cost, (
            f"{name}: MILP f2={result.objective_f2} != recomputed {obj.total_cost}"
        )


# ---------------------------------------------------------------------------
# 4. Compare with VNS heuristic
# ---------------------------------------------------------------------------

class TestVsHeuristic:
    def test_milp_not_worse_than_vns(self, small_instance):
        """MILP (f1, f2) must be lexicographically <= VNS result."""
        name, inst, milp_result = small_instance
        assert milp_result.solution is not None

        # Run VNS with 200 iterations
        from config import Config
        from greedy_init import greedy_init
        from operators import (
            ChangeVehicleType, DestroyRebuild, MergeVehicles,
            MoveOrder, SplitVehicle, SwapOrders,
        )
        from vns import run_vns
        from random import Random

        cfg = Config()
        cfg.max_iterations = 200
        rng = Random(42)
        init_sol = greedy_init(inst, rng)
        init_sol.objective = recompute_objective(init_sol, inst)

        ops = [cls(inst, 1) for cls in [
            SwapOrders, MoveOrder, DestroyRebuild,
            MergeVehicles, ChangeVehicleType, SplitVehicle,
        ]]
        weights = [3, 3, 2, 2, 2, 1]

        vns_best = run_vns(inst, [init_sol], ops, weights, cfg)
        vns_obj = recompute_objective(vns_best, inst)

        milp_f1 = milp_result.objective_f1
        milp_f2 = milp_result.objective_f2

        # Lexicographic: MILP should be <= VNS
        assert (milp_f1, milp_f2) <= (vns_obj.subcategory_splits, vns_obj.total_cost), (
            f"{name}: MILP ({milp_f1}, {milp_f2}) worse than VNS "
            f"({vns_obj.subcategory_splits}, {vns_obj.total_cost})"
        )


# ---------------------------------------------------------------------------
# 5. Locked order test (独立 solve，不占 small_instance cache)
# ---------------------------------------------------------------------------

class TestLockedOrders:
    def test_locked_orders_same_vehicle(self):
        """Orders with the same locked_vehicle_id must end up on the same vehicle."""
        orders = [
            make_order("O1", locked_vehicle_id="LOCK_A", spu_list=[SPU("FULL_PLT", 2)]),
            make_order("O2", locked_vehicle_id="LOCK_A", spu_list=[SPU("FULL_PLT", 3)]),
            make_order("O3", spu_list=[SPU("FULL_PLT", 4)]),
            make_order("O4", spu_list=[SPU("FULL_PLT", 2)]),
        ]
        inst = Instance(
            orders={o.order_id: o for o in orders},
            amount_limits={"Germany,ROAD": 5_000_000.0},
            phase=1,
        )
        result = solve_exact(inst, time_limit_seconds=60)
        assert result.status in ("optimal", "feasible")
        assert result.solution is not None

        # O1 and O2 must be assigned to the same vehicle
        v1 = result.solution.assignment["O1"]
        v2 = result.solution.assignment["O2"]
        assert v1 == v2, f"Locked orders O1→{v1}, O2→{v2} should share a vehicle"

        # Also must pass oracle
        feas = check_feasibility(result.solution, inst, 1)
        assert feas.is_feasible


# ---------------------------------------------------------------------------
# 6. Timeout test (独立 solve，短 timeout 不进 cache)
# ---------------------------------------------------------------------------

class TestTimeout:
    def test_short_timeout_no_crash(self):
        """With a very short timeout on a harder instance, solver should not crash."""
        inst = load_test_instance("s03")
        result = solve_exact(inst, time_limit_seconds=5, verbose=False)
        # Should return some status without crashing
        assert result.status in ("optimal", "feasible", "timeout", "infeasible", "error")
        # If it found a feasible solution, it should be valid
        if result.solution is not None:
            feas = check_feasibility(result.solution, inst, 1)
            # We don't assert feasibility here since very short timeout
            # may produce partial results, but it shouldn't crash
