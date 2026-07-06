"""protocol.yaml 加载与校验。

使用 Pydantic v2 做 schema 校验。
"""

from __future__ import annotations

import fnmatch
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any, Literal, Optional

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator

from scion.measurement.consumer_view import measurement_consumer_view


MeasurementGovernanceMode = Literal["on", "record_only"]


def _normalize_measurement_governance_mode(value: Any | None) -> MeasurementGovernanceMode:
    text = "on" if value is None else str(value).strip().lower().replace("-", "_")
    if text == "on":
        return "on"
    if text == "record_only":
        return "record_only"
    raise ValueError("measurement_governance must be on or record_only")


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

    priority_case_ids: tuple[str, ...] = ()
    """Stage-local case ids retained during deterministic screening selection."""


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

    runtime_model: Literal["comparative", "budget_exhausting"] = "comparative"
    """Runtime interpretation model declared by the problem measurement layer."""

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

    time_limits: "RuntimeTimeLimitConfig" = Field(
        default_factory=lambda: RuntimeTimeLimitConfig()
    )
    """Optional stage/case runtime budget overrides for protocol execution."""


class RuntimeTimeLimitRule(BaseModel):
    """Optional ordered runtime budget override for matching case/stage pairs."""

    time_limit_sec: int = Field(gt=0)
    """Solver budget for matching pairs."""

    stages: tuple[
        Literal["screening", "validation", "frozen", "canary"],
        ...,
    ] = ()
    """Stages this rule applies to; empty means all formal stages."""

    case_globs: tuple[str, ...] = ()
    """fnmatch patterns matched against the full case path and basename."""

    min_dimension: Optional[int] = Field(default=None, ge=0)
    """Minimum parsed case dimension, inclusive."""

    max_dimension: Optional[int] = Field(default=None, ge=0)
    """Maximum parsed case dimension, inclusive."""

    @model_validator(mode="after")
    def _validate_bounds(self) -> "RuntimeTimeLimitRule":
        if (
            self.min_dimension is not None
            and self.max_dimension is not None
            and self.min_dimension > self.max_dimension
        ):
            raise ValueError("min_dimension must be <= max_dimension")
        return self

    def matches(self, *, stage: str, case_path: str) -> bool:
        if self.stages and stage not in self.stages:
            return False
        normalized_case = str(case_path or "")
        basename = Path(normalized_case).name
        if self.case_globs and not any(
            fnmatch.fnmatch(normalized_case, pattern)
            or fnmatch.fnmatch(basename, pattern)
            for pattern in self.case_globs
        ):
            return False
        dimension = _case_dimension(normalized_case)
        if self.min_dimension is not None and (
            dimension is None or dimension < self.min_dimension
        ):
            return False
        if self.max_dimension is not None and (
            dimension is None or dimension > self.max_dimension
        ):
            return False
        return True

    def summary(self) -> dict[str, Any]:
        return {
            "time_limit_sec": self.time_limit_sec,
            "stages": list(self.stages),
            "case_globs": list(self.case_globs),
            "min_dimension": self.min_dimension,
            "max_dimension": self.max_dimension,
        }


class RuntimeTimeLimitConfig(BaseModel):
    """Stage defaults plus ordered case-size runtime budget overrides."""

    stage_defaults: dict[
        Literal["screening", "validation", "frozen", "canary"],
        int,
    ] = Field(default_factory=dict)
    """Default solver budget by stage; absent stages use CLI/problem default."""

    rules: tuple[RuntimeTimeLimitRule, ...] = ()
    """Ordered overrides; later matching rules take precedence."""

    @model_validator(mode="after")
    def _validate_stage_defaults(self) -> "RuntimeTimeLimitConfig":
        invalid = [
            f"{stage}={value}"
            for stage, value in self.stage_defaults.items()
            if int(value) <= 0
        ]
        if invalid:
            raise ValueError(
                "runtime.time_limits.stage_defaults must be positive: "
                + ", ".join(invalid)
            )
        return self

    def resolve(
        self,
        *,
        stage: str,
        case_path: str,
        fallback_time_limit_sec: int | float,
    ) -> int:
        stage_key = str(stage or "").strip().lower()
        fallback = max(1, int(fallback_time_limit_sec))
        limit = int(self.stage_defaults.get(stage_key, fallback))
        for rule in self.rules:
            if rule.matches(stage=stage_key, case_path=case_path):
                limit = int(rule.time_limit_sec)
        return max(1, int(limit))

    def summary(
        self,
        *,
        stage: str,
        cases: list[str] | tuple[str, ...],
        fallback_time_limit_sec: int | float,
    ) -> dict[str, Any]:
        resolved = [
            self.resolve(
                stage=stage,
                case_path=case,
                fallback_time_limit_sec=fallback_time_limit_sec,
            )
            for case in cases
        ]
        return {
            "stage": stage,
            "fallback_time_limit_sec": max(1, int(fallback_time_limit_sec)),
            "stage_default_sec": self.stage_defaults.get(stage),
            "resolved_min_sec": min(resolved) if resolved else None,
            "resolved_max_sec": max(resolved) if resolved else None,
            "resolved_unique_sec": sorted(set(resolved)),
            "rules": [rule.summary() for rule in self.rules],
        }


