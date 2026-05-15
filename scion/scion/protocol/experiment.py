from __future__ import annotations
import json
import logging
import os
import statistics
import uuid as _uuid_mod
from collections import defaultdict
from dataclasses import dataclass, replace
from typing import Any, Callable, Dict, List, Optional, Sequence, TYPE_CHECKING

logger = logging.getLogger(__name__)

from scion.core.models import (
    ExperimentStage, CanaryResult, ProtocolResult, EvalStats,
    PairwiseCaseFeedback, CaseAggregateFeedback,
    ScreeningPatternSummary, RunResult,
)
from scion.config.problem import ProtocolConfig, SplitManifest, SeedLedgerConfig
from scion.runtime.runner import Runner
from scion.protocol.evaluation import (
    lexicographic_compare, compute_delta, metric_order_from_objectives,
)
from scion.protocol.stats import compute_eval_stats
from scion.protocol.gates import (
    GateResult, screening_gate, validation_gate, frozen_gate,
)
from scion.runtime.audit import (
    declared_surface_required_runtime_fields,
    format_runtime_audit_failure,
    runtime_audit_failure_from_result,
)

if TYPE_CHECKING:
    from scion.problem.spec import ObjectiveMetricSpec, ObjectivePolicySpec


# ---------------------------------------------------------------------------
# Case-level result (T2)
# ---------------------------------------------------------------------------

@dataclass
class CaseLevelResult:
    """Aggregated result for a single case across all seeds."""
    case_id: str
    comparison: str   # majority vote: "win" / "loss" / "tie"
    delta: float      # median delta across seeds
    metric_deltas: Dict[str, float] | None = None


# ---------------------------------------------------------------------------
# SplitManager and SeedLedger wrappers
# ---------------------------------------------------------------------------

class SplitManager:
    def __init__(self, manifest: SplitManifest) -> None:
        self._manifest = manifest

    def get_cases(self, stage: ExperimentStage) -> List[str]:
        if stage == ExperimentStage.SCREENING:
            return list(self._manifest.screening)
        elif stage == ExperimentStage.VALIDATION:
            return list(self._manifest.validation)
        elif stage == ExperimentStage.FROZEN:
            return list(self._manifest.frozen)
        raise ValueError(f"Unknown stage: {stage}")

    def get_canary_cases(self) -> List[str]:
        """Return the dedicated canary case list."""
        return list(self._manifest.canary)

    def validate_disjoint(self) -> bool:
        self._manifest.validate_disjoint()
        return True


class SeedLedger:
    def __init__(self, ledger: SeedLedgerConfig) -> None:
        self._ledger = ledger

    def get_seeds(self, stage: ExperimentStage) -> List[int]:
        if stage == ExperimentStage.SCREENING:
            return list(self._ledger.screening)
        elif stage == ExperimentStage.VALIDATION:
            return list(self._ledger.validation)
        elif stage == ExperimentStage.FROZEN:
            return list(self._ledger.frozen)
        raise ValueError(f"Unknown stage: {stage}")

    def get_canary_seeds(self) -> List[int]:
        """Return the dedicated canary seed list."""
        return list(self._ledger.canary)


