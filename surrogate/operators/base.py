"""
算子基类

所有算子实现统一接口：execute(solution, rng) -> Solution
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from random import Random

from models import Solution


def generate_vehicle_id(rng: Random) -> str:
    """生成确定性的车辆 ID。

    使用 seeded rng 而非 uuid.uuid4()，确保同 seed 下两次 solver run
    产出相同的 vehicle ID，维持 V5 确定性检查。
    """
    return f"V_{rng.randint(0, 2**32 - 1):08x}"


class Operator(ABC):
    """VNS 算子基类。

    子类必须实现 execute 方法，要求：
    1. 先 deep_copy solution 再操作，不修改原解
    2. 只操作未锁定订单（locked_vehicle_id is None）
    3. 如果产出不可行解，返回原解（由调用方验证后决定是否保留）
    4. 生成新车辆 ID 必须使用 generate_vehicle_id(rng)，禁止使用 uuid
    """

    @abstractmethod
    def execute(self, solution: Solution, rng: Random) -> Solution:
        """执行算子，返回新解（或原解，若无法改进）。"""
        ...

    @property
    def name(self) -> str:
        return self.__class__.__name__
