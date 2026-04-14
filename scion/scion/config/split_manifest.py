"""split_manifest.yaml 加载与校验。

四个 case 集合（screening/validation/frozen/canary）必须互不相交。
"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field, model_validator


class SplitManifest(BaseModel):
    """split_manifest.yaml 的完整 schema。

    四个集合（screening / validation / frozen / canary）必须互不相交。

    Example::

        manifest = SplitManifest.from_yaml("split_manifest.yaml")
        manifest.screening  # ['cases/screening/case_001.json', ...]
    """

    version: str = "dev"
    """Manifest 版本号。"""

    screening: list[str] = Field(default_factory=list)
    """Screening 阶段的 case 文件路径列表。"""

    validation: list[str] = Field(default_factory=list)
    """Validation 阶段的 case 文件路径列表。"""

    frozen: list[str] = Field(default_factory=list)
    """Frozen holdout 阶段的 case 文件路径列表。"""

    canary: list[str] = Field(default_factory=list)
    """Canary regression check 的 case 文件路径列表。"""

    @model_validator(mode="after")
    def validate_disjoint(self) -> "SplitManifest":
        """校验 frozen/canary 与其他集合互不相交。

        Screening/validation 允许重叠（validation 用不同 seeds 测试稳定性）。
        Frozen 必须独立作为 holdout。

        Raises:
            ValueError: frozen/canary 与其他集合存在交集。
        """
        screening = set(self.screening)
        validation = set(self.validation)
        frozen = set(self.frozen)
        canary = set(self.canary)

        # Frozen must be disjoint from everything
        for name, other in [("screening", screening), ("validation", validation), ("canary", canary)]:
            overlap = frozen & other
            if overlap:
                raise ValueError(
                    f"split 集合 'frozen' 和 '{name}' 存在交集 (overlap): {sorted(overlap)}"
                )
        # Canary must be disjoint from screening/validation
        for name, other in [("screening", screening), ("validation", validation)]:
            overlap = canary & other
            if overlap:
                raise ValueError(
                    f"split 集合 'canary' 和 '{name}' 存在交集 (overlap): {sorted(overlap)}"
                )
        return self

    @classmethod
    def from_yaml(cls, path: str | Path) -> "SplitManifest":
        """从 YAML 文件加载并校验 SplitManifest。

        Args:
            path: split_manifest.yaml 文件路径。

        Returns:
            经过 schema 校验（含交叉校验）的 SplitManifest 实例。

        Raises:
            FileNotFoundError: 文件不存在。
            ValidationError: YAML 内容不符合 schema 或集合存在交集。
        """
        content = Path(path).read_text(encoding="utf-8")
        data = yaml.safe_load(content)
        return cls.model_validate(data)