def _select_evenly_spaced_cases(all_cases: Sequence[str], n: int) -> List[str]:
    """Select a deterministic spread across the manifest instead of a prefix.

    Split manifests are often ordered by generation family, size, or creation
    time. Prefix selection can accidentally make screening blind to later
    strata. Even spacing keeps runs reproducible while covering the full split.
    """
    cases = list(all_cases)
    total = len(cases)
    if n <= 0:
        return []
    if n >= total:
        return cases
    if n == 1:
        return [cases[total // 2]]

    indices = [round(i * (total - 1) / (n - 1)) for i in range(n)]
    # ``round`` should be unique for n <= total, but keep a deterministic
    # fill path for small edge cases and future Python behavior changes.
    selected = []
    seen: set[int] = set()
    for idx in indices:
        if idx not in seen:
            selected.append(idx)
            seen.add(idx)
    for idx in range(total):
        if len(selected) >= n:
            break
        if idx not in seen:
            selected.append(idx)
            seen.add(idx)

    return [cases[i] for i in sorted(selected[:n])]


# ---------------------------------------------------------------------------
# ExperimentProtocol
# ---------------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Comparison dispatch: generic (v0.3+) or legacy
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # T3: Canary — uses independent canary split + canary seeds
    # ------------------------------------------------------------------

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
        """
        Canary regression check using the dedicated canary split and seeds.
        Veto-only — blocks if candidate produces infeasible solutions or crashes.

        Raises ValueError if canary split/seeds are not configured.
        """
        canary_cases = self.split_manager.get_canary_cases()
        canary_seeds = self.seed_ledger.get_canary_seeds()

        if not canary_cases:
            raise ValueError(
                "Canary split not configured: split_manifest.canary is empty. "
                "Add canary cases to split_manifest.yaml."
            )
        if not canary_seeds:
            raise ValueError(
                "Canary seeds not configured: seed_ledger.canary is empty. "
                "Add canary seeds to seed_ledger.yaml."
            )

        for case in canary_cases:
            for seed in canary_seeds:
                cand_result = self.runner.run_solver(
                    workdir=candidate_ws,
                    instance_path=case,
                    seed=seed,
                    time_limit_sec=self.time_limit_sec,
                    registry_path=os.path.join(candidate_ws, "registry.yaml"),
                    selected_surface=selected_surface,
                )
                if not cand_result.success:
                    return CanaryResult(
                        passed=False,
                        reason=f"Candidate solver failed on {case}: {cand_result.error_category}",
                    )
                cand_audit_failure = runtime_audit_failure_from_result(
                    cand_result,
                    problem_spec=self._problem_spec,
                    selected_surface=selected_surface,
                )
                if cand_audit_failure is not None:
                    return CanaryResult(
                        passed=False,
                        reason=(
                            f"Candidate runtime audit failed on {case}: "
                            f"{format_runtime_audit_failure(cand_audit_failure)}"
                        ),
                    )

                champ_result = self.runner.run_solver(
                    workdir=champion_ws,
                    instance_path=case,
                    seed=seed,
                    time_limit_sec=self.time_limit_sec,
                    registry_path=os.path.join(champion_ws, "registry.yaml"),
                    selected_surface=selected_surface,
                )
                if not champ_result.success:
                    # Infra issue on champion side — skip veto
                    continue
                if runtime_audit_failure_from_result(champ_result) is not None:
                    # Existing champion-side runtime audit issues are not a
                    # candidate veto in the canary gate; validation/frozen
                    # evidence treats them as incomplete champion evidence.
                    continue

                if (
                    cand_result.output is not None
                    and champ_result.output is not None
                    and champ_result.output.feasible
                    and not cand_result.output.feasible
                ):
                    return CanaryResult(
                        passed=False,
                        reason=f"Candidate infeasible on {case} (champion was feasible)",
                    )

        return CanaryResult(passed=True, reason=None)

    # ------------------------------------------------------------------
    # T4 + T5: Case selection helpers
    # ------------------------------------------------------------------

    def _select_cases(
        self,
        stage: ExperimentStage,
        hypothesis_action: str,
        expand_round: int,
    ) -> List[str]:
        """Select cases based on stage, action type, and whether we're in expand mode.

        T5: screening selects n_cases_modify or n_cases_create based on action.
        T4: expand increases the case count, seed set stays fixed.
        """
        all_cases = self.split_manager.get_cases(stage)

        if stage == ExperimentStage.SCREENING:
            if expand_round > 0:
                # T4: expand adds cases, not seeds
                n = (
                    self.config.screening.expand_to_create
                    if hypothesis_action == "create_new"
                    else self.config.screening.expand_to_modify
                )
            else:
                n = (
                    self.config.screening.n_cases_create
                    if hypothesis_action == "create_new"
                    else self.config.screening.n_cases_modify
                )
        elif stage == ExperimentStage.VALIDATION:
            n = (
                self.config.validation.expand_to
                if expand_round > 0
                else self.config.validation.n_cases
            )
        elif stage == ExperimentStage.FROZEN:
            n = self.config.frozen.n_cases
        else:
            return all_cases

        return _select_evenly_spaced_cases(all_cases, n)

    def _select_seeds(self, stage: ExperimentStage) -> List[int]:
        """Return the fixed seed list for the stage (T4: seeds never expanded)."""
        return self.seed_ledger.get_seeds(stage)

    # ------------------------------------------------------------------
    # T2: run_experiment — case-level aggregation
    # ------------------------------------------------------------------

    def run_experiment(
        self,
        stage: ExperimentStage,
        candidate_ws: str,
        champion_ws: str,
        hypothesis_action: str,
        expand: bool = False,
        expand_round: int = 1,
        selected_surface: str | None = None,
    ) -> ProtocolResult:
        """Execute paired A/B evaluation for the given stage.

        T2: Statistical unit is case (not pair). Each case is evaluated across
        all seeds, then majority-voted to a case-level win/loss/tie and median delta.
        T4: expand increases case count; seed set is unchanged.
        T5: case count depends on stage + hypothesis_action + expand flag.
        """
        cases = self._select_cases(
            stage, hypothesis_action, expand_round if expand else 0
        )
        seeds = self._select_seeds(stage)
        total_pairs = len(cases) * len(seeds)
        attempted_pairs = 0
        valid_pairs = 0

        # Persist a partial metrics file from the start of the stage, then update
        # it after every attempted pair. Long validation/frozen stages remain
        # inspectable even if the campaign is interrupted.
        raw_ref = os.path.join(self.metrics_dir, f"{_uuid_mod.uuid4()}.json")

        # Collect pair feedback grouped by case
        pairs_by_case: Dict[str, List[PairwiseCaseFeedback]] = defaultdict(list)
        raw_pairs: List[dict] = []
        raw_failures: List[dict] = []
        failed_pairs = 0
        candidate_failed_pairs = 0
        champion_failed_pairs = 0
        runtime_ratios: list[float] = []
        runtime_deltas_ms: list[float] = []
        candidate_runtime_categories: dict[str, int] = {}
        candidate_first_runtime_failure: dict[str, Any] | None = None
        candidate_runtime_counters: dict[str, int] = {
            "operator_attempts": 0,
            "operator_accepted": 0,
            "operator_errors": 0,
            "operator_invalid_outputs": 0,
            "policy_errors": 0,
            "construction_errors": 0,
            "portfolio_errors": 0,
        }
        candidate_runtime_stop_reasons: dict[str, int] = {}
        surface_required_runtime_fields = declared_surface_required_runtime_fields(
            self._problem_spec,
            selected_surface,
        )
        candidate_surface_runtime_summary = _surface_runtime_summary_template(
            selected_surface=selected_surface,
            required_fields=surface_required_runtime_fields,
        )

        def _write_metrics_snapshot(*, complete: bool) -> None:
            with open(raw_ref, "w") as f:
                json.dump(
                    {
                        "stage": stage.value,
                        "selected_surface": selected_surface,
                        "case_ids": cases,
                        "seed_set": seeds,
                        "total_pairs": total_pairs,
                        "attempted_pairs": attempted_pairs,
                        "valid_pairs": valid_pairs,
                        "failed_pairs": failed_pairs,
                        "candidate_failed_pairs": candidate_failed_pairs,
                        "champion_failed_pairs": champion_failed_pairs,
                        "runtime_stats": _build_runtime_stats(
                            runtime_ratios,
                            runtime_deltas_ms,
                        ),
                        "candidate_surface_runtime_summary": (
                            _finalize_surface_runtime_summary(
                                candidate_surface_runtime_summary
                            )
                        ),
                        "complete": complete,
                        "pairs": raw_pairs,
                        "failures": raw_failures,
                    },
                    f,
                )

        _write_metrics_snapshot(complete=False)
        self._emit_progress(
            stage=stage.value,
            case=None,
            seed=None,
            attempted_pairs=attempted_pairs,
            completed_pairs=valid_pairs,
            total_pairs=total_pairs,
            raw_metrics_ref=raw_ref,
        )

        for case in cases:
            case_features = _extract_case_features(case)
            for seed in seeds:
                attempted_pairs += 1
                self._emit_progress(
                    stage=stage.value,
                    case=case,
                    seed=seed,
                    attempted_pairs=attempted_pairs,
                    completed_pairs=valid_pairs,
                    total_pairs=total_pairs,
                    raw_metrics_ref=raw_ref,
                )
                champ_r = self.runner.run_solver(
                    workdir=champion_ws,
                    instance_path=case,
                    seed=seed,
                    time_limit_sec=self.time_limit_sec,
                    registry_path=os.path.join(champion_ws, "registry.yaml"),
                    selected_surface=selected_surface,
                )
                cand_r = self.runner.run_solver(
                    workdir=candidate_ws,
                    instance_path=case,
                    seed=seed,
                    time_limit_sec=self.time_limit_sec,
                    registry_path=os.path.join(candidate_ws, "registry.yaml"),
                    selected_surface=selected_surface,
                )
                _record_surface_runtime_sample(
                    cand_r,
                    candidate_surface_runtime_summary,
                )
                runtime_fields = _runtime_fields(
                    cand_r,
                    champ_r,
                    candidate_required_runtime_fields=surface_required_runtime_fields,
                )
                _record_runtime_sample(
                    runtime_fields,
                    runtime_ratios,
                    runtime_deltas_ms,
                )
                runtime_observation = _candidate_runtime_observation(cand_r)
                _merge_runtime_observation(
                    runtime_observation,
                    categories=candidate_runtime_categories,
                    counters=candidate_runtime_counters,
                    stop_reasons=candidate_runtime_stop_reasons,
                )
                if (
                    candidate_first_runtime_failure is None
                    and runtime_observation.get("first_failure") is not None
                ):
                    candidate_first_runtime_failure = runtime_observation["first_failure"]

                if not cand_r.success:
                    category = _candidate_process_failure_category(cand_r)
                    _increment_category(candidate_runtime_categories, category)
                    if candidate_first_runtime_failure is None:
                        candidate_first_runtime_failure = _bounded_runtime_failure(
                            category=category,
                            code=str(cand_r.error_category or cand_r.exit_code or "process_failure"),
                            surface=None,
                            component="solver_process",
                            detail_summary=cand_r.stderr or cand_r.stdout or "candidate solver process failed",
                        )
                    failed_pairs += 1
                    candidate_failed_pairs += 1
                    failure_record = {
                        "case": case,
                        "seed": seed,
                        "side": "candidate",
                        "comparison": "loss",
                        "delta": -1.0,
                        "error_category": cand_r.error_category or "unknown",
                        "exit_code": cand_r.exit_code,
                        "elapsed_ms": cand_r.elapsed_ms,
                        **runtime_fields,
                        "stderr_tail": (cand_r.stderr or "")[-1000:],
                    }
                    raw_failures.append(failure_record)
                    raw_pairs.append({
                        "case": case,
                        "seed": seed,
                        "comparison": "loss",
                        "delta": -1.0,
                        "decisive_metric": "runtime_failure",
                        "metric_deltas": {},
                        **runtime_fields,
                        "failure": failure_record,
                    })
                    pairs_by_case[os.path.basename(case)].append(
                        PairwiseCaseFeedback(
                            case_id=os.path.basename(case),
                            seed=seed,
                            comparison="loss",
                            delta=-1.0,
                            objective_comparison=None,
                            case_features=case_features,
                        )
                    )
                    logger.info(
                        "Pair %s seed=%d: candidate solver failed category=%s elapsed_ms=%d → loss",
                        os.path.basename(case), seed,
                        cand_r.error_category or "unknown",
                        cand_r.elapsed_ms,
                    )
                    _write_metrics_snapshot(complete=False)
                    self._emit_progress(
                        stage=stage.value,
                        case=case,
                        seed=seed,
                        attempted_pairs=attempted_pairs,
                        completed_pairs=valid_pairs,
                        total_pairs=total_pairs,
                        raw_metrics_ref=raw_ref,
                    )
                    continue

                if not champ_r.success:
                    failed_pairs += 1
                    champion_failed_pairs += 1
                    failure_record = {
                        "case": case,
                        "seed": seed,
                        "side": "champion",
                        "comparison": "invalid",
                        "error_category": champ_r.error_category or "unknown",
                        "exit_code": champ_r.exit_code,
                        "elapsed_ms": champ_r.elapsed_ms,
                        **runtime_fields,
                        "stderr_tail": (champ_r.stderr or "")[-1000:],
                    }
                    raw_failures.append(failure_record)
                    raw_pairs.append({
                        "case": case,
                        "seed": seed,
                        "comparison": "invalid",
                        "delta": None,
                        "decisive_metric": "champion_runtime_failure",
                        "metric_deltas": {},
                        **runtime_fields,
                        "failure": failure_record,
                    })
                    logger.info(
                        "Pair %s seed=%d: champion solver failed category=%s elapsed_ms=%d → invalid",
                        os.path.basename(case), seed,
                        champ_r.error_category or "unknown",
                        champ_r.elapsed_ms,
                    )
                    _write_metrics_snapshot(complete=False)
                    continue

                if cand_r.output is None or champ_r.output is None:
                    failed_pairs += 1
                    if cand_r.output is None:
                        _increment_category(candidate_runtime_categories, "invalid_output")
                        if candidate_first_runtime_failure is None:
                            candidate_first_runtime_failure = _bounded_runtime_failure(
                                category="invalid_output",
                                code="missing_output",
                                surface=None,
                                component="solver_output",
                                detail_summary="candidate solver succeeded without parsed output",
                            )
                    failure_record = {
                        "case": case,
                        "seed": seed,
                        "side": "unknown",
                        "comparison": "invalid",
                        "error_category": "missing_output",
                        **runtime_fields,
                    }
                    raw_failures.append(failure_record)
                    raw_pairs.append({
                        "case": case,
                        "seed": seed,
                        "comparison": "invalid",
                        "delta": None,
                        "decisive_metric": "missing_output",
                        "metric_deltas": {},
                        **runtime_fields,
                        "failure": failure_record,
                    })
                    _write_metrics_snapshot(complete=False)
                    continue

                cand_audit_failure = runtime_audit_failure_from_result(
                    cand_r,
                    problem_spec=self._problem_spec,
                    selected_surface=selected_surface,
                )
                if cand_audit_failure is not None:
                    audit_category = _candidate_audit_failure_category(cand_audit_failure)
                    if audit_category not in (runtime_observation.get("categories") or {}):
                        _increment_category(candidate_runtime_categories, audit_category)
                    if candidate_first_runtime_failure is None:
                        candidate_first_runtime_failure = _bounded_runtime_failure_from_audit(
                            cand_audit_failure,
                            category=audit_category,
                        )
                    failed_pairs += 1
                    candidate_failed_pairs += 1
                    failure_record = {
                        "case": case,
                        "seed": seed,
                        "side": "candidate",
                        "comparison": "loss",
                        "delta": -1.0,
                        "error_category": cand_audit_failure["error_category"],
                        "exit_code": cand_r.exit_code,
                        "elapsed_ms": cand_r.elapsed_ms,
                        **runtime_fields,
                        "runtime_audit": cand_audit_failure,
                    }
                    raw_failures.append(failure_record)
                    raw_pairs.append({
                        "case": case,
                        "seed": seed,
                        "comparison": "loss",
                        "delta": -1.0,
                        "decisive_metric": cand_audit_failure["error_category"],
                        "metric_deltas": {},
                        **runtime_fields,
                        "failure": failure_record,
                    })
                    pairs_by_case[os.path.basename(case)].append(
                        PairwiseCaseFeedback(
                            case_id=os.path.basename(case),
                            seed=seed,
                            comparison="loss",
                            delta=-1.0,
                            objective_comparison=None,
                            case_features=case_features,
                        )
                    )
                    logger.info(
                        "Pair %s seed=%d: candidate runtime audit failed: %s",
                        os.path.basename(case), seed,
                        format_runtime_audit_failure(cand_audit_failure),
                    )
                    _write_metrics_snapshot(complete=False)
                    self._emit_progress(
                        stage=stage.value,
                        case=case,
                        seed=seed,
                        attempted_pairs=attempted_pairs,
                        completed_pairs=valid_pairs,
                        total_pairs=total_pairs,
                        raw_metrics_ref=raw_ref,
                    )
                    continue

                champ_audit_failure = runtime_audit_failure_from_result(champ_r)
                if champ_audit_failure is not None:
                    failed_pairs += 1
                    champion_failed_pairs += 1
                    failure_record = {
                        "case": case,
                        "seed": seed,
                        "side": "champion",
                        "comparison": "invalid",
                        "delta": None,
                        "error_category": champ_audit_failure["error_category"],
                        "exit_code": champ_r.exit_code,
                        "elapsed_ms": champ_r.elapsed_ms,
                        **runtime_fields,
                        "runtime_audit": champ_audit_failure,
                    }
                    raw_failures.append(failure_record)
                    raw_pairs.append({
                        "case": case,
                        "seed": seed,
                        "comparison": "invalid",
                        "delta": None,
                        "decisive_metric": f"champion_{champ_audit_failure['error_category']}",
                        "metric_deltas": {},
                        **runtime_fields,
                        "failure": failure_record,
                    })
                    logger.info(
                        "Pair %s seed=%d: champion runtime audit failed: %s",
                        os.path.basename(case), seed,
                        format_runtime_audit_failure(champ_audit_failure),
                    )
                    _write_metrics_snapshot(complete=False)
                    continue

                cmp, breakdown = self._compare_objectives(
                    cand_r.output.objective,
                    champ_r.output.objective,
                )
                delta = self._compute_delta(cand_r.output.objective, champ_r.output.objective)

                raw_pairs.append(
                    {
                        "case": case,
                        "seed": seed,
                        "comparison": cmp,
                        "delta": delta,
                        "decisive_metric": breakdown.decisive_metric,
                        "metric_deltas": {
                            m.name: m.signed_delta for m in breakdown.metrics
                        } if breakdown.metrics else {},
                        **runtime_fields,
                    }
                )
                valid_pairs += 1
                pair_fb = PairwiseCaseFeedback(
                    case_id=os.path.basename(case),
                    seed=seed,
                    comparison=cmp,
                    delta=delta,
                    objective_comparison=breakdown,
                    case_features=case_features,
                )
                pairs_by_case[os.path.basename(case)].append(pair_fb)
                # Log per-pair result with generic metric values
                _mc = {m.name: m for m in breakdown.metrics} if breakdown.metrics else {}
                _cand_vals = " ".join(f"{m.name}={m.candidate_value}" for m in breakdown.metrics) if breakdown.metrics else ""
                _chmp_vals = " ".join(f"{m.name}={m.champion_value}" for m in breakdown.metrics) if breakdown.metrics else ""
                logger.info(
                    "Pair %s seed=%d: cmp=%s delta=%.4f decisive=%s cand(%s) champ(%s)",
                    os.path.basename(case), seed, cmp, delta,
                    breakdown.decisive_metric,
                    _cand_vals, _chmp_vals,
                )
                _write_metrics_snapshot(complete=False)
                self._emit_progress(
                    stage=stage.value,
                    case=case,
                    seed=seed,
                    attempted_pairs=attempted_pairs,
                    completed_pairs=valid_pairs,
                    total_pairs=total_pairs,
                    raw_metrics_ref=raw_ref,
                )

        # T2: Aggregate pairs → case-level results
        all_pair_feedback = [fb for fbs in pairs_by_case.values() for fb in fbs]
        case_level_results = _aggregate_pairs_to_case_level(all_pair_feedback)

        case_comparisons = [r.comparison for r in case_level_results]
        case_deltas = [r.delta for r in case_level_results]

        if not case_comparisons:
            stats = EvalStats(
                n_cases=0, wins=0, losses=0, ties=0,
                win_rate=0.0, median_delta=0.0, ci_low=-1.0, ci_high=-1.0,
            )
            gate = GateResult(outcome="fail", reason_codes=("NO_VALID_RUNS",))
        else:
            # T2: stats computed on case-level comparisons/deltas.
            # F3: when metric_specs are present, gate CI is computed
            # hierarchically by objective priority instead of one raw scalar.
            if (
                self._metric_specs is not None
                and getattr(self._objective_policy, "mode", None) == "weighted_sum"
            ):
                metric_order = ["weighted_sum"]
            else:
                metric_order = (
                    [m.name for m in sorted(self._metric_specs, key=lambda s: s.priority)]
                    if self._metric_specs is not None else None
                )
            stats = compute_eval_stats(
                case_comparisons,
                case_deltas,
                metric_deltas=[r.metric_deltas or {} for r in case_level_results],
                metric_order=metric_order,
            )

        runtime_stats = _build_runtime_stats(runtime_ratios, runtime_deltas_ms)
        stats = replace(
            stats,
            runtime_ratio_median=runtime_stats["runtime_ratio_median"],
            runtime_delta_median_ms=runtime_stats["runtime_delta_median_ms"],
            runtime_regression_rate=runtime_stats["runtime_regression_rate"],
            runtime_pairs=runtime_stats["runtime_pairs"],
            total_pairs=total_pairs,
            attempted_pairs=attempted_pairs,
            valid_pairs=valid_pairs,
            failed_pairs=failed_pairs,
            candidate_failed_pairs=candidate_failed_pairs,
            champion_failed_pairs=champion_failed_pairs,
        )
        if case_comparisons:
            if stage == ExperimentStage.SCREENING:
                gate = screening_gate(stats, self.config)
            elif stage == ExperimentStage.VALIDATION:
                gate = validation_gate(stats, self.config)
            else:
                gate = frozen_gate(stats, self.config)

            if failed_pairs > 0 and stage in (ExperimentStage.VALIDATION, ExperimentStage.FROZEN):
                reason_codes = ["INCOMPLETE_EVIDENCE"]
                if candidate_failed_pairs:
                    reason_codes.append("CANDIDATE_RUNTIME_FAILURE")
                if champion_failed_pairs:
                    reason_codes.append("CHAMPION_RUNTIME_FAILURE")
                gate = GateResult(outcome="fail", reason_codes=tuple(reason_codes))

        # Persist final raw metrics snapshot.
        _write_metrics_snapshot(complete=True)
        runtime_summary = _format_runtime_summary(stats)
        failure_category_summary = _format_runtime_failure_categories(
            candidate_runtime_categories
        )
        runtime_failure_summary = (
            f" candidate_runtime_categories={failure_category_summary}"
            if failure_category_summary
            else ""
        )
        runtime_attempt_summary = (
            " candidate_operator_attempts="
            f"{candidate_runtime_counters['operator_attempts']}"
            " candidate_operator_accepted="
            f"{candidate_runtime_counters['operator_accepted']}"
            " candidate_operator_errors="
            f"{candidate_runtime_counters['operator_errors']}"
            " candidate_invalid_outputs="
            f"{candidate_runtime_counters['operator_invalid_outputs']}"
        )

        # Exposure control
        if stage == ExperimentStage.SCREENING:
            exposed = (
                f"stage={stage.value} win_rate={stats.win_rate:.2f} "
                f"median_delta={stats.median_delta:.4f} outcome={gate.outcome} "
                f"failed_pairs={failed_pairs} candidate_failures={candidate_failed_pairs} "
                f"{runtime_summary}{runtime_failure_summary}{runtime_attempt_summary}"
            )
        else:
            # Validation / Frozen: aggregate summary only, no per-case data
            exposed = (
                f"stage={stage.value} outcome={gate.outcome} "
                f"stat={stats.statistical_status or 'legacy'} "
                f"metric={stats.statistical_metric or 'scalar'} "
                f"valid_pairs={valid_pairs}/{total_pairs} failed_pairs={failed_pairs} "
                f"candidate_failures={candidate_failed_pairs} champion_failures={champion_failed_pairs} "
                f"{runtime_summary}{runtime_failure_summary}{runtime_attempt_summary}"
            )

        # Build case-level feedback for screening only
        case_fb: tuple = ()
        pattern: "ScreeningPatternSummary | None" = None
        if stage == ExperimentStage.SCREENING and all_pair_feedback:
            case_fb = tuple(_aggregate_case_feedback(all_pair_feedback))
            pattern = _build_pattern_summary(case_fb)

        return ProtocolResult(
            stage=stage,
            stats=stats,
            gate_outcome=gate.outcome,
            reason_codes=gate.reason_codes,
            exposed_summary=exposed,
            raw_metrics_ref=raw_ref,
            case_ids=tuple(cases),
            seed_set=tuple(seeds),
            pair_feedback=tuple(all_pair_feedback) if stage == ExperimentStage.SCREENING else (),
            case_feedback=case_fb,
            pattern_summary=pattern,
            selected_surface=selected_surface,
            candidate_surface_runtime_summary=_finalize_surface_runtime_summary(
                candidate_surface_runtime_summary
            ),
            candidate_runtime_failure_categories=dict(candidate_runtime_categories),
            candidate_first_runtime_failure=candidate_first_runtime_failure,
            candidate_operator_attempts=candidate_runtime_counters["operator_attempts"],
            candidate_operator_accepted=candidate_runtime_counters["operator_accepted"],
            candidate_operator_errors=candidate_runtime_counters["operator_errors"],
            candidate_operator_invalid_outputs=(
                candidate_runtime_counters["operator_invalid_outputs"]
            ),
            candidate_policy_errors=candidate_runtime_counters["policy_errors"],
            candidate_construction_errors=(
                candidate_runtime_counters["construction_errors"]
            ),
            candidate_portfolio_errors=candidate_runtime_counters["portfolio_errors"],
            candidate_runtime_stop_reasons=dict(candidate_runtime_stop_reasons),
        )


# ---------------------------------------------------------------------------
# T2: Case-level aggregation helper
# ---------------------------------------------------------------------------

def _candidate_runtime_observation(result: RunResult) -> dict[str, Any]:
    runtime = getattr(getattr(result, "output", None), "runtime", None)
    if not isinstance(runtime, dict):
        return {"categories": {}, "counters": {}, "stop_reasons": {}}

    counters = {
        "operator_attempts": _as_int(runtime.get("operator_attempts")),
        "operator_accepted": _as_int(runtime.get("operator_accepted")),
        "operator_errors": _as_int(runtime.get("operator_errors")),
        "operator_invalid_outputs": _as_int(runtime.get("operator_invalid_outputs")),
        "policy_errors": _as_int(runtime.get("policy_errors")),
        "construction_errors": _as_int(runtime.get("construction_errors")),
        "portfolio_errors": _as_int(runtime.get("portfolio_errors")),
    }
    categories: dict[str, int] = {}
    first_failure: dict[str, Any] | None = None

    for counter_name, category in (
        ("construction_errors", "construction_error"),
        ("portfolio_errors", "portfolio_error"),
        ("policy_errors", "policy_error"),
        ("operator_invalid_outputs", "invalid_output"),
        ("operator_errors", "operator_error"),
    ):
        count = counters[counter_name]
        if count <= 0:
            continue
        categories[category] = categories.get(category, 0) + count
        if first_failure is None:
            first_failure = _bounded_runtime_failure(
                category=category,
                code=counter_name,
                surface=None,
                component=counter_name.removesuffix("_errors"),
                detail_summary=f"solver runtime reported {counter_name}={count}",
            )

    if counters["operator_attempts"] > 0 and counters["operator_accepted"] == 0:
        categories["no_accepted_moves"] = categories.get("no_accepted_moves", 0) + 1

    stop_reasons: dict[str, int] = {}
    stop_reason = str(runtime.get("operator_stop_reason") or "").strip()
    if stop_reason:
        stop_reasons[stop_reason] = 1

    return {
        "categories": categories,
        "counters": counters,
        "stop_reasons": stop_reasons,
        "first_failure": first_failure,
    }


def _merge_runtime_observation(
    observation: dict[str, Any],
    *,
    categories: dict[str, int],
    counters: dict[str, int],
    stop_reasons: dict[str, int],
) -> None:
    for category, count in (observation.get("categories") or {}).items():
        _increment_category(categories, str(category), _as_int(count))
    for name, count in (observation.get("counters") or {}).items():
        if name in counters:
            counters[name] += _as_int(count)
    for reason, count in (observation.get("stop_reasons") or {}).items():
        reason_text = str(reason).strip()
        if reason_text:
            stop_reasons[reason_text] = stop_reasons.get(reason_text, 0) + _as_int(count)


def _candidate_process_failure_category(result: RunResult) -> str:
    category = str(result.error_category or "").strip().lower()
    if category in {"timeout", "oom", "crash"}:
        return category
    return "process_error"


def _candidate_audit_failure_category(issue: dict[str, Any]) -> str:
    raw = str(issue.get("error_category") or "").strip().lower()
    if raw == "operator_runtime_error":
        if _as_int(issue.get("operator_invalid_outputs")) > 0:
            return "invalid_output"
        return "operator_error"
    if raw == "policy_runtime_error":
        return "policy_error"
    if raw == "construction_runtime_error":
        return "construction_error"
    if raw == "portfolio_runtime_error":
        return "portfolio_error"
    if raw == "surface_runtime_contract_error":
        return "surface_contract_error"
    if raw == "baseline_runtime_error":
        return "baseline_error"
    return raw or "runtime_error"


def _bounded_runtime_failure_from_audit(
    issue: dict[str, Any],
    *,
    category: str,
) -> dict[str, Any]:
    component = "runtime_audit"
    for candidate in ("component", "operator", "policy_path", "construction_policy_path", "portfolio_policy_path"):
        value = issue.get(candidate)
        if value:
            component = str(value)
            break
    return _bounded_runtime_failure(
        category=category,
        code=str(issue.get("error_category") or category),
        surface=issue.get("selected_surface"),
        component=component,
        detail_summary=str(issue.get("detail") or "solver runtime audit failed"),
    )


def _bounded_runtime_failure(
    *,
    category: str,
    code: str,
    surface: Any,
    component: str,
    detail_summary: str,
) -> dict[str, Any]:
    return {
        "category": _bounded_text(category, 80),
        "code": _bounded_text(code, 120),
        "surface": _bounded_text(surface, 120),
        "component": _bounded_text(component, 160),
        "detail_summary": _bounded_text(detail_summary, 240),
    }


def _bounded_text(value: Any, limit: int) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)] + "..."


