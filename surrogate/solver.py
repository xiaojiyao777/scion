"""
Solver 入口

加载 JSON 实例 → 生成初始解 → 运行 VNS → 输出最优解 JSON

用法：
  python solver.py <instance.json> [--phase 1|2] [--output result.json]
"""

from __future__ import annotations

import argparse
import importlib
import json
import sys
import time
from pathlib import Path

from config import Config
from greedy_init import greedy_init
from models import (
    Instance,
    ObjectiveValue,
    Order,
    SPU,
    Solution,
    Vehicle,
    VEHICLE_TYPES,
)
from operators import (
    ChangeVehicleType,
    DestroyRebuild,
    MergeVehicles,
    MoveOrder,
    SplitVehicle,
    SwapOrders,
)
from oracle import check_feasibility, recompute_objective
from vns import run_vns


# ---------------------------------------------------------------------------
# JSON 加载
# ---------------------------------------------------------------------------

def load_instance(path: str | Path, phase: int = 1) -> Instance:
    """从 JSON 文件加载问题实例。

    JSON 格式与 data_generator.py 输出一致：
    {
      "orders": [...],
      "amount_limits": {"德国,海运": 1000000, ...},
      "vehicle_types": {...}   // 可选，忽略
    }
    """
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    orders: dict[str, Order] = {}
    for o in data["orders"]:
        spu_list = [SPU(packing_type=s["packing_type"], quantity=s["quantity"])
                    for s in o["spu_list"]]
        order = Order(
            order_id=o["order_id"],
            vehicle_category=o["vehicle_category"],
            vehicle_subcategory=o["vehicle_subcategory"],
            urgent=o["urgent"],
            hazard_flag=o["hazard_flag"],
            hazard_quantity=o["hazard_quantity"],
            pickup_name=o["pickup_name"],
            pickup_province=o["pickup_province"],
            pickup_city=o["pickup_city"],
            declaration_amount=o["declaration_amount"],
            lsp=o["lsp"],
            ship_method=o["ship_method"],
            destination_country=o["destination_country"],
            spu_list=spu_list,
            locked_vehicle_id=o.get("locked_vehicle_id"),
        )
        orders[order.order_id] = order

    amount_limits: dict[str, float] = data.get("amount_limits", {})

    return Instance(
        orders=orders,
        amount_limits=amount_limits,
        phase=phase,
    )


# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Scion 动态算子加载
# ---------------------------------------------------------------------------

def _load_operators_from_registry(
    registry_path: str | Path,
    instance: Instance,
    phase: int,
) -> tuple[list, list[float]]:
    """从 Scion 导出的 registry.yaml 动态加载算子。

    registry.yaml 格式：
      operators:
        - name: swap_orders
          file_path: operators/swap_orders.py
          class_name: SwapOrders
          weight: 0.25

    向后兼容：如果 registry_path 为 None，不会调用本函数。
    """
    import yaml

    with open(registry_path, encoding="utf-8") as f:
        registry = yaml.safe_load(f)

    operators = []
    weights = []
    for entry in registry["operators"]:
        # entry["file_path"] 格式如 "operators/swap_orders.py"
        # 提取模块名："operators.swap_orders"
        fp = entry["file_path"]
        module_name = fp.replace("/", ".").replace(".py", "")
        module = importlib.import_module(module_name)
        cls = getattr(module, entry["class_name"])
        operators.append(cls(instance, phase))
        weights.append(entry.get("weight", 1.0))

    return operators, weights


# ---------------------------------------------------------------------------
# 解序列化（用于 JSON 输出）
# ---------------------------------------------------------------------------