def _case_dimension(case_path: str) -> int | None:
    stem = Path(str(case_path or "")).stem
    patterns = (
        r"(?:^|[-_])n(?P<dimension>\d+)(?:[-_]|$)",
        r"(?:^|[-_])tai(?P<dimension>\d+)",
    )
    for pattern in patterns:
        match = re.search(pattern, stem, flags=re.IGNORECASE)
        if match:
            return int(match.group("dimension"))
    return None


def _nonnegative_float(name: str, value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a non-negative number") from exc
    if number < 0.0:
        raise ValueError(f"{name} must be a non-negative number")
    return number


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


class ExpandedBorderlineAdvanceConfig(BaseModel):
    """Policy for advancing borderline candidates after screening expand is exhausted."""

    enabled: bool = False
    """Whether below-threshold expanded screening results may queue validation."""

    win_rate_window: float = Field(default=0.05, ge=0.0, le=1.0)
    """Allowed shortfall below screening.win_rate_min."""

    require_median_delta_nonnegative: bool = True
    """Require median_delta >= 0; missing median_delta fails closed."""

    require_ci_low_nonnegative: bool = False
    """Require ci_low >= 0 when screening produces CI evidence."""

    allow_pair_level_signal: bool = False
    """Allow measurable pair-level signal to enter validation after expand."""

    pair_win_rate_min: float = Field(default=0.5, ge=0.0, le=1.0)
    """Minimum pair win rate across all evaluated pairs for diagnostic advance."""

    min_pair_total: int = Field(default=0, ge=0)
    """Minimum number of evaluated pairs required for diagnostic advance."""

    min_pair_wins: int = Field(default=0, ge=0)
    """Minimum pair wins required for diagnostic advance."""

    min_pair_win_loss_margin: int = Field(default=1, ge=0)
    """Minimum pair_wins - pair_losses margin for diagnostic advance."""

    pair_non_tie_win_rate_min: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    """Minimum pair win rate over non-tie pairs, when configured."""

    max_pair_loss_rate: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    """Maximum pair loss rate across all evaluated pairs, when configured."""


class ScreeningGate(BaseModel):
    """Screening 门控阈值。"""

    win_rate_min: float = Field(ge=0.0, le=1.0, default=0.667)
    """最小胜率阈值。"""

    median_delta_min: str | float = "practical_delta_screen"
    """最小中位 delta（可引用 problem.yaml 中的配置键名）。"""

    expanded_borderline_advance: ExpandedBorderlineAdvanceConfig = Field(
        default_factory=ExpandedBorderlineAdvanceConfig
    )
    """Explicit policy for expanded-screening borderline advancement."""


class ValidationGate(BaseModel):
    """Validation 门控阈值。"""

    win_rate_min: float = Field(ge=0.0, le=1.0, default=0.667)
    """最小胜率阈值。"""

    median_delta_min: str | float = "practical_delta_validate"
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


class MeasurementReadinessConfig(BaseModel):
    """Reduced measurement readiness status safe for generic config consumers."""

    status: Literal["ready", "degraded", "not_ready"] = "not_ready"
    reason_code: Literal[
        "ok",
        "missing_measurement",
        "missing_calibration_ref",
        "calibration_not_found",
        "calibration_unreadable",
        "calibration_incompatible",
        "calibration_incomplete",
        "calibration_stale",
    ] = "missing_measurement"
    calibration_age_days: int | None = Field(default=None, ge=0)
    calibration_max_age_days: int = Field(default=0, ge=0)
    n_pairs: int = Field(default=0, ge=0)
    mde_at_power_80: float | None = Field(default=None, ge=0.0)
    noise_band_p90_abs: float | None = Field(default=None, ge=0.0)
    effect_to_mde_ratio: float | None = Field(default=None, ge=0.0)
    signal_to_noise_tier: Literal["ready", "marginal", "low_power", "unknown"] = (
        "unknown"
    )
    calibration_evidence_level: Literal[
        "none",
        "summary_only",
        "pair_evidence",
        "full_replay",
    ] = "none"
    decision_features_excluded: bool = True


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

    practical_delta_screen: float = Field(default=0.001, ge=0.0)
    """Resolved screening practical delta in the protocol's current delta units."""

    practical_delta_validate: float = Field(default=0.001, ge=0.0)
    """Resolved validation practical delta in the protocol's current delta units."""

    pairing_validity: Literal["trajectory_stable", "trajectory_divergent"] = (
        "trajectory_stable"
    )
    """Problem-declared solver trajectory pairing model for gate/lifecycle policy."""

    measurement_governance: MeasurementGovernanceMode = "on"
    """Whether problem measurement governs protocol behavior or is status-only."""

    measurement_readiness: MeasurementReadinessConfig = Field(
        default_factory=MeasurementReadinessConfig
    )
    """Reduced measurement readiness status derived from problem-owned calibration."""

    evaluation_pipeline: EvaluationPipelineConfig = Field(
        default_factory=EvaluationPipelineConfig
    )
    """Optional staged quick/broad evaluation protocol."""

    smoke_prescreen: SmokePrescreenConfig = Field(default_factory=SmokePrescreenConfig)
    """Optional cheap pre-screen diagnostic hook."""

    @model_validator(mode="after")
    def _validate_delta_references(self) -> "ProtocolConfig":
        self._resolve_delta_reference(self.gates.screening.median_delta_min)
        self._resolve_delta_reference(self.gates.validation.median_delta_min)
        return self

    @field_validator("measurement_governance", mode="before")
    @classmethod
    def _validate_measurement_governance(cls, value: Any) -> MeasurementGovernanceMode:
        return _normalize_measurement_governance_mode(value)

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
        """Backward-compatible alias for the resolved screening practical delta."""
        return self.screening_min_practical_delta

    @property
    def screening_min_practical_delta(self) -> float:
        """Resolved screening practical delta."""
        return self._resolve_delta_reference(self.gates.screening.median_delta_min)

    @property
    def validation_min_practical_delta(self) -> float:
        """Resolved validation practical delta."""
        return self._resolve_delta_reference(self.gates.validation.median_delta_min)

    @property
    def max_runtime_ratio(self) -> float:
        """Alias for runtime.max_runtime_ratio."""
        return self.runtime.max_runtime_ratio

    def with_problem_measurement(
        self,
        problem_spec: Any | None,
        *,
        governance_mode: Any | None = None,
        measurement_readiness_as_of: date | datetime | None = None,
    ) -> "ProtocolConfig":
        """Return a copy with problem-owned measurement thresholds resolved.

        When measurement governance is ``on``, problem-owned measurement facts
        may configure protocol thresholds and runtime/pairing governance.  When
        it is ``record_only``, only reduced readiness status is recorded for
        audit/status; practical deltas, runtime model, and pairing validity stay
        on the protocol defaults or YAML values.  Neither mode exposes raw
        calibration diagnostics, BKS, gap, or free-form text to DecisionFeatures.
        """

        mode = _normalize_measurement_governance_mode(
            self.measurement_governance if governance_mode is None else governance_mode
        )
        measurement_view = measurement_consumer_view(
            problem_spec,
            as_of=measurement_readiness_as_of,
        )
        data = self.model_dump()
        data["measurement_governance"] = mode
        data["measurement_readiness"] = measurement_view.to_readiness_status_payload()
        if mode == "record_only" or not measurement_view.measurement_declared:
            return type(self).model_validate(data)

        updates: dict[str, float] = {}
        if measurement_view.practical_delta_screen is not None:
            updates["practical_delta_screen"] = _nonnegative_float(
                "practical_delta_screen",
                measurement_view.practical_delta_screen,
            )
        if measurement_view.practical_delta_validate is not None:
            updates["practical_delta_validate"] = _nonnegative_float(
                "practical_delta_validate",
                measurement_view.practical_delta_validate,
            )
        runtime_payload = dict(self.runtime.model_dump())
        runtime_payload["runtime_model"] = measurement_view.runtime_model
        data["runtime"] = runtime_payload
        data["pairing_validity"] = measurement_view.pairing_validity
        if not updates:
            return type(self).model_validate(data)
        data.update(updates)
        return type(self).model_validate(data)

    def _resolve_delta_reference(self, value: str | float | int) -> float:
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return _nonnegative_float("median_delta_min", value)
        text = str(value).strip()
        if text == "practical_delta_screen":
            return float(self.practical_delta_screen)
        if text == "practical_delta_validate":
            return float(self.practical_delta_validate)
        try:
            return _nonnegative_float("median_delta_min", text)
        except ValueError as exc:
            raise ValueError(
                "median_delta_min must be numeric or one of "
                "'practical_delta_screen', 'practical_delta_validate'"
            ) from exc

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