def _as_int(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return 0


def _increment_category(
    categories: dict[str, int],
    category: str,
    count: int = 1,
) -> None:
    category = str(category or "runtime_error").strip() or "runtime_error"
    categories[category] = categories.get(category, 0) + max(0, int(count))


def _format_runtime_failure_categories(categories: dict[str, int]) -> str:
    parts = [
        f"{category}:{count}"
        for category, count in sorted(categories.items())
        if count > 0
    ]
    return ";".join(parts[:8])


def _runtime_fields(
    cand_r: RunResult | None,
    champ_r: RunResult | None,
    *,
    candidate_required_runtime_fields: Sequence[str] = (),
) -> dict:
    candidate_elapsed = getattr(cand_r, "elapsed_ms", None)
    champion_elapsed = getattr(champ_r, "elapsed_ms", None)
    fields = {
        "candidate_elapsed_ms": candidate_elapsed,
        "champion_elapsed_ms": champion_elapsed,
        "runtime_ratio": None,
        "runtime_delta_ms": None,
        "candidate_runtime": _runtime_audit_summary(
            cand_r,
            required_runtime_fields=candidate_required_runtime_fields,
        ),
        "champion_runtime": _runtime_audit_summary(champ_r),
    }
    if candidate_elapsed is None or champion_elapsed is None:
        return fields
    fields["runtime_delta_ms"] = int(candidate_elapsed) - int(champion_elapsed)
    if champion_elapsed > 0:
        fields["runtime_ratio"] = float(candidate_elapsed) / float(champion_elapsed)
    return fields


def _runtime_audit_summary(
    result: RunResult | None,
    *,
    required_runtime_fields: Sequence[str] = (),
) -> dict:
    runtime = getattr(getattr(result, "output", None), "runtime", None)
    if not isinstance(runtime, dict):
        return {}
    summary = {
        key: value
        for key, value in runtime.items()
        if key.startswith(("baseline_", "operator_", "policy_", "construction_", "portfolio_"))
        and key not in ("operator_events", "policy_events")
        and _is_json_scalar(value)
    }
    for field in required_runtime_fields:
        if field in runtime:
            summary[field] = _bounded_json_value(runtime[field])
    events = runtime.get("operator_events")
    if isinstance(events, list):
        summary["operator_events"] = events[:5]
    policy_events = runtime.get("policy_events")
    if isinstance(policy_events, list):
        summary["policy_events"] = policy_events[:5]
    return summary


def _is_json_scalar(value: object) -> bool:
    return value is None or isinstance(value, (bool, int, float, str))


def _bounded_json_value(value: Any, *, max_items: int = 20, max_chars: int = 500) -> Any:
    if _is_json_scalar(value):
        if isinstance(value, str) and len(value) > max_chars:
            return value[: max(0, max_chars - 3)] + "..."
        return value
    if isinstance(value, (list, tuple)):
        return [
            _bounded_json_value(item, max_items=max_items, max_chars=max_chars)
            for item in list(value)[:max_items]
        ]
    if isinstance(value, dict):
        bounded: dict[str, Any] = {}
        for key in sorted(value, key=str)[:max_items]:
            bounded[str(key)] = _bounded_json_value(
                value[key],
                max_items=max_items,
                max_chars=max_chars,
            )
        return bounded
    return _bounded_text(value, max_chars)


def _surface_runtime_summary_template(
    *,
    selected_surface: str | None,
    required_fields: Sequence[str],
) -> dict[str, Any]:
    fields = tuple(str(field).strip() for field in required_fields if str(field).strip())
    surface = (selected_surface or "").strip()
    if not surface or not fields:
        return {}
    return {
        "selected_surface": surface,
        "required_runtime_fields": fields,
        "candidate_pairs": 0,
        "runtime_observed_pairs": 0,
        "runtime_missing_pairs": 0,
        "_fields": {
            field: {
                "present": 0,
                "missing": 0,
                "empty": 0,
                "failed": 0,
                "values": {},
            }
            for field in fields
        },
    }


def _record_surface_runtime_sample(
    result: RunResult,
    summary: dict[str, Any],
) -> None:
    if not summary:
        return
    summary["candidate_pairs"] += 1
    runtime = getattr(getattr(result, "output", None), "runtime", None)
    fields: dict[str, dict[str, Any]] = summary["_fields"]
    if not isinstance(runtime, dict):
        summary["runtime_missing_pairs"] += 1
        for field_summary in fields.values():
            field_summary["missing"] += 1
        return

    summary["runtime_observed_pairs"] += 1
    for field, field_summary in fields.items():
        if field not in runtime:
            field_summary["missing"] += 1
            continue
        value = runtime[field]
        if _is_empty_runtime_evidence_value(value):
            field_summary["empty"] += 1
        if _is_runtime_error_count_field(field):
            count = _parse_int(value)
            if count is None or count > 0:
                field_summary["failed"] += 1
        elif _is_runtime_true_evidence_field(field) and not _as_truthy(value):
            field_summary["failed"] += 1
        field_summary["present"] += 1
        value_key = _surface_runtime_value_key(value)
        values = field_summary["values"]
        values[value_key] = values.get(value_key, 0) + 1


def _finalize_surface_runtime_summary(summary: dict[str, Any]) -> dict[str, Any]:
    if not summary:
        return {}
    fields: dict[str, dict[str, Any]] = summary.get("_fields") or {}
    return {
        "selected_surface": summary.get("selected_surface"),
        "required_runtime_fields": list(summary.get("required_runtime_fields") or ()),
        "candidate_pairs": summary.get("candidate_pairs", 0),
        "runtime_observed_pairs": summary.get("runtime_observed_pairs", 0),
        "runtime_missing_pairs": summary.get("runtime_missing_pairs", 0),
        "fields": {
            field: {
                "present": field_summary.get("present", 0),
                "missing": field_summary.get("missing", 0),
                "empty": field_summary.get("empty", 0),
                "failed": field_summary.get("failed", 0),
                "numeric_summary": _surface_runtime_numeric_summary(
                    field_summary.get("values") or {}
                ),
                "values": [
                    {"value": value, "count": count}
                    for value, count in sorted(
                        (field_summary.get("values") or {}).items(),
                        key=lambda item: (-int(item[1]), item[0]),
                    )[:5]
                ],
            }
            for field, field_summary in fields.items()
        },
    }


def _surface_runtime_numeric_summary(values: dict[str, int]) -> dict[str, Any]:
    scalar = _numeric_scalar_summary(values)
    mapping = _numeric_mapping_summary(values)
    summary: dict[str, Any] = {}
    if scalar:
        summary["scalar"] = scalar
    if mapping:
        summary["mapping"] = mapping
    return summary


def _numeric_scalar_summary(values: dict[str, int]) -> dict[str, Any]:
    count = 0
    zero_count = 0
    nonzero_count = 0
    positive_count = 0
    negative_count = 0
    weighted_sum = 0.0
    minimum: float | None = None
    maximum: float | None = None
    for value_key, raw_count in values.items():
        parsed = _parse_surface_runtime_value(value_key)
        number = _coerce_number(parsed)
        if number is None:
            continue
        item_count = _safe_int(raw_count)
        if item_count <= 0:
            continue
        count += item_count
        weighted_sum += number * item_count
        minimum = number if minimum is None else min(minimum, number)
        maximum = number if maximum is None else max(maximum, number)
        if abs(number) <= 1e-12:
            zero_count += item_count
        else:
            nonzero_count += item_count
        if number > 0:
            positive_count += item_count
        if number < 0:
            negative_count += item_count
    if count == 0:
        return {}
    return {
        "observed_count": count,
        "weighted_sum": _round_runtime_number(weighted_sum),
        "min": _round_runtime_number(minimum),
        "max": _round_runtime_number(maximum),
        "zero_count": zero_count,
        "nonzero_count": nonzero_count,
        "positive_count": positive_count,
        "negative_count": negative_count,
    }


def _numeric_mapping_summary(values: dict[str, int]) -> dict[str, Any]:
    by_key: dict[str, dict[str, Any]] = {}
    for value_key, raw_count in values.items():
        parsed = _parse_surface_runtime_value(value_key)
        if not isinstance(parsed, dict):
            continue
        item_count = _safe_int(raw_count)
        if item_count <= 0:
            continue
        for key, raw_value in parsed.items():
            if len(by_key) >= 16 and str(key) not in by_key:
                continue
            number = _coerce_number(raw_value)
            if number is None:
                continue
            key_text = str(key)[:80]
            stats = by_key.setdefault(
                key_text,
                {
                    "observed_count": 0,
                    "weighted_sum": 0.0,
                    "min": None,
                    "max": None,
                    "zero_count": 0,
                    "nonzero_count": 0,
                    "positive_count": 0,
                    "negative_count": 0,
                },
            )
            stats["observed_count"] += item_count
            stats["weighted_sum"] += number * item_count
            stats["min"] = number if stats["min"] is None else min(stats["min"], number)
            stats["max"] = number if stats["max"] is None else max(stats["max"], number)
            if abs(number) <= 1e-12:
                stats["zero_count"] += item_count
            else:
                stats["nonzero_count"] += item_count
            if number > 0:
                stats["positive_count"] += item_count
            if number < 0:
                stats["negative_count"] += item_count
    compact: dict[str, Any] = {}
    for key, stats in by_key.items():
        compact[key] = {
            "observed_count": stats["observed_count"],
            "weighted_sum": _round_runtime_number(stats["weighted_sum"]),
            "min": _round_runtime_number(stats["min"]),
            "max": _round_runtime_number(stats["max"]),
            "zero_count": stats["zero_count"],
            "nonzero_count": stats["nonzero_count"],
            "positive_count": stats["positive_count"],
            "negative_count": stats["negative_count"],
        }
    return compact


def _parse_surface_runtime_value(value_key: str) -> Any:
    try:
        return json.loads(value_key)
    except (TypeError, ValueError):
        return value_key


def _coerce_number(value: Any) -> float | None:
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _round_runtime_number(value: float | None) -> float | None:
    if value is None:
        return None
    return round(float(value), 6)


def _surface_runtime_value_key(value: Any) -> str:
    bounded = _bounded_json_value(value, max_items=12, max_chars=240)
    try:
        text = json.dumps(bounded, sort_keys=True, separators=(",", ":"), default=str)
    except TypeError:
        text = str(bounded)
    if len(text) <= 240:
        return text
    return text[:237] + "..."


def _is_empty_runtime_evidence_value(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, tuple, dict, set, frozenset)):
        return len(value) == 0
    return False


