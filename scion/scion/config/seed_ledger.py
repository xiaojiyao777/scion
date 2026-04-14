"""seed_ledger.yaml 加载与校验。

每个实验阶段维护独立的 seed 列表，确保实验可复现。
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field


class SeedLedger(BaseModel):
    """seed_ledger.yaml 的完整 schema。

    各阶段 seed 列表独立管理，防止跨阶段的信息泄漏。

    Example::

        ledger = SeedLedger.from_yaml("seed_ledger.yaml")
        ledger.screening  # [42, 123]
    """

    version: str = "dev"
    """Ledger 版本号。"""

    screening: list[int] = Field(default_factory=list)
    """Screening 阶段使用的 seed 列表。"""

    validation: list[int] = Field(default_factory=list)
    """Validation 阶段使用的 seed 列表。"""

    frozen: list[int] = Field(default_factory=list)
    """Frozen holdout 阶段使用的 seed 列表。"""

    canary: list[int] = Field(default_factory=list)
    """Canary regression check 使用的 seed 列表。"""

    def get_seeds(self, stage: Literal["screening", "validation", "frozen", "canary"]) -> list[int]:
        """根据实验阶段返回对应的 seed 列表。

        Args:
            stage: 实验阶段名称。

        Returns:
            对应阶段的 seed 列表。

        Raises:
            ValueError: stage 不合法。
        """
        mapping = {
            "screening": self.screening,
            "validation": self.validation,
            "frozen": self.frozen,
            "canary": self.canary,
        }
        if stage not in mapping:
            raise ValueError(f"未知阶段: '{stage}'，合法值: {list(mapping.keys())}")
        return list(mapping[stage])

    @classmethod
    def from_yaml(cls, path: str | Path) -> "SeedLedger":
        """从 YAML 文件加载并校验 SeedLedger。

        Args:
            path: seed_ledger.yaml 文件路径。

        Returns:
            经过 schema 校验的 SeedLedger 实例。

        Raises:
            FileNotFoundError: 文件不存在。
            ValidationError: YAML 内容不符合 schema。
        """
        content = Path(path).read_text(encoding="utf-8")
        data = yaml.safe_load(content)
        return cls.model_validate(data)
