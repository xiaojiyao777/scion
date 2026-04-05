"""
超参数配置

所有算法超参数集中在此文件，便于 Scion agent 实验调整。
"""

from dataclasses import dataclass, field


@dataclass
class Config:
    """VNS 主循环超参数。"""

    # Solution Pool 大小
    pool_size: int = 40

    # 最大迭代轮次（每轮对 pool 内所有解各执行一次算子）
    max_iterations: int = 200

    # 连续多少轮无任何指标改进则提前退出
    no_improve_limit: int = 30

    # 随机种子（None = 不固定）
    random_seed: int | None = 42

    # 算子权重（归一化前的相对权重）
    # 格式：算子类名 → 权重
    operator_weights: dict[str, float] = field(default_factory=lambda: {
        "SwapOrders":        3.0,  # 高频：小幅扰动，改善成本
        "MoveOrder":         3.0,  # 高频：减少拆分
        "DestroyRebuild":    2.0,  # 中频：跳出局部最优
        "MergeVehicles":     2.0,  # 中频：减少成本
        "ChangeVehicleType": 2.0,  # 中频：降级节省成本
        "SplitVehicle":      1.0,  # 低频：修复超载
    })
