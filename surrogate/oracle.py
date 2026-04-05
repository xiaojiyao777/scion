"""
Feasibility Oracle + Objective Recompute Oracle

严格按 spec §5 §6 实现：
- check_feasibility: 8 条硬约束 fail-fast 顺序检查
- recompute_objective: 独立计算目标函数值
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from models import (
    Instance,
    ObjectiveValue,
    Solution,
    VEHICLE_TYPES,
    calc_pallets,
    get_region,
    get_max_pickups,
)


@dataclass
class FeasibilityResult:
    """可行性检查结果。"""
    is_feasible: bool
    violations: list[str]


def check_feasibility(
    solution: Solution,
    instance: Instance,
    phase: int,
) -> FeasibilityResult:
    """按 spec §5 fail-fast 顺序检查 8 条硬约束。

    检查顺序：
      1. H7 锁定订单未被移动
      2. H4 分车大类隔离（Phase 1）
      3. H2 片区一致
      4. H3 提货点数 ≤ 上限
      5. H1 栈板容量
      6. H5 危险品基线 → 超 1800pcs 必须用专车
      7. H8 非专车危险品 ≤ 1800pcs
      8. H6 装车基线（金额）
    """
    violations: list[str] = []

    for vid, vehicle in solution.vehicles.items():
        if not vehicle.order_ids:
            continue  # 空车跳过

        orders = [instance.orders[oid] for oid in vehicle.order_ids]

        # -----------------------------------------------------------------
        # H7: 锁定订单未被移动
        # -----------------------------------------------------------------
        for o in orders:
            if o.locked_vehicle_id is not None and o.locked_vehicle_id != vid:
                violations.append(
                    f"H7: order {o.order_id} locked to {o.locked_vehicle_id}, "
                    f"but assigned to {vid}"
                )
                return FeasibilityResult(False, violations)

        # -----------------------------------------------------------------
        # H4: 分车大类隔离（Phase 1）
        # Phase 2 中大类隔离由算法标识替代，此处跳过
        # -----------------------------------------------------------------
        if phase == 1:
            categories = {o.vehicle_category for o in orders}
            if len(categories) > 1:
                violations.append(
                    f"H4: vehicle {vid} mixes categories {categories}"
                )
                return FeasibilityResult(False, violations)

        # -----------------------------------------------------------------
        # H2: 片区一致（所有订单的 pickup_city 映射到同一片区）
        # -----------------------------------------------------------------
        regions = {get_region(o.pickup_city) for o in orders}
        if len(regions) > 1:
            violations.append(
                f"H2: vehicle {vid} mixes regions {regions}"
            )
            return FeasibilityResult(False, violations)

        region = next(iter(regions))

        # -----------------------------------------------------------------
        # H3: 提货点数 ≤ 该片区上限
        # -----------------------------------------------------------------
        pickups = {o.pickup_name for o in orders}
        max_pickups = get_max_pickups(region)
        if len(pickups) > max_pickups:
            violations.append(
                f"H3: vehicle {vid} has {len(pickups)} pickups > {max_pickups} "
                f"(region={region})"
            )
            return FeasibilityResult(False, violations)

        # -----------------------------------------------------------------
        # H1: 栈板容量
        # -----------------------------------------------------------------
        total_pallets = sum(calc_pallets(o.spu_list) for o in orders)
        capacity = VEHICLE_TYPES[vehicle.vehicle_type].capacity
        if total_pallets > capacity:
            violations.append(
                f"H1: vehicle {vid} pallets {total_pallets} > capacity {capacity}"
            )
            return FeasibilityResult(False, violations)

        # -----------------------------------------------------------------
        # H5: 危险品 > 1800pcs → 必须用专车 HQ40_DG
        # -----------------------------------------------------------------
        total_hazard = sum(
            o.hazard_quantity for o in orders if o.hazard_flag
        )
        if total_hazard > 1800 and vehicle.vehicle_type != "HQ40_DG":
            violations.append(
                f"H5: vehicle {vid} hazard {total_hazard} > 1800 "
                f"but type is {vehicle.vehicle_type}"
            )
            return FeasibilityResult(False, violations)

        # -----------------------------------------------------------------
        # H8: 非专车危险品 ≤ 1800pcs
        # （危险品专车可混装普货，无限制；非专车则危险品总量不得超 1800）
        # -----------------------------------------------------------------
        if vehicle.vehicle_type != "HQ40_DG" and total_hazard > 1800:
            # 实际上此条件与 H5 完全重叠，但按 spec 顺序保留
            violations.append(
                f"H8: non-hazard-special vehicle {vid} hazard {total_hazard} > 1800"
            )
            return FeasibilityResult(False, violations)

        # -----------------------------------------------------------------
        # H6: 装车基线（按 destination_country × ship_method 分组检查金额之和）
        # -----------------------------------------------------------------
        amount_groups: dict[str, float] = defaultdict(float)
        for o in orders:
            key = f"{o.destination_country},{o.ship_method}"
            amount_groups[key] += o.declaration_amount

        for key, total_amount in amount_groups.items():
            if key in instance.amount_limits and total_amount > instance.amount_limits[key]:
                violations.append(
                    f"H6: vehicle {vid} amount {total_amount:.2f} > "
                    f"limit {instance.amount_limits[key]} for ({key})"
                )
                return FeasibilityResult(False, violations)

    return FeasibilityResult(True, [])


def recompute_objective(
    solution: Solution,
    instance: Instance,
    solve_time_ms: int = 0,
) -> ObjectiveValue:
    """按 spec §6 重新计算目标函数值。

    Level 1: 分车小类拆分总数
    Level 2: 总运输成本（空车不计）
    Level 3: 求解时间（外部传入）
    """
    # Level 1: 每个小类使用了多少辆不同的车
    subcat_vehicles: dict[int, set[str]] = defaultdict(set)
    for oid, vid in solution.assignment.items():
        subcat = instance.orders[oid].vehicle_subcategory
        subcat_vehicles[subcat].add(vid)
    subcategory_splits = sum(
        len(vids) - 1 for vids in subcat_vehicles.values()
    )

    # Level 2: 非空车辆的成本之和
    total_cost = sum(
        VEHICLE_TYPES[v.vehicle_type].cost
        for v in solution.vehicles.values()
        if len(v.order_ids) > 0
    )

    return ObjectiveValue(
        subcategory_splits=subcategory_splits,
        total_cost=total_cost,
        solve_time_ms=solve_time_ms,
    )