def _is_runtime_error_count_field(field_name: str) -> bool:
    return field_name.endswith("_errors") or field_name.endswith("_error_count")


def _is_runtime_true_evidence_field(field_name: str) -> bool:
    return field_name.endswith("_loaded") or field_name.endswith("_executed")


def _parse_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if value.is_integer():
            return int(value)
        return None
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None


def _as_truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    return bool(value)


def _record_runtime_sample(
    fields: dict,
    ratios: list[float],
    deltas_ms: list[float],
) -> None:
    ratio = fields.get("runtime_ratio")
    delta = fields.get("runtime_delta_ms")
    if ratio is not None:
        ratios.append(float(ratio))
    if delta is not None:
        deltas_ms.append(float(delta))


def _build_runtime_stats(
    ratios: list[float],
    deltas_ms: list[float],
) -> dict:
    runtime_pairs = len(deltas_ms)
    regression_count = sum(1 for d in deltas_ms if d > 0)
    return {
        "runtime_ratio_median": statistics.median(ratios) if ratios else None,
        "runtime_delta_median_ms": statistics.median(deltas_ms) if deltas_ms else None,
        "runtime_regression_rate": (
            regression_count / runtime_pairs if runtime_pairs else None
        ),
        "runtime_pairs": runtime_pairs,
    }