def solution_to_dict(solution: Solution, instance: Instance | None = None, phase: int = 1) -> dict:
    """将 Solution 转为可序列化的字典。"""
    vehicles_out = {}
    for vid, v in solution.vehicles.items():
        vehicles_out[vid] = {
            "vehicle_id": v.vehicle_id,
            "vehicle_type": v.vehicle_type,
            "region": v.region,
            "order_ids": v.order_ids,
            "cost": VEHICLE_TYPES[v.vehicle_type].cost,
        }

    obj = solution.objective
    objective_out = {
        "subcategory_splits": obj.subcategory_splits if obj else None,
        "total_cost": obj.total_cost if obj else None,
        "solve_time_ms": obj.solve_time_ms if obj else None,
    }

    feasible = True
    if instance is not None:
        feas = check_feasibility(solution, instance, phase)
        feasible = feas.is_feasible

    return {
        "vehicles": vehicles_out,
        "assignment": solution.assignment,
        "objective": objective_out,
        "feasible": feasible,
    }


# ---------------------------------------------------------------------------
# 主函数
# ---------------------------------------------------------------------------

def solve(
    instance: Instance,
    cfg: Config | None = None,
    registry_path: str | Path | None = None,
) -> Solution:
    """执行完整求解流程，返回最优解。

    Args:
        instance: 问题实例
        cfg: 配置（可选）
        registry_path: Scion registry.yaml 路径（可选）。
                       传入时从 registry 动态加载算子，不传则用硬编码默认算子。
    """
    if cfg is None:
        cfg = Config()

    # 1. 生成初始解
    init_sol = greedy_init(instance)

    # 检查初始解可行性（如有违反则警告，仍继续求解）
    feas = check_feasibility(init_sol, instance, instance.phase)
    if not feas.is_feasible:
        # 初始解不可行时仍尝试优化（VNS 会自动丢弃不可行解）
        pass

    init_sol.objective = recompute_objective(init_sol, instance)

    # 2. 构建算子列表
    operator_classes = [
        SwapOrders,
        MoveOrder,
        DestroyRebuild,
        MergeVehicles,
        ChangeVehicleType,
        SplitVehicle,
    ]
    operators = [cls(instance, instance.phase) for cls in operator_classes]
    weights = [
        cfg.operator_weights.get(cls.__name__, 1.0)
        for cls in operator_classes
    ]

    # 2b. 如果提供了 registry，覆盖算子列表（Scion 动态加载）
    if registry_path is not None:
        operators, weights = _load_operators_from_registry(
            registry_path, instance, instance.phase
        )

    # 3. 运行 VNS
    best = run_vns(
        instance=instance,
        initial_solutions=[init_sol],
        operators=operators,
        operator_weights=weights,
        cfg=cfg,
    )

    return best


def main() -> None:
    parser = argparse.ArgumentParser(description="Scion Surrogate Solver")
    parser.add_argument("instance", help="输入实例 JSON 路径")
    parser.add_argument("--phase", type=int, default=1, choices=[1, 2],
                        help="求解阶段（1=一次分车，2=二次合并）")
    parser.add_argument("--output", default=None, help="输出 JSON 路径（默认 stdout）")
    parser.add_argument("--max-iter", type=int, default=None,
                        help="最大迭代次数（覆盖 config 默认值）")
    parser.add_argument("--seed", type=int, default=None, help="随机种子")
    parser.add_argument("--registry", default=None,
                        help="Scion operator registry YAML 路径（动态加载算子）")
    parser.add_argument("--time-limit", type=int, default=None,
                        help="求解时间上限（秒）")
    args = parser.parse_args()

    cfg = Config()
    if args.max_iter is not None:
        cfg.max_iterations = args.max_iter
    if args.seed is not None:
        cfg.random_seed = args.seed

    # 加载实例
    instance = load_instance(args.instance, phase=args.phase)

    # 计时求解
    t0 = time.time()
    best = solve(instance, cfg, registry_path=args.registry)
    elapsed_ms = int((time.time() - t0) * 1000)

    # 写入求解时间
    if best.objective:
        best.objective.solve_time_ms = elapsed_ms

    # 输出
    result = solution_to_dict(best, instance, args.phase)
    out_json = json.dumps(result, ensure_ascii=False, indent=2)

    if args.output:
        Path(args.output).write_text(out_json, encoding="utf-8")
        print(f"结果已写入 {args.output}（耗时 {elapsed_ms}ms）", file=sys.stderr)
    else:
        print(out_json)


if __name__ == "__main__":
    main()
