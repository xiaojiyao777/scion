"""
Solution Pool

管理一组候选解（pool_size=40），支持：
- 初始化（从单个或多个解填充）
- 更新（新旧合并取 top-K）
- 排序（按目标函数字典序）
"""

from __future__ import annotations

from models import Instance, ObjectiveValue, Solution
from oracle import recompute_objective


class SolutionPool:
    """维护 top-K 最优解的解池。

    排序依据：ObjectiveValue 字典序（splits → cost → time）。
    """

    def __init__(self, pool_size: int = 40) -> None:
        self.pool_size = pool_size
        self._solutions: list[Solution] = []

    # ------------------------------------------------------------------
    # 公开接口
    # ------------------------------------------------------------------

    def initialize(self, solutions: list[Solution], instance: Instance) -> None:
        """用给定解列表初始化 pool。

        每个解会计算目标函数值（若尚未计算）。
        """
        for sol in solutions:
            if sol.objective is None:
                sol.objective = recompute_objective(sol, instance)
        self._solutions = solutions
        self._trim()

    def update(self, new_solutions: list[Solution], instance: Instance) -> None:
        """将新解与当前 pool 合并，取 top-K。

        spec §4.3：新 40 个 + 旧 40 个合并，字典序排序取 top-40。
        """
        for sol in new_solutions:
            if sol.objective is None:
                sol.objective = recompute_objective(sol, instance)
        combined = self._solutions + new_solutions
        combined.sort(key=lambda s: s.objective.as_tuple())  # type: ignore[union-attr]
        self._solutions = combined[: self.pool_size]

    def best(self) -> Solution | None:
        """返回当前最优解（pool[0]）。"""
        return self._solutions[0] if self._solutions else None

    def all(self) -> list[Solution]:
        """返回 pool 内所有解的副本列表（顺序：最优在前）。"""
        return list(self._solutions)

    def __len__(self) -> int:
        return len(self._solutions)

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def _trim(self) -> None:
        """排序并截断到 pool_size。"""
        self._solutions.sort(key=lambda s: s.objective.as_tuple())  # type: ignore[union-attr]
        self._solutions = self._solutions[: self.pool_size]