def _format_runtime_summary(stats: EvalStats) -> str:
    ratio = (
        f"{stats.runtime_ratio_median:.2f}"
        if stats.runtime_ratio_median is not None
        else "NA"
    )
    delta = (
        f"{stats.runtime_delta_median_ms:.1f}"
        if stats.runtime_delta_median_ms is not None
        else "NA"
    )
    regression = (
        f"{stats.runtime_regression_rate:.2f}"
        if stats.runtime_regression_rate is not None
        else "NA"
    )
    return (
        f"runtime_pairs={stats.runtime_pairs} "
        f"runtime_ratio_median={ratio} "
        f"runtime_delta_median_ms={delta} "
        f"runtime_regression_rate={regression}"
    )


def _aggregate_pairs_to_case_level(
    pairs: List[PairwiseCaseFeedback],
) -> List[CaseLevelResult]:
    """For each case, aggregate across seeds: majority vote → win/loss/tie, median delta.

    T2: This is the core of the case-level statistical unit change.
    """
    by_case: Dict[str, List[PairwiseCaseFeedback]] = defaultdict(list)
    for p in pairs:
        by_case[p.case_id].append(p)

    result = []
    for case_id, case_pairs in by_case.items():
        wins = sum(1 for p in case_pairs if p.comparison == "win")
        losses = sum(1 for p in case_pairs if p.comparison == "loss")
        ties = len(case_pairs) - wins - losses

        # Majority vote across seeds
        if wins > losses and wins > ties:
            majority = "win"
        elif losses > wins and losses > ties:
            majority = "loss"
        else:
            # True tie in vote count (or ties dominate)
            majority = "tie"

        med_delta = statistics.median(p.delta for p in case_pairs)
        metric_deltas: dict[str, float] = {}
        metric_values: dict[str, list[float]] = defaultdict(list)
        for p in case_pairs:
            oc = p.objective_comparison
            if oc is not None and hasattr(oc, "metrics"):
                for m in oc.metrics:
                    metric_values[m.name].append(float(m.signed_delta))
        metric_deltas = {
            name: statistics.median(vals)
            for name, vals in metric_values.items()
            if vals
        }
        result.append(CaseLevelResult(
            case_id=case_id,
            comparison=majority,
            delta=med_delta,
            metric_deltas=metric_deltas,
        ))

    return result


