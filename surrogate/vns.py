"""
VNS 主循环

Variable Neighborhood Search：
  for each iteration:
      for each solution in pool:
          算子 = 按累积概率随机选取
          new_sol = 算子.execute(solution, rng)
          if new_sol 可行: 加入本轮新解列表
      pool.update(新解 + 旧解 → top-40)
  终止：达到 max_iterations 或连续 no_improve_limit 轮无任何指标改进
"""

from __future__ import annotations

import itertools
from random import Random
from typing import Callable

from config import Config
from models import Instance, ObjectiveValue, Solution
from operators.base import Operator
from oracle import check_feasibility, recompute_objective
from pool import SolutionPool


def build_cumulative_weights(
    operators: list[Operator],
    weights: list[float],
) -> list[float]:
    """将权重列表转为累积概率数组（归一化）。"""
    total = sum(weights)
    cumulative = list(itertools.accumulate(w / total for w in weights))
    return cumulative


def select_operator(
    operators: list[Operator],
    cumulative: list[float],
    rng: Random,
) -> Operator:
    """按累积概率数组随机选择一个算子。"""
    r = rng.random()
    for op, threshold in zip(operators, cumulative):
        if r <= threshold:
            return op
    return operators[-1]  # 兜底


def run_vns(
    instance: Instance,
    initial_solutions: list[Solution],
    operators: list[Operator],
    operator_weights: list[float],
    cfg: Config,
    on_iteration: Callable[[int, Solution], None] | None = None,
) -> Solution:
    """执行 VNS 主循环，返回最终最优解。

    Args:
        instance: 问题实例
        initial_solutions: 初始解列表（至少 1 个）
        operators: 算子列表
        operator_weights: 与 operators 对应的权重（未归一化）
        cfg: 超参数配置
        on_iteration: 可选回调，每轮结束时调用 on_iteration(iter_idx, best_solution)
    """
    rng = Random(cfg.random_seed)
    cumulative = build_cumulative_weights(operators, operator_weights)

    # 初始化 pool
    pool = SolutionPool(pool_size=cfg.pool_size)
    # 用初始解填充 pool（若初始解不足则重复）
    seeds: list[Solution] = []
    for i in range(cfg.pool_size):
        seeds.append(initial_solutions[i % len(initial_solutions)].deep_copy())
    pool.initialize(seeds, instance)

    best_obj: ObjectiveValue | None = pool.best().objective if pool.best() else None
    no_improve_count = 0

    for iteration in range(cfg.max_iterations):
        current_pool = pool.all()
        new_solutions: list[Solution] = []

        for sol in current_pool:
            # 按累积概率选算子
            op = select_operator(operators, cumulative, rng)
            candidate = op.execute(sol, rng)

            # 检查可行性；不可行解丢弃，保留原解
            result = check_feasibility(candidate, instance, instance.phase)
            if result.is_feasible:
                # 重新计算目标值
                candidate.objective = recompute_objective(candidate, instance)
                new_solutions.append(candidate)
            else:
                # 保留原解以维持 pool 大小
                new_solutions.append(sol.deep_copy())

        pool.update(new_solutions, instance)

        current_best = pool.best()
        current_obj = current_best.objective if current_best else None

        if on_iteration:
            on_iteration(iteration, current_best)

        # 终止检查：连续无改进
        if best_obj is not None and current_obj is not None:
            if current_obj.as_tuple() < best_obj.as_tuple():
                best_obj = current_obj
                no_improve_count = 0
            else:
                no_improve_count += 1
        else:
            best_obj = current_obj
            no_improve_count = 0

        if no_improve_count >= cfg.no_improve_limit:
            break

    best = pool.best()
    if best is None:
        raise RuntimeError("VNS 结束但 pool 为空，初始解生成可能失败")
    return best
