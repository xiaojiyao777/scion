from __future__ import annotations

import logging
import os
from collections.abc import Mapping
from typing import Any, Callable, List, Optional, Sequence, TYPE_CHECKING

from scion.config.problem import ProtocolConfig
from scion.core.models import CanaryResult, ExperimentStage, ProtocolResult
from scion.protocol.evaluation import (
    compute_delta,
    lexicographic_compare,
    metric_order_from_objectives,
)
from scion.runtime.runner import Runner
from .selection import SeedLedger, SplitManager, select_cases, select_seeds

if TYPE_CHECKING:
    from scion.problem.spec import ObjectiveMetricSpec, ObjectivePolicySpec

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
        require_metric_specs: bool = False,
        problem_spec: Any | None = None,
    ) -> None:
        self.config = protocol_config
        self.split_manager = split_manager
        self.seed_ledger = seed_ledger
        self.runner = runner
        self.time_limit_sec = time_limit_sec
        self.metrics_dir = metrics_dir
        self._metric_specs = metric_specs
        self._objective_policy = objective_policy
        self._require_metric_specs = require_metric_specs
        self._problem_spec = problem_spec
        self._progress_callback: Optional[Callable[..., None]] = None
        if self._require_metric_specs and self._metric_specs is None:
            raise ValueError("metric_specs are required for production ExperimentProtocol")
        if self._metric_specs is None:
            logger.warning(
                "ExperimentProtocol initialized without metric_specs; using legacy "
                "objective fallback"
            )
        os.makedirs(metrics_dir, exist_ok=True)

    def set_progress_callback(self, callback: Optional[Callable[..., None]]) -> None:
        """Register a lightweight progress hook for long validation/frozen runs."""
        self._progress_callback = callback

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
        if self._metric_specs is not None:
            if getattr(self._objective_policy, "mode", None) == "weighted_sum":
                from scion.problem.objectives import compare_weighted_sum
                result = compare_weighted_sum(
                    self._metric_specs, candidate_objective, champion_objective,
                )
            else:
                from scion.problem.objectives import compare_lexicographic
                result = compare_lexicographic(
                    self._metric_specs, candidate_objective, champion_objective,
                )
            return result.outcome, result
        if self._require_metric_specs:
            raise RuntimeError("metric_specs are required for objective comparison")
        # Legacy compatibility path: build an ObjectiveComparison from generic
        # lexicographic-minimize fallback semantics.
        from scion.problem.objectives import ObjectiveComparison, MetricComparison
        metric_order = metric_order_from_objectives(candidate_objective, champion_objective)
        cmp = lexicographic_compare(
            candidate_objective,
            champion_objective,
            metric_order=metric_order,
        )
        metrics = []
        decisive_seen = False
        for name in metric_order:
            cv = candidate_objective.get(name, 0)
            hv = champion_objective.get(name, 0)
            sd = float(hv) - float(cv)
            decisive = (not decisive_seen) and cv != hv
            decisive_seen = decisive_seen or decisive
            metrics.append(MetricComparison(
                name=name, candidate_value=cv, champion_value=hv,
                signed_delta=sd, relation="candidate" if sd > 0 else ("champion" if sd < 0 else "tie"),
                decisive=decisive,
            ))
        decisive_metric = next((m.name for m in metrics if m.decisive), None)
        result = ObjectiveComparison(
            outcome=cmp,
            decisive_metric=decisive_metric,
            scalar_delta=compute_delta(
                candidate_objective,
                champion_objective,
                metric_order=metric_order,
            ),
            metrics=tuple(metrics),
        )
        return cmp, result

    def _compute_delta(
        self,
        candidate_objective: dict,
        champion_objective: dict,
    ) -> float:
        if self._metric_specs is not None:
            if getattr(self._objective_policy, "mode", None) == "weighted_sum":
                from scion.problem.objectives import compare_weighted_sum
                result = compare_weighted_sum(
                    self._metric_specs, candidate_objective, champion_objective,
                )
            else:
                from scion.problem.objectives import compare_lexicographic
                result = compare_lexicographic(
                    self._metric_specs, candidate_objective, champion_objective,
                )
            return result.scalar_delta
        if self._require_metric_specs:
            raise RuntimeError("metric_specs are required for objective delta")
        return compute_delta(candidate_objective, champion_objective)

    @property
    def problem_spec(self) -> Any | None:
        return self._problem_spec

    def run_canary(
        self,
        candidate_ws: str,
        champion_ws: str,
        *,
        selected_surface: str | None = None,
    ) -> CanaryResult:
        from .canary import run_canary

        return run_canary(
            self,
            candidate_ws,
            champion_ws,
            selected_surface=selected_surface,
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

    def _select_seeds(self, stage: ExperimentStage) -> List[int]:
        return select_seeds(seed_ledger=self.seed_ledger, stage=stage)

    def run_experiment(
        self,
        stage: ExperimentStage,
        candidate_ws: str,
        champion_ws: str,
        hypothesis_action: str,
        expand: bool = False,
        expand_round: int = 1,
        selected_surface: str | None = None,
        expected_telemetry: Mapping[str, Any] | None = None,
        mechanism_changes: Sequence[Any] | None = None,
        protected_objectives: Sequence[str] = (),
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
            expected_telemetry=expected_telemetry,
            mechanism_changes=mechanism_changes,
            protected_objectives=protected_objectives,
        )


__all__ = ["ExperimentProtocol"]