# ---------------------------------------------------------------------------
# Case feedback helpers (unchanged from original)
# ---------------------------------------------------------------------------

def _extract_case_features(case_path: str) -> dict:
    """Extract lightweight features from instance path (MVP: path-level only)."""
    stem = os.path.splitext(os.path.basename(case_path))[0]
    size_bucket = "unknown"
    for tag in ("xlarge", "large", "medium", "small"):
        if tag in stem.lower():
            size_bucket = tag
            break
    return {"path_stem": stem, "size_bucket": size_bucket}


def _aggregate_case_feedback(
    pairs: List[PairwiseCaseFeedback],
) -> List[CaseAggregateFeedback]:
    """Group pair feedback by case_id and compute per-case aggregates."""
    by_case: dict[str, list[PairwiseCaseFeedback]] = defaultdict(list)
    for p in pairs:
        by_case[p.case_id].append(p)

    result = []
    for case_id, case_pairs in by_case.items():
        n = len(case_pairs)
        wins = sum(1 for p in case_pairs if p.comparison == "win")
        losses = sum(1 for p in case_pairs if p.comparison == "loss")
        ties = n - wins - losses
        wr = wins / n if n > 0 else 0.0

        # Dominant result
        mx = max(wins, losses, ties)
        if wins == losses and wins > 0:
            dominant = "mixed"
        elif mx == wins:
            dominant = "win"
        elif mx == losses:
            dominant = "loss"
        else:
            dominant = "tie"

        # Dominant decisive metric (generic)
        decisive_counts: dict[str, int] = defaultdict(int)
        for p in case_pairs:
            oc = p.objective_comparison
            dm = (oc.decisive_metric if oc and hasattr(oc, 'decisive_metric') else None) or "tie"
            decisive_counts[dm] += 1
        dominant_decisive = max(decisive_counts, key=decisive_counts.get)  # type: ignore
        if len(set(decisive_counts.values())) == 1 and len(decisive_counts) > 1:
            dominant_decisive = "mixed"

        # Median deltas per metric (generic)
        metric_deltas: dict[str, list[float]] = defaultdict(list)
        for p in case_pairs:
            oc = p.objective_comparison
            if oc and hasattr(oc, 'metrics'):
                for m in oc.metrics:
                    metric_deltas[m.name].append(m.signed_delta)
        median_deltas = {
            name: statistics.median(vals) for name, vals in metric_deltas.items() if vals
        }

        result.append(CaseAggregateFeedback(
            case_id=case_id,
            n_pairs=n,
            wins=wins,
            losses=losses,
            ties=ties,
            win_rate=wr,
            dominant_result=dominant,
            decisive_metric=dominant_decisive,
            median_deltas=median_deltas,
            seed_consistency=mx / n if n > 0 else 0.0,
            case_features=case_pairs[0].case_features if case_pairs else {},
        ))
    return result


