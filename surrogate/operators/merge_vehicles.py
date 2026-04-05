"""
算子：MergeVehicles（两辆车合并为一辆）

随机选两辆车，尝试将较小车的所有订单（锁定/未锁定均可整体操作）
合并到较大车中，然后删除空车。
"""

from __future__ import annotations

from random import Random

from models import Instance, Solution, VEHICLE_TYPES, calc_pallets
from operators.base import Operator


class MergeVehicles(Operator):
    """将两辆车合并为一辆（合并后需重新选车型）。"""

    def __init__(self, instance: Instance, phase: int = 1) -> None:
        self.instance = instance
        self.phase = phase

    def execute(self, solution: Solution, rng: Random) -> Solution:
        """随机选两辆车，尝试合并。

        合并策略：将订单较少的车合并到较大的车；若合并后超载则尝试升级车型。
        """
        vehicle_ids = [vid for vid, v in solution.vehicles.items() if v.order_ids]
        if len(vehicle_ids) < 2:
            return solution

        new_sol = solution.deep_copy()

        v1_id, v2_id = rng.sample(vehicle_ids, 2)
        v1 = new_sol.vehicles[v1_id]
        v2 = new_sol.vehicles[v2_id]

        # 将订单少的合并到订单多的（以减少空车）
        if len(v1.order_ids) > len(v2.order_ids):
            dst_vid, src_vid = v1_id, v2_id
        else:
            dst_vid, src_vid = v2_id, v1_id

        dst = new_sol.vehicles[dst_vid]
        src = new_sol.vehicles[src_vid]

        # 合并订单
        merged_oids = dst.order_ids + src.order_ids
        total_pallets = sum(
            calc_pallets(self.instance.orders[oid].spu_list) for oid in merged_oids
        )
        total_hazard = sum(
            self.instance.orders[oid].hazard_quantity
            for oid in merged_oids
            if self.instance.orders[oid].hazard_flag
        )

        # 选合适的车型：优先最小成本车型
        new_vtype = self._select_vehicle_type(total_pallets, total_hazard)
        if new_vtype is None:
            # 合并后超出最大容量，放弃
            return solution

        dst.order_ids = merged_oids
        dst.vehicle_type = new_vtype

        # 更新 assignment
        for oid in src.order_ids:
            new_sol.assignment[oid] = dst_vid

        # 删除源车
        del new_sol.vehicles[src_vid]

        return new_sol

    @staticmethod
    def _select_vehicle_type(total_pallets: int, total_hazard: int) -> str | None:
        """选择能容纳的最小成本车型；若超出所有车型容量则返回 None。"""
        from models import VEHICLE_TYPES_BY_CAPACITY

        if total_hazard > 1800:
            # 必须用专车
            if VEHICLE_TYPES["HQ40_DG"].capacity >= total_pallets:
                return "HQ40_DG"
            return None

        for code, capacity, _cost in VEHICLE_TYPES_BY_CAPACITY:
            if code == "HQ40_DG":
                continue
            if capacity >= total_pallets:
                return code
        return None
