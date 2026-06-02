"""protocol.yaml 加载与校验。

使用 Pydantic v2 做 schema 校验。
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal, Optional

import yaml
from pydantic import BaseModel, Field, model_validator


class ScreeningConfig(BaseModel):
    """Screening 阶段配置。"""

    n_cases_modify: int = Field(gt=0, default=6)
    """modify/remove 操作使用的 case 数量。"""

    n_cases_create: int = Field(gt=0, default=10)
    """create_new 操作使用的 case 数量。"""

    n_seeds: int = Field(gt=0, default=2)
    """每个 case 使用的 seed 数量。"""

    expose: str = "full"
    """暴露控制级别：full / aggregate_only / pass_fail_aggregate。"""

    expand_to_modify: int = Field(gt=0, default=10)
    """expand 时 modify 操作的 case 数量。"""

    expand_to_create: int = Field(gt=0, default=16)
    """expand 时 create 操作的 case 数量。"""


class ValidationConfig(BaseModel):
    """Validation 阶段配置。"""

    n_cases: int = Field(gt=0, default=12)
    """使用的 case 数量。"""

    n_seeds: int = Field(gt=0, default=3)
    """每个 case 使用的 seed 数量。"""

    expose: str = "aggregate_only"
    """暴露控制级别。"""

    expand_to: int = Field(gt=0, default=20)
    """expand 时的 case 数量。"""


class FrozenConfig(BaseModel):
    """Frozen holdout 阶段配置。"""

    n_cases: int = Field(gt=0, default=12)
    """使用的 case 数量。"""

    n_seeds: int = Field(gt=0, default=3)
    """每个 case 使用的 seed 数量。"""

    expose: str = "pass_fail_aggregate"
    """暴露控制级别。"""

    max_uses_per_campaign: int = Field(gt=0, default=3)
    """每次 campaign 中 frozen holdout 的最大使用次数。"""


class CanaryProtocolConfig(BaseModel):
    """Canary regression check 配置。"""

    cases: list[str] = Field(default_factory=list)
    """canary case 文件路径列表。"""

    seeds: list[int] = Field(default_factory=list)
    """canary seed 列表。"""


class RuntimeGovernanceConfig(BaseModel):
    """Runtime/algorithm-efficiency promotion governance."""

    max_runtime_ratio: float = Field(gt=0.0, default=2.0)
    """Maximum accepted candidate/champion median runtime ratio."""

    tie_speedup_ratio: float = Field(gt=0.0, le=1.0, default=0.75)
    """Median candidate/champion runtime ratio that counts as a tie-preserving speedup."""

    tie_min_runtime_pairs: int = Field(gt=0, default=1)
    """Minimum paired runtime samples required for tie-preserving speedup decisions."""

    champion_runtime_policy: Literal[
        "allow_cached",
        "fresh_required_for_runtime_tie",
        "fresh_always",
    ] = "fresh_required_for_runtime_tie"
    """Champion runtime freshness policy for runtime-sensitive promotion evidence."""


class EvaluationStageConfig(BaseModel):
    """Generic staged evaluation step.

    This is intentionally problem-agnostic. Concrete split contents and runtime
    field meanings remain adapter-owned; protocol config only names stages and
    their evidence/exposure policy.
    """

    name: str = Field(min_length=1)
    """Stable stage name such as quick_signal or broad_safety."""

    role: Literal[
        "quick_prescreen",
        "broad_screening",
        "screening",
        "validation",
        "frozen_holdout",
        "diagnostic",
    ]
    """Protocol role for reporting and downstream scheduling hooks."""

    split: Literal["screening", "validation", "frozen", "canary"] = "screening"
    """Split namespace used by the stage."""

    n_cases: Optional[int] = Field(default=None, gt=0)
    """Optional case cap for this stage; None means use the split default."""

    n_seeds: Optional[int] = Field(default=None, gt=0)
    """Optional seed cap for this stage; None means use the ledger default."""

    expose: str = "aggregate_only"
    """Exposure control level for the stage output."""

    gate: Literal["none", "diagnostic", "screening", "validation", "frozen"] = "diagnostic"
    """Gate family applied to the stage result."""

    hard_failure: bool = False
    """Whether this stage may hard-fail the candidate."""

    smoke_runtime_policy: Literal["diagnostic_only", "hard_failure"] = "diagnostic_only"
    """How runtime noise from smoke/pre-screen diagnostics is interpreted."""

    def summary(self) -> dict[str, object]:
        return {
            "name": self.name,
            "role": self.role,
            "split": self.split,
            "n_cases": self.n_cases,
            "n_seeds": self.n_seeds,
            "expose": self.expose,
            "gate": self.gate,
            "hard_failure": self.hard_failure,
            "smoke_runtime_policy": self.smoke_runtime_policy,
        }


class EvaluationPipelineConfig(BaseModel):
    """Optional quick -> broad staged evaluation protocol."""

    enabled: bool = False
    stages: tuple[EvaluationStageConfig, ...] = ()

    @model_validator(mode="after")
    def _validate_stage_names(self) -> "EvaluationPipelineConfig":
        names = [stage.name for stage in self.stages]
        if len(names) != len(set(names)):
            raise ValueError("evaluation pipeline stage names must be unique")
        return self

    def summary(self) -> list[dict[str, object]]:
        return [stage.summary() for stage in self.stages]


class SmokePrescreenConfig(BaseModel):
    """Generic hook for cheap candidate diagnostics before formal protocol."""

    enabled: bool = False
    stage_name: str = "quick_prescreen"
    runtime_noise_policy: Literal["diagnostic_only", "hard_failure"] = "diagnostic_only"
    max_cases: Optional[int] = Field(default=None, gt=0)
    notes: str = ""


class RetryConfig(BaseModel):
    """重试配置。"""

    infra_max: int = Field(ge=0, default=2)
    """基础设施故障最大重试次数。"""

    llm_fix_max: int = Field(ge=0, default=2)
    """LLM fix 最大重试次数。"""


class ScreeningGate(BaseModel):
    """Screening 门控阈值。"""

    win_rate_min: float = Field(ge=0.0, le=1.0, default=0.667)
    """最小胜率阈值。"""

    median_delta_min: str = "practical_delta_screen"
    """最小中位 delta（可引用 problem.yaml 中的配置键名）。"""


class ValidationGate(BaseModel):
    """Validation 门控阈值。"""

    win_rate_min: float = Field(ge=0.0, le=1.0, default=0.667)
    """最小胜率阈值。"""

    median_delta_min: str = "practical_delta_validate"
    """最小中位 delta（引用 problem.yaml 的键名）。"""

    bootstrap_ci_low_min: float = 0.0
    """Bootstrap CI 下界最小值。"""

    bootstrap_n: int = Field(gt=0, default=10000)
    """Bootstrap 重采样次数。"""


class FrozenGate(BaseModel):
    """Frozen holdout 门控阈值。"""

    bootstrap_ci_low_min: float = 0.0
    """Bootstrap CI 下界最小值。"""

    canary_required: bool = True
    """是否要求 canary 通过。"""


class GatesConfig(BaseModel):
    """所有门控阈值配置。"""

    screening: ScreeningGate = Field(default_factory=ScreeningGate)
    validation: ValidationGate = Field(default_factory=ValidationGate)
    frozen: FrozenGate = Field(default_factory=FrozenGate)


class ProtocolConfig(BaseModel):
    """protocol.yaml 的完整 schema。

    Example::

        config = ProtocolConfig.from_yaml("protocol.yaml")
        config.screening.n_cases_modify  # 6
    """

    version: str = "dev"
    """协议版本号。"""

    screening: ScreeningConfig = Field(default_factory=ScreeningConfig)
    validation: ValidationConfig = Field(default_factory=ValidationConfig)
    frozen: FrozenConfig = Field(default_factory=FrozenConfig)

    canary: CanaryProtocolConfig = Field(default_factory=CanaryProtocolConfig)
    """Canary regression check 配置。"""

    retry: RetryConfig = Field(default_factory=RetryConfig)
    """重试配置。"""

    gates: GatesConfig = Field(default_factory=GatesConfig)
    """门控阈值配置。"""

    runtime: RuntimeGovernanceConfig = Field(default_factory=RuntimeGovernanceConfig)
    """Runtime and algorithm-efficiency governance."""

    evaluation_pipeline: EvaluationPipelineConfig = Field(
        default_factory=EvaluationPipelineConfig
    )
    """Optional staged quick/broad evaluation protocol."""

    smoke_prescreen: SmokePrescreenConfig = Field(default_factory=SmokePrescreenConfig)
    """Optional cheap pre-screen diagnostic hook."""

    # ------------------------------------------------------------------
    # Backward-compatibility properties (used by gates.py and old tests)
    # ------------------------------------------------------------------

    @property
    def screening_win_rate_threshold(self) -> float:
        """Alias for gates.screening.win_rate_min."""
        return self.gates.screening.win_rate_min

    @property
    def validation_win_rate_threshold(self) -> float:
        """Alias for gates.validation.win_rate_min."""
        return self.gates.validation.win_rate_min

    @property
    def min_practical_delta(self) -> float:
        """Numeric practical delta threshold (default 0.001)."""
        return 0.001

    @property
    def max_runtime_ratio(self) -> float:
        """Alias for runtime.max_runtime_ratio."""
        return self.runtime.max_runtime_ratio

    def evaluation_stage_summary(self) -> list[dict[str, object]]:
        """Return protocol-stage reporting metadata.

        If an explicit staged pipeline is configured, it is reported verbatim.
        Otherwise this returns the legacy v3 stage shape so callers can render
        one uniform summary.
        """
        if self.evaluation_pipeline.enabled or self.evaluation_pipeline.stages:
            return self.evaluation_pipeline.summary()
        return [
            {
                "name": "screening",
                "role": "screening",
                "split": "screening",
                "n_cases": None,
                "n_seeds": self.screening.n_seeds,
                "expose": self.screening.expose,
                "gate": "screening",
                "hard_failure": True,
                "smoke_runtime_policy": "diagnostic_only",
            },
            {
                "name": "validation",
                "role": "validation",
                "split": "validation",
                "n_cases": self.validation.n_cases,
                "n_seeds": self.validation.n_seeds,
                "expose": self.validation.expose,
                "gate": "validation",
                "hard_failure": True,
                "smoke_runtime_policy": "diagnostic_only",
            },
            {
                "name": "frozen",
                "role": "frozen_holdout",
                "split": "frozen",
                "n_cases": self.frozen.n_cases,
                "n_seeds": self.frozen.n_seeds,
                "expose": self.frozen.expose,
                "gate": "frozen",
                "hard_failure": True,
                "smoke_runtime_policy": "diagnostic_only",
            },
        ]

    @classmethod
    def from_yaml(cls, path: str | Path) -> "ProtocolConfig":
        """从 YAML 文件加载并校验 ProtocolConfig。

        Args:
            path: protocol.yaml 文件路径。

        Returns:
            经过 schema 校验的 ProtocolConfig 实例。

        Raises:
            FileNotFoundError: 文件不存在。
            ValidationError: YAML 内容不符合 schema。
        """
        content = Path(path).read_text(encoding="utf-8")
        data = yaml.safe_load(content)
        return cls.model_validate(data)