def _build_pattern_summary(
    case_feedback: tuple[CaseAggregateFeedback, ...],
) -> ScreeningPatternSummary:
    """Build code-generated pattern summary from case-level feedback."""
    winning = [c for c in case_feedback if c.dominant_result == "win"]
    losing = [c for c in case_feedback if c.dominant_result == "loss"]
    mixed = [c for c in case_feedback if c.dominant_result == "mixed"]

    wins_by_obj: dict[str, int] = defaultdict(int)
    losses_by_obj: dict[str, int] = defaultdict(int)
    wins_by_size: dict[str, int] = defaultdict(int)
    losses_by_size: dict[str, int] = defaultdict(int)

    for c in winning:
        wins_by_obj[c.decisive_metric] += 1
        wins_by_size[c.case_features.get("size_bucket", "unknown")] += 1
    for c in losing:
        losses_by_obj[c.decisive_metric] += 1
        losses_by_size[c.case_features.get("size_bucket", "unknown")] += 1

    # Generate key observations (rule-based, generic metric names)
    observations: list[str] = []
    for metric, count in losses_by_obj.items():
        if count >= 2 and metric != "tie":
            observations.append(
                f"Most losses decided by {metric}: candidate often worsened this objective."
            )

    # Size pattern
    win_sizes = set(wins_by_size.keys())
    loss_sizes = set(losses_by_size.keys())
    if win_sizes and loss_sizes and not win_sizes.intersection(loss_sizes):
        observations.append(
            f"Candidate wins on {', '.join(sorted(win_sizes))} but loses on {', '.join(sorted(loss_sizes))}."
        )

    if mixed:
        observations.append(
            f"{len(mixed)} case(s) showed seed-sensitive behavior; treat gains there as unstable."
        )

    consistent_wins = tuple(c.case_id for c in winning if c.seed_consistency >= 0.99)
    consistent_losses = tuple(c.case_id for c in losing if c.seed_consistency >= 0.99)
    if consistent_wins:
        observations.append(f"Consistent wins: {', '.join(consistent_wins)}.")
    if consistent_losses:
        observations.append(f"Consistent losses: {', '.join(consistent_losses)}.")

    return ScreeningPatternSummary(
        total_cases=len(case_feedback),
        winning_cases=len(winning),
        losing_cases=len(losing),
        mixed_cases=len(mixed),
        wins_by_decisive_objective=dict(wins_by_obj),
        losses_by_decisive_objective=dict(losses_by_obj),
        wins_by_size_bucket=dict(wins_by_size),
        losses_by_size_bucket=dict(losses_by_size),
        consistent_win_cases=consistent_wins,
        consistent_loss_cases=consistent_losses,
        key_observations=tuple(observations),
    )


# ObjectiveComparison from problem/objectives.py is now used directly.
