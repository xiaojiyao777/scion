from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Callable, List, Optional, Sequence

from scion.config.problem import ProtocolConfig
from scion.core.models import CanaryResult, ExperimentStage, ProtocolResult
from scion.runtime.runner import Runner

from .selection import (
    CasePathResolution,
    SeedLedger,
    SplitManager,
    resolve_case_path_details,
    select_cases,
    select_seeds,
    validate_case_path_resolution,
)

if TYPE_CHECKING:
    from scion.problem.spec import ObjectiveMetricSpec, ObjectivePolicySpec

    from .types import PairedExecutionSpec

logger = logging.getLogger(__name__)


class ExperimentProtocol:
    def __init__(
        self,
        protocol_config: ProtocolConfig,
        split_manager: SplitManager,
        seed_ledger: SeedLedger,
        runner: Runner,
        time_limit_sec: int = 300,
        metrics_dir: str = "/tmp/scion_metrics",
        *,
        metric_specs: Optional[Sequence[ObjectiveMetricSpec]] = None,
        objective_policy: "ObjectivePolicySpec | None" = None,
        problem_spec: Any | None = None,
    ) -> None:
        self.config = protocol_config
        self.split_manager = split_manager
        self.seed_ledger = seed_ledger
        self.runner = runner
        self.time_limit_sec = time_limit_sec
        self.metrics_dir = metrics_dir
        self._metric_specs = _hydrate_metric_specs(metric_specs, problem_spec)
        self._objective_policy = objective_policy or _hydrate_objective_policy(
            problem_spec
        )
        self._problem_spec = problem_spec
        self._problem_adapter: Any | None = None
        self._strict_case_paths = True
        self._progress_callback: Optional[Callable[..., None]] = None
        if not _has_metric_specs(self._metric_specs):
            raise ValueError("metric_specs are required for ExperimentProtocol")

    def set_problem_adapter(self, adapter: Any | None) -> None:
        """Attach the campaign adapter for optional problem-owned projections."""

        self._problem_adapter = adapter

    def set_progress_callback(self, callback: Optional[Callable[..., None]]) -> None:
        """Register a lightweight progress hook for long validation/frozen runs."""
        self._progress_callback = callback
        runner_hook = getattr(self.runner, "set_progress_callback", None)
        if callable(runner_hook):
            try:
                runner_hook(self._emit_progress if callback is not None else None)
            except Exception:
                logger.debug(
                    "Runner progress callback registration failed", exc_info=True
                )

    def _emit_progress(self, **payload: object) -> None:
        if self._progress_callback is None:
            return
        try:
            self._progress_callback(**payload)
        except Exception:
            logger.debug("Experiment progress callback failed", exc_info=True)

    def _compare_objectives(
        self,
        candidate_objective: dict,
        champion_objective: dict,
    ) -> tuple:
        """Return (comparison_str, ObjectiveComparison)."""
        if getattr(self._objective_policy, "mode", None) == "weighted_sum":
            from scion.problem.objectives import compare_weighted_sum

            result = compare_weighted_sum(
                self._metric_specs,
                candidate_objective,
                champion_objective,
            )
        else:
            from scion.problem.objectives import compare_lexicographic

            result = compare_lexicographic(
                self._metric_specs,
                candidate_objective,
                champion_objective,
            )
        return result.outcome, result

    def _compute_delta(
        self,
        candidate_objective: dict,
        champion_objective: dict,
    ) -> float:
        if getattr(self._objective_policy, "mode", None) == "weighted_sum":
            from scion.problem.objectives import compare_weighted_sum

            result = compare_weighted_sum(
                self._metric_specs,
                candidate_objective,
                champion_objective,
            )
        else:
            from scion.problem.objectives import compare_lexicographic

            result = compare_lexicographic(
                self._metric_specs,
                candidate_objective,
                champion_objective,
            )
        return result.scalar_delta

    @property
    def objective_semantics(self) -> str:
        mode = getattr(self._objective_policy, "mode", None) or "lexicographic"
        return f"declared_objectives_{mode}"

    @property
    def problem_spec(self) -> Any | None:
        return self._problem_spec

    def run_canary(
        self,
        candidate_ws: str,
        champion_ws: str,
        *,
        selected_surface: str | None = None,
        require_complete_pairs: bool = False,
    ) -> CanaryResult:
        from .canary import run_canary

        return run_canary(
            self,
            candidate_ws,
            champion_ws,
            selected_surface=selected_surface,
            require_complete_pairs=require_complete_pairs,
        )

    def _select_cases(
        self,
        stage: ExperimentStage,
        hypothesis_action: str,
        expand_round: int,
    ) -> List[str]:
        return select_cases(
            config=self.config,
            split_manager=self.split_manager,
            stage=stage,
            hypothesis_action=hypothesis_action,
            expand_round=expand_round,
        )

    def _select_seeds(
        self,
        stage: ExperimentStage,
        *,
        expanded: bool = False,
    ) -> List[int]:
        return select_seeds(
            config=self.config,
            seed_ledger=self.seed_ledger,
            stage=stage,
            expanded=expanded,
        )

    def resolve_time_limit_sec(
        self,
        *,
        stage: ExperimentStage | str,
        case_path: str,
    ) -> int:
        stage_key = str(getattr(stage, "value", stage) or "").strip().lower()
        config = getattr(getattr(self.config, "runtime", None), "time_limits", None)
        if config is None:
            return max(1, int(self.time_limit_sec))
        return config.resolve(
            stage=stage_key,
            case_path=case_path,
            fallback_time_limit_sec=self.time_limit_sec,
        )

    def time_limit_policy_summary(
        self,
        *,
        stage: ExperimentStage | str,
        cases: Sequence[str],
    ) -> dict[str, Any]:
        stage_key = str(getattr(stage, "value", stage) or "").strip().lower()
        config = getattr(getattr(self.config, "runtime", None), "time_limits", None)
        if config is None:
            limit = max(1, int(self.time_limit_sec))
            return {
                "stage": stage_key,
                "fallback_time_limit_sec": limit,
                "resolved_min_sec": limit,
                "resolved_max_sec": limit,
                "resolved_unique_sec": [limit],
                "rules": [],
            }
        return config.summary(
            stage=stage_key,
            cases=tuple(cases),
            fallback_time_limit_sec=self.time_limit_sec,
        )

    def _resolve_case_path(self, instance_path: str, *, workspace: str) -> str:
        return self._resolve_case_path_status(
            instance_path,
            workspace=workspace,
        ).resolved

    def _resolve_case_path_status(
        self,
        instance_path: str,
        *,
        workspace: str,
    ) -> CasePathResolution:
        resolution = resolve_case_path_details(
            instance_path,
            workspace=workspace,
            safe_data_roots=self.split_manager.safe_data_roots(),
        )
        validate_case_path_resolution(
            resolution,
            strict=self._strict_case_paths,
        )
        if not resolution.safe:
            logger.warning(
                "ExperimentProtocol accepted unsafe case path in non-strict mode: "
                "path=%r status=%s reason=%s",
                resolution.original,
                resolution.status,
                resolution.reason,
            )
        return resolution

    def run_experiment(
        self,
        stage: ExperimentStage,
        candidate_ws: str,
        champion_ws: str,
        hypothesis_action: str,
        expand: bool = False,
        expand_round: int = 1,
        selected_surface: str | None = None,
        *,
        paired_execution: "PairedExecutionSpec | None" = None,
        proposal_subject: Mapping[str, Any] | None = None,
    ) -> ProtocolResult:
        from .stages import run_experiment

        return run_experiment(
            self,
            stage,
            candidate_ws,
            champion_ws,
            hypothesis_action,
            expand=expand,
            expand_round=expand_round,
            selected_surface=selected_surface,
            paired_execution=paired_execution,
            proposal_subject=proposal_subject,
        )


__all__ = ["ExperimentProtocol"]


def _has_metric_specs(metric_specs: Sequence[Any] | None) -> bool:
    return metric_specs is not None and len(metric_specs) > 0


def _hydrate_metric_specs(
    metric_specs: Sequence[Any] | None,
    problem_spec: Any | None,
) -> Sequence[Any] | None:
    if _has_metric_specs(metric_specs):
        return metric_specs
    declared = getattr(problem_spec, "objectives", None)
    if _has_metric_specs(declared):
        return tuple(declared)
    spec_v1 = getattr(problem_spec, "spec_v1", None)
    declared = getattr(spec_v1, "objectives", None)
    if _has_metric_specs(declared):
        return tuple(declared)
    return metric_specs


def _hydrate_objective_policy(problem_spec: Any | None) -> Any | None:
    policy = getattr(problem_spec, "objective_policy", None)
    if policy is not None:
        return policy
    spec_v1 = getattr(problem_spec, "spec_v1", None)
    return getattr(spec_v1, "objective_policy", None)
