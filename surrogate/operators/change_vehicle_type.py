"""
算子：ChangeVehicleType（降级车型节省成本）

对随机选择的一辆车，尝试将其车型降级到能容纳当前订单的最小车型，
从而节省运输成本。
"""

from __future__ import annotations

from random import Random

from models import (
    Instance,
    Solution,
    VEHICLE_TYPES_BY_CAPACITY,
    calc_pallets,
)
from operators.base import Operator


class ChangeVehicleType(Operator):
    """将车辆降级到能容纳当前载货的最小成本车型。"""

    def __init__(self, instance: Instance, phase: int = 1) -> None:
        self.instance = instance
        self.phase = phase

    def execute(self, solution: Solution, rng: Random) -> Solution:
        """随机选一辆非空车，尝试降级车型。"""
        non_empty = [vid for vid, v in solution.vehicles.items() if v.order_ids]
        if not non_empty:
            return solution

        new_sol = solution.deep_copy()
        vid = rng.choice(non_empty)
        vehicle = new_sol.vehicles[vid]

        orders = [self.instance.orders[oid] for oid in vehicle.order_ids]
        total_pallets = sum(calc_pallets(o.spu_list) for o in orders)
        total_hazard = sum(o.hazard_quantity for o in orders if o.hazard_flag)

        # 找最小成本车型
        best_type = self._find_minimum_type(total_pallets, total_hazard)
        if best_type is None or best_type == vehicle.vehicle_type:
            return solution

        vehicle.vehicle_type = best_type
        return new_sol

    @staticmethod
    def _find_minimum_type(total_pallets: int, total_hazard: int) -> str | None:
        """找能容纳给定栈板数和危险品量的最小成本车型。"""
        if total_hazard > 1800:
            # 必须用危险品专车
            return "HQ40_DG"

        # 在非危险品专车中找最小成本（最小容量可装下）的车型
        for code, capacity, _cost in VEHICLE_TYPES_BY_CAPACITY:
            if code == "HQ40_DG":
                continue
            if capacity >= total_pallets:
                return code
        return None
