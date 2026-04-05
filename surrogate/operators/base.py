"""
算子基类

所有算子实现统一接口：execute(solution, rng) -> Solution
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from random import Random

from models import Solution


class Operator(ABC):
    """VNS 算子基类。

    子类必须实现 execute 方法，要求：
    1. 先 deep_copy solution 再操作，不修改原解
    2. 只操作未锁定订单（locked_vehicle_id is None）
    3. 如果产出不可行解，返回原解（由调用方验证后决定是否保留）
    """

    @abstractmethod
    def execute(self, solution: Solution, rng: Random) -> Solution:
        """执行算子，返回新解（或原解，若无法改进）。"""
        ...

    @property
    def name(self) -> str:
        return self.__class__.__name__
